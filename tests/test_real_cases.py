"""Cas relevés lors du premier vrai relevé (11/11/2026), gardés pour qu'ils ne reviennent pas."""
from dosehunt.extract import content_from_text, extract
from dosehunt.formats import parse_format
from dosehunt.models import Format

ZMA = ("<table><tr><th>Ingrédient</th><th>Pour 2 gélules</th><th>AR*</th></tr>"
       "<tr><td>Magnésium</td><td>300 mg</td><td>80 %</td></tr><tr><td>L-Arginine</td><td>500 mg</td></tr>"
       "<tr><td>Zinc</td><td>15 mg</td><td>150 %</td></tr><tr><td>Vitamine B6</td><td>1,4 mg</td><td>100 %</td></tr></table>")


def test_zma_table_header_dose_and_no_cross_row_reading():
    # Toutelanutrition : « L-Arginine | 500 mg » suivi de « Zinc » ne doit pas donner 500 mg de zinc
    assert extract("zinc", ZMA, "ZMA", Format(units=60)).amount == 7.5
    assert extract("magnesium", ZMA, "ZMA", Format(units=60)).amount == 150


def test_per_serving_table_is_not_read_as_per_100g():
    # Whey HT : tableau par portion seulement ; « jusqu'à 78 % de protéines » dans le texte
    body = ("<p>Elle contient jusqu’à 78% de protéines.</p><table><tr><td>Glucides</td><td>4,2 g</td></tr>"
            "<tr><td>Protéines sur matière sèche</td><td>22,5 g</td></tr><tr><td>Protéines sur matière humide</td><td>21 g</td></tr></table>")
    assert extract("whey", body, "Whey HT", Format(grams=750)).amount == 78


def test_magnesium_element_in_table_with_salt():
    body = "<table><tr><td>Bisglycinate de magnésium Albion™</td><td>1500 mg dont magnésium élément</td><td>270 mg</td></tr></table><p>Dose journalière : 3 gélules.</p>"
    ac = extract("magnesium", body, "Magnésium bisglycinate 1500mg", Format(units=90))
    assert ac.amount == 90


def test_format_only_in_description_and_durations():
    assert content_from_text("<p>Pot de 750 g, soit 25 portions</p>") == (750.0, None)
    assert parse_format("15 jours").months == 0.5


def test_bar_single_protein_mention():
    ac = extract("barres", "<p>Une barre croustillante : 22,9 g de protéines, 9,2 g de fibres.</p>", "Crousti - 12 Barres", Format(units=12))
    assert ac.amount == 22.9 and ac.confidence < 0.8


def test_eafit_collagen_per_serving_table():
    body = ("<table><tr><th>Actifs</th><th>Par portion journalière (10 g)</th></tr>"
            "<tr><td>Hydrolysat de collagène</td><td>10 g</td></tr><tr><td>Glycine</td><td>2,5 g</td></tr></table>")
    assert extract("collagene", body, "Collagène bovin hydrolysé EAFIT - Poudre", Format(grams=300)).amount == 100


def test_bulk_sku_with_country_suffix():
    import re
    from dosehunt.config import get_site
    rx = re.compile(get_site("bulk").filters["sku_format"])
    assert rx.search("BPB-CMON-0000-0500-EU").group("size") == "0500"
    assert rx.search("BPB-PWPC-CHOC-0450").group("size") == "0450"


def test_percent_of_whey_origin_is_not_protein_content():
    body = "<p>composée à 100% de protéines de lactosérum. Elle contient 78 % de protéines.</p>"
    assert extract("whey", body, "100% Pure Whey", Format(grams=1000)).amount == 78
    assert extract("whey", "<p>composée à 100% de protéines de lactosérum</p>", "x", Format(grams=1000)) is None


def test_format_from_url_slug_and_veg_caps():
    from dosehunt.formats import url_words
    w = url_words("https://www.ericfavre.com/fr_fr/x/iso-zero-100-whey-proteine-chocolat-au-lait-1-5kg-p-194-o-1616.htm")
    assert parse_format(w).grams == 1500
    assert parse_format("120 veg caps").units == 120


