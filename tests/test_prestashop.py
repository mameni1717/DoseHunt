import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import select

from dosehunt import db
from dosehunt.collectors.prestashop import PrestaShopCollector, product_zone_html, variant_groups
from dosehunt.config import get_site
from dosehunt.extract import extract
from dosehunt.http import PoliteClient
from dosehunt.models import Format
from dosehunt.pipeline import run_site, seed
from dosehunt.robots import RobotsRules

FIX = Path(__file__).parent / "fixtures"
PAGE = (FIX / "prestashop_nutripure_zinc.html").read_text(encoding="utf-8")
PRODUCT_URL = "https://www.nutripure.fr/fr/sante/146-zinc-bisglycinate.html"

# Réponses « refresh » réelles (prix relevés le 11/11/2026), réduites au nécessaire
REFRESH = {
    "220": {"id_product_attribute": 679, "product_url": PRODUCT_URL.replace("146-", "146-679-"),
            "product_prices": '<span class="price" itemprop="price" content="16.9">16,90 €</span>',
            "product_add_to_cart": '<button class="add-to-cart" data-button-action="add-to-cart">'},
    "221": {"id_product_attribute": 680, "product_url": PRODUCT_URL.replace("146-", "146-680-"),
            "product_prices": '<span class="discount-percentage">-10%</span> <span class="price has-discount" '
                              'itemprop="price" content="45.63">45,63 €</span> <p class="product-discount"> '
                              '<span class="regular-price">50,70 €</span> </p>',
            "product_add_to_cart": '<button class="add-to-cart" data-button-action="add-to-cart">'},
}
LISTING = {"products": [
    {"id_product": "146", "name": "Zinc Bisglycinate", "url": PRODUCT_URL + "#/220-nombre_gelules-90_gelules_3_mois",
     "canonical_url": PRODUCT_URL, "category_name": "Santé", "price_amount": 16.9, "regular_price_amount": 16.9},
    {"id_product": "29", "name": "Pack les Incontournables", "url": "https://www.nutripure.fr/fr/sante/29-pack.html",
     "category_name": "Packs", "price_amount": 57.33, "regular_price_amount": 63.7},
], "pagination": {"total_items": 2, "pages_count": 1}}

FITADIUM_ROBOTS = """User-agent: *
Allow: */*?page=
Disallow: /*?order=
Disallow: /*controller=cart
Disallow: /*controller=order
Disallow: *?controller*
"""


def transport(robots: str = "", seen: list | None = None):
    def handler(req: httpx.Request):
        if seen is not None:
            seen.append(str(req.url))
        path = req.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=robots) if robots else httpx.Response(404)
        if path == "/fr/29-gamme-produits":
            assert req.headers.get("x-requested-with") == "XMLHttpRequest"
            return httpx.Response(200, json=LISTING)
        if path == "/fr/sante/146-zinc-bisglycinate.html":
            return httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})
        if path == "/fr/index.php" and req.method == "POST":
            q = parse_qs(req.url.query.decode())
            assert q["controller"] == ["product"] and q["action"] == ["refresh"]
            return httpx.Response(200, json=REFRESH[q["group[4]"][0]])
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_robots_wildcards_fitadium():
    rules = RobotsRules.parse(FITADIUM_ROBOTS, "DoseHuntBot/0.1")
    assert not rules.can_fetch("https://www.fitadium.com/index.php?controller=product&action=refresh")
    assert rules.can_fetch("https://www.fitadium.com/4-proteines?resultsPerPage=500&page=2")
    assert rules.can_fetch("https://www.fitadium.com/2084-zero-isolate-advanced-18kg.html")
    assert not rules.can_fetch("https://www.fitadium.com/4-proteines?order=product.price.asc")


def test_robots_specific_agent_and_end_anchor():
    rules = RobotsRules.parse("User-agent: *\nDisallow: /\n\nUser-agent: DoseHuntBot\nDisallow: /*.pdf$\n", "DoseHuntBot/0.1")
    assert rules.can_fetch("https://x.fr/produit.html")
    assert not rules.can_fetch("https://x.fr/notice.pdf")


def test_variant_groups_and_zone():
    groups = variant_groups(PAGE)
    assert groups == {"group[4]": [("220", "90 gélules (3 mois)"), ("221", "3x90 gélules (9 mois)")]}
    zone = product_zone_html(PAGE)
    assert "15 mg" in zone and "Magnésium 300 mg" not in zone      # le bloc « produits liés » est écarté


