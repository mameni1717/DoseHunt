import type { Metadata } from "next";

export const metadata: Metadata = { title: "Politique de confidentialité", alternates: { canonical: "/confidentialite" } };

export default function Confidentialite() {
  return (
    <article className="prose">
      <h1>Politique de confidentialité</h1>
      <p>
        DoseHunt collecte le minimum de données. Le site n'utilise aucun cookie de suivi ni de publicité, et ne
        demande aucun compte.
      </p>

      <h2>Responsable du traitement</h2>
      <p>L'éditeur du site (voir les <a href="/mentions-legales">mentions légales</a>). Contact : mameni1717@gmail.com.</p>

      <h2>Les données que nous traitons</h2>
      <ul>
        <li>
          <b>Mesure d'audience</b> : nous utilisons Vercel Analytics, qui compte les visites sans cookie et sans
          identifier les personnes. Base légale : intérêt légitime (mesurer la fréquentation du site).
        </li>
        <li>
          <b>Clics vers les marchands</b> : nous enregistrons quelle offre a été cliquée, quand, et le code promo
          éventuel. Ni adresse IP ni cookie ne sont conservés.
        </li>
        <li>
          <b>Alertes prix</b> : si tu crées une alerte, nous conservons ton adresse e-mail, ton pays et les critères de
          l'alerte, jusqu'à ce que tu la supprimes. Ton adresse sert uniquement à t'envoyer cette alerte (e-mail de
          confirmation, puis alertes). Chaque message contient un lien de désinscription. Base légale : ton
          consentement, confirmé par e-mail. Les e-mails sont envoyés par Resend.
        </li>
        <li>
          <b>Vote sur les codes promo</b> : pour éviter les votes en double, nous calculons une empreinte
          irréversible (adresse IP, navigateur et jour, hachés avec un secret). L'adresse IP n'est pas conservée
          en clair.
        </li>
      </ul>

      <h2>Sous-traitants</h2>
      <p>
        Hébergement : Vercel. Base de données : Neon. Envoi d'e-mails : Resend. Ces prestataires peuvent traiter des
        données hors de l'Union européenne, dans le cadre de garanties contractuelles (clauses types).
      </p>

      <h2>Tes droits</h2>
      <p>
        Tu peux demander l'accès, la rectification ou la suppression de tes données, ou t'opposer à leur traitement, en
        écrivant à mameni1717@gmail.com. Tu peux aussi supprimer une alerte à tout moment avec le lien présent
        dans chaque e-mail. En cas de désaccord, tu peux saisir la CNIL (cnil.fr).
      </p>

      <h2>Liens vers d'autres sites</h2>
      <p>Les sites marchands ont leur propre politique de confidentialité et leurs propres cookies.</p>
    </article>
  );
}
