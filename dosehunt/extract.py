"""Extraction des teneurs en actif depuis la description (texte et tableau nutritionnel).

Règle d'or du cahier des charges : seule la quantité d'élément compte. « Gluconate de zinc
120 mg » est le poids du sel, pas du zinc : on le relève à part (salt_label_mg) et on ne
l'utilise jamais comme teneur.

Ordre : tableau nutritionnel > phrase explicite > hypothèse documentée. Ce qui n'est pas
trouvé part à l'IA (llm.py) si elle est configurée, sinon en revue humaine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .collectors.base import html_to_text
from .models import ActiveContent, Format

N = r"(\d+(?:[.,]\d+)?)"
BIG = r"(\d{1,3}(?:[ .]\d{3})+|\d+(?:[.,]\d+)?)"     # « 3 000 », « 1.000 », « 25 »
UNIT_NOUN = r"g[ée]lules?|comprim[ée]s?|capsules?(?: molles)?|softgels?|gouttes?|tablettes?|gummies|sticks?|doses?|portions?|barres?"
SALTS = (r"gluconate|citrate|bisglycinate|glycinate|picolinate|oxyde|sulfate|malate|carbonate|chlorure|lactate|"
         r"taurate|pidolate|ascorbate|orotate|aspartate|thréonate|threonate|ultimine|optizinc|chélate|chelate|marin")
WORD_NUM = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "1/2": 0.5, "½": 0.5, "demi": 0.5,
            # espagnol (ces mots ne peuvent être capturés que par les motifs espagnols)
            "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "media": 0.5, "medio": 0.5}

# --------------------------------------------------------------------------- vocabulaire par langue
# « fr » : fragments historiques, inchangés. « es » : fragments français + équivalents espagnols (union).
UNIT_NOUN_ES = (r"c[áa]psulas?(?: blandas)?|comprimidos?|perlas?|gotas?|tabletas?|gominolas?|sobres?|dosis|"
                r"porci[óo]n(?:es)?|raci[óo]n(?:es)?|barritas?|cacitos?|tomas?\b|servicios?")
SALTS_ES = (r"gluconato|citrato|bisglicinato|glicinato|picolinato|[óo]xido|sulfato|malato|carbonato|cloruro|lactato|"
            r"taurato|pidolato|ascorbato|orotato|aspartato|treonato|quelato|acetato|"
            r"monometionina|mono-?l-?metionina|metionina")     # « 30 mg de zinc monometionina » : poids du sel (Vitobest ZMAG)
_V = {
    "fr": {
        "unit": UNIT_NOUN, "salts": SALTS, "dw": r"doses?|portions?",
        "num": r"1/2|½|demi|\d+|une?|deux|trois", "num2": r"1/2|½|\d+|une?|deux|trois",
        "after": r"par|pour|/|dans|en", "before": r"dans|pour|par", "head": r"pour|par",
        "verbs": r"apportent|apporte|contiennent|contient|fournissent|fournit|=",
        "of": r"de|d['’]", "elem": r"[ée]l[ée]ment(?:aire)?",
        "hdr": r"par|pour|portion|dose|barre", "col": r"barre|portion|dose|g[ée]lule|comprim|capsule|stick|shaker|\d+\s*g\)",
        "prot": r"prot[ée]ines?|protein", "dry": r"mati[eè]re s[eè]che",
    },
}
_V["es"] = {k: v for k, v in _V["fr"].items()}
_V["es"].update({
    "unit": UNIT_NOUN + "|" + UNIT_NOUN_ES, "salts": SALTS + "|" + SALTS_ES,
    "dw": r"doses?|portions?|dosis|porci|raci|tomas?|cacitos?|servicios?",
    "num": _V["fr"]["num"] + r"|media|medio|uno|dos|tres|cuatro", "num2": _V["fr"]["num2"] + r"|uno|dos|tres|cuatro",
    "after": _V["fr"]["after"] + r"|por|cada", "before": _V["fr"]["before"] + r"|en|para|por|cada",
    "head": _V["fr"]["head"] + r"|por|cada",
    "verbs": _V["fr"]["verbs"] + r"|aportan|aporta|contienen|contiene|proporcionan|proporciona",
    "elem": _V["fr"]["elem"] + r"|elemental",
    "hdr": _V["fr"]["hdr"] + r"|\bpor\b|porci[óo]n|raci[óo]n|dosis|barrita|toma|cacito|servicio",
    "col": _V["fr"]["col"] + r"|porci[óo]n|raci[óo]n|dosis|barrita|c[áa]psula|cacito|toma|servicio",
    "prot": _V["fr"]["prot"] + r"|prote[íi]nas?", "dry": _V["fr"]["dry"] + r"|base seca|materia seca",
})


def _v(lang: str) -> dict:
    return _V.get(lang) or _V["fr"]


def _f(x: str) -> float:
    x = x.strip()
    if re.fullmatch(r"\d{1,3}(?:[ .]\d{3})+", x):
        return float(re.sub(r"[ .]", "", x))
    return float(x.replace(",", "."))


def _count(word: Optional[str]) -> float:
    if not word:
        return 1
    word = word.strip().lower()
    return WORD_NUM.get(word, None) or (float(word.replace(",", ".")) if re.fullmatch(N, word) else 1)


@dataclass
class DoseInfo:
    units_per_dose: Optional[float] = None
    evidence: str = ""


def daily_dose(text: str, lang: str = "fr") -> DoseInfo:
    """« Dose journalière 1/2 comprimé », « 2 gélules par jour », « 1 gélule par jour »."""
    t = text.lower()
    V = _v(lang)
    pats = [
        r"dose (?:journali[eè]re|quotidienne)\s*[:\-(]?\s*(" + V["num"] + r")\s*(?:" + V["unit"] + ")",
        r"(" + V["num"] + r")\s*(?:" + V["unit"] + r")\s*(?:par|/)\s*jour",
        r"prendre\s*(" + V["num"] + r")\s*(?:" + V["unit"] + ")",
    ]
    if lang == "es":                 # « dosis diaria: 2 cápsulas », « 1 cápsula al día », « tomar 2 comprimidos »
        pats += [
            r"dosis (?:diaria|recomendada)\s*[:\-(]?\s*(" + V["num"] + r")\s*(?:" + V["unit"] + ")",
            r"(" + V["num"] + r")\s*(?:" + V["unit"] + r")\s*(?:al|por|/|cada)\s*d[íi]a",
            r"tomar\s*(" + V["num"] + r")\s*(?:" + V["unit"] + ")",
            # « Tamaño de la Ración - 3 Pastillas » (« pastillas » seulement ici : « Consumir 3 pastillas al día » ne dit pas
            # si la teneur du titre est par pastille ou par jour)
            r"tama[ñn]o de la raci[óo]n\s*[:\-–]?\s*(" + V["num"] + r")\s*(?:" + V["unit"] + r"|pastillas?)",
        ]
    for p in pats:
        m = re.search(p, t)
        if m:
            return DoseInfo(_count(m.group(1)), m.group(0))
    return DoseInfo()


def _dose_after(text: str, pos: int, window: int = 90, lang: str = "fr") -> tuple[Optional[float], str]:
    """Cherche « par gélule », « pour 2 gélules », « dans 1/2 comprimé » juste après une teneur."""
    seg = text[pos:pos + window].lower()
    V = _v(lang)
    m = re.search(r"(?:" + V["after"] + r")\s*(" + V["num"] + r")?\s*(" + V["unit"] + ")", seg)
    if not m:
        return None, ""
    noun = m.group(2)
    if re.match(V["dw"], noun):
        return -1, m.group(0)        # « par dose » : à résoudre avec la dose journalière
    return _count(m.group(1)), m.group(0)


def _dose_before(text: str, pos: int, window: int = 60, lang: str = "fr") -> tuple[Optional[float], str]:
    seg = text[max(0, pos - window):pos].lower()
    V = _v(lang)
    # « 3 gélules seulement apportent 300 mg », « 2 capsules contiennent 1 000 UI »
    m = re.search(r"(" + V["num2"] + r")\s*(" + V["unit"] + r")\s*(?:\S+\s+){0,2}?"
                  r"(?:" + V["verbs"] + r")\s*$", seg)
    if m and not re.match(V["dw"], m.group(2)):
        return _count(m.group(1)), m.group(0)
    m = None
    for m in re.finditer(r"(?:" + V["before"] + r")\s*(" + V["num"] + r")?\s*(" + V["unit"] + ")", seg):
        pass
    if not m:
        return None, ""
    if re.match(V["dw"], m.group(2)):
        return -1, m.group(0)
    return _count(m.group(1)), m.group(0)


def _table_header_dose(text: str, pos: int, lang: str = "fr") -> tuple[Optional[float], str]:
    """En-tête du tableau qui contient la valeur : « Ingrédient | Pour 2 gélules | AR* »."""
    lines = text[max(0, pos - 600):pos].split("\n")[:-1]     # la dernière est le début de la ligne courante
    for line in reversed(lines):
        if "|" not in line:
            break                                   # sortie du tableau
        V = _v(lang)
        m = re.search(r"(?:" + V["head"] + r")\s*(" + V["num2"] + r")\s*(" + V["unit"] + ")", line, re.I)
        if m:
            return (-1, line) if re.match(V["dw"], m.group(2), re.I) else (_count(m.group(1)), line)
    return None, ""


# --------------------------------------------------------------------------- tableau nutritionnel

def table_rows(text: str) -> list[list[str]]:
    return [[c.strip() for c in ln.split("|")] for ln in text.split("\n") if "|" in ln]


def table_value(text: str, row_rx: str, want: str, ok=None, lang: str = "fr") -> Optional[tuple[float, str, str]]:
    """Valeur d'une ligne du tableau nutritionnel. want = '100g' ou 'unit'. Renvoie (valeur, unité, preuve)."""
    rows = table_rows(text)
    V = _v(lang)
    col100 = colunit = None
    header_len = 0
    for row in rows:
        lower = [c.lower() for c in row]
        if any(re.search(r"100\s*g|100\s*ml", c) for c in lower) or any(re.search(V["hdr"], c) for c in lower[1:]):
            col100 = colunit = None
            header_len = len(row)
            for i, c in enumerate(lower):
                if re.search(r"100\s*g", c) and col100 is None:
                    col100 = i
                elif re.search(V["col"], c) and i > 0 and colunit is None:
                    colunit = i
        if re.match(row_rx, lower[0] if lower else "") and not re.search(V["dry"], lower[0]):
            if want == "100g" and col100 is None:
                continue                            # tableau « par portion » seulement : ne pas le lire comme 100 g
            col = col100 if want == "100g" else colunit
            # En-tête sans cellule au-dessus des libellés (« Pour 100g | Par shaker (30g) ») : colonnes décalées
            if col is not None and header_len and len(row) > header_len:
                col += len(row) - header_len
            cells = row[1:] if col is None else [row[col]] if col < len(row) else []
            for cell in cells:
                m = re.match(r"\s*<?\s*" + N + r"\s*(mg|g|µg|μg|ui|iu)?", cell.lower())
                if m:
                    if ok is not None and not ok(_f(m.group(1))):
                        break                           # ligne en double ou mal étiquetée : on lit la suivante
                    return _f(m.group(1)), (m.group(2) or "g").replace("μ", "µ"), " | ".join(row)
    return None