def test_extract_from_real_compo_table():
    ac = extract("zinc", product_zone_html(PAGE), "Zinc Bisglycinate", Format(units=90))
    assert ac.amount == 15 and ac.units_per_dose == 1 and ac.confidence >= 0.9


def test_nutriandco_phrase():
    ac = extract("magnesium", "<p>3 gélules seulement apportent 300 mg de magnésium élément !</p>", "Magnésium", Format(units=90))
    assert ac.amount == 100


def test_collector_reads_combinations():
    c = PrestaShopCollector(get_site("nutripure"), PoliteClient(0, transport=transport()))
    products = c.collect()
    assert len(products) == 1                                        # le pack est hors périmètre
    p = products[0]
    assert p.external_id == "146" and p.vendor == "Nutripure"
    assert [(v.title, v.price, v.compare_at_price) for v in p.variants] == [
        ("90 gélules (3 mois)", 16.9, None), ("3x90 gélules (9 mois)", 45.63, 50.7)]
    assert p.variants[1].options == {"Format": "3x90 gélules (9 mois)"}


def test_refresh_blocked_by_robots_falls_back_to_default():
    seen: list[str] = []
    c = PrestaShopCollector(get_site("nutripure"), PoliteClient(0, transport=transport(FITADIUM_ROBOTS, seen)))
    p = c.collect()[0]
    assert not any("controller=product" in u for u in seen)          # aucune requête interdite envoyée
    assert [(v.title, v.price) for v in p.variants] == [("Default Title", 16.9)]


def test_end_to_end_prestashop(tmp_path):
    e = db.get_engine(f"sqlite:///{tmp_path}/p.db")
    db.init_db(e)
    seed(e)
    run_site(e, get_site("nutripure"), client=PoliteClient(0, transport=transport()), use_llm=False)
    with e.connect() as conn:
        rows = conn.execute(select(db.offers.c.variant_title, db.offers.c.units, db.index_rows.c.dose_value,
                                   db.index_rows.c.final_price, db.index_rows.c.code)
                            .join(db.index_rows, db.index_rows.c.offer_id == db.offers.c.id)).mappings().all()
    by = {r["variant_title"]: r for r in rows}
    assert by["90 gélules (3 mois)"]["units"] == 90
    assert by["3x90 gélules (9 mois)"]["units"] == 270
    # Code NUTRITION10 (-10 %, confiance 0,6) : 16,90 → 15,21 € pour 90 × 15 mg = 1,35 g de zinc
    r = by["90 gélules (3 mois)"]
    assert r["code"] == "NUTRITION10" and r["final_price"] == pytest.approx(15.21)
    assert r["dose_value"] == pytest.approx(15.21 / 1.35, rel=1e-3)


def test_listing_only_when_pages_refused_with_manual_actives(tmp_path):
    """Nutripure (11/11/2026) : listing JSON autorisé, fiches en 403 pour notre robot. On ne contourne pas :
    prix du listing + teneur saisie à la main (config/manual_actives.yaml)."""
    listing = {"products": [
        {"id_product": str(i), "name": "Zinc Bisglycinate" if i == 146 else f"Zinc Test {i}",
         "url": f"https://www.nutripure.fr/fr/sante/{i}-zinc.html", "category_name": "Santé",
         "price_amount": 16.9, "regular_price_amount": 16.9} for i in (146, 201, 202, 203)],
        "pagination": {"pages_count": 1}}

    def handler(req):
        if req.url.path == "/fr/29-gamme-produits":
            return httpx.Response(200, json=listing)
        if req.url.path.endswith(".html"):
            return httpx.Response(403, text="refusé")
        return httpx.Response(404)
    e = db.get_engine(f"sqlite:///{tmp_path}/l.db")
    db.init_db(e)
    seed(e)
    client = PoliteClient(0, respect_robots=False, transport=httpx.MockTransport(handler))
    run_site(e, get_site("nutripure"), client=client, use_llm=False)
    with e.connect() as conn:
        rows = conn.execute(select(db.products.c.external_id, db.offers.c.variant_title, db.index_rows.c.dose_value)
                            .join(db.offers, db.offers.c.product_id == db.products.c.id)
                            .outerjoin(db.index_rows, db.index_rows.c.offer_id == db.offers.c.id)).all()
    by = {r[0]: r for r in rows}
    assert by["146"][1] == "90 gélules"
    # 16,90 € - NUTRITION10 (10 %) = 15,21 € pour 90 × 15 mg = 1,35 g de zinc
    assert by["146"][2] == pytest.approx(15.21 / 1.35, rel=1e-3)
    assert by["201"][2] is None                       # sans teneur saisie : hors index, en revue
