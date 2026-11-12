"""Collecteur PrestaShop 1.7+ (Fitadium, Nutri&Co, Nutripure, STC).

1. Découverte : listings JSON des catégories (en-tête X-Requested-With → PrestaShop renvoie
   {"products": [...], "pagination": {...}}) et, si configuré, sitemap des fiches.
2. Pré-filtre : on n'ouvre que les fiches dont le nom ou la catégorie relève de nos 8 catégories
   (Fitadium : 1 702 produits, dont une minorité nous concerne).
3. Fiche : JSON-LD (marque, description), zone produit avec ses onglets (composition, tableau
   nutritionnel), groupes de déclinaisons.
4. Déclinaisons : action « refresh » de la fiche pour chaque combinaison → prix, prix barré, URL.
"""
from __future__ import annotations

import html as htmllib
import itertools
import json
import logging
import re
from html.parser import HTMLParser
from typing import Iterator, Optional
from urllib.parse import urlencode, urljoin
from xml.etree import ElementTree as ET

from ..http import BlockedByRobots, FetchError
from ..models import RawProduct, RawVariant
from .base import Collector, format_hint, to_price
from .jsonld import extract_jsonld

log = logging.getLogger(__name__)

XHR = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}
MAX_COMBINATIONS = 40
MAX_CATEGORY_PAGES = 120
_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

CAPTURE_IDS = {"description", "compo", "composition", "product-details", "nutrition", "tab-description"}
CAPTURE_CLASSES = ("tab-pane", "product-description", "product-information", "product-composition",
                   "product-nutrition", "rte")
SKIP_CLASSES = ("product-accessories", "crossselling", "featured-products", "viewed-products",
                "related", "product-miniature", "reassurance", "blockreassurance")
VOID = {"br", "img", "input", "meta", "link", "hr", "source", "wbr", "col", "area"}


