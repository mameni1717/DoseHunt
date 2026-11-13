"""Règles de lecture en espagnol (sites `language: es`).

Extraits RÉELS relevés le 13/11/2026 avec le robot DoseHunt (robots.txt respecté, une requête toutes les 2,5 s) sur
masmusculo.com (catalogue Shopify products.json), myprotein.es (accueil, fiches Impact Whey Protein et Origin Pre-Entreno),
hsnstore.com (accueil, page des cupones) et zumub.com/ES (accueil). Les rares phrases construites sont signalées.
Chaque test vérifie aussi que le même texte lu avec les règles françaises donne le résultat d'avant (rien ne change en France).
"""
from datetime import datetime, timezone

from dosehunt.classify import classify
from dosehunt.codes import extract_codes, shipping_info
from dosehunt.config import Site, get_site
from dosehunt.details import product_details, review_topics
from dosehunt.extract import extract, preworkout_serving, serving_size
from dosehunt.formats import parse_format
from dosehunt.lang import default_language, looks_language
from dosehunt.models import Format, RawProduct
from dosehunt.origin import detect_origin
from dosehunt.rayons import keywords, not_a_rayon

ES = Site(id="masmusculo-es", name="Masmusculo", base_url="https://www.masmusculo.com", platform="shopify",
          collector="shopify", status="active", country="ES")
FR = Site(id="x-fr", name="X", base_url="https://x.fr", platform="shopify", collector="shopify", status="active")


def _p(title, ptype="", body="", rayons=None):
    return RawProduct(site_id="masmusculo-es", external_id=title, handle="h", title=title, url="", product_type=ptype,
                      body_html=body, rayon_categories=sorted(rayons or []))


def _cats(p, site=ES):
    return [(c.category, c.subcategory) for c in classify(p, site)]


# --------------------------------------------------------------------------- langue du site

def test_site_language_from_country_and_config():
    assert ES.language == "es" and FR.language == "fr"
    assert default_language("DE") == "de" and default_language("GB") == "en" and default_language("SE") == "sv"
    assert get_site("myprotein-es").language == "es" and get_site("myprotein-es").country == "ES"
    assert get_site("myprotein").language == "fr"


ZINC_LAMBERTS = ("<p>Aspectos esenciales de este Zinc de Lamberts Laboratorios</p><p>Aporta 15 mg de Zinc</p>"
                 "<p>Apto para vegetarianos y veganos</p><p>Exento de lactosa y gelatina</p>"
                 "<p>Este complemento alimenticio se presenta en un envase con 90 tabletas pequeñas y fáciles tabletas de tragar, "
                 "las cuales se elaboran en el Reino Unido bajo las estrictas normas de fabricación farmacéutica GMP.</p>")


def test_looks_language_es_and_require_language_filter():
    from dosehunt.classify import passes_site_filters
    assert looks_language("Zinc 15mg " + ZINC_LAMBERTS, "es")
    assert not looks_language("Zinc 15mg " + ZINC_LAMBERTS, "fr")
    fr_text = "Le zinc contribue au fonctionnement normal du système immunitaire. Une gélule par jour avec un verre d'eau."
    assert not looks_language(fr_text, "es") and looks_language(fr_text, "fr")
    site = Site(id="t-es", name="T", base_url="https://t.es", platform="shopify", collector="shopify", status="active",
                country="ES", filters={"require_language": True})
    assert passes_site_filters(_p("Zinc 15mg", "Minerales", ZINC_LAMBERTS), site)[0]
    assert not passes_site_filters(_p("Zinc bisglycinate", "", "<p>" + fr_text + "</p>"), site)[0]
    # compatibilité : require_french continue de vérifier le français
    old = Site(id="t-fr", name="T", base_url="https://t.fr", platform="shopify", collector="shopify", status="active",
               filters={"require_french": True})
    assert not passes_site_filters(_p("Zinc 15mg", "Minerales", ZINC_LAMBERTS), old)[0]


# --------------------------------------------------------------------------- classification (titres et types réels)

