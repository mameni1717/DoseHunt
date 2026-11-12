import Link from "next/link";

export default function NotFound() {
  return (
    <section className="empty">
      <p>Cette page n'existe pas ou plus.</p>
      <p><Link href="/">Retour à l'accueil</Link></p>
    </section>
  );
}
