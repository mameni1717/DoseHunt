"""Classement d'un produit dans les 8 catégories (et sous-catégories de whey)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from .collectors.base import html_to_text
from .config import Site, categories
from .models import RawProduct


@dataclass
class Classification:
    category: str
    subcategory: Optional[str] = None
    combined: bool = False          # le produit est aussi dans une autre catégorie


@lru_cache
def _compiled():
    out = {}
    for cid, c in categories().items():
        out[cid] = {
            "include": [re.compile(p, re.I) for p in c.get("include", [])],
            "exclude": [re.compile(p, re.I) for p in c.get("exclude", [])],
            "require_any": [re.compile(p, re.I) for p in c.get("require_any", [])],
            "type_exclude": [t.lower() for t in c.get("product_type_exclude", [])],
            "subs": {k: [re.compile(p, re.I) for p in v] for k, v in (c.get("subcategories") or {}).items()},
        }
    return out


FR_MARKERS = re.compile(r"\b(le|la|les|des|du|une|pour|avec|sans|est|et|par|vos|votre|chaque)\b|[éèêàùç]", re.I)
FOREIGN_MARKERS = re.compile(
    r"\b(het|een|voor|met|und|mit|für|der|die|das|il|della|delle|degli|per il|con|sono|the|with|and|for|your|"
    r"el|los|las|para|y|es|del|una|al|gli|di|che|ogni|cada|apoyo|sostegno)\b|[ñ¿¡]|ción\b|zione\b", re.I)
FOREIGN_TITLE = re.compile(r"col[áa]geno|magnesio|vitamina|zinco|bisglicinato|integratore|suplemento|proteína|omega 3 de", re.I)


def looks_french(p: RawProduct) -> bool:
    if FOREIGN_TITLE.search(p.title):
        return False
    text = (p.title + " " + html_to_text(p.body_html)[:1500]).lower()
    fr = len(FR_MARKERS.findall(text))
    foreign = len(FOREIGN_MARKERS.findall(text))
    return fr >= max(3, foreign * 1.5)


def passes_site_filters(p: RawProduct, site: Site) -> tuple[bool, str]:
    f = site.filters or {}
    allowed = f.get("product_type_in")
    if allowed and (p.product_type or "") not in allowed:
        return False, f"type « {p.product_type} » hors {allowed}"
    if f.get("require_french") and not looks_french(p):
        return False, "fiche non francophone"
    return True, ""


# Packs mélangeant plusieurs produits (« Pack Trio Barres », « Coffret découverte ») : teneur et format ambigus.
MIXED_PACK = re.compile(r"\b(pack|coffret|bundle|assortiment|box|kit|routine|programme|cure compl[eè]te|trio)\b", re.I)


# Actifs typiques d'un pré-workout : un produit du rayon sans nom explicite doit en citer au moins deux.
PRE_ACTIVES_RX = [re.compile(x, re.I) for x in (
    r"caf[ée]ine", r"citrulline", r"b[êe]ta[- ]?alanine", r"arginine", r"b[ée]ta[iï]ne", r"taurine",
    r"tyrosine", r"nitrate", r"agmatine", r"glyc[ée]rol", r"ornithine", r"guarana")]


def looks_preworkout(p: RawProduct) -> bool:
    # La description d'abord : la page entière cite aussi les produits suggérés (« vous aimerez aussi »).
    body = p.body_html or ""
    if len(re.sub(r"<[^>]+>", "", body)) < 200 and p.page_html:
        from .collectors.page import zone_html
        body = zone_html(p.page_html)
    text = p.title + " " + body
    return sum(1 for r in PRE_ACTIVES_RX if r.search(text)) >= 2


def classify(p: RawProduct, site: Optional[Site] = None) -> list[Classification]:
    if site is not None and not passes_site_filters(p, site)[0]:
        return []
    if MIXED_PACK.search(p.title):
        return []
    haystack = " ".join([p.title, p.product_type or "", " ".join(p.tags)])
    ptype = (p.product_type or "").lower()
    found: list[Classification] = []
    for cid, rx in _compiled().items():
        if not any(r.search(haystack) for r in rx["include"]):
            continue
        if any(r.search(p.title) for r in rx["exclude"]):
            continue
        if any(t and t in ptype for t in rx["type_exclude"]):
            continue
        if rx["require_any"] and not any(r.search(haystack) for r in rx["require_any"]):
            continue
        sub = None
        if rx["subs"]:
            title_type = p.title + " " + (p.product_type or "")
            sub = next((k for k, rs in rx["subs"].items() if rs and any(r.search(title_type) for r in rs)), None)
            sub = sub or next((k for k, rs in rx["subs"].items() if not rs), None)
        found.append(Classification(cid, sub))
    # Nom muet (« Evobomb », « Animal Fury ») : la catégorie du rayon du marchand, si le nom ne la contredit pas.
    if not found and p.rayon_categories:
        compiled = _compiled()
        for cid in p.rayon_categories:
            rx = compiled.get(cid)
            if rx is None or any(r.search(p.title) for r in rx["exclude"]):
                continue
            if cid == "barres" and not any(r.search(haystack) for r in rx["require_any"]):
                continue                                    # rayon « barres, boissons et gels » : pas une barre sans le mot
            if cid == "preworkout" and not looks_preworkout(p):
                continue                                    # rayon « pré-entraînement » : BCAA, sirops, greens s'y glissent
            sub = None
            if rx["subs"]:
                title_type = p.title + " " + (p.product_type or "")
                sub = next((k for k, rs in rx["subs"].items() if rs and any(r.search(title_type) for r in rs)), None)
                sub = sub or next((k for k, rs in rx["subs"].items() if not rs), None)
            found.append(Classification(cid, sub))
    # Une barre protéinée n'est pas aussi une whey, même si « whey » figure dans son nom.
    ids = {c.category for c in found}
    if "barres" in ids:
        found = [c for c in found if c.category not in ("whey",)]
    if len(found) > 1:
        for c in found:
            c.combined = True
    return found