def table_serving_to_100g(text: str, row_rx: str, lang: str = "fr") -> Optional[tuple[float, str]]:
    """Tableau sans colonne « 100 g » mais avec « Par portion journalière (10 g) » : valeur ramenée à 100 g."""
    serving, gap, best = None, 0, None
    for line in text.split("\n"):
        if "|" not in line:
            gap += 1 if line.strip() else 0
            if gap > 2:                              # sortie du tableau (une note sous l'en-tête est tolérée)
                serving = None
            continue
        gap = 0
        cells = [c.strip() for c in line.split("|")]
        head = re.search(r"(?:portion|dose|shaker|mesure)[^|]*?\(\s*" + N + r"\s*g\s*\)", line, re.I) \
            or re.search(r"(?:^|\|)[^|]{0,25}?\b(?:pour|par)\s+" + N + r"\s*g\b(?!\s*de)", line, re.I)
        if head is None and lang == "es":            # « Por ración (30 g) », « Por 30 g », « Cada cacito (30 g) », « Por ración diaria | 3,4g »
            head = re.search(r"(?:porci[óo]n|raci[óo]n|dosis|toma|cacito|servicio|scoop)[^|]*?\(\s*" + N + r"\s*g\s*\)", line, re.I) \
                or re.search(r"(?:^|\|)[^|]{0,25}?\b(?:por|cada)\s+" + N + r"\s*g\b(?!\s*de)", line, re.I) \
                or re.search(r"^\s*(?:por|cada)\s+(?:una?\s+)?(?:porci[óo]n|raci[óo]n|dosis)(?:\s+diaria)?\s*\|\s*" + N + r"\s*g\s*$", line, re.I)
        if head and _f(head.group(1)) == 100:
            head = None
        if head:
            serving = _f(head.group(1))
            continue
        if (re.search(r"\|\s*(?:par|pour)\s+(?:une\s+)?(?:dose|portion)\s*(?:\||$)", line, re.I)
                or (lang == "es" and re.search(r"\|\s*por\s+(?:una?\s+)?(?:dosis|porci[óo]n|raci[óo]n)(?:\s+diaria)?\s*(?:\||$)", line, re.I))) \
                and (size := serving_size(text, lang)):
            serving = size                           # « Par dose » sans poids : « Taille de la dose : … (10g) »
            continue
        if serving and re.match(row_rx, cells[0].lower()) and not re.search(_v(lang)["dry"], cells[0].lower()):
            for cell in cells[1:]:
                m = re.match(r"\s*" + N + r"\s*(m?g)\b", cell)
                grams = (_f(m.group(1)) / (1000 if m.group(2) == "mg" else 1)) if m else None
                if grams and grams <= serving:
                    val = round(grams / serving * 100, 1)
                    if best is None or val > best[0]:
                        best = (val, line)          # plusieurs tableaux (nature / aromatisé) : la version nature
                    break
            serving = None
    return best


def bar_weight(text: str, lang: str = "fr") -> Optional[float]:
    m = re.search(r"par barre\s*\(?\s*" + N + r"\s*g", text, re.I) or re.search(r"barres? de\s*" + N + r"\s*g", text, re.I) \
        or re.search(N + r"\s*g de (?:crunchy|crispy|moelleux|croustillance|gourmandise)", text, re.I)
    if not m and lang == "es":       # « por barrita (40 g) », « barrita proteica de 40g »
        m = re.search(r"por barrita\s*\(?\s*" + N + r"\s*g", text, re.I) \
            or re.search(r"barritas?(?: proteicas?| de prote[íi]nas?)? de\s*" + N + r"\s*g", text, re.I)
    return _f(m.group(1)) if m else None


# --------------------------------------------------------------------------- par catégorie

