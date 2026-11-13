"""Collecte groupée : peu d'allers-retours avec la base, mêmes données qu'un traitement produit par produit."""
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import event, select

from dosehunt import db, pipeline
from dosehunt.config import get_site
from dosehunt.pipeline import RunStats, load_db_codes, process_product, run_site, seed

sys.path.insert(0, str(Path(__file__).parent))
import test_pipeline as tp  # noqa: E402

IGNORE = {"id", "first_seen", "last_seen", "collected_at", "observed_at", "computed_at", "read_at", "created_at",
          "product_id", "offer_id"}


def _engine(tmp_path, name):
    e = db.get_engine(f"sqlite:///{tmp_path}/{name}.db")
    db.init_db(e)
    seed(e)
    return e


def _snapshot(e):
    out = {}
    with e.connect() as c:
        for t in ["products", "offers", "product_actives", "price_history", "index_rows", "review_queue"]:
            out[t] = sorted(json.dumps({k: v for k, v in r.items() if k not in IGNORE}, sort_keys=True, default=str)
                            for r in c.execute(select(db.metadata.tables[t])).mappings())
    return out


def _count(e):
    n = {"queries": 0, "commits": 0}
    event.listen(e, "before_cursor_execute", lambda *a, **k: n.__setitem__("queries", n["queries"] + 1))
    event.listen(e, "commit", lambda *a, **k: n.__setitem__("commits", n["commits"] + 1))
    return n


def _catalog():
    return json.loads(json.dumps(tp.CATALOG["products"]))


def test_few_round_trips(tmp_path):
    e = _engine(tmp_path, "q")
    n = _count(e)
    run_site(e, get_site("raptor"), client=tp.client(tp.shopify_transport(_catalog())), use_llm=False)
    # 13 fiches, 30 variantes : 228 requêtes et 15 validations avant le regroupement (13/11/2026)
    assert n["queries"] <= 100 and n["commits"] <= 4
    n["queries"] = n["commits"] = 0
    run_site(e, get_site("raptor"), client=tp.client(tp.shopify_transport(_catalog())), use_llm=False)
    assert n["queries"] <= 70                           # 2e passage : fiches inchangées, 159 avant
    n["queries"] = 0
    pipeline.recompute_index(e)
    assert n["queries"] <= 4                            # une mise à jour groupée, pas une par ligne


def test_same_rows_as_product_by_product(tmp_path):
    site = get_site("raptor")
    batched = _engine(tmp_path, "b")
    run_site(batched, site, client=tp.client(tp.shopify_transport(_catalog())), use_llm=False)

    one_by_one = _engine(tmp_path, "o")
    collector = pipeline.collector_for(site, tp.client(tp.shopify_transport(_catalog())))
    stats = RunStats()
    with one_by_one.begin() as conn:
        codes = load_db_codes(conn)
    for raw in collector.iter_products():
        with one_by_one.begin() as conn:                 # ancien chemin : sans cache, une transaction par produit
            process_product(conn, site, raw, codes, stats, use_llm=False)
    assert _snapshot(batched) == _snapshot(one_by_one)


def test_failing_product_loses_only_itself(tmp_path, monkeypatch):
    e = _engine(tmp_path, "f")
    real = pipeline.process_product

    def flaky(conn, site, p, *a, **k):
        real(conn, site, p, *a, **k)
        if p.external_id == "1005":                      # échoue après avoir écrit : tout son lot est annulé
            raise ValueError("donnée invalide")
    monkeypatch.setattr(pipeline, "process_product", flaky)
    stats = run_site(e, get_site("raptor"), client=tp.client(tp.shopify_transport(_catalog())), use_llm=False)
    with e.connect() as c:
        names = set(c.execute(select(db.products.c.external_id)).scalars())
        runs = c.execute(select(db.collection_runs.c.status, db.collection_runs.c.error)).all()
    assert "1005" not in names and len(names) >= 10      # les autres fiches du lot sont bien écrites
    assert runs[-1].status == "partial" and runs[-1].error.startswith("1005:")
    assert stats.products_seen == len(_catalog())        # compteurs remis d'aplomb après la reprise


@pytest.mark.parametrize("size", [1, 4])
def test_batch_size_does_not_change_rows(tmp_path, monkeypatch, size):
    site = get_site("raptor")
    ref = _engine(tmp_path, "ref")
    run_site(ref, site, client=tp.client(tp.shopify_transport(_catalog())), use_llm=False)
    monkeypatch.setattr(pipeline, "BATCH_SIZE", size)
    e = _engine(tmp_path, f"s{size}")
    run_site(e, site, client=tp.client(tp.shopify_transport(_catalog())), use_llm=False)
    assert _snapshot(e) == _snapshot(ref)
