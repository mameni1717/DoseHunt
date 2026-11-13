"""Rétention des données : garder la base Neon sous la limite de stockage de l'offre gratuite (1 Go par projet),
même avec plusieurs pays, sans rien retirer de ce que le site affiche.

Ce que le site lit (web/lib/data.ts) et qui reste intact :
  - historique sur 90 jours (plus bas) et 30 jours (prix habituel) : rien n'est touché dans cette fenêtre ;
  - courbe de la fiche produit (tout l'historique de l'offre) : au-delà de 90 jours, un point par jour suffit
    (un relevé n'est écrit que quand le prix change) ; au-delà de 400 jours, un point par semaine ;
  - offres actives, produits actifs, codes saisis à la main : jamais supprimés.

Chaque règle est une seule requête ensembliste (pas une requête par ligne). `dry_run` compte sans supprimer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Boolean, Integer, and_, column, delete, func, inspect, or_, select, table, text
from sqlalchemy.engine import Connection, Engine

from . import db

log = logging.getLogger(__name__)

SIZE_WARNING_MB = 700          # l'offre gratuite Neon s'arrête à 1 Go par projet


@dataclass
class Retention:
    history_full_days: int = 90        # historique complet
    history_daily_days: int = 400      # au-delà : un relevé par semaine
    inactive_days: int = 90            # produits / offres inactifs depuis plus longtemps : supprimés
    review_days: int = 30              # revues résolues
    runs_days: int = 60                # journal des collectes
    codes_days: int = 30               # codes « auto » expirés ou retirés du site depuis plus longtemps
    unconfirmed_alert_days: int = 7    # inscriptions d'alertes jamais confirmées (après envoi de la confirmation)


def _day(engine_name: str, col):
    return func.date(col)


def _week(engine_name: str, col):
    if engine_name == "postgresql":
        return func.date_trunc("week", col)
    return func.strftime("%Y-%W", col)


def _thin(conn: Connection, before: datetime, bucket, dry_run: bool) -> int:
    """Ne garde, avant `before`, que le dernier relevé de chaque offre par période (jour ou semaine)."""
    h = db.price_history
    later = db.price_history.alias("later")
    # un relevé plus récent de la même offre dans la même période existe : celui-ci peut partir
    newer = (select(later.c.id).where(and_(
        later.c.offer_id == h.c.offer_id, later.c.observed_at < before,
        bucket(later.c.observed_at) == bucket(h.c.observed_at),
        or_(later.c.observed_at > h.c.observed_at,
            and_(later.c.observed_at == h.c.observed_at, later.c.id > h.c.id)))).exists())
    return _apply(conn, h, and_(h.c.observed_at < before, newer), dry_run)


def _apply(conn: Connection, table, where, dry_run: bool) -> int:
    if dry_run:
        return conn.execute(select(func.count()).select_from(table).where(where)).scalar() or 0
    return conn.execute(delete(table).where(where)).rowcount or 0


def _has_table(conn: Connection, name: str) -> bool:
    return inspect(conn).has_table(name)


def purge(engine: Engine, ret: Optional[Retention] = None, dry_run: bool = False,
          now: Optional[datetime] = None) -> dict[str, int]:
    ret = ret or Retention()
    now = now or datetime.now(timezone.utc)
    today = now.date()
    name = engine.dialect.name
    out: dict[str, int] = {}
    with engine.begin() as conn:
        # 1. Historique des prix : complet sur 90 jours, puis 1 point/jour, puis 1 point/semaine au-delà de 400 jours
        out["price_history (1 relevé par jour au-delà de %d j)" % ret.history_full_days] = _thin(
            conn, now - timedelta(days=ret.history_full_days), lambda c: _day(name, c), dry_run)
        out["price_history (1 relevé par semaine au-delà de %d j)" % ret.history_daily_days] = _thin(
            conn, now - timedelta(days=ret.history_daily_days), lambda c: _week(name, c), dry_run)

        # 2. Produits inactifs depuis longtemps (sauf s'ils ont une alerte prix active), et offres inactives
        p, o = db.products, db.offers
        cutoff = now - timedelta(days=ret.inactive_days)
        old_products = select(p.c.id).where(and_(p.c.active.is_(False), p.c.last_seen < cutoff))
        if _has_table(conn, "price_alerts"):
            pa = table("price_alerts", column("product_id", Integer), column("active", Boolean))
            old_products = old_products.where(p.c.id.not_in(
                select(pa.c.product_id).where(and_(pa.c.active.is_(True), pa.c.product_id.is_not(None)))))
        old_products = old_products.scalar_subquery()
        dead_offers = select(o.c.id).where(or_(
            o.c.product_id.in_(old_products),
            and_(o.c.active.is_(False), o.c.collected_at < cutoff))).scalar_subquery()
        out["index_rows (offres supprimées)"] = _apply(conn, db.index_rows, db.index_rows.c.offer_id.in_(dead_offers), dry_run)
        out["price_history (offres supprimées)"] = _apply(conn, db.price_history,
                                                          db.price_history.c.offer_id.in_(dead_offers), dry_run)
        # en simulation, les offres comptées ici seraient déjà parties avec leur produit : même requête, même total
        out["offers (inactives depuis %d j)" % ret.inactive_days] = _apply(conn, o, o.c.id.in_(dead_offers), dry_run)
        out["product_actives (produits supprimés)"] = _apply(conn, db.product_actives,
                                                             db.product_actives.c.product_id.in_(old_products), dry_run)
        # un produit garde ses offres actives éventuelles : on ne supprime que ceux qui n'en ont plus
        gone = and_(p.c.id.in_(old_products), p.c.id.not_in(select(o.c.product_id).scalar_subquery())) if not dry_run \
            else p.c.id.in_(old_products)
        out["products (inactifs depuis %d j)" % ret.inactive_days] = _apply(conn, p, gone, dry_run)

        # 3. Revues résolues, journal des collectes
        rq = db.review_queue
        out["review_queue (résolues depuis %d j)" % ret.review_days] = _apply(
            conn, rq, and_(rq.c.resolved.is_(True), rq.c.created_at < now - timedelta(days=ret.review_days)), dry_run)
        cr = db.collection_runs
        out["collection_runs (plus de %d j)" % ret.runs_days] = _apply(
            conn, cr, cr.c.started_at < now - timedelta(days=ret.runs_days), dry_run)

        # 4. Codes relevés automatiquement, expirés ou retirés du site depuis longtemps (jamais les codes saisis)
        pc = db.promo_codes
        code_cut = today - timedelta(days=ret.codes_days)
        dead_codes = and_(pc.c.origin == "auto", or_(
            pc.c.ends_on < code_cut,
            and_(pc.c.missed_runs >= 2, pc.c.last_confirmed < code_cut)))
        out["code_votes (codes supprimés)"] = _apply(
            conn, db.code_votes, db.code_votes.c.code_id.in_(select(pc.c.id).where(dead_codes).scalar_subquery()), dry_run)
        out["promo_codes (auto, expirés ou retirés depuis %d j)" % ret.codes_days] = _apply(conn, pc, dead_codes, dry_run)

        # 5. Inscriptions d'alertes jamais confirmées, 7 jours après l'envoi de l'e-mail de confirmation
        #    (tant que les e-mails ne partent pas, confirm_sent_at reste vide : on garde l'inscription)
        if _has_table(conn, "price_alerts"):
            alert_cut = now - timedelta(days=ret.unconfirmed_alert_days)
            q = ("select count(*) from price_alerts" if dry_run else "delete from price_alerts") + \
                " where not confirmed and confirm_sent_at is not null and confirm_sent_at < :cut"
            r = conn.execute(text(q), {"cut": alert_cut})
            out["price_alerts (non confirmées)"] = (r.scalar() or 0) if dry_run else (r.rowcount or 0)
    return out


def sizes(engine: Engine, top: int = 8) -> tuple[Optional[float], list[tuple[str, float]]]:
    """Taille de la base et des plus grosses tables, en Mo (Postgres seulement)."""
    if engine.dialect.name != "postgresql":
        return None, []
    with engine.connect() as conn:
        total = conn.execute(text("select pg_database_size(current_database())")).scalar() / 1e6
        rows = conn.execute(text(
            "select relname, pg_total_relation_size(relid) from pg_catalog.pg_statio_user_tables "
            "order by 2 desc limit :n"), {"n": top}).all()
    return total, [(r[0], r[1] / 1e6) for r in rows]


def report(engine: Engine, result: dict[str, int], dry_run: bool) -> str:
    verb = "à supprimer" if dry_run else "supprimé(s)"
    lines = [f"{k:<55} {v:>8} {verb}" for k, v in result.items()]
    lines.append(f"{'Total':<55} {sum(result.values()):>8} {verb}")
    total, tables = sizes(engine)
    if total is not None:
        lines.append(f"Taille de la base : {total:.0f} Mo")
        lines += [f"  {n:<30} {s:>8.1f} Mo" for n, s in tables]
        if total > SIZE_WARNING_MB:
            lines.append(f"ATTENTION : la base dépasse {SIZE_WARNING_MB} Mo (limite de l'offre gratuite Neon : 1 Go).")
    return "\n".join(lines)
