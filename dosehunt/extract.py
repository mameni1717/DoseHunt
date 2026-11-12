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
WORD_NUM = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "1/2": 0.5, "½": 0.5, "demi": 0.5}


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


def daily_dose(text: str) -> DoseInfo:
    """« Dose journalière 1/2 comprimé », « 2 gélules par jour », « 1 gélule par jour »."""
    t = text.lower()
    pats = [
        r"dose (?:journali[eè]re|quotidienne)\s*[:\-(]?\s*(1/2|½|demi|\d+|une?|deux|trois)\s*(?:" + UNIT_NOUN + ")",
        r"(1/2|½|demi|\d+|une?|deux|trois)\s*(?:" + UNIT_NOUN + r")\s*(?:par|/)\s*jour",
        r"prendre\s*(1/2|½|demi|\d+|une?|deux|trois)\s*(?:" + UNIT_NOUN + ")",
    ]
    for p in pats:
        m = re.search(p, t)
        if m:
            return DoseInfo(_count(m.group(1)), m.group(0))
    return DoseInfo()


def _dose_after(text: str, pos: int, window: int = 90) -> tuple[Optional[float], str]:
    """Cherche « par gélule », « pour 2 gélules », « dans 1/2 comprimé » juste après une teneur."""
    seg = text[pos:pos + window].lower()
    m = re.search(r"(?:par|pour|/|dans|en)\s*(1/2|½|demi|\d+|une?|deux|trois)?\s*(" + UNIT_NOUN + ")", seg)
    if not m:
        return None, ""
    noun = m.group(2)
    if re.match(r"doses?|portions?", noun):
        return -1, m.group(0)        # « par dose » : à résoudre avec la dose journalière
    return _count(m.group(1)), m.group(0)


def _dose_before(text: str, pos: int, window: int = 60) -> tuple[Optional[float], str]:
    seg = text[max(0, pos - window):pos].lower()
    # « 3 gélules seulement apportent 300 mg », « 2 capsules contiennent 1 000 UI »
    m = re.search(r"(1/2|½|\d+|une?|deux|trois)\s*(" + UNIT_NOUN + r")\s*(?:\S+\s+){0,2}?"
                  r"(?:apportent|apporte|contiennent|contient|fournissent|fournit|=)\s*$", seg)
    if m and not re.match(r"doses?|portions?", m.group(2)):
        return _count(m.group(1)), m.group(0)
    m = None
    for m in re.finditer(r"(?:dans|pour|par)\s*(1/2|½|demi|\d+|une?|deux|trois)?\s*(" + UNIT_NOUN + ")", seg):
        pass
    if not m:
        return None, ""
    if re.match(r"doses?|portions?", m.group(2)):
        return -1, m.group(0)
    return _count(m.group(1)), m.group(0)


def _table_header_dose(text: str, pos: int) -> tuple[Optional[float], str]:
    """En-tête du tableau qui contient la valeur : « Ingrédient | Pour 2 gélules | AR* »."""
    lines = text[max(0, pos - 600):pos].split("\n")[:-1]     # la dernière est le début de la ligne courante
    for line in reversed(lines):
        if "|" not in line:
            break                                   # sortie du tableau
        m = re.search(r"(?:pour|par)\s*(1/2|½|\d+|une?|deux|trois)\s*(" + UNIT_NOUN + ")", line, re.I)
        if m:
            return (-1, line) if re.match(r"doses?|portions?", m.group(2), re.I) else (_count(m.group(1)), line)
    return None, ""


# --------------------------------------------------------------------------- tableau nutritionnel

def table_rows(text: str) -> list[list[str]]:
    return [[c.strip() for c in ln.split("|")] for ln in text.split("\n") if "|" in ln]


