"""Collecteur « fiches produits » commun aux sites sans catalogue JSON.

Réglé site par site dans sites.yaml (rubrique `filters`) :

  Découverte
    sitemaps               liste de sitemaps (absolus ou relatifs) ; .gz accepté
    sitemap_child_filter   regex des sous-sitemaps à suivre (défaut : product|produit)
    product_pattern        regex des URL de fiches
    start_urls             parcours de pages (si pas de sitemap)
    category_pattern       regex des pages à parcourir pour trouver des fiches
    prefilter_url          n'ouvrir que les fiches dont l'URL évoque nos 8 catégories
  Lecture
    variants_from          jsonld (défaut) | html_list (liste des tailles en HTML, Optigura)
    sku_format             regex à groupes `flavour` et `size` pour lire le format dans la référence (Bulk)
    hook                   traitement propre à un site (prozis : tableau nutritionnel par API)

Sources de prix, de la plus fiable à la moins fiable : configuration Magento (jsonConfig),
JSON-LD avec une offre par déclinaison, liste HTML des tailles. Une simple fourchette de prix
(AggregateOffer sans détail) n'est jamais utilisée comme prix.
"""
from __future__ import annotations

import gzip
import html as htmllib
import json
import logging
import re
from html.parser import HTMLParser
from typing import Iterator, Optional
from urllib.parse import quote, urljoin, urlsplit
from xml.etree import ElementTree as ET

from ..http import BlockedByRobots, FetchError
from ..models import RawProduct, RawVariant
from .base import Collector, format_hint, to_price

log = logging.getLogger(__name__)

_LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
XHR = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}


# --------------------------------------------------------------------------- JSON-LD

def extract_jsonld(html_text: str) -> list[dict]:
    out = []
    for block in _LD.findall(html_text):
        block = re.sub(r"/\*\s*<!\[CDATA\[\s*\*/|/\*\s*\]\]>\s*\*/|<!\[CDATA\[|\]\]>", "", block).strip()
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            try:
                data = json.loads(re.sub(r"[\x00-\x1f]", " ", block))     # retours à la ligne bruts dans une chaîne
            except json.JSONDecodeError:
                continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for i in items:
            if isinstance(i, dict):
                out.extend(i.get("@graph", [i]) if "@graph" in i else [i])
    return out


def _types(node: dict) -> set[str]:
    t = node.get("@type")
    return set(t) if isinstance(t, list) else {t} if t else set()


def _offers(node: dict) -> list[dict]:
    offers = node.get("offers") or []
    if isinstance(offers, dict):
        offers = offers["offers"] if "offers" in offers else [offers]
    return [o for o in offers if isinstance(o, dict) and "AggregateOffer" not in _types(o)]


def _compare_price(off: dict, price: float) -> Optional[float]:
    specs = off.get("priceSpecification") or []
    specs = specs if isinstance(specs, list) else [specs]
    for s in specs:
        if isinstance(s, dict) and re.search(r"ListPrice|StrikethroughPrice", str(s.get("priceType", ""))):
            p = to_price(s.get("price"))
            if p and p > price:
                return p
    return None


def main_product_node(nodes: list[dict]) -> Optional[dict]:
    group = next((n for n in nodes if "ProductGroup" in _types(n)), None)
    if group:
        return group
    products = [n for n in nodes if _types(n) & {"Product", "DietarySupplement"} and (n.get("offers") or n.get("name"))]
    return next((p for p in products if _offers(p)), products[0] if products else None)


