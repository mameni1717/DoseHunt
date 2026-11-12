"""Fixtures tirées des catalogues réels relevés le 11/11/2026 (textes raccourcis, structure Shopify conservée).

Lancer : python tests/fixtures/make_fixtures.py
"""
import json
from pathlib import Path

HERE = Path(__file__).parent


def v(id_, title, price, compare=None, available=True, grams=0, o1=None, o2=None):
    return {"id": id_, "title": title, "price": price, "compare_at_price": compare, "available": available,
            "sku": f"SKU{id_}", "grams": grams, "option1": o1 or title, "option2": o2}


RAPTOR_BAR_BODY = (
    '<h6>Description</h6>\n<ul>\n<li><strong>Édition limitée</strong></li>\n<li>45g de crunchy</li>\n'
    '<li>178 calories de cacahuètes et de chocolat</li>\n<li>29% de protéines et 20% de fibres<br>\n</li>\n'
    '<li>Boîte de 12 barres délicieuses</li>\n</ul>\n<p>__TAB__</p>\n<h6>Ingrédients et composition</h6>\n'
    '<p>Informations nutritionnelles :</p>\n<table width="100%">\n<tbody>\n'
    '<tr style="height: 19px;">\n<td style="width: 33.3333%;">Information nutritionnelle<br>\n</td>\n'
    '<td style="width: 33.3333%;">Par barre (45g)<br>\n</td>\n<td style="width: 33.3333%;">Pour 100g</td>\n</tr>\n'
    '<tr>\n<td>Energie<br>\n</td>\n<td>178 kcal<br>\n</td>\n<td>395 kcal</td>\n</tr>\n'
    '<tr>\n<td>Protéines</td>\n<td>13 g</td>\n<td>29 g</td>\n</tr>\n'
    '<tr>\n<td>\n<p>Lipides (dont acides gras saturés)</p>\n</td>\n<td>9 g (dont 2,7 g)</td>\n<td>20 g (dont 6 g)</td>\n</tr>\n'
    '</tbody></table>'
)

