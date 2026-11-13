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


def page_extras(page: str, base_url: str = "") -> dict:
    """Photo principale et note moyenne des avis.

    Photo : og:image d'abord (celle que le site choisit pour le partage, presque toujours la photo du produit),
    puis l'image du JSON-LD Product. Les adresses relatives sont complétées avec l'adresse de la page.
    """
    from urllib.parse import urljoin
    image = rating = count = None
    og = None
    for m in re.finditer(r'<meta[^>]+(?:property|name)="(?:og:image(?::secure_url)?|twitter:image)"[^>]+content="([^"]+)"|'
                         r'<meta[^>]+content="([^"]+)"[^>]+(?:property|name)="(?:og:image|twitter:image)"', page or "", re.I):
        cand = html.unescape(m.group(1) or m.group(2) or "")
        if cand and not re.search(r"logo|favicon|placeholder|default[-_]?image", cand, re.I):
            og = cand
            break
    for n in _jsonld_nodes(page):
        t = str(n.get("@type", ""))
        if "Product" in t and image is None:
            img = n.get("image")
            if isinstance(img, list):
                img = img[0] if img else None
            if isinstance(img, dict):
                img = img.get("url") or img.get("contentUrl")
            if isinstance(img, str) and img.startswith(("http", "/")):
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
    image = og or image
    if image and image.startswith("//"):
        image = "https:" + image
    if image and image.startswith("http://"):
        image = "https://" + image[7:]                   # page en https : une image http serait bloquée
    if image and not image.startswith("http") and base_url:
        image = urljoin(base_url, image)
    if image and not image.startswith("http"):
        image = None
    return {"image_url": image, "rating": rating, "review_count": count}


# --------------------------------------------------------------------------- texte : ingrédients, nutrition

_INGR = re.compile(r"(?:liste des )?ingr[ée]dients?(?:\s*\([^)]{0,40}\))?(?:\s*[:\-–]\s*|[ \t]*\n\s*)(.{15,900}?)(?=\n|$|\.\s+(?:[A-ZÉÈ][\wéè ]{2,30}\s*:|Allerg|Peut contenir|Conseil|Information))",
                   re.I | re.S)


# Espagnol : « Ingredientes: … » ; un mode d'emploi (« modo de empleo, mezclar, tomar, ml de agua, shaker, minutos »)
# n'est jamais pris pour une liste d'ingrédients.
_INGR_ES = re.compile(r"(?:lista de )?ingredientes(?:\s*\([^)]{0,40}\))?(?:\s*[:\-–]\s*|[ \t]*\n\s*)(.{15,900}?)"
                      r"(?=\n|$|\.\s+(?:[A-ZÉÈÁÍÓÚ][\wéèáíóúñ ]{2,30}\s*:|Al[ée]rg|Puede contener|Modo de empleo|Informaci[óo]n|Consejo|Para al[ée]rgenos))",
                      re.I | re.S)
_INSTRUCTIONS_ES = re.compile(r"\b(?:porci[óo]n(?:es)?|raci[óo]n(?:es)?|dosis|mezcl\w*|tomar|toma|consum\w*|ml de agua|shaker|"
                              r"antes de(?:l| su)?|minutos?|disolver|cacitos?|modo de empleo)\b", re.I)


def ingredients(text: str, lang: str = "fr") -> Optional[str]:
    for m in _INGR.finditer(text):
        val = re.sub(r"\s+", " ", m.group(1)).strip(" .;")
        if re.search(r"\b(?:portions?|dose|m[ée]lang|consomm|ml d.eau|shaker|avant (?:votre|l.)|minutes?)\b", val[:120], re.I):
            continue                                     # mode d'emploi pris pour une liste d'ingrédients
        if "," in val and not re.search(r"\b(?:de qualité|naturels?|soigneusement)\b.{0,10}$", val[:40], re.I):
            return val[:900]
    if lang == "es":
        for m in _INGR_ES.finditer(text):
            val = re.sub(r"\s+", " ", m.group(1)).strip(" .;")
            if _INSTRUCTIONS_ES.search(val[:120]):
                continue
            if "," in val and not re.search(r"\b(?:de calidad|naturales|cuidadosamente)\b.{0,10}$", val[:40], re.I):
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
# Espagnol : ajoutés aux libellés français (« Valor energético, Grasas, de las cuales saturadas, Hidratos de carbono… »)
NUTRIENTS_ES = {
    "energy_kcal": r"valor energ[ée]tico|energ[íi]a",
    "fat": r"grasas(?: totales)?|l[íi]pidos",
    "saturated": r"(?:-\s*)?de las cuales,?\s*(?:grasas\s+)?saturadas|(?:[áa]cidos\s+)?grasas saturadas|saturadas",
    "carbs": r"hidratos de carbono|carbohidratos",
    "sugars": r"(?:-\s*)?de los cuales,?\s*az[úu]cares|az[úu]cares",
    "fibre": r"fibra(?: alimentaria| diet[ée]tica)?",
    "protein": r"prote[íi]nas?",
    "salt": r"sal\b",
}