def variants_from_jsonld(node: dict, nodes: list[dict], url: str, sku_format: Optional[str] = None) -> list[RawVariant]:
    children = node.get("hasVariant") or []
    if not children and "ProductGroup" in _types(node):
        gid = node.get("productGroupID")
        children = [n for n in nodes if "Product" in _types(n) and n is not node
                    and (not gid or str(n.get("inProductGroupWithID", gid)) == str(gid))]
    if not children:
        children = [node]
    rx = re.compile(sku_format) if sku_format else None
    out: list[RawVariant] = []
    for child in children:
        child_name = child.get("name") if child is not node else None
        size = child.get("size") if isinstance(child.get("size"), str) else None
        weight = child.get("weight") or {}
        for i, off in enumerate(_offers(child)):
            price = to_price(off.get("price"))
            if price is None:
                continue
            sku = off.get("sku") or child.get("sku")
            parts = [child_name, size, off.get("name")]
            opts: dict[str, str] = {}
            if rx and sku and (m := rx.search(sku)):
                gd = m.groupdict()
                if gd.get("size"):
                    parts.append(str(int(gd["size"])) if gd["size"].isdigit() else gd["size"])
                    opts["Format"] = parts[-1]
                if gd.get("flavour"):
                    opts["Saveur"] = gd["flavour"]
            if size:
                opts.setdefault("Format", size)
            if off.get("name"):
                opts.setdefault("Format", off["name"])
            title = " / ".join(dict.fromkeys(p for p in parts if p)) or "Default Title"
            out.append(RawVariant(
                variant_id=str(sku or f"{urlsplit(url).path}-{len(out)}"),
                title=title, price=price, compare_at_price=_compare_price(off, price),
                available="OutOfStock" not in str(off.get("availability", "")) and "SoldOut" not in str(off.get("availability", "")),
                sku=sku, options=opts,
                shipping_grams=int(float(weight["value"]) * (1000 if weight.get("unitCode") in ("KGM", "kg") else 1))
                if isinstance(weight, dict) and weight.get("value") else None,
                url=off.get("url") or url,
            ))
    return out


def product_from_jsonld(site, url: str, nodes: list[dict]) -> Optional[RawProduct]:
    """Conservé pour les boutiques Shopify headless (Greenwhey)."""
    node = main_product_node(nodes)
    if node is None:
        return None
    brand = node.get("brand")
    brand = brand.get("name") if isinstance(brand, dict) else brand
    handle = url.rstrip("/").rsplit("/", 1)[-1]
    variants = variants_from_jsonld(node, nodes, url)
    for v in variants:            # Greenwhey : variante = parfum, offre = format
        if v.title.count(" / ") == 1:
            flav, fmt = v.title.split(" / ")
            v.options = {"Saveur": flav, "Format": fmt}
            v.variant_id = f"{v.sku or handle}-{fmt}"
    pid = str(node.get("productID") or node.get("productGroupID") or node.get("sku") or handle).rsplit("/", 1)[-1]
    return RawProduct(site_id=site.id, external_id=pid, handle=handle, title=(node.get("name") or "").strip(),
                      url=url, vendor=(brand or "").strip() or None, product_type=node.get("category"),
                      body_html=node.get("description") or "", variants=variants,
                      option_names=["Saveur", "Format"], source="jsonld",
                      image_url=(node.get("image")[0] if isinstance(node.get("image"), list) and node.get("image")
                                 else node.get("image") if isinstance(node.get("image"), str) else None))


# --------------------------------------------------------------------------- Magento

