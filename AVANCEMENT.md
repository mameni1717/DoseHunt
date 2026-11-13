# Avancement : architecture multi-pays + Espagne

Branche : `multi-pays`. Ce fichier sert à reprendre le travail après une coupure (quota). À jour à chaque étape.

## Décisions prises
- Code de chemin `es`, ISO `ES`, langue `es`, locale `es-ES`, devise EUR.
- Une entrée `sites.yaml` par marchand et par pays (`myprotein-es`, `hsn-es`…), comme le recommande le brief.
- Traductions : `web/messages/<lang>/<espace>.ts`, `fr` = référence, fonction `t()` maison, test de complétude.
- Pages sous `web/app/[country]/`, réécriture dans `web/proxy.ts` (Next 16), France à la racine.

## État
- [x] Étape 0 : dépôt cloné, branche créée, code lu
- [ ] Phase 1 web : country.ts, i18n, href, data.ts par pays, routage, textes, sélecteur, SEO
- [ ] Phase 1 collecte : règles par langue, pays en base (agent)
- [ ] Phase 2 : tri des sites ES (agent), config, règles ES, collecte, codes, vérif en ligne
- [ ] Bilan + notification

## Journal
- 13/11 23:00 : démarrage.
