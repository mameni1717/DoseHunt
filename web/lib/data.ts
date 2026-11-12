import { q } from "./db.ts";
import type { PromoCode } from "./codes.ts";
import { rerank, type IndexRow, type RankOptions, type Ranked } from "./rank.ts";

const COUNTRY = "FR";

const ROW_SELECT = `
  select i.offer_id, i.category, i.subcategory, i.final_price, i.dose_value, i.kg_value, i.unit_value, i.unit_label,
         i.total_active, i.active_unit, i.calc, i.combined,
         o.price, o.compare_at_price, o.variant_title, o.flavour, o.grams, o.units, o.unit_word, o.url as offer_url,
         o.collected_at, o.site_id, s.name as site_name,
         p.id as product_id, p.brand, p.name,
         a.amount, a.unit, a.basis, a.source, a.confidence, a.salt_label_mg, a.form, a.note, a.evidence
    from index_rows i
    join offers o on o.id = i.offer_id
    join products p on p.id = o.product_id
    join sites s on s.id = o.site_id
    join product_actives a on a.product_id = p.id and a.category = i.category
   where i.country = $1 and o.active and o.available and p.active`;

export interface Filters {
  sub?: string;
  site?: string;
  brand?: string;
  form?: string;
}

export async function getCodes(): Promise<PromoCode[]> {
  return q<PromoCode>(`select * from promo_codes where country = $1`, [COUNTRY]);
}

export async function getRanking(cat: string, filters: Filters, opts: RankOptions): Promise<{ rows: Ranked[]; facets: Facets }> {
  const params: unknown[] = [COUNTRY, cat];
  let sql = ROW_SELECT + ` and i.category = $2`;
  const base = await q<IndexRow>(sql, params);
  const facets = buildFacets(base);
  const filtered = base.filter((r) =>
    (!filters.sub || r.subcategory === filters.sub) &&
    (!filters.site || r.site_id === filters.site) &&
    (!filters.brand || (r.brand ?? "") === filters.brand) &&
    (!filters.form || (r.form ?? "") === filters.form));
  return { rows: rerank(filtered, await getCodes(), opts), facets };
}

export interface Facets {
  sites: [string, string][];
  brands: string[];
  forms: string[];
}

function buildFacets(rows: IndexRow[]): Facets {
  const sites = new Map<string, string>();
  const brands = new Set<string>();
  const forms = new Set<string>();
  for (const r of rows) {
    sites.set(r.site_id, r.site_name);
    if (r.brand) brands.add(r.brand);
    if (r.form) forms.add(r.form);
  }
  return {
    sites: [...sites.entries()].sort((a, b) => a[1].localeCompare(b[1], "fr")),
    brands: [...brands].sort((a, b) => a.localeCompare(b, "fr")),
    forms: [...forms].sort(),
  };
}

export async function getHome(): Promise<Record<string, { count: number; best: Ranked | null }>> {
  const rows = await q<IndexRow>(ROW_SELECT, [COUNTRY]);
  const codes = await getCodes();
  const byCat = new Map<string, IndexRow[]>();
  for (const r of rows) byCat.set(r.category, [...(byCat.get(r.category) ?? []), r]);
  const out: Record<string, { count: number; best: Ranked | null }> = {};
  for (const [cat, list] of byCat) {
    const ranked = rerank(list, codes, { mode: "dose", allFormats: false, firstOrder: false, useCodes: true });
    out[cat] = { count: ranked.length, best: ranked[0] ?? null };
  }
  return out;
}

export async function getProduct(id: number) {
  const [product] = await q<{
    id: number; site_id: string; site_name: string; brand: string | null; name: string; url: string;
    product_type: string | null; last_seen: Date; active: boolean;
  }>(`select p.id, p.site_id, s.name as site_name, p.brand, p.name, p.url, p.product_type, p.last_seen, p.active
        from products p join sites s on s.id = p.site_id where p.id = $1`, [id]);
  if (!product) return null;
  const actives = await q<{
    category: string; subcategory: string | null; combined: boolean; amount: number | null; unit: string | null;
    basis: string | null; source: string | null; confidence: number | null; evidence: string | null;
    salt_label_mg: number | null; form: string | null; note: string | null; status: string; read_at: Date;
  }>(`select category, subcategory, combined, amount, unit, basis, source, confidence, evidence, salt_label_mg, form,
             note, status, read_at from product_actives where product_id = $1 order by category`, [id]);
  const rows = await q<IndexRow>(ROW_SELECT.replace("and o.available", "") + ` and p.id = $2`, [COUNTRY, id]);
  const offers = await q<{
    id: number; variant_title: string | null; flavour: string | null; price: number; compare_at_price: number | null;
    available: boolean; url: string; collected_at: Date; grams: number | null; units: number | null; unit_word: string | null;
  }>(`select id, variant_title, flavour, price, compare_at_price, available, url, collected_at, grams, units, unit_word
        from offers where product_id = $1 and active order by coalesce(grams, 0), coalesce(units, 0), variant_title`, [id]);
  const history = await q<{ offer_id: number; observed_at: Date; price: number; final_price: number | null; best_code: string | null }>(
    `select h.offer_id, h.observed_at, h.price, h.final_price, h.best_code
       from price_history h join offers o on o.id = h.offer_id
      where o.product_id = $1 order by h.observed_at`, [id]);
  const codes = (await getCodes()).filter((c) => c.site_id === product.site_id);
  return { product, actives, rows, offers, history, codes };
}

function normalize(s: string): string {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

export async function search(text: string): Promise<Ranked[]> {
  const words = normalize(text).split(" ").filter((w) => w.length >= 2).slice(0, 6);
  if (!words.length) return [];
  const params: unknown[] = [COUNTRY];
  const conds = words.map((w) => {
    params.push(`%${w}%`);
    const n = params.length;
    return `(p.canonical_key like $${n} or lower(s.name) like $${n} or i.category like $${n} or coalesce(a.form, '') like $${n})`;
  });
  const rows = await q<IndexRow>(ROW_SELECT + ` and ` + conds.join(" and ") + ` limit 400`, params);
  const ranked = rerank(rows, await getCodes(), { mode: "dose", allFormats: false, firstOrder: false, useCodes: true });
  return ranked.slice(0, 60);
}

export async function lastUpdate(): Promise<Date | null> {
  const [r] = await q<{ t: Date | null }>(`select max(finished_at) as t from collection_runs where status in ('ok', 'partial')`);
  if (r?.t) return r.t;
  const [o] = await q<{ t: Date | null }>(`select max(collected_at) as t from offers`);
  return o?.t ?? null;
}