def test_header_without_label_cell_eafit():
    body = ("<table><tr><th>Pour 100g</th><th>Par shaker (30g)</th></tr>"
            "<tr><td>Énergie</td><td>353 kcal</td><td>106 kcal</td></tr>"
            "<tr><td>Protéines</td><td>83 g</td><td>25 g</td></tr></table>")
    assert extract("whey", body, "Pure Isolate Protein Premium", Format(grams=750)).amount == 83
    assert extract("barres", body.replace("shaker (30g)", "barre (60g)"), "Barre", Format(units=1)).amount == 25


def test_anomalies_found_in_top_rankings():
    from dosehunt.checks import check_format, check_active
    from dosehunt.models import ActiveContent
    # Myprotein « 30portions » sans poids : une poudre exige un poids
    assert check_format(parse_format("THE Whey 30portions Pistache"), "per_100g")
    # Bulk « 48 » (référence) : une barre de 48 g, pas 48 barres
    f = parse_format("48")
    assert f.grams == 48 and f.units is None
    # Oméga-3 : 1 120 mg d'EPA + DHA par capsule est irréaliste
    assert check_active(ActiveContent("omega3", "epa_dha", 1120, "mg", "per_unit", "regex_text", 0.9))


def test_format_hint_from_page_nutriandco():
    from dosehunt.collectors.base import format_hint
    page = ("<li>900g - 30 portions</li><li>900g - 30 portions</li><li>900g - 30 portions (1 mois)</li>"
            "<p>Achat en lot 3 x 900g</p><table><tr><td>Pour 30g (une portion)</td><td>Pour 100g</td></tr></table>")
    assert format_hint(page) == "900 g"
    assert format_hint("<p>Pilulier de 120 gélules</p><td>Pour 2 gélules</td>") == "120 gélules"
    assert format_hint("<td>Pour 30g</td><td>Pour 100g</td>") is None


def test_eafit_div_table_converted():
    from dosehunt.collectors.page import divtables_to_tables, zone_html
    from dosehunt.extract import extract
    from dosehunt.models import Format
    page = ('<main><h2>INFORMATIONS NUTRITIONNELLES</h2><div id="resp-table"><div id="resp-table-header">'
            '<div class="table-header-cell"> </div><div class="table-header-cell">Pour 100 g</div>'
            '<div class="table-header-cell">AR*</div><div class="table-header-cell">Par dose de 40 g</div></div>'
            '<div class="resp-table-row"><div class="table-body-cell">Énergie</div><div class="table-body-cell">405 kcal</div>'
            '<div class="table-body-cell">/</div><div class="table-body-cell">162 kcal</div></div>'
            '<div class="resp-table-row"><div class="table-body-cell">Protéines</div><div class="table-body-cell">75 g</div>'
            '<div class="table-body-cell">/</div><div class="table-body-cell">30 g</div></div></div>'
            '<div class="grid"><div class="text-center">Livraison offerte dès 49€</div></div></main>')
    conv = divtables_to_tables(page)
    assert conv.count("<table>") == 1 and conv.count("<tr>") == 3 and '<div class="grid">' in conv
    assert extract("whey", zone_html(conv), "Pure Whey", Format(grams=850)).amount == 75


def test_bar_counts_lot_and_x():
    from dosehunt.formats import parse_format
    assert parse_format("Barre Protéinée Noix & Caramel Lot de 24").total_units == 24
    assert parse_format("La Barre Fit x 32  Chocolat").total_units == 32
    assert parse_format("Lot de 2 – Zinc 60 gélules").total_units == 120
    assert parse_format("Boite de 20 barres de 70g").total_grams == 1400


