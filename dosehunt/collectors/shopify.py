"""Collecteur Shopify : tout le catalogue via /products.json, 250 produits par page.

Une page = une requête. Raptor (44 produits) tient en 1 requête, Fitness Boutique (2 075) en 9.
"""
from __future__ import annotations

import logging
from typing import Iterator

from ..models import RawProduct, RawVariant
from .base import Collector, to_price

log = logging.getLogger(__name__)

MAX_PAGES = 100


def parse_product(site, p: dict) -> RawProduct:
    option_names = [o.get("name", "") for o in p.get("options") or []]
    variants = []
    for v in p.get("variants") or []:
        price = to_price(v.get("price"))
        if price is None:
            continue
        compare = to_price(v.get("compare_at_price"))
        if compare is not None and compare <= price:
            compare = None        # 0.00, égal ou inférieur au prix : pas un vrai prix barré
        opts = {}
        for i, name in enumerate(option_names, start=1):
            val = v.get(f"option{i}")
            if val and val != "Default Title":
                opts[name] = val
        variants.append(RawVariant(
            variant_id=str(v.get("id")),
            title=v.get("title") or "",
            price=price,
            compare_at_price=compare,
            available=bool(v.get("available", True)),
            sku=v.get("sku") or None,
            options=opts,
            shipping_grams=v.get("grams") or None,
            url=f"{site.product_url(p['handle'])}?variant={v.get('id')}",
        ))
    tags = p.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return RawProduct(
        site_id=site.id,
        external_id=str(p["id"]),
        handle=p["handle"],
        title=(p.get("title") or "").strip(),
        url=site.product_url(p["handle"]),
        vendor=p.get("vendor") or None,
        product_type=p.get("product_type") or None,
        tags=tags,
        body_html=p.get("body_html") or "",
        variants=variants,
        option_names=option_names,
        updated_at=p.get("updated_at"),
        source="shopify_json",
        image_url=((p.get("images") or [{}])[0] or {}).get("src") or (p.get("image") or {}).get("src"),
    )


class ShopifyCollector(Collector):
    platform = "shopify"

    def iter_products(self) -> Iterator[RawProduct]:
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            url = f"{self.site.root}/products.json?limit={self.site.page_size}&page={page}"
            data = self.client.get_json(url)
            products = (data or {}).get("products") or []
            log.info("%s page %d : %d produits", self.site.id, page, len(products))
            for p in products:
                pid = str(p.get("id"))
                if pid in seen:      # certaines boutiques renvoient la dernière page en boucle
                    continue
                seen.add(pid)
                yield parse_product(self.site, p)
            if len(products) < self.site.page_size:
                return
        log.warning("%s : arrêt après %d pages", self.site.id, MAX_PAGES)
