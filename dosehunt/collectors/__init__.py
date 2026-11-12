"""Registre des collecteurs : le champ `collector` de sites.yaml choisit la classe."""
from __future__ import annotations

from typing import Optional

from ..config import Site
from ..http import PoliteClient
from .base import Collector, NotYetImplemented
from .feed import AffiliateFeedCollector
from .page import PageCollector, ShopifyHeadlessCollector
from .prestashop import PrestaShopCollector
from .shopify import ShopifyCollector

REGISTRY: dict[str, type[Collector]] = {
    "shopify": ShopifyCollector,
    "shopify_headless": ShopifyHeadlessCollector,
    "prestashop": PrestaShopCollector,
    "magento": PageCollector,          # sitemap + fiche ; la config Magento (jsonConfig) est lue sur la fiche
    "page": PageCollector,
    "jsonld": PageCollector,
    "affiliate_feed": AffiliateFeedCollector,
}


def collector_for(site: Site, client: Optional[PoliteClient] = None) -> Collector:
    cls = REGISTRY.get(site.collector, NotYetImplemented)
    return cls(site, client)


__all__ = ["Collector", "collector_for", "REGISTRY"]