def test_tln_serving_only_table_and_zma_header_dose():
    from dosehunt.extract import extract
    from dosehunt.models import Format
    whey = ('<table><tr><td>Ingrédient</td><td>Pour 30g</td></tr><tr><td>Protéines sur matière sèche</td><td>25,5 g</td></tr>'
            '<tr><td>Protéines sur matière humide</td><td>24,6 g</td></tr></table>')
    assert extract("whey", whey, "Pure Isolate TLN", Format(grams=900)).amount == 82
    zma = ("<p>150% d'apport de référence de zinc</p><p>2mg</p><p>de vitamine B6</p><table><tr><td>Ingrédient</td>"
           "<td>Pour 3 comprimés</td><td>AR*</td></tr><tr><td>Magnésium</td><td>300 mg</td><td>80 %</td></tr>"
           "<tr><td>Zinc</td><td>15 mg</td><td>150 %</td></tr></table>")
    assert extract("zinc", zma, "ZMA TLN", Format(units=90)).amount == 5
    assert extract("magnesium", zma, "ZMA TLN", Format(units=90)).amount == 100


def test_optigura_data_label_serving_header():
    from dosehunt.collectors.page import datalabel_headers, zone_html
    from dosehunt.extract import extract
    from dosehunt.models import Format
    page = ('<main><table><tbody><tr><td data-label="Valeurs pour 30g"><span>Glucides</span></td><td data-label=""> 1.4g </td>'
            '<td data-label="% AR">-</td></tr><tr><td data-label="Valeurs pour 30g"><span>Protéines</span></td>'
            '<td data-label=""> 24g </td><td data-label="% AR"> 48%</td></tr></tbody></table></main>')
    assert extract("whey", zone_html(datalabel_headers(page)), "Gold Standard", Format(grams=908)).amount == 80


def test_dose_inferred_from_title_and_salt_cap():
    from dosehunt.extract import extract
    from dosehunt.formats import url_words, parse_format
    from dosehunt.models import Format
    c = extract("magnesium", "<p>Chaque dose apporte 225 mg de magnésium.</p>", "Citrate de magnésium 112,5mg", Format(units=240))
    assert c.amount == 112.5 and c.units_per_dose == 2 and c.salt_label_mg is None
    m = extract("magnesium", "<p>346,5mg de magnésium élémentaire par dose journalière.</p>", "Magnesium malate 1000mg", Format(units=120))
    assert m.confidence < 0.55                            # part en revue
    assert parse_format(url_words("https://www.nutripure.fr/fr/musculation/334-barre-proteinee.html")).units is None


def test_nutriandco_omega_header_three_capsules():
    from dosehunt.extract import extract
    from dosehunt.models import Format
    t = ('<table><tr><td>Eléments</td><td>Pour 3 Capsules</td><td>Pour 6 Capsules</td></tr><tr><td>Huile de poissons</td>'
         '<td>1500 mg</td><td>3000 mg</td></tr><tr><td>• dont EPA</td><td>150 mg</td><td>300 mg</td></tr>'
         '<tr><td>• dont DHA</td><td>750 mg</td><td>1500 mg</td></tr></table>')
    assert extract("omega3", t, "Oméga-3", Format(units=60)).amount == 300


def test_bar_per100_value_in_per_bar_column_is_converted():
    from dosehunt.extract import extract
    from dosehunt.models import Format
    t = "<table><tr><td>Valeurs</td><td>Par barre</td></tr><tr><td>Protéines</td><td>35 g</td></tr></table>"
    ac = extract("barres", t, "Crush Protein Bar - 45 g", Format(units=1, unit_grams=45))
    assert ac.amount == 15.8 and ac.confidence == 0.75


# --- relevé du 12/11/2026 : produits bon marché passés à la trappe -------------------------------

def test_zumub_creatine_table_header_without_leading_cell_and_note():
    body = ("<table><tr><td>Pour 3 g</td><td>% Valeur quotidienne</td></tr></table>"
            "<p>La taille de la portion peut varier.</p>"
            "<table><tr><td>Monohydrate de créatine</td><td>3 g</td><td>*</td></tr></table>")
    ac = extract("creatine", body, "Créatine", parse_format("Créatine 1 kg"))
    assert ac and ac.amount == 100


def test_flavoured_and_plain_tables_keep_plain_version():
    body = ("<table><tr><th></th><th>Pour 3,5 g</th><th>AR</th></tr><tr><td>Créatine</td><td>3 g</td></tr></table>"
            "<table><tr><th></th><th>Pour 3 g</th><th>AR</th></tr><tr><td>Créatine</td><td>3 g</td></tr></table>")
    assert extract("creatine", body, "Créatine", parse_format("1 kg")).amount == 100


