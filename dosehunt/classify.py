"""Classement d'un produit dans les 8 catégories (et sous-catégories de whey)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from .collectors.base import html_to_text
from .config import Site, categories
from .lang import FOREIGN_MARKERS_COMPAT as FOREIGN_MARKERS, FR_FOREIGN_TITLE as FOREIGN_TITLE, FR_MARKERS, looks_language, norm
from .models import RawProduct


@dataclass
class Classification:
    category: str
    subcategory: Optional[str] = None
    combined: bool = False          # le produit est aussi dans une autre catégorie


def _rules(c: dict, lang: str) -> dict:
    """Règles d'une catégorie pour une langue : françaises, plus le bloc de la langue (`es:`) s'il existe."""
    extra = c.get(lang) if lang != "fr" else None
    if not extra:
        return c
    out = dict(c)
    for key in ("include", "exclude", "require_any", "product_type_exclude"):
        if extra.get(key):
            out[key] = list(c.get(key) or []) + list(extra[key])
    if extra.get("subcategories"):
        subs = {k: list(v) for k, v in (c.get("subcategories") or {}).items()}
        for k, v in extra["subcategories"].items():
            subs[k] = subs.get(k, []) + list(v or [])
        out["subcategories"] = subs
    return out


@lru_cache
def _compiled(lang: str = "fr"):
    out = {}
    for cid, c0 in categories().items():
        c = _rules(c0, lang)
        out[cid] = {
            "include": [re.compile(p, re.I) for p in c.get("include", [])],
            "exclude": [re.compile(p, re.I) for p in c.get("exclude", [])],
            "require_any": [re.compile(p, re.I) for p in c.get("require_any", [])],
            "type_exclude": [t.lower() for t in c.get("product_type_exclude", [])],
            "subs": {k: [re.compile(p, re.I) for p in v] for k, v in (c.get("subcategories") or {}).items()},
        }
    return out


def _lang(site: Optional[Site]) -> str:
    return norm(site.language) if site is not None else "fr"


def looks_french(p: RawProduct) -> bool:
    return looks_language_product(p, "fr")


def looks_language_product(p: RawProduct, lang: str) -> bool:
    """La fiche (titre + début de la description) est-elle dans la langue `lang` ?"""
    return looks_language(p.title + " " + html_to_text(p.body_html)[:1500], lang, title=p.title)


def passes_site_filters(p: RawProduct, site: Site) -> tuple[bool, str]:
    f = site.filters or {}
    allowed = f.get("product_type_in")
    if allowed and (p.product_type or "") not in allowed:
        return False, f"type « {p.product_type} » hors {allowed}"
    if f.get("require_french") and not looks_french(p):      # ancien nom, gardé : vérifie le français
        return False, "fiche non francophone"
    if f.get("require_language") and not looks_language_product(p, site.language):
        return False, f"fiche pas en langue du site ({site.language})"
    return True, ""


# Packs mélangeant plusieurs produits (« Pack Trio Barres », « Coffret découverte ») : teneur et format ambigus.
MIXED_PACK = re.compile(r"\b(pack|coffret|bundle|assortiment|box|kit|routine|programme|cure compl[eè]te|trio)\b", re.I)
# Espagnol : « pack, lote, kit, set, estuche, surtido… » (« caja de 12 barritas » reste un produit unique)
MIXED_PACK_LANG = {"es": re.compile(r"\b(lotes?|sets?|estuches?|surtidos?|tr[íi]o|rutina|programa|packs?)\b", re.I)}


def _mixed_pack(title: str, lang: str) -> bool:
    if MIXED_PACK.search(title):
        return True
    rx = MIXED_PACK_LANG.get(lang)
    return bool(rx and rx.search(title))


# Actifs typiques d'un pré-workout : un produit du rayon sans nom explicite doit en citer au moins un.
PRE_ACTIVES_RX = [re.compile(x, re.I) for x in (
    r"caf[ée]ine", r"citrulline", r"b[êe]ta[- ]?alanine", r"arginine", r"b[ée]ta[iï]ne", r"taurine",
    r"tyrosine", r"nitrate", r"agmatine", r"glyc[ée]rol", r"ornithine", r"guarana")]
PRE_ACTIVES_LANG = {"es": [re.compile(x, re.I) for x in (
    r"cafe[íi]na", r"citrulina", r"beta[- ]?alanina", r"arginina", r"beta[íi]na", r"taurina",
    r"tirosina", r"nitratos?", r"agmatina", r"glicerol", r"ornitina", r"guaran[áa]")]}


def looks_preworkout(p: RawProduct, lang: str = "fr") -> bool:
    # La description d'abord : la page entière cite aussi les produits suggérés (« vous aimerez aussi »).
    body = p.body_html or ""
    if len(re.sub(r"<[^>]+>", "", body)) < 200 and p.page_html:
        from .collectors.page import zone_html
        body = zone_html(p.page_html)
    text = p.title + " " + body
    rxs = PRE_ACTIVES_RX + PRE_ACTIVES_LANG.get(lang, [])
    return any(r.search(text) for r in rxs)   # « Knockout » : caféine seule, mais bien un booster


def classify(p: RawProduct, site: Optional[Site] = None, lang: Optional[str] = None) -> list[Classification]:
    """`lang` : règles d'une langue sans passer de site (préfiltre d'adresses) ; sinon la langue du site, ou « fr »."""
    if site is not None and not passes_site_filters(p, site)[0]:
        return []
    lang = norm(lang) if lang else _lang(site)
    if _mixed_pack(p.title, lang):
        return []
    haystack = " ".join([p.title, p.product_type or "", " ".join(p.tags)])
    ptype = (p.product_type or "").lower()
    found: list[Classification] = []
    for cid, rx in _compiled(lang).items():
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
        compiled = _compiled(lang)
        for cid in p.rayon_categories:
            rx = compiled.get(cid)
            if rx is None or any(r.search(p.title) for r in rx["exclude"]):
                continue
            if cid == "barres" and not any(r.search(haystack) for r in rx["require_any"]):
                continue                                    # rayon « barres, boissons et gels » : pas une barre sans le mot
            if cid == "preworkout" and not looks_preworkout(p, lang):
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
