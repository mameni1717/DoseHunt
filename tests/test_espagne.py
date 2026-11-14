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


# --------------------------------------------------------------------------- 14/11 : première collecte espagnole
# Extraits RÉELS relevés le 14/11/2026 avec le robot DoseHunt (robots.txt respecté, une requête toutes les 2,5 s) :
# masmusculo.com (products.json, pages 1 à 4), myprotein.es, bulk.com/es et sunday-natural.es (fiches citées).

def test_intruders_es_masmusculo_titles():
    # « booster » seul ne fait pas un pré-workout ; testostérone, thyroïde, thermogénique : exclus (titres et types réels)
    for title, ptype in [("TestoXT Booster", "Complejos Testosterona"), ("Testosterone Booster", "Complejos Testosterona"),
                         ("Thyro Booster", "Otros Quemadores"), ("ThermoLean Booster", "Termogénicos"), ("Tribooster", "Tribulus")]:
        assert _cats(_p(title, ptype)) == [], title
    # mélanges testostérone / sommeil : ni zinc, ni magnésium
    assert _cats(_p("Tribulus + Zinc", "Tribulus")) == []
    assert _cats(_p("Tribulus y ZMA", "Tribulus")) == []
    assert _cats(_p("Triptófano con Melatonina + Magnesio y Vit B6", "Mejora del sueño")) == []
    assert _cats(_p("Triptófano con Magnesio y Vitamina B6", "Mejora del sueño", "", {"magnesium"})) == []   # via rayon aussi
    # gummies, petit-déjeuner, EAA
    assert _cats(_p("Vegan Gummy Bar BCAAs", "Barritas de Carbohidratos")) == []
    assert _cats(_p("Protein Breakfast", "Proteina de Suero Whey")) == []
    assert _cats(_p("Premium EAA + Glutamina", "Esenciales e Hidrolizados")) == []
    # une protéine « con creatina » reste une protéine (Myprotein « Origin Protein (con Creatina) »)
    assert _cats(_p("Origin Protein (con Creatina)", "", "", {"whey"})) == [("whey", "classique")]
    # ZMA reste zinc + magnésium, comme en France ; « Sweet Dream » (BIG) est une caséine micellaire : gardée
    assert _cats(_p("ZMA", "ZMA")) == [("zinc", None), ("magnesium", None)] == _cats(_p("ZMA", "ZMA"), FR)
    assert _cats(_p("Sweet Dream", "Caseina")) == [("whey", "caseine")]
    # un « booster » dont la description cite un actif typique reste un pré-workout (construit)
    assert _cats(_p("Nitro Booster", "", "<p>Con 200 mg de cafeína y 6 g de citrulina.</p>")) == [("preworkout", None)]
    # règles françaises inchangées
    assert _cats(_p("TestoXT Booster", "Complejos Testosterona"), FR) == [("preworkout", None)]
    assert _cats(_p("Tribulus + Zinc", "Tribulus"), FR) == [("zinc", None)]


ON_CREATINA_POLVO = ("<p>La Creatina en Polvo de Optimum viene en un bote de 317 g.</p>"
                     "<p>Cada dosis recomendada de 3,6 g de creatina provee 3,6 g de creatina monohidrato .</p>"
                     "<p>Dosis diaria recomendada de la Creatina en Polvo</p><p>Diluir 3,6 g (1 medidor al ras) en un vaso con agua.</p>")
ON_MICRONIZADA = ("<p>La toma diaria indicada aporta 3 g de creatina .</p><p>Aporta 3 g de creatina por toma diaria .</p>"
                  "<p>Cada toma diaria indicada proporciona 3,4 g de monohidrato de creatina, equivalentes a 3 g de creatina .</p>"
                  "<p>Mezclar 3,4 g con 240 ml de agua fría y remover hasta que se haya disuelto completamente. Tomar 3,4 g al día.</p>")
VITOBEST_PREMIUM = ("<p>3 g de creatina por dosis recomendada.</p><p>Una ingesta diaria de 3 g de creatina mejora el rendimiento "
                    "físico en series sucesivas de ejercicios breves de alta intensidad. (*)</p>")


