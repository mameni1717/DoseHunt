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


def _tiers(segment: str) -> list[dict]:
    tiers = []
    for m in PCT.finditer(segment):
        pct = int(m.group(1) or m.group(2))
        if not 3 <= pct <= 70:
            continue
        after = segment[m.end():m.end() + 60]
        before = segment[max(0, m.start() - 40):m.start()]
        mo = MIN_ORDER.search(after) or MIN_ORDER.search(before)
        upto = re.match(r"\s*jusqu['’]?\s*[àa]\s*\d", after)
        minimum = 0.0 if upto or not mo else float(mo.group(1).replace(",", "."))
        tiers.append({"min": minimum, "pct": pct})
    uniq = {(t["min"], t["pct"]): t for t in tiers}
    return sorted(uniq.values(), key=lambda t: t["min"])


def extract_codes(text: str) -> list[FoundCode]:
    found: dict[str, FoundCode] = {}
    patterns = [
        re.compile(r"(?i:code|coupon)(?i:s)?\s*(?i:promo(?:tionnel)?)?\s*(?:[:«\"“]|(?i:avec))?\s*[«\"“]?\s*" + CODE_TOKEN + r"\b"),
        re.compile(r"(?:€|euros?|%)\s*(?:d['’]achats?)?\s*[:=]\s*" + CODE_TOKEN + r"\b"),
    ]
    hits = sorted({(m.start(1), m.end(1), m.group(1)) for rx in patterns for m in rx.finditer(text)})
    # « avec les codes BLACK10 / BLACK15 » : les codes suivants d'une énumération
    extra = []
    for s, e, c in hits:
        for m in re.finditer(r"\s*(?:/|et|,|ou)\s*" + CODE_TOKEN + r"\b", text[e:e + 60]):
            if m.start() != 0 and not text[e:e + m.start()].strip(" /,") == "":
                break
            extra.append((e + m.start(1), e + m.end(1), m.group(1)))
            e = e + m.end()
    hits = sorted(set(hits + extra))
    hits = [h for h in hits if h[2] not in STOP and (re.search(r"\d", h[2]) or len(h[2]) >= 5)]
    prev_end = -1
    for i, (start, end, code) in enumerate(hits):
        next_start = hits[i + 1][0] if i + 1 < len(hits) else None
        seg = _segment(text, start, end, prev_end, next_start)
        prev_end = end
        tiers = _tiers(seg)
        fc = FoundCode(code=code, tiers=tiers, evidence=re.sub(r"\s+", " ", seg).strip()[:300])
        fc.up_to = bool(re.search(r"jusqu['’]?\s*[àa]\s*-?\s*\d{1,2}\s*%", seg, re.I)) and len(tiers) == 1
        if tiers:
            fc.value = tiers[0]["pct"]
            fc.min_order = tiers[0]["min"] or None
        found.setdefault(code, FoundCode(code=code)).merge(fc)

    # Conditions générales : on lit les mentions proches des codes (notes de bas de bandeau)
    for code, fc in found.items():
        for m in re.finditer(re.escape(code), text):
            window = text[max(0, m.start() - 400):m.end() + 600].lower()
            if re.search(r"premi[èe]re commande|1(?:è|e|ère|re)\s*commande|nouveaux? clients?|bienvenue", window):
                fc.first_order_only = True
            if re.search(r"(?<!non )cumulable avec (?:les |la |toutes les )?(?:promotions?|promos?|prix barr|offres?)", window):
                fc.stackable_with_sale = True
            if (e := ENDS.search(text[max(0, m.start() - 400):m.end() + 600])):
                d, mth, y = int(e.group(1)), int(e.group(2)), int(e.group(3))
                y = y + 2000 if y < 100 else y
                try:
                    fc.ends_on = fc.ends_on or date(y, mth, d)
                except ValueError:
                    pass
    return [fc for fc in found.values() if fc.value is not None]


def collect_site_codes(site: Site, client: Optional[PoliteClient] = None, pages: Optional[list[str]] = None) -> list[FoundCode]:
    own = client is None
    client = client or PoliteClient(delay_seconds=site.delay_seconds)
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
            for fc in extract_codes(html_to_text(resp.text)):
                merged.setdefault(fc.code, FoundCode(code=fc.code)).merge(fc)
    finally:
        if own:
            client.close()
    return list(merged.values())