def table_value(text: str, row_rx: str, want: str) -> Optional[tuple[float, str, str]]:
    """Valeur d'une ligne du tableau nutritionnel. want = '100g' ou 'unit'. Renvoie (valeur, unité, preuve)."""
    rows = table_rows(text)
    col100 = colunit = None
    header_len = 0
    for row in rows:
        lower = [c.lower() for c in row]
        if any(re.search(r"100\s*g|100\s*ml", c) for c in lower) or any(re.search(r"par|pour|portion|dose|barre", c) for c in lower[1:]):
            col100 = colunit = None
            header_len = len(row)
            for i, c in enumerate(lower):
                if re.search(r"100\s*g", c) and col100 is None:
                    col100 = i
                elif re.search(r"barre|portion|dose|g[ée]lule|comprim|capsule|stick|shaker|\d+\s*g\)", c) and i > 0 and colunit is None:
                    colunit = i
        if re.match(row_rx, lower[0] if lower else "") and not re.search(r"mati[eè]re s[eè]che", lower[0]):
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
                    return _f(m.group(1)), (m.group(2) or "g").replace("μ", "µ"), " | ".join(row)
    return None


def table_serving_to_100g(text: str, row_rx: str) -> Optional[tuple[float, str]]:
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
        if head and _f(head.group(1)) == 100:
            head = None
        if head:
            serving = _f(head.group(1))
            continue
        if serving and re.match(row_rx, cells[0].lower()) and not re.search(r"mati[eè]re s[eè]che", cells[0].lower()):
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


def bar_weight(text: str) -> Optional[float]:
    m = re.search(r"par barre\s*\(?\s*" + N + r"\s*g", text, re.I) or re.search(r"barres? de\s*" + N + r"\s*g", text, re.I) \
        or re.search(N + r"\s*g de (?:crunchy|crispy|moelleux|croustillance|gourmandise)", text, re.I)
    return _f(m.group(1)) if m else None


# --------------------------------------------------------------------------- par catégorie

def _protein_per_100g(text: str) -> Optional[ActiveContent]:
    tv = table_value(text, r"prot[ée]ines?|protein", "100g")
    if tv and tv[1] == "g":
        return ActiveContent("whey", "protein", tv[0], "g", "per_100g", "regex_table", 0.95, tv[2])
    ts = table_serving_to_100g(text, r"prot[ée]ines?|protein")
    if ts:
        return ActiveContent("whey", "protein", ts[0], "g", "per_100g", "regex_table", 0.9, ts[1],
                             note="tableau par portion seulement : valeur ramenée à 100 g")
    for rx, conf in [
        (r"prot[ée]ines?\s*[:\-]?\s*" + N + r"\s*g\s*(?:pour|/|par)\s*100\s*g", 0.9),
        (N + r"\s*g de prot[ée]ines?\s*(?:pour|/|par|aux)\s*100\s*g", 0.9),
        (N + r"[ \t]*%[ \t]*(?:de[ \t]*)?prot[ée]ines?", 0.85),
        (r"(?:teneur|taux) (?:en|de) prot[ée]ines?\s*(?:de|:)?\s*" + N + r"\s*%", 0.85),
    ]:
        for m in re.finditer(rx, text, re.I):
            after = text[m.end():m.end() + 30].lower()
            # « composée à 100 % de protéines de lactosérum » décrit l'origine, pas la teneur
            if _f(m.group(1)) < 20:
                continue                                # « 2 % » d'AR, de matières grasses… : pas une teneur de poudre protéinée
            if "%" in m.group(0) and (_f(m.group(1)) >= 98 or re.match(r"\s*(de lactos|de whey|d['’]origine|laiti|v[ée]g[ée]tal)", after)):
                continue
            return ActiveContent("whey", "protein", _f(m.group(1)), "g", "per_100g", "regex_text", conf, m.group(0))
    m = re.search(N + r"\s*g de prot[ée]ines?.{0,40}?(?:par|pour|/|dans)\s*(?:une\s*)?(?:portion|dose|shaker|scoop|mesure|service)?\s*(?:de\s*)?" + N + r"\s*g",
                  text, re.I | re.S)
    if m and 5 <= _f(m.group(2)) <= 100:
        per100 = round(_f(m.group(1)) / _f(m.group(2)) * 100, 1)
        return ActiveContent("whey", "protein", per100, "g", "per_100g", "regex_text", 0.85, m.group(0),
                             note=f"calculé : {m.group(1)} g pour {m.group(2)} g")
    pst = _per_serving_text(text, r"prot[ée]ines?")
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