def test_classification_es_real_titles():
    assert _cats(_p("100% Whey Protein Professional", "Proteina de Suero Whey")) == [("whey", "classique")]
    assert _cats(_p("Evolution Isolate", "Proteína de Aislado de Suero")) == [("whey", "isolate")]
    assert _cats(_p("Vegan Protein", "Proteína Vegetal y Vegano")) == [("whey", "vegane")]
    assert _cats(_p("Caseína Micellar", "Caseina")) == [("whey", "caseine")]
    assert _cats(_p("Creatina Monohidrato", "Creatina monohidrato")) == [("creatine", None)]
    assert _cats(_p("Energy Storm", "Pre entreno")) == [("preworkout", None)]
    assert _cats(_p("Protein Bar (Barrita de Proteína)", "Barritas de Proteinas")) == [("barres", None)]
    assert _cats(_p("Zinc Bisglicinato", "Minerales")) == [("zinc", None)]
    assert _cats(_p("Vitamina C Liposomada 800mg", "Vitamina C")) == [("vitamine_c", None)]
    assert _cats(_p("Glutavol post-entrenamiento", "Glutamina")) == [("glutamine", None)]
    # règles françaises : « Creatina », « Caseína », « Pre entreno » ne sont pas reconnus (France inchangée)
    assert _cats(_p("Creatina Monohidrato", "Creatina monohidrato"), FR) == []
    assert _cats(_p("Energy Storm", "Pre entreno"), FR) == []


def test_exclusions_es():
    # gainers, crèmes, acides aminés : le type « Proteína… » ne suffit pas
    assert _cats(_p("Whey Mass", "Ganadores de peso con proteína")) == []
    assert _cats(_p("Whey Protein Cream", "Cremas de Chocolate Bajas en Azúcar")) == []
    assert _cats(_p("Real Vegan Amino+", "Proteína Vegetal y Vegano")) == []
    # barres énergétiques / avoine et packs
    assert _cats(_p("FlapJack (Barrita de Avena Energética)", "Barritas de Carbohidratos")) == []
    assert _cats(_p("Race Day Mix Pack", "Barritas de Carbohidratos")) == []
    assert _cats(_p("Lote Creatina + Proteína")) == []                       # construit : « lote » = pack


def test_preworkout_exclusions_es_from_rayon():
    body = "<p>Con cafeína, beta alanina y citrulina malato.</p>"
    # rayon « pre-entreno » : ingrédient seul, électrolytes, sirop → exclus
    assert _cats(_p("Arginina, Ornitina y Lisina", "Arginina", body, {"preworkout"})) == []
    assert _cats(_p("Electrolyte Powder (Electrolitos En Polvo)", "Intra-Entrenamiento", body, {"preworkout"})) == []
    assert _cats(_p("Zero Syrup (Sirope Cero)", "Salsas y Siropes", body, {"preworkout"})) == []
    assert _cats(_p("Pre-Entreno Cápsulas")) == []                            # construit : gélules exclues
    assert _cats(_p("Colágeno Booster")) == [("collagene", None)]             # construit : « booster » ≠ pré-workout
    # « sin cafeína » n'exclut PAS (Myprotein : « Origin Pre-Entreno Sin Estimulantes », « … y sin cafeína »)
    assert _cats(_p("Origin Pre-Entreno Sin Estimulantes", "", "<p>Una fórmula práctica y contundente, … y sin cafeína.</p>")) == [("preworkout", None)]
    assert _cats(_p("Pre-Entreno Sin Cafeína")) == [("preworkout", None)]


# --------------------------------------------------------------------------- extraction

EVOLUTION_ISOLATE = ("<p>Evolution Isolate de Amix: proteína aislada con 29 g de proteína por toma</p>"
                     "<p>Proteína (base seca): 29 g por 35 g.</p>"
                     "<p>Mezcla 35 g (1½ cacitos) con 350-400 ml de agua fría o leche desnatada . Utiliza una batidora o shaker "
                     "y mezcla durante 30 segundos. Toma de 1 a 3 dosis al día entre comidas</p>")
PROTEIN_BAR = ("<p>Protein Bar es una barrita proteica de 40g desarrollada por Masmusculo Supplements , diseñada para aportar "
               "proteínas de calidad de forma práctica y sabrosa.</p><p>34-35 g de proteína por cada 100 g</p>")
