import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { activeLabel, categories, categoryById, milkOrigin, modeDef, type Mode } from "@/lib/categories";
import { getCompare, getRanking } from "@/lib/data";
import { displayName, formatMoney, formatNumber } from "@/lib/format";
import { formatLabel, type Ranked } from "@/lib/rank";
import { nutriLabels } from "@/components/ProductFacts";
import { ApplyFilters, GoButton } from "@/components/client";
import { applyFiltersText, goButtonText } from "@/components/OfferCard";
import { brandKey, norm } from "@/lib/group";
import { countryFromPath, href } from "@/lib/country";
import { t, tp } from "@/lib/i18n";
import { alternates } from "@/lib/seo";

export const dynamic = "force-dynamic";

type Params = Promise<{ country: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const country = countryFromPath((await params).country);
  if (!country) return {};
  return { title: t(country.lang, "compare.title"), alternates: alternates(country, "/comparer") };
}

type SP = Record<string, string | string[] | undefined>;
const list = (v: string | string[] | undefined) => (Array.isArray(v) ? v : v ? v.split(",") : []).filter(Boolean);

const value = (r: Ranked, m: Mode) => (m === "dose" ? r.doseNow : m === "kg" ? r.kgNow : r.unitNow);

export default async function Compare({ params, searchParams }: { params: Params; searchParams: Promise<SP> }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  const L = country.lang;
  const byId = categoryById(country);
  const money = (v: number) => formatMoney(v, country);
  const num = (v: number, d = 0) => formatNumber(v, country, d);
  const goM = goButtonText(L);
  const sp = await searchParams;
  const ids = list(sp.ids).map(Number).filter(Number.isFinite).slice(0, 8);
  const asked = typeof sp.cat === "string" && byId[sp.cat] ? sp.cat : undefined;
  const first = asked ? [] : await getCompare(country, ids.slice(0, 1));
  const cat = asked ?? first[0]?.row.category ?? "whey";
  const items = await getCompare(country, ids, cat);                 // seulement des produits de la catégorie choisie
  const c = byId[cat];
  const brands = list(sp.brand);
  const ranking = await getRanking(country, cat, {}, { mode: c.defaultMode, allFormats: true, firstOrder: false, useCodes: true });
  const facets = ranking.facets;
  const seenIds = new Set<number>();                 // une ligne par produit (son offre la moins chère), arômes compris
  const rows = ranking.rows.filter((r) => (seenIds.has(r.product_id) ? false : (seenIds.add(r.product_id), true)));
  // Recherche manuelle : tous les produits de la catégorie, ruptures comprises ; sans recherche, les 80 moins chers en stock.
  const q = typeof sp.q === "string" ? sp.q.trim() : "";
  const words = norm(q).split(/[^a-z0-9%]+/).filter((w) => w.length >= 2);
  const inBrands = (r: Ranked) => !brands.length || brands.includes(brandKey(r.brand));
  const found = words.length
    ? rows.filter((r) => inBrands(r) && words.every((w) => norm(`${r.brand ?? ""} ${r.name} ${r.site_name}`).includes(w))).slice(0, 80)
    : rows.filter((r) => r.available && inBrands(r)).slice(0, 80);
  const selected = rows.filter((r) => ids.includes(r.product_id) && !found.some((f) => f.product_id === r.product_id));
  const candidates = [...selected, ...found];
  const modes = Object.keys(c.modes) as Mode[];
  const bestOf = (f: (r: Ranked) => number | null, lowIsBest = true) => {
    const vals = items.map((i) => f(i.row)).filter((v): v is number => v != null);
    return vals.length ? (lowIsBest ? Math.min(...vals) : Math.max(...vals)) : null;
  };

  return (
    <>
      <section className="summary"><div>
        <h1>{t(L, "compare.title")}</h1>
        <p>{t(L, "compare.intro")}</p>
      </div></section>

      <form className="controls" action={href(country, "/comparer")}>
        <div className="row">
          <label className="ctl-label" htmlFor="cat">{t(L, "compare.category")}</label>
          <select id="cat" className="filter" name="cat" defaultValue={cat}>
            {categories(country).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
        </div>
        <details className="more" open={brands.length > 0}>
          <summary>{brands.length ? t(L, "compare.brands.some", { n: brands.length }) : t(L, "compare.brands.all")}</summary>
          <div className="row checks">
            {facets.brands.map(([k, label]) => (
              <label key={k} className="check"><input type="checkbox" name="brand" value={k} defaultChecked={brands.includes(k)} /> {label}</label>
            ))}
          </div>
        </details>
        <ApplyFilters m={applyFiltersText(L)} />
      </form>

      <form className="controls" action={href(country, "/comparer")}>
        <input type="hidden" name="cat" value={cat} />
        {brands.map((b) => <input key={b} type="hidden" name="brand" value={b} />)}
        <div className="row">
          <label className="ctl-label" htmlFor="q">{t(L, "compare.search")}</label>
          <input id="q" className="filter grow" name="q" defaultValue={q} placeholder={t(L, "compare.search.placeholder")} />
          <button className="btn ghost" type="submit">{t(L, "compare.search")}</button>
          {q && <Link className="btn ghost small" href={href(country, "/comparer") + `?cat=${cat}${brands.map((b) => `&brand=${b}`).join("")}${ids.length ? `&ids=${ids.join(",")}` : ""}`}>{t(L, "compare.search.clear")}</Link>}
        </div>
        <div className="pick">
          <p className="note-small">{q ? tp(L, "compare.results", found.length, { q }) : t(L, "compare.cheapest", { n: found.length })}
            {ids.length ? ` ${t(L, "compare.picked", { n: ids.length })}` : ""}</p>
          {candidates.map((r) => (
            <label key={r.product_id} className="check">
              <input type="checkbox" name="ids" value={r.product_id} defaultChecked={ids.includes(r.product_id)} />
              {displayName(r.brand, r.name, " ")} <small>· {r.site_name} · {num(r.value ?? 0, 2)} {modeDef(country, cat, c.defaultMode).unit}{r.available ? "" : ` · ${t(L, "compare.outOfStockLong")}`}</small>
            </label>
          ))}
          {candidates.length === 0 && <p className="note-small">{t(L, "compare.noMatch")}</p>}
        </div>
        <div className="row"><button className="btn blaze" type="submit" formAction={href(country, "/comparer")}>{t(L, "compare.submit")}</button></div>
      </form>

      {items.length >= 2 ? (
        <div className="cmpwrap">
          <table className="t cmp">
            <thead>
              <tr><th></th>{items.map(({ row: r }) => (
                <th key={r.product_id}>
                  {r.image_url && <img src={r.image_url} alt="" width={64} height={64} referrerPolicy="no-referrer" />}
                  <Link href={href(country, `/p/${r.product_id}`)}>{displayName(r.brand, r.name, " ")}</Link>
                  <small>{r.site_name}{r.available ? "" : ` · ${t(L, "compare.outOfStock")}`}</small>
                </th>))}</tr>
            </thead>
            <tbody>
              <tr><th>{t(L, "compare.row.price")}</th>{items.map(({ row: r }) => <td key={r.product_id}><b>{money(r.final)}</b> · {formatLabel(r, country.locale)}{r.applied ? ` ${t(L, "compare.row.code", { code: r.applied.code.code })}` : ""}</td>)}</tr>
              {modes.map((m) => {
                const b = bestOf((r) => value(r, m));
                return (
                  <tr key={m}><th>{modeDef(country, cat, m).label}</th>{items.map(({ row: r }) => {
                    const v = value(r, m);
                    return <td key={r.product_id} className={v != null && v === b ? "win" : ""}>{v != null ? `${num(v, 2)} ${modeDef(country, cat, m).unit}` : "–"}</td>;
                  })}</tr>
                );
              })}
              <tr><th>{c.activeShare ?? t(L, "compare.row.content")}</th>{items.map(({ row: r }) => <td key={r.product_id}>{activeLabel(country, r.category, r.amount, r.unit, r.basis)}</td>)}</tr>
              <tr><th>{t(L, "compare.row.reviews")}</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.rating != null && r.review_count ? tp(L, "compare.row.rating", r.review_count, { rating: num(r.rating, 1) }) : "–"}</td>)}</tr>
              <tr><th>{t(L, "compare.row.ingredientCount")}</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.ingredient_count ?? "–"}</td>)}</tr>
              <tr><th>{t(L, "compare.row.sweeteners")}</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.sweeteners ? (r.attributes.sweeteners.join(", ") || t(L, "compare.row.none")) : r.attributes?.no_sweetener ? t(L, "compare.row.noneSheet") : "–"}</td>)}</tr>
              <tr><th>{t(L, "compare.row.additives")}</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.watched_additives ? (r.attributes.watched_additives.join(", ") || t(L, "compare.row.none")) : "–"}</td>)}</tr>
              <tr><th>{t(L, "compare.row.lactose")}</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.lactose_free ? t(L, "compare.row.yesSheet") : t(L, "compare.row.unspecified")}</td>)}</tr>
              {cat === "whey" && <tr><th>{t(L, "compare.row.milk")}</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.milk_origin ? milkOrigin(country, r.attributes.milk_origin) : "–"}</td>)}</tr>}
              <tr><th>{country.madeIn}</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.origin_country === country.code ? t(L, "compare.row.yesFlag", { flag: country.flag }) : t(L, "compare.row.unspecified")}</td>)}</tr>
              {nutriLabels(country).map(([k, label, u]) => items.some((i) => i.nutrition?.[k] != null) ? (
                <tr key={k}><th>{label} <small>{t(L, "compare.row.per100")}</small></th>{items.map(({ row: r, nutrition }) => <td key={r.product_id}>{nutrition?.[k] != null ? `${num(nutrition[k] as number, 1)} ${u}` : "–"}</td>)}</tr>
              ) : null)}
              <tr><th>{t(L, "compare.row.ingredients")}</th>{items.map(({ row: r, ingredients }) => <td key={r.product_id} className="small">{ingredients ?? t(L, "compare.row.ingredientsNone")}</td>)}</tr>
              <tr><th></th>{items.map(({ row: r }) => <td key={r.product_id}><GoButton offerId={r.offer_id} code={r.applied?.code.code} m={goM} /></td>)}</tr>
            </tbody>
          </table>
          <p className="note-small">{t(L, "compare.note")}</p>
        </div>
      ) : (
        <p className="empty">{t(L, "compare.empty")}</p>
      )}
    </>
  );
}