def _balanced_json(text: str, start: int) -> Optional[str]:
    depth, in_str, esc = 0, False, False
    for j in range(start, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    return None


def magento_config(page: str) -> Optional[dict]:
    """jsonConfig des produits configurables (Luma : "jsonConfig": {...} ; Hyvä : initConfigurableOptions('id', {...}))."""
    for marker in ('"jsonConfig":', "initConfigurableOptions("):
        pos = page.find(marker)
        while pos >= 0:
            brace = page.find("{", pos)
            raw = _balanced_json(page, brace) if brace >= 0 else None
            if raw:
                try:
                    cfg = json.loads(raw)
                    if cfg.get("attributes") and (cfg.get("index") or cfg.get("optionPrices")):
                        return cfg
                except json.JSONDecodeError:
                    pass
            pos = page.find(marker, pos + len(marker))
    return None


def variants_from_magento(cfg: dict, url: str) -> list[RawVariant]:
    attrs = cfg.get("attributes") or {}
    labels = {aid: {str(o["id"]): o.get("label", "") for o in a.get("options", [])} for aid, a in attrs.items()}
    names = {aid: a.get("label") or a.get("code") or aid for aid, a in attrs.items()}
    salable = cfg.get("salable") or {}
    sold = {str(p) for opts in salable.values() for pids in (opts.values() if isinstance(opts, dict) else []) for p in pids}
    skus = cfg.get("skus") or {}
    out = []
    for pid, combo in (cfg.get("index") or {}).items():
        prices = (cfg.get("optionPrices") or {}).get(pid) or {}
        price = to_price((prices.get("finalPrice") or {}).get("amount"))
        if price is None:
            continue
        old = to_price((prices.get("oldPrice") or {}).get("amount"))
        price = round(price, 2)
        old = round(old, 2) if old and old > price + 0.009 else None
        opts = {names[aid]: labels.get(aid, {}).get(str(oid), "") for aid, oid in combo.items() if aid in names}
        out.append(RawVariant(
            variant_id=str(pid), title=" / ".join(v for v in opts.values() if v) or "Default Title",
            price=price, compare_at_price=old, available=(not salable) or str(pid) in sold,
            sku=skus.get(pid) if isinstance(skus, dict) else None, options=opts, url=url,
        ))
    return out


# --------------------------------------------------------------------------- liste HTML des tailles (Optigura)

def variants_from_html_list(page: str, url: str) -> list[RawVariant]:
    m = re.search(r'<div class="opt1">(.*?)</ul>', page, re.S)
    if not m:
        return []
    out = []
    for i, li in enumerate(re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S)):
        spans = [re.sub(r"<[^>]+>|<!---->", " ", s) for s in re.findall(r"<span[^>]*>(.*?)</span>", li, re.S)]
        spans = [re.sub(r"\s+", " ", htmllib.unescape(s)).strip() for s in spans]
        label = next((s for s in spans if s and "€" not in s), "")
        price_txt = next((s for s in spans if "€" in s), "")
        pm = re.search(r"(\d+(?:[.,]\d{1,2})?)", price_txt.replace(" ", "").replace(" ", ""))
        price = to_price(pm.group(1).replace(",", ".")) if pm else None
        if label and price:
            out.append(RawVariant(variant_id=f"{urlsplit(url).path}-{label}", title=label, price=price,
                                  options={"Taille": label}, url=url))
    return out


# --------------------------------------------------------------------------- zone produit

ZONE_IDS = re.compile(r"description|product-?info|product-?detail|nutrition|composition|ingredient|tab-?content|"
                      r"specification|caracteristi|accordion|pdp", re.I)
ZONE_SKIP = re.compile(r"related|upsell|cross-?sell|recommend|similar|carousel|slider|product-?card|product-?item|"
                       r"product-?tile|miniature|recently|viewed|footer|header|menu|navbar|breadcrumb|review|avis|"
                       r"newsletter|cookie|modal", re.I)
SKIP_TAGS = {"header", "footer", "nav", "aside", "form", "noscript", "svg", "button"}
BLOCK = {"p", "div", "li", "tr", "td", "th", "table", "h1", "h2", "h3", "h4", "ul", "ol", "section", "dl", "dt", "dd"}
VOID = {"br", "img", "input", "meta", "link", "hr", "source", "wbr", "col", "area", "use", "path"}


class _Zone(HTMLParser):
    def __init__(self, whole_body: bool):
        super().__init__(convert_charrefs=True)
        self.whole = whole_body
        self.stack: list[tuple[str, str]] = []
        self.parts: list[str] = []
        self.cap = 1 if whole_body else 0
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            if tag == "br" and self.cap and not self.skip:
                self.parts.append("<br>")
            return
        a = dict(attrs)
        marker = f"{a.get('id') or ''} {a.get('class') or ''}"
        role = ""
        if tag in SKIP_TAGS or (marker.strip() and ZONE_SKIP.search(marker) and not ZONE_IDS.search(a.get("id") or "")):
            role = "skip"
        elif not self.whole and (tag == "main" or (marker.strip() and ZONE_IDS.search(marker))):
            role = "cap"
        self.stack.append((tag, role))
        if role == "skip":
            self.skip += 1
        elif role == "cap":
            self.cap += 1
        if self.cap and not self.skip and tag in BLOCK:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        while self.stack:
            t, role = self.stack.pop()
            if self.cap and not self.skip and t in BLOCK:
                self.parts.append(f"</{t}>")
            if role == "skip":
                self.skip -= 1
            elif role == "cap":
                self.cap -= 1
            if t == tag:
                break

    def handle_data(self, data):
        if self.cap and not self.skip and data.strip():
            self.parts.append(htmllib.escape(data))


