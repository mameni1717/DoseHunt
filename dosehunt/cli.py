"""Ligne de commande DoseHunt.

  dosehunt init                       crée les tables et charge sites, pays, codes
  dosehunt collect --site raptor      collecte un site
  dosehunt collect --platform shopify collecte tous les sites actifs d'une plateforme
  dosehunt collect --all              collecte tous les sites actifs
  dosehunt recompute                  recalcule l'index (après une modification des codes)
  dosehunt export -o data.json        exporte l'index pour le site
  dosehunt status                     fraîcheur et taux d'échec par site
  dosehunt review                     liste ce qui attend une revue humaine
  dosehunt review --fix ID --amount 15 --basis per_unit   corrige une teneur à la main
  dosehunt detect https://exemple.fr  détecte la plateforme d'un site
  dosehunt sites                      liste les 25 sites et leur état
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from sqlalchemy import and_, func, select, update

from . import db
from .config import get_site, sites


def _engine(args):
    engine = db.get_engine(args.db)
    db.init_db(engine)
    return engine


def cmd_init(args):
    from .pipeline import seed
    engine = _engine(args)
    seed(engine)
    print(f"Base prête ({engine.url.render_as_string(hide_password=True)}) : {len(sites())} sites chargés.")


def cmd_collect(args):
    from .pipeline import run_site, seed
    engine = _engine(args)
    seed(engine)
    if args.site:
        targets = [get_site(s) for s in args.site]
        refused = [t for t in targets if t.status in ("blocked", "paused") and not args.force]
        for t in refused:
            print(f"{t.name} : site {t.status} ({t.notes.strip()[:120]}…). Rien n'est envoyé ; --force pour passer outre.")
        targets = [t for t in targets if t not in refused]
        if not targets:
            return
    else:
        def runnable(s):
            if s.status == "active":
                return True
            # The Protein Works : s'active dès que l'URL du flux d'affiliation est fournie
            return s.status == "needs_feed" and bool(os.environ.get((s.filters or {}).get("feed_env", "")))
        targets = [s for s in sites().values() if runnable(s)
                   and (args.all or (args.platform and s.collector == args.platform))]
    if not targets:
        sys.exit("Aucun site à collecter : précise --site, --platform ou --all.")
    failed = 0
    for site in targets:
        st = run_site(engine, site, use_llm=not args.no_llm, limit=args.limit, reextract=args.reextract,
                      only_top=args.only_top)
        print(f"{site.name:<20} {st.products_seen:>5} produits  {st.products_in_scope:>4} dans nos catégories  "
              f"{st.offers_indexed:>5} offres indexées  {st.sent_to_review:>4} en revue  {st.pages_fetched:>3} pages lues  {st.llm_calls:>3} appels IA")
        failed += st.products_seen == 0
    sys.exit(1 if failed == len(targets) else 0)


def cmd_codes(args):
    """Relève les codes promo affichés par les sites, puis recalcule l'index."""
    from .pipeline import recompute_index, seed, store_found_codes
    engine = _engine(args)
    seed(engine)
    targets = [get_site(s) for s in args.site] if args.site else [s for s in sites().values() if s.status == "active"]
    from .codes import collect_site_shipping
    from .pipeline import store_shipping
    from .codes import survey_site_codes
    from .pipeline import top_product_urls
    for site in targets:
        try:
            products = sorted(top_product_urls(engine, site.id, 50))[:2]   # 2 fiches phares : codes affichés sur les fiches
        except Exception:                                # noqa: BLE001
            products = []
        found, pages_read = survey_site_codes(site, products)
        st = store_found_codes(engine, site, found, pages_read=pages_read)
        try:
            th, free_codes, ev = collect_site_shipping(site)
            th = th if th is not None else (site.filters or {}).get("free_shipping_from")
            store_shipping(engine, site, th, free_codes, ev)
            print(f"{site.name:<20} livraison offerte : {'dès ' + format(th, 'g') + ' €' if th else 'seuil non trouvé'}"
                  f"{' ; codes ' + ', '.join(free_codes) if free_codes else ''}")
        except Exception as exc:                         # noqa: BLE001
            print(f"{site.name:<20} livraison : lecture impossible ({exc})")
        desc = ", ".join(f"{f.code} ({'/'.join(str(t['pct']) + '%' + (' dès ' + str(int(t['min'])) + '€' if t['min'] else '') for t in f.tiers)})"
                         for f in found) or "aucun"
        print(f"{site.name:<20} {desc}  [{st['new']} nouveau(x), {st['confirmed']} confirmé(s), "
              f"{st.get('missed', 0)} absent(s) cette fois ; {pages_read} page(s) lue(s) dont {len(products)} fiche(s)]")
    if not args.no_recompute:
        print(f"{recompute_index(engine)} lignes d'index recalculées.")


