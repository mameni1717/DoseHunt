"""Chargement des fichiers de configuration (sites, catégories, codes)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

CONFIG_DIR = Path(os.environ.get("DOSEHUNT_CONFIG", Path(__file__).resolve().parent.parent / "config"))


@dataclass
class Site:
    id: str
    name: str
    base_url: str
    platform: str
    collector: str
    status: str
    path_prefix: str = ""
    country: str = "FR"
    currency: str = "EUR"
    delay_seconds: float = 2.0
    page_size: int = 250
    filters: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    # Lien d'affiliation : {url} est remplacé par l'adresse de l'offre encodée. Vide = lien direct.
    # Exemple Awin : https://www.awin1.com/cread.php?awinmid=12345&awinaffid=67890&ued={url}
    affiliate_template: str = ""

    @property
    def root(self) -> str:
        return self.base_url.rstrip("/") + (self.path_prefix or "")

    def product_url(self, handle: str) -> str:
        return f"{self.root}/products/{handle}"


def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache
def sites() -> dict[str, Site]:
    data = _load("sites.yaml")
    defaults = data.get("defaults", {})
    out: dict[str, Site] = {}
    for raw in data["sites"]:
        merged = {**{k: v for k, v in defaults.items() if k in Site.__dataclass_fields__}, **raw}
        merged = {k: v for k, v in merged.items() if k in Site.__dataclass_fields__}
        out[raw["id"]] = Site(**merged)
    return out


def get_site(site_id: str) -> Site:
    try:
        return sites()[site_id]
    except KeyError as exc:
        raise SystemExit(f"Site inconnu : {site_id}. Sites : {', '.join(sites())}") from exc


@lru_cache
def categories() -> dict[str, dict]:
    return _load("categories.yaml")["categories"]


@lru_cache
def manual_actives() -> list[dict]:
    path = CONFIG_DIR / "manual_actives.yaml"
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("products", [])


def manual_for(site_id: str, external_id: str, title: str, category: Optional[str] = None) -> list[dict]:
    import re as _re
    out = []
    for m in manual_actives():
        if m["site"] != site_id or (category and m["category"] != category):
            continue
        key = str(m["match"])
        if key == str(external_id) or (not key.isdigit() and _re.search(key, title or "", _re.I)):
            out.append(m)
    return out


@lru_cache
def codes_config() -> dict:
    return _load("codes.yaml")


def database_url(explicit: Optional[str] = None) -> str:
    return explicit or os.environ.get("DOSEHUNT_DATABASE_URL", "sqlite:///dosehunt.db")


USER_AGENT = os.environ.get(
    "DOSEHUNT_USER_AGENT",
    "DoseHuntBot/0.1 (+https://dosehunt.fr/robot ; comparateur de prix ; contact@dosehunt.fr)",
)
