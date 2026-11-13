"""Alertes prix : après chaque collecte, un e-mail quand un produit (ou le meilleur d'une catégorie) passe sous le seuil.

Les inscriptions sont faites sur le site (table price_alerts, créée par le site). Les e-mails partent par l'API Resend
quand RESEND_API_KEY est défini ; sans clé, rien n'est envoyé et les alertes restent en attente.
Une alerte ne prévient qu'une fois par passage sous le seuil : elle se réarme quand le prix remonte au-dessus.
"""
from __future__ import annotations

import html
import logging
import os
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)

DDL = """create table if not exists price_alerts (
    id serial primary key, email varchar(254) not null, product_id integer, category varchar(40) not null,
    subcategory varchar(40), mode varchar(10) not null default 'dose', threshold double precision not null,
    country varchar(2) not null default 'FR', token varchar(64) not null unique, confirmed boolean not null default false,
    active boolean not null default true, confirm_sent_at timestamptz, last_notified_at timestamptz,
    last_value double precision, created_at timestamptz not null default now())"""

COLUMN = {"price": "i.final_price", "dose": "i.dose_value", "kg": "i.kg_value", "unit": "i.unit_value"}
UNIT = {"price": "€"}


def site_url() -> str:
    return os.environ.get("SITE_URL", "https://dosehunt.com").rstrip("/")


def send(to: str, subject: str, body_html: str) -> bool:
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return False
    r = httpx.post("https://api.resend.com/emails", timeout=20, headers={"authorization": f"Bearer {key}"},
                   json={"from": os.environ.get("ALERT_FROM", "DoseHunt <alertes@dosehunt.fr>"), "to": to,
                         "subject": subject, "html": body_html})
    if r.status_code >= 300:
        log.warning("e-mail refusé par Resend (%s) : %s", r.status_code, r.text[:200])
    return r.status_code < 300


def current(conn, a) -> Optional[tuple[float, str, Optional[int]]]:
    """(valeur actuelle, nom du produit, id produit) : la meilleure offre en stock visée par l'alerte."""
    col = COLUMN.get(a.mode, "i.dose_value")
    where = ["i.category = :cat", "i.country = :country", "o.active", "o.available", "p.active", f"{col} is not null"]
    params = {"cat": a.category, "country": a.country}
    if a.product_id:
        where.append("p.id = :pid")
        params["pid"] = a.product_id
    elif a.subcategory:
        where.append("i.subcategory = :sub")
        params["sub"] = a.subcategory
    row = conn.execute(text(f"""select {col} as v, coalesce(p.brand || ' ', '') || p.name as name, p.id as pid
                                 from index_rows i join offers o on o.id = i.offer_id join products p on p.id = o.product_id
                                where {' and '.join(where)} order by {col} limit 1"""), params).first()
    return (float(row.v), row.name, row.pid) if row else None


def run(engine: Engine) -> dict[str, int]:
    stats = {"confirmations": 0, "alerts_sent": 0, "checked": 0}
    with engine.begin() as conn:
        conn.execute(text(DDL if engine.dialect.name == "postgresql" else DDL.replace("serial primary key", "integer primary key")
                          .replace("timestamptz", "timestamp").replace("now()", "CURRENT_TIMESTAMP")))
    if not os.environ.get("RESEND_API_KEY"):
        log.warning("RESEND_API_KEY absent : aucune alerte envoyée (les inscriptions restent en attente)")
    with engine.begin() as conn:
        pending = conn.execute(text("""select id, email, token from price_alerts
                                        where active and not confirmed and confirm_sent_at is null""")).all()
        for a in pending:
            link = f"{site_url()}/api/alerts/confirm?token={a.token}"
            if send(a.email, "Confirme ton alerte prix DoseHunt",
                    f"<p>Bonjour,</p><p>Pour activer ton alerte prix, clique ici : <a href=\"{link}\">confirmer l'alerte</a>.</p>"
                    "<p>Si tu n'es pas à l'origine de cette demande, ignore ce message.</p>"):
                conn.execute(text("update price_alerts set confirm_sent_at = CURRENT_TIMESTAMP where id = :id"), {"id": a.id})
                stats["confirmations"] += 1
        alerts = conn.execute(text("select * from price_alerts where active and confirmed")).all()
        for a in alerts:
            stats["checked"] += 1
            cur = current(conn, a)
            if cur is None:
                continue
            value, name, pid = cur
            below = value < a.threshold
            armed = a.last_notified_at is None or (a.last_value is not None and a.last_value >= a.threshold)
            sent = False
            if below and armed:
                unit = UNIT.get(a.mode, "")
                where = f"{site_url()}/p/{pid}" if pid else f"{site_url()}/c/{a.category}"
                stop = f"{site_url()}/api/alerts/stop?token={a.token}"
                sent = send(a.email, f"Baisse de prix : {name} à {value:.2f}{(' ' + unit) if unit else ''}".replace(".", ","),
                            f"<p><b>{html.escape(name)}</b> est passé sous ton seuil de {a.threshold:.2f} : "
                            f"<b>{value:.2f}</b>{(' ' + unit) if unit else ''} (selon le mode choisi).</p>"
                            f"<p><a href=\"{where}\">Voir l'offre sur DoseHunt</a></p>"
                            f"<p style=\"color:#777\">Les prix changent vite : vérifie le prix chez le marchand avant d'acheter. "
                            f"<a href=\"{stop}\">Ne plus recevoir cette alerte</a>.</p>")
                stats["alerts_sent"] += int(sent)
            conn.execute(text("update price_alerts set last_value = :v" + (", last_notified_at = CURRENT_TIMESTAMP" if sent else "")
                              + " where id = :id"), {"v": value, "id": a.id})
    return stats
