"""Schéma de la base (SQLAlchemy Core) : PostgreSQL en production, SQLite en local.

Les 7 tables du cahier des charges (pays, sites, livraison, produits, offres, codes promo,
historique de prix), plus les tables de fonctionnement : teneurs par catégorie (produits
combinés), index calculé, revue humaine, journal des collectes.
"""
from __future__ import annotations

import re

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, MetaData, String,
                        Table, Text, UniqueConstraint, create_engine)
from sqlalchemy.engine import Engine

from .config import database_url

metadata = MetaData()

countries = Table(
    "countries", metadata,
    Column("code", String(2), primary_key=True),
    Column("name", String(64), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("vat_rate", Float),
    Column("language", String(5)),
)

sites = Table(
    "sites", metadata,
    Column("id", String(40), primary_key=True),
    Column("name", String(80), nullable=False),
    Column("platform", String(40)),
    Column("collector", String(40)),
    Column("status", String(20)),
    Column("affiliate_id", String(120)),
    Column("affiliate_template", Text),
    Column("base_url", String(200)),
    Column("country", String(2)),        # une entrée par marchand et par pays (myprotein-es) : pays du site
    Column("language", String(5)),       # langue des fiches (règles de lecture)
)

# Domaine par pays. Modèle retenu : une entrée sites.yaml par marchand ET par pays (myprotein-fr, myprotein-es),
# donc une seule ligne site_domains par site (écrite par seed, lue nulle part ailleurs pour l'instant).
site_domains = Table(
    "site_domains", metadata,
    Column("site_id", ForeignKey("sites.id"), primary_key=True),
    Column("country", ForeignKey("countries.code"), primary_key=True),
    Column("base_url", String(200), nullable=False),
    Column("ships_to", Boolean, default=True),
)

shipping = Table(                # phase 2
    "shipping", metadata,
    Column("site_id", ForeignKey("sites.id"), primary_key=True),
    Column("country", ForeignKey("countries.code"), primary_key=True),
    Column("fee", Float),
    Column("free_threshold", Float),
    Column("delay_days", String(20)),
)

products = Table(                # ce que contient le produit, tel que vendu par un site
    "products", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("site_id", ForeignKey("sites.id"), nullable=False),
    Column("external_id", String(80), nullable=False),
    Column("handle", String(255)),
    Column("brand", String(120)),
    Column("name", String(400), nullable=False),
    Column("product_type", String(120)),
    Column("canonical_key", String(255), index=True),   # marque + nom normalisés, pour regrouper entre sites
    Column("url", String(500)),
    Column("body_hash", String(64)),                    # relecture des teneurs seulement si la fiche change
    Column("content_hint", String(60)),                 # contenance lue sur la page produit (« 120 gélules »)
    Column("origin_country", String(2)),                # pays de fabrication déclaré sur la fiche (ISO : FR, IT…)
    Column("origin_evidence", String(200)),             # extrait qui le prouve
    Column("image_url", String(500)),                   # photo principale
    Column("rating", Float),                            # note moyenne des avis sur 5
    Column("review_count", Integer),
    Column("ingredients", Text),                        # liste d'ingrédients lue sur la fiche
    Column("nutrition", JSON),                          # valeurs pour 100 g {protein, fat, sugars, salt…}
    Column("attributes", JSON),                         # sans lactose, édulcorants, origine du lait… (filtres)
    Column("review_topics", JSON),                      # thèmes des avis publiés sur la fiche (goût, mélange…)
    Column("tags", JSON),
    Column("first_seen", DateTime(timezone=True)),
    Column("last_seen", DateTime(timezone=True)),
    Column("active", Boolean, default=True),
    UniqueConstraint("site_id", "external_id", name="uq_product_site"),
)

product_actives = Table(         # une ligne par catégorie : un produit combiné en a plusieurs
    "product_actives", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
    Column("category", String(20), nullable=False),
    Column("subcategory", String(20)),
    Column("combined", Boolean, default=False),
    Column("active", String(20)),
    Column("amount", Float),
    Column("unit", String(4)),
    Column("basis", String(20)),
    Column("source", String(20)),
    Column("confidence", Float),
    Column("evidence", Text),
    Column("units_per_dose", Float),
    Column("salt_label_mg", Float),
    Column("form", String(40)),
    Column("note", Text),
    Column("status", String(12), default="ok"),         # ok | review | manual
    Column("read_at", DateTime(timezone=True)),
    UniqueConstraint("product_id", "category", name="uq_active_cat"),
)

offers = Table(                  # un produit vendu sur un site dans un pays, dans un format
    "offers", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
    Column("site_id", ForeignKey("sites.id"), nullable=False),
    Column("country", ForeignKey("countries.code"), nullable=False),
    Column("variant_id", String(80), nullable=False),
    Column("variant_title", String(255)),
    Column("flavour", String(120)),
    Column("url", String(600)),
    Column("grams", Float),
    Column("units", Integer),
    Column("unit_word", String(20)),
    Column("unit_grams", Float),
    Column("format_label", String(120)),
    Column("format_confidence", Float),
    Column("price", Float, nullable=False),
    Column("compare_at_price", Float),
    Column("currency", String(3)),
    Column("available", Boolean),
    Column("collected_at", DateTime(timezone=True)),
    Column("active", Boolean, default=True),
    UniqueConstraint("site_id", "country", "variant_id", name="uq_offer_variant"),
)

promo_codes = Table(
    "promo_codes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("site_id", ForeignKey("sites.id"), nullable=False),
    Column("country", ForeignKey("countries.code"), nullable=False),
    Column("code", String(60), nullable=False),
    Column("discount_type", String(20)),
    Column("value", Float),
    Column("min_order", Float),
    Column("first_order_only", Boolean, default=False),
    Column("stackable_with_sale", Boolean, default=True),
    Column("applies_to", JSON),
    Column("source", Text),
    Column("confidence", Float),
    Column("last_confirmed", Date),
    Column("ends_on", Date),
    Column("votes_ok", Integer, default=0),
    Column("votes_ko", Integer, default=0),
    Column("tiers", JSON),                 # paliers : [{"min": 0, "pct": 20}, {"min": 70, "pct": 25}]
    Column("origin", String(10)),          # manual (codes.yaml) | auto (relevé sur le site)
    Column("missed_runs", Integer, default=0),   # relevés successifs où un code « auto » n'était plus affiché
    Column("evidence", Text),              # phrase du site où le code a été lu
    UniqueConstraint("site_id", "country", "code", name="uq_code"),
)

price_history = Table(
    "price_history", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("offer_id", ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("price", Float, nullable=False),
    Column("compare_at_price", Float),
    Column("best_code", String(60)),
    Column("final_price", Float),
    Column("available", Boolean),
)

index_rows = Table(              # l'index déjà calculé que lit la recherche : aucun calcul à la volée
    "index_rows", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("offer_id", ForeignKey("offers.id", ondelete="CASCADE"), nullable=False),
    Column("category", String(20), nullable=False),
    Column("subcategory", String(20)),
    Column("country", String(2), nullable=False),
    Column("final_price", Float),
    Column("code", String(60)),
    Column("total_active", Float),
    Column("active_unit", String(4)),
    Column("dose_value", Float, index=True),
    Column("kg_value", Float),
    Column("unit_value", Float),
    Column("unit_label", String(40)),
    Column("calc", JSON),
    Column("combined", Boolean),
    Column("computed_at", DateTime(timezone=True)),
    UniqueConstraint("offer_id", "category", name="uq_index_offer_cat"),
)

review_queue = Table(
    "review_queue", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("site_id", String(40), nullable=False),
    Column("external_id", String(80), nullable=False),
    Column("category", String(20)),
    Column("reason", String(30), nullable=False),
    Column("detail", Text),
    Column("payload", JSON),
    Column("created_at", DateTime(timezone=True)),
    Column("resolved", Boolean, default=False),
    UniqueConstraint("site_id", "external_id", "category", "reason", name="uq_review"),
)

collection_runs = Table(
    "collection_runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("site_id", String(40), nullable=False, index=True),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", String(12)),          # ok | partial | failed
    Column("requests", Integer),
    Column("products_seen", Integer),
    Column("products_in_scope", Integer),
    Column("offers_indexed", Integer),
    Column("sent_to_review", Integer),
    Column("llm_calls", Integer),
    Column("error", Text),
)


def get_engine(url: str | None = None) -> Engine:
    u = database_url(url)
    # Adresse Neon telle que copiée depuis leur console (« postgresql://… ») : pilote psycopg 3
    u = re.sub(r"^postgres(?:ql)?://", "postgresql+psycopg://", u)
    if u.startswith("sqlite"):
        # plusieurs collectes en parallèle (un processus par site) : attendre le verrou plutôt qu'échouer
        return create_engine(u, future=True, connect_args={"timeout": 120})
    # Postgres (Neon) : petit pool, connexions vérifiées avant usage (Neon a pu se mettre en veille) et recyclées,
    # pour que la base puisse s'éteindre dès la fin d'une collecte (scale to zero). cli.py ferme le pool en sortie.
    return create_engine(
        u, future=True, pool_size=2, max_overflow=2, pool_pre_ping=True, pool_recycle=300,
        connect_args={"connect_timeout": 15, "keepalives": 1, "keepalives_idle": 30,
                      "keepalives_interval": 10, "keepalives_count": 5},
    )


click_log = Table(               # clics vers les marchands (mesure de l'affiliation, sans donnée personnelle)
    "click_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("offer_id", Integer, index=True),
    Column("code", String(60)),
    Column("clicked_at", DateTime(timezone=True)),
)

code_votes = Table(              # retours « ce code marche / ne marche plus »
    "code_votes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code_id", ForeignKey("promo_codes.id", ondelete="CASCADE"), index=True),
    Column("works", Boolean, nullable=False),
    Column("voted_at", DateTime(timezone=True)),
    Column("fingerprint", String(64)),     # empreinte anonyme (hash) pour limiter les votes répétés
)