products = [
    # Raptor : vitamine D en durée (1 mois / 3 mois), prix barré incohérent sur la Glowy
    {"id": 11006989893978, "title": "Vitamine D3 – ancienne formule", "handle": "vitamine-d3-ancienne-formule",
     "vendor": "Raptor Nutrition", "product_type": "", "tags": ["YGroup_vitamine-d3"],
     "body_html": "<p>La vitamine D3 dosée à 3 000 UI pour 2 gélules, à prendre au cours d’un repas.</p>",
     "options": [{"name": "Durée", "position": 1, "values": ["1 mois", "3 mois"]}],
     "variants": [v(54845901963610, "1 mois", "11.90", "16.90", grams=49),
                  v(54845901996378, "3 mois", "33.90", "35.70", grams=148)]},
    {"id": 10338189902170, "title": "(Super) Crunchy Peanuts Choco - 12 Barres Protéinées",
     "handle": "barre-proteinee-super-crunchy-peanuts-choco", "vendor": "Raptor Nutrition", "product_type": "",
     "tags": [], "body_html": RAPTOR_BAR_BODY,
     "options": [{"name": "Quantité", "position": 1, "values": ["1 boîte", "2 boîtes"]}],
     "variants": [v(51928620335450, "1 boîte", "37.99", None, True, 720),
                  v(51928620368218, "2 boîtes", "72.99", "71.98", True, 1440)]},
    {"id": 8756123271514, "title": "Glowy - Collagène Sticks + Vitamine C", "handle": "glowy-collagene-sticks",
     "vendor": "Raptor Nutrition", "product_type": "", "tags": [],
     "body_html": "<p>4,5 g de collagène marin hydrolysé et 120 mg de vitamine C dans un stick au goût orange-pamplemousse, à diluer chaque jour.</p>",
     "options": [{"name": "Goût", "position": 1, "values": ["Orange Pamplemousse"]},
                 {"name": "Durée", "position": 2, "values": ["1 mois", "3 mois"]}],
     "variants": [v(47656697659738, "Orange Pamplemousse / 1 mois", "48.00", "44.00", o1="Orange Pamplemousse", o2="1 mois")]},
    # Toutelanutrition : whey avec format + saveur, créatine pure, œuf à exclure
    {"id": 1001, "title": "Native Whey Isolate", "handle": "native-whey-isolate", "vendor": "Nutrimuscle",
     "product_type": "Isolate", "tags": [],
     "body_html": "<p>Whey native isolate.</p><table><tr><td>Valeurs nutritionnelles</td><td>Pour 100 g</td><td>Par portion de 30 g</td></tr>"
                  "<tr><td>Protéines</td><td>85 g</td><td>25,5 g</td></tr></table>",
     "options": [{"name": "Conditionnement", "position": 1}, {"name": "Saveur", "position": 2}],
     "variants": [v(2001, "Pot de 1kg / Chocolat", "58.95", o1="Pot de 1kg", o2="Chocolat"),
                  v(2002, "Pot de 2.25Kg / Vanille", "123.95", o1="Pot de 2.25Kg", o2="Vanille")]},
    {"id": 1002, "title": "Créatine Monohydrate", "handle": "creatine-monohydrate-tln", "vendor": "TLN",
     "product_type": "Créatine", "tags": [], "body_html": "<p>Créatine en poudre.</p>",
     "options": [{"name": "Conditionnement", "position": 1}],
     "variants": [v(2003, "Pot de 250g", "14.90")]},
    {"id": 1003, "title": "Egg Protein", "handle": "egg-protein", "vendor": "Nutrimuscle", "product_type": "whey",
     "tags": [], "body_html": "<p>Protéine d'oeuf.</p>", "options": [{"name": "Conditionnement", "position": 1}],
     "variants": [v(2004, "Pot de 1kg / Chocolat", "54.95")]},
    {"id": 1004, "title": "Whey + Collagen HT", "handle": "whey-collagen-ht", "vendor": "Eiyolab", "product_type": "whey",
     "tags": [], "body_html": "<p>24 g de protéines pour une portion de 30 g.</p>",
     "options": [{"name": "Conditionnement", "position": 1}, {"name": "Saveur", "position": 2}],
     "variants": [v(2005, "Doypack de 750g / Chocolat", "39.90", o1="Doypack de 750g", o2="Chocolat")]},
    # BioTechUSA : erreur d'unité réelle (« Zinc 12,5 g ») et format dans le titre
    {"id": 1005, "title": "Zinc Duo - 60 comprimés", "handle": "zinc-duo-60-comprimes", "vendor": "BioTechUSA",
     "product_type": "Vitamines", "tags": [],
     "body_html": "<p>Que contient Zinc Duo de BioTechUSA ?</p><p>Dose journalière 1/2 comprimé / Nombre des doses dans le produit: 120</p>"
                  "<p>Les agents dans 1/2 comprimé Zinc 12,5 g (VNR* 125%) - à partir de gluconate de zinc 10 g - à partir de bisglycinate de zinc 2,5 g</p>",
     "options": [{"name": "Title", "position": 1}],
     "variants": [v(2006, "Default Title", "10.90", "0.00")]},
    # Nutrimuscle : zinc propre ; magnésium avec dose
    {"id": 1006, "title": "Zinc Ultimine 5,5 %", "handle": "zinc-ultimine-5-5", "vendor": "Nutrimuscle",
     "product_type": "Minéraux", "tags": [],
     "body_html": "<ul><li>Zinc breveté Ultimine™, obtenu par fermentation naturelle du Koji</li>"
                  "<li>12 mg de zinc par gélule, soit 120 % des VNR</li><li>Dosage recommandé : 1 gélule par jour</li></ul>",
     "options": [{"name": "Format", "position": 1}], "variants": [v(2007, "30 gélules", "8.95")]},
    # Prozis-like : le piège du « 120 mg »
    {"id": 1007, "title": "Gluconate de Zinc 120 mg - 120 comprimés", "handle": "gluconate-zinc-120",
     "vendor": "Test", "product_type": "Minéraux", "tags": [],
     "body_html": "<p>Gluconate de zinc 120 mg par comprimé, soit 15 mg de zinc élément par comprimé.</p>",
     "options": [{"name": "Title", "position": 1}], "variants": [v(2008, "Default Title", "11.99")]},
    # Fitness Boutique : barre olympique à exclure
    {"id": 1008, "title": "Barre Olympique 350 kg", "handle": "barre-olympique", "vendor": "FB", "product_type": "MATERIEL",
     "tags": [], "body_html": "<p>Barre de musculation.</p>", "options": [{"name": "Title", "position": 1}],
     "variants": [v(2009, "Default Title", "159.00")]},
    # Oméga-3 en capsules
    {"id": 1009, "title": "Oméga 3 EPAX®", "handle": "omega-3-epax", "vendor": "Nutrimuscle",
     "product_type": "Nutriments - Oméga 3", "tags": [],
     "body_html": "<p>Pour 2 capsules : EPA 660 mg, DHA 440 mg.</p>",
     "options": [{"name": "Format", "position": 1}],
     "variants": [v(2010, "60 capsules", "17.95"), v(2011, "120 capsules", "30.95")]},
    # Magnésium
    {"id": 1010, "title": "Magnésium bisglycinate 1500mg", "handle": "magnesium-bisglycinate", "vendor": "Terravita",
     "product_type": "Minéraux", "tags": [],
     "body_html": "<p>1500 mg de bisglycinate de magnésium pour 3 gélules, soit 300 mg de magnésium pour 3 gélules.</p>",
     "options": [{"name": "Conditionnement", "position": 1}], "variants": [v(2012, "90 gélules", "14.90")]},
]

