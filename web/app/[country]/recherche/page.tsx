import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { OfferCard } from "@/components/OfferCard";
import { categoryById } from "@/lib/categories";
import { countryFromPath, href } from "@/lib/country";
import { search } from "@/lib/data";
import { t, tp } from "@/lib/i18n";
import type { Ranked } from "@/lib/rank";

export const dynamic = "force-dynamic";

type Params = Promise<{ country: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const country = countryFromPath((await params).country);
  if (!country) return {};
  return { title: t(country.lang, "search.meta.title") };
}

export default async function SearchPage({ params, searchParams }: { params: Params; searchParams: Promise<{ q?: string }> }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  const L = country.lang;
  const { q = "" } = await searchParams;
  const rows = q.trim() ? await search(country, q) : [];
  const byCat = new Map<string, Ranked[]>();
  for (const r of rows) byCat.set(r.category, [...(byCat.get(r.category) ?? []), r]);
  const cats = categoryById(country);
  return (
    <>
      <form className="search" action={href(country, "/recherche")} role="search">
        <input name="q" defaultValue={q} placeholder={t(L, "search.placeholder")} aria-label={t(L, "search.label")} />
        <button type="submit">{t(L, "search.button")}</button>
      </form>
      {q && rows.length === 0 && <p className="empty">{t(L, "search.none", { q })}</p>}
      {[...byCat.entries()].map(([cat, list]) => (
        <section key={cat} style={{ display: "grid", gap: 10 }}>
          <h2 style={{ font: "700 24px/1 var(--display)", textTransform: "uppercase", margin: "8px 0 0" }}>
            {cats[cat]?.label} · {tp(L, "search.results", list.length)}
          </h2>
          <ol className="list">
            {list.map((r, i) => <OfferCard key={r.offer_id} r={r} rank={i + 1} mode="dose" best={i === 0} country={country} />)}
          </ol>
        </section>
      ))}
    </>
  );
}
