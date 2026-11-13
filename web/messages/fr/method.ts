// Textes français (method) : référence. Ne pas changer un mot sans raison : la France doit rester identique.
const fr = {
  "method.meta.title": "Notre méthode",
  "method.title": "Notre méthode",
  "method.intro": "DoseHunt classe les compléments alimentaires selon leur <b>prix final réel par unité active</b> : ce que tu paies vraiment, code promo compris, divisé par ce que le produit contient vraiment.",

  "method.criterion.title": "Le critère de classement",
  "method.criterion.text": "Un seul critère : le prix comparé, du moins cher au plus cher. Trois façons de comparer, au choix :",
  "method.criterion.dose": "<b>Par dose d'actif</b> : {cur} par kg de protéine, de créatine, de collagène ou de glutamine, par 100 mg de caféine (pré-workout), par g de zinc ou de magnésium élément, par 100 000 UI de vitamine D, par g de vitamine C, par g d'EPA + DHA.",
  "method.criterion.kg": "<b>Par kg de produit</b> : le prix au poids, comme en magasin (poudres).",
  "method.criterion.unit": "<b>Par unité</b> : {cur} par barre, gélule ou comprimé.",
  "method.criterion.default": "Mode par défaut : {list}.",

  "method.group.title": "Un produit, une ligne",
  "method.group.text": "Chez un même marchand, les arômes et formats d'un même produit sont regroupés : seul le moins cher pour le mode choisi est affiché (« à partir de »). « Tous les formats et arômes », dans « + de filtres », les montre tous. Les produits en rupture de stock sont masqués par défaut.",

  "method.calc.title": "Le calcul",
  "method.calc.final": "Prix final = prix affiché − remise du meilleur code applicable",
  "method.calc.compared": "Prix comparé = prix final ÷ quantité d'actif, poids ou nombre d'unités du contenant entier",
  "method.calc.text": "Le calcul porte sur tout le contenant, jamais sur la portion déclarée. Il est affiché en entier sous chaque offre (« Voir le calcul »). Les frais de port ne sont pas encore pris en compte.",

  "method.real.title": "La teneur réelle",
  "method.real.text": "Seule compte la quantité d'actif lue dans le tableau nutritionnel ou la composition. « Gluconate de zinc 120 mg » désigne le poids du sel : le comprimé n'apporte que 15 mg de zinc. Une teneur hors de la fourchette attendue (par exemple 900 mg de zinc par gélule) est vérifiée par une personne avant d'apparaître. Une teneur supposée est signalée comme telle.",
  "method.real.combined": "Un produit qui apporte plusieurs actifs (whey + collagène, zinc + magnésium) apparaît dans chaque liste concernée, avec son prix entier attribué à l'actif de la liste et le badge « produit combiné ».",
  "method.real.claims": "« Fabriqué en France », « sans lactose », « sans édulcorant » ou l'origine du lait ne sont affichés que si la fiche du marchand le dit en toutes lettres, ou si sa liste d'ingrédients le montre. « Conçu en France » ou « marque française » ne suffisent pas. Une fiche muette est exclue du filtre correspondant.",

  "method.codes.title": "Les codes promo",
  "method.codes.text": "Le meilleur code valable est appliqué automatiquement, même s'il ne rapporte rien à DoseHunt. Chaque code est stocké avec ses conditions (remise, paliers, minimum de commande, première commande, date de fin) et sa date de dernière vérification. Sa fiabilité baisse avec le temps et avec les signalements « ne marche plus » ; sous un certain seuil, il reste affiché mais n'entre plus dans le prix. Les codes « première commande » sont exclus par défaut. Le prix sans code reste toujours visible.",

  "method.data.title": "D'où viennent les données",
  "method.data.text": "Les prix et teneurs sont relevés automatiquement sur les sites marchands : toutes les 4 heures pour les 50 meilleurs produits de chaque catégorie, toutes les 8 heures pour tous les autres et pour les codes promo affichés par les sites. La date du dernier relevé figure sous chaque offre. Nous relevons des données factuelles (prix, formats, teneurs, ingrédients, valeurs nutritionnelles, note moyenne des avis) ; la photo est affichée depuis le site du marchand.",

  "method.neutral.title": "Neutralité et rémunération",
  "method.neutral.paid": "Aucun emplacement payant dans le classement : un marchand ne peut pas acheter une meilleure place.",
  "method.neutral.nonAffiliated": "Les sites non affiliés apparaissent exactement comme les autres.",
  "method.neutral.affiliation": "DoseHunt se rémunère par l'affiliation : quand tu achètes après avoir cliqué sur « Voir l'offre », le marchand peut nous verser une commission, sans surcoût pour toi. Ces liens sont signalés (<code>rel=\"sponsored\"</code>).",
  "method.neutral.partners": "Des codes partenaires négociés avec des marques peuvent apparaître ; ils sont classés selon la même règle.",

  "method.not.title": "Ce que DoseHunt ne fait pas",
  "method.not.text": "DoseHunt compare des prix. Il ne donne aucun conseil de dosage ni d'avis médical, et ne vérifie pas la conformité réglementaire des produits : un produit livrable en France y est considéré comme vendu légalement.",

  "method.error.title": "Une erreur ?",
  "method.error.text": "Un prix, une teneur ou un code faux : écris-nous à contact@dosehunt.fr, ou indique sous l'offre si un code ne marche plus. Nous corrigeons vite, car un seul chiffre faux suffit à perdre ta confiance.",
} as const;
export default fr;
