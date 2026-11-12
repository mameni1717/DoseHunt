import { test } from "node:test";
import assert from "node:assert/strict";
import { rerank, type IndexRow } from "./rank.ts";
import { bestCode, effectiveConfidence, type PromoCode } from "./codes.ts";

const today = new Date().toISOString().slice(0, 10);

function row(over: Partial<IndexRow>): IndexRow {
  return {
    offer_id: 1, category: "whey", subcategory: "isolate", final_price: 50, dose_value: 62.5, kg_value: 50, unit_value: 1.5,
    unit_label: "€/portion de 30 g", total_active: 800, active_unit: "g", calc: [], combined: false, price: 50,
    compare_at_price: null, available: true, variant_title: "1 kg", flavour: null, grams: 1000, units: null, unit_word: null,
    offer_url: "https://x", collected_at: new Date(), site_id: "a", site_name: "A", product_id: 1, brand: "B", name: "N",
    amount: 80, unit: "g", basis: "per_100g", source: "regex_table", confidence: 0.95, salt_label_mg: null, form: null,
    note: null, evidence: null, ...over,
  };
}

function code(over: Partial<PromoCode>): PromoCode {
  return {
    id: 1, site_id: "a", code: "C10", discount_type: "percent", value: 10, min_order: null, first_order_only: false,
    stackable_with_sale: true, applies_to: "all", confidence: 0.9, last_confirmed: today, ends_on: null, votes_ok: 0,
    votes_ko: 0, tiers: null, source: null, origin: "manual", ...over,
  };
}

test("le code fait passer une offre devant une autre (exemple du cahier des charges)", () => {
  // Whey B : 40 € sans code, 1 kg à 89 % ; Whey A : 37 €, 1 kg à 87 %
  const b = row({ offer_id: 1, product_id: 1, site_id: "b", price: 40, final_price: 40, dose_value: 40 / 0.89 });
  const a = row({ offer_id: 2, product_id: 2, site_id: "a2", price: 37, final_price: 37, dose_value: 37 / 0.87 });
  const codes = [code({ site_id: "b", value: 20 })];
  const r = rerank([a, b], codes, { mode: "dose", allFormats: false, firstOrder: false, useCodes: true });
  assert.equal(r[0].offer_id, 1);
  assert.equal(r[0].final, 32);
  assert.ok(Math.abs((r[0].value as number) - 35.96) < 0.01);
  const sans = rerank([a, b], codes, { mode: "dose", allFormats: false, firstOrder: false, useCodes: false });
  assert.equal(sans[0].offer_id, 2);
});

test("codes 1re commande exclus par défaut, paliers et cumul", () => {
  const first = code({ first_order_only: true, value: 15 });
  assert.equal(bestCode([first], "a", "whey", 50, false, { firstOrder: false, useCodes: true }), null);
  assert.equal(bestCode([first], "a", "whey", 50, false, { firstOrder: true, useCodes: true })?.final, 42.5);
  const duo = code({ tiers: [{ min: 0, pct: 20 }, { min: 70, pct: 25 }] });
  assert.equal(bestCode([duo], "a", "whey", 80, false, { firstOrder: false, useCodes: true })?.pct, 25);
  const noStack = code({ stackable_with_sale: false });
  assert.equal(bestCode([noStack], "a", "whey", 50, true, { firstOrder: false, useCodes: true }), null);
});

test("la confiance baisse avec l'âge et les signalements", () => {
  const old = code({ last_confirmed: new Date(Date.now() - 180 * 86_400_000).toISOString() });
  assert.ok(effectiveConfidence(old) < 0.5);
  assert.ok(effectiveConfidence(code({ votes_ko: 3 })) < 0.5);
  assert.equal(effectiveConfidence(code({ ends_on: "2020-01-01" })), 0);
});

test("une offre par produit sauf « tous les formats »", () => {
  const rows = [row({ offer_id: 1 }), row({ offer_id: 2, price: 90, final_price: 90, dose_value: 56.25, grams: 2000 })];
  assert.equal(rerank(rows, [], { mode: "dose", allFormats: false, firstOrder: false, useCodes: true }).length, 1);
  assert.equal(rerank(rows, [], { mode: "dose", allFormats: true, firstOrder: false, useCodes: true }).length, 2);
});

test("les arômes d'un même produit chez un même marchand sont regroupés, la ligne la moins chère reste", () => {
  const base = { site_id: "eafit", brand: "EAFIT", subcategory: "classique" };
  const rows = [
    row({ ...base, offer_id: 1, product_id: 1, name: "EAFIT Pure Whey Fraise 850g", flavour: "Fraise", dose_value: 40 }),
    row({ ...base, offer_id: 2, product_id: 2, name: "Pure Whey Myrtille 750g", flavour: "Myrtille", dose_value: 38 }),
    row({ ...base, offer_id: 3, product_id: 3, name: "EAFIT Pure whey Café 2,2kg", flavour: "Café", dose_value: 31 }),
    row({ ...base, offer_id: 4, product_id: 4, name: "Pure Whey Isolate Chocolat 750g", flavour: "Chocolat", dose_value: 45 }),
    row({ offer_id: 5, product_id: 5, site_id: "autre", brand: "EAFIT", name: "Pure Whey Fraise 850g", dose_value: 35 }),
  ];
  const r = rerank(rows, [], { mode: "dose", allFormats: false, firstOrder: false, useCodes: true });
  assert.deepEqual(r.map((x) => x.offer_id), [3, 5, 4]);
  assert.equal(r[0].variants, 3);
  assert.equal(r[2].variants, 1);
});

test("sans marque renseignée, le nom du marchand est retiré du nom (« EAFIT Pure Whey » = « Pure Whey » chez EAFIT)", () => {
  const base = { site_id: "eafit", site_name: "EAFIT", brand: null, subcategory: "classique" };
  const rows = [
    row({ ...base, offer_id: 1, product_id: 1, name: "EAFIT Pure Whey Fraise 2,2 kg", dose_value: 64 }),
    row({ ...base, offer_id: 2, product_id: 2, name: "Pure Whey Vanille Intense 2.2 kg", dose_value: 65 }),
  ];
  const r = rerank(rows, [], { mode: "dose", allFormats: false, firstOrder: false, useCodes: true });
  assert.equal(r.length, 1);
  assert.equal(r[0].variants, 2);
});

test("les ruptures de stock passent après toutes les offres disponibles", () => {
  const rows = [
    row({ offer_id: 1, product_id: 1, site_id: "a", name: "A", dose_value: 20, available: false }),
    row({ offer_id: 2, product_id: 2, site_id: "b", name: "B", dose_value: 40 }),
  ];
  const r = rerank(rows, [], { mode: "dose", allFormats: false, firstOrder: false, useCodes: true });
  assert.deepEqual(r.map((x) => x.offer_id), [2, 1]);
});
