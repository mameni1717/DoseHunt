import type { Metadata } from "next";

export const metadata: Metadata = { title: "Mentions légales", alternates: { canonical: "/mentions-legales" } };

// À COMPLÉTER avant la mise en ligne : les champs [ ... ] sont des informations personnelles que seul l'éditeur connaît.
export default function MentionsLegales() {
  return (
    <article className="prose">
      <h1>Mentions légales</h1>

      <h2>Éditeur du site</h2>
      <p>
        DoseHunt, site édité par [NOM ET PRÉNOM DE L'ÉDITEUR, ou raison sociale et forme juridique si société],
        [ADRESSE POSTALE, ou adresse de domiciliation].<br />
        Contact : [ADRESSE E-MAIL DE CONTACT].<br />
        Directeur de la publication : [NOM].<br />
        [Si entreprise : numéro SIREN / SIRET, numéro de TVA intracommunautaire.]
      </p>

      <h2>Hébergement</h2>
      <p>
        Le site est hébergé par Vercel Inc., 440 N Barranca Ave #4133, Covina, CA 91723, États-Unis (vercel.com).
        Les données sont stockées dans une base Neon (neon.tech).
      </p>

      <h2>Nature du site et liens affiliés</h2>
      <p>
        DoseHunt est un comparateur de prix de compléments alimentaires. Le site ne vend aucun produit. Certains liens
        vers les marchands sont des liens affiliés : si tu achètes après avoir cliqué, DoseHunt peut recevoir une
        commission, sans surcoût pour toi. Le classement ne dépend que du prix comparé, aucun marchand ne peut payer pour
        être mieux classé (voir <a href="/methode">notre méthode</a>).
      </p>

      <h2>Contenu et responsabilité</h2>
      <p>
        Les prix, teneurs et codes promo sont relevés automatiquement sur les sites marchands et peuvent changer à tout
        moment : vérifie toujours le prix final sur le site du marchand avant d'acheter. DoseHunt ne donne aucun conseil
        médical ou de dosage ; en cas de doute, demande l'avis d'un professionnel de santé.
      </p>

      <h2>Propriété intellectuelle</h2>
      <p>
        La structure, les textes et le code du site sont la propriété de l'éditeur. Les marques et noms de produits cités
        appartiennent à leurs propriétaires respectifs.
      </p>

      <h2>Données personnelles</h2>
      <p>Voir la <a href="/confidentialite">politique de confidentialité</a>.</p>
    </article>
  );
}
