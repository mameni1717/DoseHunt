"""Rayons des marchands : la catégorie d'un produit donnée par le site lui-même.

Le nom d'un produit ne dit pas toujours ce qu'il est (« Evobomb », « Animal Fury » sont des pré-workouts).
Les rayons du marchand (« Pré-entraînement », « Créatine »…) le disent. Ce module :
  1. détecte les rayons dans les menus du site (`dosehunt rayons-detect`, résultat relu et gardé dans config/rayons.yaml) ;
  2. les parcourt à chaque collecte, pages suivantes comprises, et rend {adresse de fiche: {catégories}}.
La catégorie du rayon ne sert que si le nom du produit ne permet pas de le classer.
"""
from __future__ import annotations

import html as htmllib
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlsplit

import yaml

log = logging.getLogger(__name__)

RAYONS_FILE = Path(__file__).resolve().parent.parent / "config" / "rayons.yaml"

# Mots d'un lien de menu (texte ou adresse) qui désignent un rayon de nos catégories
KEYWORDS = {
    "preworkout": r"pr[ée][- ]?work[- ]?out|pr[ée][- ]?(?:entra[iî]nement|training)|pre[- ]?entrenamiento|boosters?\b|formules?[- ]pre",
    "creatine": r"cr[ée]atine",
    "whey": r"\bwhey\b|prot[ée]ines?[- ](?:en[- ]poudre|de[- ]lactos|v[ée]g[ée]tales?|vegan)|isolats?[- ]de[- ]prot|cas[ée]ines?|clear[- ]whey",
    "collagene": r"collag[eè]ne",
    "barres": r"barres?[- ](?:prot[ée]in|hyperprot)|protein[- ]bars?",
    "zinc": r"\bzinc\b",
    "magnesium": r"magn[ée]sium",
    "vitamine_d": r"vitamines?[- ]d3?\b",
    "vitamine_c": r"vitamines?[- ]c\b",
    "omega3": r"om[ée]ga[- ]?3|huiles?[- ]de[- ]poisson",
    "glutamine": r"glutamine",
}
# Liens qui ressemblent à un rayon mais n'en sont pas
NOT_A_RAYON = re.compile(r"blog|conseil|guide|recette|actualit|magazine|article|avis|faq|marques?/|brand|/pages?/|"
                         r"compte|panier|cart|login|contact|livraison|cgv|mentions|parrain|fidelit|programme|"
                         r"quiz|calculat|comparatif|meilleur|sexualit|libido|testost|sans-|snack|pack|best-?seller|"
                         r"low-carb|tags/|promo|outlet|nouveaut|cadeau|-gh\b|hormon|sommeil|immun", re.I)


def load() -> dict[str, dict[str, list[str]]]:
    if not RAYONS_FILE.exists():
        return {}
    return yaml.safe_load(RAYONS_FILE.read_text(encoding="utf-8")) or {}


