"""Chaîne complète pour un site : collecte → classement → teneurs → contrôles → base → index."""
from __future__ import annotations

import hashlib
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Optional

from sqlalchemy import and_, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine

from . import checks, db, extract, llm
from .classify import classify, passes_site_filters
from .collectors import collector_for
from .config import Site, categories, codes_config, sites
from .formats import merge, parse_format, variant_flavour, variant_format
from .models import ActiveContent, Format, RawProduct, ReviewItem, now_utc
from .pricing import Code, best_code, compute

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- utilitaires base

def upsert(conn: Connection, table, values: dict, keys: list[str], update_cols: Optional[Iterable[str]] = None) -> int:
    ins = (pg_insert if conn.dialect.name == "postgresql" else sqlite_insert)(table).values(**values)
    cols = list(update_cols) if update_cols is not None else [k for k in values if k not in keys]
    stmt = ins.on_conflict_do_update(index_elements=keys, set_={c: ins.excluded[c] for c in cols}) if cols \
        else ins.on_conflict_do_nothing(index_elements=keys)
    conn.execute(stmt)
    if "id" not in table.c:
        return 0
    row = conn.execute(select(table.c.id).where(and_(*[table.c[k] == values[k] for k in keys]))).first()
    return row[0]


def canonical_key(brand: Optional[str], name: str) -> str:
    s = f"{brand or ''} {name}".lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|mg|gelules?|comprimes?|capsules?|caps|tabs?|barres?)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())[:255]


def seed(engine: Engine) -> None:
    """Pays, sites et codes promo depuis la configuration."""
    with engine.begin() as conn:
        upsert(conn, db.countries, {"code": "FR", "name": "France", "currency": "EUR", "vat_rate": 0.2, "language": "fr"}, ["code"])
        for s in sites().values():
            upsert(conn, db.sites, {"id": s.id, "name": s.name, "platform": s.platform,
                                    "collector": s.collector, "status": s.status, "base_url": s.root,
                                    "affiliate_template": s.affiliate_template or None}, ["id"])
            upsert(conn, db.site_domains, {"site_id": s.id, "country": s.country, "base_url": s.root}, ["site_id", "country"])
        for c in codes_config().get("codes", []):
            upsert(conn, db.promo_codes, {
                "site_id": c["site"], "country": c.get("country", "FR"), "code": c["code"],
                "discount_type": c.get("discount_type", "percent"), "value": c["value"],
                "min_order": c.get("min_order"), "first_order_only": c.get("first_order_only", False),
                "stackable_with_sale": c.get("stackable_with_sale", True), "applies_to": c.get("applies_to", "all"),
                "source": c.get("source"), "confidence": c.get("confidence", 0.5),
                "last_confirmed": c.get("last_confirmed"), "ends_on": c.get("ends_on"),
                "tiers": c.get("tiers"), "origin": "manual",
            }, ["site_id", "country", "code"],
                update_cols=["discount_type", "value", "min_order", "first_order_only", "stackable_with_sale",
                             "applies_to", "source", "confidence", "last_confirmed", "ends_on", "tiers", "origin"])


SAMPLE = re.compile(r"[ée]chantillon|\bsample\b|\bmonodose\b|\btesteur\b|\b1\s*portions?\b", re.I)

AUTO_CONFIDENCE = 0.75        # code affiché par le site lui-même
UP_TO_CONFIDENCE = 0.4        # « jusqu'à -36 % » : sous le seuil, affiché mais pas appliqué