IMPACT_TABLE = ("<p>Mezcla 30 g (aprox. 1 cacito) con 250 ml de agua o leche y consume 30 minutos antes y/o después del ejercicio.</p>"
                "<table><tr><th>Valores típicos</th><th>Por 100 g</th><th>Por 30 g</th></tr>"
                "<tr><td>Valor energético</td><td>1602 kJ</td><td>481 kJ</td></tr>"
                "<tr><td>Valor energético</td><td>379 kcal</td><td>114 kcal</td></tr>"
                "<tr><td>Grasas</td><td>5,9 g</td><td>1,8 g</td></tr>"
                "<tr><td>de las cuales saturadas</td><td>3,6 g</td><td>1,1 g</td></tr>"
                "<tr><td>Hidratos de carbono</td><td>8,9 g</td><td>2,7 g</td></tr>"
                "<tr><td>de los cuales azúcares</td><td>5,1 g</td><td>1,5 g</td></tr>"
                "<tr><td>Proteínas</td><td>72 g</td><td>22 g</td></tr>"
                "<tr><td>Sal</td><td>0,44 g</td><td>0,13 g</td></tr></table>"
                "<p>Contiene 30 raciones</p>"
                "<p>Ingredientes: Concentrado de proteína de suero de leche (Leche) (96 %) (contiene emulsionantes (lecitina de "
                "Soja, lecitina de girasol)), aroma, edulcorante (sucralosa). Para alérgenos, consulta los ingredientes en negrita.</p>")


def test_protein_per_100g_es():
    ac = extract("whey", IMPACT_TABLE, "Impact Whey Protein", Format(grams=1000), "es")
    assert ac.amount == 72 and ac.source == "regex_table"
    assert extract("whey", IMPACT_TABLE, "Impact Whey Protein", Format(grams=1000)) is None     # français : inchangé
    ac = extract("whey", EVOLUTION_ISOLATE, "Evolution Isolate", Format(grams=2000), "es")
    assert ac.amount == 82.9 and "29 g por 35 g" in ac.evidence
    bar = extract("barres", PROTEIN_BAR, "Protein Bar (Barrita de Proteína)", Format(units=1), "es")
    assert bar.amount == 14.0                                               # 35 g/100 g × barrita de 40 g


def test_serving_es():
    origin_pre = "<p>Tamaño de la ración 20g</p><p>Principios activos</p><p>Por ración diaria</p>"
    assert serving_size("Tamaño de la ración 20g", "es") == 20 and serving_size("Tamaño de la ración 20g") is None
    assert serving_size("En cada servicio de 30 g se incluyen las cantidades indicadas", "es") == 30
    assert serving_size("1 cacito (30 g)", "es") == 30 and serving_size("Una dosis de 30 g al día", "es") == 30
    assert serving_size("cada toma de 6,8 g", "es") == 6.8 and serving_size("por ración (25 g)", "es") == 25
    assert preworkout_serving(origin_pre.replace("<p>", "").replace("</p>", "\n"), "es").amount == 20
    wild_pump = "Disolver 25 g (2 dosificadores) en un vaso de agua (200 ml – 250 ml).\nTomar 1 hora antes del entrenamiento."
    assert preworkout_serving(wild_pump, "es").amount == 25 and preworkout_serving(wild_pump) is None
    ac = extract("preworkout", "<p>Mezclar 20g (aproximadamente 2 cacitos) con 300ml de agua</p>", "Origin", Format(grams=600), "es")
    assert ac.amount == 20


def test_zinc_and_creatine_es():
    ac = extract("zinc", ZINC_LAMBERTS, "Zinc 15mg", Format(units=90), "es")
    assert ac.amount == 15
    crea = ("<p>3 g de creatina monohidrato por servicio , una dosis diaria sencilla de integrar.</p>"
            "<p>Cantidad por servicio: 3 g de creatina monohidrato.</p>")
    assert extract("creatine", crea, "Creatina Monohidrato", Format(grams=500), "es").amount == 100


def test_details_es_nutrition_ingredients_and_instructions():
    d = product_details(IMPACT_TABLE, "Impact Whey Protein", "es")
    assert d["nutrition"] == {"energy_kcal": 379.0, "fat": 5.9, "saturated": 3.6, "carbs": 8.9, "sugars": 5.1,
                              "protein": 72.0, "salt": 0.44}
    assert d["ingredients"].startswith("Concentrado de proteína de suero de leche")
    assert d["attributes"]["sweeteners"] == ["sucralose"] and d["attributes"]["no_sweetener"] is False
    # mode d'emploi pris pour une liste (construit à partir du mode d'emploi réel d'Impact Whey) : rejeté
    instr = "<p>Ingredientes: Mezcla 30 g (aprox. 1 cacito) con 250 ml de agua o leche, y consume 30 minutos antes.</p>"
    assert product_details(instr, "", "es")["ingredients"] is None
    assert product_details(IMPACT_TABLE, "Impact Whey Protein")["nutrition"] is None          # français : inchangé


