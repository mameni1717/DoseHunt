"""Interface commune des collecteurs."""
from __future__ import annotations

import html
import re
from abc import ABC, abstractmethod
from typing import Iterator, Optional

from ..config import Site
from ..http import PoliteClient
from ..models import RawProduct


class Collector(ABC):
    """Un collecteur relève tout le catalogue d'un site et produit des RawProduct.

    Il ne classe pas et n'extrait pas les teneurs : il relève fidèlement ce que le site publie.
    """

    platform: str = ""

    def __init__(self, site: Site, client: Optional[PoliteClient] = None):
        self.site = site
        self.client = client or PoliteClient(delay_seconds=site.delay_seconds, language=site.language)
        self.only_urls: Optional[list[str]] = None      # mise à jour ciblée (top 50) : fiches connues, sans parcours

    @abstractmethod
    def iter_products(self) -> Iterator[RawProduct]:
        ...

    def collect(self) -> list[RawProduct]:
        return list(self.iter_products())


class NotYetImplemented(Collector):
    """Plateformes prévues mais pas encore branchées (PrestaShop, Magento, sur-mesure, flux)."""

    PLAN = {
        "prestashop": "Lire le sitemap produits puis le JSON-LD de chaque fiche ; variantes via "
                      "l'action « refresh » de la fiche (index.php?controller=product&ajax=1&action=refresh).",
        "magento": "Lire le sitemap produits puis le JSON-LD ; prix par variante via le bloc "
                   "« jsonConfig » des produits configurables.",
        "custom": "Collecteur dédié par site : données structurées (JSON-LD) des fiches en priorité.",
        "affiliate_feed": "Importer le flux produits du réseau d'affiliation (CSV/XML Awin, Effiliation…).",
    }

    def iter_products(self) -> Iterator[RawProduct]:
        raise NotImplementedError(
            f"Collecteur « {self.site.collector} » pas encore écrit pour {self.site.name}. "
            f"Plan : {self.PLAN.get(self.site.collector, '—')}"
        )


# --------------------------------------------------------------------------- utilitaires

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def html_to_text(raw: str) -> str:
    """Texte lisible d'une description HTML, en gardant une ligne par bloc et par cellule."""
    if not raw:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    text = re.sub(r"\s+", " ", text)          # les retours à la ligne du HTML ne comptent pas
    # Dans une cellule de tableau, <br> et <p> ne doivent pas casser la ligne du tableau.
    text = re.sub(r"(?is)(<t[dh][^>]*>)(.*?)(</t[dh]>)",
                  lambda m: m.group(1) + re.sub(r"(?i)<br\s*/?>|</?p[^>]*>|</?div[^>]*>", " ", m.group(2)) + m.group(3),
                  text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h\d|table|ul|ol)>", "\n", text)
    text = re.sub(r"(?i)</t[dh]>", " | ", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text).replace("\xa0", " ").replace(" ", " ")
    lines = [_WS.sub(" ", ln).strip(" |") for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def to_price(value) -> Optional[float]:
    if value in (None, "", "0", "0.00", 0):
        return None
    try:
        price = float(str(value).replace(",", "."))
    except ValueError:
        return None
    return price if price > 0 else None


_HINT = re.compile(
    r"(?:(?:pot|sachet|doypack|bo[iî]te|pilulier|flacon|seau|tube)\s+de\s+)?"
    r"(\d+(?:[.,]\d+)?)\s?(kg|g|g[ée]lules?|capsules?|comprim[ée]s?)\b"
    r"(?=\s*(?:-|–|·|\(|/)?\s*(?:\d+\s*(?:portions?|doses?|jours|servings?)|\(?\d+\s*mois|\(?1\s*mois))", re.I)
_CONTAINER = re.compile(r"\b(pot|sachet|doypack|bo[iî]te|pilulier|flacon|seau|tube)\s+de\s+(\d+(?:[.,]\d+)?)\s?(kg|g|g[ée]lules?|capsules?|comprim[ée]s?)\b", re.I)


def format_hint(page_html: str) -> Optional[str]:
    """Format le plus cité sur la page (« 900g - 30 portions », « Pot de 500 g ») quand la déclinaison ne le donne pas.

    Les tableaux nutritionnels (« Pour 30g ») ne comptent pas : seules les mentions suivies d'un nombre de portions,
    de jours ou de mois, ou précédées d'un contenant (pot, pilulier…), sont retenues.
    """
    text = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page_html or ""))
    text = html.unescape(text)
    counts: dict[str, int] = {}
    for m in list(_HINT.finditer(text)) + list(_CONTAINER.finditer(text)):
        num, unit = (m.group(1), m.group(2)) if m.re is _HINT else (m.group(2), m.group(3))
        key = f"{num.replace(',', '.')} {unit.lower()}"
        counts[key] = counts.get(key, 0) + (2 if m.re is _CONTAINER else 1)
    if not counts:
        return None
    best, n = max(counts.items(), key=lambda kv: kv[1])
    return best if n >= 2 or len(counts) == 1 else None