def _nutrients(lang: str) -> dict:
    if lang != "es":
        return NUTRIENTS
    return {k: v + "|" + NUTRIENTS_ES[k] for k, v in NUTRIENTS.items()}


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


def nutrition(text: str, lang: str = "fr") -> dict:
    """Valeurs pour 100 g lues dans le tableau nutritionnel (seulement celles qui y figurent)."""
    from .extract import table_value
    out: dict = {}
    for key, rx in _nutrients(lang).items():
        if key == "energy_kcal":
            val = _energy_per_100g(text, rx)
            if val is not None and 0 <= val <= 900:
                out[key] = val
            continue
        tv = table_value(text, r"(?:" + rx + ")", "100g", lang=lang)
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

# Espagnol : motifs ajoutés aux motifs français (mêmes clés, mêmes libellés affichés).
SWEETENERS_ES = {
    "sucralose": r"sucralosa", "acésulfame K": r"acesulfamo", "aspartame": r"aspartamo", "stévia": r"stevia|esteviol",
    "cyclamate": r"ciclamato", "saccharine": r"sacarina", "sucralose ou autre (non précisé)": r"edulcorantes?\b(?!\s*:)",
    "érythritol": r"eritritol", "xylitol": r"xilitol", "maltitol": r"maltitol",
}
WATCHED_ADDITIVES_ES = {
    "sucralose": r"sucralosa", "acésulfame K": r"acesulfamo", "aspartame": r"aspartamo", "cyclamate": r"ciclamato",
    "carraghénanes": r"carragenina|carragenanos?", "dioxyde de titane": r"di[óo]xido de titanio",
    "huile de palme": r"aceite de palma|\bpalma\b", "sirop de glucose-fructose": r"jarabe de glucosa[- ]fructosa",
    "colorants azoïques": r"amarillo anaranjado|rojo allura", "polyols (laxatifs à forte dose)": r"sorbitol|xilitol",
}


def _merged(base: dict, extra: dict, lang: str) -> dict:
    return base if lang != "es" else {k: v + ("|" + extra[k] if k in extra else "") for k, v in base.items()}


MILK_ORIGIN = [
    ("FR", r"lait (?:100\s*%\s*)?(?:fran[çc]ais|de france|d['’]origine fran[çc]aise|origine france|collect[ée] en france)|vaches fran[çc]aises"),
    ("IE", r"lait (?:irlandais|d['’]irlande)|origine irlande"),
    ("NL", r"lait (?:n[ée]erlandais|des pays-bas|hollandais)|frieslandcampina"),
    ("DE", r"lait allemand|lait d['’]allemagne"),
    ("NZ", r"nouvelle-z[ée]lande|n[ée]o-z[ée]landais"),
    ("EU", r"lait (?:europ[ée]en|de l['’]ue|d['’]origine europ[ée]enne)|origine ue\b"),
]


MILK_ORIGIN_ES = [
    ("ES", r"leche (?:100\s*%\s*)?(?:espa[ñn]ola|de espa[ñn]a|de origen espa[ñn]ol)|vacas espa[ñn]olas"),
    ("FR", r"leche (?:francesa|de francia)"),
    ("IE", r"leche (?:irlandesa|de irlanda)|origen irlanda"),
    ("NL", r"leche (?:holandesa|neerlandesa|de los pa[íi]ses bajos)"),
    ("DE", r"leche (?:alemana|de alemania)"),
    ("NZ", r"nueva zelanda|neozeland[ée]s"),
    ("EU", r"leche (?:europea|de la ue|de origen europeo)"),
]