def zone_html(page: str) -> str:
    """HTML de la zone produit (description, onglets, tableau nutritionnel), sans menus ni produits liés."""
    clean = re.sub(r"(?is)<(script|style|template)[^>]*>.*?</\1>|<!--.*?-->", " ", page)
    best = ""
    for whole in (False, True):
        p = _Zone(whole)
        try:
            p.feed(clean)
        except Exception:                                   # HTML très cassé
            continue
        out = "".join(p.parts)
        size = len(re.sub(r"<[^>]+>|\s", "", out))
        if size > 200:
            return out                                      # zone produit trouvée et substantielle
        if size > len(re.sub(r"<[^>]+>|\s", "", best)):
            best = out
    return best


_NUTRI = re.compile(r"prot[ée]ines?|kcal|nutritionnel|zinc|magn[ée]sium|vitamine|epa|dha|cr[ée]atine|collag", re.I)
_SCRIPT = re.compile(r"(?is)<script\b[^>]*>(.*?)</script>")
_TABLE_IN_JS = re.compile(r"<table|\\u003ctable", re.I)
MAX_JS_STRING = 60000


def _unescaped_quote(s: str, i: int) -> bool:
    if s[i] != '"':
        return False
    n, j = 0, i - 1
    while j >= 0 and s[j] == "\\":
        n, j = n + 1, j - 1
    return n % 2 == 0


def _js_strings_with_table(script: str):
    """Chaînes JS contenant « <table », repérées depuis chaque « <table » (et non depuis chaque guillemet :
    l'ancienne expression régulière repartait de chaque guillemet et s'emballait sur les pages de plusieurs Mo)."""
    last_end = -1
    for m in _TABLE_IN_JS.finditer(script):
        if m.start() < last_end:
            continue
        start = m.start() - 1
        floor = max(0, m.start() - MAX_JS_STRING)
        while start >= floor and not _unescaped_quote(script, start):
            start -= 1
        if start < floor:
            continue
        end = m.end()
        ceil = min(len(script), m.end() + MAX_JS_STRING)
        while end < ceil and not _unescaped_quote(script, end):
            end += 1
        if end >= ceil:
            continue
        last_end = end
        yield script[start + 1:end]


def embedded_tables(page: str, limit: int = 4) -> str:
    """Tableaux nutritionnels injectés par script (chaîne JSON contenant du HTML, thèmes Magento Hyvä/EAFIT)."""
    out = []
    raws = (raw for sm in _SCRIPT.finditer(page) if _TABLE_IN_JS.search(sm.group(1))
            for raw in _js_strings_with_table(sm.group(1)))
    for raw in raws:
        if "\\" not in raw:
            continue                                     # pas une chaîne échappée : déjà dans le HTML visible
        try:
            html = json.loads('"' + raw + '"')
        except json.JSONDecodeError:
            continue
        if _NUTRI.search(html):
            out.append(html)
            if len(out) >= limit:
                break
    return "\n".join(out)



_DIV = re.compile(r"<(/?)div\b([^>]*)>", re.I)
_DIV_TABLE = re.compile(r"""(?:id|class)\s*=\s*["'][^"']*\b(?:resp-table|div-table|nutrition-table|table-nutri\w*)\b(?![-\w])""", re.I)
_DIV_ROW = re.compile(r"""(?:id|class)\s*=\s*["'][^"']*\b(?:resp-table-row|resp-table-header|table-row|table-header-row|nutri\w*-row)\b(?![-\w])""", re.I)
_DIV_CELL = re.compile(r"""class\s*=\s*["'][^"']*\b(?:table-(?:body|header)-cell|table-cell|nutri\w*-cell)\b(?![-\w])""", re.I)


_TABLE_BLOCK = re.compile(r"(?is)(<table\b[^>]*>)(.*?</table>)")
_DATA_LABEL = re.compile(r"""data-label\s*=\s*["'][^"']*?\b((?:pour|par)\s*\d+(?:[.,]\d+)?\s*(?:g|ml|g[ée]lules?|comprim[ée]s?|capsules?))\b""", re.I)


