"""Calcul du prix final et des trois modes de comparaison (cahier des charges, « Règles de calcul »).

P_final = P_catalogue − remise du meilleur code applicable
Prix comparé = P_final / (kg de produit | quantité d'actif | nombre d'unités)
Tous les calculs portent sur le contenant entier, jamais sur la portion déclarée.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .config import categories, codes_config
from .models import ActiveContent, Format

DEFAULT_SERVING_G = {"whey": 30, "preworkout": 10, "collagene": 10, "creatine": 3, "glutamine": 5}


# Un code relevé sur le site et absent de 2 relevés de suite (environ 16 h) n'est plus appliqué.
MISSED_RUNS_LIMIT = 2


@dataclass
class Code:
    code: str
    site: str
    country: str
    discount_type: str
    value: float
    first_order_only: bool = False
    stackable_with_sale: bool = True
    applies_to: object = "all"
    min_order: Optional[float] = None
    confidence: float = 0.5
    last_confirmed: Optional[date] = None
    votes_ok: int = 0
    votes_ko: int = 0
    source: str = ""
    ends_on: Optional[date] = None
    tiers: Optional[list] = None          # [{"min": 0, "pct": 20}, {"min": 70, "pct": 25}]
    origin: str = "manual"
    missed_runs: int = 0                  # code relevé automatiquement mais absent des derniers relevés

    def percent_for(self, price: float) -> Optional[float]:
        """Remise applicable à un panier contenant ce seul produit (paliers compris)."""
        if self.tiers:
            ok = [t["pct"] for t in self.tiers if price >= (t.get("min") or 0)]
            return max(ok) if ok else None
        if self.min_order and price < self.min_order:
            return None
        return self.value

    def effective_confidence(self, today: Optional[date] = None) -> float:
        """Baisse avec l'âge de la dernière confirmation et les signalements « ne marche plus »."""
        today = today or date.today()
        conf = self.confidence
        if self.last_confirmed:
            age = (today - self.last_confirmed).days
            conf *= 0.5 ** (max(age, 0) / 90)          # demi-vie de 90 jours
        conf += 0.05 * min(self.votes_ok, 4)
        conf -= 0.15 * self.votes_ko
        if self.ends_on and today > self.ends_on:
            conf = 0
        if self.origin == "auto" and self.missed_runs >= MISSED_RUNS_LIMIT:
            conf = 0                                   # retiré du site depuis 2 relevés : plus appliqué
        return max(0.0, min(1.0, conf))


def load_codes() -> list[Code]:
    out = []
    for c in codes_config().get("codes", []):
        fields = {k: v for k, v in c.items() if k in Code.__dataclass_fields__}
        out.append(Code(**fields))
    return out


@dataclass
class AppliedCode:
    code: Code
    final: float
    discount: float


def best_code(site_id: str, country: str, category: str, price: float, on_sale: bool,
              codes: list[Code], *, first_order: bool = False, today: Optional[date] = None) -> Optional[AppliedCode]:
    threshold = codes_config().get("min_confidence", 0.5)
    best: Optional[AppliedCode] = None
    for c in codes:
        if c.site != site_id or c.country != country:
            continue
        if c.first_order_only and not first_order:
            continue
        if on_sale and not c.stackable_with_sale:
            continue
        if c.applies_to != "all" and category not in (c.applies_to or []):
            continue
        if c.effective_confidence(today) < threshold:
            continue
        if c.discount_type == "free_shipping":
            continue                                  # livraison offerte : affichée, ne change pas le prix du produit
        if c.discount_type == "percent":
            pct = c.percent_for(price)
            if pct is None:
                continue
            discount = price * pct / 100
        else:
            if c.min_order and price < c.min_order:
                continue
            discount = min(c.value, price)
        final = round(price - discount, 2)
        if best is None or final < best.final:
            best = AppliedCode(c, final, round(discount, 2))
    return best


@dataclass
class Computed:
    final_price: float
    code: Optional[str]
    total_active: Optional[float]      # dans l'unité de l'actif (g, mg, UI)
    active_unit: str
    dose_value: Optional[float]        # prix par dose d'actif (€/kg de protéine, €/g de zinc…)
    kg_value: Optional[float]          # prix par kg de produit
    unit_value: Optional[float]        # prix par unité (barre, gélule) ou par portion
    unit_label: str
    calc: list[str]