def _protein_per_100g(text: str, lang: str = "fr") -> Optional[ActiveContent]:
    prot = _v(lang)["prot"]
    tv = table_value(text, prot, "100g", ok=lambda x: x >= 20, lang=lang) \
        or table_value(text, prot, "100g", lang=lang)
    if tv and tv[1] == "g":
        return ActiveContent("whey", "protein", tv[0], "g", "per_100g", "regex_table", 0.95, tv[2])
    ts = table_serving_to_100g(text, prot, lang)
    if ts:
        return ActiveContent("whey", "protein", ts[0], "g", "per_100g", "regex_table", 0.9, ts[1],
                             note="tableau par portion seulement : valeur ramenée à 100 g")
    pats = [
        (r"prot[ée]ines?\s*[:\-]?\s*" + N + r"\s*g\s*(?:pour|/|par)\s*100\s*g", 0.9),
        (N + r"\s*g de prot[ée]ines?\s*(?:pour|/|par|aux)\s*100\s*g", 0.9),
        (N + r"[ \t]*%[ \t]*(?:de[ \t]*)?prot[ée]ines?", 0.85),
        (r"(?:teneur|taux) (?:en|de) prot[ée]ines?\s*(?:de|:)?\s*" + N + r"\s*%", 0.85),
    ]
    if lang == "es":                 # « 34-35 g de proteína por cada 100 g », « 80 % de proteína », « Proteínas: 72 g por 100 g »
        pats += [
            (r"prote[íi]nas?\s*[:\-]?\s*" + N + r"\s*g\s*(?:por|/|en)\s*(?:cada\s*)?100\s*g", 0.9),
            (N + r"\s*g de prote[íi]nas?\s*(?:por|/|en|cada)\s*(?:cada\s*)?100\s*g", 0.9),
            (N + r"[ \t]*%[ \t]*(?:de[ \t]*)?prote[íi]nas?", 0.85),
            (r"(?:contenido|porcentaje) (?:en|de) prote[íi]nas?\s*(?:de|del|:)?\s*" + N + r"\s*%", 0.85),
        ]
    for rx, conf in pats:
        for m in re.finditer(rx, text, re.I):
            after = text[m.end():m.end() + 30].lower()
            # « composée à 100 % de protéines de lactosérum » décrit l'origine, pas la teneur
            if _f(m.group(1)) < 20:
                continue                                # « 2 % » d'AR, de matières grasses… : pas une teneur de poudre protéinée
            if "%" in m.group(0) and (_f(m.group(1)) >= 98 or re.match(r"\s*(de lactos|de whey|d['’]origine|laiti|v[ée]g[ée]tal)", after)):
                continue
            if lang == "es" and "%" in m.group(0) and re.match(r"\s*(de suero|de whey|de origen|l[áa]cte|vegetal|de leche)", after):
                continue                                # « 80 % proteína de suero » : l'origine, pas la teneur
            return ActiveContent("whey", "protein", _f(m.group(1)), "g", "per_100g", "regex_text", conf, m.group(0))
    m = re.search(N + r"\s*g de prot[ée]ines?.{0,40}?(?:par|pour|/|dans)\s*(?:une\s*)?(?:portion|dose|shaker|scoop|mesure|service)?\s*(?:de\s*)?" + N + r"\s*g",
                  text, re.I | re.S)
    if m and 5 <= _f(m.group(2)) <= 100:
        per100 = round(_f(m.group(1)) / _f(m.group(2)) * 100, 1)
        return ActiveContent("whey", "protein", per100, "g", "per_100g", "regex_text", 0.85, m.group(0),
                             note=f"calculé : {m.group(1)} g pour {m.group(2)} g")
    if lang == "es":
        # « 29 g de proteína por toma de 35 g », « Proteína (base seca): 29 g por 35 g », « Cada 35 g aportan 29 g de proteína »
        ms = re.search(N + r"\s*g de prote[íi]nas?.{0,40}?(?:por|en|/)\s*(?:cada\s*)?(?:una?\s*)?(?:porci[óo]n|raci[óo]n|dosis|toma|"
                       r"cacito|servicio|scoop|batido)?\s*(?:de\s*)?" + N + r"\s*g", text, re.I | re.S)
        if not (ms and 5 <= _f(ms.group(2)) <= 100):
            ms = re.search(r"prote[íi]nas?[^:\n]{0,25}:\s*" + N + r"\s*g\s*(?:por|en|/)\s*" + N + r"\s*g", text, re.I)
        if ms and 5 <= _f(ms.group(2)) <= 100 and _f(ms.group(1)) <= _f(ms.group(2)):
            per100 = round(_f(ms.group(1)) / _f(ms.group(2)) * 100, 1)
            return ActiveContent("whey", "protein", per100, "g", "per_100g", "regex_text", 0.85, ms.group(0),
                                 note=f"calculé : {ms.group(1)} g pour {ms.group(2)} g")
        mc = re.search(r"cada\s+" + N + r"\s*g\s+(?:aportan?|contienen?|proporcionan?)\s+" + N + r"\s*g de prote[íi]nas?", text, re.I)
        if mc and 5 <= _f(mc.group(1)) <= 100 and _f(mc.group(2)) <= _f(mc.group(1)):
            per100 = round(_f(mc.group(2)) / _f(mc.group(1)) * 100, 1)
            return ActiveContent("whey", "protein", per100, "g", "per_100g", "regex_text", 0.85, mc.group(0),
                                 note=f"calculé : {mc.group(2)} g pour {mc.group(1)} g")
    pst = _per_serving_text(text, r"prot[ée]ines?" if lang == "fr" else r"prot[ée]ines?|prote[íi]nas?", lang)
    if pst and 20 <= pst[0] <= 100:
        return ActiveContent("whey", "protein", pst[0], "g", "per_100g", "regex_text", 0.8, pst[1],
                             note="calculé : protéines par portion ÷ poids de la portion")
    return None


# Part maximale d'élément dans chaque sel (avec une marge) : au-delà, la teneur lue ne peut pas être « par unité ».
ELEMENT_SHARE = {
    "magnesium": {"oxyde": 0.62, "carbonate": 0.30, "marin": 0.40, "chlorure": 0.13, "citrate": 0.17, "malate": 0.17,
                  "bisglycinate": 0.16, "glycinate": 0.16, "lactate": 0.13, "taurate": 0.10, "pidolate": 0.10,
                  "thréonate": 0.09, "threonate": 0.09},
    "zinc": {"oxyde": 0.82, "sulfate": 0.38, "citrate": 0.33, "bisglycinate": 0.32, "glycinate": 0.32,
             "picolinate": 0.22, "gluconate": 0.15, "orotate": 0.18},
}


# Noms espagnols des sels (mêmes parts d'élément), utilisés seulement pour les sites en espagnol.
_SALT_ES = {"oxyde": "[óo]xido", "carbonate": "carbonato", "marin": "marino", "chlorure": "cloruro", "citrate": "citrato",
            "malate": "malato", "bisglycinate": "bisglicinato", "glycinate": "glicinato", "lactate": "lactato",
            "taurate": "taurato", "pidolate": "pidolato", "thréonate": "treonato", "sulfate": "sulfato",
            "picolinate": "picolinato", "gluconate": "gluconato", "orotate": "orotato"}


def _element_share(category: str, lang: str) -> dict:
    share = ELEMENT_SHARE.get(category, {})
    if lang != "es":
        return share
    out = dict(share)
    for k, v in share.items():
        if k in _SALT_ES:
            out.setdefault(_SALT_ES[k], v)
    return out


