"""Collecteur « fiches » et flux d'affiliation, sur des fragments relevés sur les sites le 11/11/2026."""
import gzip
import json

import httpx
import pytest
from sqlalchemy import select

from dosehunt import db
from dosehunt.collectors.feed import AffiliateFeedCollector, parse_feed
from dosehunt.collectors.page import (PageCollector, extract_jsonld, magento_config, variants_from_html_list,
                                      variants_from_magento, zone_html)
from dosehunt.config import Site, get_site
from dosehunt.extract import extract
from dosehunt.formats import parse_format
from dosehunt.http import PoliteClient
from dosehunt.models import Format
from dosehunt.pipeline import run_site, seed


def client(handler):
    return PoliteClient(0, respect_robots=False, transport=httpx.MockTransport(handler))


def site(**filters) -> Site:
    return Site(id="t", name="Test", base_url="https://shop.test", platform="page", collector="page",
                status="active", filters=filters)


# ------------------------------------------------------------------ Bulk : format dans la référence

BULK = """<html><head><script type="application/ld+json">{"@graph":[{"@type":"WebPage","name":"Pure Whey"},
{"@type":"Product","name":"Protéine Whey en Poudre","brand":{"@type":"Brand","name":"Bulk"},"offers":[
{"@type":"Offer","sku":"BPB-PWPC-CHOC-0450","price":17.99,"priceCurrency":"EUR","availability":"InStock",
 "priceSpecification":{"@type":"UnitPriceSpecification","priceType":"https://schema.org/ListPrice","price":27.49}},
{"@type":"Offer","sku":"BPB-PWPC-CHOC-0900","price":29.99,"priceCurrency":"EUR","availability":"InStock"},
{"@type":"Offer","sku":"BPB-PWPC-UNFL-4000","price":124.99,"priceCurrency":"EUR","availability":"OutOfStock"}]}]}
</script></head><body><main><table><tr><th>Valeurs</th><th>Pour 100 g</th><th>Par portion de 30 g</th></tr>
<tr><td>Protéines</td><td>65g</td><td>23g</td></tr></table></main></body></html>"""


def test_bulk_sku_format_and_list_price():
    c = PageCollector(site(sku_format=r"-(?P<flavour>[A-Z]{3,5})-(?P<size>\d{4})$"), client(lambda r: httpx.Response(404)))
    p = c.parse_page("https://shop.test/fr/products/proteine-whey-poudre/bpb-wpc8-0000", BULK)
    v = p.variants
    assert [(x.options["Format"], x.price, x.compare_at_price, x.available) for x in v] == [
        ("450", 17.99, 27.49, True), ("900", 29.99, None, True), ("4000", 124.99, None, False)]
    assert parse_format(v[0].title).grams == 450                 # « 450 » nu : poudre → grammes
    assert extract("whey", p.body_html, p.title, Format(grams=450)).amount == 65


# ------------------------------------------------------------------ HSN : Magento 2 Hyvä

HSN_CFG = {"attributes": {
    "216": {"code": "content_weight", "label": "Content Weight", "options": [
        {"id": "6045", "label": "Monodose (30g)", "products": ["14668"]},
        {"id": "1854", "label": "500g", "products": ["15001"]},
        {"id": "3486", "label": "2Kg", "products": ["16765"]}]},
    "218": {"code": "flavour", "label": "Flavour", "options": [
        {"id": "1706", "label": "Chocolat", "products": ["14668", "15001", "16765"]}]}},
    "index": {"14668": {"216": "6045", "218": "1706"}, "15001": {"216": "1854", "218": "1706"},
              "16765": {"216": "3486", "218": "1706"}},
    "optionPrices": {
        "14668": {"oldPrice": {"amount": 2.780981}, "finalPrice": {"amount": 1.909551}},
        "15001": {"oldPrice": {"amount": 19.9}, "finalPrice": {"amount": 19.9}},
        "16765": {"oldPrice": {"amount": 71.92}, "finalPrice": {"amount": 69.7624}}},
    "salable": {"216": {"6045": ["14668"], "1854": ["15001"]}},
    "skus": {"14668": "HSNS-MW30CH", "15001": "HSNS-MW500CH", "16765": "HSNS-MW2KCH"}}
