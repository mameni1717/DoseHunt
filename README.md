# DoseHunt

Deux parties : les **collectes** (ce dossier, Python) qui remplissent la base, et le **site** (`web/`, Next.js)
qui la lit. Voir `web/README.md` pour le site.

## Collectes automatiques

Le système qui alimente DoseHunt : il relève les catalogues des 25 sites, classe les produits dans
les 8 catégories, lit la teneur réelle en actif, contrôle sa cohérence, puis calcule et stocke
le prix final par unité active. La recherche du site lit cet index déjà calculé : aucune IA ni
aucun calcul au moment de la visite.

## Où on en est

Premier relevé réel le 11/11/2026. **19 sites collectés automatiquement**, 1 en listing seul (Nutripure),
4 sites refusent notre robot (accès à demander), 1 en pause.

| Collecteur | Sites | État au 11/11/2026 |
|---|---|---|
| `shopify` | Toutelanutrition, Body&Fit, Fitness Boutique, Raptor, Nutrimea, BioTechUSA, AM Nutrition | collectés |
| `shopify_headless` | Greenwhey | collecté |
| `prestashop` | Fitadium, Nutri&Co, STC Nutrition | collectés |
| `prestashop` (listing seul) | Nutripure | fiches refusées (403) ; prix du listing + teneurs de `config/manual_actives.yaml` |
| `magento` | EAFIT, HSN | collectés |
| `page` | Myprotein, Bulk, Zumub, Optigura, Eric Favre, nu3 (via Redcare) | collectés |
| — | **Nutrimuscle, Prozis, Decathlon** | **refusent notre robot** (403 ou 429) : on ne contourne pas, accès à demander |
| `affiliate_feed` | The Protein Works | défi Cloudflare : flux d'affiliation à fournir |
| — | AllNutrition | en pause (boutique polonaise, devise ambiguë) |

Un site qui refuse notre robot identifié n'est jamais contourné (pas de faux navigateur, pas de rotation
d'adresses) : on demande l'accès par un partenariat ou un flux d'affiliation, puis on repasse le site en `active`.

### Particularités par site

