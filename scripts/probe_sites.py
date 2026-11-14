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
        if not fiche and locs:
            out["exemples"] = " ".join(locs[:3])
            fiche = locs[len(locs) // 2]
        if fiche:
            out["fiche"], html = code(c, fiche)
            out["json-ld"] = "oui" if html and "application/ld+json" in html else "non"
        print(f"{site.id:18} " + "  ".join(f"{k}={v}" for k, v in out.items()) + (f"  ({fiche})" if fiche else ""), flush=True)


def discover(site) -> None:
    """Adresses de fiches que trouverait la collecte (sitemaps, motifs, préfiltre), sans rien lire ni écrire en base."""
    import time
    from dosehunt.collectors import collector_for
    t = time.time()
    col = collector_for(site)
    try:
        urls = col.discover()
    except Exception as e:                               # noqa: BLE001
        print(f"{site.id:18} découverte impossible : {e}", flush=True)
        return
    from collections import Counter
    from urllib.parse import urlsplit
    tops = Counter("/".join(urlsplit(u).path.split("/")[:5]) for u in urls).most_common(40)
    print(f"{site.id:18} rubriques : {tops}", flush=True)
    print(f"{site.id:18} {len(urls)} fiches retenues en {time.time() - t:.0f} s ; exemples : {urls[:3]}", flush=True)


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--discover":
        for sid in args[1:]:
            discover(sites()[sid])
        return
    wanted = args
    for s in sites().values():
        if (wanted and s.id in wanted) or (not wanted and s.status in ("blocked", "decide")):
            try:
                probe(s)
            except Exception as e:                       # une sonde ne doit pas arrêter les autres
                print(f"{s.id:18} erreur : {e}", flush=True)


if __name__ == "__main__":
    main()
