"""Export de l'index au format lu par le site (même structure que le prototype : CODES + PRODUCTS)."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.engine import Engine

from . import db
from .config import categories


def build_export(engine: Engine, country: str = "FR") -> dict:
    o, p, a, i, s = db.offers.c, db.products.c, db.product_actives.c, db.index_rows.c, db.sites.c
    q = (select(i.category, i.subcategory, i.final_price, i.code, i.total_active, i.active_unit, i.dose_value,
                i.kg_value, i.unit_value, i.unit_label, i.calc, i.combined, i.computed_at,
                o.id.label("offer_id"), o.variant_title, o.flavour, o.url.label("offer_url"), o.grams, o.units,
                o.unit_word, o.price, o.compare_at_price, o.collected_at,
                p.id.label("product_id"), p.brand, p.name, p.url.label("product_url"),
                a.amount, a.unit, a.basis, a.source, a.confidence, a.salt_label_mg, a.form, a.note, a.evidence,
                s.id.label("site_id"), s.name.label("site_name"))
         .select_from(db.index_rows.join(db.offers, o.id == i.offer_id)
                      .join(db.products, p.id == o.product_id)
                      .join(db.product_actives, and_(a.product_id == p.id, a.category == i.category))
                      .join(db.sites, s.id == o.site_id))
         .where(i.country == country))
    grouped: dict[tuple, dict] = {}
    with engine.connect() as conn:
        rows = conn.execute(q).mappings().all()
        codes = conn.execute(select(db.promo_codes).where(db.promo_codes.c.country == country)).mappings().all()
    for r in rows:
        key = (r["product_id"], r["category"], r["flavour"] or "")
        g = grouped.setdefault(key, {
            "id": f"{r['site_id']}-{r['product_id']}-{r['category']}" + (f"-{r['flavour']}" if r["flavour"] else ""),
            "cat": r["category"], "sub": r["subcategory"], "brand": r["brand"], "name": r["name"],
            "site": r["site_name"], "siteId": r["site_id"], "flavour": r["flavour"], "url": r["product_url"],
            "active": r["amount"], "activeUnit": r["unit"], "basis": r["basis"],
            "activeSource": r["source"], "activeConfidence": r["confidence"], "evidence": r["evidence"],
            "labelMg": r["salt_label_mg"], "form": r["form"], "note": r["note"],
            "combo": bool(r["combined"]), "formats": [],
        })
        g["formats"].append({
            "label": r["variant_title"], "g": r["grams"], "units": r["units"], "unitWord": r["unit_word"],
            "price": r["price"], "compareAt": r["compare_at_price"], "final": r["final_price"], "code": r["code"],
            "totalActive": r["total_active"], "dose": r["dose_value"], "kg": r["kg_value"],
            "unit": r["unit_value"], "unitLabel": r["unit_label"], "calc": r["calc"], "url": r["offer_url"],
            "checkedAt": (r["collected_at"].isoformat() if isinstance(r["collected_at"], datetime) else r["collected_at"]),
        })
    by_cat = defaultdict(int)
    for g in grouped.values():
        by_cat[g["cat"]] += 1
        g["formats"].sort(key=lambda f: (f["g"] or 0, f["units"] or 0))
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "country": country,
        "categories": {cid: {"label": c["label"], "doseLabel": c["dose_label"], "defaultMode": c["default_mode"],
                             "count": by_cat.get(cid, 0)} for cid, c in categories().items()},
        "codes": {c["code"]: {"site": c["site_id"], "label": c["code"], "type": c["discount_type"], "value": c["value"],
                              "first": bool(c["first_order_only"]), "confidence": c["confidence"], "source": c["source"],
                              "lastConfirmed": str(c["last_confirmed"]) if c["last_confirmed"] else None}
                  for c in codes},
        "products": sorted(grouped.values(), key=lambda g: (g["cat"], min((f["dose"] or 9e9) for f in g["formats"]))),
    }


def write_export(engine: Engine, path: str, country: str = "FR") -> dict:
    data = build_export(engine, country)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, default=str)
    return data
