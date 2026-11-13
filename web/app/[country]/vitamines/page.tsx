import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { vitaminCategories, vitaminsGroup } from "@/lib/categories";
import { countryFromPath } from "@/lib/country";
import { getHome } from "@/lib/data";
import { t } from "@/lib/i18n";
import { alternates } from "@/lib/seo";
import { CategoryTile } from "@/components/CategoryTiles";

export const dynamic = "force-dynamic";

type Params = Promise<{ country: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const country = countryFromPath((await params).country);
  if (!country) return {};
  return {
    title: t(country.lang, "category.vitamins.title", { label: vitaminsGroup(country).label }),
    alternates: alternates(country, "/vitamines"),
  };
}

export default async function Vitamins({ params }: { params: Params }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  const L = country.lang;
  const home = await getHome(country);
  const vit = vitaminsGroup(country);
  return (
    <>
      <section className="summary"><div>
        <h1>{vit.label}</h1>
        <p>{t(L, "category.vitamins.text")}</p>
      </div></section>
      <section className="grid" aria-label={vit.label}>
        {vitaminCategories(country).map((c) => <CategoryTile key={c.id} c={c} h={home[c.id]} country={country} />)}
      </section>
    </>
  );
}