def test_serving_table_in_mg():
    body = ("<table><tr><th></th><th>Pour 4.6 g</th><th>AR %*</th></tr>"
            "<tr><td>Protéines</td><td>0 g</td><td>-</td></tr>"
            "<tr><td>Créatine monohydrate</td><td>3400 mg</td><td>-</td></tr></table>")
    assert extract("creatine", body, "Micronized Creatine", parse_format("300g")).amount == 73.9


def test_valeurs_pour_30g_header():
    body = ("<table><tr><td>Valeurs pour 30g</td><td></td><td>% AR</td></tr>"
            "<tr><td>Protéines</td><td>24g</td><td>48%</td></tr></table>")
    assert extract("whey", body, "Gold Standard", parse_format("2000g")).amount == 80


def test_reference_intake_percentage_is_not_protein_content():
    body = "<p>2%</p><p>Protéines</p><p>Avec 20g de protéines par dose.</p>"
    assert extract("whey", body, "100% Pure Whey", parse_format("1000g")) is None


def test_collagen_peptides_use_protein_content():
    body = "<p>90% de protéines par portion</p><p>Ingrédients : peptides de collagène bovin</p>"
    ac = extract("collagene", body, "Peptides de Collagène PEPTAN®", parse_format("300 g"))
    assert ac and ac.amount == 90


def test_json_nutrition_metafields_and_template_tables():
    from dosehunt.collectors.page import with_nutrition_tables
    page = ('<script>{"info_diet": {"dosage":"Pour 100 g","detail_nutritionnel":['
            '{"title":"Energie","value":"374","unit":"kcal"},{"title":"Protéines","value":"76","unit":"g"}]}}</script>')
    assert extract("whey", with_nutrition_tables("<p>Gold Standard</p>", page), "Gold Standard", parse_format("2kg")).amount == 76
    page2 = ('<template><table><tr><th>Nutriments</th><th>Par dose</th><th>Pour 100 g</th></tr>'
             '<tr><td>Protéines</td><td>24 g</td><td>81g</td></tr></table></template>')
    assert extract("whey", with_nutrition_tables("<p>Native</p>", page2), "Native whey", parse_format("2Kg")).amount == 81


def test_dose_weight_and_active_per_dose_in_text():
    body = "<p>Une portion : 4.1 g</p><p>Rocky Athletes Creatine contient par portion : 3 g de Créatine, 57,8 mg de Magnésium</p>"
    ac = extract("creatine", body, "Rocky Athletes Creatine (200g)", parse_format("200g"))
    assert ac and ac.amount == 73.2


def test_thousands_with_space_in_table():
    body = ("<p>Une portion : 4.1 g</p><table><tr><td>Pour 4.1 g</td><td>AR %*</td></tr>"
            "<tr><td>Créatine monohydrate - Créatine</td><td>3 400 mg 3 000 mg</td><td>- -</td></tr></table>")
    assert extract("creatine", body, "Rocky Athletes Creatine", parse_format("200g")).amount == 82.9


def test_protein_per_dose_text():
    body = "<p>Dose : 30g</p><p>Chaque shaker apporte 24 g de protéines.</p>"
    assert extract("whey", body, "Whey X", parse_format("1kg")).amount == 80


def test_par_dose_header_uses_dose_size_found_elsewhere():
    from dosehunt.collectors.page import with_nutrition_tables
    page = ("<div>Taille de la dose : 1 doseur de 25ml (10g)</div>"
            "<table><tr><th>Quantité de nutriments</th><th>Par dose</th><th>Par dose journalière</th></tr>"
            "<tr><td>Collagène bovin hydrolysé</td><td>10000 mg</td><td>10000 mg</td></tr></table>")
    body = with_nutrition_tables(page, page)
    assert extract("collagene", body, "Collagène hydrolysé (bovin) en poudre", parse_format("1Kg")).amount == 100