def store_found_codes(engine: Engine, site: Site, found: list, today=None, pages_read: int = 1) -> dict:
    """Enregistre les codes relevés sur un site. Un code saisi à la main n'est pas écrasé : on confirme seulement
    qu'il est toujours affiché (date de dernière confirmation)."""
    from datetime import date as _date
    today = today or _date.today()
    stats = {"new": 0, "confirmed": 0}
    with engine.begin() as conn:
        for fc in found:
            row = conn.execute(select(db.promo_codes).where(and_(
                db.promo_codes.c.site_id == site.id, db.promo_codes.c.country == site.country,
                db.promo_codes.c.code == fc.code))).mappings().first()
            if row and row["origin"] == "manual":
                conn.execute(update(db.promo_codes).where(db.promo_codes.c.id == row["id"]).values(
                    last_confirmed=today, confidence=max(row["confidence"] or 0, AUTO_CONFIDENCE)))
                stats["confirmed"] += 1
                continue
            stats["confirmed" if row else "new"] += 1
            upsert(conn, db.promo_codes, {
                "site_id": site.id, "country": site.country, "code": fc.code, "discount_type": "percent",
                "value": fc.value, "min_order": fc.min_order, "first_order_only": fc.first_order_only,
                "stackable_with_sale": fc.stackable_with_sale, "applies_to": "all",
                "source": "affiché sur le site (relevé automatique)" + (" ; remise « jusqu'à », variable selon les produits : "
                          "affichée mais non appliquée au prix" if fc.up_to else ""),
                "confidence": UP_TO_CONFIDENCE if fc.up_to else (getattr(fc, "confidence", None) or AUTO_CONFIDENCE),
                "last_confirmed": today, "ends_on": fc.ends_on, "tiers": fc.tiers or None, "origin": "auto",
                "evidence": fc.evidence, "missed_runs": 0,
            }, ["site_id", "country", "code"],
                update_cols=["value", "min_order", "first_order_only", "stackable_with_sale", "confidence",
                             "last_confirmed", "ends_on", "tiers", "evidence", "source", "missed_runs"])
        # Codes relevés automatiquement et absents cette fois : un relevé manqué de plus (seulement si les pages
        # ont bien été lues ; un site injoignable ne fait pas disparaître ses codes).
        if pages_read:
            seen = {fc.code for fc in found}
            for row in conn.execute(select(db.promo_codes.c.id, db.promo_codes.c.code, db.promo_codes.c.missed_runs)
                                    .where(and_(db.promo_codes.c.site_id == site.id, db.promo_codes.c.country == site.country,
                                                db.promo_codes.c.origin == "auto",
                                                db.promo_codes.c.discount_type != "free_shipping"))).mappings():
                if row["code"] not in seen:
                    conn.execute(update(db.promo_codes).where(db.promo_codes.c.id == row["id"])
                                 .values(missed_runs=(row["missed_runs"] or 0) + 1))
                    stats["missed"] = stats.get("missed", 0) + 1
    return stats


def store_shipping(engine: Engine, site: Site, threshold, free_codes: list, evidence: str = "", today=None) -> None:
    """Seuil de livraison offerte et codes « livraison offerte » relevés sur le site."""
    from datetime import date as _date
    today = today or _date.today()
    with engine.begin() as conn:
        if threshold is not None:
            upsert(conn, db.shipping, {"site_id": site.id, "country": site.country, "free_threshold": threshold},
                   ["site_id", "country"], update_cols=["free_threshold"])
        for code in free_codes:
            upsert(conn, db.promo_codes, {
                "site_id": site.id, "country": site.country, "code": code, "discount_type": "free_shipping",
                "value": None, "applies_to": "all", "source": "affiché sur le site (relevé automatique) : livraison offerte",
                "confidence": AUTO_CONFIDENCE, "last_confirmed": today, "origin": "auto", "evidence": evidence[:300],
            }, ["site_id", "country", "code"], update_cols=["discount_type", "confidence", "last_confirmed", "source"])


def load_db_codes(conn: Connection) -> list[Code]:
    out = []
    for r in conn.execute(select(db.promo_codes)).mappings():
        out.append(Code(code=r["code"], site=r["site_id"], country=r["country"], discount_type=r["discount_type"],
                        value=r["value"], first_order_only=bool(r["first_order_only"]),
                        stackable_with_sale=bool(r["stackable_with_sale"]), applies_to=r["applies_to"] or "all",
                        min_order=r["min_order"], confidence=r["confidence"] or 0.5,
                        last_confirmed=r["last_confirmed"], ends_on=r["ends_on"],
                        votes_ok=r["votes_ok"] or 0, votes_ko=r["votes_ko"] or 0, source=r["source"] or "",
                        tiers=r["tiers"] or None, origin=r["origin"] or "manual",
                        missed_runs=r.get("missed_runs") or 0))
    return out


# --------------------------------------------------------------------------- traitement d'un produit

@dataclass
class RunStats:
    products_seen: int = 0
    products_in_scope: int = 0
    offers_indexed: int = 0
    sent_to_review: int = 0
    llm_calls: int = 0
    pages_fetched: int = 0
    reviews: list[ReviewItem] = field(default_factory=list)


# À incrémenter quand les règles de lecture des fiches changent : toutes les fiches sont relues une fois.
RULES_VERSION = "2026-11-13"


def _body_hash(p: RawProduct) -> str:
    return hashlib.sha256((RULES_VERSION + "\n" + p.title + "\n" + p.body_html).encode()).hexdigest()


