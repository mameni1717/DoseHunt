// Classement : recalcule le prix final selon les réglages de l'utilisateur, puis le prix comparé.
// L'index stocke, pour chaque offre, le prix final par défaut et les trois prix comparés : on en déduit les
// quantités (actif, kg, unités) sans dupliquer les règles de calcul de la collecte.

import { bestCode, type Applied, type PromoCode } from "./codes.ts";
import { flavourWords, groupKey, norm } from "./group.ts";
import type { Mode } from "./categories.ts";

export interface Attributes {
  lactose_free?: boolean;
  no_sweetener?: boolean;
  no_sucralose?: boolean;
  sweeteners?: string[];
  watched_additives?: string[];
  ingredient_count?: number | null;
  milk_origin?: string;
  grass_fed?: boolean;
  preworkout?: Record<string, { label: string; dose: number; unit: string; ref: number; ok: boolean }>;
}

export interface IndexRow {
  offer_id: number;
  category: string;
  subcategory: string | null;
  final_price: number;
  dose_value: number | null;
  kg_value: number | null;
  unit_value: number | null;
  unit_label: string | null;
  total_active: number | null;
  active_unit: string | null;
  calc: string[] | null;
  combined: boolean;
  price: number;
  compare_at_price: number | null;
  available: boolean;
  variant_title: string | null;
  flavour: string | null;
  grams: number | null;
  units: number | null;
  unit_word: string | null;
  offer_url: string;
  collected_at: string | Date;
  site_id: string;
  site_name: string;
  product_id: number;
  brand: string | null;
  name: string;
  origin_country?: string | null;
  origin_evidence?: string | null;
  image_url?: string | null;
  rating?: number | null;
  review_count?: number | null;
  attributes?: Attributes | null;
  hist_min?: number | null;        // plus bas prix final relevé sur 90 jours
  hist_avg30?: number | null;      // prix habituel : moyenne des relevés des 30 derniers jours
  hist_since?: string | Date | null;
  hist_n?: number | null;          // nombre de relevés (un relevé = un changement de prix)
  free_from?: number | null;       // livraison offerte dès … € chez ce marchand
  free_code?: string | null;       // code « livraison offerte » connu
  amount: number | null;
  unit: string | null;
  basis: string | null;
  source: string | null;
  confidence: number | null;
  salt_label_mg: number | null;
  form: string | null;
  note: string | null;
  evidence: string | null;
}

export interface Ranked extends IndexRow {
  variants: number;       // arômes / déclinaisons regroupés sous cette ligne (1 = pas de regroupement)
  final: number;
  applied: Applied | null;
  value: number | null;
  doseNow: number | null;
  kgNow: number | null;
  unitNow: number | null;
}

export interface RankOptions {
  mode: Mode;
  allFormats: boolean;
  firstOrder: boolean;
  useCodes: boolean;
}

const den = (final: number, v: number | null) => (v && v > 0 ? final / v : null);

export function rerank(rows: IndexRow[], codes: PromoCode[], opts: RankOptions): Ranked[] {
  const out: Ranked[] = rows.map((r) => {
    const applied = bestCode(codes, r.site_id, r.category, r.price, r.compare_at_price != null, opts);
    const final = applied ? applied.final : r.price;
    const dDen = den(r.final_price, r.dose_value);
    const kDen = den(r.final_price, r.kg_value);
    const uDen = den(r.final_price, r.unit_value);
    const doseNow = dDen ? final / dDen : null;
    const kgNow = kDen ? final / kDen : null;
    const unitNow = uDen ? final / uDen : null;
    const value = opts.mode === "dose" ? doseNow : opts.mode === "kg" ? kgNow : unitNow;
    return { ...r, variants: 1, final, applied, value, doseNow, kgNow, unitNow };
  });
  const usable = out.filter((r) => r.value != null && isFinite(r.value));
  // En stock d'abord, puis du moins cher au plus cher ; les ruptures suivent, dans le même ordre.
  usable.sort((a, b) => Number(!a.available) - Number(!b.available) || (a.value as number) - (b.value as number));
  if (opts.allFormats) return usable;
  // Un seul produit par marchand, tous arômes et formats confondus : on garde la ligne au meilleur ratio
  // pour le mode choisi, et on compte les arômes regroupés (« à partir de »).
  const flavours = flavourWords(rows.map((r) => r.flavour));
  const groups = new Map<string, { best: Ranked; tastes: Set<string> }>();
  for (const r of usable) {
    const key = groupKey(r, flavours);
    const taste = `${r.product_id}|${norm(r.flavour ?? "")}`;
    const g = groups.get(key);
    if (g) g.tastes.add(taste);
    else groups.set(key, { best: r, tastes: new Set([taste]) });
  }
  return [...groups.values()].map((g) => ({ ...g.best, variants: g.tastes.size }));
}

/** Format affiché (« 2,5 kg », « 90 gélules ») ; locale du pays (défaut France). */
export function formatLabel(r: Pick<IndexRow, "grams" | "units" | "unit_word" | "variant_title">, locale = "fr-FR"): string {
  if (r.units && r.unit_word && r.unit_word !== "dose") return `${r.units} ${r.unit_word}${r.units > 1 ? "s" : ""}`;
  if (r.grams) return r.grams >= 1000 ? `${(r.grams / 1000).toLocaleString(locale, { maximumFractionDigits: 2 })} kg` : `${r.grams} g`;
  return r.variant_title ?? "";
}
