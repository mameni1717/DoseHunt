"""Structures de données échangées entre collecteurs, extraction et stockage.

Séparation clé du cahier des charges : un *produit* (ce qu'il contient) est distinct
d'une *offre* (où et à quel prix il est vendu). Côté collecte, une variante Shopify
(format × parfum) devient une offre.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RawVariant:
    """Une variante telle que vue sur le site (un format et/ou un parfum)."""
    variant_id: str
    title: str                      # « Vanille / 1.00 kg », « 1 boîte », « Default Title »
    price: float                    # prix catalogue TTC, devise du site
    compare_at_price: Optional[float] = None   # prix barré, None si absent ou incohérent
    available: bool = True
    sku: Optional[str] = None
    options: dict[str, str] = field(default_factory=dict)   # {"Saveur": "Vanille", "Format": "1.00 kg"}
    shipping_grams: Optional[int] = None   # poids d'expédition Shopify : indice seulement, jamais une teneur
    url: Optional[str] = None


@dataclass
class RawProduct:
    """Un produit tel que relevé, avant classement et extraction."""
    site_id: str
    external_id: str
    handle: str
    title: str
    url: str
    vendor: Optional[str] = None            # marque
    product_type: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    body_html: str = ""                     # description, souvent avec le tableau nutritionnel
    variants: list[RawVariant] = field(default_factory=list)
    option_names: list[str] = field(default_factory=list)
    updated_at: Optional[str] = None
    collected_at: datetime = field(default_factory=now_utc)
    source: str = "shopify_json"            # shopify_json | jsonld | feed | api
    origin_text: str = ""                   # méta-description et zone d'achat de la page : « Fabriqué en France »


@dataclass
class Format:
    """Contenu d'un contenant, déduit du libellé de variante ou du titre."""
    grams: Optional[float] = None           # poids net total (poudres, barres)
    units: Optional[int] = None             # gélules, comprimés, capsules, barres, gouttes, sticks
    unit_word: Optional[str] = None         # gélule | comprimé | capsule | barre | goutte | stick | gummy
    unit_grams: Optional[float] = None      # poids d'une barre ou d'un stick
    pack_count: int = 1                     # « 2 boîtes », « (3 produits) »
    months: Optional[float] = None          # « 3 mois », « 15 jours » : à convertir avec la dose journalière
    millilitres: Optional[float] = None
    confidence: float = 1.0
    raw: str = ""

    @property
    def total_grams(self) -> Optional[float]:
        if self.grams is not None:
            return self.grams * self.pack_count
        if self.units and self.unit_grams:
            return self.units * self.unit_grams * self.pack_count
        return None

    @property
    def total_units(self) -> Optional[int]:
        return self.units * self.pack_count if self.units else None


@dataclass
class ActiveContent:
    """Teneur en actif d'un produit pour une catégorie donnée."""
    category: str
    active: str                 # protein | collagen | creatine | zinc | magnesium | vitamin_d | epa_dha
    amount: float
    unit: str                   # g | mg | UI
    basis: str                  # per_100g | per_unit
    source: str                 # regex_table | regex_text | llm | manual | assumed
    confidence: float
    evidence: str = ""          # extrait de texte qui justifie la valeur
    units_per_dose: Optional[float] = None
    salt_label_mg: Optional[float] = None   # « 120 mg » affichés mais poids du sel
    form: Optional[str] = None              # bisglycinate, citrate, gluconate…
    note: Optional[str] = None


@dataclass
class ReviewItem:
    site_id: str
    external_id: str
    reason: str                 # out_of_range | no_extraction | format_unknown | price_jump | language
    detail: str
    payload: dict = field(default_factory=dict)
