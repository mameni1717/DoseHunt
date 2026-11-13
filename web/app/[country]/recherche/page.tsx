import type { Metadata } from "next";
import { OfferCard } from "@/components/OfferCard";
import { CATEGORY_BY_ID } from "@/lib/categories";
import { search } from "@/lib/data";
import type { Ranked } from "@/lib/rank";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Recherche" };

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const rows = q.trim() ? await search(q) : [];
  const byCat = new Map<string, Ranked[]>();
  for (const r of rows) byCat.set(r.category, [...(byCat.get(r.category) ?? []), r]);
  return (
    <>
      <form className="search" action="/recherche" role="search">
        <input name="q" defaultValue={q} placeholder="whey isolate chocolat, zinc bisglycinate…" aria-label="Recherche" />
        <button type="submit">Chercher</button>
      </form>
      {q && rows.length === 0 && <p className="empty">Aucun produit trouvé pour « {q} ».</p>}
      {[...byCat.entries()].map(([cat, list]) => (
        <section key={cat} style={{ display: "grid", gap: 10 }}>
          <h2 style={{ font: "700 24px/1 var(--display)", textTransform: "uppercase", margin: "8px 0 0" }}>
            {CATEGORY_BY_ID[cat]?.label} · {list.length} résultat{list.length > 1 ? "s" : ""}
          </h2>
          <ol className="list">
            {list.map((r, i) => <OfferCard key={r.offer_id} r={r} rank={i + 1} mode="dose" best={i === 0} />)}
          </ol>
        </section>
      ))}
    </>
  );
}
