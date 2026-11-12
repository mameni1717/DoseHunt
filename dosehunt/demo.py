"""Jeu de démonstration : les offres relevées à la main pour le prototype le 11/11/2026 (11 sites, whey et zinc).

Sert à faire tourner le site en local tant que les collectes réelles n'ont pas tourné. Les produits passent
par la même chaîne que les vraies collectes (classement, extraction, contrôles, calcul), à partir d'une
description reconstituée avec les teneurs relevées. Aucun historique n'est inventé : une seule observation
par offre. Les URL pointent vers les vraies fiches.
"""
from __future__ import annotations

from sqlalchemy.engine import Engine

from .config import get_site
from .models import RawProduct, RawVariant
from .pipeline import RunStats, load_db_codes, process_product, seed

# (site, id, marque, nom, url, teneur, formats) — teneur : g de protéine / 100 g, ou mg d'actif par unité
WHEY = [
    ("myprotein", "mp-impact", "Myprotein", "Impact Whey Protein", "https://fr.myprotein.com/p/nutrition-sportive/impact-whey-protein/10530943/", 72,
     [(450, 21.49), (900, 35.99), (1800, 67.99), (2700, 99.99), (3600, 128.99)]),
    ("myprotein", "mp-iso", "Myprotein", "Impact Whey Isolate", "https://fr.myprotein.com/p/nutrition-sportive/impact-whey-isolate/10530911/", 82,
     [(450, 29.99), (900, 49.99), (2700, 139.99)]),
    ("bulk", "bulk-pure", "Bulk", "Pure Whey Protein", "https://www.bulk.com/fr/products/proteine-whey-poudre/bpb-wpc8-0000", 65,
     [(500, 22.99), (1000, 37.99), (2500, 89.99), (5000, 169.99)]),
    ("prozis", "pz-real", "Prozis", "100% Real Whey Protein", "https://www.prozis.com/fr/fr/prozis/100-real-whey-protein-907g", 77,
     [(400, 24.99), (907, 49.99), (1814, 99.98)]),
    ("prozis", "pz-iso", "Prozis", "100% Real Whey Isolate", "https://www.prozis.com/fr/fr/prozis/100-real-whey-isolate-907g", 86,
     [(400, 31.99), (907, 69.99), (1814, 139.98)]),
    ("nutripure", "np-iso", "Nutripure", "Whey Isolate Native", "https://www.nutripure.fr/fr/musculation/13-whey-isolate-native.html", 94,
     [(750, 44.90), (2000, 109.90)]),
    ("nutrimuscle", "nm-iso", "Nutrimuscle", "Whey Native Isolate", "https://www.nutrimuscle.com/products/whey-native-isolate", 85,
     [(500, 38.95), (1000, 70.95), (2250, 147.95), (4000, 246.95)]),
]
# (site, id, marque, nom, url, mg de zinc élément par unité, mot, formats, mg affichés (sel) ou None, forme)
ZINC = [
    ("myprotein", "mp-zinc", "Myprotein", "Zinc en comprimés", "https://fr.myprotein.com/p/nutrition-sportive/zinc-en-comprimes/10575261/", 15, "comprimés", [(90, 6.99), (270, 15.00)], None, None),
    ("bulk", "bulk-zinc", "Bulk", "OptiZinc", "https://www.bulk.com/fr/products/optizinc-comprimes/bpb-ozin-0000", 6, "comprimés", [(90, 8.99)], None, "OptiZinc"),
    ("raptor", "rap-zinc", "Raptor Nutrition", "Zinc bisglycinate Albion", "https://raptornutrition.fr/products/zinc-bisglycinate-albion", 15, "gélules", [(60, 15.90), (180, 45.90)], None, "bisglycinate"),
    ("nutrimea", "nmea-zinc", "Nutrimea", "Zinc « 40 mg »", "https://www.nutrimea.com/fr-fr/products/zinc-citrate", 12.5, "gélules", [(120, 14.90)], 40, "citrate"),
    ("toutelanutrition", "tln-zinc", "Terravita", "Zinc bisglycinate", "https://www.toutelanutrition.com/products/zinc-bisglycinate", 10, "gélules", [(120, 13.90)], 50, "bisglycinate"),
    ("bodyandfit", "bf-swan-cit", "Swanson", "Zinc Citrate 50 mg élément", "https://www.bodyandfit.com/fr-fr/products/zinc-citrate-50mg-elemental", 50, "gélules", [(60, 6.69)], None, "citrate"),
    ("bodyandfit", "bf-swan-pic", "Swanson", "Zinc Picolinate 22 mg", "https://www.bodyandfit.com/fr-fr/products/zinc-picolinate-body-preferred-form-22mg", 22, "gélules", [(60, 4.69)], None, "picolinate"),
    ("bodyandfit", "bf-complex", "Body&Fit", "Zinc Complex", "https://www.bodyandfit.com/fr-fr/products/zinc-complex", 15, "comprimés", [(180, 15.99)], None, None),
    ("fitnessboutique", "fb-pure", "Pure AM Nutrition", "PURE Bisglycinate de zinc", "https://www.fitnessboutique.fr/products/pure-am-nutrition-pure-bisglycinate-de-zinc-prod-purzinc120", 15, "gélules", [(120, 12.90)], None, "bisglycinate"),
    ("fitnessboutique", "fb-tibo", "Tibo InShape", "Zinc Bisglycinate", "https://www.fitnessboutique.fr/products/tibo-inshape-zinc-bisglycinate-prod-tibzinc90", 15, "gélules", [(90, 19.90)], None, "bisglycinate"),
    ("biotechusa", "bt-bisg", "BioTechUSA", "Zinc Bisglycinate", "https://shop.biotechusa.fr/products/zinc-bisglycinate-60-comprimes", 25, "comprimés", [(60, 13.90)], None, "bisglycinate"),
    ("prozis", "pz-zinc", "Prozis", "Gluconate de Zinc « 120 mg »", "https://www.prozis.com/fr/fr/prozis/gluconate-de-zinc-120-mg-120-comprimes", 15, "comprimés", [(120, 11.99)], 120, "gluconate"),
    ("nutripure", "np-zinc", "Nutripure", "Zinc Bisglycinate", "https://www.nutripure.fr/fr/sante/146-zinc-bisglycinate.html", 15, "gélules", [(90, 16.90)], None, "bisglycinate"),
    ("nutrimuscle", "nm-zinc", "Nutrimuscle", "Zinc Ultimine 5,5 %", "https://www.nutrimuscle.com/products/zinc-ultimine-5-5", 12, "gélules", [(30, 8.95)], None, "ultimine"),
]
COMBOS = [
    ("bodyandfit", "bf-zmag", "Body&Fit", "Zinc & Magnesium", "https://www.bodyandfit.com/fr-fr/products/zinc-magnesium",
     "<p>10 mg de zinc par gélule et 150 mg de magnésium par gélule. Dose journalière : 1 gélule.</p>", [("90 gélules", 12.99)]),
]