def _review(conn: Connection, stats: RunStats, item: ReviewItem, category: Optional[str] = None) -> None:
    stats.sent_to_review += 1
    stats.reviews.append(item)
    upsert(conn, db.review_queue, {
        "site_id": item.site_id, "external_id": item.external_id, "category": category or "",
        "reason": item.reason, "detail": item.detail, "payload": item.payload,
        "created_at": now_utc(), "resolved": False,
    }, ["site_id", "external_id", "category", "reason"], update_cols=["detail", "payload", "created_at", "resolved"])


def _resolve_active(conn: Connection, p: RawProduct, product_id: int, category: str, sub, combined: bool,
                    body_changed: bool, sample_fmt: Format, stats: RunStats, use_llm: bool,
                    reextract: bool = False, fetch_page=None) -> Optional[ActiveContent]:
    from .config import manual_for
    manual = manual_for(p.site_id, p.external_id, p.title, category)
    if manual:
        m = manual[0]
        ac = ActiveContent(category, categories()[category]["active"], float(m["amount"]), m["unit"], m["basis"],
                           "manual", 1.0, m.get("source", "vérifié à la main"), form=m.get("form"),
                           salt_label_mg=m.get("salt_label_mg"))
        upsert(conn, db.product_actives, {
            "product_id": product_id, "category": category, "subcategory": sub, "combined": combined,
            "active": ac.active, "amount": ac.amount, "unit": ac.unit, "basis": ac.basis, "source": "manual",
            "confidence": 1.0, "evidence": ac.evidence[:1000], "form": ac.form, "salt_label_mg": ac.salt_label_mg,
            "note": None, "units_per_dose": None, "status": "manual", "read_at": now_utc(),
        }, ["product_id", "category"])
        return ac
    existing = conn.execute(select(db.product_actives).where(and_(
        db.product_actives.c.product_id == product_id, db.product_actives.c.category == category))).mappings().first()
    stale_rule = existing is not None and existing["status"] == "ok" and existing["basis"] != categories()[category]["basis"]
    if existing and (existing["status"] == "manual" or (not body_changed and not reextract and not stale_rule
                                                         and existing["status"] == "ok")):
        return ActiveContent(category, existing["active"], existing["amount"], existing["unit"], existing["basis"],
                             existing["source"], existing["confidence"], existing["evidence"] or "",
                             existing["units_per_dose"], existing["salt_label_mg"], existing["form"], existing["note"])
    if existing and not body_changed and not reextract and existing["status"] == "review":
        return None                                  # déjà en attente de revue, inutile de relire

    ac = extract.extract(category, p.body_html, p.title, sample_fmt)
    if (ac is None or checks.check_active(ac)) and fetch_page is not None and p.source == "shopify_json":
        # La description du catalogue JSON n'a souvent pas la composition : elle est dans les onglets de la page.
        page_html = fetch_page(p.url)
        if page_html:
            from .collectors.page import zone_html, with_nutrition_tables
            zone = with_nutrition_tables(zone_html(page_html), page_html)
            p.body_html = (p.body_html or "") + "\n" + zone      # sert aussi au format (« Pot de 750 g »)
            from .collectors.base import format_hint
            if (hint := format_hint(page_html)):
                p.body_html += f"\n<p>Contenance : {hint}</p>"
            retry = extract.extract(category, zone, p.title, sample_fmt)
            if retry is not None and (ac is None or not checks.check_active(retry)):
                ac = retry
                stats.pages_fetched += 1
    if ac is None and use_llm and llm.enabled():
        stats.llm_calls += 1
        ac = llm.llm_extract(category, p.title, p.body_html, [v.title for v in p.variants])
        if ac:
            ac.category = category
    status, problem = "ok", None
    if ac is None:
        status, problem = "review", "aucune teneur trouvée dans la fiche"
        reason = "no_extraction"
    else:
        problem = checks.check_active(ac)
        reason = "out_of_range"
        if problem:
            status = "review"
    values = {
        "product_id": product_id, "category": category, "subcategory": sub, "combined": combined,
        "status": status, "read_at": now_utc(),
        **({"active": ac.active, "amount": ac.amount, "unit": ac.unit, "basis": ac.basis, "source": ac.source,
            "confidence": ac.confidence, "evidence": ac.evidence[:1000], "units_per_dose": ac.units_per_dose,
            "salt_label_mg": ac.salt_label_mg, "form": ac.form, "note": ac.note} if ac else {}),
    }
    upsert(conn, db.product_actives, values, ["product_id", "category"])
    if not problem:
        conn.execute(update(db.review_queue).where(and_(
            db.review_queue.c.site_id == p.site_id, db.review_queue.c.external_id == p.external_id,
            db.review_queue.c.category == category, db.review_queue.c.resolved.is_(False),
            db.review_queue.c.reason.in_(["no_extraction", "out_of_range"]))).values(resolved=True))
    if problem:
        _review(conn, stats, ReviewItem(p.site_id, p.external_id, reason, problem, {
            "title": p.title, "url": p.url, "category": category,
            "extracted": ac.__dict__ if ac else None,
        }), category)
        return None
    return ac