def attributes(text: str, ingr: Optional[str], lang: str = "fr") -> dict:
    low = text.lower()
    att: dict = {}
    es = lang == "es"
    if re.search(r"sans lactose|lactose[- ]free|0\s*%\s*(?:de\s*)?lactose|<\s*0[,.]1\s*g\s*de\s*lactose|d[ée]lactos[ée]e?", low) \
            or (es and re.search(r"sin lactosa|libre de lactosa|exento de lactosa|0\s*%\s*(?:de\s*)?lactosa|deslactosad", low)):
        att["lactose_free"] = True
    found = []
    if ingr:
        for name, rx in _merged(SWEETENERS, SWEETENERS_ES, lang).items():
            if re.search(rx, ingr, re.I):
                found.append(name)
        if "sucralose ou autre (non précisé)" in found and len(found) > 1:
            found.remove("sucralose ou autre (non précisé)")
        found = [("édulcorant non précisé" if f.startswith("sucralose ou autre") else f) for f in found]
        att["sweeteners"] = found
        att["no_sweetener"] = not found
        att["no_sucralose"] = "sucralose" not in found
        att["watched_additives"] = [n for n, rx in _merged(WATCHED_ADDITIVES, WATCHED_ADDITIVES_ES, lang).items()
                                    if re.search(rx, ingr, re.I)]
        att["ingredient_count"] = ingredient_count(ingr)
    elif re.search(r"sans (?:aucun )?[ée]dulcorants?|non [ée]dulcor[ée]|sans sucralose", low) \
            or (es and re.search(r"sin (?:ning[úu]n )?edulcorantes?|no edulcorad|sin sucralosa", low)):
        att["no_sucralose"] = True
        if re.search(r"sans (?:aucun )?[ée]dulcorants?|non [ée]dulcor[ée]", low) \
                or (es and re.search(r"sin (?:ning[úu]n )?edulcorantes?|no edulcorad", low)):
            att["no_sweetener"] = True
    for code, rx in MILK_ORIGIN + (MILK_ORIGIN_ES if es else []):
        if re.search(rx, low):
            att["milk_origin"] = code
            break
    if re.search(r"grass[- ]?fed|vaches? nourries? (?:à|a) l['’]herbe|p[âa]turage", low) \
            or (es and re.search(r"alimentadas? con pasto|de pasto|pastoreo", low)):
        att["grass_fed"] = True
    return att


# --------------------------------------------------------------------------- pré-workout : actifs par portion

# Doses utilisées dans les études (référence affichée à côté de la dose de la portion, jamais un conseil)
PRE_ACTIVES = {
    "caffeine": (r"caf[ée]ine(?: anhydre| naturelle)?|caffeine(?: anhydrous)?", "mg", 200, "Caféine"),
    "citrulline_malate": (r"(?:l-)?citrulline malate|malate de (?:l-)?citrulline", "g", 8, "Citrulline malate"),
    "citrulline": (r"(?:l-)?citrulline(?! malate)", "g", 6, "Citrulline"),
    "beta_alanine": (r"b[êe]ta[- ]?alanine|beta[- ]alanine|carnosyn", "g", 3.2, "Bêta-alanine"),
    "creatine": (r"(?:monohydrate de )?cr[ée]atine(?: monohydrate)?|creapure", "g", 3, "Créatine"),
    "betaine": (r"b[ée]ta[iï]ne(?: anhydre)?", "g", 2.5, "Bétaïne"),
}
PRE_ACTIVES_ES = {
    "caffeine": r"cafe[íi]na(?: anhidra| natural)?",
    "citrulline_malate": r"(?:dl-|l-)?citrulina malato|(?:dl-)?malato de (?:l-)?citrulina",
    "citrulline": r"(?:l-)?citrulina(?! malato)",
    "beta_alanine": r"beta[- ]?alanina",
    "creatine": r"(?:monohidrato de )?creatina(?: monohidrato)?",
    "betaine": r"beta[íi]na(?: anhidra)?",
}