def _dose_from_title(title: str, amount: float, category: str, upd: float, conf: float, note: str):
    """Dose inconnue (« par dose ») : le titre aide à trancher.

    « Citrate de magnésium 112,5mg » + « 225 mg par dose » → 2 unités par dose.
    « Magnesium malate 1000mg » + « 346,5 mg par dose » : 346,5 mg de magnésium ne tiennent pas dans 1 000 mg de
    malate (≤ 17 %) → la dose compte plusieurs unités, nombre inconnu : confiance abaissée, revue humaine.
    """
    m = re.search(N + r"\s*mg\b", title, re.I)
    if not m:
        return upd, amount, conf, note
    label = _f(m.group(1))
    salt = next((s_ for s_ in ELEMENT_SHARE.get(category, {}) if re.search(s_, title, re.I)), None)
    if salt and label >= 300:                        # poids du sel dans le titre (« malate 1000mg »)
        if amount > label * ELEMENT_SHARE[category][salt]:
            return upd, amount, 0.4, (f"{amount:g} mg par dose dépassent ce que contient une unité de {label:g} mg de "
                                      f"{salt} : dose de plusieurs unités, à vérifier")
        return upd, amount, conf, note
    ratio = amount / label if label else 0
    k = round(ratio)
    if 2 <= k <= 4 and abs(ratio - k) < 0.02:
        return k, amount, 0.85, f"{amount:g} mg par dose et {label:g} mg par unité selon le titre : dose de {k} unités"
    return upd, amount, conf, note


