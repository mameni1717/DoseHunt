"""Langue des fiches : langue par défaut d'un pays et reconnaissance de la langue d'un texte.

Convention des règles de lecture (classify, extract, details, codes, origin, rayons, formats, pipeline) :
  - « fr » : les règles historiques, strictement inchangées (elles contiennent aussi les termes anglais et les marques) ;
  - autre langue : les règles françaises + les ajouts propres à cette langue (ex. « es »).
Une langue sans ajouts retombe donc sur les règles françaises.
"""
from __future__ import annotations

import re

DEFAULT_LANGUAGE = {"FR": "fr", "BE": "fr", "ES": "es", "DE": "de", "AT": "de", "GB": "en", "IE": "en",
                    "IT": "it", "NL": "nl", "PL": "pl", "SE": "sv", "PT": "pt"}

# Langues pour lesquelles des règles propres existent à côté des règles françaises.
RULE_LANGUAGES = ("fr", "es")


def default_language(country: str) -> str:
    return DEFAULT_LANGUAGE.get((country or "FR").upper(), "fr")


def norm(lang: str | None) -> str:
    """Langue des règles : « fr » si absente."""
    return (lang or "fr").lower()[:2]


# --------------------------------------------------------------------------- reconnaissance de la langue

FR_MARKERS = re.compile(r"\b(le|la|les|des|du|une|pour|avec|sans|est|et|par|vos|votre|chaque)\b|[éèêàùç]", re.I)
FR_FOREIGN = re.compile(
    r"\b(het|een|voor|met|und|mit|für|der|die|das|il|della|delle|degli|per il|con|sono|the|with|and|for|your|"
    r"el|los|las|para|y|es|del|una|al|gli|di|che|ogni|cada|apoyo|sostegno)\b|[ñ¿¡]|ción\b|zione\b", re.I)
FR_FOREIGN_TITLE = re.compile(r"col[áa]geno|magnesio|vitamina|zinco|bisglicinato|integratore|suplemento|proteína|omega 3 de", re.I)

# Espagnol : mots outils et vocabulaire courant des fiches (« proteína, sabor, envío, ingredientes… »).
ES_MARKERS = re.compile(
    r"\b(el|los|las|del|por|con|para|cada|una|es|y|sin|tu|su|sus|al|como|dosis|sabor|env[íi]o|ingredientes|"
    r"prote[íi]na|prote[íi]nas|c[áa]psulas|comprimidos|tomar|mezclar|agua|recomendada|diaria)\b|[ñ¿¡]|ci[óo]n\b|[áíóú]", re.I)
ES_FOREIGN = re.compile(
    r"\b(le|les|des|du|une|pour|avec|sans|est|et|vos|votre|chaque|the|with|and|for|your|het|een|voor|met|und|mit|"
    r"für|der|die|das|il|della|delle|degli|sono|gli|di|che|ogni|não|você|uma|são|também)\b|[èêàùçãõ]|ção\b|ões\b|zione\b", re.I)
ES_FOREIGN_TITLE = re.compile(r"prot[ée]ine\b|g[ée]lules|collag[eè]ne|vitamine\b|magn[ée]sium|integratore|prote[ií]ne\b|"
                              r"kapseln|vitamin\b", re.I)

_MARKERS = {"fr": (FR_MARKERS, FR_FOREIGN, FR_FOREIGN_TITLE), "es": (ES_MARKERS, ES_FOREIGN, ES_FOREIGN_TITLE)}


def looks_language(text: str, lang: str, title: str = "") -> bool:
    """Le texte (titre + début de description) est-il dans la langue `lang` ?

    Langue sans marqueurs connus : rien n'est filtré (True)."""
    rules = _MARKERS.get(norm(lang))
    if rules is None:
        return True
    own, foreign, foreign_title = rules
    if title and foreign_title.search(title):
        return False
    low = (text or "").lower()
    mine = len(own.findall(low))
    other = len(foreign.findall(low))
    return mine >= max(3, other * 1.5)
FOREIGN_MARKERS_COMPAT = FR_FOREIGN   # ancien nom (classify.FOREIGN_MARKERS)
