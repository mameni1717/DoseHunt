"""Rétention des données (dosehunt purge) : la base reste petite sans rien retirer de ce que le site affiche."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text

from dosehunt import db
from dosehunt.pipeline import seed
from dosehunt.purge import purge

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def _engine(tmp_path):
    e = db.get_engine(f"sqlite:///{tmp_path}/p.db")
    db.init_db(e)
    seed(e)
    with e.begin() as c:
        c.execute(text("create table price_alerts (id integer primary key, email text, product_id integer, "
                       "category text, confirmed boolean default 0, active boolean default 1, confirm_sent_at timestamp)"))
    return e


def _product(c, ext, active=True, last_seen=NOW, offer_active=True, collected=NOW):
    pid = c.execute(db.products.insert().values(site_id="hsn", external_id=ext, name=ext, active=active,
                                                last_seen=last_seen)).inserted_primary_key[0]
    oid = c.execute(db.offers.insert().values(product_id=pid, site_id="hsn", country="FR", variant_id=ext + "-v",
                                              price=10, active=offer_active, collected_at=collected)).inserted_primary_key[0]
    c.execute(db.index_rows.insert().values(offer_id=oid, country="FR", category="whey", final_price=10))
    c.execute(db.product_actives.insert().values(product_id=pid, category="whey", active="protein", amount=80))
    return pid, oid


def _count(e, table, where=None):
    with e.connect() as c:
        q = select(func.count()).select_from(table)
        return c.execute(q.where(where) if where is not None else q).scalar()


def test_history_thinned_beyond_90_days(tmp_path):
    e = _engine(tmp_path)
    with e.begin() as c:
        _, oid = _product(c, "a")
        h = db.price_history
        for d in (120, 30):                            # 4 relevés le même jour, il y a 120 j et il y a 30 j
            for hour in range(4):
                c.execute(h.insert().values(offer_id=oid, observed_at=NOW - timedelta(days=d, hours=hour), price=10 + hour))
        for d in range(500, 507):                      # une semaine entière il y a plus de 400 j
            c.execute(h.insert().values(offer_id=oid, observed_at=NOW - timedelta(days=d), price=9))
    purge(e, now=NOW)
    h = db.price_history
    assert _count(e, h, h.c.observed_at > NOW - timedelta(days=90)) == 4          # fenêtre de 90 j intacte
    old = _count(e, h, h.c.observed_at.between(NOW - timedelta(days=121), NOW - timedelta(days=119)))
    assert old == 1                                                                 # 1 relevé par jour
    with e.connect() as c:                                                          # le dernier du jour est gardé
        kept = c.execute(select(h.c.price).where(h.c.observed_at < NOW - timedelta(days=100),
                                                 h.c.observed_at > NOW - timedelta(days=400))).scalar()
    assert kept == 10                                                               # heure 0 = le plus récent
    assert _count(e, h, h.c.observed_at < NOW - timedelta(days=400)) <= 2           # 1 par semaine (à cheval)


def test_inactive_products_removed_but_alerted_kept(tmp_path):
    e = _engine(tmp_path)
    with e.begin() as c:
        gone, _ = _product(c, "old", active=False, last_seen=NOW - timedelta(days=200), offer_active=False)
        watched, _ = _product(c, "watched", active=False, last_seen=NOW - timedelta(days=200), offer_active=False)
        recent, _ = _product(c, "recent", active=False, last_seen=NOW - timedelta(days=10), offer_active=False)
        live, _ = _product(c, "live")
        c.execute(text("insert into price_alerts (email, product_id, category, active) values ('a@b.fr', :p, 'whey', 1)"),
                  {"p": watched})
    purge(e, now=NOW)
    ids = {r[0] for r in e.connect().execute(select(db.products.c.id))}
    assert gone not in ids and {watched, recent, live} <= ids
    assert _count(e, db.offers) == 3 and _count(e, db.index_rows) == 3 and _count(e, db.product_actives) == 3


def test_codes_reviews_runs_alerts(tmp_path):
    e = _engine(tmp_path)
    pc = db.promo_codes
    with e.begin() as c:
        manual_before = c.execute(select(func.count()).select_from(pc).where(pc.c.origin != "auto")).scalar()
        old = date(2026, 9, 1)
        c.execute(pc.insert().values(site_id="hsn", country="FR", code="AUTOOLD", discount_type="percent", value=10,
                                     origin="auto", ends_on=old))
        c.execute(pc.insert().values(site_id="hsn", country="FR", code="GONE", discount_type="percent", value=10,
                                     origin="auto", missed_runs=2, last_confirmed=old))
        c.execute(pc.insert().values(site_id="hsn", country="FR", code="FRESH", discount_type="percent", value=10,
                                     origin="auto", missed_runs=2, last_confirmed=date(2026, 11, 12)))
        c.execute(pc.insert().values(site_id="hsn", country="FR", code="MANUALOLD", discount_type="percent", value=10,
                                     origin="manual", ends_on=old))
        c.execute(db.review_queue.insert().values(site_id="hsn", external_id="1", reason="x", resolved=True,
                                                  created_at=NOW - timedelta(days=60)))
        c.execute(db.review_queue.insert().values(site_id="hsn", external_id="2", reason="x", resolved=False,
                                                  created_at=NOW - timedelta(days=60)))
        c.execute(db.collection_runs.insert().values(site_id="hsn", started_at=NOW - timedelta(days=90)))
        c.execute(db.collection_runs.insert().values(site_id="hsn", started_at=NOW - timedelta(days=1)))
        c.execute(text("insert into price_alerts (email, category, confirmed, confirm_sent_at) values "
                       "('old@x.fr', 'whey', 0, :old), ('never@x.fr', 'whey', 0, null)"),
                  {"old": NOW - timedelta(days=10)})
    purge(e, now=NOW)
    codes = {r[0] for r in e.connect().execute(select(pc.c.code))}
    assert "AUTOOLD" not in codes and "GONE" not in codes and {"FRESH", "MANUALOLD"} <= codes
    assert _count(e, pc, pc.c.origin != "auto") == manual_before + 1            # codes saisis : jamais touchés
    assert _count(e, db.review_queue) == 1 and _count(e, db.collection_runs) == 1
    emails = {r[0] for r in e.connect().execute(text("select email from price_alerts"))}
    assert emails == {"never@x.fr"}                  # confirmation jamais partie : inscription gardée


def test_dry_run_changes_nothing(tmp_path):
    e = _engine(tmp_path)
    with e.begin() as c:
        _product(c, "old", active=False, last_seen=NOW - timedelta(days=200), offer_active=False)
        c.execute(db.collection_runs.insert().values(site_id="hsn", started_at=NOW - timedelta(days=90)))
    before = (_count(e, db.products), _count(e, db.offers), _count(e, db.collection_runs))
    counted = purge(e, dry_run=True, now=NOW)
    assert sum(counted.values()) >= 3
    assert (_count(e, db.products), _count(e, db.offers), _count(e, db.collection_runs)) == before
