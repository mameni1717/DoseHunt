"""Lecture du contenu d'un contenant à partir des libellés : « Pot de 1,38kg », « 12x50g »,
« Boite de 20 barres de 70g », « 120 gélules », « 900 g (1 produit) », « 2 boîtes », « 3 mois »…"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from .models import Format, RawProduct, RawVariant

NUM = r"(\d+(?:[.,]\d+)?)"
# Les mots espagnols (« cápsulas », « comprimidos », « barritas », « dosis »…) sont ajoutés en union : ils n'apparaissent
# jamais dans les libellés français, qui sont donc lus exactement comme avant.
UNIT_WORDS = {
    "gélule": r"g[ée]lules?|v[ée]gicaps?|(?:v[ée]g(?:an|gie|[ée]tales?)?\s+)?caps\b|vcaps",
    "capsule": r"capsules?(?: molles)?|softgels?|c[áa]psulas?(?: blandas| vegetales| veganas)?|perlas\b",
    "comprimé": r"comprim[ée]s?|tabs?\b|tablets?|tablettes?|comprimidos?|tabletas?",
    "gummy": r"gummies|gummy|gommes?|gominolas?",
    "goutte": r"gouttes?|gotas\b",
    "stick": r"sticks?|sachets? individuels?|unidoses?|sobres\b",
    "ampoule": r"ampoules?|shots?|fioles?|ampollas?|viales\b",
    "barre": r"barres?|bars?\b|barritas?|barras\b",
}
FORMAT_OPTION = re.compile(r"format|taille|size|contenance|conditionnement|packaging|inhoud|quantit|poids|dur[ée]e|title|"
                           r"tama[ñn]o|cantidad|peso|contenido", re.I)
FLAVOUR_OPTION = re.compile(r"saveur|go[uû]ts?|parfum|ar[oô]me|flavou?r|smaak|sabor", re.I)


def _f(x: str) -> float:
    return float(x.replace(",", "."))


def parse_format(text: str, *, prefer_units: bool = False) -> Format:
    """Lit un libellé. `prefer_units` aide à interpréter un nombre nu (« 60 », « 400.0 »)."""
    raw = text or ""
    t = raw.lower().replace("×", "x").replace(" ", " ").replace("\xa0", " ")
    fmt = Format(raw=raw)
    if not t.strip() or t.strip() == "default title":
        fmt.confidence = 0
        return fmt

    # Lots : « 2 boîtes », « (3 produits) », « lot de 3 », « pack de 2 » (hors « pack de 12 barres »)
    m = re.search(r"\b(\d+)\s*(bo[iî]tes|produits|pots|lots|doypacks|sachets|flacons|piluliers|botes|productos|frascos)\b", t)
    if m and int(m.group(1)) > 1:
        fmt.pack_count = int(m.group(1))
    m = re.search(r"\b(?:lot|pack|duo|trio|lote)\s+de\s+(\d+)\b(?!\s*(?:" + "|".join(UNIT_WORDS.values()) + r"))", t)
    if m:
        fmt.pack_count = int(m.group(1))
    if re.search(r"\bduo\b", t) and fmt.pack_count == 1 and re.search(r"pack|lot", t):
        fmt.pack_count = 2

    # Barres et sachets multiples : « 12x50g », « boite de 20 barres de 70g », « 12 barres »
    m = re.search(r"\b(\d+)\s*x\s*" + NUM + r"\s*(g|gr)\b", t)
    if m:
        fmt.units, fmt.unit_grams, fmt.unit_word = int(m.group(1)), _f(m.group(2)), "barre"
    m = re.search(r"(\d+)\s*(barres?|bars?|barritas?|barras)\b(?:\s*de\s*" + NUM + r"\s*g)?", t)
    if m:
        fmt.units, fmt.unit_word = int(m.group(1)), "barre"
        if m.group(3):
            fmt.unit_grams = _f(m.group(3))

    # « 3x90 gélules » : lot de 3 piluliers de 90
    if fmt.units is None:
        m = re.search(r"\b(\d+)\s*x\s*(\d+)\s*(?:" + "|".join(v for k, v in UNIT_WORDS.items() if k != "barre") + ")", t)
        if m:
            fmt.pack_count, fmt.units = int(m.group(1)), int(m.group(2))
            fmt.unit_word = next(k for k, v in UNIT_WORDS.items() if re.search(v, t[m.start():m.end() + 12]))

    # « Barre … Lot de 24 », « La Barre Fit x 32 » : nombre de barres
    if fmt.units is None and re.search(r"\bbarres?\b|\bbars?\b|\bbarritas?\b", t):
        m = re.search(r"(?:lot de|pack de|bo[iî]te de|lote de|caja de|\bx|×)\s*(\d{1,3})\b(?!\s*(?:g|gr|kg|ml)\b)", t)
        if m:
            fmt.units, fmt.unit_word, fmt.pack_count = int(m.group(1)), "barre", 1

    # Gélules, comprimés, capsules, gouttes…
    if fmt.units is None:
        for word, rx in UNIT_WORDS.items():
            m = re.search(r"(\d+)\s*(?:" + rx + ")", t)
            if m:
                fmt.units, fmt.unit_word = int(m.group(1)), word
                break
        else:
            m = re.search(r"(\d+)\s*(?:pack|pcs|pièces|portions|doses|porciones|raciones|dosis|servicios|tomas)\b", t)
            if m:
                fmt.units, fmt.unit_word = int(m.group(1)), "dose"

    # Poids : « 1,38kg », « 2.25 Kg », « 900 g », « 1.816kg », « 2030g »
    if fmt.unit_grams is None or fmt.units is None:
        m = re.search(NUM + r"\s*(kg|kilos?)\b", t) or re.search(NUM + r"\s*(g|gr|grammes?|gramos?)\b", t)
        if m:
            grams = _f(m.group(1)) * (1000 if m.group(2).startswith("k") else 1)
            if fmt.unit_word == "barre" and fmt.units and grams < 200:
                fmt.unit_grams = grams
            elif fmt.units is None or fmt.unit_word != "barre":
                fmt.grams = grams
                if fmt.units is None and grams < 120 and re.search(r"barre|bar\b|barrita", t):
                    fmt.units, fmt.unit_grams, fmt.grams, fmt.unit_word = 1, grams, None, "barre"

    # « 1.8 kg (2 produits) » : le poids affiché est déjà le total du lot.
    if fmt.grams is not None and fmt.pack_count > 1 and re.search(r"\(\s*\d+\s*produits?\s*\)", t):
        fmt.pack_count = 1

    m = re.search(NUM + r"\s*ml\b", t)
    if m:
        fmt.millilitres = _f(m.group(1))
    m = re.search(r"(\d+)\s*(?:mois|meses)\b", t)
    if m:
        fmt.months = int(m.group(1))
    m = re.search(r"(\d+)\s*(?:jours|d[íi]as)\b", t)
    if m and fmt.months is None:
        fmt.months = int(m.group(1)) / 30          # « 15 jours » = un demi-mois de cure

    # Nombre nu (« 60 », « 45.0 », « 400.0 ») : interprétation prudente
    if fmt.grams is None and fmt.units is None and fmt.months is None and fmt.millilitres is None:
        m = re.fullmatch(r"\s*" + NUM + r"\s*", t)
        if m:
            n = _f(m.group(1))
            if prefer_units and n == int(n) and n <= 1000:
                fmt.units, fmt.confidence = int(n), 0.6
            elif n >= 100:
                fmt.grams, fmt.confidence = n, 0.5
            elif n >= 20:
                fmt.grams, fmt.confidence = n, 0.4          # « 48 » (référence Bulk) : une barre de 48 g
            else:
                fmt.confidence = 0
                return fmt

    if fmt.grams is None and fmt.units is None and fmt.months is None and fmt.millilitres is None:
        # « 2 boîtes » seul : le contenu d'une boîte viendra du titre, mais le lot compte.
        fmt.confidence = 0.5 if fmt.pack_count > 1 else 0
    return fmt


def merge(primary: Format, *fallbacks: Format) -> Format:
    """Complète les champs vides de `primary` avec ceux des libellés de secours."""
    out = Format(**{k: getattr(primary, k) for k in primary.__dataclass_fields__})
    for fb in fallbacks:
        for field in ("grams", "units", "unit_word", "unit_grams", "months", "millilitres"):
            if getattr(out, field) is None and getattr(fb, field) is not None:
                setattr(out, field, getattr(fb, field))
        if out.pack_count == 1 and fb.pack_count > 1:
            out.pack_count = fb.pack_count
        if out.confidence == 0 and fb.confidence:
            out.confidence = fb.confidence * 0.9
    # Une « boîte de 12 barres » × « 2 boîtes » : unités du titre, lot de la variante.
    return out


def variant_format(product: RawProduct, variant: RawVariant, *, prefer_units: bool = False) -> Format:
    sources: list[str] = []
    for name, value in variant.options.items():
        if FORMAT_OPTION.search(name) and not FLAVOUR_OPTION.search(name):
            sources.append(value)
    sources.append(variant.title)
    sources.append(product.title)
    sources.append(url_words(variant.url or product.url))      # dernier recours : « …-1-5kg-p-194… » (Eric Favre)
    parsed = [parse_format(s, prefer_units=prefer_units) for s in sources]
    usable = [p for p in parsed if p.confidence > 0] or parsed
    return merge(usable[0], *usable[1:])


def url_words(url: Optional[str]) -> str:
    """Mots de l'adresse d'une fiche, avec « 1-5kg » lu comme « 1.5kg » ; identifiants numériques retirés."""
    if not url:
        return ""
    path = re.sub(r"\?.*$", "", url).rstrip("/").rsplit("/", 1)[-1]
    path = re.sub(r"\.(html?|php)$", "", path)
    path = re.sub(r"-p-\d+(?:-o-\d+)?$|-c-[\d_]+$|\b\d{5,}\b", "", path)
    path = re.sub(r"^\d+(?:-\d+)?-", "", path)        # PrestaShop : « 334-barre-proteinee », « 146-679-zinc »
    path = re.sub(r"(\d)-(\d{1,2})(kg|g)\b", r"\1.\2\3", path)
    return re.sub(r"[-_]+", " ", path)


def variant_flavour(variant: RawVariant) -> Optional[str]:
    for name, value in variant.options.items():
        if FLAVOUR_OPTION.search(name):
            return value
    # « Vanille / 1.00 kg » : la partie qui ne contient pas de format
    for part in (variant.title or "").split(" / "):
        if part and parse_format(part).confidence == 0 and part != "Default Title" and not re.fullmatch(r"[\d\s.,-]+", part):
            return part.strip()
    return None


def first_units_in_text(text: str) -> Optional[tuple[int, str]]:
    """« Boîte de 60 gélules » dans une description."""
    for word, rx in UNIT_WORDS.items():
        if word == "barre":
            continue
        m = re.search(r"(\d+)\s*(?:" + rx + ")", text, re.I)
        if m and 10 <= int(m.group(1)) <= 1000:
            return int(m.group(1)), word
    return None


def iter_format_sources(product: RawProduct) -> Iterable[str]:
    yield product.title
    for v in product.variants:
        yield v.title