def test_creatine_es_serving_claims_and_tablets():
    ac = extract("creatine", ON_CREATINA_POLVO, "Creatina en Polvo", Format(grams=317), "es")
    assert ac.amount == 100 and "3,6 g de creatina" in ac.evidence
    assert extract("creatine", ON_CREATINA_POLVO, "Creatina en Polvo", Format(grams=317)) is None     # français : inchangé
    # créatine comptée en monohydrate (3,4 g pour une dose de 3,4 g), jamais « 3 g de creatina » (base) ni l'allégation
    assert extract("creatine", ON_MICRONIZADA, "Creatina Micronizada", Format(grams=300), "es").amount == 100
    assert serving_size("Una ingesta diaria de 3 g de creatina", "es") is None
    # « 3 g de creatina por dosis recomendada » sans poids de dose : rien (l'allégation « ingesta diaria de 3 g » ne compte pas)
    assert extract("creatine", VITOBEST_PREMIUM, "Creatina Premium (Cr-Ystalpure®)", Format(grams=500), "es") is None
    # comprimés : grammes de monohydrate par dose (Optimum Nutrition, masmusculo)
    on_tabs = ("<p>3,0 g de monohidrato de creatina por cada 3 comprimidos.</p><p>De esa cantidad, 2,6 g corresponden a creatina .</p>"
               "<p>Tomar 3 comprimidos al día.</p>")
    ac = extract("creatine", on_tabs, "Creatina Monohidrato en tabletas", Format(units=180), "es")
    assert ac.amount == 1000 and ac.units_per_dose == 3
    on_2500 = ("<p>Especificaciones por dosis (2 cápsulas):</p><p>Tiene 2,5 gr de monohidrato de creatina, de los cuales 2,2 gr "
               "son de creatina</p><p>Se recomienda consumir 2 cápsulas al día</p>")
    assert extract("creatine", on_2500, "Creatina 2500", Format(units=200), "es").amount == 1250
    # Myprotein, tableau : « Tamaño de la Ración - 3 Pastillas » + « Monohidrato de Creatina | | | 3 g »
    mp_tabs = ("<p>1. La creatina mejora el rendimiento físico en ejercicios de ráfagas cortas y alta intensidad. Los efectos "
               "beneficiosos se obtienen con una ingesta diaria de 3 g de creatina.</p><p>Tamaño de la Ración - 3 Pastillas</p>"
               "<p>Raciones Por Envase - 83 (250 Pastillas)</p><table><tr><td>Valores nutricionales típicos</td><td>Por Porción</td></tr>"
               "<tr><td>Monohidrato de Creatina</td><td></td><td></td><td>3 g</td></tr></table>")
    ac = extract("creatine", mp_tabs, "Creatina Monohidrato en Tabletas", Format(units=250), "es")
    assert ac.amount == 1000 and "| 3 g" in ac.evidence
    # Myprotein, sachets « 20 x 6.8g » : de la poudre, pas 20 gélules de 3 000 mg
    sobres = ("<p>Tamaño de la ración: 3,4g</p><p>Raciones por envase: 2</p><table><tr><td>Principios activos</td></tr>"
              "<tr><td>Por ración diaria</td><td>3,4g</td></tr><tr><td>Monohidrato de creatina (Creapure®)</td><td>3,4g</td></tr>"
              "<tr><td>del cual creatina</td><td>3g</td></tr></table>")
    fmt = parse_format("THE Creatine (Creapure) |Sobres monodosis 20 x 6.8g Sin Sabor")
    assert fmt.units == 20 and fmt.unit_grams == 6.8
    assert extract("creatine", sobres, "THE Creatine (Creapure) |Sobres monodosis", fmt, "es").amount == 100
    # Bulk « Creatina Monohidratada » (tailles « 100 / 250 / 500 / 1000 ») : monohydrate pur supposé, comme en France
    ac = extract("creatine", "<p>Compra Creatina Monohidratada 99,99 % pura en polvo al precio más bajo en España.</p>",
                 "Creatina Monohidratada", Format(grams=500), "es")
    assert ac.amount == 100 and ac.source == "assumed"
    assert serving_size("Mezclar 1 medidas (aproximadamente 3,4 g) con 200 ml de agua", "es") == 3.4     # Bulk Creapure


