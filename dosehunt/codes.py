"""Relevé automatique des codes promo affichés par les sites (bandeaux, pages d'accueil, fiches).

Cahier des charges : « Promos affichées sur le site → lecture automatique de la page d'accueil et des
pages produits, toutes les 2 à 6 h ». Chaque code est stocké avec ses conditions et sa date de dernière
vérification ; un code qui n'est plus affiché perd de la confiance avec le temps (demi-vie de 90 jours,
cf. pricing.Code.effective_confidence) au lieu de disparaître brutalement.

Formes réelles traitées (relevées le 11/11/2026) :
  Fitadium          « -10% + cadeau dès 80€ : BLACK10 | -15% + cadeau dès 100€ : BLACK15 »
                    « *Offre valable … jusqu'au 20/11/2026 … cumulable avec les promotions Black Month »
  Toutelanutrition  « -20% jusqu'à 69,99 euros d'achat et -25% à partir de 70 euros d'achats ! CODE : DUO20 »
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .collectors.base import html_to_text
from .config import Site
from .http import BlockedByRobots, FetchError, PoliteClient

log = logging.getLogger(__name__)

STOP = {
    "CODE", "CODES", "PROMO", "OFFRE", "OFFRES", "BLACK", "FRIDAY", "NOVEMBER", "LIVRAISON", "GRATUITE", "OFFERTE",
    "NOUVEAU", "NOUVEAUTE", "NOUVEAUTES", "AJOUTER", "PANIER", "SOLDES", "MONTH", "WEEK", "CYBER", "MONDAY",
    "FRANCE", "EURO", "EUROS", "TTC", "HT", "VEGAN", "WHEY", "BCAA", "ZMA", "EAA", "MSM", "DHEA", "EPA", "DHA",
    "AJR", "VNR", "BIO", "ISO", "HACCP", "PURE", "GRATUIT", "CADEAU", "CADEAUX", "MAINTENANT", "VOIR", "TOUT",
    "INFO", "INFOS", "STOCK", "LIMITE", "VALABLE", "MON", "TON", "VOTRE", "CLIQUEZ", "COPIER", "COPIE", "SHOP",
    "FAQ", "CGV", "SAV", "TOP", "NEW", "SALE", "OFF", "FREE", "GIFT", "MEILLEURE", "VENTE", "VENTES",
}
CODE_TOKEN = r"([A-Z][A-Z0-9_-]{3,19})"
PCT = re.compile(r"-\s*(\d{1,2})\s*%|(\d{1,2})\s*%\s*(?:de\s+)?(?:r[ée]duction|remise|off|offerts?)")
MIN_ORDER = re.compile(r"(?:d[èe]s|[àa] partir de|pour)\s*(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:€|euros?)(?:\s*d['’]achats?)?", re.I)
ENDS = re.compile(r"jusqu['’]?\s*au\s*(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", re.I)

# --- espagnol : ajouté aux règles françaises pour les sites en espagnol
STOP_ES = {
    "CODIGO", "CUPON", "CUPONES", "DESCUENTO", "DESCUENTOS", "ENVIO", "ENVIOS", "GRATIS", "OFERTA", "OFERTAS", "REBAJAS",
    "NUEVO", "NUEVOS", "NOVEDADES", "REGALO", "AHORA", "COMPRAR", "CARRITO", "CESTA", "AQUI", "TODO", "TODOS", "TIENDA",
    "VALIDAR", "USAR", "EXTRA", "PROMOCION", "PROMOCIONES", "HASTA", "DESDE", "PEDIDO", "CLIENTES", "IVA",
}
_CODE_ES = re.compile(r"(?i:c[óo]digo|cup[óo]n)(?i:es|s)?\s*(?i:(?:de\s+)?(?:descuento|promocional|promo|regalo))?\s*"
                      r"(?:[:«\"“]|(?i:con))?\s*[«\"“]?\s*" + CODE_TOKEN + r"\b")
PCT_ES = re.compile(r"-\s*(\d{1,2})\s*%|(\d{1,2})\s*%\s*(?:de\s+)?(?:descuento|dto\.?|rebaja|off|extra|adicional)"
                    r"|(?i:\bun)\s+(\d{1,2})\s*%", re.I)
MIN_ORDER_ES = re.compile(r"(?:desde|a partir de|en (?:pedidos|compras) (?:superiores a|de m[áa]s de|desde|a partir de)|"
                          r"por compras? (?:superiores a|de m[áa]s de|desde)|para pedidos (?:superiores a|de m[áa]s de)|"
                          r"m[áa]s de)\s*(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:€|euros?)", re.I)
ENDS_ES = re.compile(r"(?:hasta|v[áa]lido hasta) el\s*(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", re.I)


def _stop(lang: str) -> set:
    return STOP | STOP_ES if lang == "es" else STOP


@dataclass
class FoundCode:
    code: str
    value: Optional[float] = None            # % de remise principal (palier le plus bas)
    tiers: list[dict] = field(default_factory=list)   # [{"min": 0, "pct": 20}, {"min": 70, "pct": 25}]
    min_order: Optional[float] = None
    first_order_only: bool = False
    stackable_with_sale: bool = False         # prudent : ne pas cumuler avec un prix déjà barré, sauf mention
    ends_on: Optional[date] = None
    evidence: str = ""
    up_to: bool = False                       # « jusqu'à -36 % » : remise variable selon les produits
    confidence: Optional[float] = None        # imposée (code vu sur une seule fiche produit : non appliqué)

    def merge(self, other: "FoundCode") -> None:
        if self.value is None and other.value is not None:
            self.value, self.tiers, self.min_order = other.value, other.tiers, other.min_order
        self.first_order_only |= other.first_order_only
        self.stackable_with_sale |= other.stackable_with_sale
        self.ends_on = self.ends_on or other.ends_on
        if other.value is not None and self.value == other.value:
            self.up_to |= other.up_to
        if len(self.evidence) < 40:
            self.evidence = other.evidence or self.evidence


def _segment(text: str, start: int, end: int, prev_end: int, next_start: Optional[int] = None) -> str:
    """Le morceau de phrase qui porte le code : de la dernière coupure (| ou saut de ligne, ou code précédent)
    jusqu'à la coupure suivante, sans déborder sur la phrase du code suivant."""
    left = max(text.rfind("|", 0, start), text.rfind("\n", 0, start), prev_end, start - 220)
    right_cut = [p for p in (text.find("|", end), text.find("\n", end)) if p != -1]
    if next_start is not None:
        sentence_end = max(text.rfind(".", end, next_start), text.rfind("!", end, next_start))
        right_cut.append(sentence_end if sentence_end > end else end)
    right = min(right_cut + [end + 120])
    return text[left + 1:right]