def _dose_from_title(title: str, amount: float, category: str, upd: float, conf: float, note: str, lang: str = "fr"):
    """Dose inconnue (« par dose ») : le titre aide à trancher.

    « Citrate de magnésium 112,5mg » + « 225 mg par dose » → 2 unités par dose.
    « Magnesium malate 1000mg » + « 346,5 mg par dose » : 346,5 mg de magnésium ne tiennent pas dans 1 000 mg de
    malate (≤ 17 %) → la dose compte plusieurs unités, nombre inconnu : confiance abaissée, revue humaine.
    """
    m = re.search(N + r"\s*mg\b", title, re.I)
    if not m:
        return upd, amount, conf, note
    label = _f(m.group(1))
    shares = _element_share(category, lang)
    salt = next((s_ for s_ in shares if re.search(s_, title, re.I)), None)
    if salt and label >= 300:                        # poids du sel dans le titre (« malate 1000mg »)
        if amount > label * shares[salt]:
            return upd, amount, 0.4, (f"{amount:g} mg par dose dépassent ce que contient une unité de {label:g} mg de "
                                      f"{salt} : dose de plusieurs unités, à vérifier")
        return upd, amount, conf, note
    ratio = amount / label if label else 0
    k = round(ratio)
    if 2 <= k <= 4 and abs(ratio - k) < 0.02:
        return k, amount, 0.85, f"{amount:g} mg par dose et {label:g} mg par unité selon le titre : dose de {k} unités"
    return upd, amount, conf, note


def _per_unit_element(text: str, category: str, element_rx: str, active: str, unit: str = "mg",
                      lang: str = "fr") -> Optional[ActiveContent]:
    """Zinc, magnésium : quantité d'élément par gélule/comprimé, en écartant le poids du sel."""
    t = text
    V = _v(lang)
    SALTS_L, ELEM, UNIT_L = V["salts"], V["elem"], V["unit"]
    salt_label = None
    candidates: list[tuple[float, str, int, int, str]] = []    # (valeur, unité, début, fin, source)

    # a) « 12 mg de zinc », « 15 mg de zinc élément »
    for m in re.finditer(N + r"[ \t]*(mg|g|µg)[ \t]*(?:de[ \t]+|d['’][ \t]*)?(?:" + element_rx + r")(?![ \t]*(?:" + SALTS_L + "))", t, re.I):
        candidates.append((_f(m.group(1)), m.group(2).lower(), m.start(), m.end(), "regex_text"))
    # b) « Zinc 12,5 g (VNR 125 %) », « Zinc | 15 mg | 150 % », sauf « gluconate de zinc 120 mg »
    for m in re.finditer(r"(?<![\w-])(?:" + element_rx + r")(?:[ \t]+(?:" + ELEM + r"))?[ \t]*[:|\-]?[ \t]*(?:\|[ \t]*)?" + N + r"[ \t]*(mg|g|µg)\b", t, re.I):
        before = t[max(0, m.start() - 30):m.start()].lower()
        if re.search(r"(" + SALTS_L + r")\s*(?:de|d['’])\s*$", before):
            salt_label = _f(m.group(1)) * (1000 if m.group(2).lower() == "g" else 1)
            continue
        src = "regex_table" if "|" in t[m.start():m.end()] else "regex_text"
        candidates.append((_f(m.group(1)), m.group(2).lower(), m.start(), m.end(), src))
    # c) poids du sel affiché : « Gluconate de zinc 120 mg », « 50 mg de bisglycinate de zinc »
    if salt_label is None:
        m = re.search(r"(?:" + SALTS_L + r")\s*(?:de|d['’])\s*(?:" + element_rx + r")\s*[:\-]?\s*" + N + r"\s*mg", t, re.I) \
            or re.search(N + r"\s*mg\s*(?:de\s+)?(?:" + SALTS_L + r")\s*(?:de|d['’])\s*(?:" + element_rx + ")", t, re.I)
        if m:
            salt_label = _f(m.group(1))
    if not candidates:
        return None

    tables = [c for c in candidates if c[4] == "regex_table"]
    val, u, start, end, src = (tables or candidates)[0]
    amount = val * {"mg": 1, "g": 1000, "µg": 0.001}[u]
    upd, ev = (None, "")
    if src == "regex_table":
        hw = r"pour|par|dans" if lang == "fr" else r"pour|par|dans|por|en|cada"
        heads = list(re.finditer(r"(?:" + hw + r")\s+(?:dose (?:journali[eè]re\s*)?\(?\s*)?(" + V["num2"] + r")\s*(" + UNIT_L + r")",
                                 t[max(0, start - 800):start], re.I))
        if heads and not re.match(V["dw"], heads[-1].group(2)):
            upd, ev = _count(heads[-1].group(1)), heads[-1].group(0)
    if upd is None:
        upd, ev = _dose_after(t, end, lang=lang)
    if upd is None:
        upd, ev = _dose_before(t, start, lang=lang)
    if upd is None and src == "regex_table":
        upd, ev = _table_header_dose(t, start, lang)
    note = None
    conf = 0.95 if src == "regex_table" else 0.9
    if upd == -1 or upd is None:
        dd = daily_dose(t, lang)
        if dd.units_per_dose:
            upd, ev = dd.units_per_dose, (ev + " ; " + dd.evidence).strip(" ;")
        else:
            upd = 1
            conf = 0.6
            note = "dose d'une unité supposée (la fiche ne précise pas le nombre d'unités par dose)"
    if note and upd == 1:
        upd, amount, conf, note = _dose_from_title(t.split("\n", 1)[0], amount, category, upd, conf, note, lang)
    per_unit = amount / upd
    if salt_label and abs(salt_label - per_unit) < 0.5:
        salt_label = None                            # « 112,5 mg » du titre = teneur réelle par unité, pas le sel
    form = None
    fm = re.search(r"(" + SALTS_L + ")", t, re.I)
    if fm:
        form = fm.group(1).lower()
    return ActiveContent(category, active, round(per_unit, 3), unit, "per_unit", src, conf,
                         t[max(0, start - 20):end + 60].replace("\n", " "), units_per_dose=upd,
                         salt_label_mg=salt_label, form=form, note=note)


def _vitamin_d(text: str, lang: str = "fr") -> Optional[ActiveContent]:
    m = re.search(BIG + r"\s*(?:UI|IU)\b", text, re.I)
    ui = None
    if m:
        ui, start, end = _f(m.group(1)), m.start(), m.end()
    else:
        m = re.search(N + r"\s*(?:µg|μg|mcg|ug)\s*(?:de\s+)?(?:" + ("vitamine" if lang == "fr" else "vitamine|vitamina") + r"\s*)?d3?", text, re.I)
        if m is None and lang == "es":
            # « Vitamina D3: 50µg por cápsula (1000% VRN) », « Vitamina D3 (colecalciferol) | 25 µg »
            m = re.search(r"vitamina\s*d3?\b(?:\s*\([^)\n]{0,30}\))?\s*[:|\-]?\s*(?:\|\s*)?" + N + r"\s*(?:µg|μg|mcg|ug)", text, re.I) \
                or re.search(r"vitamina\s*d3?\s*\+\s*k2(?:\s+[a-z]+)?\s*\(\s*" + N + r"\s*(?:µg|μg|mcg|ug)\s*/", text, re.I)   # titre « Vitamina D3 + K2 (100μg/150μg) » : D3 d'abord
        if m:
            ui, start, end = _f(m.group(1)) * 40, m.start(), m.end()
    if ui is None:
        return None
    upd, ev = _dose_after(text, end, lang=lang)
    if upd is None:
        upd, ev = _dose_before(text, start, lang=lang)
    conf, note = 0.9, None
    if upd in (None, -1):
        dd = daily_dose(text, lang)
        upd = dd.units_per_dose or 1
        if not dd.units_per_dose:
            conf, note = 0.6, "dose d'une unité supposée"
    return ActiveContent("vitamine_d", "vitamin_d", round(ui / upd, 1), "UI", "per_unit", "regex_text", conf,
                         text[max(0, start - 20):end + 60].replace("\n", " "), units_per_dose=upd, note=note)


