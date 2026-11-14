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


# E-mails dans la langue du pays de l'alerte, liens vers la bonne version du site (France à la racine, /es…).
PREFIX = {"FR": "", "ES": "/es"}
MAIL = {
    "fr": {
        "confirm_subject": "Confirme ton alerte prix DoseHunt",
        "confirm_body": "<p>Bonjour,</p><p>Pour activer ton alerte prix, clique ici : <a href=\"{link}\">confirmer l'alerte</a>.</p>"
                        "<p>Si tu n'es pas à l'origine de cette demande, ignore ce message.</p>",
        "drop_subject": "Baisse de prix : {name} à {value}",
        "drop_body": "<p><b>{name}</b> est passé sous ton seuil de {threshold} : <b>{value}</b> (selon le mode choisi).</p>"
                     "<p><a href=\"{where}\">Voir l'offre sur DoseHunt</a></p>"
                     "<p style=\"color:#777\">Les prix changent vite : vérifie le prix chez le marchand avant d'acheter. "
                     "<a href=\"{stop}\">Ne plus recevoir cette alerte</a>.</p>",
    },
    "es": {
        "confirm_subject": "Confirma tu alerta de precio de DoseHunt",
        "confirm_body": "<p>Hola:</p><p>Para activar tu alerta de precio, haz clic aquí: <a href=\"{link}\">confirmar la alerta</a>.</p>"
                        "<p>Si no has pedido esta alerta, ignora este mensaje.</p>",
        "drop_subject": "Bajada de precio: {name} a {value}",
        "drop_body": "<p><b>{name}</b> ha bajado de tu precio límite de {threshold}: <b>{value}</b> (según el modo elegido).</p>"
                     "<p><a href=\"{where}\">Ver la oferta en DoseHunt</a></p>"
                     "<p style=\"color:#777\">Los precios cambian rápido: comprueba el precio en la tienda antes de comprar. "
                     "<a href=\"{stop}\">No recibir más esta alerta</a>.</p>",
    },
}
LANG = {"FR": "fr", "ES": "es"}


def _lang(country: Optional[str]) -> str:
    return LANG.get((country or "FR").upper(), "fr")


def site_url() -> str:
    return os.environ.get("SITE_URL", "https://dosehunt.com").rstrip("/")


def send(to: str, subject: str, body_html: str) -> bool:
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return False
    r = httpx.post("https://api.resend.com/emails", timeout=20, headers={"authorization": f"Bearer {key}"},
                   json={"from": os.environ.get("ALERT_FROM") or "DoseHunt <alertes@dosehunt.com>", "to": to,   # secret absent = chaîne vide dans GitHub
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
        pending = conn.execute(text("""select id, email, token, country from price_alerts
                                        where active and not confirmed and confirm_sent_at is null""")).all()
        for a in pending:
            link = f"{site_url()}/api/alerts/confirm?token={a.token}"
            M = MAIL[_lang(a.country)]
            if send(a.email, M["confirm_subject"], M["confirm_body"].format(link=link)):
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
                base = site_url() + PREFIX.get((a.country or "FR").upper(), "")
                where = f"{base}/p/{pid}" if pid else f"{base}/c/{a.category}"
                stop = f"{site_url()}/api/alerts/stop?token={a.token}"
                M = MAIL[_lang(a.country)]
                shown = f"{value:.2f}{(' ' + unit) if unit else ''}"
                sent = send(a.email, M["drop_subject"].format(name=name, value=shown).replace(".", ","),
                            M["drop_body"].format(name=html.escape(name), threshold=f"{a.threshold:.2f}", value=shown,
                                                  where=where, stop=stop))
                stats["alerts_sent"] += int(sent)
            conn.execute(text("update price_alerts set last_value = :v" + (", last_notified_at = CURRENT_TIMESTAMP" if sent else "")
                              + " where id = :id"), {"v": value, "id": a.id})
    return stats