def _tiers(segment: str, lang: str = "fr") -> list[dict]:
    tiers = []
    pcts = PCT if lang != "es" else PCT_ES
    for m in pcts.finditer(segment):
        pct = int(next(g for g in m.groups() if g))
        if not 3 <= pct <= 70:
            continue
        after = segment[m.end():m.end() + (60 if lang != "es" else 90)]
        before = segment[max(0, m.start() - 40):m.start()]
        mo = MIN_ORDER.search(after) or MIN_ORDER.search(before)
        if mo is None and lang == "es":
            mo = MIN_ORDER_ES.search(after) or MIN_ORDER_ES.search(before)
        upto = re.match(r"\s*jusqu['’]?\s*[àa]\s*\d", after)
        minimum = 0.0 if upto or not mo else float(mo.group(1).replace(",", "."))
        tiers.append({"min": minimum, "pct": pct})
    uniq = {(t["min"], t["pct"]): t for t in tiers}
    return sorted(uniq.values(), key=lambda t: t["min"])


def extract_codes(text: str, lang: str = "fr") -> list[FoundCode]:
    found: dict[str, FoundCode] = {}
    stop = _stop(lang)
    patterns = [
        re.compile(r"(?i:code|coupon)(?i:s)?\s*(?i:promo(?:tionnel)?)?\s*(?:[:«\"“]|(?i:avec))?\s*[«\"“]?\s*" + CODE_TOKEN + r"\b"),
        re.compile(r"(?:€|euros?|%)\s*(?:d['’]achats?)?\s*[:=]\s*" + CODE_TOKEN + r"\b"),
    ]
    if lang == "es":                 # « código descuento X », « cupón: X », « usa el código X », « con el código X »
        patterns.append(_CODE_ES)
    hits = sorted({(m.start(1), m.end(1), m.group(1)) for rx in patterns for m in rx.finditer(text)})
    # « avec les codes BLACK10 / BLACK15 » : les codes suivants d'une énumération
    extra = []
    for s, e, c in hits:
        for m in re.finditer(r"\s*(?:/|et|,|ou" + ("|y|o" if lang == "es" else "") + r")\s*" + CODE_TOKEN + r"\b", text[e:e + 60]):
            if m.start() != 0 and not text[e:e + m.start()].strip(" /,") == "":
                break
            extra.append((e + m.start(1), e + m.end(1), m.group(1)))
            e = e + m.end()
    hits = sorted(set(hits + extra))
    hits = [h for h in hits if h[2] not in stop and (re.search(r"\d", h[2]) or len(h[2]) >= 5)]
    prev_end = -1
    for i, (start, end, code) in enumerate(hits):
        next_start = hits[i + 1][0] if i + 1 < len(hits) else None
        seg = _segment(text, start, end, prev_end, next_start)
        prev_end = end
        tiers = _tiers(seg, lang)
        fc = FoundCode(code=code, tiers=tiers, evidence=re.sub(r"\s+", " ", seg).strip()[:300])
        fc.up_to = (bool(re.search(r"jusqu['’]?\s*[àa]\s*-?\s*\d{1,2}\s*%", seg, re.I))
                    or (lang == "es" and bool(re.search(r"hasta\s+(?:un\s+|el\s+)?-?\s*\d{1,2}\s*%", seg, re.I)))) and len(tiers) == 1
        if tiers:
            fc.value = tiers[0]["pct"]
            fc.min_order = tiers[0]["min"] or None
        found.setdefault(code, FoundCode(code=code)).merge(fc)

    # Conditions générales : on lit les mentions proches des codes (notes de bas de bandeau)
    for code, fc in found.items():
        for m in re.finditer(re.escape(code), text):
            window = text[max(0, m.start() - 400):m.end() + 600].lower()
            if re.search(r"premi[èe]re commande|1(?:è|e|ère|re)\s*commande|nouveaux? clients?|bienvenue", window) \
                    or (lang == "es" and re.search(r"primer pedido|primera compra|nuevos? clientes?|bienvenida", window)):
                fc.first_order_only = True
            if re.search(r"(?<!non )cumulable avec (?:les |la |toutes les )?(?:promotions?|promos?|prix barr|offres?)", window) \
                    or (lang == "es" and re.search(r"(?<!no )(?:acumulable|combinable) con (?:las |otras |todas las )?(?:promociones|ofertas|rebajas)", window)):
                fc.stackable_with_sale = True
            near = text[max(0, m.start() - 400):m.end() + 600]
            if (e := ENDS.search(near) or (ENDS_ES.search(near) if lang == "es" else None)):
                d, mth, y = int(e.group(1)), int(e.group(2)), int(e.group(3))
                y = y + 2000 if y < 100 else y
                try:
                    fc.ends_on = fc.ends_on or date(y, mth, d)
                except ValueError:
                    pass
    return [fc for fc in found.values() if fc.value is not None]