def _per_serving_value(text: str, rx: str, lang: str = "fr") -> Optional[tuple[float, str]]:
    """Quantité par portion d'un actif : colonne « par portion » du tableau, sinon « 200 mg de caféine »."""
    from .extract import table_value
    tv = table_value(text, r"(?:" + rx + ")", "unit", lang=lang)
    if tv is None:
        rows = [ln for ln in text.split("\n") if "|" in ln and re.match(r"\s*(?:" + rx + r")\b", ln, re.I)]
        if rows:
            m = re.search(r"\|\s*<?\s*(\d+(?:[.,]\d+)?)\s*(mg|g|µg)\b", rows[0], re.I)
            if m:
                tv = (float(m.group(1).replace(",", ".")), m.group(2).lower(), rows[0])
    if tv is None:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mg|g)\s*(?:de\s+|d['’])?(?:" + rx + r")\b", text, re.I)
        if m:
            tv = (float(m.group(1).replace(",", ".")), m.group(2).lower(), m.group(0))
    if tv is None or tv[1] not in ("mg", "g"):
        return None
    return tv[0], tv[1]


def preworkout_profile(text: str, lang: str = "fr") -> Optional[dict]:
    """{actif: {dose, unité, référence, atteinte}} par portion, pour les actifs reconnus présents sur la fiche."""
    out: dict = {}
    for key, (rx, unit, ref, label) in PRE_ACTIVES.items():
        if lang == "es":
            rx = rx + "|" + PRE_ACTIVES_ES[key]
        v = _per_serving_value(text, rx, lang)
        if not v:
            continue
        val = v[0] / 1000 if (v[1] == "mg" and unit == "g") else v[0] * 1000 if (v[1] == "g" and unit == "mg") else v[0]
        if (unit == "mg" and not 10 <= val <= 600) or (unit == "g" and not 0.1 <= val <= 15):
            continue                                    # valeur pour 100 g ou faute de lecture : on ne l'affiche pas
        out[key] = {"label": label, "dose": round(val, 2), "unit": unit, "ref": ref, "ok": val >= ref * 0.95}
    if "citrulline_malate" in out:
        out.pop("citrulline", None)
    return out or None


def product_details(body_html: str, title: str = "", lang: str = "fr") -> dict:
    text = html_to_text(body_html or "")
    ingr = ingredients(text, lang)
    att = attributes(title + "\n" + text, ingr, lang)
    pre = preworkout_profile(text, lang)
    if pre:
        att["preworkout"] = pre
    return {"ingredients": ingr, "nutrition": nutrition(text, lang) or None, "attributes": att}


# --------------------------------------------------------------------------- avis : thèmes

TOPICS = {
    "Goût": r"go[uû]ts?\b|saveurs?|d[ée]licieu|bon go[uû]t|[ée]c(?:œ|oe)urant|chimique|trop sucr|taste|flavou?r",
    "Mélange": r"m[ée]lang|dissou|dilu|grumeau|soluble|se m[ée]lange|mix|mousse",
    "Digestion": r"dig[eè]r|digest|ballonn|estomac|ventre|intestin|\bgaz\b|ballon|bloat|lourd",
    "Texture": r"texture|[ée]pais|onctu|cr[ée]meu|aqueu|consistance",
    "Efficacité": r"efficac|r[ée]sultats?|r[ée]cup|[ée]nergie|\bpump\b|focus|concentration|force|effets?\b|boost",
    "Prix": r"\bprix\b|\bcher\b|qualit[ée][- /]prix|rapport qualit|[ée]conomique|value for money",
    "Emballage et doseur": r"emballage|sachet|\bpot\b|doseur|cuill[eè]re|scoop|bo[iî]te|refermer|zip",
}
NEGATIVE = re.compile(r"\bpas (?:tr[eè]s )?(?:bon|top|terrible|efficace|fou)|mauvais|d[ée]cevant|d[ée][çc]u|horrible|imbuvable|"
                      r"grumeaux|ballonn|[ée]c(?:œ|oe)urant|trop sucr|chimique|infect|bof|moyen\b|cass[ée]|ab[iî]m[ée]", re.I)
# Espagnol : lexique des thèmes et du sentiment, ajouté au lexique français pour les sites en espagnol.
TOPICS_ES = {
    "Goût": r"sabor(?:es)?|delicios|\brico\b|asqueros|empalagos|qu[íi]mico|demasiado dulce",
    "Mélange": r"mezcl|disuelv|disolv|grumos?|soluble|espuma",
    "Digestion": r"digest|hinchaz|hinchad|est[óo]mago|barriga|tripa|intestin|\bgases\b|pesadez|sienta mal",
    "Texture": r"textura|espes|cremos|aguad|consistencia",
    "Efficacité": r"eficaz|eficacia|resultados?|recuperaci|energ[íi]a|congesti[óo]n|concentraci[óo]n|fuerza|efectos?\b",
    "Prix": r"precio|\bcaro\b|calidad[- /]precio|econ[óo]mic|barato",
    "Emballage et doseur": r"envase|bolsa|\bbote\b|dosificador|cacito|cuchar|cierre|\bcaja\b",
}
NEGATIVE_ES = re.compile(r"\bno (?:est[áa] |es )?(?:muy )?(?:bueno|rico|eficaz)|\bmalo\b|decepcion|horrible|imbebible|grumos|"
                         r"hinchaz|asqueros|empalagos|qu[íi]mico|\bregular\b|\broto\b|da[ñn]ado|fatal", re.I)
POSITIVE_ES = re.compile(r"excelente|muy bueno|muy rico|perfect|genial|buen[íi]simo|riqu[íi]simo|delicios|"
                         r"se (?:mezcla|disuelve) (?:muy |super )?bien|sin problemas|lo recomiendo|recomendable|de diez", re.I)
POSITIVE = re.compile(r"excellent|tr[eè]s bon|parfait|\btop\b|super\b|d[ée]licieu|g[ée]nial|au top|impeccable|nickel|"
                      r"se m[ée]lange (?:tr[eè]s |super )?bien|aucun (?:souci|probl)|recommande", re.I)


def _review_list(page: str) -> list[tuple[str, Optional[float]]]:
    """(texte, note sur 5) des avis présents dans la page : JSON-LD Review, widgets Judge.me et microdonnées."""
    out: list[tuple[str, Optional[float]]] = []
    for n in _jsonld_nodes(page):
        if "Review" in str(n.get("@type", "")) and n.get("reviewBody"):
            r = n.get("reviewRating") or {}
            try:
                note = float(str(r.get("ratingValue")).replace(",", ".")) * 5 / float(str(r.get("bestRating") or 5).replace(",", "."))
            except (TypeError, ValueError):
                note = None
            out.append((html.unescape(str(n["reviewBody"])), note))
    if True:                                            # toutes les sources sont cumulées puis dédoublonnées
        for m in re.finditer(r'class="[^"]*jdgm-rev\b[^"]*"[^>]*data-score="(\d)".*?class="[^"]*jdgm-rev__body[^"]*"[^>]*>(.*?)</div>',
                             page, re.S | re.I):
            out.append((re.sub(r"<[^>]+>", " ", html.unescape(m.group(2))), float(m.group(1))))
    if True:                                            # blocs d'avis rendus dans la page (HSN : data-review-id)
        starts = [m.start() for m in re.finditer(r'data-review-id="', page)]
        for i, a in enumerate(starts):
            block = page[a:starts[i + 1] if i + 1 < len(starts) else a + 4000][:4000]
            text = re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>|<[^>]+>", " ", block)).strip()
            stars = len(re.findall(r'class="[^"]*(?:text-hsn-yellow|star-full|fill-current)[^"]*"', block))
            out.append((html.unescape(text), float(stars) if 1 <= stars <= 5 else None))
    if True:
        for m in re.finditer(r'itemprop="reviewBody"[^>]*>(.*?)</', page, re.S | re.I):
            out.append((re.sub(r"<[^>]+>", " ", html.unescape(m.group(1))), None))
    seen, uniq = set(), []
    for t, note in out:
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) >= 8 and t not in seen:
            seen.add(t)
            uniq.append((t, note))
    return uniq[:200]


def review_topics(page: str, lang: str = "fr") -> Optional[dict]:
    """{thème: {mentions, positifs, négatifs}} à partir des avis publiés sur la fiche (au moins 3 mentions par thème)."""
    reviews = _review_list(page or "")
    if not reviews:
        return None
    topics = TOPICS if lang != "es" else {k: v + "|" + TOPICS_ES[k] for k, v in TOPICS.items()}
    neg_rx = [NEGATIVE] + ([NEGATIVE_ES] if lang == "es" else [])
    pos_rx = [POSITIVE] + ([POSITIVE_ES] if lang == "es" else [])
    stats: dict[str, dict] = {}
    for text, note in reviews:
        sentences = re.split(r"(?<=[.!?])\s+|\n", text)
        for topic, rx in topics.items():
            hits = [s for s in sentences if re.search(rx, s, re.I)]
            if not hits:
                continue
            st = stats.setdefault(topic, {"mentions": 0, "pos": 0, "neg": 0})
            st["mentions"] += 1
            chunk = " ".join(hits)
            neg = any(r.search(chunk) for r in neg_rx)
            pos = any(r.search(chunk) for r in pos_rx)
            if neg or (note is not None and note <= 2 and not pos):
                st["neg"] += 1
            elif pos or (note is not None and note >= 4):
                st["pos"] += 1
    kept = {k: v for k, v in stats.items() if v["mentions"] >= 2}
    return {"reviews_read": len(reviews), "topics": kept} if kept else None
