import { qc } from "./db.ts";
import type { PromoCode } from "./codes.ts";
import { rerank, type Attributes, type IndexRow, type RankOptions, type Ranked } from "./rank.ts";

export interface Nutrition { energy_kcal?: number; fat?: number; saturated?: number; carbs?: number; sugars?: number; fibre?: number; protein?: number; salt?: number }
import type { Country } from "./country.ts";
import { brandKey, flavourWords, norm } from "./group.ts";
import { productKey } from "./optimize.ts";
import { SPEC_BY_ID } from "./categories.ts";

// Le pays est le premier argument de chaque fonction et un paramètre SQL ($1) : la clé du cache qc le contient,
// donc chaque pays a son propre cache. Aucune valeur de pays globale ici (test : lib/country-sql.test.ts).

const ROW_SELECT = `
  select i.offer_id, i.category, i.subcategory, i.final_price, i.dose_value, i.kg_value, i.unit_value, i.unit_label,
         i.total_active, i.active_unit, i.calc, i.combined,
         o.price, o.compare_at_price, o.available, o.variant_title, o.flavour, o.grams, o.units, o.unit_word, o.url as offer_url,
         o.collected_at, o.site_id, s.name as site_name,
         p.id as product_id, p.brand, p.name, p.origin_country, p.origin_evidence, p.image_url, p.rating, p.review_count, p.attributes,
         a.amount, a.unit, a.basis, a.source, a.confidence, a.salt_label_mg, a.form, a.note, a.evidence
    from index_rows i
    join offers o on o.id = i.offer_id
    join products p on p.id = o.product_id
    join sites s on s.id = o.site_id
    join product_actives a on a.product_id = p.id and a.category = i.category
   where i.country = $1 and o.active and p.active
     and (i.category <> 'preworkout' or a.basis = 'per_serving')`;   // anciens relevés à la caféine écartés   // ruptures incluses : affichées en grisé, en fin de liste

export interface Filters {
  sub?: string;
  site?: string;
  brand?: string;
  form?: string;
  madeIn?: boolean;     // seulement les produits fabriqués dans le pays du site
  lactose?: boolean;    // sans lactose déclaré
  noSweetener?: boolean;
  noSucralose?: boolean;
  minActive?: number;   // taux d'actif minimum (% pour les poudres)
  milk?: string;        // origine du lait (code pays)
}

export function matches(r: IndexRow, f: Filters, iso: string): boolean {
  const a = r.attributes ?? {};
  return (!f.sub || r.subcategory === f.sub) &&
    (!f.site || r.site_id === f.site) &&
    (!f.brand || brandKey(r.brand) === f.brand) &&
    (!f.form || (r.form ?? "") === f.form) &&
    (!f.madeIn || r.origin_country === iso) &&
    (!f.lactose || a.lactose_free === true) &&
    (!f.noSweetener || a.no_sweetener === true) &&
    (!f.noSucralose || a.no_sucralose === true) &&
    (!f.minActive || (r.basis === "per_100g" && r.unit === "g" && (r.amount ?? 0) >= f.minActive)) &&
    (!f.milk || a.milk_origin === f.milk);
}

export async function getCodes(country: Country): Promise<PromoCode[]> {
  return qc<PromoCode>(`select * from promo_codes where country = $1`, [country.code]);
}

