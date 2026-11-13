// Catégories : structure (modes, sous-types, filtres) ici, libellés dans les traductions (messages/<lang>/cats.ts).
// Miroir de config/categories.yaml côté collecte. Les libellés dépendent du pays : categories(country).

import type { Country } from "./country.ts";
import { t, type MessageKey } from "./i18n.ts";

export type Mode = "dose" | "kg" | "unit";

export interface ModeDef { label: string; unit: string; short: string }

export interface Category {
  id: string;
  label: string;
  short: string;
  group: "main" | "vitamins";          // « Vitamines & autres » regroupe les compléments en gélules
  defaultMode: Mode;
  modes: Partial<Record<Mode, ModeDef>>;
  subs?: Record<string, string>;
  activeName: string;                   // « protéine », « zinc »… pour les cartes
  activeShare?: string;                 // libellé du taux d'actif sur les cartes (« Taux de protéine »)
  filters?: ("lactose" | "sweetener" | "sucralose" | "minActive" | "milk")[];
}

/** Structure d'une catégorie, sans texte. modes : d'où vient le libellé de chaque mode (clé de traduction). */
export interface CategorySpec {
  id: string;
  group: "main" | "vitamins";
  defaultMode: Mode;
  modes: Partial<Record<Mode, string>>;   // préfixe de clé : "cat.whey.dose", "cat.kg"…
  subs?: string[];
  filters?: Category["filters"];
}

export const CATEGORY_SPECS: CategorySpec[] = [
  { id: "whey", group: "main", defaultMode: "dose", modes: { dose: "cat.whey.dose", kg: "cat.kg" },
    subs: ["classique", "isolate", "clear", "caseine", "vegane"], filters: ["lactose", "sweetener", "sucralose", "minActive", "milk"] },
  { id: "creatine", group: "main", defaultMode: "dose", modes: { dose: "cat.creatine.dose", kg: "cat.kg" }, filters: ["sweetener"] },
  { id: "preworkout", group: "main", defaultMode: "dose", modes: { dose: "cat.preworkout.dose", kg: "cat.kg" }, filters: ["sweetener", "sucralose"] },
  { id: "collagene", group: "main", defaultMode: "dose", modes: { dose: "cat.collagene.dose", kg: "cat.kg" }, filters: ["sweetener"] },
  { id: "barres", group: "main", defaultMode: "unit", modes: { unit: "cat.barres.unit", dose: "cat.barres.dose", kg: "cat.kg" },
    filters: ["sweetener", "sucralose"] },
  { id: "zinc", group: "vitamins", defaultMode: "dose", modes: { dose: "cat.zinc.dose", unit: "cat.unitMode" } },
  { id: "magnesium", group: "vitamins", defaultMode: "dose", modes: { dose: "cat.magnesium.dose", unit: "cat.unitMode" } },
  { id: "vitamine_d", group: "vitamins", defaultMode: "dose", modes: { dose: "cat.vitamine_d.dose", unit: "cat.vitamine_d.unit" } },
  { id: "vitamine_c", group: "vitamins", defaultMode: "dose", modes: { dose: "cat.vitamine_c.dose", unit: "cat.unitMode" } },
  { id: "omega3", group: "vitamins", defaultMode: "dose", modes: { dose: "cat.omega3.dose", unit: "cat.omega3.unit" } },
  { id: "glutamine", group: "vitamins", defaultMode: "dose", modes: { dose: "cat.glutamine.dose", kg: "cat.kg" } },
];

export const CATEGORY_IDS = CATEGORY_SPECS.map((c) => c.id);
export const SPEC_BY_ID: Record<string, CategorySpec> = Object.fromEntries(CATEGORY_SPECS.map((c) => [c.id, c]));
export const VITAMINS_ID = "vitamines";

function build(country: Country): Category[] {
  const L = country.lang;
  const k = (key: string) => t(L, key as MessageKey, { cur: country.symbol });
  return CATEGORY_SPECS.map((s) => ({
    id: s.id, group: s.group, defaultMode: s.defaultMode, filters: s.filters,
    label: k(`cat.${s.id}.label`), short: k(`cat.${s.id}.short`),
    activeName: k(`cat.${s.id}.activeName`), activeShare: k(`cat.${s.id}.activeShare`),
    modes: Object.fromEntries(Object.entries(s.modes).map(([m, p]) =>
      [m, { label: k(`${p}.label`), unit: k(`${p}.unit`), short: k(`${p}.short`) }])) as Partial<Record<Mode, ModeDef>>,
    subs: s.subs ? Object.fromEntries(s.subs.map((sub) => [sub, k(`cat.${s.id}.sub.${sub}`)])) : undefined,
  }));
}

const cache = new Map<string, { all: Category[]; byId: Record<string, Category> }>();
function forCountry(country: Country) {
  let c = cache.get(country.code);
  if (!c) {
    const all = build(country);
    c = { all, byId: Object.fromEntries(all.map((x) => [x.id, x])) };
    cache.set(country.code, c);
  }
  return c;
}

/** Catégories avec les libellés du pays. */
export function categories(country: Country): Category[] {
  return forCountry(country).all;
}
export function categoryById(country: Country): Record<string, Category> {
  return forCountry(country).byId;
}
export function mainCategories(country: Country): Category[] {
  return categories(country).filter((c) => c.group === "main");
}
export function vitaminCategories(country: Country): Category[] {
  return categories(country).filter((c) => c.group === "vitamins");
}
export function vitaminsGroup(country: Country) {
  return { id: VITAMINS_ID, label: t(country.lang, "cat.vitamins.label"), short: t(country.lang, "cat.vitamins.short") };
}

export function modeOf(c: Category | CategorySpec, m: string | undefined): Mode {
  return m && c.modes[m as Mode] ? (m as Mode) : c.defaultMode;
}

export function modeDef(country: Country, cat: string, mode: Mode): ModeDef {
  const c = categoryById(country)[cat];
  return c.modes[mode] ?? c.modes[c.defaultMode]!;
}

export const MILK_CODES = ["FR", "IE", "NL", "DE", "NZ", "EU", "ES"];
export function milkOrigin(country: Country, code: string): string {
  return MILK_CODES.includes(code) ? t(country.lang, `cat.milk.${code}` as MessageKey) : code;
}

export function activeLabel(country: Country, cat: string, amount: number | null, unit: string | null, basis: string | null): string {
  const L = country.lang;
  if (amount == null) return t(L, "cat.active.unknown");
  const c = categoryById(country)[cat];
  const n = amount.toLocaleString(country.locale, { maximumFractionDigits: 1 });
  if (basis === "per_serving") return t(L, "cat.active.perServing", { n });
  if (basis === "per_100g" && unit === "g") return t(L, "cat.active.percent", { n });
  if (basis === "per_100g") return t(L, "cat.active.per100", { n, unit: unit ?? "" });
  return t(L, "cat.active.perUnit", { n, unit: unit ?? "", active: c?.activeName ?? t(L, "cat.active.fallback") });
}