def _per_unit_element(text: str, category: str, element_rx: str, active: str, unit: str = "mg") -> Optional[ActiveContent]:
    """Zinc, magnésium : quantité d'élément par gélule/comprimé, en écartant le poids du sel."""
    t = text
    salt_label = None
    candidates: list[tuple[float, str, int, int, str]] = []    # (valeur, unité, début, fin, source)

    # a) « 12 mg de zinc », « 15 mg de zinc élément »
    for m in re.finditer(N + r"[ \t]*(mg|g|µg)[ \t]*(?:de[ \t]+|d['’][ \t]*)?(?:" + element_rx + r")(?![ \t]*(?:" + SALTS + "))", t, re.I):
        candidates.append((_f(m.group(1)), m.group(2).lower(), m.start(), m.end(), "regex_text"))
    # b) « Zinc 12,5 g (VNR 125 %) », « Zinc | 15 mg | 150 % », sauf « gluconate de zinc 120 mg »
    for m in re.finditer(r"(?<![\w-])(?:" + element_rx + r")(?:[ \t]+[ée]l[ée]ment(?:aire)?)?[ \t]*[:|\-]?[ \t]*(?:\|[ \t]*)?" + N + r"[ \t]*(mg|g|µg)\b", t, re.I):
        before = t[max(0, m.start() - 30):m.start()].lower()
        if re.search(r"(" + SALTS + r")\s*(?:de|d['’])\s*$", before):
            salt_label = _f(m.group(1)) * (1000 if m.group(2).lower() == "g" else 1)
            continue
        src = "regex_table" if "|" in t[m.start():m.end()] else "regex_text"
        candidates.append((_f(m.group(1)), m.group(2).lower(), m.start(), m.end(), src))
    # c) poids du sel affiché : « Gluconate de zinc 120 mg », « 50 mg de bisglycinate de zinc »
    if salt_label is None:
        m = re.search(r"(?:" + SALTS + r")\s*(?:de|d['’])\s*(?:" + element_rx + r")\s*[:\-]?\s*" + N + r"\s*mg", t, re.I) \
            or re.search(N + r"\s*mg\s*(?:de\s+)?(?:" + SALTS + r")\s*(?:de|d['’])\s*(?:" + element_rx + ")", t, re.I)
        if m:
            salt_label = _f(m.group(1))
    if not candidates:
        return None

    tables = [c for c in candidates if c[4] == "regex_table"]
    val, u, start, end, src = (tables or candidates)[0]
    amount = val * {"mg": 1, "g": 1000, "µg": 0.001}[u]
    upd, ev = (None, "")
    if src == "regex_table":
        heads = list(re.finditer(r"(?:pour|par|dans)\s+(?:dose (?:journali[eè]re\s*)?\(?\s*)?(1/2|½|\d+|une?|deux|trois)\s*(" + UNIT_NOUN + r")",
                                 t[max(0, start - 800):start], re.I))
        if heads and not re.match(r"doses?|portions?", heads[-1].group(2)):
            upd, ev = _count(heads[-1].group(1)), heads[-1].group(0)
    if upd is None:
        upd, ev = _dose_after(t, end)
    if upd is None:
        upd, ev = _dose_before(t, start)
    if upd is None and src == "regex_table":
        upd, ev = _table_header_dose(t, start)
    note = None
    conf = 0.95 if src == "regex_table" else 0.9
    if upd == -1 or upd is None:
        dd = daily_dose(t)
        if dd.units_per_dose:
            upd, ev = dd.units_per_dose, (ev + " ; " + dd.evidence).strip(" ;")
        else:
            upd = 1
            conf = 0.6
            note = "dose d'une unité supposée (la fiche ne précise pas le nombre d'unités par dose)"
    if note and upd == 1:
        upd, amount, conf, note = _dose_from_title(t.split("\n", 1)[0], amount, category, upd, conf, note)
    per_unit = amount / upd
    if salt_label and abs(salt_label - per_unit) < 0.5:
        salt_label = None                            # « 112,5 mg » du titre = teneur réelle par unité, pas le sel
    form = None
    fm = re.search(r"(" + SALTS + ")", t, re.I)
    if fm:
        form = fm.group(1).lower()
    return ActiveContent(category, active, round(per_unit, 3), unit, "per_unit", src, conf,
                         t[max(0, start - 20):end + 60].replace("\n", " "), units_per_dose=upd,
                         salt_label_mg=salt_label, form=form, note=note)


def _vitamin_d(text: str) -> Optional[ActiveContent]:
    m = re.search(BIG + r"\s*(?:UI|IU)\b", text, re.I)
    ui = None
    if m:
        ui, start, end = _f(m.group(1)), m.start(), m.end()
    else:
        m = re.search(N + r"\s*(?:µg|μg|mcg|ug)\s*(?:de\s+)?(?:vitamine\s*)?d3?", text, re.I)
        if m:
            ui, start, end = _f(m.group(1)) * 40, m.start(), m.end()
    if ui is None:
        return None
    upd, ev = _dose_after(text, end)
    if upd is None:
        upd, ev = _dose_before(text, start)
    conf, note = 0.9, None
    if upd in (None, -1):
        dd = daily_dose(text)
        upd = dd.units_per_dose or 1
        if not dd.units_per_dose:
            conf, note = 0.6, "dose d'une unité supposée"
    return ActiveContent("vitamine_d", "vitamin_d", round(ui / upd, 1), "UI", "per_unit", "regex_text", conf,
                         text[max(0, start - 20):end + 60].replace("\n", " "), units_per_dose=upd, note=note)