def test_preworkout_profile_es():
    page = ("<table><tr><th>Principios activos</th><th>Por ración diaria</th></tr>"
            "<tr><td>DL-malato de L-citrulina</td><td>8g</td></tr><tr><td>Beta alanina</td><td>3,5g</td></tr>"
            "<tr><td>L-tirosina</td><td>250mg</td></tr></table>")
    pre = product_details(page, "Origin Pre-Entreno Sin Estimulantes", "es")["attributes"]["preworkout"]
    assert pre["citrulline_malate"]["dose"] == 8 and pre["beta_alanine"]["dose"] == 3.5


def test_format_labels_es():
    f = parse_format("90 Cápsulas")
    assert f.units == 90 and f.unit_word == "capsule"
    assert parse_format("60 comprimidos").units == 60
    assert parse_format("Caja de 12 barritas").units == 12
    assert parse_format("Impact Whey Protein - 900G - 30raciones").grams == 900


# --------------------------------------------------------------------------- livraison offerte, codes

def test_free_shipping_es():
    mp = "Envío Gratis a partir de 55€ + 15% EXTRA para nuevos clientes Calidad al más alto nivel"
    hsn = "Envío gratis en 24/48 horas desde 29,99 € en Península"
    zumub = "ENVÍO GRATIS A PARTIR DE €30 | ENTREGA EN 24 HORAS"
    assert shipping_info(mp, "es")[0] == 55
    assert shipping_info(hsn, "es")[0] == 29.99
    assert shipping_info(zumub, "es")[0] == 30
    assert shipping_info("(3904) Envío gratis +10% Descuento", "es")[0] is None           # « +10% » n'est pas un seuil
    assert shipping_info("Gastos de envío gratis en pedidos superiores a 49,90€.", "es")[0] == 49.9
    assert all(shipping_info(t)[0] is None for t in (mp, hsn, zumub))                      # français : inchangé


def test_promo_codes_es():
    # Pages réelles sans code : rien ne doit être pris pour un code (« código descuento HSN », « botón VALIDAR »…)
    hsn = ("Accede a tu cesta y busca la casilla: '¿Tienes un código descuento HSN?'\n"
           "Pega en esa casilla el código descuento HSN y presiona el botón VALIDAR.\n"
           "Asegúrate que el código HSN ha funcionado.\n"
           "Introduzca el código de 6 dígitos enviado a su cuenta de correo electrónico.")
    zumub = "¡Recibe un código de descuento de €5 en tu primer pedido!"
    mp = "introduce el código en la casilla marcada “Usar código” en la página de la cesta de compra"
    assert extract_codes(hsn, "es") == [] and extract_codes(zumub, "es") == [] and extract_codes(mp, "es") == []
    # Construit (aucun code n'était affiché le 13/11 sur les sites autorisés), sur la formule réelle de Myprotein
    (c,) = extract_codes("Únete a nuestra newsletter y recibe un 15% EXTRA en tu primer pedido con el código BIENVENIDA15", "es")
    assert (c.code, c.value, c.first_order_only) == ("BIENVENIDA15", 15, True)
    (d,) = extract_codes("BLACK FRIDAY: -25% en toda la web con el código BLACK25 en pedidos superiores a 60 €", "es")
    assert d.value == 25 and d.min_order == 60
    (e,) = extract_codes("Cupón descuento: VERANO10 -10% de descuento en proteínas", "es")
    assert e.code == "VERANO10" and e.value == 10
    assert extract_codes("Cupón descuento: VERANO10 -10% de descuento en proteínas") == []   # français : inchangé


# --------------------------------------------------------------------------- origine, avis, rayons