def datalabel_headers(page: str) -> str:
    """Optigura : la portion est dans un attribut (<td data-label="Valeurs pour 30g">), pas dans un en-tête visible.
    On ajoute une ligne d'en-tête « | Pour 30g » au tableau pour que la portion soit connue à la lecture."""
    if "data-label" not in page:
        return page

    def fix(m: re.Match) -> str:
        inner = m.group(2)
        lab = _DATA_LABEL.search(inner)
        if not lab or re.search(r"<th\b[^>]*>[^<]*(?:pour|par)\s*\d", inner, re.I):
            return m.group(0)
        return f"{m.group(1)}<tr><td>Valeurs</td><td>{htmllib.escape(lab.group(1))}</td></tr>{inner}"
    return _TABLE_BLOCK.sub(fix, page)



def divtables_to_tables(page: str) -> str:
    """Tableaux construits en <div> (EAFIT : #resp-table, .resp-table-row, .table-body-cell) → vrais <table>.

    Seules les div dont la classe ou l'identifiant désigne explicitement un tableau, une ligne ou une cellule sont
    converties ; les autres restent intactes. Une pile apparie chaque </div> à son ouverture.
    """
    if "table-" not in page and "resp-table" not in page:
        return page
    out, stack, last = [], [], 0
    for m in _DIV.finditer(page):
        out.append(page[last:m.start()])
        last = m.end()
        if m.group(1):                                   # </div>
            tag = stack.pop() if stack else "div"
            out.append(f"</{tag}>")
            continue
        attrs = m.group(2)
        tag = "td" if _DIV_CELL.search(attrs) else "tr" if _DIV_ROW.search(attrs) else "table" if _DIV_TABLE.search(attrs) else "div"
        stack.append(tag)
        out.append(f"<{tag}>" if tag != "div" else m.group(0))
    out.append(page[last:])
    return "".join(out)

# Une vraie ligne de tableau nutritionnel : un nutriment puis, dans la même ligne, une quantité chiffrée.
_HAS_TABLE = re.compile(r"<t[dh][^>]*>[^<]*(?:prot[ée]ines?|zinc|magn|kcal|cr[ée]atine|collag|epa\b|dha\b|vitamine d|chol[ée]calcif)"
                        r"(?:(?!</tr>).){0,300}?\d[\d,.]*\s*(?:g|mg|µg|mcg|ui|iu|kcal|kj)\b", re.I | re.S)


_JSON_NUTRI = re.compile(r'"dosage"\s*:\s*"([^"]{0,60})"\s*,\s*"detail_nutritionnel"\s*:\s*(\[[^\]]{0,6000}\])')


_HAS_HEADER = re.compile(r"<t[dh][^>]*>[^<]{0,40}(?:100\s*g|100\s*ml|par |pour |portion|dose)", re.I)


def json_nutrition_tables(page: str, limit: int = 3) -> str:
    """Tableaux nutritionnels rangés dans le JSON des variantes (métachamps Shopify « info_diet », Fitness Boutique)."""
    out, seen = [], set()
    for m in _JSON_NUTRI.finditer(page):
        try:
            rows = json.loads(m.group(2))
        except ValueError:
            continue
        cells = [(str(r.get("title", "")), f'{r.get("value", "")} {r.get("unit", "")}'.strip()) for r in rows if isinstance(r, dict)]
        key = (m.group(1), tuple(cells))
        if not cells or key in seen:
            continue
        seen.add(key)
        head = htmllib.escape(m.group(1).replace("\\/", "/"))
        out.append(f"<table><tr><th>Nutriment</th><th>{head}</th></tr>" +
                   "".join(f"<tr><td>{htmllib.escape(t)}</td><td>{htmllib.escape(v)}</td></tr>" for t, v in cells) + "</table>")
        if len(out) >= limit:
            break
    return "\n".join(out)


_SERVING_FACT = re.compile(r"(?:taille (?:de la|d['’]une) (?:dose|portion)|une portion|1 portion|dose journali[eè]re|portion journali[eè]re)\s*:?\s*[^<\n]{1,60}", re.I)


