"""Import d'un flux produits d'affiliation (CSV ou XML, gzip accepté).

Source la plus stable selon le cahier des charges, et la seule possible pour The Protein Works,
protégé par un défi Cloudflare même pour un vrai navigateur.

Réglages (sites.yaml, rubrique filters) :
  feed_url   URL du flux ; ou feed_env : nom de la variable d'environnement qui la contient
             (les URL de flux Awin/Effiliation contiennent une clé personnelle : ne pas la versionner)
  feed_map   correspondance des colonnes si elles diffèrent des noms Awin/Google Shopping habituels
"""
from __future__ import annotations

import csv
import gzip
import io
import logging
import os
import re
from typing import Iterator, Optional
from xml.etree import ElementTree as ET

from ..models import RawProduct, RawVariant
from .base import Collector, to_price

log = logging.getLogger(__name__)

DEFAULT_MAP = {
    "id": ["aw_product_id", "merchant_product_id", "product_id", "id", "g:id", "sku"],
    "parent": ["parent_product_id", "item_group_id", "g:item_group_id"],
    "title": ["product_name", "title", "name", "g:title"],
    "url": ["aw_deep_link", "merchant_deep_link", "deeplink", "link", "url", "g:link"],
    "price": ["search_price", "display_price", "sale_price", "price", "g:sale_price", "g:price", "store_price"],
    "compare": ["rrp_price", "product_price_old", "was_price", "base_price", "g:price"],
    "brand": ["brand_name", "brand", "g:brand", "manufacturer"],
    "description": ["description", "product_short_description", "g:description", "specifications"],
    "type": ["merchant_category", "category_name", "product_type", "g:product_type", "category"],
    "available": ["in_stock", "availability", "stock_status", "g:availability"],
    "size": ["size", "g:size", "custom_1", "product_weight"],
    "flavour": ["colour", "flavour", "flavor", "g:color", "custom_2"],
}


def _pick(row: dict, keys: list[str]) -> Optional[str]:
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return None


def _price(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", text.replace(" ", ""))
    return to_price(m.group(0).replace(",", ".")) if m else None


def parse_feed(content: bytes) -> list[dict]:
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    head = content[:500].lstrip()
    if head.startswith(b"<"):
        root = ET.fromstring(content)
        rows = []
        for item in root.iter():
            if item.tag.split("}")[-1] in ("item", "product", "entry", "prod"):
                row = {}
                for child in item:
                    tag = child.tag
                    if tag.startswith("{"):
                        tag = "g:" + tag.split("}")[1] if "base.google.com" in tag else tag.split("}")[1]
                    row[tag] = (child.text or "").strip()
                if row:
                    rows.append(row)
        return rows
    text = content.decode("utf-8-sig", errors="replace")
    dialect = csv.Sniffer().sniff(text[:5000], delimiters=",;|\t")
    return list(csv.DictReader(io.StringIO(text), dialect=dialect))


class AffiliateFeedCollector(Collector):
    platform = "affiliate_feed"

    def feed_url(self) -> Optional[str]:
        f = self.site.filters or {}
        return f.get("feed_url") or (os.environ.get(f["feed_env"]) if f.get("feed_env") else None)

    def iter_products(self) -> Iterator[RawProduct]:
        url = self.feed_url()
        if not url:
            env = (self.site.filters or {}).get("feed_env", "DOSEHUNT_FEED_" + self.site.id.upper())
            raise NotImplementedError(
                f"Flux d'affiliation de {self.site.name} non configuré : inscris-toi au programme du marchand "
                f"puis renseigne l'URL du flux dans la variable {env}.")
        resp = self.client.get(url)
        mapping = {**DEFAULT_MAP, **((self.site.filters or {}).get("feed_map") or {})}
        rows = parse_feed(resp.content)
        log.info("%s : %d lignes dans le flux", self.site.id, len(rows))
        products: dict[str, RawProduct] = {}
        for row in rows:
            pid, title, link = _pick(row, mapping["id"]), _pick(row, mapping["title"]), _pick(row, mapping["url"])
            price = _price(_pick(row, mapping["price"]))
            if not (pid and title and link and price):
                continue
            compare = _price(_pick(row, mapping["compare"]))
            avail = (_pick(row, mapping["available"]) or "1").lower()
            group = _pick(row, mapping["parent"]) or pid
            size, flavour = _pick(row, mapping["size"]), _pick(row, mapping["flavour"])
            opts = {k: v for k, v in (("Format", size), ("Saveur", flavour)) if v}
            variant = RawVariant(
                variant_id=pid, title=" / ".join(opts.values()) or title, price=price,
                compare_at_price=compare if compare and compare > price else None,
                available=avail not in ("0", "false", "no", "out of stock", "out_of_stock", "rupture"),
                options=opts, url=link,
            )
            p = products.get(group)
            if p is None:
                p = products[group] = RawProduct(
                    site_id=self.site.id, external_id=group, handle=group, title=title, url=link,
                    vendor=_pick(row, mapping["brand"]), product_type=_pick(row, mapping["type"]),
                    body_html=_pick(row, mapping["description"]) or "", option_names=list(opts), source="feed")
            if not opts and p.variants:          # une ligne par variante sans attributs : le titre porte le format
                variant.title = title
            p.variants.append(variant)
        yield from products.values()
