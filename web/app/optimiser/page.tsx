import type { Metadata } from "next";
import { CATEGORIES } from "@/lib/categories";
import { DEFAULT_QTY, KIND_BY_CATEGORY, KIND_LABEL, SHIPPING_ESTIMATE } from "@/lib/optimize";
import { Optimizer, type CatChoice } from "@/components/Optimizer";

export const metadata: Metadata = {
  title: "Optimiser mes achats : le site le moins cher pour toute ta liste",
  description:
    "Whey, créatine, collagène, barres, pré-workout, vitamines : indique ce que tu achètes et DoseHunt trouve les 3 sites où commander toute ta liste au moins cher, code promo et livraison offerte compris.",
  alternates: { canonical: "/optimiser" },
};

export default function OptimiserPage() {
  const cats: CatChoice[] = CATEGORIES.filter((c) => KIND_BY_CATEGORY[c.id]).map((c) => ({
    id: c.id, label: c.label, subs: c.subs ?? {}, kind: KIND_BY_CATEGORY[c.id],
    kindLabel: KIND_LABEL[KIND_BY_CATEGORY[c.id]], defaultQty: DEFAULT_QTY[c.id] ?? 1,
  }));
  return (
    <>
      <section className="summary"><div>
        <h1>Optimiser <em>mes achats</em></h1>
        <p>Ajoute ce que tu achètes d&apos;habitude. On calcule, pour chaque marchand, le panier complet le moins cher
          (code promo appliqué au panier entier, livraison offerte comptée) et on te montre les 3 meilleurs sites
          où tout commander en une seule fois.</p>
      </div></section>
      <Optimizer cats={cats} shippingEstimate={SHIPPING_ESTIMATE} />
    </>
  );
}