/** Historique (plus bas sur 90 jours, prix habituel sur 30 jours) et livraison offerte, ajoutés aux lignes. */
export async function enrich(country: Country, rows: IndexRow[], codes?: PromoCode[]): Promise<IndexRow[]> {
  if (!rows.length) return rows;
  const ids = [...new Set(rows.map((r) => r.offer_id))];
  const [hist, ship] = await Promise.all([
    qc<{ offer_id: number; min90: number | null; avg30: number | null; since: Date; n: number }>(
      `select offer_id,
              min(coalesce(final_price, price)) as min90,
              avg(coalesce(final_price, price)) filter (where observed_at > now() - interval '30 days') as avg30,
              min(observed_at) as since, count(*)::int as n
         from price_history where offer_id = any($1::int[]) and observed_at > now() - interval '90 days'
        group by offer_id`, [ids]).catch(() => []),
    qc<{ site_id: string; free_threshold: number | null }>(`select site_id, free_threshold from shipping where country = $1`, [country.code]).catch(() => []),
  ]);
  const h = new Map(hist.map((x) => [x.offer_id, x]));
  const s = new Map(ship.map((x) => [x.site_id, x.free_threshold]));
  const freeCodes = new Map<string, string>();
  for (const c of codes ?? await getCodes(country)) if (c.discount_type === "free_shipping" && !freeCodes.has(c.site_id)) freeCodes.set(c.site_id, c.code);
  for (const r of rows) {
    const x = h.get(r.offer_id);
    r.hist_min = x?.min90 != null ? Number(x.min90) : null;
    r.hist_avg30 = x?.avg30 != null ? Number(x.avg30) : null;
    r.hist_since = x?.since ?? null;
    r.hist_n = x?.n ?? 0;
    r.free_from = s.get(r.site_id) ?? null;
    r.free_code = freeCodes.get(r.site_id) ?? null;
  }
  return rows;
}

export async function getRanking(country: Country, cat: string, filters: Filters, opts: RankOptions): Promise<{ rows: Ranked[]; facets: Facets }> {
  const params: unknown[] = [country.code, cat];
  const sql = ROW_SELECT + ` and i.category = $2`;
  const codes = await getCodes(country);
  const base = await enrich(country, await qc<IndexRow>(sql, params), codes);
  const facets = buildFacets(country, base);
  const filtered = base.filter((r) => matches(r, filters, country.code));
  return { rows: rerank(filtered, codes, opts), facets };
}

export interface Facets {
  milk: string[];       // origines du lait présentes dans la catégorie
  madeIn: number;       // nombre d'offres fabriquées dans le pays du site (avant filtres)
  sites: [string, string][];
  brands: [string, string][];   // [clé normalisée, orthographe la plus courante]
  forms: string[];
}

function buildFacets(country: Country, rows: IndexRow[]): Facets {
  const sites = new Map<string, string>();
  const spellings = new Map<string, Map<string, number>>();   // « BioTechUSA », « Biotech USA » → une seule marque
  const forms = new Set<string>();
  for (const r of rows) {
    sites.set(r.site_id, r.site_name);
    if (r.brand) {
      const k = brandKey(r.brand);
      if (!k) continue;
      const m = spellings.get(k) ?? new Map<string, number>();
      m.set(r.brand, (m.get(r.brand) ?? 0) + 1);
      spellings.set(k, m);
    }
    if (r.form) forms.add(r.form);
  }
  const brands: [string, string][] = [...spellings.entries()].map(([k, m]) =>
    [k, [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0][0]]);
  return {
    milk: [...new Set(rows.map((r) => r.attributes?.milk_origin).filter((x): x is string => !!x))].sort(),
    madeIn: new Set(rows.filter((r) => r.origin_country === country.code).map((r) => r.product_id)).size,
    sites: [...sites.entries()].sort((a, b) => a[1].localeCompare(b[1], country.locale)),
    brands: brands.sort((a, b) => a[1].localeCompare(b[1], country.locale, { sensitivity: "base" })),
    forms: [...forms].sort(),
  };
}

export async function getHome(country: Country): Promise<Record<string, { count: number; best: Ranked | null }>> {
  const rows = await qc<IndexRow>(ROW_SELECT, [country.code]);
  const codes = await getCodes(country);
  const byCat = new Map<string, IndexRow[]>();
  for (const r of rows) if (r.available) byCat.set(r.category, [...(byCat.get(r.category) ?? []), r]);
  const out: Record<string, { count: number; best: Ranked | null }> = {};
  for (const [cat, list] of byCat) {
    const mode = SPEC_BY_ID[cat]?.defaultMode ?? "dose";
    const ranked = rerank(list, codes, { mode, allFormats: false, firstOrder: false, useCodes: true });
    out[cat] = { count: ranked.length, best: ranked[0] ?? null };
  }
  return out;
}