def test_protein_per_serving_es_masmusculo():
    stacker = ("<p>Whey Isolate de Stacker2 viene en un envase con 750 gr de preparado alimenticio en polvo.</p>"
               "<p>Especificaciones por dosis (30 gr, sabor chocolate), los valores varían según el sabor:</p>"
               "<p>Tiene un valor energético de 119 Kcal</p><p>Posee 27 gr de proteínas</p><p>Tiene 0,06 gr de sal</p>"
               "<p>Mezclar 1 cucharada (30 gr) con 200 ml de agua fría y tomar de 2 a 3 veces al día</p>")
    assert extract("whey", stacker, "Whey Isolate", Format(grams=750), "es").amount == 90
    beverly = ("<p>Caseína micelar aislada: aporta 27,3 g de proteínas por servicio.</p>"
               "<p>Mezclar 1 scoop de proteína (35 g) en agua, leche o bebida vegetal y tomar después del entrenamiento.</p>")
    assert extract("whey", beverly, "Caseína Micellar", Format(grams=1000), "es").amount == 78
    biotech = ("<p>Aporta 23 gramos de proteína por cada porción.</p><p>Uso recomendado : Como complemento alimenticio se debe "
               "mezclar 30 gramos del producto o 1 porción en 300 mililitros de agua o leche descremada.</p>")
    assert extract("whey", biotech, "Protein Power", Format(grams=1000), "es").amount == 76.7
    assert extract("whey", biotech, "Protein Power", Format(grams=1000)) is None                       # français : inchangé


def test_zinc_omega_vitd_es_masmusculo():
    zmag = ("<p>Aspectos esenciales del ZMAG de Vitobest por 2 cápsulas</p><p>Aporta 30 mg de zinc monometionina</p>"
            "<p>Con 5.98 mg de zinc elemental</p><p>Tiene 450 mg de magnesio aspartato</p><p>Contiene 66.98 mg de magnesio elemental</p>"
            "<p>Se recomienda tomar 2 cápsulas al día de este producto, entre unos 30 a 60 minutos antes de ir a dormir</p>")
    assert extract("zinc", zmag, "ZMA", Format(units=100), "es").amount == 2.99          # 30 mg = poids du sel (monométhionine)
    assert extract("magnesium", zmag, "ZMA", Format(units=100), "es").amount == 33.49
    amix = "<p>Presenta 15 mg de zinc elemental por cápsula</p><p>La dosis diaria recomendada es de 1 cápsula al día</p>"
    assert extract("zinc", amix, "Zinc Bisglicinato", Format(units=90), "es").amount == 15
    # l'allégation « ingesta de 250mg de EPA y DHA » n'est pas une teneur
    mm_omega = ("<p>* (El efecto beneficioso se obtiene con una ingesta de 250mg de EPA y DHA)</p><p>Posee una composición a base "
                "de ingredientes naturales y que proporciona 12% de DHA (ácido docosahexaenoico) y 18% de EPA</p><p>Tomar 3 softgel al día.</p>")
    assert extract("omega3", mm_omega, "Omega 3", Format(units=120), "es") is None
    d3 = "<p>Vitamina D3: 50µg por cápsula (1000% VRN).</p><p>Vitamina K2: 75µg por cápsula (100% VRN).</p>"
    assert extract("vitamine_d", d3, "Vitamina D3 + K2 (50μg/75μg)", Format(units=60), "es").amount == 2000
    ultra = "<p>Vitamina D (colecalciferol)</p><p>Tomar 1 cápsula al día acompañada de agua preferiblemente antes de comer.</p>"
    assert extract("vitamine_d", ultra, "Vitamina D3 + K2 (100Μg/150Μg)", Format(units=240), "es").amount == 4000
    assert extract("vitamine_d", ultra, "Vitamina D3 + K2 (100Μg/150Μg)", Format(units=240)) is None   # français : inchangé


def test_servings_es_myprotein_masmusculo():
    mezcla = ("<p>150 mg de cafeína por ración</p><p>Tamaño por ración - 1 cucharada (11.5 g)</p>"
              "<p>Raciones por envase - 22 (250 g), 43 (500 g)</p>")
    assert extract("preworkout", mezcla, "Mezcla Pre-Entreno", Format(grams=250), "es").amount == 11.5
    assert extract("preworkout", mezcla, "Mezcla Pre-Entreno", Format(grams=250)) is None
    vitobest = "<p>Cantidad recomendada: 25 g mezclados en 250 ml de agua</p><p>Momento de consumo: Antes del ejercicio</p>"
    assert extract("preworkout", vitobest, "Pre Training", Format(grams=500), "es").amount == 25
    glut = ("<p>SIN SABOR</p><p>Tamaño de la ración - 5g</p><p>Raciones por envase - 200 raciones (1kg)</p>"
            "<table><tr><td>Principios activos</td><td>Por ración diaria</td></tr><tr><td>L-glutamina</td><td></td><td>5,0g</td></tr></table>")
    assert extract("glutamine", glut, "L-Glutamina en polvo", Format(grams=1000), "es").amount == 100
    glut_tabs = ("<p>Tamaño de la Ración - 3 Pastillas</p><p>Raciones Por Envase - 83 (250 Pastillas)</p>"
                 "<table><tr><td>Valores nutricionales típicos</td><td>Por Porción</td></tr>"
                 "<tr><td>L Glutamina</td><td></td><td></td><td>3 g</td></tr></table>")
    assert extract("glutamine", glut_tabs, "L-glutamina Comprimidos", Format(units=250), "es").amount == 1000
    # « Consumir 3 pastillas al día » ne divise pas la teneur du titre (Lamberts « Vitamina C 1500mg ») : seulement « Tamaño de la ración »
    lamberts = ("<p>Vitamina C 1500 mg con bioflavonoides</p><p>Uso recomendado : Consumir 3 pastillas al día. La primera en la "
                "mañana, otra en la tarde y la última antes de dormir.</p>")
    assert extract("vitamine_c", lamberts, "Vitamina C 1500mg con Bioflavonoides", Format(units=100), "es").amount == 1500


