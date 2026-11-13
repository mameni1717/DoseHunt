import type { Metadata } from "next";
import { CATEGORIES } from "@/lib/categories";

export const metadata: Metadata = { title: "Notre méthode" };

// Page exigée par les règles de loyauté des plateformes (Code de la consommation, art. L111-7 et D111-7) :
// critères de classement, existence de liens rémunérés, référencement payant.
export default function Methode() {
  return (
    <article className="prose">
      <h1>Notre méthode</h1>
      <p>
        DoseHunt classe les compléments alimentaires selon leur <b>prix final réel par unité active</b> : ce que tu paies
        vraiment, code promo compris, divisé par ce que le produit contient vraiment.
      </p>

      <h2>Le critère de classement</h2>
      <p>Un seul critère : le prix comparé, du moins cher au plus cher. Trois façons de comparer, au choix :</p>
      <ul>
        <li><b>Par dose d'actif</b> : € par kg de protéine, de créatine, de collagène ou de glutamine, par 100 mg de caféine (pré-workout), par g de zinc ou de magnésium élément, par 100 000 UI de vitamine D, par g de vitamine C, par g d'EPA + DHA.</li>
        <li><b>Par kg de produit</b> : le prix au poids, comme en magasin (poudres).</li>
        <li><b>Par unité</b> : € par barre, gélule ou comprimé.</li>
      </ul>
      <p>Mode par défaut : {CATEGORIES.map((c) => `${c.label.toLowerCase()} (${c.modes[c.defaultMode]!.label.toLowerCase()})`).join(", ")}.</p>

      <h2>Un produit, une ligne</h2>
      <p>
        Chez un même marchand, les arômes et formats d'un même produit sont regroupés : seul le moins cher pour le mode
        choisi est affiché (« à partir de »). « Tous les formats et arômes », dans « + de filtres », les montre tous.
        Les produits en rupture de stock sont masqués par défaut.
      </p>

      <h2>Le calcul</h2>
      <p><code>Prix final = prix affiché − remise du meilleur code applicable</code></p>
      <p><code>Prix comparé = prix final ÷ quantité d'actif, poids ou nombre d'unités du contenant entier</code></p>
      <p>
        Le calcul porte sur tout le contenant, jamais sur la portion déclarée. Il est affiché en entier sous chaque offre
        (« Voir le calcul »). Les frais de port ne sont pas encore pris en compte.
      </p>

      <h2>La teneur réelle</h2>
      <p>
        Seule compte la quantité d'actif lue dans le tableau nutritionnel ou la composition. « Gluconate de zinc 120 mg »
        désigne le poids du sel : le comprimé n'apporte que 15 mg de zinc. Une teneur hors de la fourchette attendue
        (par exemple 900 mg de zinc par gélule) est vérifiée par une personne avant d'apparaître. Une teneur supposée est
        signalée comme telle.
      </p>
      <p>
        Un produit qui apporte plusieurs actifs (whey + collagène, zinc + magnésium) apparaît dans chaque liste concernée,
        avec son prix entier attribué à l'actif de la liste et le badge « produit combiné ».
      </p>
      <p>
        « Fabriqué en France », « sans lactose », « sans édulcorant » ou l'origine du lait ne sont affichés que si la fiche du
        marchand le dit en toutes lettres, ou si sa liste d'ingrédients le montre. « Conçu en France » ou « marque française »
        ne suffisent pas. Une fiche muette est exclue du filtre correspondant.
      </p>

      <h2>Les codes promo</h2>
      <p>
        Le meilleur code valable est appliqué automatiquement, même s'il ne rapporte rien à DoseHunt. Chaque code est
        stocké avec ses conditions (remise, paliers, minimum de commande, première commande, date de fin) et sa date de
        dernière vérification. Sa fiabilité baisse avec le temps et avec les signalements « ne marche plus » ; sous un
        certain seuil, il reste affiché mais n'entre plus dans le prix. Les codes « première commande » sont exclus par
        défaut. Le prix sans code reste toujours visible.
      </p>

      <h2>D'où viennent les données</h2>
      <p>
        Les prix et teneurs sont relevés automatiquement sur les sites marchands : toutes les 4 heures pour les 50 meilleurs
        produits de chaque catégorie, toutes les 8 heures pour tous les autres et pour les codes promo affichés par les sites.
        La date du dernier relevé figure sous chaque offre. Nous relevons des données factuelles (prix, formats, teneurs,
        ingrédients, valeurs nutritionnelles, note moyenne des avis) ; la photo est affichée depuis le site du marchand.
      </p>

      <h2>Neutralité et rémunération</h2>
      <ul>
        <li>Aucun emplacement payant dans le classement : un marchand ne peut pas acheter une meilleure place.</li>
        <li>Les sites non affiliés apparaissent exactement comme les autres.</li>
        <li>
          DoseHunt se rémunère par l'affiliation : quand tu achètes après avoir cliqué sur « Voir l'offre », le marchand
          peut nous verser une commission, sans surcoût pour toi. Ces liens sont signalés (<code>rel="sponsored"</code>).
        </li>
        <li>Des codes partenaires négociés avec des marques peuvent apparaître ; ils sont classés selon la même règle.</li>
      </ul>

      <h2>Ce que DoseHunt ne fait pas</h2>
      <p>
        DoseHunt compare des prix. Il ne donne aucun conseil de dosage ni d'avis médical, et ne vérifie pas la conformité
        réglementaire des produits : un produit livrable en France y est considéré comme vendu légalement.
      </p>

      <h2>Une erreur ?</h2>
      <p>Un prix, une teneur ou un code faux : écris-nous à contact@dosehunt.fr, ou indique sous l'offre si un code ne marche plus. Nous corrigeons vite, car un seul chiffre faux suffit à perdre ta confiance.</p>
    </article>
  );
}
