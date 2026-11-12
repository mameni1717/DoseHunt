"""Extraction de secours par un modèle de langage, quand les règles ne trouvent rien.

Activée seulement si ANTHROPIC_API_KEY est défini. Le résultat passe par les mêmes contrôles
de cohérence que l'extraction par règles, et il est mis en cache par empreinte de la
description : une fiche n'est relue que si son texte change.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import httpx

from .collectors.base import html_to_text
from .models import ActiveContent

log = logging.getLogger(__name__)

MODEL = os.environ.get("DOSEHUNT_LLM_MODEL", "claude-haiku-5-5")
API_URL = "https://api.anthropic.com/v1/messages"

ACTIVE_SPEC = {
    "whey": ("protein", "g", "per_100g", "grammes de protéines pour 100 g de poudre"),
    "preworkout": ("caffeine", "mg", "per_100g", "mg de caféine pour 100 g de poudre"),
    "glutamine": ("glutamine", "g", "per_100g", "grammes de glutamine pour 100 g de poudre (ou mg par gélule si gélules)"),
    "vitamine_c": ("vitamin_c", "mg", "per_unit", "mg de vitamine C par gélule ou comprimé"),
    "collagene": ("collagen", "g", "per_100g", "grammes de collagène pour 100 g de poudre (ou mg par gélule si gélules)"),
    "creatine": ("creatine", "g", "per_100g", "grammes de créatine pour 100 g de poudre (ou mg par gélule si gélules)"),
    "barres": ("protein", "g", "per_unit", "grammes de protéines par barre"),
    "zinc": ("zinc", "mg", "per_unit", "mg de zinc ÉLÉMENT par gélule ou comprimé (jamais le poids du sel : gluconate, citrate…)"),
    "magnesium": ("magnesium", "mg", "per_unit", "mg de magnésium ÉLÉMENT par gélule ou comprimé (jamais le poids du sel)"),
    "vitamine_d": ("vitamin_d", "UI", "per_unit", "UI de vitamine D par gélule, comprimé ou goutte (1 µg = 40 UI)"),
    "omega3": ("epa_dha", "mg", "per_unit", "mg d'EPA + DHA par capsule"),
}

PROMPT = """Tu lis une fiche de complément alimentaire pour un comparateur de prix.
Catégorie : {category}. Donnée demandée : {what}.
Si la fiche donne la quantité par dose de plusieurs unités (ex. « pour 2 gélules »), divise.
Si la donnée n'est pas dans le texte, réponds null : n'invente rien, ne devine pas d'après la marque.

Réponds uniquement en JSON :
{{"amount": nombre ou null, "unit": "{unit}", "basis": "per_100g" | "per_unit",
  "units_per_dose": nombre ou null, "units_in_container": nombre ou null,
  "evidence": "citation exacte et courte du texte qui donne la valeur",
  "salt_label_mg": nombre ou null, "form": "bisglycinate|citrate|…" ou null}}

Titre : {title}
Formats vendus : {formats}

Fiche :
{text}"""


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def llm_extract(category: str, title: str, body_html: str, formats: list[str]) -> Optional[ActiveContent]:
    if not enabled() or category not in ACTIVE_SPEC:
        return None
    active, unit, basis, what = ACTIVE_SPEC[category]
    text = html_to_text(body_html)[:12000]
    if len(text) < 40:
        return None
    prompt = PROMPT.format(category=category, what=what, unit=unit, title=title,
                           formats=", ".join(formats[:8]), text=text)
    try:
        resp = httpx.post(API_URL, timeout=60, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, json={"model": MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]})
        resp.raise_for_status()
        content = resp.json()["content"][0]["text"]
        data = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
    except Exception as exc:          # réseau, quota, JSON invalide : on n'invente rien
        log.warning("Extraction IA échouée pour %s : %s", title, exc)
        return None
    if data.get("amount") in (None, "", 0):
        return None
    evidence = (data.get("evidence") or "").strip()
    # L'IA doit citer le texte : une citation absente de la fiche fait baisser la confiance.
    quoted = evidence and re.sub(r"\s+", " ", evidence.lower())[:40] in re.sub(r"\s+", " ", text.lower())
    return ActiveContent(
        category=category, active=active, amount=float(data["amount"]), unit=data.get("unit") or unit,
        basis=data.get("basis") or basis, source="llm", confidence=0.8 if quoted else 0.5,
        evidence=evidence, units_per_dose=data.get("units_per_dose"),
        salt_label_mg=data.get("salt_label_mg"), form=data.get("form"),
        note=None if quoted else "citation de l'IA introuvable dans la fiche",
    )
