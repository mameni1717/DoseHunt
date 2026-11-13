"""Pays de fabrication d'un produit, lu dans le texte de la fiche.

On ne retient que des formules de fabrication explicites (« fabriqué en France », « made in France »).
« Conçu en France », « conditionné en France », « marque française » ou « lait français » ne disent pas où le produit est fabriqué :
ils ne comptent pas. Le pays est rendu en code ISO (FR, IT…) pour servir à n'importe quelle version du site.
"""
from __future__ import annotations

import html
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

# --- espagnol : ajouté aux règles françaises pour les sites en espagnol
COUNTRIES_ES = {
    "FR": r"francia", "BE": r"b[ée]lgica", "DE": r"alemania", "IT": r"italia", "ES": r"espa[ñn]a", "NL": r"pa[íi]ses bajos|holanda",
    "PL": r"polonia", "HU": r"hungr[íi]a", "GB": r"(?:el\s+)?reino unido|inglaterra", "CH": r"suiza", "AT": r"austria",
    "SE": r"suecia", "IE": r"irlanda", "US": r"(?:los\s+)?estados unidos|ee\.?\s?uu\.?", "CA": r"canad[áa]",
}
# « fabricado en España », « elaborado en », « hecho en », « se fabrica en el Reino Unido », « desarrollado y fabricado en
# Alemania ». « Producida en » n'est pas retenu : sur les fiches, il désigne la matière première (« Creapure producida en Alemania »).
_MADE_ES = (r"(?:(?:dise[ñn]ad[oa]s?|desarrollad[oa]s?|formulad[oa]s?|envasad[oa]s?)\s+y\s+)?"
            r"(?:(?:fabricad[oa]s?|elaborad[oa]s?|hech[oa]s?|manufacturad[oa]s?|se\s+(?:fabrica|elabora|hace)n?)"
            r"(?:\s+(?:exclusivamente|[úu]nicamente|[íi]ntegramente|enteramente|100\s*%|localmente|aqu[íi]|"
            r"en nuestras? (?:f[áa]bricas?|instalaciones|laboratorios?)))?)"
            r"\s+(?:en|in)\s+(?:el\s+|los\s+)?")
_ADJ_ES = {"ES": r"fabricaci[óo]n\s+(?:100\s*%\s*)?espa[ñn]ola"}
_NEG_ES = re.compile(r"\b(?:no|ni)\b[^.\n]{0,15}$", re.I)


def detect_origin(body_html: str, title: str = "", lang: str = "fr") -> tuple[Optional[str], Optional[str]]:
    """(code pays, extrait qui le prouve), ou (None, None) si la fiche ne le dit pas clairement."""
    text = (title + "\n" + html_to_text(body_html or "")).replace(" ", " ")
    hits: list[tuple[int, str, str]] = []
    if lang == "es":
        for code, names in COUNTRIES.items():
            names = names + ("|" + COUNTRIES_ES[code] if code in COUNTRIES_ES else "")
            for m in re.finditer(r"(?:" + _MADE_ES + r"|(?:pa[íi]s|lugar) de (?:fabricaci[óo]n|producci[óo]n)\s*[:|]\s*|made in:?\s*)(?:"
                                 + names + r")\b", text, re.I):
                if _NEG_ES.search(text[max(0, m.start() - 20):m.start()]):
                    continue                              # « no está fabricado en España »
                hits.append((m.start(), code, m.group(0)))
            if code in _ADJ_ES:
                hits += [(m.start(), code, m.group(0)) for m in re.finditer(_ADJ_ES[code], text, re.I)]
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
    return code, sentence_around(text, pos, pos + len(ev))


def sentence_around(text: str, start: int, end: int, limit: int = 160) -> str:
    """La phrase qui contient la mention, coupée proprement (pas de mot tronqué au début ou à la fin)."""
    left = max(text.rfind(sep, 0, start) for sep in (". ", "\n", "! ", "? ", " | ", "•"))
    left = 0 if left < 0 else left + 1
    rights = [i for i in (text.find(sep, end) for sep in (". ", "\n", "! ", "? ", " | ", "•")) if i >= 0]
    right = min(rights) if rights else len(text)
    s = re.sub(r"\s+", " ", text[left:right]).strip(" .|•-–")
    if len(s) > limit:                                   # trop long : centré sur la mention, coupé aux espaces
        m0 = s.lower().find(text[start:end].lower()[:20])
        a = max(0, m0 - 60)
        b = min(len(s), max(m0, 0) + len(text[start:end]) + 60)
        a = s.find(" ", a) + 1 if a > 0 else 0
        b = s.rfind(" ", 0, b) if b < len(s) else b
        s = ("…" if a > 0 else "") + s[a:b].strip() + ("…" if b < len(s) else "")
    return s[:200]


def origin_text_from_page(page: str, lang: str = "fr") -> str:
    """Endroits de la page où les marques écrivent l'origine hors description : méta-descriptions et zone d'achat
    (badges « Fabriqué en France » sous le bouton). Pas la page entière : menus et pieds de page ont souvent une
    rubrique « Made in France » qui ne dit rien du produit affiché."""
    if not page:
        return ""
    parts = [html.unescape(m.group(1)) for m in re.finditer(
        r'<meta[^>]+(?:name|property)="(?:description|og:description)"[^>]+content="([^"]*)"', page, re.I)]
    clean = re.sub(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>", " ", page)
    clean = re.sub(r"(?is)<(header|nav|footer)\b.*?</\1>", " ", clean)
    text = html.unescape(re.sub(r"<[^>]+>", " ", clean))
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"ajouter au panier|add to cart|acheter maintenant|buy now", text, re.I)
    if not m and lang == "es":
        m = re.search(r"a[ñn]adir al carrito|a[ñn]adir a la cesta|comprar ahora", text, re.I)
    if m:
        parts.append(text[max(0, m.start() - 600):m.end() + 600])
    return "\n".join(f"<p>{html.escape(p)}</p>" for p in parts)
