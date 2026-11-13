import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AlertForm } from "@/components/AlertForm";
import { categories, categoryById, modeDef, type Mode } from "@/lib/categories";
import { countryFromPath, href } from "@/lib/country";
import { getProduct, getRanking } from "@/lib/data";
import { t } from "@/lib/i18n";
import { rich } from "@/lib/rich";
import { rerank } from "@/lib/rank";
import { displayName } from "@/lib/format";
import { alternates } from "@/lib/seo";

export const dynamic = "force-dynamic";

type Params = Promise<{ country: string }>;
type SP = Record<string, string | undefined>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const country = countryFromPath((await params).country);
  if (!country) return {};
  return { title: t(country.lang, "alerts.title"), alternates: alternates(country, "/alertes") };
}

export default async function Alerts({ params, searchParams }: { params: Params; searchParams: Promise<SP> }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  const L = country.lang;
  const sp = await searchParams;
  const byId = categoryById(country);
  const productId = Number(sp.product) || undefined;
  const d = productId ? await getProduct(country, productId) : null;
  const cat = (sp.cat && byId[sp.cat]) ? sp.cat : d?.actives[0]?.category ?? "whey";
  const c = byId[cat];
  const modes = Object.keys(c.modes) as Mode[];
  const units = [
    ...(d ? [{ mode: "price", label: t(L, "alerts.unit.price", { cur: country.symbol }) }] : []),
    ...modes.map((m) => ({ mode: m, label: t(L, "alerts.unit.mode", { label: modeDef(country, cat, m).label.toLowerCase(), unit: modeDef(country, cat, m).unit }) })),
  ];
  const defaults: Record<string, number> = {};
  if (d) {
    const r = rerank(d.rows, d.codes, { mode: c.defaultMode, allFormats: true, firstOrder: false, useCodes: true }).find((x) => x.available);
    if (r) { defaults.price = r.final; if (r.doseNow) defaults.dose = r.doseNow; if (r.kgNow) defaults.kg = r.kgNow; if (r.unitNow) defaults.unit = r.unitNow; }
  } else {
    const { rows } = await getRanking(country, cat, { sub: sp.sub }, { mode: c.defaultMode, allFormats: false, firstOrder: false, useCodes: true });
    const best = rows.find((x) => x.available);
    if (best) { if (best.doseNow) defaults.dose = best.doseNow; if (best.kgNow) defaults.kg = best.kgNow; if (best.unitNow) defaults.unit = best.unitNow; }
  }
  const b = (x: React.ReactNode) => <b>{x}</b>;

  return (
    <>
      <section className="summary"><div>
        <h1>{t(L, "alerts.title")}</h1>
        {sp.confirmed && <p className="ok">{t(L, "alerts.confirmed")}</p>}
        {sp.stopped && <p className="ok">{t(L, "alerts.stopped")}</p>}
        {sp.invalid && <p className="err">{t(L, "alerts.invalid")}</p>}
        <p>{d
          ? rich(L, "alerts.intro.product", { b }, { name: displayName(d.product.brand, d.product.name, " ") })
          : rich(L, "alerts.intro.category", { b }, { cat: c.label, sub: sp.sub && c.subs?.[sp.sub] ? ` (${c.subs[sp.sub]})` : "" })}</p>
      </div></section>

      {!d && (
        <form className="controls" action={href(country, "/alertes")}>
          <div className="row">
            <label className="ctl-label" htmlFor="cat">{t(L, "alerts.category")}</label>
            <select id="cat" className="filter" name="cat" defaultValue={cat}>
              {categories(country).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
            </select>
            {c.subs && (
              <select className="filter" name="sub" defaultValue={sp.sub ?? ""} aria-label={t(L, "alerts.type")}>
                <option value="">{t(L, "alerts.allTypes")}</option>
                {Object.entries(c.subs).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            )}
            <button className="btn ghost" type="submit">{t(L, "alerts.choose")}</button>
          </div>
        </form>
      )}

      <section className="panel">
        <AlertForm country={country.code} product={productId} cat={cat} sub={d ? undefined : sp.sub} units={units} defaults={defaults}
          m={{ email: t(L, "alerts.form.email"), placeholder: t(L, "alerts.form.placeholder"), when: t(L, "alerts.form.when"),
               under: t(L, "alerts.form.under"), sending: t(L, "alerts.form.sending"), create: t(L, "alerts.form.create"),
               saved: t(L, "alerts.form.saved"), failed: t(L, "alerts.form.failed"), failedLater: t(L, "alerts.form.failedLater"),
               privacy: t(L, "alerts.form.privacy") }} />
        <p className="note-small">{t(L, "alerts.prefilled")} {d ? <Link href={href(country, `/p/${productId}`)}>{t(L, "alerts.back")}</Link> : null}</p>
      </section>
    </>
  );
}