- **Myprotein** : tout est dans un JSON-LD ProductGroup (jusqu'à 138 déclinaisons format × parfum par fiche).
- **Prozis** : une fiche par format ; JSON-LD enveloppé dans des commentaires CDATA ; tableau nutritionnel
  chargé à part, lu sur `/product/nutrition-table`. Le prix affiché inclut déjà la promo du moment
  (BNOVEMBER) : le code n'est pas appliqué une seconde fois (`stackable_with_sale: false`).
- **Bulk** : une offre par déclinaison sans libellé ; le format est lu dans la référence
  (`BPB-PWPC-CHOC-0450` = chocolat, 450 g) ; prix barré dans `priceSpecification`.
- **HSN** (Magento 2 Hyvä) : déclinaisons, prix et prix barrés lus dans `initConfigurableOptions`.
  Fiches très lourdes (environ 7 Mo). Un tableau nutritionnel par parfum : le premier est retenu.
- **EAFIT** : une fiche par parfum et format. robots.txt interdit tout paramètre d'URL : aucun n'est utilisé.
- **Zumub** et **Optigura** : pas de sitemap, parcours des catégories. Optigura ne donne qu'une fourchette
  de prix en JSON-LD : tailles et prix sont lus dans la liste HTML de la fiche.
- **Decathlon** : sitemaps de tout le catalogue de sport ; seules les URL évoquant nos catégories sont ouvertes.
- **nu3** : plus de site propre. Décision prise : on suit les produits nu3 vendus par Redcare Pharmacie
  (page marque, 49 produits).
- **The Protein Works** : défi Cloudflare, même pour un vrai navigateur. Seule voie propre : son flux
  d'affiliation. Renseigner `DOSEHUNT_FEED_THEPROTEINWORKS` suffit à l'activer.
- **AllNutrition** : en pause. C'est une boutique internationale polonaise sans version française
  (allnutrition.fr n'existe pas) et la devise est ambiguë (titre « 29 € », données de prix « 29.9 PLN »).
  À réactiver (`status: active`) seulement après vérification de la devise et de la livraison en France.

### Règle commune aux collecteurs « fiches »

Une simple fourchette de prix (`AggregateOffer` sans détail) n'est jamais prise pour un prix. Sources, de la plus
fiable à la moins fiable : configuration Magento, JSON-LD avec une offre par déclinaison, liste HTML des tailles.
La zone lue pour les teneurs est la zone produit (description, onglets, tableau nutritionnel) : menus, avis et
blocs « produits liés » sont écartés pour ne pas lire la teneur d'un autre produit.

### Comment marche la collecte PrestaShop

1. **Découverte** : les pages catégories renvoient leur listing en JSON quand on les appelle comme le
   fait le site lui-même (en-tête `X-Requested-With`), 500 produits par page. Nutripure et STC ont une
   catégorie qui liste tout (`listing_urls`) ; Nutri&Co passe par son sitemap (`sitemap_product_pattern`) ;
   Fitadium par les catégories de sa page d'accueil.
2. **Pré-filtre** : seules les fiches dont le nom ou la catégorie relève de nos 8 catégories sont ouvertes.
3. **Fiche** : marque et description (JSON-LD), zone produit avec ses onglets (composition, tableau
   nutritionnel). Les blocs « produits liés » sont écartés pour ne pas lire la teneur d'un autre produit.
4. **Déclinaisons** : l'action « refresh » de la fiche donne le prix et le prix barré de chaque format.
   Fitadium l'interdit dans son robots.txt (`*?controller*`) : on prend alors le prix de la déclinaison
   par défaut. Chez Fitadium le format est en général dans le nom et les déclinaisons sont des parfums.

## Le circuit

```
collecteur (shopify / shopify_headless / …)
   → RawProduct : titre, type, tags, description HTML, variantes (format × parfum, prix, prix barré)
classify.py   → 0, 1 ou plusieurs catégories (plusieurs = produit combiné)
formats.py    → contenu du contenant : « Pot de 1,38kg », « 12x50g », « 2 boîtes », « 3 mois »…
extract.py    → teneur réelle : tableau nutritionnel > phrase explicite > hypothèse documentée
llm.py        → secours par l'IA si rien n'est trouvé (facultatif, mis en cache par fiche)
checks.py     → fourchettes par catégorie ; hors fourchette = revue humaine, pas d'index
pricing.py    → meilleur code applicable, puis € par dose d'actif, par kg, par unité
pipeline.py   → base de données, historique de prix, index calculé
export.py     → JSON lu par le site (même structure que le prototype)
```

## Installer

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[postgres,dev]"
export DOSEHUNT_DATABASE_URL=postgresql+psycopg://user:mdp@hote/dosehunt   # sinon SQLite local
dosehunt init
pytest -q                      # 71 tests sur des données tirées des vrais sites
```

## Utiliser

```bash
dosehunt collect --site raptor --limit 20 -v   # premier essai : 1 requête, 44 produits
dosehunt collect --platform shopify            # les 8 sites Shopify
dosehunt collect --platform prestashop         # les 4 sites PrestaShop
dosehunt collect --platform page               # les 8 sites sur-mesure
dosehunt collect --all                         # tous les sites actifs
dosehunt status                                # fraîcheur, offres indexées, revue, taux d'échec
dosehunt review                                # ce qui attend un humain
dosehunt review --fix 12 --amount 12.5 --basis per_unit --note "mg et non g sur la fiche"
dosehunt export -o index.json                  # pour le site
dosehunt codes                                 # relève les codes promo affichés par les sites, puis recalcule
dosehunt recompute                             # après modification de config/codes.yaml
dosehunt demo                                  # charge le jeu de démonstration (relevé du 11/11/2026)
dosehunt collect --site raptor --reextract     # relit toutes les teneurs après une amélioration des règles
dosehunt push-neon                             # copie la base locale vers Neon par HTTPS (DOSEHUNT_NEON_URL)
dosehunt detect https://www.exemple.fr         # plateforme d'un nouveau site
```

Planification : `deploy/crontab` (serveur) ou `.github/workflows/collect.yml` (GitHub Actions).

## Règles appliquées

- **Le piège du sel.** « Gluconate de zinc 120 mg » est relevé à part (`salt_label_mg`) et n'est
  jamais pris pour la teneur. Seule la quantité d'élément compte.
- **Dose sur plusieurs unités.** « 3 000 UI pour 2 gélules » donne 1 500 UI par gélule ;
  « dose journalière 1/2 comprimé » double la teneur par comprimé.
- **Formats en durée.** « 3 mois » devient 3 × 30 × la dose journalière lue sur la fiche.
- **Lots.** « 2 boîtes » multiplie le contenu d'une boîte lu dans le titre ; « 1.8 kg (2 produits) »
  reste 1,8 kg, le poids affiché étant déjà le total.
- **Prix barrés.** Un `compare_at_price` à 0, égal ou inférieur au prix est ignoré.
- **Erreurs des fiches.** BioTechUSA affiche « Zinc 12,5 g » au lieu de mg : la teneur sort de la
  fourchette, part en revue avec la mention « probable erreur d'unité ».
- **Hypothèses signalées.** Une teneur supposée (dose d'une gélule, créatine pure à 100 %) porte une
  note et une confiance réduite, visibles dans l'export.
- **Produits combinés.** Une whey + collagène apparaît dans chaque liste, prix entier attribué à
  l'actif de la liste, avec `combo: true`.
- **Relecture économe.** Les teneurs ne sont relues que si le texte de la fiche change ; une teneur
  corrigée à la main n'est jamais écrasée.
- **Prix suspects.** Une baisse de plus de 60 % d'un relevé à l'autre part en revue.
- **Produits disparus.** Retirés de l'index, gardés en base pour l'historique.

## Politesse envers les sites

Robot identifié (`DOSEHUNT_USER_AGENT`), robots.txt respecté avec ses jokers (`*`, `$` : le module
standard de Python les ignore, d'où `robots.py`), une requête à la fois par site avec
2 s de pause, reprise sur 429/503 en respectant `Retry-After`. Un site Shopify complet se relève en
1 à 9 requêtes. Seules les données factuelles sont stockées (prix, formats, teneurs) : ni photos ni
textes descriptifs, conformément à la section juridique du cahier des charges.

## Ajouter un site

1. `dosehunt detect https://site.fr` pour connaître la plateforme.
2. Ajouter une entrée dans `config/sites.yaml` (`collector: shopify` suffit pour un Shopify).
3. Filtres possibles : `product_type_in` (catalogues mélangés), `require_french` (catalogues multilingues).

## Limites connues

- Gouttes de vitamine D : le nombre de gouttes par flacon manque souvent, ces offres partent en revue.
- Minéraux en poudre (ex. magnésium en poudre d'Eric Favre, dosé par cuillère) : la catégorie compare par
  gélule ou comprimé, ces offres partent en revue faute de nombre d'unités.
- Le filtrage par URL (Myprotein, Prozis, Decathlon, HSN, EAFIT…) peut laisser passer un produit dont l'adresse
  n'évoque aucune de nos catégories : à surveiller au premier relevé.
- Durées : un site Shopify se relève en moins d'une minute ; un site « fiches » en 15 à 60 minutes à 2 s
  par requête.
- Body&Fit publie parfois des formats sans unité (« 45.0 ») : le titre sert alors de secours.
- Nutrimea mélange plusieurs langues : le filtre francophone écarte les fiches étrangères, au risque
  d'écarter une fiche française très courte.
- Les prix de Body&Fit et Nutrimea sont lus via leur préfixe `/fr-fr` : à recouper au premier relevé
  avec le prix affiché sur la fiche.

## Codes promo

- **Affichés par les sites** : `dosehunt codes` lit la page d'accueil (et les pages `code_pages` d'un site) toutes
  les 3 h. Paliers (« -20 % jusqu'à 69,99 €, -25 % dès 70 € »), minimums (« dès 80 € »), dates de fin,
  « première commande » et cumul avec les promos sont reconnus. Sans mention explicite, un code n'est pas cumulé
  avec un prix déjà barré (prudence : mieux vaut afficher un prix un peu trop haut qu'un prix faux).
- **Saisis à la main** (`config/codes.yaml`, origine `manual`) : jamais écrasés par le relevé automatique, qui
  confirme seulement qu'ils sont toujours affichés.
- **Fiabilité** : demi-vie de 90 jours depuis la dernière confirmation, +0,05 par vote « marche », -0,15 par vote
  « ne marche plus » ; sous 0,5 le code reste affiché mais n'entre plus dans le prix.
- **Pas encore automatisés** : codes d'influenceurs et agrégateurs (Dealabs, Poulpeo, iGraal).

## Premier relevé réel (11/11/2026) : ce qu'il a appris

- **Sites qui refusent notre robot** : Nutrimuscle (403), Prozis (429 de Cloudflare), Decathlon (403 sur les fiches).
  Ils sont marqués `status: blocked` et `dosehunt collect` refuse de les solliciter, même nommément, sauf `--force`.
  On ne contourne pas un refus : demander un accès ou un flux d'affiliation.
- **Description Shopify incomplète** : quand le catalogue JSON n'a pas la composition, la page produit est lue une
  fois (onglets, tableau nutritionnel), puis mise en cache tant que la fiche ne change pas.
- **Tableaux qui n'en sont pas** : tableaux en `<div>` (EAFIT), portion indiquée dans un attribut `data-label`
  (Optigura), tableaux injectés en JavaScript : convertis en vrais tableaux avant lecture.
- **Doses** : l'en-tête du tableau (« Pour 3 comprimés ») donne le nombre d'unités ; « par dose » sans nombre est
  tranché par le titre (« 112,5 mg » par comprimé pour 225 mg par dose = 2 comprimés). Une teneur qui dépasse ce
  que le sel peut contenir (346 mg de magnésium dans 1 000 mg de malate) part en revue.
- **Barres** : une teneur supérieure à la moitié du poids de la barre est en réalité « pour 100 g » : convertie,
  avec une note et une confiance réduite.
- **Formats** : format le plus cité sur la page (« 900g - 30 portions ») en secours ; « Boite de 12 », « Lot de 24 »,
  « x 32 » pour les barres ; échantillons d'une portion écartés ; packs mélangeant plusieurs produits écartés.
- **Codes « jusqu'à »** : « JUSQU'À -36 % avec GREENFRIDAY » est un plafond, pas une remise uniforme : affiché, non
  appliqué au prix.
- `dosehunt collect --reextract` relit toutes les teneurs après une amélioration des règles ; les revues qui ne se
  reproduisent pas lors d'une collecte complète sont closes automatiquement.

## Publier dans Neon

Le port PostgreSQL n'étant pas toujours joignable (bac à sable, réseau d'entreprise), `dosehunt push-neon` copie la
base locale vers Neon par HTTPS (remplacement complet, avec `DOSEHUNT_NEON_URL`). Le site utilise le pilote
serverless de Neon (WebSocket sur le port 443) dès que `DATABASE_URL` pointe vers Neon.

## Mises à jour automatiques (GitHub Actions)

`.github/workflows/collect.yml` collecte directement dans Neon (secret `DOSEHUNT_NEON_URL`), un job par site :

- toutes les 8 h (2 h, 10 h, 18 h UTC) : tous les produits, puis `dosehunt codes` (codes affichés par les sites), puis `dosehunt alerts` ;
- entre deux (6 h, 14 h, 22 h UTC) : `dosehunt collect --only-top 50` (les fiches du top 50 de chaque catégorie et sous-catégorie ; Shopify relit tout, c'est une seule requête), puis les alertes.

Lancer à la main : onglet Actions > Collecte DoseHunt > Run workflow (scope `full` ou `top`, un site ou tous).

Une fois ces collectes en place, Neon est la base de référence : ne plus utiliser `dosehunt push-neon`, qui remplace tout
(sauf les clics et les alertes prix, qui appartiennent au site).

## Alertes prix

Le site enregistre les inscriptions (table `price_alerts`, créée par le site). `dosehunt alerts` envoie la confirmation puis
les alertes par l'API Resend : secrets `RESEND_API_KEY` et `ALERT_FROM` (adresse d'un domaine vérifié chez Resend), dans
GitHub Actions et dans Vercel. Sans clé, les inscriptions restent en attente et rien n'est envoyé.