def test_origin_es():
    assert detect_origin(ZINC_LAMBERTS, "Zinc 15mg", "es")[0] == "GB"
    assert detect_origin("<p>Desarrollado y fabricado en Alemania.</p>", "Vegan Omega 3 Gummies", "es")[0] == "DE"
    assert detect_origin("<p>Fabricado en España</p>", "", "es")[0] == "ES"
    assert detect_origin("<p>Made in Spain</p>", "", "es")[0] == "ES"
    # matière première, pas le produit : « Creapure® , una materia prima producida en Alemania por AlzChem »
    creapure = ("<p>Creatina (Creapure®) de LifePRO es un complemento alimenticio en polvo elaborado principalmente con "
                "creatina monohidrato Creapure® , una materia prima producida en Alemania por AlzChem Trostberg GmbH.</p>")
    assert detect_origin(creapure, "Creatina (Creapure®)", "es") == (None, None)
    assert detect_origin("<p>No está fabricado en España</p>", "", "es") == (None, None)
    assert detect_origin(ZINC_LAMBERTS, "Zinc 15mg") == (None, None)                        # français : inchangé


def test_review_topics_es():
    # Construit : avis Judge.me en espagnol
    rev = ('<div class="jdgm-rev" data-score="5"><div class="jdgm-rev__body">Muy rico el sabor a chocolate. Se mezcla muy bien, sin grumos.</div></div>'
           '<div class="jdgm-rev" data-score="2"><div class="jdgm-rev__body">El sabor es demasiado dulce y me provoca hinchazón.</div></div>'
           '<div class="jdgm-rev" data-score="4"><div class="jdgm-rev__body">Buen sabor y se disuelve rápido en el shaker.</div></div>')
    t = review_topics(rev, "es")["topics"]
    assert t["Goût"]["mentions"] == 3 and t["Mélange"]["mentions"] >= 2


def test_rayons_keywords_es():
    kw = keywords("es")
    import re
    assert re.search(kw["preworkout"], "Pre-entrenos", re.I) and re.search(kw["creatine"], "creatina", re.I)
    assert re.search(kw["barres"], "barritas-proteicas", re.I) and re.search(kw["glutamine"], "Glutamina", re.I)
    assert not_a_rayon("https://www.hsnstore.com/blog/nutricion", "es")
    assert not_a_rayon("https://x.es/salud-sexual/testosterona", "es") and not_a_rayon("https://x.es/sueno-y-descanso", "es")
    assert not not_a_rayon("https://x.es/nutricion-deportiva/pre-entrenos", "es")
    assert keywords("fr") is keywords()                                                    # français : inchangé


# --------------------------------------------------------------------------- base : pays, top 50 par pays

def _engine(tmp_path):
    from dosehunt import db
    from dosehunt.pipeline import seed
    e = db.get_engine(f"sqlite:///{tmp_path}/es.db")
    db.init_db(e)
    seed(e)
    return e


def test_seed_inserts_all_countries_and_site_country(tmp_path):
    from sqlalchemy import select
    from dosehunt import db
    e = _engine(tmp_path)
    with e.connect() as conn:
        rows = {r.code: r for r in conn.execute(select(db.countries))}
        assert rows["FR"].vat_rate == 0.2 and rows["FR"].language == "fr"
        assert rows["ES"].currency == "EUR" and rows["ES"].vat_rate == 0.1 and rows["ES"].language == "es"
        s = conn.execute(select(db.sites).where(db.sites.c.id == "myprotein-es")).mappings().one()
        assert s["country"] == "ES" and s["language"] == "es"
        dom = conn.execute(select(db.site_domains).where(db.site_domains.c.site_id == "myprotein-es")).mappings().all()
        assert [d["country"] for d in dom] == ["ES"]


def test_top_product_urls_is_per_country(tmp_path):
    from dosehunt import db
    from dosehunt.pipeline import top_product_urls
    e = _engine(tmp_path)
    now = datetime.now(timezone.utc)
    with e.begin() as conn:
        for i, (site, country, value) in enumerate([("myprotein", "FR", 10.0), ("myprotein-es", "ES", 30.0)], start=1):
            conn.execute(db.products.insert().values(id=i, site_id=site, external_id=str(i), name="Whey", url=f"https://{country}/p/{i}"))
            conn.execute(db.offers.insert().values(id=i, product_id=i, site_id=site, country=country, variant_id=str(i),
                                                   price=20, available=True, active=True))
            conn.execute(db.index_rows.insert().values(offer_id=i, category="whey", subcategory="classique", country=country,
                                                       dose_value=value, computed_at=now))
    # le produit espagnol est 1er en Espagne même si l'offre française est moins chère
    assert top_product_urls(e, "myprotein-es", 1) == ["https://ES/p/2"]
    assert top_product_urls(e, "myprotein", 1) == ["https://FR/p/1"]