# Colonnes ajoutées après la première version : ajoutées aux bases existantes au démarrage.
LATE_COLUMNS = {"promo_codes": {"tiers": "JSON", "origin": "VARCHAR(10)", "evidence": "TEXT", "missed_runs": "INTEGER DEFAULT 0"},
                "sites": {"affiliate_template": "TEXT", "base_url": "VARCHAR(200)", "country": "VARCHAR(2)",
                          "language": "VARCHAR(5)"},
                "products": {"content_hint": "VARCHAR(60)", "origin_country": "VARCHAR(2)",
                             "origin_evidence": "VARCHAR(200)", "image_url": "VARCHAR(500)", "rating": "FLOAT",
                             "review_count": "INTEGER", "ingredients": "TEXT", "nutrition": "JSON",
                             "attributes": "JSON", "review_topics": "JSON"}}


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in LATE_COLUMNS.items():
            have = {c["name"] for c in insp.get_columns(table)}
            for name, sqltype in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}"))
        # Colonnes élargies après coup (« per_serving », « free_shipping » dépassent 10 caractères).
        if engine.dialect.name == "postgresql":
            for table, col, width in WIDENED:
                length = next((c["type"].length for c in insp.get_columns(table) if c["name"] == col), None)
                if length is not None and length < width:
                    conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE VARCHAR({width})"))


WIDENED = [("product_actives", "basis", 20), ("promo_codes", "discount_type", 20)]
