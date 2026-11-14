"""Les valeurs de config/sites.yaml doivent tenir dans les colonnes de la base : SQLite (tests locaux) ne vérifie
pas les longueurs de varchar, Postgres (Neon) refuse et la collecte entière échoue (bulk-es, 14/11/2026)."""
from sqlalchemy import String

from dosehunt import db
from dosehunt.config import sites


def test_sites_tiennent_dans_les_colonnes():
    cols = {c.name: c.type.length for c in db.sites.columns if isinstance(c.type, String) and c.type.length}
    for s in sites().values():
        row = {"id": s.id, "name": s.name, "platform": s.platform, "collector": s.collector, "status": s.status,
               "base_url": s.root, "country": s.country, "language": s.language}
        for k, v in row.items():
            if k in cols and v is not None:
                assert len(str(v)) <= cols[k], f"{s.id}.{k} = {v!r} dépasse varchar({cols[k]})"