def test_sunday_natural_es_tables_and_contents():
    from dosehunt.extract import content_from_text
    luxe = ("<p>Modo de empleo: tomar 4 cápsulas al día con 200 ml de agua</p><table><tr><td>4 cápsulas</td><td>%N% VRN*</td></tr>"
            "<tr><td>Hidrolizado de colágeno (de vacuno)</td><td>2000 mg</td><td>**</td></tr></table>")
    ac = extract("collagene", luxe, "Colágeno SunGlow® Luxe", Format(units=120), "es")
    assert ac.amount == 500 and ac.source == "regex_table"
    assert extract("collagene", luxe, "Colágeno SunGlow® Luxe", Format(units=120)) is None              # français : inchangé
    pure = ("<p>Térmicamente estable: ideal para mezclar con café caliente, sin desnaturalización, sin pérdida de ingredientes, pleno "
            "disfrute</p><p>Ingredientes</p><p>Hidrolizado de colágeno¹ (de vacuno).</p>"
            "<table><tr><td>Valores nutricionales</td><td>por cada 100 g de polvo</td><td>por ración (10 g)</td></tr>"
            "<tr><td>Proteínas</td><td>92 g</td><td>9,2 g</td></tr></table>")
    assert extract("collagene", pure, "Colágeno en polvo SunGlow® Pure", Format(grams=450), "es").amount == 92
    glut = ("<p>3000 mg de L-glutamina por 4 cucharas de medición</p><p>Tomar 4 cucharas de medición al día (aprox. 3 g de "
            "L-glutamina) con 200 ml de agua antes de las comidas.</p><table><tr><td>4 cucharas de medición (3 g)</td><td>% VRN*</td></tr>"
            "<tr><td>L-glutamina</td><td>3000 mg</td><td>-**</td></tr></table>")
    assert extract("glutamine", glut, "L-glutamina de fermentación en polvo, vegana", Format(grams=300), "es").amount == 100
    assert content_from_text("<p>Hidrolizado de colágeno 100 % puro ✓ 450 g de polvo ✓ Sin aditivos</p>", "es") == (450, None)
    assert content_from_text("<p>VITAMINA D3 + K2 MK7 TODO-TRANS 2500 UI + 100 µg x 300 gotas. Alta dosis</p>", "es") == (None, 300)
    assert content_from_text("<p>450 g de polvo</p>") == (None, None)                                 # français : inchangé


def test_bulk_es_sku_formats():
    from dosehunt.collectors.page import variants_from_jsonld
    rx = get_site("bulk-es").filters["sku_format"]
    node = {"@type": "Product", "name": "Caseína Micelar", "offers": [
        {"@type": "Offer", "sku": "BPB-MCAS-CHOC-0500-V2", "price": 21.99, "availability": "InStock"},
        {"@type": "Offer", "sku": "HERO-PBAR-CCAR-BX12", "price": 29.99, "availability": "InStock"},
        {"@type": "Offer", "sku": "HERO-PBAR-CCAR-0050", "price": 2.79, "availability": "InStock"}]}
    titles = [v.title for v in variants_from_jsonld(node, [node], "https://www.bulk.com/es/products/x", rx)]
    assert titles == ["500", "Pack de 12", "50"]
    # l'entrée française garde sa règle
    assert [v.title for v in variants_from_jsonld(node, [node], "u", get_site("bulk").filters["sku_format"])][2] == "50"