def _fill_units(fmt: Format, ac: Optional[ActiveContent], p: RawProduct) -> Format:
    """Formats en durée (« 3 mois ») ou sans nombre d'unités : on complète depuis la fiche."""
    if fmt.total_units is None and fmt.months and ac and ac.units_per_dose:
        fmt.units = int(round(fmt.months * 30 * ac.units_per_dose))
        fmt.confidence = min(fmt.confidence, 0.7)
    if fmt.total_units is None and fmt.months:
        return fmt      # durée sans dose journalière connue : un « pilulier de 90 » ne vaut pas pour toutes les durées
    if fmt.total_units is None and fmt.grams is None:
        grams, units = extract.content_from_text(p.body_html)
        if grams or units:
            fmt.grams, fmt.units = grams, units
            fmt.unit_word = fmt.unit_word or ("gélule" if units else None)
            fmt.confidence = min(fmt.confidence or 0.7, 0.7)
    if fmt.total_units is None and fmt.grams is None and (ac is None or ac.category != "barres"):
        n = extract.units_from_text(p.body_html)   # « boîte de 60 gélules » : pas pour les barres
        if n:
            fmt.units, fmt.confidence = n, min(fmt.confidence or 0.7, 0.7)
    return fmt


def _format_from_text(fmt: Format, p: RawProduct, basis: str, category: str, n_variants: int) -> Format:
    """Libellé muet sur le poids ou le nombre d'unités : on le cherche dans le texte de la fiche.

    « 120 portions » + « Dose : 30 g » = 3,6 kg ; « Poids net : 500 g » ; « Boîte de 60 gélules ».
    Le poids lu dans la fiche ne vaut que pour un produit à format unique : avec plusieurs tailles,
    il ne dirait pas laquelle.
    """
    if fmt.months is not None:
        return fmt
    text = extract.html_to_text(p.body_html or "")
    if basis in ("per_100g", "per_serving") and fmt.total_grams is None:
        size = extract.serving_size(text)
        if fmt.total_units and fmt.unit_word in ("dose", "stick", None) and size:
            fmt.grams, fmt.units, fmt.unit_word = round(fmt.total_units * size, 1), None, None
            fmt.confidence = max(min(fmt.confidence or 0.75, 0.75), 0.6)
            return fmt
        if n_variants == 1 or fmt.confidence == 0:
            grams, _ = extract.content_from_text(p.body_html)
            if grams is None:
                m = re.search(r"Contenance\s*:\s*([\d.,]+)\s*(kg|g)\b", text, re.I)      # format le plus cité sur la page
                if m:
                    grams = float(m.group(1).replace(",", ".")) * (1000 if m.group(2).lower() == "kg" else 1)
            if grams and 20 <= grams <= 15000:
                fmt.grams, fmt.confidence = grams, max(fmt.confidence, 0.7)
    elif basis == "per_unit" and fmt.total_units is None and category != "barres" and (n_variants == 1 or fmt.confidence == 0):
        _, units = extract.content_from_text(p.body_html)
        units = units or extract.units_from_text(p.body_html)
        if units:
            fmt.units, fmt.unit_word, fmt.confidence = units, fmt.unit_word or "gélule", max(fmt.confidence, 0.7)
    return fmt


def _drop_old_categories(conn: Connection, site: Site, p: RawProduct, keep: set[str]) -> None:
    """Produit reclassé (règles resserrées) : ses lignes d'index des catégories quittées sont retirées."""
    pid = conn.execute(select(db.products.c.id).where(and_(
        db.products.c.site_id == site.id, db.products.c.external_id == p.external_id))).scalar()
    if pid is None:
        return
    offer_ids = select(db.offers.c.id).where(db.offers.c.product_id == pid)
    q = delete(db.index_rows).where(db.index_rows.c.offer_id.in_(offer_ids))
    if keep:
        q = q.where(db.index_rows.c.category.not_in(keep))
    conn.execute(q)


