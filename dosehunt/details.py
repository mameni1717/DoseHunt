"""Détails d'une fiche au-delà de la teneur : photo, note des avis, ingrédients, valeurs nutritionnelles, attributs.

Ils servent aux cartes du site, aux filtres (sans lactose, sans édulcorant, origine du lait…) et au comparateur.
Tout vient du texte de la fiche : quand la fiche ne dit rien, la valeur reste vide (jamais devinée).
"""
from __future__ import annotations

import html
import json
import re
from typing import Optional

from .collectors.base import html_to_text

# --------------------------------------------------------------------------- page : photo et avis


def _jsonld_nodes(page: str) -> list[dict]:
    out: list[dict] = []
    for m in re.finditer(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page or ""):
        try:
            data = json.loads(m.group(1).strip())
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                out.append(n)
                stack += [v for v in n.values() if isinstance(v, (dict, list))]
            elif isinstance(n, list):
                stack += n
    return out


def page_extras(page: str) -> dict:
    """Photo principale et note moyenne des avis (JSON-LD Product / AggregateRating, sinon og:image)."""
    image = rating = count = None
    for n in _jsonld_nodes(page):
        t = str(n.get("@type", ""))
        if "Product" in t and image is None:
            img = n.get("image")
            if isinstance(img, list):
                img = img[0] if img else None
            if isinstance(img, dict):
                img = img.get("url") or img.get("contentUrl")
            if isinstance(img, str) and img.startswith(("http", "//")):
                image = img
        agg = n.get("aggregateRating") if "Product" in t else (n if "AggregateRating" in t else None)
        if isinstance(agg, dict) and rating is None:
            try:
                r = float(str(agg.get("ratingValue")).replace(",", "."))
                best = float(str(agg.get("bestRating") or 5).replace(",", "."))
                c = int(float(str(agg.get("reviewCount") or agg.get("ratingCount") or 0)))
                if c > 0 and 0 < r <= best:
                    rating, count = round(r * 5 / best, 2), c
            except (TypeError, ValueError):
                pass
    if image is None:
        m = re.search(r'<meta[^>]+property="og:image(?::secure_url)?"[^>]+content="([^"]+)"', page or "", re.I)
        image = html.unescape(m.group(1)) if m else None
    if image and image.startswith("//"):
        image = "https:" + image
    return {"image_url": image, "rating": rating, "review_count": count}


# --------------------------------------------------------------------------- texte : ingrédients, nutrition

_INGR = re.compile(r"(?:liste des )?ingr[ée]dients?(?:\s*\([^)]{0,40}\))?(?:\s*[:\-–]\s*|[ \t]*\n\s*)(.{15,900}?)(?=\n|$|\.\s+(?:[A-ZÉÈ][\wéè ]{2,30}\s*:|Allerg|Peut contenir|Conseil|Information))",
                   re.I | re.S)


def ingredients(text: str) -> Optional[str]:
    for m in _INGR.finditer(text):
        val = re.sub(r"\s+", " ", m.group(1)).strip(" .;")
        if "," in val and not re.search(r"\b(?:de qualité|naturels?|soigneusement)\b.{0,10}$", val[:40], re.I):
            return val[:900]
    return None


def ingredient_count(ingr: Optional[str]) -> Optional[int]:
    """Nombre d'ingrédients de premier niveau (le contenu des parenthèses ne compte pas)."""
    if not ingr:
        return None
    depth, parts, cur = 0, [], ""
    for ch in ingr:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return len([p for p in parts if re.search(r"[^\W\d_]{3}", p)])


NUTRIENTS = {                      # clé → libellé de ligne du tableau
    "energy_kcal": r"[ée]nergie|valeur [ée]nerg[ée]tique",
    "fat": r"mati[eè]res? grasses?|graisses|lipides",
    "saturated": r"(?:-\s*)?dont (?:acides gras )?satur[ée]s|acides gras satur[ée]s",
    "carbs": r"glucides|hydrates de carbone",
    "sugars": r"(?:-\s*)?dont sucres|sucres",
    "fibre": r"fibres(?: alimentaires)?",
    "protein": r"prot[ée]ines?",
    "salt": r"sel\b",
}


def _energy_per_100g(text: str, rx: str) -> Optional[float]:
    """kcal de la colonne « 100 g » (pas de la colonne « par dose ») ; sinon la première valeur en kcal."""
    col = None
    for line in text.split("\n"):
        cells = [c.strip().lower() for c in line.split("|")]
        if len(cells) > 1 and any(re.search(r"100\s*g", c) for c in cells):
            col = next(i for i, c in enumerate(cells) if re.search(r"100\s*g", c))
            header_len = len(cells)
            continue
        if re.match(r"\s*(?:" + rx + ")", line, re.I) and "kcal" in line.lower():
            parts = line.split("|")
            if col is not None:
                idx = col + (len(parts) - header_len if len(parts) > header_len else 0)
                if idx < len(parts):
                    mm = re.search(r"(\d+(?:[.,]\d+)?)\s*kcal", parts[idx], re.I)
                    if mm:
                        return float(mm.group(1).replace(",", "."))
            if col is None:
                mm = re.search(r"(\d+(?:[.,]\d+)?)\s*kcal", line, re.I)
                if mm:
                    return float(mm.group(1).replace(",", "."))
            return None
    return None


