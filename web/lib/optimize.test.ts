import { test } from "node:test";
import assert from "node:assert/strict";
import type { IndexRow } from "./rank.ts";
import type { PromoCode } from "./codes.ts";
import { measure, optimize, productKey } from "./optimize.ts";
import { flavourWords } from "./group.ts";

let id = 0;
function row(over: Partial<IndexRow>): IndexRow {
  id += 1;
  return {
    offer_id: id, category: "whey", subcategory: "classique", final_price: 20, dose_value: 1, kg_value: 1, unit_value: 1,
    unit_label: null, total_active: null, active_unit: null, calc: [], combined: false, price: 20, compare_at_price: null,
    available: true, variant_title: "1 kg", flavour: null, grams: 1000, units: null, unit_word: null, offer_url: "https://x",
    collected_at: new Date(), site_id: "a", site_name: "A", product_id: id, brand: "B", name: "Whey", amount: 80, unit: "g",
    basis: "per_100g", source: "regex_table", confidence: 0.9, salt_label_mg: null, form: null, note: null, evidence: null, ...over,
  };
}
function code(over: Partial<PromoCode>): PromoCode {
  return {
    id: 1, site_id: "a", code: "X", discount_type: "percent", value: 10, min_order: null, first_order_only: false,
    stackable_with_sale: true, applies_to: null, confidence: 0.9, last_confirmed: new Date().toISOString(), ends_on: null,
    votes_ok: 0, votes_ko: 0, tiers: null, source: null, origin: null, ...over,
  };
}
const opts = { firstOrder: false, useCodes: true };

test("mesure par type de besoin", () => {
  assert.equal(measure(row({ grams: 1000 }), "grams"), 1000);
  assert.equal(measure(row({ basis: "per_unit", units: 90, unit_word: "gélule", grams: null }), "units"), 90);
  assert.equal(measure(row({ category: "preworkout", basis: "per_serving", amount: 10, grams: 300 }), "portions"), 30);
  assert.equal(measure(row({ basis: "per_unit", units: 90, unit_word: "gélule", grams: 60 }), "grams"), null);
});

test("un seul site, panier complet, plusieurs exemplaires, code et livraison offerte", () => {
  const rows = [
    row({ site_id: "a", site_name: "A", price: 20, grams: 1000 }),
    row({ site_id: "a", site_name: "A", category: "creatine", subcategory: null, price: 15, grams: 300 }),
    row({ site_id: "b", site_name: "B", price: 18, grams: 1000 }),                 // B n'a pas de créatine : exclu
    row({ site_id: "c", site_name: "C", price: 12, grams: 500 }),                  // 2 × 500 g = 24 €
    row({ site_id: "c", site_name: "C", category: "creatine", subcategory: null, price: 14, grams: 500 }),
  ];
  const needs = [{ cat: "whey", qty: 1000 }, { cat: "creatine", qty: 300 }];
  const ship = new Map<string, number | null>([["a", 30], ["c", 60]]);
  const res = optimize(needs, rows, [code({ site_id: "a", value: 10 })], ship, opts);
  assert.deepEqual(res.map((b) => b.site_id), ["a", "c"]);
  const a = res[0];
  assert.equal(a.subtotal, 35);
  assert.equal(a.code?.discount, 3.5);
  assert.equal(a.total, 31.5);
  assert.equal(a.freeShipping, true);
  const c = res[1];
  assert.equal(c.lines[0].copies, 2);
  assert.equal(c.total, 38);
  assert.equal(c.missingForFree, 22);
});

test("minimum de commande, 1re commande, promo non cumulable", () => {
  const rows = [row({ site_id: "a", price: 40, compare_at_price: 50 })];
  const needs = [{ cat: "whey", qty: 1000 }];
  const ship = new Map<string, number | null>();
  assert.equal(optimize(needs, rows, [code({ min_order: 50 })], ship, opts)[0].code, null);
  assert.equal(optimize(needs, rows, [code({ first_order_only: true })], ship, opts)[0].code, null);
  assert.equal(optimize(needs, rows, [code({ first_order_only: true })], ship, { ...opts, firstOrder: true })[0].code?.discount, 4);
  assert.equal(optimize(needs, rows, [code({ stackable_with_sale: false })], ship, opts)[0].code, null);
  assert.equal(optimize(needs, rows, [code({ discount_type: "amount", value: 5 })], ship, opts)[0].total, 35);
});

test("produit épinglé : le même produit sur chaque site, sinon site exclu", () => {
  const rows = [
    row({ site_id: "a", site_name: "A", brand: "Bulk", name: "Pure Whey 1kg", price: 25 }),
    row({ site_id: "a", site_name: "A", brand: "Other", name: "Cheap Whey", price: 10 }),
    row({ site_id: "b", site_name: "B", brand: "Bulk", name: "Pure Whey (1 kg)", price: 22 }),
    row({ site_id: "c", site_name: "C", brand: "Other", name: "Cheap Whey", price: 9 }),
  ];
  const pin = productKey(rows[0], flavourWords(rows.map((r) => r.flavour)));
  const res = optimize([{ cat: "whey", qty: 1000, pin }], rows, [], new Map(), opts);
  assert.deepEqual(res.map((b) => b.site_id), ["b", "a"]);
  assert.equal(res[1].lines[0].row.name, "Pure Whey 1kg");
});

test("à total proche, le site avec livraison offerte passe devant", () => {
  const rows = [row({ site_id: "a", price: 30 }), row({ site_id: "b", price: 33 })];
  const res = optimize([{ cat: "whey", qty: 1000 }], rows, [], new Map([["b", 30]]), opts);
  assert.equal(res[0].site_id, "b");
});

test("2,5 kg : combinaison de formats d'un même produit plutôt que 5 × 500 g", () => {
  const rows = [
    row({ site_id: "a", site_name: "A", price: 12, grams: 500 }),
    row({ site_id: "a", site_name: "A", price: 20, grams: 1000 }),
    row({ site_id: "a", site_name: "A", price: 36, grams: 2000 }),
  ];
  const [b] = optimize([{ cat: "whey", qty: 2500 }], rows, [], new Map(), { firstOrder: false, useCodes: false });
  assert.deepEqual(b.lines.map((l) => [l.row.grams, l.copies]), [[2000, 1], [500, 1]]);
  assert.equal(b.subtotal, 48);
});

test("1,5 kg : pas de surplus inutile quand 1 kg + 500 g coûte moins que 2 kg", () => {
  const rows = [
    row({ site_id: "a", site_name: "A", price: 12, grams: 500 }),
    row({ site_id: "a", site_name: "A", price: 20, grams: 1000 }),
    row({ site_id: "a", site_name: "A", price: 45, grams: 2000 }),
  ];
  const [b] = optimize([{ cat: "whey", qty: 1500 }], rows, [], new Map(), { firstOrder: false, useCodes: false });
  assert.equal(b.subtotal, 32);
});