/** Fiche d'un produit vendu dans ce pays ; null sinon (pas de fiche française servie sous /es → 404). */
export async function getProduct(country: Country, id: number) {
  const [product] = await qc<{
    id: number; site_id: string; site_name: string; brand: string | null; name: string; url: string;
    product_type: string | null; last_seen: Date; active: boolean;
    origin_country: string | null; origin_evidence: string | null; image_url: string | null; rating: number | null;
    review_count: number | null; ingredients: string | null; nutrition: Nutrition | null; attributes: Attributes | null;
    review_topics: { reviews_read: number; topics: Record<string, { mentions: number; pos: number; neg: number }> } | null;
  }>(`select p.id, p.site_id, s.name as site_name, p.brand, p.name, p.url, p.product_type, p.last_seen, p.active,
             p.origin_country, p.origin_evidence, p.image_url, p.rating, p.review_count, p.ingredients, p.nutrition, p.attributes, p.review_topics
        from products p join sites s on s.id = p.site_id
       where p.id = $1 and exists (select 1 from offers o where o.product_id = p.id and o.country = $2)`, [id, country.code]);
  if (!product) return null;
  const actives = await qc<{
    category: string; subcategory: string | null; combined: boolean; amount: number | null; unit: string | null;
    basis: string | null; source: string | null; confidence: number | null; evidence: string | null;
    salt_label_mg: number | null; form: string | null; note: string | null; status: string; read_at: Date;
  }>(`select category, subcategory, combined, amount, unit, basis, source, confidence, evidence, salt_label_mg, form,
             note, status, read_at from product_actives where product_id = $1 order by category`, [id]);
  const rows = await enrich(country, await qc<IndexRow>(ROW_SELECT + ` and p.id = $2`, [country.code, id]));
  const offers = await qc<{
    id: number; variant_title: string | null; flavour: string | null; price: number; compare_at_price: number | null;
    available: boolean; url: string; collected_at: Date; grams: number | null; units: number | null; unit_word: string | null;
  }>(`select id, variant_title, flavour, price, compare_at_price, available, url, collected_at, grams, units, unit_word
        from offers where product_id = $1 and country = $2 and active order by coalesce(grams, 0), coalesce(units, 0), variant_title`, [id, country.code]);
  const history = await qc<{ offer_id: number; observed_at: Date; price: number; final_price: number | null; best_code: string | null }>(
    `select h.offer_id, h.observed_at, h.price, h.final_price, h.best_code
       from price_history h join offers o on o.id = h.offer_id
      where o.product_id = $1 and o.country = $2 order by h.observed_at`, [id, country.code]);
  const codes = (await getCodes(country)).filter((c) => c.site_id === product.site_id);
  return { product, actives, rows, offers, history, codes };
}