class _ProductZone(HTMLParser):
    """Récupère le HTML des zones produit (description, onglets), sans les blocs « produits liés »."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str]] = []     # (tag, rôle) avec rôle = capture | skip | ""
        self.parts: list[str] = []
        self.capturing = 0
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        role = ""
        if any(c in cls for c in SKIP_CLASSES):
            role = "skip"
        elif a.get("id") in CAPTURE_IDS or any(re.search(rf"(^|\s){c}(\s|$)", cls) for c in CAPTURE_CLASSES):
            role = "capture"
        if tag in VOID:
            if self.capturing and not self.skipping:
                self.parts.append("<br>" if tag == "br" else "")
            return
        self.stack.append((tag, role))
        if role == "skip":
            self.skipping += 1
        elif role == "capture":
            self.capturing += 1
        if self.capturing and not self.skipping and tag in ("p", "div", "li", "tr", "td", "th", "table", "h2", "h3", "h4", "ul"):
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        while self.stack:
            t, role = self.stack.pop()
            if self.capturing and not self.skipping and t in ("p", "div", "li", "tr", "td", "th", "table", "h2", "h3", "h4", "ul"):
                self.parts.append(f"</{t}>")
            if role == "skip":
                self.skipping -= 1
            elif role == "capture":
                self.capturing -= 1
                self.parts.append("\n")
            if t == tag:
                break

    def handle_data(self, data):
        if self.capturing and not self.skipping:
            self.parts.append(htmllib.escape(data))


def product_zone_html(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page)
    parser = _ProductZone()
    try:
        parser.feed(page)
    except Exception:        # HTML trop cassé : on se contentera du JSON-LD
        return ""
    return "".join(parser.parts)


def _attrs(tag_html: str) -> dict[str, str]:
    return {k.lower(): htmllib.unescape(v) for k, v in re.findall(r'([\w:-]+)\s*=\s*"([^"]*)"', tag_html)}


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def variant_groups(page: str) -> dict[str, list[tuple[str, str]]]:
    """{"group[4]": [("220", "90 gélules (3 mois)"), ("221", "3x90 gélules (9 mois)")]}"""
    groups: dict[str, list[tuple[str, str]]] = {}
    for m in re.finditer(r'<select[^>]*name="(group\[\d+\])"[^>]*>(.*?)</select>', page, re.S | re.I):
        opts = re.findall(r'<option[^>]*value="(\d+)"[^>]*>(.*?)</option>', m.group(2), re.S | re.I)
        groups[m.group(1)] = [(v, _strip(t)) for v, t in opts]
    for m in re.finditer(r"<input\b[^>]*>", page, re.I):
        a = _attrs(m.group(0))
        name = a.get("name", "")
        if not re.fullmatch(r"group\[\d+\]", name) or a.get("type", "radio") not in ("radio", "checkbox", "hidden"):
            continue
        label = a.get("title") or a.get("aria-label") or ""
        if not label:
            tail = re.match(r"(.*?)</(?:label|li)>", page[m.end():m.end() + 600], re.S | re.I)
            label = _strip(tail.group(1)) if tail else ""
        lst = groups.setdefault(name, [])
        if a.get("value") and all(v != a["value"] for v, _ in lst):
            lst.append((a["value"], label))
    return {k: v for k, v in groups.items() if v}


def _group_label(page: str, group: str) -> str:
    gid = re.search(r"\d+", group).group(0)
    m = re.search(rf'<label[^>]*for="group_{gid}"[^>]*>(.*?)</label>', page, re.S | re.I) \
        or re.search(rf'data-product-attribute="{gid}".{{0,400}}?<span[^>]*class="[^"]*control-label[^"]*"[^>]*>(.*?)</span>',
                     page, re.S | re.I)
    return _strip(m.group(1)).rstrip(" :") if m else f"Option {gid}"


def parse_refresh(data: dict) -> tuple[Optional[float], Optional[float], Optional[str], bool]:
    prices = data.get("product_prices") or ""
    m = re.search(r'content="(\d+(?:\.\d+)?)"', prices) or re.search(r'class="[^"]*current-price[^"]*"[^>]*>\s*([\d\s.,]+)', prices)
    price = to_price(m.group(1).replace(" ", "").replace(",", ".")) if m else None
    r = re.search(r'regular-price[^>]*>\s*([\d\s.,]+)', prices)
    regular = to_price(r.group(1).replace(" ", "").replace("\xa0", "").replace(",", ".")) if r else None
    if regular is not None and price is not None and regular <= price:
        regular = None
    add = data.get("product_add_to_cart") or ""
    available = not re.search(r'add-to-cart[^>]*disabled|product-unavailable|Rupture|Épuisé', add, re.I)
    return price, regular, data.get("product_url"), available


class PrestaShopCollector(Collector):
    platform = "prestashop"

    # -- découverte -------------------------------------------------------
    def listing_urls(self) -> list[str]:
        configured = (self.site.filters or {}).get("listing_urls")
        if configured:
            return [urljoin(self.site.base_url, u) for u in configured]
        resp = self.client.get(self.site.root + "/")
        links = re.findall(r'href="(' + re.escape(self.site.base_url.rstrip("/")) + r'[^"#?]*?/\d+-[a-z0-9-]+/?)"', resp.text, re.I)
        # Seules les catégories qui peuvent contenir nos 8 familles de produits (le reste : vêtements, matériel…)
        kw = re.compile((self.site.filters or {}).get("category_keywords",
                        r"prot|whey|isolat|cr[eé]atine|vitamin|min[eé]ra|om[eé]ga|barre|snack|collag|zinc|magn|sant|"
                        r"bien-etre|complement|nutrition|sport|musculation|vegan"), re.I)
        links = [l for l in dict.fromkeys(links) if kw.search(l.rsplit("/", 1)[-1])]
        return links[:60]

    def discover(self) -> dict[str, dict]:
        """{url_de_fiche: {id, name, category, brand, price, regular}}"""
        found: dict[str, dict] = {}
        for cat in self.listing_urls():
            for page in range(1, MAX_CATEGORY_PAGES + 1):
                sep = "&" if "?" in cat else "?"
                url = f"{cat}{sep}resultsPerPage=500&page={page}"
                if not self.client.allowed(url):
                    url = f"{cat}{sep}page={page}"          # Fitadium : seul « ?page= » est autorisé
                try:
                    resp = self.client.get(url, headers=XHR, accept_404=True)
                except FetchError as exc:
                    log.warning("%s : listing ignoré %s (%s)", self.site.id, cat, exc)
                    break
                if resp is None or "json" not in resp.headers.get("content-type", ""):
                    break
                data = resp.json()
                for p in data.get("products") or []:
                    link = (p.get("canonical_url") or p.get("url") or "").split("#")[0]
                    if link and link not in found:
                        found[link] = {"id": str(p.get("id_product")), "name": p.get("name") or "",
                                       "description_short": p.get("description_short") or "",
                                       "category": p.get("category_name") or "", "brand": p.get("manufacturer_name"),
                                       "price": to_price(p.get("price_amount")),
                                       "regular": to_price(p.get("regular_price_amount"))}
                pag = data.get("pagination") or {}
                if page >= int(pag.get("pages_count") or 1):
                    break
        pattern = (self.site.filters or {}).get("sitemap_product_pattern")
        if pattern:
            for link in self._sitemap_links(re.compile(pattern)):
                found.setdefault(link, {"id": None, "name": "", "category": "", "brand": None, "price": None, "regular": None})
        return found

    def _sitemap_links(self, pattern: re.Pattern) -> list[str]:
        out, queue, seen = [], [self.site.base_url.rstrip("/") + "/sitemap.xml"], set()
        while queue:
            sm = queue.pop(0)
            if sm in seen:
                continue
            seen.add(sm)
            resp = self.client.get(sm, accept_404=True)
            if resp is None:
                continue
            root = ET.fromstring(resp.content)
            locs = [(l.text or "").strip() for l in root.iter(f"{_NS}loc")]
            if root.tag == f"{_NS}sitemapindex":
                queue += [l for l in locs if "product" in l or "produit" in l]
            else:
                out += [l for l in locs if pattern.search(l)]
        return list(dict.fromkeys(out))

    def _in_scope(self, meta: dict) -> bool:
        from ..classify import classify          # import tardif : classify importe aussi collectors
        if not meta["name"]:
            return True                  # vu seulement dans le sitemap : on ouvre la fiche pour savoir
        probe = RawProduct(site_id=self.site.id, external_id="", handle="", title=meta["name"], url="",
                           product_type=meta["category"])
        return bool(classify(probe))

    # -- fiche ------------------------------------------------------------
    def fetch_product(self, url: str, meta: dict) -> Optional[RawProduct]:
        resp = self.client.get(url, accept_404=True)
        if resp is None:
            return None
        page = resp.text
        nodes = extract_jsonld(page)
        node = next((n for n in nodes if "Product" in str(n.get("@type"))), {})
        brand = node.get("brand")
        brand = brand.get("name") if isinstance(brand, dict) else brand
        idp = meta.get("id") or (re.search(r'name="id_product"\s+value="(\d+)"', page) or
                                 re.search(r'value="(\d+)"\s+name="id_product"', page) or
                                 re.search(r'"id_product"\s*:\s*"?(\d+)', page) or [None, None])[1]
        if not idp:
            return None
        title = (node.get("name") or meta.get("name") or "").strip()
        body = product_zone_html(page) or (node.get("description") or "")
        from .page import with_nutrition_tables         # import tardif (page importe base comme nous)
        from ..origin import origin_text_from_page
        body = with_nutrition_tables(body, page)
        hint = format_hint(page)
        if hint:
            body += f"\n<p>Contenance : {hint}</p>"
        groups = variant_groups(page)
        variants = self._variants(url, idp, page, groups, node, meta)
        return RawProduct(
            site_id=self.site.id, external_id=str(idp), handle=url.rstrip("/").rsplit("/", 1)[-1],
            title=title, url=url, vendor=brand or meta.get("brand"),
            product_type=meta.get("category") or node.get("category"), body_html=body,
            variants=variants, option_names=[_group_label(page, g) for g in groups], source="prestashop",
            origin_text=origin_text_from_page(page),
        )

    refresh_blocked = False

    def _variants(self, url, idp, page, groups, node, meta) -> list[RawVariant]:
        if groups and not self.refresh_blocked:
            endpoint = f"{self.site.root}/index.php?controller=product&action=refresh"
            if not self.client.allowed(endpoint):
                # Fitadium : « Disallow: *?controller* ». On s'en tient au prix de la déclinaison par défaut.
                self.refresh_blocked = True
                log.warning("%s : robots.txt interdit la lecture des déclinaisons ; prix de la déclinaison "
                            "par défaut seulement", self.site.id)
        if not groups or self.refresh_blocked:
            offers = node.get("offers") or {}
            offers = offers[0] if isinstance(offers, list) and offers else offers
            price = to_price(offers.get("price") if isinstance(offers, dict) else None) or meta.get("price")
            if price is None:
                return []
            regular = meta.get("regular")
            return [RawVariant(variant_id=f"{idp}-0", title="Default Title", price=price,
                               compare_at_price=regular if regular and regular > price else None,
                               available="OutOfStock" not in str(offers.get("availability", "")) if isinstance(offers, dict) else True,
                               url=url)]
        names = {g: _group_label(page, g) for g in groups}
        combos = list(itertools.product(*[[(g, v, lbl) for v, lbl in vals] for g, vals in groups.items()]))[:MAX_COMBINATIONS]
        out = []
        endpoint = f"{self.site.root}/index.php"
        for combo in combos:
            params = {"controller": "product", "id_product": idp, "ajax": 1, "action": "refresh", "quantity_wanted": 1}
            params.update({g: v for g, v, _ in combo})
            try:
                resp = self.client.post(f"{endpoint}?{urlencode(params)}", headers=XHR)
                data = resp.json() if resp is not None else {}
            except BlockedByRobots:
                self.refresh_blocked = True
                return self._variants(url, idp, page, {}, node, meta)
            except (FetchError, json.JSONDecodeError, ValueError) as exc:
                log.warning("%s : déclinaison illisible %s %s (%s)", self.site.id, url, params, exc)
                continue
            price, regular, vurl, available = parse_refresh(data)
            if price is None:
                continue
            ipa = data.get("id_product_attribute") or "-".join(v for _, v, _ in combo)
            out.append(RawVariant(
                variant_id=f"{idp}-{ipa}", title=" / ".join(lbl for _, _, lbl in combo), price=price,
                compare_at_price=regular, available=available,
                options={names[g]: lbl for g, _, lbl in combo}, url=vurl or url,
            ))
        return out

    def iter_products(self) -> Iterator[RawProduct]:
        catalogue = self.discover()
        scoped = {u: m for u, m in catalogue.items() if self._in_scope(m)}
        log.info("%s : %d fiches trouvées, %d dans nos catégories", self.site.id, len(catalogue), len(scoped))
        self.catalogue_size = len(catalogue)
        refused = 0
        for url, meta in scoped.items():
            if refused >= 3:                      # le site refuse ses fiches à notre robot : listing seul
                product = self.listing_product(url, meta)
                if product:
                    yield product
                continue
            try:
                product = self.fetch_product(url, meta)
            except (FetchError, BlockedByRobots) as exc:
                if isinstance(exc, FetchError) and exc.status == 403:
                    refused += 1
                    if refused == 3:
                        log.warning("%s : fiches refusées (403) à notre robot, passage au listing seul "
                                    "(teneurs depuis config/manual_actives.yaml)", self.site.id)
                    product = self.listing_product(url, meta)
                    if product:
                        yield product
                    continue
                log.warning("%s : fiche ignorée %s (%s)", self.site.id, url, exc)
                continue
            if product and product.variants:
                yield product

    def listing_product(self, url: str, meta: dict) -> Optional[RawProduct]:
        """Produit construit depuis le listing JSON (autorisé), quand la fiche est refusée. Sans teneur saisie à la
        main, il restera hors index (revue « aucune teneur trouvée »)."""
        from ..config import manual_for
        if not meta.get("id") or not meta.get("price"):
            return None
        manual = manual_for(self.site.id, meta["id"], meta["name"])
        fmt = manual[0].get("format") if manual else None
        regular = meta.get("regular")
        variant = RawVariant(variant_id=f"{meta['id']}-listing", title=fmt or "Default Title", price=meta["price"],
                             compare_at_price=regular if regular and regular > meta["price"] + 0.009 else None,
                             options={"Format": fmt} if fmt else {}, url=url)
        return RawProduct(site_id=self.site.id, external_id=str(meta["id"]), handle=url.rstrip("/").rsplit("/", 1)[-1],
                          title=meta["name"], url=url, vendor=meta.get("brand"), product_type=meta.get("category"),
                          body_html=meta.get("description_short") or "", variants=[variant], source="prestashop_listing")