def _omega3(text: str, lang: str = "fr") -> Optional[ActiveContent]:
    acid = r"acide" if lang == "fr" else r"acide|[áa]cido"
    sum_and = r"\+|et" if lang == "fr" else r"\+|et|y"

    def claim(m) -> bool:
        # « El efecto beneficioso se obtiene con una ingesta (diaria) de 250 mg de EPA y DHA » : l'allégation, pas la teneur
        return lang != "fr" and bool(re.search(r"ingesta\s+(?:diaria\s+)?de\s*$", text[max(0, m.start() - 30):m.start()], re.I))

    def first(rx):
        return next((m for m in re.finditer(rx, text, re.I) if not claim(m)), None)

    def grab(name):
        m = first(N + r"\s*mg\s*(?:d['’]\s*|de\s*)?(?:(?:" + acid + r")\s+\w+\s+)?\(?" + name + r"\b") \
            or re.search(r"\b" + name + r"\b[^|\n\d]{0,40}[:|\-]?\s*(?:\|\s*)?" + N + r"\s*mg", text, re.I)
        return (m, _f(m.group(1))) if m else (None, None)
    m_sum = first(N + r"\s*mg\s*(?:d['’]\s*|de\s*)?(?:epa\s*(?:" + sum_and + r")\s*dha|om[ée]ga[- ]?3)") if lang != "fr" \
        else re.search(N + r"\s*mg\s*(?:d['’]\s*)?(?:epa\s*(?:\+|et)\s*dha|om[ée]ga[- ]?3)", text, re.I)
    me, epa = grab("EPA")
    md, dha = grab("DHA")
    if epa is not None and dha is not None:
        total, anchor = epa + dha, max(me.end(), md.end())
        start = min(me.start(), md.start())
    elif m_sum:
        total, anchor, start = _f(m_sum.group(1)), m_sum.end(), m_sum.start()
    else:
        return None
    upd = _table_header_dose(text, start, lang)[0] if "|" in text[start:anchor + 1] else None
    if upd is None:
        upd, _ = _dose_after(text, anchor, lang=lang)
    if upd is None:
        upd, _ = _dose_before(text, start, lang=lang)
    conf, note = 0.9, None
    if upd in (None, -1):
        dd = daily_dose(text, lang)
        upd = dd.units_per_dose or 1
        if not dd.units_per_dose:
            conf, note = 0.6, "dose d'une capsule supposée"
    return ActiveContent("omega3", "epa_dha", round(total / upd, 1), "mg", "per_unit", "regex_text", conf,
                         text[max(0, start - 10):anchor + 40].replace("\n", " "), units_per_dose=upd, note=note)


def _powder_or_caps(text: str, category: str, active: str, noun_rx: str, title: str, fmt: Format,
                    lang: str = "fr") -> Optional[ActiveContent]:
    """Créatine, collagène : poudre (g pour 100 g) ou gélules (mg par unité)."""
    pep = r"peptides de" if lang == "fr" else r"peptides de|p[ée]ptidos de"
    sachets = lang == "es" and (fmt.unit_grams or 0) >= 2.5      # « Sobres monodosis 20 x 6.8g » : de la poudre en sachets, pas des gélules
    if fmt.units and fmt.grams is None and not sachets:          # gélules
        m = re.search(BIG + r"\s*mg\s*(?:de\s+)?(?:(?:" + pep + r")\s+)?(?:" + noun_rx + ")", text, re.I)
        grams_unit = 1
        if lang == "es":
            # tableau d'abord : « 4 cápsulas | %VRN / Hidrolizado de colágeno (de vacuno) | 2000 mg » (Sunday Natural)
            mt = re.search(r"^\s*(?:" + noun_rx + r")(?:\s*\([^)\n]{0,30}\))?\s*\|\s*" + BIG + r"\s*mg\b", text, re.I | re.M)
            if mt:
                head = re.search(r"^\s*(?:por\s+)?(" + _v(lang)["num2"] + r")\s*(?:" + _v(lang)["unit"] + r")[^|\n]*\|[^\n]*$",
                                 text[max(0, mt.start() - 300):mt.start()], re.I | re.M)
                upd_t = _count(head.group(1)) if head and not re.match(_v(lang)["dw"], head.group(0).strip().split()[-1]) else None
                upd_t = upd_t or daily_dose(text, lang).units_per_dose
                if upd_t:
                    return ActiveContent(category, active, round(_f(mt.group(1)) / upd_t, 1), "mg", "per_unit", "regex_table", 0.9,
                                         (head.group(0).strip() + " / " if head else "") + mt.group(0).strip(), units_per_dose=upd_t)
        if not m and lang == "es":
            # « 3,0 g de monohidrato de creatina por cada 3 comprimidos », « Tiene 2,5 gr de monohidrato de creatina »,
            # tableau « Monohidrato de Creatina | | | 3 g » ; jamais l'allégation « una ingesta diaria de 3 g de creatina »
            rx_g = (N + r"[ \t]*(?:g|gr|gramos)[ \t]+(?:de\s+)?(?:(?:" + pep + r")\s+)?(?:" + noun_rx + r")"
                    r"|(?:" + noun_rx + r")\s*(?:\|\s*)+" + N + r"\s*(?:g|gr|gramos)\b")
            m = next((x for x in re.finditer(rx_g, text, re.I)
                      if not re.search(r"ingesta\s+(?:diaria\s+)?de\s*$", text[max(0, x.start() - 30):x.start()], re.I)
                      and _f(x.group(1) or x.group(2)) <= 20), None)
            grams_unit = 1000
        if m:
            upd, _ = _dose_after(text, m.end(), lang=lang)
            if upd is None:
                upd, _ = _dose_before(text, m.start(), lang=lang)
            conf = 0.9
            if upd in (None, -1):
                dd = daily_dose(text, lang)
                upd = dd.units_per_dose or 1
                conf = 0.9 if dd.units_per_dose else 0.6
            amount = round(_f(m.group(1) or m.group(2)) * grams_unit / upd, 1)
            cap = 2000                                   # au-delà, impossible dans une seule gélule
            tm = re.search(r"(\d{3,4})\s*mg", title, re.I)
            if amount > cap and tm and 300 <= int(tm.group(1)) <= cap:
                # « 3 000 mg » lus pour la dose entière ; le titre donne la quantité par gélule (« Excell 1000mg »)
                return ActiveContent(category, active, float(tm.group(1)), "mg", "per_unit", "regex_text", 0.85,
                                     title, note=f"{amount:g} mg lus pour une dose ; {tm.group(1)} mg par unité d'après le titre")
            return ActiveContent(category, active, amount, "mg", "per_unit", "regex_text", conf,
                                 m.group(0), units_per_dose=upd)
        return None
    m = re.search(N + r"\s*g\s*(?:de\s+|d['’]\s*)?(?:peptides de\s+)?(?:" + noun_rx + r").{0,50}?(?:par|pour|/|dans)\s*(?:une\s*)?(?:portion|dose|mesure|stick|sachet|shaker)?\s*(?:de\s*)?" + N + r"\s*g",
                  text, re.I | re.S)
    if not m and lang == "es":       # « 10 g de colágeno por dosis de 12 g »
        m = re.search(N + r"\s*g\s*(?:de\s+)?(?:(?:" + pep + r")\s+)?(?:" + noun_rx + r").{0,50}?(?:por|/|en)\s*(?:cada\s*)?(?:una?\s*)?"
                      r"(?:porci[óo]n|raci[óo]n|dosis|toma|cacito|servicio|sobre|stick|shaker)?\s*(?:de\s*)?" + N + r"\s*g", text, re.I | re.S)
    if m and _f(m.group(2)) >= _f(m.group(1)):
        per100 = round(_f(m.group(1)) / _f(m.group(2)) * 100, 1)
        return ActiveContent(category, active, per100, "g", "per_100g", "regex_text", 0.85, m.group(0),
                             note=f"calculé : {m.group(1)} g pour {m.group(2)} g")
    tv = table_value(text, r"(?:" + noun_rx + ")", "100g", lang=lang)
    if tv and tv[1] == "g" and tv[0] <= 100:
        return ActiveContent(category, active, tv[0], "g", "per_100g", "regex_table", 0.9, tv[2])
    ts = table_serving_to_100g(text, r"(?:hydrolysat de |peptides? de )?(?:" + noun_rx + ")" if lang == "fr" else
                               r"(?:hydrolysat de |peptides? de |hidrolizado de |p[ée]ptidos? de )?(?:" + noun_rx + ")", lang)
    if ts:
        return ActiveContent(category, active, ts[0], "g", "per_100g", "regex_table", 0.85, ts[1],
                             note="ramené à 100 g depuis la colonne « par portion »")
    pst = _per_serving_text(text, noun_rx, lang)
    if pst:
        return ActiveContent(category, active, pst[0], "g", "per_100g", "regex_text", 0.8, pst[1],
                             note="calculé : quantité par portion ÷ poids de la portion")
    pure_rx, mix_rx = r"monohydrat|creapure|micronis|100\s*%|pure", r"complexe|\+|matrix|blend|pre|ph-x|malate|hcl|plus"
    if lang == "es":
        pure_rx, mix_rx = pure_rx + r"|monohidrat|micronizada|pura", mix_rx + r"|complejo|con\b"
    if category == "creatine" and re.search(pure_rx, title, re.I) and not re.search(mix_rx, title, re.I):
        return ActiveContent(category, active, 100, "g", "per_100g", "assumed", 0.7, title,
                             note="créatine monohydrate pure supposée (100 %), sans autre ingrédient déclaré dans le titre")
    return None


