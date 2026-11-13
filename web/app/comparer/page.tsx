import type { Metadata } from "next";
import Link from "next/link";
import { CATEGORIES, CATEGORY_BY_ID, MILK_ORIGINS, activeLabel, modeDef, type Mode } from "@/lib/categories";
import { getCompare, getRanking } from "@/lib/data";
import { displayName, eur, num } from "@/lib/format";
import { formatLabel, type Ranked } from "@/lib/rank";
import { NUTRI_LABELS } from "@/components/ProductFacts";
import { AutoSubmit, GoButton } from "@/components/client";
import { brandKey, norm } from "@/lib/group";
import { currentCountry } from "@/lib/country";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Comparer des produits" };

type SP = Record<string, string | string[] | undefined>;
const list = (v: string | string[] | undefined) => (Array.isArray(v) ? v : v ? v.split(",") : []).filter(Boolean);

const value = (r: Ranked, m: Mode) => (m === "dose" ? r.doseNow : m === "kg" ? r.kgNow : r.unitNow);

export default async function Compare({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const ids = list(sp.ids).map(Number).filter(Number.isFinite).slice(0, 8);
  const asked = typeof sp.cat === "string" && CATEGORY_BY_ID[sp.cat] ? sp.cat : undefined;
  const first = asked ? [] : await getCompare(ids.slice(0, 1));
  const cat = asked ?? first[0]?.row.category ?? "whey";
  const items = await getCompare(ids, cat);                 // seulement des produits de la catégorie choisie
  const c = CATEGORY_BY_ID[cat];
  const brands = list(sp.brand);
  const ranking = await getRanking(cat, {}, { mode: c.defaultMode, allFormats: true, firstOrder: false, useCodes: true });
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
  const country = currentCountry();
  const modes = Object.keys(c.modes) as Mode[];
  const bestOf = (f: (r: Ranked) => number | null, lowIsBest = true) => {
    const vals = items.map((i) => f(i.row)).filter((v): v is number => v != null);
    return vals.length ? (lowIsBest ? Math.min(...vals) : Math.max(...vals)) : null;
  };

  return (
    <>
      <section className="summary"><div>
        <h1>Comparer des produits</h1>
        <p>Choisis une catégorie, éventuellement des marques, puis coche 2 produits ou plus. Tu peux aussi cocher « Comparer »
          directement sur les cartes du classement.</p>
      </div></section>

      <form className="controls" action="/comparer">
        <AutoSubmit />
        <div className="row">
          <label className="ctl-label" htmlFor="cat">Catégorie</label>
          <select id="cat" className="filter" name="cat" defaultValue={cat}>
            {CATEGORIES.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
        </div>
        <details className="more" open={brands.length > 0}>
          <summary>Marques{brands.length ? ` (${brands.length})` : " : toutes"}</summary>
          <div className="row checks">
            {facets.brands.map(([k, label]) => (
              <label key={k} className="check"><input type="checkbox" name="brand" value={k} defaultChecked={brands.includes(k)} /> {label}</label>
            ))}
          </div>
        </details>
      </form>

      <form className="controls" action="/comparer">
        <input type="hidden" name="cat" value={cat} />
        {brands.map((b) => <input key={b} type="hidden" name="brand" value={b} />)}
        <div className="row">
          <label className="ctl-label" htmlFor="q">Chercher</label>
          <input id="q" className="filter grow" name="q" defaultValue={q} placeholder={`Nom, marque ou marchand (ruptures comprises)`} />
          <button className="btn ghost" type="submit">Chercher</button>
          {q && <Link className="btn ghost small" href={`/comparer?cat=${cat}${brands.map((b) => `&brand=${b}`).join("")}${ids.length ? `&ids=${ids.join(",")}` : ""}`}>Effacer</Link>}
        </div>
        <div className="pick">
          <p className="note-small">{q ? `${found.length} résultat${found.length > 1 ? "s" : ""} pour « ${q} », en stock ou en rupture.`
            : `Les ${found.length} produits en stock les moins chers. Cherche un nom pour voir aussi les ruptures.`}
            {ids.length ? ` Déjà choisis : ${ids.length}.` : ""}</p>
          {candidates.map((r) => (
            <label key={r.product_id} className="check">
              <input type="checkbox" name="ids" value={r.product_id} defaultChecked={ids.includes(r.product_id)} />
              {displayName(r.brand, r.name, " ")} <small>· {r.site_name} · {num(r.value ?? 0, 2)} {modeDef(cat, c.defaultMode).unit}{r.available ? "" : " · rupture de stock"}</small>
            </label>
          ))}
          {candidates.length === 0 && <p className="note-small">Aucun produit ne correspond.</p>}
        </div>
        <div className="row"><button className="btn blaze" type="submit" formAction="/comparer">Comparer la sélection</button></div>
      </form>

      {items.length >= 2 ? (
        <div className="cmpwrap">
          <table className="t cmp">
            <thead>
              <tr><th></th>{items.map(({ row: r }) => (
                <th key={r.product_id}>
                  {r.image_url && <img src={r.image_url} alt="" width={64} height={64} referrerPolicy="no-referrer" />}
                  <Link href={`/p/${r.product_id}`}>{displayName(r.brand, r.name, " ")}</Link>
                  <small>{r.site_name}{r.available ? "" : " · rupture"}</small>
                </th>))}</tr>
            </thead>
            <tbody>
              <tr><th>Prix</th>{items.map(({ row: r }) => <td key={r.product_id}><b>{eur(r.final)}</b> · {formatLabel(r)}{r.applied ? ` (code ${r.applied.code.code})` : ""}</td>)}</tr>
              {modes.map((m) => {
                const b = bestOf((r) => value(r, m));
                return (
                  <tr key={m}><th>{modeDef(cat, m).label}</th>{items.map(({ row: r }) => {
                    const v = value(r, m);
                    return <td key={r.product_id} className={v != null && v === b ? "win" : ""}>{v != null ? `${num(v, 2)} ${modeDef(cat, m).unit}` : "–"}</td>;
                  })}</tr>
                );
              })}
              <tr><th>{c.activeShare ?? "Teneur"}</th>{items.map(({ row: r }) => <td key={r.product_id}>{activeLabel(r.category, r.amount, r.unit, r.basis)}</td>)}</tr>
              <tr><th>Avis clients</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.rating != null && r.review_count ? `★ ${num(r.rating, 1)} (${r.review_count} avis)` : "–"}</td>)}</tr>
              <tr><th>Nombre d'ingrédients</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.ingredient_count ?? "–"}</td>)}</tr>
              <tr><th>Édulcorants</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.sweeteners ? (r.attributes.sweeteners.join(", ") || "aucun") : r.attributes?.no_sweetener ? "aucun (d'après la fiche)" : "–"}</td>)}</tr>
              <tr><th>Additifs souvent évités</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.watched_additives ? (r.attributes.watched_additives.join(", ") || "aucun") : "–"}</td>)}</tr>
              <tr><th>Sans lactose</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.lactose_free ? "oui (d'après la fiche)" : "non précisé"}</td>)}</tr>
              {cat === "whey" && <tr><th>Origine du lait</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.attributes?.milk_origin ? MILK_ORIGINS[r.attributes.milk_origin] ?? r.attributes.milk_origin : "–"}</td>)}</tr>}
              <tr><th>{country.madeIn}</th>{items.map(({ row: r }) => <td key={r.product_id}>{r.origin_country === country.code ? `oui ${country.flag}` : "non précisé"}</td>)}</tr>
              {NUTRI_LABELS.map(([k, label, u]) => items.some((i) => i.nutrition?.[k] != null) ? (
                <tr key={k}><th>{label} <small>/100 g</small></th>{items.map(({ row: r, nutrition }) => <td key={r.product_id}>{nutrition?.[k] != null ? `${num(nutrition[k] as number, 1)} ${u}` : "–"}</td>)}</tr>
              ) : null)}
              <tr><th>Ingrédients</th>{items.map(({ row: r, ingredients }) => <td key={r.product_id} className="small">{ingredients ?? "non lus sur la fiche"}</td>)}</tr>
              <tr><th></th>{items.map(({ row: r }) => <td key={r.product_id}><GoButton offerId={r.offer_id} code={r.applied?.code.code} /></td>)}</tr>
            </tbody>
          </table>
          <p className="note-small">En vert : le meilleur prix de la ligne. « Additifs souvent évités » est une liste factuelle
            (édulcorants intenses, carraghénanes, dioxyde de titane, huile de palme…), pas un avis médical.</p>
        </div>
      ) : (
        <p className="empty">Coche au moins 2 produits pour lancer la comparaison.</p>
      )}
    </>
  );
}
