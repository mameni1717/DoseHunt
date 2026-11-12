"""Détection de la plateforme d'un site (Shopify, headless, PrestaShop, Magento, WooCommerce)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .http import FetchError, PoliteClient


@dataclass
class Detection:
    url: str
    platform: str
    evidence: list[str]
    suggested_collector: str


SIGNS = [
    ("shopify", re.compile(r"cdn\.shopify\.com|Shopify\.theme|window\.Shopify", re.I)),
    ("prestashop", re.compile(r"var prestashop\s*=|prestashop\.(min\.)?js|PrestaShop", re.I)),
    ("magento", re.compile(r"Magento_|requirejs-config\.js|mage/cookies|x-magento", re.I)),
    ("woocommerce", re.compile(r"woocommerce", re.I)),
]


def detect(base_url: str, client: PoliteClient | None = None) -> Detection:
    own = client is None
    client = client or PoliteClient(delay_seconds=1.0)
    evidence: list[str] = []
    try:
        home = client.get(base_url)
        page = home.text if home is not None else ""
        hits = {name for name, rx in SIGNS if rx.search(page[:400_000])}
        evidence += [f"signature {h} dans la page d'accueil" for h in sorted(hits)]
        pj = client.get_json(base_url.rstrip("/") + "/products.json?limit=1", accept_404=True)
        if pj and "products" in pj:
            return Detection(base_url, "shopify", evidence + ["products.json répond"], "shopify")
        if "shopify" in hits:
            return Detection(base_url, "shopify (headless)", evidence + ["products.json absent"], "shopify_headless")
        for name in ("prestashop", "magento", "woocommerce"):
            if name in hits:
                return Detection(base_url, name, evidence, name if name != "woocommerce" else "jsonld")
        return Detection(base_url, "inconnue", evidence, "custom")
    except FetchError as exc:
        return Detection(base_url, "injoignable", [str(exc)], "custom")
    finally:
        if own:
            client.close()