def collect_site_codes(site: Site, client: Optional[PoliteClient] = None, pages: Optional[list[str]] = None) -> list[FoundCode]:
    own = client is None
    client = client or PoliteClient(delay_seconds=site.delay_seconds, language=site.language)
    urls = pages or [site.root + "/"] + [u if u.startswith("http") else site.base_url.rstrip("/") + u
                                          for u in (site.filters or {}).get("code_pages", [])]
    merged: dict[str, FoundCode] = {}
    try:
        for url in urls:
            try:
                resp = client.get(url, accept_404=True)
            except (FetchError, BlockedByRobots) as exc:
                log.warning("%s : page de codes ignorée %s (%s)", site.id, url, exc)
                continue
            if resp is None:
                continue
            for fc in extract_codes(html_to_text(resp.text), site.language):
                merged.setdefault(fc.code, FoundCode(code=fc.code)).merge(fc)
    finally:
        if own:
            client.close()
    return list(merged.values())


# Code vu sur UNE seule fiche produit et nulle part ailleurs : peut-être propre à ce produit.
# Affiché, mais sous le seuil de confiance (pas appliqué aux autres produits du site).
PRODUCT_ONLY_CONFIDENCE = 0.45


def survey_site_codes(site: Site, product_urls: Optional[list[str]] = None,
                      client: Optional[PoliteClient] = None) -> tuple[list[FoundCode], int]:
    """Codes affichés sur l'accueil, les pages de codes et quelques fiches produits du site.
    Renvoie (codes, nombre de pages lues) : 0 page lue = site injoignable, les codes connus ne sont pas
    comptés comme disparus. Un code vu sur les pages générales ou sur au moins 2 fiches vaut pour tout le site."""
    own = client is None
    client = client or PoliteClient(delay_seconds=site.delay_seconds, language=site.language)
    general = [site.root + "/"] + [u if u.startswith("http") else site.base_url.rstrip("/") + u
                                   for u in (site.filters or {}).get("code_pages", [])]
    merged: dict[str, FoundCode] = {}
    on_general: set[str] = set()
    product_hits: dict[str, int] = {}
    pages_read = 0
    try:
        for url in general + list(product_urls or []):
            try:
                resp = client.get(url, accept_404=True)
            except (FetchError, BlockedByRobots) as exc:
                log.warning("%s : page de codes ignorée %s (%s)", site.id, url, exc)
                continue
            if resp is None:
                continue
            pages_read += 1
            for fc in extract_codes(html_to_text(resp.text), site.language):
                merged.setdefault(fc.code, FoundCode(code=fc.code)).merge(fc)
                if url in general:
                    on_general.add(fc.code)
                else:
                    product_hits[fc.code] = product_hits.get(fc.code, 0) + 1
    finally:
        if own:
            client.close()
    for code, fc in merged.items():
        if code not in on_general and product_hits.get(code, 0) < 2:
            fc.confidence = PRODUCT_ONLY_CONFIDENCE
    return list(merged.values()), pages_read