_THOUSANDS = re.compile(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d)\s*(?:mg|g|µg|μg|mcg|ui|iu|kcal|kj)\b)", re.I)


_G_ES = r"\s*(?:g|gr|gramos)\b"        # « 33 gr », « 30 gramos »
_SERVING_ES = [
    # « Tamaño de la ración 20g », « 1 cacito (30 g) », « por porción (30 g) », « Ración: 30 g », « por dosis (30 gr, sabor chocolate) »
    re.compile(r"(?:una|1)?\s*(?:porci[óo]n|raci[óo]n|dosis|toma|cacito|scoop|servicio)(?:es|s)?\s*(?:diaria|recomendada)?\s*[:=(]\s*" + N + _G_ES, re.I),
    re.compile(r"tama[ñn]o (?:de la |de |por )?(?:porci[óo]n|raci[óo]n|dosis|toma)\s*[:=(\-–]?\s*" + N + _G_ES, re.I),   # « Tamaño de la ración - 5g »
    re.compile(r"(?:una |1 )(?:dosis|porci[óo]n|raci[óo]n|toma)[^\n]{0,40}?\(\s*" + N + _G_ES, re.I),
    # « dosis de 30 g », « cada toma de 10 g », « por ración de 30 g », « en cada servicio de 30 g »,
    # « Cada dosis recomendada de 3,6 g », « La dosis recomendada es de 30 g (1 cazo) »
    re.compile(r"(?:\b(?:cada|una|1|por|en)\s+)?\b(?:dosis|porci[óo]n|raci[óo]n|toma|cacito|cuchara(?:da)?|servicio|scoop)\s+"
               r"(?:(?:diaria|recomendada|indicada)\s+)?(?:es\s+)?(?:de|de aproximadamente|de unos)\s+" + N + _G_ES, re.I),
    # « Mezclar 1 scoop de proteína (35 g) », « Mezclar 1 cucharada (30 gr) », « Tomar 1 cazo (50 gr aprox.) »
    # « Mezclar 1 medidas (aproximadamente 3,4 g) » (Bulk)
    re.compile(r"\b(?:\d+(?:[.,]\d+)?|un|una)\s+(?:scoops?|cazos?|cacitos?|cucharadas?|cucharas? de medici[óo]n|medid(?:or|a)s?|dosificador(?:es)?|cuchara medidora)\b"
               r"[^()\n]{0,25}\(\s*(?:aproximadamente|aprox\.?|unos|approx\.?)?\s*" + N + _G_ES, re.I),
    # « Cantidad recomendada: 25 g mezclados en 250 ml de agua »
    re.compile(r"\bcantidad\s+(?:diaria\s+)?recomendada\s*[:=]\s*" + N + _G_ES, re.I),
    # « Mezclar 35 g (1 cazo) con 200-250 ml de agua », « Diluir 30 gr en 250 ml », « Disolver 25 g de producto »
    re.compile(r"\b(?:mezcla(?:r)?|diluir|disolver|disuelve|a[ñn]adir|a[ñn]ade)\s+" + N + _G_ES, re.I),
]


def serving_size(text: str, lang: str = "fr") -> Optional[float]:
    """Poids d'une portion déclaré en texte : « Une portion : 4.1 g », « 1 dose = 30 g », « Dose : 30g »."""
    m = re.search(r"(?:une|1)?\s*(?:portion|dose|mesure|scoop|shaker)s?\s*(?:journali[eè]re|recommand[ée]e)?\s*[:=(]\s*" + N + r"\s*g\b",
                  text, re.I) \
        or re.search(r"(?:taille de la |une |1 )(?:dose|portion)[^\n]{0,40}?\(\s*" + N + r"\s*g\s*\)", text, re.I) \
        or re.search(r"(?:chaque|une|1|par|pour une?)\s+(?:dose|portion|scoop|mesure|cuill[eè]re)\s+(?:de|d['’]environ)\s+" + N + r"\s*g\b", text, re.I)
    if m and 1 <= _f(m.group(1)) <= 150:
        return _f(m.group(1))
    if lang == "es":
        for rx in _SERVING_ES:
            m = rx.search(text)
            if m and 1 <= _f(m.group(1)) <= 150:
                return _f(m.group(1))
    return None


def _per_serving_text(text: str, noun_rx: str, lang: str = "fr") -> Optional[tuple[float, str]]:
    """« 3 g de créatine » (ou « créatine : 3 g ») par portion + poids de la portion : teneur pour 100 g."""
    size = serving_size(text, lang)
    if not size:
        return None
    unit_rx = r"m?g" if lang == "fr" else r"mg|g(?:r|ramos)?"     # espagnol : « 27 gr de proteínas », « 23 gramos de proteína »
    first = None
    sep = r"\s*:?\s*" if lang == "fr" else r"\s*(?:[:|]\s*)*"           # espagnol : « L-glutamina | | 5,0g »
    for m in re.finditer(r"(?<![\d.,])" + N + r"\s*(" + unit_rx + r")\s*(?:de\s+|d['’]\s*)?(?:" + noun_rx + r")\b|(?:" + noun_rx + r")" + sep + N + r"\s*(" + unit_rx + r")\b",
                         text, re.I):
        val, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        grams = _f(val) / (1000 if unit.lower() == "mg" else 1)
        if lang != "fr" and re.search(r"ingesta\s+(?:diaria\s+)?de\s*$", text[max(0, m.start() - 30):m.start()], re.I):
            continue                 # « Una ingesta diaria de 3 g de creatina mejora el rendimiento » : allégation, pas la teneur
        if 0 < grams <= size:
            found = round(grams / size * 100, 1), f"{m.group(0)} {'por dosis de' if lang == 'es' else 'pour une portion de'} {size:g} g"
            if lang == "fr" or re.search(r"monohidrat|monohydrat", m.group(0), re.I):
                return found
            # « 3 g de creatina » puis « 3,4 g de monohidrato de creatina, equivalentes a 3 g de creatina » : comme partout,
            # la teneur de créatine se compte en monohydrate (la poudre de monohydrate pur vaut 100 %)
            first = first or found
    return first