def process_product(conn: Connection, site: Site, p: RawProduct, codes: list[Code], stats: RunStats,
                    *, use_llm: bool = True, reextract: bool = False, fetch_page=None) -> None:
    stats.products_seen += 1
    ok, why = passes_site_filters(p, site)
    if not ok:
        return
    found = classify(p, site)
    _drop_old_categories(conn, site, p, {c.category for c in found})
    if not found:
        return
    stats.products_in_scope += 1
    now = now_utc()
    bh = _body_hash(p)
    prev = conn.execute(select(db.products.c.id, db.products.c.body_hash, db.products.c.content_hint,
                               db.products.c.origin_country).where(and_(
        db.products.c.site_id == site.id, db.products.c.external_id == p.external_id))).first()
    body_changed = prev is None or prev.body_hash != bh
    product_id = upsert(conn, db.products, {
        "site_id": site.id, "external_id": p.external_id, "handle": p.handle, "brand": p.vendor,
        "name": p.title, "product_type": p.product_type, "canonical_key": canonical_key(p.vendor, p.title),
        "url": p.url, "body_hash": bh, "tags": p.tags, "first_seen": now, "last_seen": now, "active": True,
    }, ["site_id", "external_id"], update_cols=["handle", "brand", "name", "product_type", "canonical_key",
                                                 "url", "body_hash", "tags", "last_seen", "active"])

    from .details import product_details
    # Pays de fabrication : fiche du catalogue, sinon page produit (Shopify : la description JSON est souvent courte).
    if prev is None or body_changed or reextract:
        from .origin import detect_origin
        from .origin import origin_text_from_page
        origin, evidence = detect_origin(p.body_html, p.title)
        if origin is None and p.origin_text:
            origin, evidence = detect_origin(p.origin_text)
        if origin is None and fetch_page is not None and p.source == "shopify_json":
            page_html = fetch_page(p.url)
            if page_html:
                from .collectors.page import zone_html
                origin, evidence = detect_origin(zone_html(page_html), p.title)
                if origin is None:
                    origin, evidence = detect_origin(origin_text_from_page(page_html))
        from .details import page_extras
        extras = {"image_url": p.image_url, "rating": p.rating, "review_count": p.review_count}
        if p.source == "shopify_json" and fetch_page is not None and (page_cached := getattr(fetch_page, "cache", {}).get(p.url)):
            pe = page_extras(page_cached)                # avis Judge.me / Yotpo : seulement dans la page
            extras = {k: extras[k] or pe[k] for k in extras}
        conn.execute(update(db.products).where(db.products.c.id == product_id).values(
            origin_country=origin, origin_evidence=evidence, **extras))

    # Contenance absente des libellés (« Default Title », parfum seul) : on la lit une fois sur la page produit.
    hint = prev.content_hint if prev is not None and not body_changed and not reextract else None
    if p.variants and fetch_page is not None and p.source == "shopify_json" and hint is None:
        probe = variant_format(p, p.variants[0], prefer_units=True)
        if probe.total_grams is None and probe.total_units is None and probe.months is None:
            grams, units = extract.content_from_text(p.body_html)
            n = units or extract.units_from_text(p.body_html)
            if not grams and not n:
                page_html = fetch_page(p.url)
                if page_html:
                    from .collectors.page import zone_html
                    zone = zone_html(page_html)
                    p.body_html = (p.body_html or "") + "\n" + zone
                    stats.pages_fetched += 1
                    grams, units = extract.content_from_text(zone)
                    n = units or extract.units_from_text(zone)
            hint = f"{grams:g} g" if grams else f"{n} gélules" if n else None
            if hint:
                conn.execute(update(db.products).where(db.products.c.id == product_id).values(content_hint=hint))
    p_hint = parse_format(hint) if hint else None

    cats = categories()
    for cl in found:
        basis = cats[cl.category]["basis"]
        powder = bool(re.search(r"\bpoudre\b|\bpowder\b", p.title, re.I))
        # Barres : un nombre nu est un poids (« 48 » = barre de 48 g) ; poudre : un nombre nu est un poids aussi.
        prefer_units = (basis == "per_unit" or cl.category in ("creatine", "collagene", "glutamine")) and cl.category != "barres" and not powder
        sample_fmt = variant_format(p, p.variants[0], prefer_units=prefer_units) if p.variants else Format()
        ac = _resolve_active(conn, p, product_id, cl.category, cl.subcategory, cl.combined,
                             body_changed, sample_fmt, stats, use_llm, reextract, fetch_page)
        for v in p.variants:
            if SAMPLE.search(v.title or ""):
                continue                    # échantillon d'une portion : sans intérêt pour un prix au kilo
            fmt = _fill_units(variant_format(p, v, prefer_units=prefer_units), ac, p)
            if (cl.category == "barres" and fmt.total_units is None and re.match(r"\s*barre\b", p.title, re.I)
                    and v.price <= 6                                    # prix d'une barre, pas d'une boîte
                    and not re.search(r"\bbarres\b|\blot\b|\bbo[iî]te\b|\bpack\b", p.title + " " + v.title, re.I)):
                fmt.units, fmt.unit_word, fmt.confidence = 1, "barre", 0.6     # « Barre … » vendue à l'unité
            if cl.category == "barres" and fmt.total_units is None:
                mb = re.search(r"(?:bo[iî]te|lot|pack|carton|display)\s+de\s+(\d{1,3})\b(?!\s*(?:g|gr|kg)\b)", v.title, re.I)
                if mb:                                                       # Optigura : « Boite de 12 »
                    fmt.units, fmt.unit_word = int(mb.group(1)), "barre"
                    fmt.confidence = max(fmt.confidence, 0.8)
            if p_hint and fmt.total_grams is None and fmt.total_units is None and fmt.months is None:
                fmt = merge(p_hint, fmt)
                fmt.confidence = min(fmt.confidence or 0.7, 0.7)
            if cl.category == "barres" and fmt.total_units is None:
                m_b = re.search(r"(\d{1,3})\s*barres", p.title + " " + extract.html_to_text(p.body_html)[:2000], re.I)
                if m_b and int(m_b.group(1)) > 1 and not fmt.grams:
                    fmt.units, fmt.unit_word = int(m_b.group(1)), "barre"
            if cl.category == "barres" and fmt.total_units is None and fmt.grams and fmt.grams <= 150:
                fmt.units, fmt.unit_grams, fmt.grams, fmt.unit_word = 1, fmt.grams, None, "barre"   # « 60g » : une barre
            fmt = _format_from_text(fmt, p, basis, cl.category, len(p.variants))
            if ac and ac.basis == "per_unit" and ac.category in ("creatine", "collagene", "glutamine") and fmt.total_units is None:
                fmt.confidence = 0
            offer_id = upsert(conn, db.offers, {
                "product_id": product_id, "site_id": site.id, "country": site.country, "variant_id": v.variant_id,
                "variant_title": v.title, "flavour": variant_flavour(v), "url": v.url or p.url,
                "grams": fmt.total_grams, "units": fmt.total_units, "unit_word": fmt.unit_word,
                "unit_grams": fmt.unit_grams, "format_label": fmt.raw[:120], "format_confidence": fmt.confidence,
                "price": v.price, "compare_at_price": v.compare_at_price, "currency": site.currency,
                "available": v.available, "collected_at": now, "active": True,
            }, ["site_id", "country", "variant_id"])

            last = conn.execute(select(db.price_history.c.price, db.price_history.c.available)
                                .where(db.price_history.c.offer_id == offer_id)
                                .order_by(db.price_history.c.observed_at.desc()).limit(1)).first()
            jump = checks.check_price_jump(last.price if last else None, v.price)
            applied = best_code(site.id, site.country, cl.category, v.price, v.compare_at_price is not None, codes)
            final = applied.final if applied else v.price
            if last is None or last.price != v.price or bool(last.available) != v.available:
                conn.execute(db.price_history.insert().values(
                    offer_id=offer_id, observed_at=now, price=v.price, compare_at_price=v.compare_at_price,
                    best_code=applied.code.code if applied else None, final_price=final, available=v.available))

            problem = jump or (checks.check_format(fmt, ac.basis) if ac else None)
            if not problem and ac and cl.category == "barres" and fmt.unit_grams and ac.amount > 0.5 * fmt.unit_grams:
                # 36 g de protéines dans une barre de 45 g : la valeur lue est « pour 100 g », pas « par barre »
                problem = (f"{ac.amount:g} g de protéines pour une barre de {fmt.unit_grams:g} g : "
                           f"valeur probablement donnée pour 100 g")
            if ac is None or problem:                  # rupture de stock : gardée, le site l'affiche en grisé
                conn.execute(delete(db.index_rows).where(and_(
                    db.index_rows.c.offer_id == offer_id, db.index_rows.c.category == cl.category)))
                if problem:
                    _review(conn, stats, ReviewItem(site.id, f"{p.external_id}:{v.variant_id}",
                                                    "price_jump" if jump else "format_unknown", problem,
                                                    {"title": p.title, "variant": v.title, "url": v.url}), cl.category)
                continue
            conn.execute(update(db.review_queue).where(and_(
                db.review_queue.c.site_id == site.id, db.review_queue.c.external_id == f"{p.external_id}:{v.variant_id}",
                db.review_queue.c.resolved.is_(False))).values(resolved=True))
            res = compute(cl.category, v.price, fmt, ac, applied)
            upsert(conn, db.index_rows, {
                "offer_id": offer_id, "category": cl.category, "subcategory": cl.subcategory,
                "country": site.country, "final_price": res.final_price, "code": res.code,
                "total_active": res.total_active, "active_unit": res.active_unit, "dose_value": res.dose_value,
                "kg_value": res.kg_value, "unit_value": res.unit_value, "unit_label": res.unit_label,
                "calc": res.calc, "combined": cl.combined, "computed_at": now,
            }, ["offer_id", "category"])
            stats.offers_indexed += 1