def test_origin_detection():
    from dosehunt.origin import detect_origin
    assert detect_origin("<p>Fabriqué en France par Peptan® 🇫🇷</p>")[0] == "FR"
    assert detect_origin("<p>Conçue et fabriquée en France</p>")[0] == "FR"
    assert detect_origin("<table><tr><td>Pays de fabrication</td><td>France</td></tr></table>")[0] == "FR"
    assert detect_origin("<p>Conçu en France, fabriqué en Italie</p>")[0] == "IT"
    for no in ("<p>Marque française</p>", "<p>Lait d'origine France</p>", "<p>Fabriqué en Europe</p>",
               "<p>fabriqué avec du lait collecté en France</p>", "<p>Ce produit n'est pas fabriqué en France</p>"):
        assert detect_origin(no)[0] is None, no


def test_duplicate_protein_row_keeps_plausible_value():
    body = ("<table><tr><th></th><th>100 g</th><th>AR</th><th>25 g</th></tr>"
            "<tr><td>Protéines</td><td>3,2 g</td><td>**</td><td>0,8 g</td></tr>"
            "<tr><td>Protéines</td><td>74 g</td><td>148%</td><td>19 g</td></tr></table>")
    assert extract("whey", body, "Vegan Protein", parse_format("500 g")).amount == 74


def test_creatine_caps_dose_amount_falls_back_to_title():
    ac = extract("creatine", "<p>3000 mg de créatine</p>", "Créatine Excell 1000mg", parse_format("100 gélules"))
    assert ac.amount == 1000 and ac.unit == "mg"


def test_portions_times_serving_size():
    from dosehunt.pipeline import _format_from_text
    from dosehunt.models import RawProduct, RawVariant
    from dosehunt.formats import variant_format
    v = RawVariant(variant_id="1", title="Impact Whey 120portions Chocolat", price=99.0)
    p = RawProduct(site_id="x", external_id="1", handle="", title="Impact Whey", url="",
                   body_html="<p>Taille de la portion : 30 g</p>", variants=[v])
    f = _format_from_text(variant_format(p, v), p, "per_100g", "whey", 1)
    assert f.total_grams == 3600


def test_origin_in_meta_description_and_buy_box_but_not_menu():
    from dosehunt.origin import detect_origin, origin_text_from_page
    page = ('<head><meta name="description" content="Formulation pour les articulations. Made in France."></head>'
            '<nav><a href="/made-in-france">Made in France</a></nav><main>Articulations 69,00 € Ajouter au panier'
            ' Fabriqué en France Paiement sécurisé</main>')
    assert detect_origin(origin_text_from_page(page))[0] == "FR"
    menu_only = '<nav><a>Fabriqué en France</a></nav><main>Whey 30 € Ajouter au panier Livraison offerte</main>'
    assert detect_origin(origin_text_from_page(menu_only))[0] is None


def test_new_categories_extraction():
    assert extract("whey", "<table><tr><th>Nutriments</th><th>Pour 100 g</th></tr><tr><td>Protéines</td><td>80 g</td></tr></table>",
                   "Micellar Casein", parse_format("908 g")).amount == 80
    ac = extract("vitamine_c", "<p>1000 mg de vitamine C par comprimé.</p>", "Vitamine C 1000", parse_format("100 comprimés"))
    assert ac and ac.amount == 1000
    ac = extract("glutamine", "<p>Une portion : 5 g</p><p>5 g de L-glutamine par portion</p>", "L-Glutamine", parse_format("500 g"))
    assert ac and ac.amount == 100


def test_clear_whey_subcategory():
    from dosehunt.classify import classify
    from dosehunt.models import RawProduct
    def sub(t):
        return [(c.category, c.subcategory) for c in classify(RawProduct(site_id="x", external_id="1", handle="", title=t, url=""))]
    assert sub("Clear Whey Isolate") == [("whey", "clear")]
    assert sub("Clear Vegan Protein") == [("whey", "vegane")]
    assert sub("Native Micellar Casein Isolate") == [("whey", "caseine")]
    ac = extract("preworkout", "<table><tr><td>Pour 10 g</td><td>AR</td></tr><tr><td>Caféine</td><td>200 mg</td><td>-</td></tr></table>",
                 "C4", parse_format("300 g"))
    assert ac.amount == 10 and ac.basis == "per_serving"


