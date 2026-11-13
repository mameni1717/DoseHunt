import Link from "next/link";
import { MAIN_CATEGORIES, VITAMIN_CATEGORIES, VITAMINS_GROUP } from "@/lib/categories";
import { getHome, lastUpdate } from "@/lib/data";
import { ago } from "@/lib/format";
import { CategoryTile } from "@/components/CategoryTiles";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [home, updated] = await Promise.all([getHome(), lastUpdate()]);
  const vitCount = VITAMIN_CATEGORIES.reduce((n, c) => n + (home[c.id]?.count ?? 0), 0);
  return (
    <>
      <section className="hero">
        <h1>Le vrai prix <em>au gramme utile</em>, code promo compris.</h1>
        <p>
          DoseHunt classe les compléments selon leur prix final par gramme de protéine, de créatine, de zinc réel ou
          d'EPA + DHA, avec le meilleur code valable en France. Prix mis à jour {ago(updated)}.
        </p>
        <form className="search" action="/recherche" role="search">
          <label htmlFor="q" className="ctl-label" style={{ alignSelf: "center" }}>Chercher</label>
          <input id="q" name="q" placeholder="whey isolate chocolat, zinc bisglycinate…" />
          <button type="submit">Chercher</button>
        </form>
      </section>
      <Link href="/optimiser" className="opt-banner">
        <span className="opt-banner-kicker">Nouveau</span>
        <strong>Optimiser mes achats</strong>
        <span>Whey, créatine, barres… indique ce que tu prends : on trouve les 3 sites où tout commander au moins cher, code promo et livraison offerte compris.</span>
        <span className="opt-banner-go">Composer mon panier →</span>
      </Link>
      <section className="grid" aria-label="Catégories">
        {MAIN_CATEGORIES.map((c) => <CategoryTile key={c.id} c={c} h={home[c.id]} />)}
        <Link href="/vitamines" className="catcard group">
          <h2>{VITAMINS_GROUP.label}</h2>
          <div className="meta">{VITAMIN_CATEGORIES.map((c) => c.short).join(", ")}</div>
          <div className="meta">{vitCount} produits comparés</div>
        </Link>
      </section>
      <section className="notes">
        <div className="note trapnote">
          <h3>Le piège du « 120 mg »</h3>
          « Gluconate de zinc 120 mg » désigne le poids du sel, pas du zinc : 15 mg de zinc réel seulement. DoseHunt compare
          toujours la quantité d'actif réelle, lue dans le tableau nutritionnel.
        </div>
        <div className="note">
          <h3>Un classement qui ne s'achète pas</h3>
          L'ordre dépend uniquement du prix final par unité active. Le meilleur code est appliqué même s'il ne rapporte rien
          à DoseHunt. <Link href="/methode">Notre méthode</Link>.
        </div>
        <div className="note">
          <h3>Comparer, être prévenu</h3>
          Coche « Comparer » sur plusieurs produits pour les voir côte à côte, ou crée une <Link href="/alertes">alerte prix</Link> :
          un e-mail dès qu'un produit passe sous ton prix.
        </div>
      </section>
    </>
  );
}