_SERVING_HEAD = re.compile(r"(?:pour|par)\s+(?:une?\s+|1\s+)?(?:portion|dose|scoop|mesure|service|serving)?\s*\(?\s*" + N + r"\s*g\b(?!\s*de)", re.I)


_SERVING_HEAD_ES = re.compile(r"(?:por|cada)\s+(?:una?\s+|1\s+)?(?:porci[óo]n|raci[óo]n|dosis|toma|cacito|scoop|servicio|serving)?"
                              r"(?:\s+diaria)?\s*\(?\s*" + N + r"\s*g\b(?!\s*de)", re.I)


def preworkout_serving(text: str, lang: str = "fr") -> Optional[ActiveContent]:
    """Pré-workout : la portion recommandée par la marque (« 1 dose = 10 g », « Pour 10 g » en tête de tableau).

    Le classement se fait au prix d'une portion : prix au kg × poids de la portion."""
    size = serving_size(text, lang)
    src, ev = "regex_text", ""
    if size is None:
        for line in text.split("\n"):
            if "|" in line:
                m = _SERVING_HEAD.search(line) or (_SERVING_HEAD_ES.search(line) if lang == "es" else None)
                if m and _f(m.group(1)) != 100:
                    size, src, ev = _f(m.group(1)), "regex_table", line.strip()
                    break
    if size is None:
        m = re.search(r"(?:m[ée]langer|diluer|dissoudre)\s+" + N + r"\s*g\b", text, re.I)
        if not m and lang == "es":   # « Mezclar 20g (aproximadamente 2 cacitos) », « Disolver 25 g (2 dosificadores) »
            m = re.search(r"(?:mezcla[r]?|diluir|disolver|disuelve)\s+" + N + r"\s*g\b", text, re.I)
        if m:
            size, ev = _f(m.group(1)), m.group(0)
    if size is None or not 2 <= size <= 40:
        return None
    return ActiveContent("preworkout", "serving", size, "g", "per_serving", src, 0.85,
                         ev or f"portion de {size:g} g", note="portion recommandée par la marque")


def _caffeine_per_100g(text: str, lang: str = "fr") -> Optional[ActiveContent]:
    """Pré-workout : mg de caféine pour 100 g de poudre (« Caféine | 200 mg » pour une dose de 10 g)."""
    rx = r"(?:caf[ée]ine(?: anhydre)?|caffeine(?: anhydrous)?)" if lang == "fr" else \
        r"(?:caf[ée]ine(?: anhydre)?|caffeine(?: anhydrous)?|cafe[íi]na(?: anhidra)?)"
    tv = table_value(text, rx, "100g", lang=lang)
    if tv and tv[1] in ("mg", "g"):
        mg = tv[0] * (1000 if tv[1] == "g" else 1)
        return ActiveContent("preworkout", "caffeine", mg, "mg", "per_100g", "regex_table", 0.9, tv[2])
    ts = table_serving_to_100g(text, rx, lang)        # rend des g pour 100 g
    if ts:
        return ActiveContent("preworkout", "caffeine", round(ts[0] * 1000, 1), "mg", "per_100g", "regex_table", 0.85,
                             ts[1], note="ramené à 100 g depuis la dose")
    size = serving_size(text, lang)
    m = re.search(N + r"\s*mg\s*(?:de\s+)?" + rx, text, re.I) or re.search(rx + r"\s*:?\s*" + N + r"\s*mg", text, re.I)
    if m and size:
        mg = _f(m.group(1))
        if mg < size * 1000:
            return ActiveContent("preworkout", "caffeine", round(mg / size * 100, 1), "mg", "per_100g", "regex_text", 0.8,
                                 f"{m.group(0)} pour une dose de {size:g} g", note="calculé : caféine par dose ÷ poids de la dose")
    return None