def _omega3(text: str) -> Optional[ActiveContent]:
    def grab(name):
        m = re.search(N + r"\s*mg\s*(?:d['’]\s*|de\s*)?(?:acide\s+\w+\s+)?\(?" + name + r"\b", text, re.I) \
            or re.search(r"\b" + name + r"\b[^|\n\d]{0,40}[:|\-]?\s*(?:\|\s*)?" + N + r"\s*mg", text, re.I)
        return (m, _f(m.group(1))) if m else (None, None)
    m_sum = re.search(N + r"\s*mg\s*(?:d['’]\s*)?(?:epa\s*(?:\+|et)\s*dha|om[ée]ga[- ]?3)", text, re.I)
    me, epa = grab("EPA")
    md, dha = grab("DHA")
    if epa is not None and dha is not None:
        total, anchor = epa + dha, max(me.end(), md.end())
        start = min(me.start(), md.start())
    elif m_sum:
        total, anchor, start = _f(m_sum.group(1)), m_sum.end(), m_sum.start()
    else:
        return None
    upd = _table_header_dose(text, start)[0] if "|" in text[start:anchor + 1] else None
    if upd is None:
        upd, _ = _dose_after(text, anchor)
    if upd is None:
        upd, _ = _dose_before(text, start)
    conf, note = 0.9, None
    if upd in (None, -1):
        dd = daily_dose(text)
        upd = dd.units_per_dose or 1
        if not dd.units_per_dose:
            conf, note = 0.6, "dose d'une capsule supposée"
    return ActiveContent("omega3", "epa_dha", round(total / upd, 1), "mg", "per_unit", "regex_text", conf,
                         text[max(0, start - 10):anchor + 40].replace("\n", " "), units_per_dose=upd, note=note)


def _powder_or_caps(text: str, category: str, active: str, noun_rx: str, title: str, fmt: Format) -> Optional[ActiveContent]:
    """Créatine, collagène : poudre (g pour 100 g) ou gélules (mg par unité)."""
    if fmt.units and fmt.grams is None:          # gélules
        m = re.search(BIG + r"\s*mg\s*(?:de\s+)?(?:peptides de\s+)?(?:" + noun_rx + ")", text, re.I)
        if m:
            upd, _ = _dose_after(text, m.end())
            if upd is None:
                upd, _ = _dose_before(text, m.start())
            conf = 0.9
            if upd in (None, -1):
                dd = daily_dose(text)
                upd = dd.units_per_dose or 1
                conf = 0.9 if dd.units_per_dose else 0.6
            return ActiveContent(category, active, round(_f(m.group(1)) / upd, 1), "mg", "per_unit", "regex_text", conf,
                                 m.group(0), units_per_dose=upd)
        return None
    m = re.search(N + r"\s*g\s*(?:de\s+|d['’]\s*)?(?:peptides de\s+)?(?:" + noun_rx + r").{0,50}?(?:par|pour|/|dans)\s*(?:une\s*)?(?:portion|dose|mesure|stick|sachet|shaker)?\s*(?:de\s*)?" + N + r"\s*g",
                  text, re.I | re.S)
    if m and _f(m.group(2)) >= _f(m.group(1)):
        per100 = round(_f(m.group(1)) / _f(m.group(2)) * 100, 1)
        return ActiveContent(category, active, per100, "g", "per_100g", "regex_text", 0.85, m.group(0),
                             note=f"calculé : {m.group(1)} g pour {m.group(2)} g")
    tv = table_value(text, r"(?:" + noun_rx + ")", "100g")
    if tv and tv[1] == "g" and tv[0] <= 100:
        return ActiveContent(category, active, tv[0], "g", "per_100g", "regex_table", 0.9, tv[2])
    ts = table_serving_to_100g(text, r"(?:hydrolysat de |peptides? de )?(?:" + noun_rx + ")")
    if ts:
        return ActiveContent(category, active, ts[0], "g", "per_100g", "regex_table", 0.85, ts[1],
                             note="ramené à 100 g depuis la colonne « par portion »")
    pst = _per_serving_text(text, noun_rx)
    if pst:
        return ActiveContent(category, active, pst[0], "g", "per_100g", "regex_text", 0.8, pst[1],
                             note="calculé : quantité par portion ÷ poids de la portion")
    if category == "creatine" and re.search(r"monohydrat|creapure|micronis|100\s*%|pure", title, re.I) \
            and not re.search(r"complexe|\+|matrix|blend|pre|ph-x|malate|hcl|plus", title, re.I):
        return ActiveContent(category, active, 100, "g", "per_100g", "assumed", 0.7, title,
                             note="créatine monohydrate pure supposée (100 %), sans autre ingrédient déclaré dans le titre")
    return None


