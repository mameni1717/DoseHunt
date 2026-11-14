"""Sonde polie des sites marqués « bloqués » : même robot déclaré et même client que la collecte (robots.txt respecté,
délai entre requêtes), lancée depuis GitHub Actions. Un refus vu depuis un autre réseau (bac à sable) n'est pas
forcément un refus du robot ; un 403/429 ici, si. Aucune tentative de contournement : on note le code, c'est tout.

Usage : python scripts/probe_sites.py [id_site ...]   (défaut : tous les sites blocked/decide)
"""
from __future__ import annotations

import re
import sys

from dosehunt.config import sites
from dosehunt.http import BlockedByRobots, FetchError, PoliteClient


def code(client: PoliteClient, url: str) -> tuple[str, str]:
    try:
        r = client.get(url, accept_404=True)
    except BlockedByRobots:
        return "robots", ""
    except FetchError as e:
        return str(e.status or "erreur"), ""
    if r is None:
        return "404", ""
    return str(r.status_code), r.text


def probe(site) -> None:
    root = site.root.rstrip("/")
    origin = re.match(r"https?://[^/]+", site.base_url).group(0)
    with PoliteClient(delay_seconds=max(3.0, site.delay_seconds), max_retries=1, language=site.language) as c:
        out = {}
        out["robots"], robots = code(c, origin + "/robots.txt")
        out["accueil"], _ = code(c, root + "/")
        if site.collector == "shopify":
            out["products.json"], _ = code(c, root + "/products.json?limit=1")
        sm = (site.filters or {}).get("sitemaps") or re.findall(r"(?im)^sitemap:\s*(\S+)", robots)[:1] or [origin + "/sitemap.xml"]
        sm_url = sm[0] if sm[0].startswith("http") else origin + sm[0]
        out["sitemap"], body = code(c, sm_url)
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body or "")
        if locs and "<sitemapindex" in (body or ""):
            child = next((u for u in locs if re.search(r"product|produc", u, re.I)), locs[0])
            out["sitemap enfant"], body = code(c, child)
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body or "")
        pat = (site.filters or {}).get("product_pattern")
        fiche = next((u for u in locs if (re.search(pat, u) if pat else re.search(r"\.html$|/products?/|/p/", u))), None)
        if fiche:
            out["fiche"], html = code(c, fiche)
            out["json-ld"] = "oui" if html and "application/ld+json" in html else "non"
        print(f"{site.id:18} " + "  ".join(f"{k}={v}" for k, v in out.items()) + (f"  ({fiche})" if fiche else ""), flush=True)


def main() -> None:
    wanted = sys.argv[1:]
    for s in sites().values():
        if (wanted and s.id in wanted) or (not wanted and s.status in ("blocked", "decide")):
            try:
                probe(s)
            except Exception as e:                       # une sonde ne doit pas arrêter les autres
                print(f"{s.id:18} erreur : {e}", flush=True)


if __name__ == "__main__":
    main()