def test_product_details_ingredients_nutrition_attributes():
    from dosehunt.details import product_details, page_extras
    body = ("<p>Whey native issue de lait français. Sans lactose.</p>"
            "<table><tr><th>Nutriments</th><th>Pour 100 g</th></tr><tr><td>Énergie</td><td>1600 kJ / 380 kcal</td></tr>"
            "<tr><td>Protéines</td><td>80 g</td></tr><tr><td>Sel</td><td>0,3 g</td></tr></table>"
            "<p>Ingrédients : Protéines de lactosérum (lait) 98%, arôme naturel, émulsifiant (lécithine de tournesol), "
            "édulcorant : sucralose. Allergènes : lait.</p>")
    d = product_details(body, "Whey")
    assert d["nutrition"] == {"energy_kcal": 380.0, "protein": 80.0, "salt": 0.3}
    a = d["attributes"]
    assert a["lactose_free"] and a["milk_origin"] == "FR" and a["sweeteners"] == ["sucralose"]
    assert a["no_sweetener"] is False and a["ingredient_count"] == 4 and "sucralose" in a["watched_additives"]
    assert product_details("<p>Ingrédients : protéines de lactosérum, cacao maigre, sel.</p>")["attributes"]["no_sweetener"] is True
    e = page_extras('<script type="application/ld+json">{"@type":"Product","image":["https://x/i.jpg"],'
                    '"aggregateRating":{"ratingValue":"9.2","bestRating":"10","reviewCount":"120"}}</script>')
    assert e == {"image_url": "https://x/i.jpg", "rating": 4.6, "review_count": 120}


def test_alerts_notify_once_then_rearm(tmp_path, monkeypatch):
    from sqlalchemy import text
    from dosehunt import db, alerts
    e = db.get_engine(f"sqlite:///{tmp_path}/a.db")
    db.init_db(e)
    sent = []
    monkeypatch.setenv("RESEND_API_KEY", "x")
    monkeypatch.setattr(alerts, "send", lambda to, subject, body: sent.append(subject) or True)
    alerts.run(e)                                   # crée la table
    with e.begin() as c:
        c.execute(text("insert into sites (id, name, platform, collector, status) values ('s', 'S', 'shopify', 'shopify', 'active')"))
        c.execute(text("insert into products (id, site_id, external_id, name, active) values (1, 's', '1', 'Whey X', 1)"))
        c.execute(text("insert into offers (id, product_id, site_id, country, variant_id, price, available, active) values (1, 1, 's', 'FR', 'v', 30, 1, 1)"))
        c.execute(text("insert into index_rows (offer_id, category, country, final_price, dose_value) values (1, 'whey', 'FR', 30, 40)"))
        c.execute(text("insert into price_alerts (email, product_id, category, mode, threshold, country, token, confirmed) "
                       "values ('a@b.fr', 1, 'whey', 'dose', 45, 'FR', 't1', 1)"))
    alerts.run(e); alerts.run(e)
    assert len(sent) == 1                           # une seule fois tant que le prix reste sous le seuil
    with e.begin() as c:
        c.execute(text("update index_rows set dose_value = 50"))
    alerts.run(e)
    with e.begin() as c:
        c.execute(text("update index_rows set dose_value = 39"))
    alerts.run(e)
    assert len(sent) == 2                           # réarmée après être repassée au-dessus


def test_page_image_og_first_relative_and_https():
    from dosehunt.details import page_extras
    page = ('<meta property="og:image" content="https://www.zumub.com/images/large/zumub/x_LRG.jpg">'
            '<script type="application/ld+json">{"@type":"Product","image":"https://www.zumub.com/images/large/x_LRG.jpg"}</script>')
    assert page_extras(page)["image_url"] == "https://www.zumub.com/images/large/zumub/x_LRG.jpg"
    rel = '<script type="application/ld+json">{"@type":"Product","image":"/img/prods/1/main.webp"}</script>'
    assert page_extras(rel, "https://www.optigura.fr/product/x")["image_url"] == "https://www.optigura.fr/img/prods/1/main.webp"
    assert page_extras('<meta property="og:image" content="http://shop.fr/a.jpg">')["image_url"] == "https://shop.fr/a.jpg"
    assert page_extras('<meta property="og:image" content="https://shop.fr/logo.png">')["image_url"] is None