def demo_products() -> list[RawProduct]:
    out = []
    for site, pid, brand, name, url, prot, formats in WHEY:
        body = (f"<p>Valeurs relevées le 11/11/2026.</p><table><tr><th>Nutrition</th><th>Pour 100 g</th></tr>"
                f"<tr><td>Protéines</td><td>{prot} g</td></tr></table>")
        variants = [RawVariant(variant_id=f"{pid}-{g}", title=f"{g} g" if g < 1000 else f"{g / 1000:g} kg", price=price,
                               options={"Format": f"{g} g"}, url=url) for g, price in formats]
        out.append(RawProduct(site, pid, pid, name, url, brand, "whey", [], body, variants, ["Format"], source="demo"))
    for site, pid, brand, name, url, mg, word, formats, label, form in ZINC:
        unit = word.rstrip("s")
        salt = f"<p>{form.capitalize() if form else 'Sel'} de zinc {label} mg par {unit}, soit </p>" if label else "<p></p>"
        body = (f"{salt}<p>{str(mg).replace('.', ',')} mg de zinc élément par {unit}. Dose journalière : 1 {unit}.</p>"
                + (f"<p>Forme : {form}.</p>" if form else ""))
        variants = [RawVariant(variant_id=f"{pid}-{n}", title=f"{n} {word}", price=price, options={"Format": f"{n} {word}"},
                               url=url) for n, price in formats]
        ptype = "DIETETIQUE" if site == "fitnessboutique" else "Minéraux"     # filtre réel du site
        out.append(RawProduct(site, pid, pid, name, url, brand, ptype, [], body, variants, ["Format"], source="demo"))
    for site, pid, brand, name, url, body, formats in COMBOS:
        variants = [RawVariant(variant_id=f"{pid}-{i}", title=t, price=p, options={"Format": t}, url=url)
                    for i, (t, p) in enumerate(formats)]
        out.append(RawProduct(site, pid, pid, name, url, brand, "Minéraux", [], body, variants, ["Format"], source="demo"))
    return out


def load_demo(engine: Engine) -> RunStats:
    seed(engine)
    stats = RunStats()
    with engine.begin() as conn:
        codes = load_db_codes(conn)
        for p in demo_products():
            process_product(conn, get_site(p.site_id), p, codes, stats, use_llm=False)
    return stats
