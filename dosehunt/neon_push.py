"""Copie la base locale vers Neon par son interface SQL en HTTPS.

Utile quand le port PostgreSQL (5432) n'est pas joignable mais que le web l'est (proxy d'entreprise, bac à sable).
En production, les collectes écrivent directement dans Neon (DOSEHUNT_DATABASE_URL) : cet outil sert au
démarrage, pour publier un premier relevé fait ailleurs.

Remplacement complet : les tables de Neon sont vidées puis remplies. À n'utiliser qu'avant la mise en service,
ou en connaissance de cause (les votes et clics enregistrés par le site seraient remplacés).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal

import httpx
from sqlalchemy import JSON, Integer, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateIndex, CreateTable

from . import db

log = logging.getLogger(__name__)
CHUNK = 250


class NeonHTTP:
    def __init__(self, url: str):
        self.url = url.replace("postgresql+psycopg://", "postgresql://").replace("postgres+psycopg://", "postgres://")
        host = re.search(r"@([^/:?]+)", self.url).group(1)
        self.endpoint = f"https://{host}/sql"
        self.client = httpx.Client(timeout=120)
        self.headers = {"Neon-Connection-String": self.url, "Content-Type": "application/json"}

    def query(self, sql: str, params: list | None = None) -> dict:
        r = self.client.post(self.endpoint, headers=self.headers, json={"query": sql, "params": params or []})
        if r.status_code >= 400:
            raise RuntimeError(f"Neon {r.status_code} : {r.text[:300]}")
        return r.json()

    def transaction(self, queries: list[tuple[str, list]]) -> None:
        body = {"queries": [{"query": q, "params": p} for q, p in queries]}
        r = self.client.post(self.endpoint, headers={**self.headers, "Neon-Batch-Isolation-Level": "ReadCommitted"}, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"Neon {r.status_code} : {r.text[:300]}")


def _value(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def create_schema(neon: NeonHTTP) -> None:
    dialect = postgresql.dialect()
    for table in db.metadata.sorted_tables:
        neon.query(str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)))
        for idx in table.indexes:
            neon.query(str(CreateIndex(idx, if_not_exists=True).compile(dialect=dialect)))
    for table, cols in db.LATE_COLUMNS.items():
        for name, sqltype in cols.items():
            neon.query(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {sqltype.replace('JSON', 'JSON')}")


def copy_engine(src: Engine, dst: Engine) -> dict[str, int]:
    """Copie complète d'une base vers une autre par connexion directe (ex. SQLite local → PostgreSQL local)."""
    from sqlalchemy import text
    db.init_db(dst)
    counts: dict[str, int] = {}
    tables = db.metadata.sorted_tables
    with dst.begin() as out:
        if dst.dialect.name == "postgresql":
            out.execute(text("TRUNCATE " + ", ".join(t.name for t in reversed(tables)) + " RESTART IDENTITY CASCADE"))
        with src.connect() as inp:
            for table in tables:
                rows = [dict(r._mapping) for r in inp.execute(select(table))]
                counts[table.name] = len(rows)
                if rows:
                    out.execute(table.insert(), rows)
                    if dst.dialect.name == "postgresql" and isinstance(getattr(table.c, "id", None) and table.c.id.type, Integer):
                        out.execute(text(f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), (SELECT max(id) FROM {table.name}))"))
    return counts


# Tables écrites par le site lui-même (clics) : jamais remplacées par l'envoi des collectes.
# Les alertes prix (price_alerts) sont créées par le site hors de ce schéma, donc jamais touchées non plus.
SITE_OWNED = {"click_log"}


def push(engine: Engine, neon_url: str) -> dict[str, int]:
    if engine.dialect.name == "sqlite" and engine.url.database:
        # Instantané cohérent : une collecte en cours peut écrire pendant l'envoi (offres et historique décalés).
        import sqlite3
        import tempfile
        from sqlalchemy import create_engine
        snap = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        src, dst = sqlite3.connect(engine.url.database, timeout=120), sqlite3.connect(snap)
        src.backup(dst)
        src.close()
        dst.close()
        engine = create_engine(f"sqlite:///{snap}", future=True)
    neon = NeonHTTP(neon_url)
    create_schema(neon)
    tables = [t for t in db.metadata.sorted_tables if t.name not in SITE_OWNED]
    neon.query("TRUNCATE " + ", ".join(t.name for t in reversed(tables)) + " RESTART IDENTITY CASCADE")
    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for table in tables:
            cols = [c.name for c in table.columns]
            is_json = [isinstance(c.type, JSON) for c in table.columns]
            rows = conn.execute(select(table)).all()
            counts[table.name] = len(rows)
            for i in range(0, len(rows), CHUNK):
                chunk = rows[i:i + CHUNK]
                params, values = [], []
                for row in chunk:
                    marks = []
                    for v, js in zip(row, is_json):
                        params.append(json.dumps(v, ensure_ascii=False) if js and v is not None else _value(v))
                        marks.append(f"${len(params)}")
                    values.append("(" + ", ".join(marks) + ")")
                neon.query(f"INSERT INTO {table.name} ({', '.join(cols)}) VALUES {', '.join(values)}", params)
            if "id" in cols and rows and isinstance(table.c.id.type, Integer):      # pas pour sites.id (texte)
                neon.query(f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id')::regclass, "
                           f"(SELECT max(id) FROM {table.name})::bigint)")
            log.info("%s : %d lignes", table.name, len(rows))
    return counts
