"""Relevé des codes promo sur les textes réels des bandeaux (11/11/2026) et leur effet sur les prix."""
from datetime import date

import httpx
import pytest
from sqlalchemy import select

from dosehunt import db
from dosehunt.codes import collect_site_codes, extract_codes
from dosehunt.config import get_site
from dosehunt.http import PoliteClient
from dosehunt.pipeline import load_db_codes, seed, store_found_codes
from dosehunt.pricing import Code, best_code

FITADIUM = """Black Month -10% + cadeau dès 80€ : BLACK10 | -15% + cadeau dès 100€ : BLACK15
MON PANIER
*Offre valable, dans la limite des stocks disponibles, jusqu’au 20/11/2026 à 09h30, sur tout le site Fitadium.com, avec
les codes BLACK10 / BLACK15. Offre cumulable avec les promotions Black Month, hors autres promotions en cours,
programmes, packs et cures. Codes non cumulables avec d’autres codes promotionnels."""
TLN = """Fermer
Pré Black Friday ! -20% jusqu'à 69,99 euros d'achat et -25% à partir de 70 euros d'achats ! CODE : DUO20
LES MEILLEURES VENTES
Prix normal 49,90 € Jusqu'à 25% avec le code DUO20 AJOUTER AU PANIER"""


def test_fitadium_two_codes_with_thresholds_and_end_date():
    got = {c.code: c for c in extract_codes(FITADIUM)}
    assert set(got) == {"BLACK10", "BLACK15"}
    assert got["BLACK10"].tiers == [{"min": 80.0, "pct": 10}]
    assert got["BLACK15"].tiers == [{"min": 100.0, "pct": 15}]
    assert got["BLACK10"].ends_on == date(2026, 11, 20) and got["BLACK10"].stackable_with_sale


def test_tln_tiered_code():
    (c,) = extract_codes(TLN)
    assert c.code == "DUO20" and c.tiers == [{"min": 0.0, "pct": 20}, {"min": 70.0, "pct": 25}]
    assert not c.stackable_with_sale                     # rien n'autorise le cumul : prudence


def test_first_order_and_no_false_attribution():
    (c,) = extract_codes("Bienvenue ! -10% sur ta première commande avec le code HELLO10")
    assert c.first_order_only
    got = extract_codes("Code promo : FREESHIP pour la livraison. Le CODE PROMO du moment -15% : SUMMER15")
    assert [x.code for x in got] == ["SUMMER15"]          # FREESHIP n'a pas de remise en % : ignoré
    assert extract_codes("LIVRAISON OFFERTE dès 50€ - NOUVEAUTES WHEY") == []


def test_tiers_in_best_code():
    duo = Code(code="DUO20", site="toutelanutrition", country="FR", discount_type="percent", value=20,
               tiers=[{"min": 0, "pct": 20}, {"min": 70, "pct": 25}], confidence=0.75, last_confirmed=date.today())
    assert best_code("toutelanutrition", "FR", "whey", 49.90, False, [duo]).final == pytest.approx(39.92)
    assert best_code("toutelanutrition", "FR", "whey", 89.90, False, [duo]).final == pytest.approx(67.43)
    black10 = Code(code="BLACK10", site="fitadium", country="FR", discount_type="percent", value=10,
                   tiers=[{"min": 80, "pct": 10}], confidence=0.75, last_confirmed=date.today())
    assert best_code("fitadium", "FR", "whey", 59.90, False, [black10]) is None   # sous le minimum de 80 €