def detect(site, client, product_rx: Optional[re.Pattern] = None) -> dict[str, list[str]]:
    """Liens de menu de la page d'accueil qui mènent aux rayons de nos catégories (au plus 4 par catégorie)."""
    start = site.root.rstrip("/") + "/"
    resp = client.get(start, accept_404=True)
    if resp is None:
        return {}
    host = urlsplit(site.base_url).netloc
    found: dict[str, list[str]] = {}
    for m in re.finditer(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', resp.text, re.I | re.S):
        url = urljoin(start, htmllib.unescape(m.group(1))).split("?")[0].rstrip("/")
        if urlsplit(url).netloc != host or NOT_A_RAYON.search(url):
            continue
        if product_rx is not None and product_rx.search(url):
            continue                                        # fiche produit, pas un rayon
        if site.collector in ("shopify",) and "/collections/" not in url:
            continue                                        # Shopify : un rayon est une collection
        if site.collector == "prestashop" and url.endswith(".html"):
            continue                                        # PrestaShop : les fiches finissent en .html, pas les rayons
        if site.path_prefix and not urlsplit(url).path.startswith(site.path_prefix):
            continue
        text = re.sub(r"<[^>]+>|\s+", " ", htmllib.unescape(m.group(2))).strip()
        slug = urlsplit(url).path.rsplit("/", 1)[-1]
        for cat, rx in KEYWORDS.items():
            if re.search(rx, text, re.I) or re.search(rx, slug.replace("-", " "), re.I):
                lst = found.setdefault(cat, [])
                if url not in lst and len(lst) < 4:
                    lst.append(url)
    return found


def _paginate(url: str, page: str, n: int) -> Optional[str]:
    """Adresse de la page n du rayon si le site en annonce une (?p=, ?page=, /page/n)."""
    for pat in (rf'href="([^"]*[?&](?:p|page|pg)={n}\b[^"]*)"', rf'href="([^"]*/page/{n}/?)"'):
        m = re.search(pat, page, re.I)
        if m:
            return urljoin(url, htmllib.unescape(m.group(1)))
    return None


def shopify_rayon(client, site, url: str, max_pages: int = 10) -> set[str]:
    """Rayon Shopify (/collections/x) : identifiants des produits par l'API JSON de la collection."""
    path = urlsplit(url).path.rstrip("/")
    ids: set[str] = set()
    for p in range(1, max_pages + 1):
        data = client.get_json(f"{site.base_url.rstrip('/')}{path}/products.json?limit=250&page={p}", accept_404=True)
        prods = (data or {}).get("products") or []
        ids |= {str(x["id"]) for x in prods}
        if len(prods) < 250:
            break
    return ids


def html_rayon(client, url: str, product_rx: re.Pattern, max_pages: int = 15, nested: bool = False) -> set[str]:
    """Rayon HTML : liens de fiches produit de la page et des pages suivantes.

    nested : le site range ses fiches sous l'adresse du rayon (Zumub) ; on ne garde que celles-là, pas le menu."""
    links: set[str] = set()
    prefix = url.rstrip("/") + "/"
    current: Optional[str] = url
    host = urlsplit(url).netloc
    for n in range(2, max_pages + 2):
        resp = client.get(current, accept_404=True) if current else None
        if resp is None:
            break
        before = len(links)
        for href in re.findall(r'href="([^"#]+)"', resp.text):
            link = urljoin(current, htmllib.unescape(href)).split("#")[0].split("?")[0]
            if urlsplit(link).netloc == host and product_rx.search(link) and (not nested or link.startswith(prefix)
                                                                            or re.search(r"-p-\d+$", link)):
                links.add(link)
        if len(links) == before:
            break                                           # page sans nouvelle fiche : fin du rayon
        current = _paginate(current, resp.text, n)
    return links


def rayon_map(collector) -> dict[str, set[str]]:
    """{identifiant (Shopify) ou adresse de fiche : catégories des rayons où elle figure} pour ce site."""
    site = collector.site
    rayons = load().get(site.id) or {}
    out: dict[str, set[str]] = {}
    if not rayons:
        return out
    shopify = site.collector == "shopify"
    presta = site.collector == "prestashop"
    if presta:
        collector._rayon_meta = {}
    rx = None
    if not shopify and not presta:
        pat = (site.filters or {}).get("rayon_product_pattern") or (site.filters or {}).get("product_pattern")
        rx = re.compile(pat) if pat else None
    for cat, urls in rayons.items():
        for url in urls:
            try:
                if presta:
                    metas = collector.listing(url)
                    collector._rayon_meta.update(metas)
                    keys = set(metas)
                elif shopify:
                    keys = shopify_rayon(collector.client, site, url)
                else:
                    keys = html_rayon(collector.client, url, rx, nested=bool((site.filters or {}).get("rayon_nested"))) if rx else set()
            except Exception as exc:                        # noqa: BLE001 — un rayon illisible n'arrête pas la collecte
                log.info("%s : rayon illisible %s (%s)", site.id, url, exc)
                continue
            for k in keys:
                out.setdefault(k, set()).add(cat)
            log.info("%s : rayon %s → %d fiches (%s)", site.id, url, len(keys), cat)
    return out
