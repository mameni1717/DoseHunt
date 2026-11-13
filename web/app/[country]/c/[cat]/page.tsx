import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { OfferCard, applyFiltersText } from "@/components/OfferCard";
import { ApplyFilters } from "@/components/client";
import { categoryById, milkOrigin, modeDef, modeOf, vitaminsGroup, type Mode } from "@/lib/categories";
import { countryFromPath, href } from "@/lib/country";
import { getRanking } from "@/lib/data";
import { displayName, formatNumber, qs } from "@/lib/format";
import { t, tp, type MessageKey } from "@/lib/i18n";
import { rich } from "@/lib/rich";
import { alternates } from "@/lib/seo";
import { SITE_URL, monthYear } from "@/lib/site";

export const dynamic = "force-dynamic";

const PAGE = 20;
type SP = Record<string, string | undefined>;
type Params = Promise<{ country: string; cat: string }>;

export async function generateMetadata({ params, searchParams }: { params: Params; searchParams: Promise<SP> }): Promise<Metadata> {
  const p = await params;
  const country = countryFromPath(p.country);
  if (!country) return {};
  const L = country.lang;
  const c = categoryById(country)[p.cat];
  if (!c) return {};
  const sp = await searchParams;
  const sub = sp.sub && c.subs?.[sp.sub];
  const filtered = Object.keys(sp).some((k) => k !== "sub" && sp[k]);
  const seo = t(L, `category.seo.${c.id}` as MessageKey);
  const title = t(L, "category.meta.title", {
    sub: sub ? t(L, "category.meta.subPrefix", { sub }) : "",
    title: seo.startsWith("category.seo.") ? c.label : seo,
    month: monthYear(country),
  });
  const description = t(L, "category.meta.description", {
    label: c.label, sub: sub ? ` (${sub})` : "", mode: modeDef(country, c.id, c.defaultMode).label.toLowerCase(),
  });
  const path = `/c/${c.id}${sub ? `?sub=${sp.sub}` : ""}`;
  return {
    title, description,
    alternates: alternates(country, path),
    openGraph: { title, description, url: href(country, path), locale: country.ogLocale },
    robots: filtered ? { index: false, follow: true } : undefined,   // vues filtrées : pas de doublons dans Google
  };
}