function normalize(s: string): string {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

export async function search(country: Country, text: string): Promise<Ranked[]> {
  const words = normalize(text).split(" ").filter((w) => w.length >= 2).slice(0, 6);
  if (!words.length) return [];
  const params: unknown[] = [country.code];
  const conds = words.map((w) => {
    params.push(`%${w}%`);
    const n = params.length;
    return `(p.canonical_key like $${n} or lower(s.name) like $${n} or i.category like $${n} or coalesce(a.form, '') like $${n})`;
  });
  const rows = await qc<IndexRow>(ROW_SELECT + ` and ` + conds.join(" and ") + ` limit 400`, params);
  const ranked = rerank(rows, await getCodes(country), { mode: "dose", allFormats: false, firstOrder: false, useCodes: true });
  return ranked.slice(0, 60);
}

/** Dernière collecte réussie (toutes les collectes passent par le même job, tous pays confondus). */
export async function lastUpdate(country: Country): Promise<Date | null> {
  const [r] = await qc<{ t: Date | null }>(`select max(finished_at) as t from collection_runs where status in ('ok', 'partial')`);
  if (r?.t) return r.t;
  const [o] = await qc<{ t: Date | null }>(`select max(collected_at) as t from offers where country = $1`, [country.code]);
  return o?.t ?? null;
}

export interface CompareItem {
  row: Ranked;
  ingredients: string | null;
  nutrition: Nutrition | null;
}

/** Produits choisis pour le comparateur : leur meilleure offre (mode par défaut de la catégorie) et leur composition. */
export async function getCompare(country: Country, ids: number[], cat?: string): Promise<CompareItem[]> {
  if (!ids.length) return [];
  const rows = cat
    ? await qc<IndexRow>(ROW_SELECT + ` and p.id = any($2::int[]) and i.category = $3`, [country.code, ids, cat])
    : await qc<IndexRow>(ROW_SELECT + ` and p.id = any($2::int[])`, [country.code, ids]);
  const codes = await getCodes(country);
  await enrich(country, rows, codes);
  const details = await qc<{ id: number; ingredients: string | null; nutrition: Nutrition | null }>(
    `select id, ingredients, nutrition from products where id = any($1::int[])`, [ids]);   // ids déjà filtrés par pays (rows)
  const byId = new Map(details.map((d) => [d.id, d]));
  const out: CompareItem[] = [];
  for (const id of ids) {
    const mine = rows.filter((r) => r.product_id === id);
    if (!mine.length) continue;
    const cat = SPEC_BY_ID[mine[0].category];
    const ranked = rerank(mine.filter((r) => r.category === mine[0].category), codes,
      { mode: cat?.defaultMode ?? "dose", allFormats: true, firstOrder: false, useCodes: true });
    const best = ranked.find((r) => r.available) ?? ranked[0];
    if (best) out.push({ row: best, ingredients: byId.get(id)?.ingredients ?? null, nutrition: byId.get(id)?.nutrition ?? null });
  }
  return out;
}

/** « Optimiser mes achats » : offres en stock des catégories demandées, codes et seuils de livraison offerte. */
export async function getOptimizerData(country: Country, cats: string[]): Promise<{ rows: IndexRow[]; codes: PromoCode[]; shipping: Map<string, number | null> }> {
  const [rows, codes, ship] = await Promise.all([
    qc<IndexRow>(ROW_SELECT + ` and i.category = any($2::text[]) and o.available`, [country.code, cats]),
    getCodes(country),
    qc<{ site_id: string; free_threshold: number | null }>(`select site_id, free_threshold from shipping where country = $1`, [country.code]).catch(() => []),
  ]);
  return { rows, codes, shipping: new Map(ship.map((s) => [s.site_id, s.free_threshold != null ? Number(s.free_threshold) : null])) };
}

/** Recherche d'un produit à épingler : une ligne par produit (clé indépendante du marchand). */
export async function searchPinnable(country: Country, cat: string, text: string): Promise<{ key: string; label: string; sites: number }[]> {
  const words = norm(text).split(/[^a-z0-9%]+/).filter((w) => w.length >= 2);
  if (!words.length) return [];
  const rows = await qc<IndexRow>(ROW_SELECT + ` and i.category = $2 and o.available`, [country.code, cat]);
  const flavours = flavourWords(rows.map((r) => r.flavour));
  const out = new Map<string, { key: string; label: string; sites: Set<string> }>();
  for (const r of rows) {
    if (!words.every((w) => norm(`${r.brand ?? ""} ${r.name}`).includes(w))) continue;
    const key = productKey(r, flavours);
    const g = out.get(key) ?? { key, label: `${r.brand ? r.brand + " · " : ""}${r.name}`, sites: new Set<string>() };
    g.sites.add(r.site_id);
    out.set(key, g);
  }
  return [...out.values()].sort((a, b) => b.sites.size - a.sites.size).slice(0, 12)
    .map((g) => ({ key: g.key, label: g.label, sites: g.sites.size }));
}