HSN = ("<html><body><main><h1>Evowhey protein</h1><table><thead><tr><th>Valeurs nutritionnelles</th>"
       "<th x-show=\"activeTab === 'por_servicio'\">Par dose</th><th x-show=\"activeTab === 'por_cien_gramos'\">Pour 100 g</th>"
       "</tr></thead><tbody><tr><td><p>Protéines</p></td><td> 22 g </td><td> 73 g </td></tr></tbody></table></main>"
       "<script> function initConfigurableSwatchOptions_16688() { const c = initConfigurableOptions( '16688', "
       + json.dumps(HSN_CFG) + " ); }</script></body></html>")


def test_magento_hyva_config():
    cfg = magento_config(HSN)
    v = variants_from_magento(cfg, "https://www.hsnstore.fr/marques/sport-series/evowhey-protein")
    by = {x.title: x for x in v}
    assert by["Monodose (30g) / Chocolat"].price == 1.91 and by["Monodose (30g) / Chocolat"].compare_at_price == 2.78
    assert by["500g / Chocolat"].compare_at_price is None          # ancien prix égal : pas une promo
    assert by["2Kg / Chocolat"].available is False                 # absent de « salable »
    assert parse_format(by["2Kg / Chocolat"].title).grams == 2000
    assert extract("whey", zone_html(HSN), "Evowhey", Format(grams=500)).amount == 73


# ------------------------------------------------------------------ Optigura : liste HTML des tailles

OPTIGURA = """<div class="options"><div class="opt1"><div class="label"><div class="wrap"> Taille </div></div>
<div class="c-select"><div class="list"><ul><li><span><!----> 30g </span> <span class="ml-4 text-xs"> 2,40 €</span></li>
<li><span><!----> 300g </span> <span class="ml-4 text-xs"> 26,90 €</span></li><li><span><!----> 900g </span>
<span class="ml-4 text-xs"> 55,90 €</span></li><li><span><!----> 2000g </span> <span class="ml-4 text-xs"> 94,90 €</span></li>
</ul></div></div></div></div>"""


def test_optigura_html_list():
    v = variants_from_html_list(OPTIGURA, "https://www.optigura.fr/product/100-whey-protein-advanced")
    assert [(x.title, x.price) for x in v] == [("30g", 2.4), ("300g", 26.9), ("900g", 55.9), ("2000g", 94.9)]


# ------------------------------------------------------------------ Zumub : parcours + ProductGroup

ZUMUB_CAT = '<a href="/FR/creatine-monohydrate-de-creatine-c-213_165_74/creatine-1kg-p-25901#7186">Créatine</a>' \
            '<a href="/FR/whey-c-213_1">Whey</a><a href="https://autre.site/x-p-1">x</a>'
ZUMUB_PRODUCT = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"ProductGroup","name":"Créatine",
"brand":{"@type":"Brand","name":"Zumub"},"productGroupID":"25901","hasVariant":[
{"@type":"Product","name":"Créatine 100 g","sku":"9182","size":"100 g","offers":{"@type":"Offer","price":"1.50",
 "priceCurrency":"EUR","availability":"https://schema.org/InStock","priceSpecification":{"@type":"UnitPriceSpecification",
 "priceType":"https://schema.org/ListPrice","price":"2.50","priceCurrency":"EUR"}}},
{"@type":"Product","name":"Créatine 1 kg","sku":"7186","size":"1 kg","offers":{"@type":"Offer","price":"12.98",
 "priceCurrency":"EUR","availability":"https://schema.org/InStock"}}]}</script>