def cmd_alerts(args):
    from .alerts import run
    st = run(_engine(args))
    print(f"Alertes : {st['checked']} vérifiées, {st['alerts_sent']} e-mail(s) envoyé(s), {st['confirmations']} confirmation(s) envoyée(s).")


def cmd_sites_json(args):
    import json
    print(json.dumps([k for k, v in sites().items() if v.status == "active"
                      or (v.status == "needs_feed" and os.environ.get((v.filters or {}).get("feed_env", "")))]))


def cmd_gaps(args):
    """Rayons du marchand vs produits classés chez nous : ce qui manque, par site et par catégorie."""
    from sqlalchemy import select, and_
    from .collectors import collector_for
    from .rayons import rayon_map
    from . import db as _db
    engine = _engine(args)
    targets = [get_site(s) for s in args.site] if args.site else [s for s in sites().values() if s.status == "active"]
    for site in targets:
        try:
            rmap = rayon_map(collector_for(site))
        except Exception as exc:                         # noqa: BLE001
            print(f"{site.name:<20} rayons illisibles ({exc})")
            continue
        with engine.connect() as conn:
            rows = conn.execute(select(_db.products.c.url, _db.products.c.external_id, _db.product_actives.c.category,
                                       _db.product_actives.c.status)
                                .select_from(_db.products.join(_db.product_actives, _db.product_actives.c.product_id == _db.products.c.id))
                                .where(and_(_db.products.c.site_id == site.id, _db.products.c.active.is_(True)))).all()
        have = {}
        for r in rows:
            for key in (r.url.split("?")[0] if r.url else "", r.external_id):
                have.setdefault((key, r.category), r.status)
        per_cat: dict[str, list] = {}
        for key, cats in rmap.items():
            for c in cats:
                per_cat.setdefault(c, []).append(key)
        for c, keys in sorted(per_cat.items()):
            ok = sum(1 for k in keys if have.get((k, c)) == "ok")
            review = sum(1 for k in keys if have.get((k, c)) == "review")
            missing = [k for k in keys if (k, c) not in have]
            print(f"{site.name:<20} {c:<11} rayon {len(keys):>4}  classés {ok:>4}  à vérifier {review:>4}  absents {len(missing):>4}"
                  + (f"  ex. {missing[0]}" if missing else ""))


def cmd_demo(args):
    from .demo import load_demo
    st = load_demo(_engine(args))
    print(f"Démonstration chargée : {st.products_in_scope} produits, {st.offers_indexed} offres indexées, "
          f"{st.sent_to_review} en revue.")


def cmd_push_neon(args):
    from .neon_push import push
    url = os.environ.get("DOSEHUNT_NEON_URL")
    if not url:
        sys.exit("Renseigne DOSEHUNT_NEON_URL (adresse de connexion Neon).")
    counts = push(_engine(args), url)
    print("Copié vers Neon : " + ", ".join(f"{t} {n}" for t, n in counts.items() if n))


def cmd_recompute(args):
    from .pipeline import recompute_index, seed
    engine = _engine(args)
    seed(engine)
    print(f"{recompute_index(engine)} lignes d'index recalculées.")


def cmd_export(args):
    from .export import write_export
    data = write_export(_engine(args), args.output, args.country)
    counts = ", ".join(f"{c['label']} {c['count']}" for c in data["categories"].values())
    print(f"{len(data['products'])} produits exportés vers {args.output} ({counts}).")