def test_rayon_category_when_name_is_silent():
    from dosehunt.classify import classify
    from dosehunt.models import RawProduct
    p = RawProduct(site_id="hsn", external_id="1", handle="", title="Evobomb", url="", rayon_categories=["preworkout"],
                   body_html="Caféine 200 mg, bêta-alanine 3 g, citrulline malate 6 g")
    assert [(c.category) for c in classify(p)] == ["preworkout"]
    greens = RawProduct(site_id="bulk", external_id="9", handle="", title="Complete Greens", url="",
                        body_html="spiruline, chlorelle", rayon_categories=["preworkout"])
    assert classify(greens) == []                   # rayon « pré-entraînement » sans actifs de pré-workout
    syrup = RawProduct(site_id="bulk", external_id="8", handle="", title="Sirop zéro calorie", url="", tags=["pre-workout"])
    assert classify(syrup) == []
    gel = RawProduct(site_id="z", external_id="2", handle="", title="Energy Gel citron", url="", rayon_categories=["barres"])
    assert classify(gel) == []                      # rayon « barres, boissons et gels » : pas une barre sans le mot
    caps = RawProduct(site_id="z", external_id="3", handle="", title="Caféine 200 mg 90 comprimés", url="", rayon_categories=["preworkout"])
    assert classify(caps) == []


def test_preworkout_price_per_serving_and_profile():
    from dosehunt.pricing import compute
    from dosehunt.models import Format
    from dosehunt.details import preworkout_profile
    from dosehunt.collectors.base import html_to_text
    body = ("<p>Dose : 12,5 g</p><table><tr><th>Nutriments</th><th>Pour 100 g</th><th>Par portion (12,5 g)</th></tr>"
            "<tr><td>Caféine</td><td>1600 mg</td><td>200 mg</td></tr><tr><td>L-Citrulline</td><td>40 g</td><td>5 g</td></tr></table>")
    ac = extract("preworkout", body, "Pre X", parse_format("375 g"))
    assert ac.basis == "per_serving" and ac.amount == 12.5
    r = compute("preworkout", 30.0, Format(grams=375, confidence=1, raw="375 g"), ac, None)
    assert r.dose_value == 1.0                      # 30 € / 30 portions
    prof = preworkout_profile(html_to_text(body))
    assert prof["caffeine"]["dose"] == 200 and prof["caffeine"]["ok"] and not prof["citrulline"]["ok"]


def test_free_shipping_threshold_and_code():
    from dosehunt.codes import shipping_info
    assert shipping_info("Livraison Mondial Relay offerte dès 59,90€ *")[0] == 59.9
    assert shipping_info("LIVRAISON GRATUITE AU-DESSUS DE €50 | LIVRÉ EN 48 HEURES")[0] == 50
    assert shipping_info("Livraison offerte avec le code FREESHIP24")[1] == ["FREESHIP24"]


def test_review_topics_from_page():
    from dosehunt.details import review_topics
    reviews = [("Très bon goût, se mélange bien.", 5), ("Goût chimique, déçu.", 1), ("Super goût vanille", 5),
               ("Aucun souci de digestion", 5), ("Ballonnements, digestion difficile", 2)]
    page = "".join(f'<script type="application/ld+json">{{"@type":"Review","reviewBody":"{t}","reviewRating":{{"ratingValue":"{n}"}}}}</script>'
                   for t, n in reviews)
    t = review_topics(page)["topics"]
    assert t["Goût"] == {"mentions": 3, "pos": 2, "neg": 1}
    assert t["Digestion"]["mentions"] == 2


def test_rayon_cross_links_dropped():
    from dosehunt.rayons import drop_cross_links
    out = {"sirop": {"zinc", "whey", "preworkout"}, "evobomb": {"preworkout"}, "iso": {"whey", "collagene"}}
    assert drop_cross_links("bulk", out) == {"evobomb": {"preworkout"}, "iso": {"whey", "collagene"}}
