# Avancement : architecture multi-pays + Espagne

Branche : `multi-pays`. Ce fichier sert à reprendre le travail après une coupure (quota). À jour à chaque étape.

## Décisions prises
- Code de chemin `es`, ISO `ES`, langue `es`, locale `es-ES`, devise EUR.
- Une entrée `sites.yaml` par marchand et par pays (`myprotein-es`, `hsn-es`…), comme le recommande le brief.
- Traductions : `web/messages/<lang>/<espace>.ts`, `fr` = référence, fonction `t()` maison, test de complétude.
- Pages sous `web/app/[country]/`, réécriture dans `web/proxy.ts` (Next 16), France à la racine.

## État
- [x] Étape 0 : dépôt cloné, branche créée, code lu
- [~] Phase 1 web : FAIT country.ts, i18n (t/tp/rich), href, data.ts par pays + test anti-oubli, routage app/[country] + proxy.ts, layout + accueil + 404 traduits, sélecteur/bandeau/cookie/api/geo, sitemaps par pays, robots, seo.ts (hreflang). EN COURS (3 agents) : OfferCard/catégorie/recherche/vitamines ; fiche/comparer/alertes ; Optimiser/méthode/légal
- [ ] Phase 1 collecte : règles par langue, pays en base (agent)
- [ ] Phase 2 : tri des sites ES (agent), config, règles ES, collecte, codes, vérif en ligne
- [ ] Bilan + notification

## Journal
- 13/11 23:00 : démarrage.
- 14/11 00:30 : coupure quota à 23:40 ; agents relancés. Référence France enregistrée dans /home/claude/baseline (pages HTML du site en ligne avant chantier).
- Agents : tri ES → /home/claude/es-triage ; collecte par langue → worktree /home/claude/dh-collecte (branche multi-pays-collecte).