def cmd_purge(args):
    """Rétention : allège l'historique ancien et supprime ce qui ne sert plus (limite de stockage Neon)."""
    from .purge import Retention, purge, report
    ret = Retention(history_full_days=args.history_days, history_daily_days=args.history_weekly_after,
                    inactive_days=args.inactive_days, review_days=args.review_days, runs_days=args.runs_days,
                    codes_days=args.codes_days, unconfirmed_alert_days=args.alert_days)
    engine = _engine(args)
    print(report(engine, purge(engine, ret, dry_run=args.dry_run), args.dry_run))


def cmd_status(args):
    engine = _engine(args)
    r = db.collection_runs.c
    with engine.connect() as conn:
        last = select(r.site_id, func.max(r.id).label("mid")).group_by(r.site_id).subquery()
        runs = {x.site_id: x for x in conn.execute(select(db.collection_runs).join(last, r.id == last.c.mid)).mappings()}
        fails = dict(conn.execute(select(r.site_id, func.sum((r.status != "ok").cast(db.Integer)) * 1.0 / func.count())
                                  .group_by(r.site_id)).all())
        pending = dict(conn.execute(select(db.review_queue.c.site_id, func.count())
                                    .where(db.review_queue.c.resolved.is_(False)).group_by(db.review_queue.c.site_id)).all())
    print(f"{'Site':<20}{'Collecteur':<18}{'Dernière collecte':<20}{'État':<9}{'Offres':>7}{'Revue':>7}{'Échecs':>8}")
    for s in sites().values():
        run = runs.get(s.id)
        when = run["finished_at"].strftime("%d/%m %H:%M") if run and run["finished_at"] else "jamais"
        print(f"{s.name:<20}{s.collector:<18}{when:<20}{(run['status'] if run else s.status):<9}"
              f"{(run['offers_indexed'] if run else 0):>7}{pending.get(s.id, 0):>7}"
              f"{(f'{fails[s.id] * 100:.0f} %' if s.id in fails else '—'):>8}")


def cmd_review(args):
    engine = _engine(args)
    q = db.review_queue.c
    if args.fix:
        with engine.begin() as conn:
            item = conn.execute(select(db.review_queue).where(q.id == args.fix)).mappings().first()
            if not item:
                sys.exit(f"Revue {args.fix} introuvable.")
            pid = conn.execute(select(db.products.c.id).where(and_(
                db.products.c.site_id == item["site_id"],
                db.products.c.external_id == item["external_id"].split(":")[0]))).scalar_one()
            conn.execute(update(db.product_actives).where(and_(
                db.product_actives.c.product_id == pid, db.product_actives.c.category == item["category"]))
                .values(amount=args.amount, basis=args.basis or db.product_actives.c.basis, status="manual",
                        source="manual", confidence=1.0, note=args.note))
            conn.execute(update(db.review_queue).where(q.id == args.fix).values(resolved=True))
        print("Teneur corrigée à la main. Elle sera reprise à la prochaine collecte du site "
              f"(dosehunt collect --site {item['site_id']}).")
        return
    with engine.connect() as conn:
        rows = conn.execute(select(db.review_queue).where(q.resolved.is_(False))
                            .order_by(q.site_id, q.reason).limit(args.limit)).mappings().all()
    if args.json:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1, default=str))
        return
    for r in rows:
        title = (r["payload"] or {}).get("title", "")
        print(f"#{r['id']:<5} {r['site_id']:<16} {r['category'] or '':<11} {r['reason']:<15} {title[:45]:<46} {r['detail']}")
    print(f"\n{len(rows)} élément(s) en attente.")


def cmd_detect(args):
    from .detect import detect
    for url in args.urls:
        d = detect(url)
        print(f"{url} → {d.platform} (collecteur conseillé : {d.suggested_collector}) ; {'; '.join(d.evidence)}")


