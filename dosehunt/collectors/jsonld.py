"""Compatibilité : les outils JSON-LD vivent désormais dans page.py."""
from .page import (PageCollector, ShopifyHeadlessCollector, SitemapJsonLdCollector, extract_jsonld,  # noqa: F401
                   main_product_node, product_from_jsonld, variants_from_jsonld)
