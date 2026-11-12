# DoseHunt : site web

Next.js 16 (App Router) + PostgreSQL. Le site lit l'index déjà calculé par les collectes (`index_rows`) :
aucun appel d'IA ni recalcul lourd pendant une visite. Seuls les réglages de l'utilisateur (codes « 1re commande »,
codes activés ou non, mode de comparaison) sont appliqués à la volée, avec la même logique que la collecte.

## Pages

| URL | Rôle |
|---|---|
| `/` | Accueil : recherche et meilleure offre de chaque catégorie |
| `/c/[catégorie]` | Classement : type (whey), 3 modes, tous les formats, 1re commande, codes, filtres site / marque / forme |
| `/p/[id]` | Fiche : teneur réelle et sa source, toutes les offres, historique du prix, codes et vote |
| `/recherche?q=` | Recherche plein texte (accents ignorés) |
| `/methode` | Critères de classement, rémunération, neutralité (obligation légale, art. L111-7 du Code de la consommation) |
| `/go/[offre]` | Redirection vers le marchand (lien affilié si configuré), clic compté sans donnée personnelle |
| `POST /api/codes/[id]/vote` | « Ce code marche / ne marche plus » : un vote par personne, par code et par jour |

## Lancer en local

```bash
# 1. Une base remplie par les collectes, ou la démonstration :
cd .. && dosehunt --db postgresql+psycopg://user@localhost/dosehunt demo
# 2. Le site :
cd web && cp .env.example .env.local   # puis renseigner DATABASE_URL
npm install && npm run dev             # http://localhost:3000
npm test                               # tests du classement et des codes
```

## Mettre en ligne

1. Base PostgreSQL hébergée (Neon, Supabase, Scaleway…), à ton nom. Les collectes y écrivent
   (`DOSEHUNT_DATABASE_URL=postgresql+psycopg://…`), le site y lit (`DATABASE_URL=postgres://…`).
2. Projet Vercel pointant sur le dossier `web/`, variables `DATABASE_URL` et `VOTE_SALT` (chaîne aléatoire).
3. Liens d'affiliation : renseigner `affiliate_template` par site dans `config/sites.yaml`
   (ex. `https://www.awin1.com/cread.php?awinmid=…&awinaffid=…&ued={url}`), puis `dosehunt init`.
4. Retirer `DOSEHUNT_DEMO` (bandeau « données de démonstration ») dès que les vraies collectes tournent.