<main><div class="description">Créatine monohydrate pure.</div></main>"""


def test_zumub_crawl_and_product_group():
    seen = []

    def handler(req):
        seen.append(req.url.path)
        if req.url.path == "/FR/":
            return httpx.Response(200, text=ZUMUB_CAT)
        if req.url.path == "/FR/whey-c-213_1":
            return httpx.Response(200, text="")
        if req.url.path.endswith("-p-25901"):
            return httpx.Response(200, text=ZUMUB_PRODUCT)
        return httpx.Response(404)
    s = site(start_urls=["/FR/"], category_pattern=r"/FR/[a-z0-9-]+-c-[\d_]+$", product_pattern=r"-p-\d+$")
    products = PageCollector(s, client(handler)).collect()
    assert len(products) == 1 and products[0].external_id == "25901"
    assert [(v.title, v.price, v.compare_at_price) for v in products[0].variants] == [
        ("Créatine 100 g / 100 g", 1.5, 2.5), ("Créatine 1 kg / 1 kg", 12.98, None)]
    assert "/FR/whey-c-213_1" in seen and not any("autre.site" in u for u in seen)


# ------------------------------------------------------------------ Prozis : CDATA + tableau par API

PROZIS = """<script>/*<![CDATA[*/ { "@context": "https://schema.org/", "@type": "Product", "name": "100% Real Whey Protein 907g",
"brand": {"@type": "Brand", "name": "Prozis"}, "sku": "NUT00/1838081663", "offers": {"@type": "Offer", "priceCurrency": "EUR",
"price": "39.99", "availability": "https://schema.org/InStock", "priceSpecification": {"@type": "UnitPriceSpecification",
"priceType": "https://schema.org/StrikethroughPrice", "priceCurrency": "EUR", "price": "49.99"}}} /*]]>*/</script>"""
PROZIS_PAGE = PROZIS.replace("<script>", '<script type="application/ld+json">') + \
    '<script>VueEs6.render("#pdp",{"url":"https:\\/\\/www.prozis.com\\/fr\\/fr\\/product\\/index?_id=183808"})</script>'
PROZIS_NUT = {"nutTable": {"servings": {"size": {"label": "Dose", "value": "1 doseur(s)(30 g)"},
                                        "container": {"label": "Doses par emballage", "value": 30}},
                           "weight": {"label": "Poids net:", "value": "907 g"},
                           "table": {"energy": {"name": "Énergie", "amount": {"byServ": "114.96 kcal", "by100": "383.20 kcal"}},
                                     "nutrients": [{"name": "Protéines", "amount": {"byServ": "23.10 g", "by100": "77 g"},
                                                    "ingredients": []}], "vitamins": [], "complex": []}}}


def test_prozis_cdata_and_nutrition_hook():
    def handler(req):
        if req.url.path == "/fr/fr/product/nutrition-table":
            assert req.url.params["id"] == "183808" and req.url.params["sku"] == "NUT00/1838081663"
            return httpx.Response(200, json=PROZIS_NUT)
        return httpx.Response(404)
    s = get_site("prozis")
    p = PageCollector(s, client(handler)).parse_page("https://www.prozis.com/fr/fr/prozis/100-real-whey-protein-907g", PROZIS_PAGE)
    v = p.variants[0]
    assert (v.price, v.compare_at_price) == (39.99, 49.99)
    assert extract("whey", p.body_html, p.title, Format(grams=907)).amount == 77


def test_cdata_jsonld_parses():
    assert extract_jsonld(PROZIS.replace("<script>", '<script type="application/ld+json">'))[0]["name"] == "100% Real Whey Protein 907g"


# ------------------------------------------------------------------ Decathlon : fiche par variante, sitemap filtré

DECATHLON = """<script type="application/ld+json">[{"@type":"ProductGroup","name":"Pure whey protéine 100% isolate chocolat 900g",
"brand":{"@type":"Brand","name":"DECATHLON"},"productGroupID":"339686"},{"@type":"Product","name":"Pure whey protéine 100% isolate chocolat 900g",
"sku":"8756408","offers":{"@type":"Offer","price":39.99,"priceCurrency":"EUR","availability":"https://schema.org/InStock"}}]</script>"""


def test_decathlon_sitemap_prefilter_gz():
    index = b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://www.decathlon.fr/sitemap/decathlon-products-0.xml</loc></sitemap></sitemapindex>'
    urls = (b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b'<url><loc>https://www.decathlon.fr/p/pure-whey-proteine-100percent-isolate-chocolat-900g/339686/g122m8756408</loc></url>'
            b'<url><loc>https://www.decathlon.fr/p/chaussure-running-kiprun/123/g1m2</loc></url>'
            b'<url><loc>https://www.decathlon.fr/p/barre-de-traction-murale/999/g1m3</loc></url></urlset>')
    opened = []

    def handler(req):
        if req.url.path == "/decathlon-products-index.xml":
            return httpx.Response(200, content=index)
        if req.url.path == "/sitemap/decathlon-products-0.xml":
            return httpx.Response(200, content=gzip.compress(urls))
        if req.url.path.startswith("/p/"):
            opened.append(req.url.path)
            return httpx.Response(200, text=DECATHLON)
        return httpx.Response(404)
    s = site(sitemaps=["/decathlon-products-index.xml"], product_pattern="/p/", prefilter_url=True)
    s.base_url = "https://www.decathlon.fr"
    products = PageCollector(s, client(handler)).collect()
    assert opened == ["/p/pure-whey-proteine-100percent-isolate-chocolat-900g/339686/g122m8756408"]
    assert products[0].variants[0].price == 39.99 and products[0].vendor == "DECATHLON"


# ------------------------------------------------------------------ zone produit

def test_zone_skips_related_products():
    page = ("<header><a>Zinc 50 mg</a></header><main><div class='product-description'><p>15 mg de zinc par gélule.</p>"
            + "<p>" + "Texte descriptif. " * 20 + "</p></div><div class='related-products'><p>Zinc 99 mg par gélule</p></div></main>")
    z = zone_html(page)
    assert "15 mg de zinc" in z and "99 mg" not in z and "50 mg" not in z


# ------------------------------------------------------------------ flux d'affiliation

AWIN_CSV = ("aw_product_id,product_name,aw_deep_link,search_price,rrp_price,brand_name,merchant_category,in_stock,description\n"
            "101,Whey Protein 80 1kg,https://www.awin1.com/pclick.php?p=101,29.99,39.99,The Protein Works,Whey,1,"
            "\"78 g de protéines pour 100 g\"\n"
            "102,Zinc 60 Caps,https://www.awin1.com/pclick.php?p=102,7.99,,The Protein Works,Vitamines,0,15 mg de zinc par gélule\n")


def test_feed_csv_and_missing_url(monkeypatch):
    rows = parse_feed(gzip.compress(AWIN_CSV.encode()))
    assert rows[0]["product_name"] == "Whey Protein 80 1kg"
    s = get_site("theproteinworks")
    monkeypatch.delenv("DOSEHUNT_FEED_THEPROTEINWORKS", raising=False)
    with pytest.raises(NotImplementedError, match="DOSEHUNT_FEED_THEPROTEINWORKS"):
        AffiliateFeedCollector(s, client(lambda r: httpx.Response(404))).collect()
    monkeypatch.setenv("DOSEHUNT_FEED_THEPROTEINWORKS", "https://feeds.test/tpw.csv.gz")
    got = AffiliateFeedCollector(s, client(lambda r: httpx.Response(200, content=gzip.compress(AWIN_CSV.encode())))).collect()
    assert [(p.title, p.variants[0].price, p.variants[0].compare_at_price, p.variants[0].available) for p in got] == [
        ("Whey Protein 80 1kg", 29.99, 39.99, True), ("Zinc 60 Caps", 7.99, None, False)]


def test_feed_end_to_end(tmp_path, monkeypatch):
    e = db.get_engine(f"sqlite:///{tmp_path}/f.db")
    db.init_db(e)
    seed(e)
    monkeypatch.setenv("DOSEHUNT_FEED_THEPROTEINWORKS", "https://feeds.test/tpw.csv")
    run_site(e, get_site("theproteinworks"), client=client(lambda r: httpx.Response(200, text=AWIN_CSV)), use_llm=False)
    with e.connect() as conn:
        rows = conn.execute(select(db.index_rows.c.category, db.index_rows.c.dose_value)).all()
    # le zinc est en rupture : gardé dans l'index, le site l'affiche en grisé en fin de liste
    assert sorted(rows) == [("whey", pytest.approx(29.99 / 0.78, rel=1e-3)), ("zinc", pytest.approx(8.8778, rel=1e-3))]