# Lignes du calcul affichées sur le site (« Voir le calcul ») : dans la langue du site. Le site web retrouve la ligne
# du contenu par son premier mot (« Contenu », « Contenido »).
_CALC = {
    "fr": {"price": "Prix affiché : {p:.2f} €", "code": "Code {c} : -{d:.2f} € → {f:.2f} €", "nocode": "Code : aucun → {f:.2f} €",
           "c100": "Contenu : {g:g} g × {s} = {t:g} {u} d'actif", "per100": "{a:g} {u} pour 100 g",
           "cserv": "Contenu : {g:g} g ÷ portion de {a:g} g = {t:.0f} portions",
           "cunit": "Contenu : {n} unités × {a:g} {u} = {t:g} {u} d'actif"},
    "es": {"price": "Precio mostrado: {p:.2f} €", "code": "Código {c}: -{d:.2f} € → {f:.2f} €", "nocode": "Código: ninguno → {f:.2f} €",
           "c100": "Contenido: {g:g} g × {s} = {t:g} {u} de activo", "per100": "{a:g} {u} por 100 g",
           "cserv": "Contenido: {g:g} g ÷ dosis de {a:g} g = {t:.0f} dosis",
           "cunit": "Contenido: {n} unidades × {a:g} {u} = {t:g} {u} de activo"},
}


def compute(category: str, price: float, fmt: Format, ac: ActiveContent, applied: Optional[AppliedCode],
            lang: str = "fr") -> Computed:
    c = categories()[category]
    T = _CALC.get(lang, _CALC["fr"])
    final = applied.final if applied else price
    calc = [T["price"].format(p=price)]
    calc.append(T["code"].format(c=applied.code.code, d=applied.discount, f=final) if applied else T["nocode"].format(f=final))

    grams, units = fmt.total_grams, fmt.total_units
    total_active = None
    if ac.basis == "per_100g" and grams:
        total_active = grams * ac.amount / 100
        share = f"{ac.amount:g} %" if ac.unit == "g" else T["per100"].format(a=ac.amount, u=ac.unit)
        calc.append(T["c100"].format(g=grams, s=share, t=total_active, u=ac.unit))
    elif ac.basis == "per_serving" and grams:
        total_active = grams / ac.amount                 # nombre de portions dans le contenant
        calc.append(T["cserv"].format(g=grams, a=ac.amount, t=total_active))
    elif ac.basis == "per_unit" and units:
        total_active = units * ac.amount
        calc.append(T["cunit"].format(n=units, a=ac.amount, u=ac.unit, t=total_active))

    dose = None
    if total_active and ac.basis == "per_serving":
        dose = final / total_active                       # prix d'une portion
        calc.append(f"{c['dose_label']} : {dose:.2f}")
    elif total_active:
        if ac.unit == "g":
            div = c.get("dose_divisor_g", 1000)
            dose = final / (total_active / div)
        elif ac.unit == "mg":
            div_mg = c.get("dose_divisor_mg") or c.get("dose_divisor_g", 1000) * 1000
            dose = final / (total_active / div_mg)
        elif ac.unit == "UI":
            dose = final / (total_active / c.get("dose_divisor_ui", 100000))
        calc.append(f"{c['dose_label']} : {dose:.2f}")

    kg = final / (grams / 1000) if grams else None
    if ac.basis == "per_unit" and units:
        unit_value, unit_label = final / units, f"€/{fmt.unit_word or 'unité'}"
    elif grams and ac.basis == "per_serving":
        unit_value, unit_label = final / (grams / ac.amount), f"€/portion de {ac.amount:g} g"
    elif grams:
        serving = c.get("serving_g") or DEFAULT_SERVING_G.get(category, 30)
        unit_value, unit_label = final / (grams / serving), f"€/portion de {serving} g"
    else:
        unit_value, unit_label = None, ""
    r = lambda x: round(x, 4) if x is not None else None
    return Computed(final, applied.code.code if applied else None, r(total_active), ac.unit,
                    r(dose), r(kg), r(unit_value), unit_label, calc)