# --------------------------------------------------------------------------- un site

    # Ingrédients, valeurs nutritionnelles, attributs : relus à chaque passage, après la lecture éventuelle de la page (simple lecture du texte déjà relevé),
    # pour profiter tout de suite d'une règle améliorée sans attendre que la fiche change.
    vals = product_details(p.body_html, p.title)
    page_for_reviews = p.page_html or getattr(fetch_page, "cache", {}).get(p.url) or ""
    if not page_for_reviews and p.source == "shopify_json" and fetch_page is not None and (prev is None or body_changed):
        page_for_reviews = fetch_page(p.url) or ""         # avis Shopify : seulement dans la page, lue une fois
    if page_for_reviews:
        from .details import review_topics
        vals["review_topics"] = review_topics(page_for_reviews)
    if p.image_url or p.rating is not None:
        vals.update({k: v for k, v in {"image_url": p.image_url, "rating": p.rating, "review_count": p.review_count}.items() if v is not None})
    conn.execute(update(db.products).where(db.products.c.id == product_id).values(**vals))


def top_product_urls(engine: Engine, site_id: str, n: int) -> list[str]:
    """Fiches de ce site présentes dans le top n d'au moins une catégorie ou sous-catégorie (mode par défaut)."""
    cats = categories()
    col = {"dose": db.index_rows.c.dose_value, "kg": db.index_rows.c.kg_value, "unit": db.index_rows.c.unit_value}
    urls: set[str] = set()
    with engine.connect() as conn:
        for cid, c in cats.items():
            value = col.get(c.get("default_mode", "dose"), db.index_rows.c.dose_value)
            subs = [None] + list((c.get("subcategories") or {}).keys())
            for sub in subs:
                q = (select(db.offers.c.product_id, db.products.c.url, db.offers.c.site_id, value.label("v"))
                     .select_from(db.index_rows.join(db.offers, db.offers.c.id == db.index_rows.c.offer_id)
                                  .join(db.products, db.products.c.id == db.offers.c.product_id))
                     .where(and_(db.index_rows.c.category == cid, db.offers.c.active.is_(True),
                                 db.offers.c.available.is_(True), value.is_not(None)))
                     .order_by(value))
                if sub:
                    q = q.where(db.index_rows.c.subcategory == sub)
                seen: list[int] = []
                for r in conn.execute(q):
                    if r.product_id in seen:
                        continue
                    seen.append(r.product_id)
                    if r.site_id == site_id:
                        urls.add(r.url)
                    if len(seen) >= n:
                        break
    return sorted(urls)


