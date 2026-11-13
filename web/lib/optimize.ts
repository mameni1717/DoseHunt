// « Optimiser mes achats » : pour une liste de besoins (1 kg de whey, 300 g de créatine, 12 barres…),
// le panier le moins cher sur UN SEUL marchand, code promo appliqué au panier entier et livraison offerte
// comptée. Fonctions pures : les données viennent de lib/data.ts, les tests de lib/optimize.test.ts.

import { MIN_CONFIDENCE, effectiveConfidence, percentFor, type PromoCode } from "./codes.ts";
import { brandKey, coreName, flavourWords } from "./group.ts";
import type { IndexRow } from "./rank.ts";

export type QtyKind = "grams" | "units" | "portions";

/** Unité dans laquelle on exprime le besoin, par catégorie. */
export const KIND_BY_CATEGORY: Record<string, QtyKind> = {
  whey: "grams", creatine: "grams", collagene: "grams", glutamine: "grams",
  preworkout: "portions",
  barres: "units", zinc: "units", magnesium: "units", vitamine_d: "units", vitamine_c: "units", omega3: "units",
};

export const DEFAULT_QTY: Record<string, number> = {
  whey: 1000, creatine: 500, collagene: 500, glutamine: 500, preworkout: 30,
  barres: 12, zinc: 90, magnesium: 90, vitamine_d: 90, vitamine_c: 90, omega3: 90,
};

export const KIND_LABEL: Record<QtyKind, string> = { grams: "g de produit", units: "unités", portions: "portions" };

export interface Need {
  cat: string;
  sub?: string | null;
  qty: number;
  pin?: string | null;         // clé produit (catégorie | marque | nom sans arôme ni taille) : ce produit-là partout
  pinLabel?: string | null;
  minActive?: number | null;   // taux de protéine minimum (%), poudres lues pour 100 g
}

export interface Line {
  need: Need;
  row: IndexRow;
  copies: number;              // nombre d'exemplaires du format retenu
  covered: number;             // quantité obtenue (dans l'unité du besoin)
  cost: number;                // prix affiché × exemplaires, avant code
}

export interface Basket {
  site_id: string;
  site_name: string;
  lines: Line[];
  subtotal: number;
  code: { code: string; discount: number; pct: number | null; firstOrder: boolean } | null;
  total: number;
  freeFrom: number | null;     // seuil de livraison offerte connu
  freeShipping: boolean;
  missingForFree: number | null;
  freeCode: string | null;     // code « livraison offerte » connu
  rankValue: number;           // total + estimation du port si non offert (classement seulement)
}

export interface OptimizeOptions { firstOrder: boolean; useCodes: boolean }

/** Estimation des frais de port utilisée pour départager, jamais affichée comme un prix. */
export const SHIPPING_ESTIMATE = 6;
const MAX_COPIES = 24;

/** Quantité d'un exemplaire de l'offre dans l'unité du besoin, ou null si l'offre ne s'y prête pas. */
export function measure(r: IndexRow, kind: QtyKind): number | null {
  if (kind === "units") return r.units && r.unit_word && r.unit_word !== "dose" ? r.units : null;
  if (kind === "grams") return r.grams && r.basis !== "per_unit" ? r.grams : null;
  // portions : poids du pot ÷ portion recommandée
  if (r.basis === "per_serving" && r.unit === "g" && r.amount && r.grams) return Math.floor(r.grams / r.amount);
  return null;
}

/** Clé d'un produit indépendante du marchand, pour retrouver « le même produit » sur chaque site. */
export function productKey(r: Pick<IndexRow, "category" | "brand" | "name" | "site_name">, flavours: Set<string>): string {
  return [r.category, brandKey(r.brand), coreName(r.name, r.brand, flavours, r.site_name ?? "")].join("|");
}