def extract(category: str, body_html: str, title: str, fmt: Format, lang: str = "fr") -> Optional[ActiveContent]:
    """Teneur d'une fiche. `lang` : langue du site (« fr » : règles historiques ; « es » : françaises + espagnoles)."""
    lang = (lang or "fr").lower()[:2]
    es = lang == "es"
    text = _THOUSANDS.sub("", html_to_text(body_html))
    full = title + "\n" + text
    if category == "preworkout":
        return preworkout_serving(text, lang)
    if category in ("whey", "caseine"):
        ac = _protein_per_100g(text, lang)
        if ac:
            ac.category = category
        return ac
    if category == "vitamine_c":
        return _per_unit_element(full, "vitamine_c", r"vitamine c|vit\.? ?c|acide l?-?ascorbique"
                                 + (r"|vitamina c|[áa]cido l?-?asc[óo]rbico" if es else ""), "vitamin_c", lang=lang)
    if category == "glutamine":
        return _powder_or_caps(text, "glutamine", "glutamine", r"l-?glutamine|glutamine" + (r"|(?:l[- ]?)?glutamina" if es else ""),
                               title, fmt, lang)
    if category == "barres":
        weight0 = fmt.unit_grams or bar_weight(text, lang)
        tv = table_value(text, _v(lang)["prot"], "unit", lang=lang)
        if tv and tv[1] == "g" and tv[0] < 40:
            if weight0 and tv[0] > 0.5 * weight0:
                # 35 g de protéines dans une barre de 45 g : impossible, c'est la valeur pour 100 g
                return ActiveContent("barres", "protein", round(tv[0] * weight0 / 100, 1), "g", "per_unit",
                                     "regex_table", 0.75, tv[2],
                                     note=f"{tv[0]:g} g lus pour une barre de {weight0:g} g : pris comme valeur pour 100 g")
            return ActiveContent("barres", "protein", tv[0], "g", "per_unit", "regex_table", 0.95, tv[2])
        m = re.search(N + r"\s*g de prot[ée]ines?\s*(?:par|/|dans chaque|dans une)\s*barre", text, re.I)
        if not m and es:             # « 20 g de proteína por barrita »
            m = re.search(N + r"\s*g de prote[íi]nas?\s*(?:por|/|en cada|en una|cada)\s*barrita", text, re.I)
        if m:
            return ActiveContent("barres", "protein", _f(m.group(1)), "g", "per_unit", "regex_text", 0.9, m.group(0))
        per100 = _protein_per_100g(text, lang)
        weight = fmt.unit_grams or bar_weight(text, lang)
        if per100 and weight:
            return ActiveContent("barres", "protein", round(per100.amount * weight / 100, 1), "g", "per_unit",
                                 per100.source, per100.confidence * 0.95, per100.evidence,
                                 note=f"{per100.amount} g pour 100 g × barre de {weight:g} g")
        # « 22,9 g de protéines » seul, sans mention de 100 g : sur une fiche de barre, c'est la teneur par barre.
        noun = r"prot[ée]ines?" if not es else r"(?:prot[ée]ines?|prote[íi]nas?)"
        found = [m for m in re.finditer(N + r"\s*g de " + noun, text, re.I)
                 if not re.search(r"100\s*g|portion|dose" + (r"|porci|raci|dosis" if es else ""), text[m.end():m.end() + 25], re.I)]
        if len(found) == 1 and _f(found[0].group(1)) <= 35:
            return ActiveContent("barres", "protein", _f(found[0].group(1)), "g", "per_unit", "regex_text", 0.75,
                                 found[0].group(0), note="teneur par barre supposée (seule teneur citée sur la fiche)")
        return None
    if category == "zinc":
        return _per_unit_element(full, "zinc", r"zinc|zn", "zinc", lang=lang)
    if category == "magnesium":
        return _per_unit_element(full, "magnesium", r"magn[ée]sium|mg2\+" + (r"|magnesio" if es else ""), "magnesium", lang=lang)
    if category == "vitamine_d":
        return _vitamin_d(full, lang)
    if category == "omega3":
        return _omega3(text, lang)
    if category == "creatine":
        return _powder_or_caps(text, "creatine", "creatine", r"(?:monohydrate de )?cr[ée]atine(?: monohydrate)?|creapure"
                               + (r"|(?:monohidrato de )?creatina(?: monohidrato)?" if es else ""), title, fmt, lang)
    if category == "collagene":
        noun = r"(?:hydrolysat (?:de |d['’])|peptides? (?:de |d['’]))?collag[eè]ne(?: marin| bovin| hydrolys[ée])?"
        if es:
            noun += r"|(?:hidrolizado de |p[ée]ptidos? de )?col[áa]geno(?: marino| bovino| hidrolizado)?"
        ac = _powder_or_caps(text, "collagene", "collagen", noun, title, fmt, lang)
        if ac is None and not (fmt.units and fmt.grams is None):
            # Poudre de peptides de collagène sans ligne « collagène » : ses protéines sont le collagène.
            ingr = re.search(r"ingr[ée]dients?\s*:?\s*([^\n]{0,80})", text, re.I)
            pure = (ingr and re.match(r"\s*(?:\d+\s*%\s*)?(?:peptides?|hydrolysat|collag)", ingr.group(1), re.I)) \
                or re.search(r"peptides? de collag|collagen peptides|hydrolysat de collag|peptan|naticol|verisol", title, re.I)
            if not pure and es:
                # toutes les mentions « Ingredientes » (la première peut être « sin pérdida de ingredientes, pleno disfrute »)
                pure = any(re.match(r"\s*(?:\d+\s*%\s*)?(?:p[ée]ptidos?|hidrolizado|col[áa]geno)", g.group(1), re.I)
                           for g in re.finditer(r"ingredientes?\s*:?\s*([^\n]{0,80})", text, re.I)) \
                    or re.search(r"p[ée]ptidos? de col[áa]geno|col[áa]geno hidrolizado", title, re.I)
            prot = _protein_per_100g(text, lang) if pure else None
            if prot and 60 <= prot.amount <= 100:
                ac = ActiveContent("collagene", "collagen", prot.amount, "g", "per_100g", prot.source,
                                   round(prot.confidence * 0.85, 2), prot.evidence,
                                   note="peptides de collagène : teneur en protéines prise comme teneur en collagène")
        return ac
    return None


def content_from_text(body_html: str, lang: str = "fr") -> tuple[Optional[float], Optional[int]]:
    """« Poids net : 907 g », « Contenance : 120 gélules » quand ni le titre ni la variante ne donnent le format."""
    text = html_to_text(body_html)
    m = re.search(r"(?:poids net|contenance|contenu|quantit[ée] nette|net weight|(?:pot|sachet|doypack|bo[iî]te|"
                  r"pilulier|flacon|seau|tube)\s+de)\s*[:\-|]?\s*" + N +
                  r"\s*(kg|g|gr|g[ée]lules?|comprim[ée]s?|capsules?)\b", text, re.I)
    if not m and lang == "es":       # « Peso neto: 900 g », « Contenido: 90 cápsulas », « bote de 1 kg »
        m = re.search(r"(?:peso neto|contenido neto|contenido|cantidad neta|(?:bote|bolsa|doypack|caja|frasco|cubo|tubo|"
                      r"envase)\s+(?:de|con))\s*[:\-|]?\s*" + N +
                      r"\s*(kg|g|gr|c[áa]psulas?|comprimidos?|tabletas?|perlas?)\b", text, re.I)
    if not m and lang == "es":
        # Sunday Natural : « 360 g de polvo », « 2500 UI + 100 µg x 300 gotas », « 1750 gotas »
        m = re.search(r"(?<![\d.,])" + N + r"\s*(kg|g)\s+(?:de|en)\s+polvo\b", text, re.I)
        if not m:
            mg_ = re.search(r"\bx\s*(\d{2,4})\s*gotas\b|(?<![\d.,])(\d{2,4})\s*gotas\b(?!\s*(?:al|por|cada|diarias))", text, re.I)
            if mg_ and 50 <= int(mg_.group(1) or mg_.group(2)) <= 5000:
                return None, int(mg_.group(1) or mg_.group(2))
    if not m:
        return None, None
    value, unit = _f(m.group(1)), m.group(2).lower()
    if unit == "kg":
        return value * 1000, None
    if unit in ("g", "gr"):
        return value, None
    return None, int(value)


def units_from_text(body_html: str, lang: str = "fr") -> Optional[int]:
    """Nombre d'unités du contenant quand le libellé ne le dit pas (« Emballage suffisant pour 120 jours »)."""
    text = html_to_text(body_html)
    m = re.search(r"(?:bo[iî]te|pot|pilulier|flacon|sachet)\s*de\s*(\d+)\s*(?:" + UNIT_NOUN + ")", text, re.I) \
        or re.search(r"(\d+)\s*(?:g[ée]lules|comprim[ée]s|capsules)\b", text, re.I)
    if not (m and 10 <= int(m.group(1)) <= 1000) and lang == "es":   # « envase con 90 tabletas », « 60 cápsulas »
        m = re.search(r"(?:bote|frasco|caja|envase|blíster|blister)\s*(?:de|con)\s*(\d+)\s*(?:" + _v(lang)["unit"] + ")", text, re.I) \
            or re.search(r"(\d+)\s*(?:c[áa]psulas|comprimidos|tabletas|perlas)\b", text, re.I)
    if m and 10 <= int(m.group(1)) <= 1000:
        return int(m.group(1))
    m = re.search(r"nombre (?:des |de )?doses?[^:]*:\s*(\d+)", text, re.I)
    if not m and lang == "es":
        m = re.search(r"(?:n[úu]mero de (?:dosis|tomas|raciones)|(?:dosis|raciones|porciones) por envase)[^:]*:\s*(\d+)", text, re.I)
    if m:
        dd = daily_dose(text, lang)
        return int(int(m.group(1)) * (dd.units_per_dose or 1))
    # « Cure de 120 jours | 1 gélule par jour », « Emballage suffisant pour 120 jours »
    m = re.search(r"(?:cure de|suffisant pour|pour une cure de)\s*(\d+)\s*(jours|mois)", text, re.I)
    if not m and lang == "es":
        m = re.search(r"(?:para|suficiente para|tratamiento de)\s*(\d+)\s*(d[íi]as|meses)", text, re.I)
    if m:
        dd = daily_dose(text, lang)
        if dd.units_per_dose:
            days = int(m.group(1)) * (30 if m.group(2).lower() in ("mois", "meses") else 1)
            return int(round(days * dd.units_per_dose))
    return None