def run_site(engine: Engine, site: Site, *, client=None, use_llm: bool = True, limit: Optional[int] = None,
             reextract: bool = False, only_top: Optional[int] = None) -> RunStats:
    stats = RunStats()
    started = now_utc()
    collector = collector_for(site, client)
    scoped_run = False
    if only_top and site.collector in ("page", "prestashop", "magento"):
        # Mise à jour du top : seulement les fiches déjà classées dans le top, sans parcourir le catalogue.
        collector.only_urls = top_product_urls(engine, site.id, only_top)
        scoped_run = True
        log.info("%s : mise à jour du top %d, %d fiches", site.id, only_top, len(collector.only_urls))
    status, error = "ok", None
    seen_ids: set[str] = set()

    page_cache: dict[str, Optional[str]] = {}

    def fetch_page(url: str) -> Optional[str]:
        if url in page_cache:                            # même page demandée pour l'origine, le format, la teneur
            return page_cache[url]
        if len(page_cache) > 20:
            page_cache.clear()
        try:
            resp = collector.client.get(url, accept_404=True)
            page_cache[url] = resp.text if resp is not None else None
            return page_cache[url]
        except Exception as exc:                         # noqa: BLE001 — une page manquante ne bloque pas la collecte
            log.info("%s : page produit illisible %s (%s)", site.id, url, exc)
            return None
    fetch_page.cache = page_cache                       # lu par process_product (avis, photo)

    try:
        with engine.begin() as conn:
            codes = load_db_codes(conn)
        for i, raw in enumerate(collector.iter_products()):
            if limit and i >= limit:
                status = "partial"
                break
            seen_ids.add(raw.external_id)
            for attempt in range(4):
                try:
                    with engine.begin() as conn:         # une transaction par produit : une erreur n'arrête pas tout
                        process_product(conn, site, raw, codes, stats, use_llm=use_llm, reextract=reextract,
                                        fetch_page=fetch_page)
                    break
                except Exception as exc:                 # noqa: BLE001
                    if "database is locked" in str(exc) and attempt < 3:
                        time.sleep(5 + 10 * attempt)     # base SQLite occupée par une autre collecte : on réessaie
                        continue
                    log.exception("%s : produit %s en erreur", site.id, raw.external_id)
                    status, error = "partial", f"{raw.external_id}: {exc}"
                    break
    except NotImplementedError as exc:
        status, error = "failed", str(exc)
        log.warning(str(exc))
    except Exception as exc:                             # noqa: BLE001
        status, error = "failed", repr(exc)
        log.exception("%s : collecte échouée", site.id)

    for attempt in range(6):                             # clôture : réessayer si la base est occupée
        try:
            with engine.begin() as conn:
                if status == "ok" and seen_ids and not scoped_run:
                    # Les revues qui ne se sont pas reproduites pendant cette collecte complète sont closes.
                    conn.execute(update(db.review_queue).where(and_(
                        db.review_queue.c.site_id == site.id, db.review_queue.c.resolved.is_(False),
                        db.review_queue.c.created_at < started)).values(resolved=True))
                    # Produits disparus du catalogue : retirés de l'index, gardés en base pour l'historique.
                    gone = [r.id for r in conn.execute(select(db.products.c.id).where(and_(
                        db.products.c.site_id == site.id, db.products.c.active.is_(True),
                        db.products.c.external_id.not_in(seen_ids))))]
                    if gone:
                        conn.execute(update(db.products).where(db.products.c.id.in_(gone)).values(active=False))
                        offer_ids = select(db.offers.c.id).where(db.offers.c.product_id.in_(gone))
                        conn.execute(update(db.offers).where(db.offers.c.product_id.in_(gone)).values(active=False))
                        conn.execute(delete(db.index_rows).where(db.index_rows.c.offer_id.in_(offer_ids)))
                conn.execute(db.collection_runs.insert().values(
                    site_id=site.id, started_at=started, finished_at=now_utc(), status=status,
                    requests=getattr(collector.client, "requests_made", None), products_seen=stats.products_seen,
                    products_in_scope=stats.products_in_scope, offers_indexed=stats.offers_indexed,
                    sent_to_review=stats.sent_to_review, llm_calls=stats.llm_calls, error=error))
            break
        except Exception as exc:                         # noqa: BLE001
            if "database is locked" not in str(exc) or attempt == 5:
                raise
            time.sleep(10)
    log.info("%s : %s, %d produits, %d dans nos catégories, %d offres indexées, %d en revue",
             site.id, status, stats.products_seen, stats.products_in_scope, stats.offers_indexed, stats.sent_to_review)
    return stats