def serving_facts(page: str) -> str:
    """« Taille de la dose : 1 doseur de 25ml (10g) » : souvent hors de la zone produit, indispensable au calcul."""
    text = re.sub(r"<[^>]+>", "\n", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page))
    found = []
    for m in _SERVING_FACT.finditer(text):
        fact = re.sub(r"\s+", " ", htmllib.unescape(m.group(0))).strip()
        if re.search(r"\d", fact) and fact not in found:
            found.append(fact)
        if len(found) >= 2:
            break
    return "".join(f"<p>{htmllib.escape(f)}</p>" for f in found)


def with_nutrition_tables(body: str, page: str) -> str:
    """Ajoute à la zone produit le tableau nutritionnel de la page s'il lui manque (onglet, <template>, JS)."""
    facts = serving_facts(page)
    if facts and facts not in body:
        body += "\n" + facts
    if not _HAS_TABLE.search(body) or not _HAS_HEADER.search(body):
        # pas de tableau, ou un tableau dont l'en-tête (« 100 g | 1 dose ») a été perdu avec la zone
        body += "\n" + page_nutrition_tables(datalabel_headers(divtables_to_tables(page)))
    if not _HAS_TABLE.search(body):
        body += "\n" + json_nutrition_tables(page)
    if not _HAS_TABLE.search(body):
        body += "\n" + embedded_tables(page)
    return body


def page_nutrition_tables(page: str, limit: int = 4) -> str:
    """Tableaux nutritionnels de la page, où qu'ils soient (secours quand la zone produit les a manqués)."""
    clean = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)   # <template> gardé : tableaux Alpine.js (HSN)
    tables = [t for t in re.findall(r"(?is)<table\b.*?</table>", clean) if _NUTRI.search(re.sub(r"<[^>]+>", " ", t))]
    facts = []
    text = re.sub(r"<[^>]+>", "\n", clean)
    for m in re.finditer(r"(poids net|contenance|contenu net|quantit[ée] nette)\s*:?\s*\n*\s*([^\n]{1,40})", text, re.I):
        facts.append(f"<p>{htmllib.escape(m.group(1))} : {htmllib.escape(m.group(2).strip())}</p>")
        if len(facts) >= 2:
            break
    return "\n".join(facts[:2] + tables[:limit])


# --------------------------------------------------------------------------- traitements propres à un site

def prozis_nutrition(client, site, page: str, node: dict) -> str:
    """Prozis charge son tableau nutritionnel depuis /product/nutrition-table : on le convertit en tableau HTML."""
    m = re.search(r"index\?_id=(\d+)", page.replace("\\/", "/"))
    sku = node.get("sku")
    if not m or not sku:
        return ""
    pid = m.group(1)
    url = f"{site.root}/product/nutrition-table?cachetag=no&sku={quote(sku, safe='')}&id={pid}&parent={pid}"
    try:
        resp = client.get(url, headers=XHR, accept_404=True)
        data = resp.json().get("nutTable") if resp is not None else None
    except (FetchError, BlockedByRobots, ValueError) as exc:
        log.warning("Prozis : tableau nutritionnel illisible pour %s (%s)", sku, exc)
        return ""
    if not data:
        return ""
    table = data.get("table") or {}
    serving = ((data.get("servings") or {}).get("size") or {}).get("value") or "dose"
    doses = ((data.get("servings") or {}).get("container") or {}).get("value")
    weight = (data.get("weight") or {}).get("value")
    rows = []

    def add(items, level=0):
        for it in items or []:
            if not isinstance(it, dict) or not it.get("name"):
                continue
            amt = it.get("amount") or {}
            rows.append(f"<tr><td>{htmllib.escape(it['name'])}</td><td>{htmllib.escape(str(amt.get('byServ') or ''))}</td>"
                        f"<td>{htmllib.escape(str(amt.get('by100') or ''))}</td></tr>")
            add(it.get("ingredients"), level + 1)

    if table.get("energy"):
        add([table["energy"]])
    for key in ("nutrients", "vitamins", "complex"):
        add(table.get(key))
    head = (f"<p>Dose journalière : {htmllib.escape(serving)}</p>" + (f"<p>Nombre de doses : {doses}</p>" if doses else "")
            + (f"<p>Poids net : {htmllib.escape(str(weight))}</p>" if weight else ""))
    return (head + f"<table><tr><th>Informations nutritionnelles</th><th>Par dose ({htmllib.escape(serving)})</th>"
            f"<th>Pour 100 g</th></tr>{''.join(rows)}</table>")