# --------------------------------------------------------------------------- livraison offerte

_AMOUNT = r"(?:€\s*(\d{1,3}(?:[.,]\d{1,2})?)|(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:€|euros?\b|eur\b))"
_FROM = r"(?:d[èe]s|des|[àa]\s+partir\s+de|au[- ]del[àa]\s+de|au[- ]dessus\s+de|pour\s+(?:toute\s+)?commande\s+(?:de|sup[ée]rieure\s+[àa]))"
FREE_FROM = [
    # « Livraison offerte dès 49 € », « Livraison Mondial Relay offerte dès 59,90 € », « LIVRAISON GRATUITE AU-DESSUS DE €50 »
    re.compile(r"(?:livraison|frais\s+de\s+port)[^.\n€]{0,45}?(?:offerte|gratuite|offerts?|gratuits?)[^.\n€\d]{0,50}?" + _FROM + r"\s*" + _AMOUNT, re.I),
    # « Dès 60 € d'achat, livraison offerte »
    re.compile(_FROM + r"\s*" + _AMOUNT + r"\s*(?:d['’]achats?)?\s*[:,-]?\s*(?:la\s+)?livraison\s+(?:est\s+)?(?:offerte|gratuite)", re.I),
]
FREE_ALWAYS = re.compile(r"livraison\s+(?:offerte|gratuite)\s+(?:sans\s+minimum|d[èe]s\s+(?:le\s+)?(?:1er|premier)\s+euro|sur\s+toutes?\s+(?:les\s+)?commandes?)", re.I)
FREE_CODE = [
    re.compile(r"livraison\s+(?:offerte|gratuite)[^.\n]{0,60}?code\s*(?:promo\s*)?[:«\"“]?\s*" + CODE_TOKEN + r"\b", re.I),
    re.compile(r"code\s*(?:promo\s*)?[:«\"“]?\s*" + CODE_TOKEN + r"[»\"”]?\s*[^.\n]{0,40}?livraison\s+(?:offerte|gratuite)", re.I),
]


# Espagnol : « Envío gratis a partir de 55€ », « envío gratuito desde 39,90€ », « ENVÍO GRATIS A PARTIR DE €30 »,
# « gastos de envío gratis en pedidos superiores a 49 € », « Envío gratis en 24/48 horas desde 29,99 € ».
# Montant : virgule ou point, symbole avant ou après, pas de \b après €.
_FROM_ES = (r"(?:desde|a\s+partir\s+de|en\s+(?:pedidos|compras)\s+(?:superiores\s+a|de\s+m[áa]s\s+de|desde|a\s+partir\s+de|de)|"
            r"por\s+compras?\s+(?:superiores\s+a|de\s+m[áa]s\s+de|desde)|para\s+pedidos\s+(?:superiores\s+a|de\s+m[áa]s\s+de|desde)|"
            r"(?:al\s+)?gastar|m[áa]s\s+de|superiores?\s+a|\+)")