function bestLine(need: Need, rows: IndexRow[], flavours: Set<string>): Line | null {
  const kind = KIND_BY_CATEGORY[need.cat] ?? "grams";
  let best: Line | null = null;
  for (const r of rows) {
    if (!r.available || r.category !== need.cat) continue;
    if (need.sub && r.subcategory !== need.sub) continue;
    if (need.pin && productKey(r, flavours) !== need.pin) continue;
    if (!need.pin && r.combined) continue;
    if (need.minActive && !(r.basis === "per_100g" && r.unit === "g" && (r.amount ?? 0) >= need.minActive)) continue;   // « whey + collagène » ne compte pas comme le collagène de la liste
    const m = measure(r, kind);
    if (!m || m <= 0) continue;
    const copies = Math.max(1, Math.ceil(need.qty / m - 1e-9));
    if (copies > MAX_COPIES) continue;
    const cost = Math.round(r.price * copies * 100) / 100;
    const covered = m * copies;
    // le moins cher ; à prix égal, le moins de surplus
    if (!best || cost < best.cost - 0.005 || (Math.abs(cost - best.cost) < 0.005 && covered < best.covered))
      best = { need, row: r, copies, covered, cost };
  }
  return best;
}

/** Meilleur code du marchand sur le panier entier (minimum de commande, paliers, catégories, cumul avec les promos). */
export function basketCode(codes: PromoCode[], siteId: string, lines: Line[], subtotal: number, opts: OptimizeOptions,
                           today = new Date()): Basket["code"] {
  if (!opts.useCodes) return null;
  let best: Basket["code"] = null;
  for (const c of codes) {
    if (c.site_id !== siteId || c.discount_type === "free_shipping") continue;
    if (c.first_order_only && !opts.firstOrder) continue;
    if (effectiveConfidence(c, today) < MIN_CONFIDENCE) continue;
    const eligible = lines.filter((l) =>
      (!Array.isArray(c.applies_to) || c.applies_to.includes(l.need.cat)) &&
      (c.stackable_with_sale || l.row.compare_at_price == null));
    const base = eligible.reduce((s, l) => s + l.cost, 0);
    if (base <= 0) continue;
    let discount: number;
    let pct: number | null = null;
    if (c.discount_type === "percent") {
      pct = percentFor(c, subtotal);            // minimum de commande et paliers : sur le montant du panier
      if (pct == null) continue;
      discount = base * pct / 100;
    } else {
      if (c.min_order && subtotal < c.min_order) continue;
      discount = Math.min(c.value ?? 0, base);
    }
    discount = Math.round(discount * 100) / 100;
    if (discount > 0 && (!best || discount > best.discount))
      best = { code: c.code, discount, pct, firstOrder: c.first_order_only };
  }
  return best;
}

export function optimize(needs: Need[], rows: IndexRow[], codes: PromoCode[], shipping: Map<string, number | null>,
                         opts: OptimizeOptions, top = 3): Basket[] {
  const valid = needs.filter((n) => n.qty > 0 && KIND_BY_CATEGORY[n.cat]);
  if (!valid.length) return [];
  const flavours = flavourWords(rows.map((r) => r.flavour));
  const bySite = new Map<string, IndexRow[]>();
  for (const r of rows) bySite.set(r.site_id, [...(bySite.get(r.site_id) ?? []), r]);
  const freeCodes = new Map<string, string>();
  for (const c of codes) if (c.discount_type === "free_shipping" && !freeCodes.has(c.site_id)) freeCodes.set(c.site_id, c.code);

  const baskets: Basket[] = [];
  for (const [site, siteRows] of bySite) {
    const lines: Line[] = [];
    for (const n of valid) {
      const l = bestLine(n, siteRows, flavours);
      if (!l) break;
      lines.push(l);
    }
    if (lines.length !== valid.length) continue;           // il manque un produit : pas de panier sur ce site
    const subtotal = Math.round(lines.reduce((s, l) => s + l.cost, 0) * 100) / 100;
    const code = basketCode(codes, site, lines, subtotal, opts);
    const total = Math.round((subtotal - (code?.discount ?? 0)) * 100) / 100;
    const freeFrom = shipping.get(site) ?? null;
    const freeShipping = freeFrom != null && total >= freeFrom;
    baskets.push({
      site_id: site, site_name: siteRows[0].site_name, lines, subtotal, code, total, freeFrom, freeShipping,
      missingForFree: freeFrom != null && !freeShipping ? Math.round((freeFrom - total) * 100) / 100 : null,
      freeCode: freeCodes.get(site) ?? null,
      rankValue: total + (freeShipping || freeCodes.has(site) ? 0 : SHIPPING_ESTIMATE),
    });
  }
  baskets.sort((a, b) => a.rankValue - b.rankValue || a.total - b.total);
  return baskets.slice(0, top);
}