HOOKS = {"prozis": prozis_nutrition}


# --------------------------------------------------------------------------- collecteur

def _extras(page: str, url: str = "") -> dict:
    from ..details import page_extras             # import tardif, comme pour l'origine
    return page_extras(page, url)


def _origin_text(page: str) -> str:
    from ..origin import origin_text_from_page   # import tardif : origin importe collectors.base
    return origin_text_from_page(page)


def _words(url: str) -> str:
    path = urlsplit(url).path
    return re.sub(r"[-_/.]+", " ", re.sub(r"\.(html?|php|aspx)$", "", path))


class PageCollector(Collector):
    platform = "page"
    max_category_pages = 400

    @property
    def cfg(self) -> dict:
        return self.site.filters or {}

    def _abs(self, u: str) -> str:
        return u if u.startswith("http") else urljoin(self.site.base_url.rstrip("/") + "/", u.lstrip("/"))

    # -- découverte -------------------------------------------------------
    def _fetch_xml(self, url: str) -> Optional[ET.Element]:
        resp = self.client.get(url, accept_404=True)
        if resp is None:
            return None
        content = resp.content
        if content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)
        try:
            return ET.fromstring(content)
        except ET.ParseError:
            log.warning("%s : sitemap illisible %s", self.site.id, url)
            return None

    def sitemap_urls(self) -> list[str]:
        sitemaps = self.cfg.get("sitemaps") or (["/sitemap.xml"] if not self.cfg.get("start_urls") else [])
        child_rx = re.compile(self.cfg.get("sitemap_child_filter", r"product|produit"), re.I)
        prod_rx = re.compile(self.cfg.get("product_pattern", r"/products?/"))
        queue = [self._abs(s) for s in sitemaps]
        seen, urls = set(), []
        while queue:
            sm = queue.pop(0)
            if sm in seen:
                continue
            seen.add(sm)
            root = self._fetch_xml(sm)
            if root is None:
                continue
            locs = [(l.text or "").strip() for l in root.iter(f"{_NS}loc")]
            if root.tag == f"{_NS}sitemapindex":
                queue += [l for l in locs if child_rx.search(l)]
            else:
                urls += [l for l in locs if prod_rx.search(l)]
        return list(dict.fromkeys(urls))

    def crawl_urls(self) -> list[str]:
        start = [self._abs(u) for u in self.cfg.get("start_urls", [])]
        cat_rx = re.compile(self.cfg["category_pattern"]) if self.cfg.get("category_pattern") else None
        prod_rx = re.compile(self.cfg.get("product_pattern", r"/products?/"))
        host = urlsplit(self.site.base_url).netloc
        queue, seen, found = list(start), set(), []
        while queue and len(seen) < self.max_category_pages:
            page_url = queue.pop(0)
            if page_url in seen:
                continue
            seen.add(page_url)
            try:
                resp = self.client.get(page_url, accept_404=True)
            except (FetchError, BlockedByRobots) as exc:
                log.warning("%s : page ignorée %s (%s)", self.site.id, page_url, exc)
                continue
            if resp is None:
                continue
            for href in re.findall(r'href="([^"#]+)', resp.text):
                link = urljoin(page_url, htmllib.unescape(href)).split("#")[0]
                if urlsplit(link).netloc != host:
                    continue
                base, _, query = link.partition("?")
                pg = re.search(r"(?:^|&)((?:page|p|pg|pagenum)=\d+)(?:&|$)", query)
                link = base + (f"?{pg.group(1)}" if pg and cat_rx and cat_rx.search(base) else "")
                if prod_rx.search(base):
                    found.append(base)
                elif cat_rx and cat_rx.search(base) and link not in seen:
                    queue.append(link)
        return list(dict.fromkeys(found))

    def discover(self) -> list[str]:
        urls = self.sitemap_urls() if self.cfg.get("sitemaps") or not self.cfg.get("start_urls") else []
        if self.cfg.get("start_urls"):
            urls += self.crawl_urls()
        urls = list(dict.fromkeys(urls))
        if self.cfg.get("prefilter_url"):
            from ..classify import classify             # import tardif : classify importe aussi collectors
            urls = [u for u in urls if classify(RawProduct(site_id=self.site.id, external_id="", handle="",
                                                            title=_words(u), url=u))]
        return urls

    # -- fiche ------------------------------------------------------------
    def parse_page(self, url: str, page: str) -> Optional[RawProduct]:
        nodes = extract_jsonld(page)
        node = main_product_node(nodes) or {}
        title = (node.get("name") or "").strip()
        if not title:
            m = re.search(r'<meta property="og:title" content="([^"]+)"', page) or re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
            title = re.sub(r"<[^>]+>|\s+", " ", htmllib.unescape(m.group(1))).strip() if m else ""
        if not title:
            return None
        brand = node.get("brand")
        brand = brand.get("name") if isinstance(brand, dict) else brand

        cfg_mag = magento_config(page)
        if cfg_mag:
            variants = variants_from_magento(cfg_mag, url)
        elif self.cfg.get("variants_from") == "html_list":
            variants = variants_from_html_list(page, url) or variants_from_jsonld(node, nodes, url) if node else variants_from_html_list(page, url)
        else:
            variants = variants_from_jsonld(node, nodes, url, self.cfg.get("sku_format")) if node else []

        body = with_nutrition_tables(zone_html(datalabel_headers(divtables_to_tables(page))), page)
        desc = node.get("description") or ""
        if desc and desc[:80] not in body:
            body = f"<p>{htmllib.escape(desc)}</p>\n{body}"
        hint = format_hint(page)
        if hint:
            body += f"\n<p>Contenance : {hint}</p>"
        hook = HOOKS.get(self.cfg.get("hook", ""))
        if hook:
            body = hook(self.client, self.site, page, node) + "\n" + body

        pid = str(node.get("productGroupID") or node.get("productID") or node.get("sku")
                  or urlsplit(url).path.strip("/")).rsplit("/", 1)[-1][:80]
        return RawProduct(
            site_id=self.site.id, external_id=pid, handle=urlsplit(url).path.strip("/").rsplit("/", 1)[-1][:255],
            title=title, url=url, vendor=(brand or "").strip() or None,
            product_type=node.get("category") if isinstance(node.get("category"), str) else None,
            body_html=body, variants=variants,
            option_names=sorted({k for v in variants for k in v.options}), source="page",
            origin_text=_origin_text(page),
            **_extras(page, url),
        )

    def iter_products(self) -> Iterator[RawProduct]:
        urls = self.only_urls if self.only_urls is not None else self.discover()
        log.info("%s : %d fiches à ouvrir", self.site.id, len(urls))
        limit = self.cfg.get("max_products")
        seen_ids: set[str] = set()
        for i, url in enumerate(urls):
            if limit and i >= limit:
                break
            try:
                resp = self.client.get(url, accept_404=True)
            except (FetchError, BlockedByRobots) as exc:
                log.warning("%s : fiche ignorée %s (%s)", self.site.id, url, exc)
                continue
            if resp is None:
                continue
            product = self.parse_page(url, resp.text)
            if not product or not product.variants:
                if product:
                    log.info("%s : aucun prix lisible sur %s", self.site.id, url)
                continue
            if product.external_id in seen_ids:         # deux URL pour la même fiche
                continue
            seen_ids.add(product.external_id)
            yield product


class ShopifyHeadlessCollector(PageCollector):
    """Greenwhey : sitemap + JSON-LD ProductGroup (variante = parfum, offre = format)."""
    platform = "shopify_headless"

    @property
    def cfg(self) -> dict:
        return {"sitemaps": ["/sitemap.xml"], "product_pattern": r"/products/[^/?#]+$", **(self.site.filters or {})}

    def parse_page(self, url, page):
        product = product_from_jsonld(self.site, url, extract_jsonld(page))
        if product:
            product.body_html = (product.body_html or "") + "\n" + zone_html(page)   # tableau nutritionnel de la page
            ex = _extras(page, url)
            product.image_url = product.image_url or ex["image_url"]
            product.rating, product.review_count = ex["rating"], ex["review_count"]
        return product


SitemapJsonLdCollector = PageCollector
