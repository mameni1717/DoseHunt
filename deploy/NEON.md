# Neon : réglages pour consommer le moins possible

Neon facture (ou décompte, sur l'offre gratuite) le temps pendant lequel la base est allumée, multiplié par sa
taille (« CU-heures »), plus le stockage. Le code fait déjà sa part : le site interroge Neon en HTTP sans garder
de connexion ouverte, et la collecte ferme toutes ses connexions à la fin de chaque commande. Il reste trois
réglages à faire une fois dans la console Neon.

> Les libellés des menus ci-dessous viennent de la documentation Neon et peuvent légèrement varier :
> vérifier sur https://neon.com/docs/manage/computes et https://neon.com/docs/guides/autoscaling-guide.

## 1. Taille de la base (autoscaling)

1. Console Neon → projet DoseHunt → **Branches** → branche principale (`main` / `production`).
2. Onglet **Computes** → sur le compute principal, **Edit**.
3. **Autoscaling** : minimum **0.25 CU**, maximum **0.5 CU**.
   - Si les collectes deviennent nettement plus lentes (journaux GitHub), passer le maximum à **1 CU**.
   - Ne pas laisser 2 CU : une collecte peut alors consommer jusqu'à 8 fois plus qu'à 0.25 CU.
4. **Save**.

## 2. Mise en veille (scale to zero)

Dans le même écran **Edit** du compute : **Scale to zero** activé, délai **5 minutes**
(« Suspend compute after 5 minutes of inactivity »). Sur l'offre gratuite, ce délai est en principe fixé à
5 minutes et ne peut pas être désactivé : il suffit de vérifier qu'il est bien actif.

## 3. Adresse de connexion « pooler »

Console → **Connect** (ou **Connection details**) → cocher **Connection pooling** : l'adresse contient alors
`-pooler` dans le nom d'hôte. Utiliser cette adresse :

- dans Vercel → projet → **Settings** → **Environment Variables** → `DATABASE_URL` ;
- dans GitHub → dépôt → **Settings** → **Secrets and variables** → **Actions** → `DOSEHUNT_NEON_URL`.

## 4. Mot de passe (à faire avant le lancement public)

Le dépôt est public : par sécurité, réinitialiser le mot de passe du rôle de la base
(console → **Roles** → rôle utilisé → **Reset password**), puis remplacer l'adresse complète (avec `-pooler`)
dans les deux endroits du point 3. Redéployer le site sur Vercel après le changement de variable.

## 5. Suivre la consommation

Console → **Usage** (ou **Billing**) : CU-heures du mois, stockage, transfert.

Limites de l'offre gratuite (documentation Neon, octobre 2026) : 100 CU-heures par projet et par mois,
1 Go de stockage par projet, 5 Go de transfert. Au-delà :

- **CU-heures ou transfert épuisés** : la base est suspendue jusqu'au mois suivant → le site n'affiche plus de prix
  et les collectes échouent. Passer à l'offre Launch (paiement à l'usage) débloque immédiatement.
- **Stockage plein** : les écritures qui agrandissent la base sont refusées (les collectes échouent), la lecture
  continue. Libérer de la place (purge des anciennes données) ou passer à l'offre Launch.

Repère : à 0.25 CU, 100 CU-heures = 400 heures allumée par mois, soit environ 13 h par jour. Avec le cache des
pages, Neon n'est réveillée que par les collectes (6 par jour, de 20 à 90 minutes chacune).