(HERE / "shopify_products.json").write_text(json.dumps({"products": products}, ensure_ascii=False, indent=1), encoding="utf-8")

GREENWHEY_PAGE = """<!DOCTYPE html><html lang="fr"><head>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"ProductGroup","name":"Isolat de Whey Native",
"productID":"gid://shopify/Product/2000280584255","description":"Notre isolat de whey native est issu de lait frais des Alpes. Chaque portion de 30 g contient 25 g de protéines natives.",
"url":"https://greenwhey.com/products/isolat-de-whey-native-100-bio","brand":{"@type":"Brand","name":"greenwhey"},"category":"Whey 100% Bio",
"hasVariant":[{"@type":"Product","name":"Chocolat","sku":"GRN-WPI-CHOCOLATE","weight":{"@type":"QuantitativeValue","unitCode":"g","value":990},
"offers":[{"@type":"Offer","name":"900 g (1 produit)","price":59.95,"priceCurrency":"EUR","availability":"https://schema.org/InStock"},
{"@type":"Offer","name":"1.8 kg (2 produits)","price":113.91,"priceCurrency":"EUR","availability":"https://schema.org/InStock"}]}]}</script>
</head><body></body></html>"""
(HERE / "greenwhey_product.html").write_text(GREENWHEY_PAGE, encoding="utf-8")

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://greenwhey.com/sitemap/products/1.xml</loc></sitemap>
  <sitemap><loc>https://greenwhey.com/sitemap/articles/1.xml</loc></sitemap>
</sitemapindex>"""
SITEMAP_PRODUCTS = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://greenwhey.com/products/isolat-de-whey-native-100-bio</loc></url>
</urlset>"""
(HERE / "greenwhey_sitemap_index.xml").write_text(SITEMAP_INDEX, encoding="utf-8")
(HERE / "greenwhey_sitemap_products.xml").write_text(SITEMAP_PRODUCTS, encoding="utf-8")
print("fixtures écrites")
