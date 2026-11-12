import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from dosehunt import db
from dosehunt.classify import classify
from dosehunt.collectors.jsonld import ShopifyHeadlessCollector
from dosehunt.collectors.shopify import ShopifyCollector, parse_product
from dosehunt.config import get_site
from dosehunt.export import build_export
from dosehunt.extract import extract
from dosehunt.formats import parse_format
from dosehunt.http import PoliteClient
from dosehunt.models import Format
from dosehunt.pipeline import recompute_index, run_site, seed

FIX = Path(__file__).parent / "fixtures"
CATALOG = json.loads((FIX / "shopify_products.json").read_text(encoding="utf-8"))


def shopify_transport(products, page_size=250):
    def handler(request: httpx.Request):
        if request.url.path.endswith("/products.json"):
            page = int(request.url.params.get("page", 1))
            chunk = products[(page - 1) * page_size: page * page_size]
            return httpx.Response(200, json={"products": chunk})
        return httpx.Response(404, text="not found")
    return httpx.MockTransport(handler)


def client(transport):
    return PoliteClient(delay_seconds=0, respect_robots=False, transport=transport)


@pytest.fixture
def engine(tmp_path):
    e = db.get_engine(f"sqlite:///{tmp_path}/t.db")
    db.init_db(e)
    seed(e)
    return e


def raw(title, **kw):
    site = get_site("raptor")
    base = {"id": 1, "handle": "h", "title": title, "vendor": "x", "product_type": kw.pop("product_type", ""),
            "tags": [], "body_html": kw.pop("body", ""), "options": [{"name": "Title"}],
            "variants": [{"id": 9, "title": "Default Title", "price": "10.00", "option1": "Default Title"}]}
    base.update(kw)
    return parse_product(site, base)


# ---------------------------------------------------------------- collecteur

def test_shopify_pagination_and_dedup():
    products = CATALOG["products"] * 1
    site = get_site("raptor")
    site.page_size = 5
    try:
        got = ShopifyCollector(site, client(shopify_transport(products, 5))).collect()
    finally:
        site.page_size = 250
    assert len(got) == len(products)
    assert len({p.external_id for p in got}) == len(products)


def test_compare_at_price_cleanup():
    site = get_site("biotechusa")
    p = next(x for x in CATALOG["products"] if x["id"] == 1005)
    assert parse_product(site, p).variants[0].compare_at_price is None          # 0.00
    glowy = next(x for x in CATALOG["products"] if x["id"] == 8756123271514)
    assert parse_product(site, glowy).variants[0].compare_at_price is None      # 44 < 48


def test_headless_sitemap_jsonld():
    pages = {
        "/sitemap.xml": (FIX / "greenwhey_sitemap_index.xml").read_bytes(),
        "/sitemap/products/1.xml": (FIX / "greenwhey_sitemap_products.xml").read_bytes(),
        "/products/isolat-de-whey-native-100-bio": (FIX / "greenwhey_product.html").read_bytes(),
    }

    def handler(req):
        body = pages.get(req.url.path)
        return httpx.Response(200, content=body) if body else httpx.Response(404)

    got = ShopifyHeadlessCollector(get_site("greenwhey"), client(httpx.MockTransport(handler))).collect()
    assert len(got) == 1
    p = got[0]
    assert p.title == "Isolat de Whey Native" and p.external_id == "2000280584255"
    assert [v.price for v in p.variants] == [59.95, 113.91]
    assert p.variants[1].options == {"Saveur": "Chocolat", "Format": "1.8 kg (2 produits)"}


# ---------------------------------------------------------------- classement

@pytest.mark.parametrize("title,ptype,expected", [
    ("Native Whey Isolate", "Isolate", {"whey": "isolate"}),
    ("100% Vegan Protein", "Protéines végétales", {"whey": "vegane"}),
    ("Radical Whey", "whey", {"whey": "classique"}),
    ("Egg Protein", "whey", {}),
    ("Diet Shake", "Protéine minceur", {}),
    ("Barre Olympique 350 kg", "MATERIEL", {}),
    ("Crispy Protein Bar", "barres", {"barres": None}),
    ("Whey + Collagen HT", "whey", {"whey": "classique", "collagene": None}),
    ("Zinc & Magnesium", "", {"zinc": None, "magnesium": None}),
    ("Vitamine D3 + K2 MK7", "Immunité", {"vitamine_d": None}),
    ("Multivitamines", "Vitamines", {}),
    ("Omega 3 + Krill", "", {"omega3": None}),
    ("Crea ZERO", "Créatine", {"creatine": None}),
])
def test_classify(title, ptype, expected):
    got = {c.category: c.subcategory for c in classify(raw(title, product_type=ptype))}
    assert got == expected


def test_combined_flag():
    cl = classify(raw("Zinc & Magnesium"))
    assert all(c.combined for c in cl)


def test_site_filters():
    fb = get_site("fitnessboutique")
    assert classify(raw("Créatine", product_type="DIETETIQUE"), fb)
    assert classify(raw("Créatine Gym Bag", product_type="ACCESS"), fb) == []
    nm = get_site("nutrimea")
    dutch = raw("Magnesium Glycinaat", body="<p>Magnesium glycinaat voor het zenuwstelsel en de spieren, met vitamine B6.</p>")
    assert classify(dutch, nm) == []


# ---------------------------------------------------------------- formats

@pytest.mark.parametrize("label,grams,units", [
    ("Pot de 1,38kg / Chocolat", 1380, None),
    ("Vanille / 2.25 kg", 2250, None),
    ("900 g (1 produit)", 900, None),
    ("1.8 kg (2 produits)", 1800, None),
    ("Boite de 20 barres de 70g / Myrtille", 1400, 20),
    ("Golden Caramel / 12x50g", 600, 12),
    ("Pilulier de 120 gélules", None, 120),
    ("90 capsules molles", None, 90),
    ("80 gummies / Cola", None, 80),
])
def test_parse_format(label, grams, units):
    f = parse_format(label)
    assert f.total_grams == grams and f.total_units == units


