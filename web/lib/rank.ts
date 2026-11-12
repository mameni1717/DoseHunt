// Classement : recalcule le prix final selon les réglages de l'utilisateur, puis le prix comparé.
// L'index stocke, pour chaque offre, le prix final par défaut et les trois prix comparés : on en déduit les
// quantités (actif, kg, unités) sans dupliquer les règles de calcul de la collecte.

import { bestCode, type Applied, type PromoCode } from "./codes.ts";
import type { Mode } from "./categories.ts";

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
    return { ...r, final, applied, value, doseNow, kgNow, unitNow };
  });
  const usable = out.filter((r) => r.value != null && isFinite(r.value));
  usable.sort((a, b) => (a.value as number) - (b.value as number));
  if (opts.allFormats) return usable;
  const seen = new Set<number>();
  return usable.filter((r) => (seen.has(r.product_id) ? false : (seen.add(r.product_id), true)));
}

export function formatLabel(r: Pick<IndexRow, "grams" | "units" | "unit_word" | "variant_title">): string {
  if (r.units && r.unit_word && r.unit_word !== "dose") return `${r.units} ${r.unit_word}${r.units > 1 ? "s" : ""}`;
  if (r.grams) return r.grams >= 1000 ? `${(r.grams / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 2 })} kg` : `${r.grams} g`;
  return r.variant_title ?? "";
}