FREE_FROM_ES = [
    re.compile(r"(?:env[íi]os?|gastos\s+de\s+env[íi]o|entrega)[^.\n€]{0,45}?(?:gratis|gratuitos?|gratuita)[^.\n€]{0,50}?" + _FROM_ES + r"\s*" + _AMOUNT, re.I),
    re.compile(_FROM_ES + r"\s*" + _AMOUNT + r"\s*(?:de\s+compra)?\s*[:,-]?\s*(?:el\s+|los\s+)?(?:env[íi]o|gastos\s+de\s+env[íi]o)\s+"
               r"(?:es\s+|son\s+)?(?:gratis|gratuitos?)", re.I),
]
FREE_ALWAYS_ES = re.compile(r"env[íi]o\s+(?:gratis|gratuito)\s+(?:sin\s+(?:pedido\s+|compra\s+)?m[íi]nim[oa]|en\s+todos\s+(?:los\s+)?pedidos|"
                            r"desde\s+el\s+primer\s+euro)", re.I)
FREE_CODE_ES = [
    re.compile(r"env[íi]o\s+(?:gratis|gratuito)[^.\n]{0,60}?(?:c[óo]digo|cup[óo]n)\s*(?:de\s+descuento\s*|promocional\s*)?[:«\"“]?\s*" + CODE_TOKEN + r"\b", re.I),
    re.compile(r"(?:c[óo]digo|cup[óo]n)\s*(?:de\s+descuento\s*|promocional\s*)?[:«\"“]?\s*" + CODE_TOKEN + r"[»\"”]?\s*[^.\n]{0,40}?env[íi]o\s+(?:gratis|gratuito)", re.I),
]


def shipping_info(text: str, lang: str = "fr") -> tuple[Optional[float], list[str], str]:
    """(seuil de livraison offerte en €, codes « livraison offerte », extrait) lus dans une page du site.

    Le seuil le plus souvent cité l'emporte (un bandeau répété sur la page compte plusieurs fois)."""
    counts: dict[float, int] = {}
    evidence = ""
    for rx in FREE_FROM + (FREE_FROM_ES if lang == "es" else []):
        for m in rx.finditer(text):
            v = float((m.group(1) or m.group(2)).replace(",", "."))
            if 5 <= v <= 300:
                counts[v] = counts.get(v, 0) + 1
                evidence = evidence or re.sub(r"\s+", " ", m.group(0))[:160]
    threshold = max(counts, key=lambda k: (counts[k], -k)) if counts else None
    if threshold is None and (m := FREE_ALWAYS.search(text) or (FREE_ALWAYS_ES.search(text) if lang == "es" else None)):
        threshold, evidence = 0.0, re.sub(r"\s+", " ", m.group(0))[:160]
    codes = []
    stop = _stop(lang)
    for rx in FREE_CODE + (FREE_CODE_ES if lang == "es" else []):
        for m in rx.finditer(text):
            c = m.group(1)
            if c not in stop and c not in codes and (re.search(r"\d", c) or len(c) >= 5):
                codes.append(c)
    return threshold, codes, evidence


def collect_site_shipping(site: Site, client: Optional[PoliteClient] = None) -> tuple[Optional[float], list[str], str]:
    own = client is None
    client = client or PoliteClient(delay_seconds=site.delay_seconds, language=site.language)
    pages = [site.root + "/"] + [u if u.startswith("http") else site.base_url.rstrip("/") + u
                                 for u in (site.filters or {}).get("shipping_pages", [])]
    best: tuple[Optional[float], list[str], str] = (None, [], "")
    try:
        for url in pages:
            try:
                resp = client.get(url, accept_404=True)
            except (FetchError, BlockedByRobots):
                continue
            if resp is None:
                continue
            th, codes, ev = shipping_info(html_to_text(resp.text), site.language)
            if th is not None and best[0] is None:
                best = (th, best[1], ev)
            best = (best[0], list(dict.fromkeys(best[1] + codes)), best[2])
    finally:
        if own:
            client.close()
    return best
