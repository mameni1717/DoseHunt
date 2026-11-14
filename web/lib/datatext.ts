// Textes écrits par la collecte (en français) et affichés tels quels : notes de calcul, noms des actifs du
// pré-workout, thèmes des avis, source des codes relevés. En France ils restent inchangés ; ailleurs ils sont
// traduits ici, d'après la liste finie des phrases que produit la collecte (dosehunt/extract.py, details.py,
// pipeline.py). Une phrase inconnue reste telle quelle.

import type { Lang } from "./country.ts";

type Rule = [RegExp, string];

const NUM = String.raw`([\d.,]+)`;

const ES: Rule[] = [
  // notes de teneur (extract.py)
  [/^tableau par portion seulement : valeur ramenée à 100 g$/, "tabla solo por dosis: valor convertido a 100 g"],
  [new RegExp(`^calculé : ${NUM} g pour ${NUM} g$`), "calculado: $1 g por cada $2 g"],
  [/^calculé : protéines par portion ÷ poids de la portion$/, "calculado: proteína por dosis ÷ peso de la dosis"],
  [/^calculé : quantité par portion ÷ poids de la portion$/, "calculado: cantidad por dosis ÷ peso de la dosis"],
  [/^calculé : caféine par dose ÷ poids de la dose$/, "calculado: cafeína por dosis ÷ peso de la dosis"],
  [/^dose d'une unité supposée \(la fiche ne précise pas le nombre d'unités par dose\)$/, "dosis de una unidad supuesta (la ficha no indica cuántas unidades por dosis)"],
  [/^dose d'une unité supposée$/, "dosis de una unidad supuesta"],
  [/^dose d'une capsule supposée$/, "dosis de una perla supuesta"],
  [new RegExp(`^${NUM} mg lus pour une dose ; ${NUM} mg par unité d'après le titre$`), "$1 mg leídos por dosis; $2 mg por unidad según el título"],
  [/^ramené à 100 g depuis la colonne « par portion »$/, "convertido a 100 g desde la columna «por dosis»"],
  [/^ramené à 100 g depuis la dose$/, "convertido a 100 g desde la dosis"],
  [/^créatine monohydrate pure supposée \(100 %\), sans autre ingrédient déclaré dans le titre$/, "creatina monohidrato pura supuesta (100 %), sin otro ingrediente indicado en el título"],
  [/^portion recommandée par la marque$/, "dosis recomendada por la marca"],
  [new RegExp(`^${NUM} g lus pour une barre de ${NUM} g : pris comme valeur pour 100 g$`), "$1 g leídos para una barrita de $2 g: tomado como valor por 100 g"],
  [new RegExp(`^${NUM} g pour 100 g × barre de ${NUM} g$`), "$1 g por 100 g × barrita de $2 g"],
  [/^teneur par barre supposée \(seule teneur citée sur la fiche\)$/, "cantidad por barrita supuesta (única cantidad citada en la ficha)"],
  [/^peptides de collagène : teneur en protéines prise comme teneur en collagène$/, "péptidos de colágeno: proteína tomada como colágeno"],
  [new RegExp(`^portion de ${NUM} g$`), "dosis de $1 g"],
  // actifs du pré-workout (details.py)
  [/^Caféine$/, "Cafeína"], [/^Citrulline malate$/, "Citrulina malato"], [/^Citrulline$/, "Citrulina"],
  [/^Bêta-alanine$/, "Beta-alanina"], [/^Créatine$/, "Creatina"], [/^Bétaïne$/, "Betaína"],
  // thèmes des avis (details.py)
  [/^Goût$/, "Sabor"], [/^Mélange$/, "Mezcla"], [/^Digestion$/, "Digestión"], [/^Texture$/, "Textura"],
  [/^Efficacité$/, "Eficacia"], [/^Prix$/, "Precio"], [/^Emballage et doseur$/, "Envase y dosificador"],
  // source des codes relevés automatiquement (pipeline.py)
  [/^affiché sur le site \(relevé automatique\) : livraison offerte$/, "mostrado en la web (lectura automática): envío gratis"],
  [/^affiché sur le site \(relevé automatique\) ; remise « jusqu'à », variable selon les produits : affichée mais non appliquée au prix$/,
   "mostrado en la web (lectura automática); descuento «hasta», variable según el producto: se muestra pero no se aplica al precio"],
  [/^affiché sur le site \(relevé automatique\)$/, "mostrado en la web (lectura automática)"],
];

const RULES: Partial<Record<Lang, Rule[]>> = { es: ES };

export function dataText(lang: Lang, s: string | null | undefined): string {
  if (!s) return "";
  const rules = RULES[lang];
  if (!rules) return s;
  const t = s.trim();
  for (const [rx, out] of rules) if (rx.test(t)) return t.replace(rx, out);
  return s;
}
