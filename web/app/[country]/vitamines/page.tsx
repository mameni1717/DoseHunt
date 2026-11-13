import type { Metadata } from "next";
import { VITAMIN_CATEGORIES, VITAMINS_GROUP } from "@/lib/categories";
import { getHome } from "@/lib/data";
import { CategoryTile } from "@/components/CategoryTiles";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: `${VITAMINS_GROUP.label} : le moins cher au gramme utile` };

export default async function Vitamins() {
  const home = await getHome();
  return (
    <>
      <section className="summary"><div>
        <h1>{VITAMINS_GROUP.label}</h1>
        <p>Minéraux, vitamines et acides aminés, comparés au prix de l'actif réellement apporté (zinc ou magnésium élément,
          UI de vitamine D, EPA + DHA…), pas au poids du comprimé.</p>
      </div></section>
      <section className="grid" aria-label={VITAMINS_GROUP.label}>
        {VITAMIN_CATEGORIES.map((c) => <CategoryTile key={c.id} c={c} h={home[c.id]} />)}
      </section>
    </>
  );
}