def test_store_does_not_overwrite_manual_codes(tmp_path):
    e = db.get_engine(f"sqlite:///{tmp_path}/c.db")
    db.init_db(e)
    seed(e)
    site = get_site("toutelanutrition")
    store_found_codes(e, site, extract_codes(TLN), today=date(2026, 11, 11))
    nm = get_site("nutrimuscle")
    from dosehunt.codes import FoundCode
    store_found_codes(e, nm, [FoundCode(code="NMA_QFITLIFE", value=50, tiers=[{"min": 0, "pct": 50}])],
                      today=date(2026, 11, 11))
    with e.connect() as conn:
        rows = {r["code"]: r for r in conn.execute(select(db.promo_codes)).mappings()}
    assert rows["DUO20"]["origin"] == "auto" and rows["DUO20"]["tiers"][1]["pct"] == 25
    assert rows["NMA_QFITLIFE"]["value"] == 5                       # valeur saisie à la main conservée
    assert rows["NMA_QFITLIFE"]["last_confirmed"] == date(2026, 11, 11)   # mais confirmé comme toujours affiché
    codes = {c.code: c for c in load_db_codes(e.connect())}
    assert codes["DUO20"].percent_for(80) == 25


def test_collect_site_codes_reads_homepage():
    page = "<html><body><div class='announcement-bar'><p>Pré Black Friday ! -20% jusqu'à 69,99 euros d'achat et " \
           "-25% à partir de 70 euros d'achats ! CODE : DUO20</p></div></body></html>"
    client = PoliteClient(0, respect_robots=False, transport=httpx.MockTransport(lambda r: httpx.Response(200, text=page)))
    (c,) = collect_site_codes(get_site("toutelanutrition"), client)
    assert c.code == "DUO20"


def test_up_to_discount_is_not_applied():
    (c,) = extract_codes("JUSQU'A -36% AVEC LE CODE « GREENFRIDAY »")
    assert c.code == "GREENFRIDAY" and c.up_to
    (d,) = extract_codes(TLN)
    assert not d.up_to                                   # paliers explicites : appliqués


def test_upto_discount_is_not_applied():
    (c,) = extract_codes("JUSQU'A -36% AVEC LE CODE « GREENFRIDAY »")
    assert c.up_to and c.tiers == [{"min": 0.0, "pct": 36}]
    (d,) = extract_codes(TLN)
    assert not d.up_to                                   # « -20% jusqu'à 69,99 € » : palier, pas plafond


def test_auto_code_dropped_after_two_missed_surveys(tmp_path):
    e = db.get_engine(f"sqlite:///{tmp_path}/m.db")
    db.init_db(e)
    seed(e)
    site = get_site("toutelanutrition")
    today = date(2026, 11, 13)
    store_found_codes(e, site, extract_codes(TLN), today=today)
    duo = lambda: next(c for c in load_db_codes(e.connect()) if c.code == "DUO20")
    store_found_codes(e, site, [], today=today, pages_read=0)       # site injoignable : rien ne change
    assert duo().missed_runs == 0
    store_found_codes(e, site, [], today=today, pages_read=1)       # 1er relevé sans le code : encore appliqué
    assert duo().effective_confidence(today) >= 0.5
    store_found_codes(e, site, [], today=today, pages_read=1)       # 2e relevé sans le code : retiré du prix
    assert duo().effective_confidence(today) == 0
    store_found_codes(e, site, extract_codes(TLN), today=today)     # réaffiché : de nouveau appliqué
    assert duo().missed_runs == 0 and duo().effective_confidence(today) >= 0.5


def test_product_page_codes():
    from dosehunt.codes import PRODUCT_ONLY_CONFIDENCE, survey_site_codes
    pages = {"/": "<p>Bienvenue</p>",
             "/p1": "<p>-10% avec le code FICHE10</p><p>-20% avec le code SEUL20</p>",
             "/p2": "<p>-10% avec le code FICHE10</p>"}
    client = PoliteClient(0, respect_robots=False,
                          transport=httpx.MockTransport(lambda r: httpx.Response(200, text=pages.get(r.url.path, ""))))
    site = get_site("toutelanutrition")
    base = site.root
    got, read = survey_site_codes(site, [base + "/p1", base + "/p2"], client)
    got = {c.code: c for c in got}
    assert read == 3
    assert got["FICHE10"].confidence is None                     # vu sur 2 fiches : vaut pour tout le site
    assert got["SEUL20"].confidence == PRODUCT_ONLY_CONFIDENCE    # vu sur une seule fiche : affiché, non appliqué
