"""Pays de fabrication d'un produit, lu dans le texte de la fiche.

On ne retient que des formules de fabrication explicites (« fabriqué en France », « made in France »).
« Conçu en France », « conditionné en France », « marque française » ou « lait français » ne disent pas où le produit est fabriqué :
ils ne comptent pas. Le pays est rendu en code ISO (FR, IT…) pour servir à n'importe quelle version du site.
"""
from __future__ import annotations

import re
from typing import Optional

from .collectors.base import html_to_text

# Nom du pays tel qu'il apparaît après « fabriqué en / made in » → code ISO
COUNTRIES = {
    "FR": r"france",
    "BE": r"belgique|belgium",
    "DE": r"allemagne|germany",
    "IT": r"italie|italy",
    "ES": r"espagne|spain",
    "PT": r"portugal",
    "NL": r"pays[- ]bas|hollande|netherlands|holland",
    "PL": r"pologne|poland",
    "HU": r"hongrie|hungary",
    "GB": r"royaume[- ]uni|angleterre|united kingdom|england|\buk\b",
    "CH": r"suisse|switzerland",
    "AT": r"autriche|austria",
    "SE": r"su[eè]de|sweden",
    "IE": r"irlande|ireland",
    "US": r"[ée]tats[- ]unis|usa|united states",
    "CA": r"canada",
}

_MADE = (r"(?:(?:con[çc]ue?s?|d[ée]velopp[ée]e?s?|formul[ée]e?s?|conditionn[ée]e?s?)\s+et\s+)?"
         r"(?:(?:fabriqu[ée]e?s?|manufactur[ée]e?s?|[ée]labor[ée]e?s?|made|manufactured|produced)"
         r"(?:\s+(?:exclusivement|uniquement|int[ée]gralement|enti[eè]rement|100\s*%|localement|ici|par nos soins|"
         r"dans nos (?:usines|laboratoires|ateliers)|in our (?:factory|facilities)))?"
         r"|produite?s?)"
         r"\s+(?:en|au|aux|in|dans le|dans les)\s+")
_ADJ = {"FR": r"fabrication\s+(?:100\s*%\s*)?fran[çc]aise|origine\s+france\s+garantie|🇫🇷\s*fabriqu"}
_NEG = re.compile(r"\b(?:pas|non|ni)\b[^.\n]{0,15}$", re.I)


def detect_origin(body_html: str, title: str = "") -> tuple[Optional[str], Optional[str]]:
    """(code pays, extrait qui le prouve), ou (None, None) si la fiche ne le dit pas clairement."""
    text = (title + "\n" + html_to_text(body_html or "")).replace(" ", " ")
    hits: list[tuple[int, str, str]] = []
    for code, names in COUNTRIES.items():
        for m in re.finditer(r"(?:" + _MADE + r"|(?:pays|lieu) de (?:fabrication|production)\s*[:|]\s*|made in:?\s*)(?:" + names + r")\b",
                             text, re.I):
            if _NEG.search(text[max(0, m.start() - 20):m.start()]):
                continue                                  # « n'est pas fabriqué en France »
            hits.append((m.start(), code, m.group(0)))
        if code in _ADJ:
            hits += [(m.start(), code, m.group(0)) for m in re.finditer(_ADJ[code], text, re.I)]
    if not hits:
        return None, None
    codes = {c for _, c, _ in hits}
    if len(codes) > 1:
        return None, None                                 # plusieurs pays cités : on ne tranche pas
    pos, code, ev = min(hits)
    snippet = re.sub(r"\s+", " ", text[max(0, pos - 40):pos + len(ev) + 40]).strip()
    return code, snippet[:200]