# ---------------------------------------------------------------- extraction

def test_salt_trap_zinc():
    ac = extract("zinc", "<p>Gluconate de zinc 120 mg par comprimé, soit 15 mg de zinc élément par comprimé.</p>",
                 "Gluconate de Zinc 120 mg", Format(units=120))
    assert ac.amount == 15 and ac.salt_label_mg == 120


def test_magnesium_per_dose():
    ac = extract("magnesium", "<p>1500 mg de bisglycinate de magnésium pour 3 gélules, soit 300 mg de magnésium pour 3 gélules.</p>",
                 "Magnésium bisglycinate 1500mg", Format(units=90))
    assert ac.amount == 100 and ac.units_per_dose == 3


def test_vitamin_d_thousands_and_dose():
    ac = extract("vitamine_d", "<p>La vitamine D3 dosée à 3 000 UI pour 2 gélules.</p>", "Vitamine D3", Format())
    assert ac.amount == 1500


def test_whey_per_serving():
    ac = extract("whey", "<p>24 g de protéines pour une portion de 30 g.</p>", "Whey", Format(grams=750))
    assert ac.amount == 80


def test_bar_from_table_with_br_in_cells():
    p = next(x for x in CATALOG["products"] if x["id"] == 10338189902170)
    ac = extract("barres", p["body_html"], p["title"], Format(units=12))
    assert ac.amount == 13 and ac.source == "regex_table"


def test_omega_sum_per_capsule():
    ac = extract("omega3", "<p>Pour 2 capsules : EPA 660 mg, DHA 440 mg.</p>", "Oméga 3", Format(units=60))
    assert ac.amount == 550


# ---------------------------------------------------------------- bout en bout

def test_end_to_end(engine):
    site = get_site("raptor")      # le catalogue de test est servi comme un seul site Shopify
    stats = run_site(engine, site, client=client(shopify_transport(CATALOG["products"])), use_llm=False)
    assert stats.products_seen == len(CATALOG["products"])
    with engine.connect() as conn:
        rows = conn.execute(select(db.index_rows.c.category, db.index_rows.c.dose_value, db.index_rows.c.unit_value,
                                   db.offers.c.variant_title, db.offers.c.units, db.offers.c.grams, db.products.c.name)
                            .join(db.offers, db.offers.c.id == db.index_rows.c.offer_id)
                            .join(db.products, db.products.c.id == db.offers.c.product_id)).mappings().all()
        reviews = conn.execute(select(db.review_queue)).mappings().all()
    by = {(r["name"], r["variant_title"], r["category"]): r for r in rows}

    # Whey isolate 85 % : 58,95 € / 0,85 kg = 69,35 €/kg de protéine
    r = by[("Native Whey Isolate", "Pot de 1kg / Chocolat", "whey")]
    assert r["dose_value"] == pytest.approx(58.95 / 0.85, rel=1e-3)

    # Vitamine D en durée : 1 mois × 30 j × 2 gélules = 60 gélules × 1 500 UI = 90 000 UI → 11,90 € / 0,9
    r = by[("Vitamine D3 – ancienne formule", "1 mois", "vitamine_d")]
    assert r["units"] == 60
    assert r["dose_value"] == pytest.approx(11.90 / 0.9, rel=1e-3)

    # Barres : 2 boîtes × 12 barres
    assert by[("(Super) Crunchy Peanuts Choco - 12 Barres Protéinées", "2 boîtes", "barres")]["units"] == 24

    # Piège du sel : 15 mg réels, pas 120
    r = by[("Gluconate de Zinc 120 mg - 120 comprimés", "Default Title", "zinc")]
    assert r["dose_value"] == pytest.approx(11.99 / (120 * 15 / 1000), rel=1e-3)

    # Produit combiné présent dans les deux listes
    cats = {k[2] for k in by if k[0] == "Whey + Collagen HT"}
    assert "whey" in cats

    # Exclus : œuf et barre olympique jamais indexés
    names = {k[0] for k in by}
    assert "Egg Protein" not in names and "Barre Olympique 350 kg" not in names

    # Erreur d'unité BioTechUSA (« 12,5 g ») : en revue, pas dans l'index
    assert ("Zinc Duo - 60 comprimés", "Default Title", "zinc") not in by
    zd = [x for x in reviews if x["external_id"] == "1005"]
    assert zd and "g au lieu de mg" in zd[0]["detail"]

    # Export lisible par le front
    data = build_export(engine)
    assert data["categories"]["zinc"]["count"] >= 2
    assert any(p["labelMg"] == 120 for p in data["products"])


def test_second_run_keeps_history_and_recompute(engine):
    site = get_site("raptor")
    products = json.loads(json.dumps(CATALOG["products"]))
    run_site(engine, site, client=client(shopify_transport(products)), use_llm=False)
    products[3]["variants"][0]["price"] = "49.95"            # baisse de prix de la whey
    products = [p for p in products if p["id"] != 1009]       # oméga-3 retiré du catalogue
    run_site(engine, site, client=client(shopify_transport(products)), use_llm=False)
    with engine.connect() as conn:
        hist = conn.execute(select(db.price_history.c.price).join(db.offers).where(db.offers.c.variant_id == "2001")
                            .order_by(db.price_history.c.observed_at)).scalars().all()
        omega_indexed = conn.execute(select(db.index_rows).where(db.index_rows.c.category == "omega3")).all()
    assert hist == [58.95, 49.95]
    assert omega_indexed == []
    assert recompute_index(engine) > 0
