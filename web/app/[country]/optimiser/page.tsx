import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { categories } from "@/lib/categories";
import { countryFromPath, href } from "@/lib/country";
import { MESSAGES, t } from "@/lib/i18n";
import { rich } from "@/lib/rich";
import { alternates } from "@/lib/seo";
import { DEFAULT_QTY, KIND_BY_CATEGORY, KIND_LABEL_KEY, SHIPPING_ESTIMATE } from "@/lib/optimize";
import { Optimizer, type CatChoice, type OptimizerMessages } from "@/components/Optimizer";

type Params = Promise<{ country: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const country = countryFromPath((await params).country);
  if (!country) return {};
  const L = country.lang;
  return {
    title: t(L, "optimizer.meta.title"),
    description: t(L, "optimizer.meta.description"),
    alternates: alternates(country, "/optimiser"),
  };
}

export default async function OptimiserPage({ params }: { params: Params }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  const L = country.lang;
  const cats: CatChoice[] = categories(country).filter((c) => KIND_BY_CATEGORY[c.id]).map((c) => ({
    id: c.id, label: c.label, subs: c.subs ?? {}, kind: KIND_BY_CATEGORY[c.id],
    kindLabel: t(L, KIND_LABEL_KEY[KIND_BY_CATEGORY[c.id]]), defaultQty: DEFAULT_QTY[c.id] ?? 1,
  }));
  // Textes du composant client : seulement l'espace « optimizer. », dans la langue du pays.
  const m: OptimizerMessages = Object.fromEntries(Object.entries(MESSAGES[L])
    .filter(([k]) => k.startsWith("optimizer.") && !k.startsWith("optimizer.meta."))
    .map(([k, v]) => [k.slice("optimizer.".length), v]));
  return (
    <>
      <section className="summary"><div>
        <h1>{rich(L, "optimizer.title", { em: (c) => <em>{c}</em> })}</h1>
        <p>{t(L, "optimizer.intro")}</p>
      </div></section>
      <Optimizer cats={cats} shippingEstimate={SHIPPING_ESTIMATE} m={m} country={country.code}
        go={{ view: t(L, "offer.go.view"), copied: t(L, "offer.go.copied"), note: t(L, "offer.go.note") }}
        locale={country.locale} currency={country.currency} productPrefix={href(country, "/p")} />
    </>
  );
}