_THOUSANDS = re.compile(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d)\s*(?:mg|g|µg|μg|mcg|ui|iu|kcal|kj)\b)", re.I)


def serving_size(text: str) -> Optional[float]:
    """Poids d'une portion déclaré en texte : « Une portion : 4.1 g », « 1 dose = 30 g », « Dose : 30g »."""
    m = re.search(r"(?:une|1)?\s*(?:portion|dose|mesure|scoop|shaker)s?\s*(?:journali[eè]re|recommand[ée]e)?\s*[:=(]\s*" + N + r"\s*g\b",
                  text, re.I)
    if m and 1 <= _f(m.group(1)) <= 150:
        return _f(m.group(1))
    return None


def _per_serving_text(text: str, noun_rx: str) -> Optional[tuple[float, str]]:
    """« 3 g de créatine » (ou « créatine : 3 g ») par portion + poids de la portion : teneur pour 100 g."""
    size = serving_size(text)
    if not size:
        return None
    for m in re.finditer(r"(?<![\d.,])" + N + r"\s*(m?g)\s*(?:de\s+|d['’]\s*)?(?:" + noun_rx + r")\b|(?:" + noun_rx + r")\s*:?\s*" + N + r"\s*(m?g)\b",
                         text, re.I):
        val, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        grams = _f(val) / (1000 if unit.lower() == "mg" else 1)
        if 0 < grams <= size:
            return round(grams / size * 100, 1), f"{m.group(0)} pour une portion de {size:g} g"
    return None


def extract(category: str, body_html: str, title: str, fmt: Format) -> Optional[ActiveContent]:
    text = _THOUSANDS.sub("", html_to_text(body_html))
    full = title + "\n" + text
    if category == "whey":
        return _protein_per_100g(text)
    if category == "barres":
        weight0 = fmt.unit_grams or bar_weight(text)
        tv = table_value(text, r"prot[ée]ines?|protein", "unit")
        if tv and tv[1] == "g" and tv[0] < 40:
            if weight0 and tv[0] > 0.5 * weight0:
                # 35 g de protéines dans une barre de 45 g : impossible, c'est la valeur pour 100 g
                return ActiveContent("barres", "protein", round(tv[0] * weight0 / 100, 1), "g", "per_unit",
                                     "regex_table", 0.75, tv[2],
                                     note=f"{tv[0]:g} g lus pour une barre de {weight0:g} g : pris comme valeur pour 100 g")
            return ActiveContent("barres", "protein", tv[0], "g", "per_unit", "regex_table", 0.95, tv[2])
        m = re.search(N + r"\s*g de prot[ée]ines?\s*(?:par|/|dans chaque|dans une)\s*barre", text, re.I)
        if m:
            return ActiveContent("barres", "protein", _f(m.group(1)), "g", "per_unit", "regex_text", 0.9, m.group(0))
        per100 = _protein_per_100g(text)
        weight = fmt.unit_grams or bar_weight(text)
        if per100 and weight:
            return ActiveContent("barres", "protein", round(per100.amount * weight / 100, 1), "g", "per_unit",
                                 per100.source, per100.confidence * 0.95, per100.evidence,
                                 note=f"{per100.amount} g pour 100 g × barre de {weight:g} g")
        # « 22,9 g de protéines » seul, sans mention de 100 g : sur une fiche de barre, c'est la teneur par barre.
        found = [m for m in re.finditer(N + r"\s*g de prot[ée]ines?", text, re.I)
                 if not re.search(r"100\s*g|portion|dose", text[m.end():m.end() + 25], re.I)]
        if len(found) == 1 and _f(found[0].group(1)) <= 35:
            return ActiveContent("barres", "protein", _f(found[0].group(1)), "g", "per_unit", "regex_text", 0.75,
                                 found[0].group(0), note="teneur par barre supposée (seule teneur citée sur la fiche)")
        return None
    if category == "zinc":
        return _per_unit_element(full, "zinc", r"zinc|zn", "zinc")
    if category == "magnesium":
        return _per_unit_element(full, "magnesium", r"magn[ée]sium|mg2\+", "magnesium")
    if category == "vitamine_d":
        return _vitamin_d(full)
    if category == "omega3":
        return _omega3(text)
    if category == "creatine":
        return _powder_or_caps(text, "creatine", "creatine", r"(?:monohydrate de )?cr[ée]atine(?: monohydrate)?|creapure", title, fmt)
    if category == "collagene":
        ac = _powder_or_caps(text, "collagene", "collagen",
                             r"(?:hydrolysat (?:de |d['’])|peptides? (?:de |d['’]))?collag[eè]ne(?: marin| bovin| hydrolys[ée])?", title, fmt)
        if ac is None and not (fmt.units and fmt.grams is None):
            # Poudre de peptides de collagène sans ligne « collagène » : ses protéines sont le collagène.
            ingr = re.search(r"ingr[ée]dients?\s*:?\s*([^\n]{0,80})", text, re.I)
            pure = (ingr and re.match(r"\s*(?:\d+\s*%\s*)?(?:peptides?|hydrolysat|collag)", ingr.group(1), re.I)) \
                or re.search(r"peptides? de collag|collagen peptides|hydrolysat de collag|peptan|naticol|verisol", title, re.I)
            prot = _protein_per_100g(text) if pure else None
            if prot and 60 <= prot.amount <= 100:
                ac = ActiveContent("collagene", "collagen", prot.amount, "g", "per_100g", prot.source,
                                   round(prot.confidence * 0.85, 2), prot.evidence,
                                   note="peptides de collagène : teneur en protéines prise comme teneur en collagène")
        return ac
    return None


