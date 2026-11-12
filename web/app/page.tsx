import Link from "next/link";
import { CATEGORIES } from "@/lib/categories";
import { getHome, lastUpdate } from "@/lib/data";
import { ago, displayName, num } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [home, updated] = await Promise.all([getHome(), lastUpdate()]);
  return (
    <>
      <section className="hero">
        <h1>Le vrai prix <em>au gramme utile</em>, code promo compris.</h1>
        <p>
          Choisis un produit : DoseHunt classe les offres de {CATEGORIES.length} catégories selon leur prix final par
          gramme de protéine, de zinc réel ou d'EPA + DHA, avec le meilleur code valable en France. Mis à jour {ago(updated)}.
        </p>
        <form className="search" action="/recherche" role="search">
          <label htmlFor="q" className="ctl-label" style={{ alignSelf: "center" }}>Chercher</label>
          <input id="q" name="q" placeholder="whey isolate chocolat, zinc bisglycinate…" />
          <button type="submit">Chercher</button>
        </form>
      </section>
      <section className="grid" aria-label="Catégories">
        {CATEGORIES.map((c) => {
          const h = home[c.id];
          const best = h?.best;
          return (
            <Link key={c.id} href={`/c/${c.id}`} className={`catcard${best ? "" : " empty"}`}>
              <h2>{c.label}</h2>
              {best ? (
                <>
                  <div className="unit">{num(best.value ?? 0, 2)}<small>{c.modes.dose.unit}</small></div>
                  <div className="meta">Meilleure offre : {displayName(best.brand, best.name, " ")} ({best.site_name})</div>
                  <div className="meta">{h.count} produit{h.count > 1 ? "s" : ""} comparé{h.count > 1 ? "s" : ""}</div>
                </>
              ) : (
                <div className="meta">Pas encore d'offre relevée</div>
              )}
            </Link>
          );
        })}
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
      </section>
    </>
  );
}