def cmd_sites(args):
    for s in sites().values():
        print(f"{s.id:<17} {s.name:<20} {s.platform:<24} {s.collector:<18} {s.status}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dosehunt", description="Collectes automatiques DoseHunt")
    ap.add_argument("--db", help="URL de la base (sinon DOSEHUNT_DATABASE_URL, sinon sqlite:///dosehunt.db)")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    c = sub.add_parser("collect")
    c.add_argument("--site", action="append")
    c.add_argument("--platform", help="collecteur : shopify, shopify_headless, prestashop, magento, page, affiliate_feed")
    c.add_argument("--all", action="store_true")
    c.add_argument("--no-llm", action="store_true", help="ne pas appeler l'IA en secours")
    c.add_argument("--limit", type=int, help="nombre maximal de produits (essais)")
    c.add_argument("--reextract", action="store_true", help="relire toutes les teneurs (après une amélioration des règles)")
    c.add_argument("--force", action="store_true", help="collecter même un site marqué blocked ou paused")
    c.add_argument("--only-top", type=int, metavar="N",
                   help="ne relire que les fiches du top N de chaque catégorie et sous-catégorie (Shopify : tout, c'est une requête)")
    c.set_defaults(func=cmd_collect)
    k = sub.add_parser("codes", help="relève les codes promo affichés par les sites")
    k.add_argument("--site", action="append")
    k.add_argument("--no-recompute", action="store_true")
    k.set_defaults(func=cmd_codes)
    sub.add_parser("recompute").set_defaults(func=cmd_recompute)
    sub.add_parser("alerts", help="envoie les alertes prix (e-mails) après une collecte").set_defaults(func=cmd_alerts)
    g = sub.add_parser("gaps", help="compare les rayons des marchands aux produits classés (ce qui manque)")
    g.add_argument("--site", action="append")
    g.set_defaults(func=cmd_gaps)
    sub.add_parser("sites-json", help="liste JSON des sites à collecter (matrice GitHub Actions)").set_defaults(func=cmd_sites_json)
    sub.add_parser("push-neon", help="copie la base locale vers Neon par HTTPS (remplacement complet)").set_defaults(func=cmd_push_neon)
    sub.add_parser("demo", help="charge le jeu de démonstration (relevé du prototype, 11/11/2026)").set_defaults(func=cmd_demo)
    e = sub.add_parser("export")
    e.add_argument("-o", "--output", default="dosehunt-index.json")
    e.add_argument("--country", default="FR")
    e.set_defaults(func=cmd_export)
    pu = sub.add_parser("purge", help="rétention : allège l'historique ancien, supprime ce qui ne sert plus")
    pu.add_argument("--dry-run", action="store_true", help="compter sans supprimer")
    pu.add_argument("--history-days", type=int, default=90, help="historique complet sur N jours (défaut 90)")
    pu.add_argument("--history-weekly-after", type=int, default=400, help="un relevé par semaine au-delà de N jours")
    pu.add_argument("--inactive-days", type=int, default=90, help="produits et offres inactifs depuis N jours")
    pu.add_argument("--review-days", type=int, default=30, help="revues résolues depuis N jours")
    pu.add_argument("--runs-days", type=int, default=60, help="journal des collectes au-delà de N jours")
    pu.add_argument("--codes-days", type=int, default=30, help="codes auto expirés ou retirés depuis N jours")
    pu.add_argument("--alert-days", type=int, default=7, help="alertes non confirmées N jours après la confirmation")
    pu.set_defaults(func=cmd_purge)
    sub.add_parser("status").set_defaults(func=cmd_status)
    r = sub.add_parser("review")
    r.add_argument("--limit", type=int, default=200)
    r.add_argument("--json", action="store_true")
    r.add_argument("--fix", type=int, help="id de la revue à corriger")
    r.add_argument("--amount", type=float)
    r.add_argument("--basis", choices=["per_100g", "per_unit"])
    r.add_argument("--note")
    r.set_defaults(func=cmd_review)
    d = sub.add_parser("detect")
    d.add_argument("urls", nargs="+")
    d.set_defaults(func=cmd_detect)
    sub.add_parser("sites").set_defaults(func=cmd_sites)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s : %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