def content_from_text(body_html: str) -> tuple[Optional[float], Optional[int]]:
    """« Poids net : 907 g », « Contenance : 120 gélules » quand ni le titre ni la variante ne donnent le format."""
    text = html_to_text(body_html)
    m = re.search(r"(?:poids net|contenance|contenu|quantit[ée] nette|net weight|(?:pot|sachet|doypack|bo[iî]te|"
                  r"pilulier|flacon|seau|tube)\s+de)\s*[:\-|]?\s*" + N +
                  r"\s*(kg|g|gr|g[ée]lules?|comprim[ée]s?|capsules?)\b", text, re.I)
    if not m:
        return None, None
    value, unit = _f(m.group(1)), m.group(2).lower()
    if unit == "kg":
        return value * 1000, None
    if unit in ("g", "gr"):
        return value, None
    return None, int(value)


def units_from_text(body_html: str) -> Optional[int]:
    """Nombre d'unités du contenant quand le libellé ne le dit pas (« Emballage suffisant pour 120 jours »)."""
    text = html_to_text(body_html)
    m = re.search(r"(?:bo[iî]te|pot|pilulier|flacon|sachet)\s*de\s*(\d+)\s*(?:" + UNIT_NOUN + ")", text, re.I) \
        or re.search(r"(\d+)\s*(?:g[ée]lules|comprim[ée]s|capsules)\b", text, re.I)
    if m and 10 <= int(m.group(1)) <= 1000:
        return int(m.group(1))
    m = re.search(r"nombre (?:des |de )?doses?[^:]*:\s*(\d+)", text, re.I)
    if m:
        dd = daily_dose(text)
        return int(int(m.group(1)) * (dd.units_per_dose or 1))
    # « Cure de 120 jours | 1 gélule par jour », « Emballage suffisant pour 120 jours »
    m = re.search(r"(?:cure de|suffisant pour|pour une cure de)\s*(\d+)\s*(jours|mois)", text, re.I)
    if m:
        dd = daily_dose(text)
        if dd.units_per_dose:
            days = int(m.group(1)) * (30 if m.group(2).lower() == "mois" else 1)
            return int(round(days * dd.units_per_dose))
    return None