def recompute_index(engine: Engine) -> int:
    """Recalcule l'index après un changement de codes promo, sans recollecter."""
    n = 0
    with engine.begin() as conn:
        codes = load_db_codes(conn)
        o, a = db.offers.c, db.product_actives.c
        rows = conn.execute(select(db.index_rows.c.id.label("index_id"), db.index_rows.c.category,
                                   o.site_id, o.country, o.price, o.compare_at_price, o.grams, o.units, o.unit_word,
                                   o.format_label, a.active, a.amount, a.unit, a.basis, a.source, a.confidence)
                            .select_from(db.index_rows.join(db.offers, db.offers.c.id == db.index_rows.c.offer_id)
                                         .join(db.product_actives, and_(
                                             db.product_actives.c.product_id == db.offers.c.product_id,
                                             db.product_actives.c.category == db.index_rows.c.category)))
                            ).mappings().all()
        for r in rows:
            fmt = Format(grams=r["grams"], units=r["units"], unit_word=r["unit_word"], raw=r["format_label"] or "")
            ac = ActiveContent(r["category"], r["active"], r["amount"], r["unit"], r["basis"], r["source"], r["confidence"])
            applied = best_code(r["site_id"], r["country"], r["category"], r["price"], r["compare_at_price"] is not None, codes)
            res = compute(r["category"], r["price"], fmt, ac, applied)
            conn.execute(update(db.index_rows).where(db.index_rows.c.id == r["index_id"]).values(
                final_price=res.final_price, code=res.code, dose_value=res.dose_value, kg_value=res.kg_value,
                unit_value=res.unit_value, calc=res.calc, computed_at=now_utc()))
            n += 1
    return n
