// Choix du meilleur code promo : même logique que dosehunt/pricing.py (confiance, paliers, cumul, 1re commande).

export interface PromoCode {
  id: number;
  site_id: string;
  code: string;
  discount_type: string;
  value: number | null;
  min_order: number | null;
  first_order_only: boolean;
  stackable_with_sale: boolean;
  applies_to: unknown;
  confidence: number | null;
  last_confirmed: string | Date | null;
  ends_on: string | Date | null;
  votes_ok: number | null;
  votes_ko: number | null;
  tiers: { min: number; pct: number }[] | null;
  source: string | null;
  origin: string | null;
  missed_runs?: number | null;   // code relevé sur le site, absent des derniers relevés
}

export const MIN_CONFIDENCE = 0.5;
/** Un code relevé sur le site et absent de 2 relevés de suite (environ 16 h) n'est plus appliqué. */
export const MISSED_RUNS_LIMIT = 2;
const HALF_LIFE_DAYS = 90;

function toDate(d: string | Date | null): Date | null {
  if (!d) return null;
  return d instanceof Date ? d : new Date(d);
}

export function effectiveConfidence(c: PromoCode, today = new Date()): number {
  let conf = c.confidence ?? 0.5;
  const last = toDate(c.last_confirmed);
  if (last) {
    const age = Math.max(0, (today.getTime() - last.getTime()) / 86_400_000);
    conf *= Math.pow(0.5, age / HALF_LIFE_DAYS);
  }
  conf += 0.05 * Math.min(c.votes_ok ?? 0, 4);
  conf -= 0.15 * (c.votes_ko ?? 0);
  const end = toDate(c.ends_on);
  if (end && today.getTime() > end.getTime() + 86_400_000) conf = 0;
  if (c.origin === "auto" && (c.missed_runs ?? 0) >= MISSED_RUNS_LIMIT) conf = 0;   // retiré du site
  return Math.max(0, Math.min(1, conf));
}

export function percentFor(c: PromoCode, price: number): number | null {
  if (c.tiers && c.tiers.length) {
    const ok = c.tiers.filter((t) => price >= (t.min || 0)).map((t) => t.pct);
    return ok.length ? Math.max(...ok) : null;
  }
  if (c.min_order && price < c.min_order) return null;
  return c.value;
}

export interface Applied {
  code: PromoCode;
  final: number;
  pct: number | null;
  confidence: number;
}

export function bestCode(
  codes: PromoCode[], siteId: string, category: string, price: number, onSale: boolean,
  opts: { firstOrder: boolean; useCodes: boolean },
): Applied | null {
  if (!opts.useCodes) return null;
  let best: Applied | null = null;
  for (const c of codes) {
    if (c.site_id !== siteId) continue;
    if (c.discount_type === "free_shipping") continue;      // livraison offerte : affichée à part, pas une remise
    if (c.first_order_only && !opts.firstOrder) continue;
    if (onSale && !c.stackable_with_sale) continue;
    if (Array.isArray(c.applies_to) && !c.applies_to.includes(category)) continue;
    const conf = effectiveConfidence(c);
    if (conf < MIN_CONFIDENCE) continue;
    let final: number;
    let pct: number | null = null;
    if (c.discount_type === "percent") {
      pct = percentFor(c, price);
      if (pct == null) continue;
      final = Math.round(price * (1 - pct / 100) * 100) / 100;
    } else {
      if (c.min_order && price < c.min_order) continue;
      final = Math.max(0, Math.round((price - (c.value ?? 0)) * 100) / 100);
    }
    if (!best || final < best.final) best = { code: c, final, pct, confidence: conf };
  }
  return best;
}

export function confidenceLabel(conf: number): string {
  if (conf >= 0.75) return "haute";
  if (conf >= 0.55) return "moyenne";
  return "faible";
}