def nutrition(text: str) -> dict:
    """Valeurs pour 100 g lues dans le tableau nutritionnel (seulement celles qui y figurent)."""
    from .extract import table_value
    out: dict = {}
    for key, rx in NUTRIENTS.items():
        if key == "energy_kcal":
            val = _energy_per_100g(text, rx)
            if val is not None and 0 <= val <= 900:
                out[key] = val
            continue
        tv = table_value(text, r"(?:" + rx + ")", "100g")
        if tv and tv[1] == "g" and 0 <= tv[0] <= 100:
            out[key] = tv[0]
    return out


# --------------------------------------------------------------------------- attributs pour les filtres

SWEETENERS = {
    "sucralose": r"sucralose|e\s?955",
    "acésulfame K": r"ac[ée]sulfame|e\s?950",
    "aspartame": r"aspartame|e\s?951",
    "stévia": r"st[ée]via|st[ée]viol|e\s?960",
    "cyclamate": r"cyclamate|e\s?952",
    "saccharine": r"saccharine|e\s?954",
    "sucralose ou autre (non précisé)": r"[ée]dulcorants?\b(?!\s*:)",
    "érythritol": r"[ée]rythritol|e\s?968",
    "xylitol": r"xylitol|e\s?967",
    "maltitol": r"maltitol|e\s?965",
}

# Additifs que beaucoup de consommateurs préfèrent éviter (liste factuelle, sans jugement de santé)
WATCHED_ADDITIVES = {
    "sucralose": r"sucralose|e\s?955",
    "acésulfame K": r"ac[ée]sulfame|e\s?950",
    "aspartame": r"aspartame|e\s?951",
    "cyclamate": r"cyclamate|e\s?952",
    "carraghénanes": r"carragh[ée]nane|e\s?407\b",
    "dioxyde de titane": r"dioxyde de titane|e\s?171\b",
    "huile de palme": r"huile de palme|palme\b",
    "sirop de glucose-fructose": r"sirop de glucose[- ]fructose|isoglucose",
    "colorants azoïques": r"e\s?1(?:02|04|10|22|24|29)\b|tartrazine|jaune orang[ée]|rouge allura",
    "polyols (laxatifs à forte dose)": r"maltitol|sorbitol|xylitol|e\s?96[57]\b|e\s?420\b",
}

MILK_ORIGIN = [
    ("FR", r"lait (?:100\s*%\s*)?(?:fran[çc]ais|de france|d['’]origine fran[çc]aise|origine france|collect[ée] en france)|vaches fran[çc]aises"),
    ("IE", r"lait (?:irlandais|d['’]irlande)|origine irlande"),
    ("NL", r"lait (?:n[ée]erlandais|des pays-bas|hollandais)|frieslandcampina"),
    ("DE", r"lait allemand|lait d['’]allemagne"),
    ("NZ", r"nouvelle-z[ée]lande|n[ée]o-z[ée]landais"),
    ("EU", r"lait (?:europ[ée]en|de l['’]ue|d['’]origine europ[ée]enne)|origine ue\b"),
]


def attributes(text: str, ingr: Optional[str]) -> dict:
    low = text.lower()
    att: dict = {}
    if re.search(r"sans lactose|lactose[- ]free|0\s*%\s*(?:de\s*)?lactose|<\s*0[,.]1\s*g\s*de\s*lactose|d[ée]lactos[ée]e?", low):
        att["lactose_free"] = True
    found = []
    if ingr:
        for name, rx in SWEETENERS.items():
            if re.search(rx, ingr, re.I):
                found.append(name)
        if "sucralose ou autre (non précisé)" in found and len(found) > 1:
            found.remove("sucralose ou autre (non précisé)")
        found = [("édulcorant non précisé" if f.startswith("sucralose ou autre") else f) for f in found]
        att["sweeteners"] = found
        att["no_sweetener"] = not found
        att["no_sucralose"] = "sucralose" not in found
        att["watched_additives"] = [n for n, rx in WATCHED_ADDITIVES.items() if re.search(rx, ingr, re.I)]
        att["ingredient_count"] = ingredient_count(ingr)
    elif re.search(r"sans (?:aucun )?[ée]dulcorants?|non [ée]dulcor[ée]|sans sucralose", low):
        att["no_sucralose"] = True
        if re.search(r"sans (?:aucun )?[ée]dulcorants?|non [ée]dulcor[ée]", low):
            att["no_sweetener"] = True
    for code, rx in MILK_ORIGIN:
        if re.search(rx, low):
            att["milk_origin"] = code
            break
    if re.search(r"grass[- ]?fed|vaches? nourries? (?:à|a) l['’]herbe|p[âa]turage", low):
        att["grass_fed"] = True
    return att


def product_details(body_html: str, title: str = "") -> dict:
    text = html_to_text(body_html or "")
    ingr = ingredients(text)
    return {"ingredients": ingr, "nutrition": nutrition(text) or None, "attributes": attributes(title + "\n" + text, ingr)}