export default async function CategoryPage({ params, searchParams }: { params: Params; searchParams: Promise<SP> }) {
  const p = await params;
  const country = countryFromPath(p.country);
  if (!country) notFound();
  const L = country.lang;
  const { cat } = p;
  const sp = await searchParams;
  if (cat === "caseine") redirect(href(country, "/c/whey?sub=caseine"));          // ancienne catégorie, désormais un type de whey
  const c = categoryById(country)[cat];
  if (!c) notFound();
  const mode: Mode = modeOf(c, sp.mode);
  const opts = { mode, allFormats: sp.all === "1", firstOrder: sp.first === "1", useCodes: sp.codes !== "0" };
  const filters = {
    sub: sp.sub, site: sp.site, brand: sp.brand, form: sp.form, madeIn: sp.made === "1",
    lactose: sp.lactose === "1", noSweetener: sp.nosweet === "1", noSucralose: sp.nosucra === "1",
    minActive: sp.min ? Number(sp.min) : undefined, milk: sp.milk,
  };
  const { rows: all, facets } = await getRanking(country, cat, filters, opts);
  const showOut = sp.stock === "all";
  const outCount = all.filter((r) => !r.available).length;
  const rows = showOut ? all : all.filter((r) => r.available);
  const shown = Math.max(PAGE, Number(sp.n) || PAGE);
  const visible = rows.slice(0, shown);
  const inStock = rows.filter((r) => r.available);
  const best = inStock[0];
  const base: SP = { ...sp, n: undefined };
  const md = modeDef(country, cat, mode);
  const has = (f: string) => (c.filters ?? []).includes(f as never);
  const extraActive = [sp.site, sp.brand, sp.form, sp.lactose, sp.nosweet, sp.nosucra, sp.min, sp.milk, sp.all, sp.first, sp.codes, sp.stock].filter(Boolean).length;
  const share = c.activeShare ?? "";

  return (
    <>
      {c.group === "vitamins" && <p className="crumb"><Link href={href(country, "/vitamines")}>← {vitaminsGroup(country).label}</Link></p>}
      <section className="summary" aria-live="polite">
        <div>
          <h1>{c.label}</h1>
          {best ? (
            <p>
              {rich(L, "category.best", { b: (x) => <b>{x}</b> }, {
                name: displayName(best.brand, best.name, " "), site: best.site_name,
                from: best.variants > 1 ? t(L, "category.best.from") : "",
                value: `${formatNumber(best.value ?? 0, country, 2)} ${md.unit.replace(/\.$/, "")}`,
                code: best.applied ? t(L, "category.best.code", { code: best.applied.code.code }) : "",
              })}
              {" "}{tp(L, "category.inStock", inStock.length)}{filters.madeIn ? tp(L, "category.inStock.made", inStock.length, { country: country.name }) : ""}.
            </p>
          ) : (
            <p>{outCount ? t(L, "category.none.out", { n: outCount }) : t(L, "category.none")}</p>
          )}
        </div>
      </section>

      <form className="controls" action={href(country, `/c/${cat}`)} aria-label={t(L, "category.form.label")}>
        {c.subs && (
          <div className="row">
            <span className="ctl-label">{t(L, "category.type")}</span>
            <div className="seg">
              <Link href={qs(base, { sub: undefined })} aria-current={!sp.sub}>{t(L, "category.type.all")}</Link>
              {Object.entries(c.subs).map(([id, label]) => (
                <Link key={id} href={qs(base, { sub: id })} aria-current={sp.sub === id}>{label}</Link>
              ))}
            </div>
            {sp.sub && <input type="hidden" name="sub" value={sp.sub} />}
          </div>
        )}
        <div className="row">
          <span className="ctl-label">{t(L, "category.sortBy")}</span>
          <div className="seg">
            {(Object.keys(c.modes) as Mode[]).map((m) => (
              <Link key={m} href={qs(base, { mode: m === c.defaultMode ? undefined : m })} aria-current={mode === m}>{c.modes[m]!.label}</Link>
            ))}
          </div>
          {sp.mode && <input type="hidden" name="mode" value={sp.mode} />}
          <label className="check made">
            <input type="checkbox" name="made" value="1" defaultChecked={filters.madeIn} />
            <span aria-hidden="true">{country.flag}</span> {country.madeIn}<small> ({facets.madeIn})</small>
          </label>
        </div>
        <details className="more" open={extraActive > 0}>
          <summary>{t(L, "category.more")}{extraActive ? tp(L, "category.more.active", extraActive) : ""}</summary>
          <div className="row">
            <select className="filter" name="brand" defaultValue={sp.brand ?? ""} aria-label={t(L, "category.brand")}>
              <option value="">{t(L, "category.brand.all")}</option>
              {facets.brands.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
            <select className="filter" name="site" defaultValue={sp.site ?? ""} aria-label={t(L, "category.site")}>
              <option value="">{t(L, "category.site.all")}</option>
              {facets.sites.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            </select>
            {facets.forms.length > 0 && (
              <select className="filter" name="form" defaultValue={sp.form ?? ""} aria-label={t(L, "category.formFilter")}>
                <option value="">{t(L, "category.formFilter.all")}</option>
                {facets.forms.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            )}
            {has("minActive") && (
              <select className="filter" name="min" defaultValue={sp.min ?? ""} aria-label={t(L, "category.min.label", { share })}>
                <option value="">{t(L, "category.min.all", { share })}</option>
                {[60, 70, 75, 80, 85, 90].map((v) => <option key={v} value={v}>{t(L, "category.min.option", { share, v })}</option>)}
              </select>
            )}
            {has("milk") && facets.milk.length > 0 && (
              <select className="filter" name="milk" defaultValue={sp.milk ?? ""} aria-label={t(L, "category.milk.label")}>
                <option value="">{t(L, "category.milk.all")}</option>
                {facets.milk.map((m) => <option key={m} value={m}>{t(L, "category.milk.option", { origin: milkOrigin(country, m) })}</option>)}
              </select>
            )}
          </div>
          <div className="row">
            {has("lactose") && <label className="check"><input type="checkbox" name="lactose" value="1" defaultChecked={filters.lactose} /> {t(L, "category.lactose")}</label>}
            {has("sweetener") && <label className="check"><input type="checkbox" name="nosweet" value="1" defaultChecked={filters.noSweetener} /> {t(L, "category.noSweetener")}</label>}
            {has("sucralose") && <label className="check"><input type="checkbox" name="nosucra" value="1" defaultChecked={filters.noSucralose} /> {t(L, "category.noSucralose")}</label>}
            <label className="check"><input type="checkbox" name="stock" value="all" defaultChecked={showOut} /> {t(L, "category.showOut", { n: outCount })}</label>
            <label className="check"><input type="checkbox" name="all" value="1" defaultChecked={opts.allFormats} /> {t(L, "category.allFormats")}</label>
            <label className="check"><input type="checkbox" name="first" value="1" defaultChecked={opts.firstOrder} /> {t(L, "category.firstOrder")}</label>
            <label className="check"><input type="checkbox" name="codes" value="0" defaultChecked={!opts.useCodes} /> {t(L, "category.ignoreCodes")}</label>
          </div>
          {(has("lactose") || has("sweetener")) && (
            <p className="note-small">{t(L, "category.withoutNote")}</p>
          )}
        </details>
        <ApplyFilters m={applyFiltersText(L)}>
          {extraActive > 0 && <Link className="btn ghost" href={qs({ sub: sp.sub, mode: sp.mode }, {}) || href(country, `/c/${cat}`)}>{t(L, "category.reset")}</Link>}
        </ApplyFilters>
      </form>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
        "@context": "https://schema.org", "@type": "ItemList", name: c.label,
        itemListElement: inStock.slice(0, 20).map((r, i) => ({
          "@type": "ListItem", position: i + 1, url: `${SITE_URL}${href(country, `/p/${r.product_id}`)}`, name: displayName(r.brand, r.name, " "),
        })),
      }) }} />

      {visible.length > 0 ? (
        <ol className="list">
          {visible.map((r, i) => <OfferCard key={r.offer_id} r={r} rank={i + 1} mode={mode} best={i === 0 && r.available} country={country} />)}
        </ol>
      ) : (
        <p className="empty">{t(L, "category.none")}</p>
      )}
      {rows.length > shown && (
        <p className="more-results">
          <Link className="btn ghost" href={`${qs(base, { n: String(shown + PAGE) })}#r${shown + 1}`} scroll={false}>
            {tp(L, "category.moreResults", Math.min(PAGE, rows.length - shown), { shown, total: rows.length })}
          </Link>
        </p>
      )}

      <section className="notes">
        <div className="note">
          <h3>{t(L, "category.note.calc.title")}</h3>
          {t(L, "category.note.calc.text")}
        </div>
        <div className="note">
          <h3>{t(L, "category.note.alert.title")}</h3>
          {rich(L, "category.note.alert.text", { link: (x) => <Link href={href(country, `/alertes?cat=${cat}`)}>{x}</Link> })}
        </div>
      </section>
    </>
  );
}
