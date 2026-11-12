// Libellés, modes de comparaison et regroupement des catégories (miroir de config/categories.yaml côté collecte).

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

const kg: ModeDef = { label: "Prix par kg de produit", unit: "€/kg", short: "€/kg produit" };

export const CATEGORIES: Category[] = [
  {
    id: "whey", label: "Protéines en poudre", short: "Whey", group: "main", defaultMode: "dose",
    modes: { dose: { label: "Prix par kg de protéine", unit: "€/kg prot.", short: "€/kg protéine" }, kg },
    subs: { classique: "Whey", isolate: "Whey isolate", clear: "Clear whey", caseine: "Caséine", vegane: "Protéine végétale" },
    activeName: "protéine", activeShare: "Taux de protéine",
    filters: ["lactose", "sweetener", "sucralose", "minActive", "milk"],
  },
  {
    id: "creatine", label: "Créatine", short: "Créatine", group: "main", defaultMode: "dose",
    modes: { dose: { label: "Prix par kg de créatine", unit: "€/kg créat.", short: "€/kg créatine" }, kg },
    activeName: "créatine", activeShare: "Taux de créatine", filters: ["sweetener"],
  },
  {
    id: "preworkout", label: "Pré-workout", short: "Pré-workout", group: "main", defaultMode: "dose",
    modes: { dose: { label: "Prix pour 100 mg de caféine", unit: "€/100 mg caf.", short: "€/100 mg caféine" }, kg },
    activeName: "caféine", activeShare: "Caféine pour 100 g", filters: ["sweetener", "sucralose"],
  },
  {
    id: "collagene", label: "Collagène", short: "Collagène", group: "main", defaultMode: "dose",
    modes: { dose: { label: "Prix par kg de collagène", unit: "€/kg coll.", short: "€/kg collagène" }, kg },
    activeName: "collagène", activeShare: "Taux de collagène", filters: ["sweetener"],
  },
  {
    id: "barres", label: "Barres protéinées", short: "Barres", group: "main", defaultMode: "unit",
    modes: {
      unit: { label: "Prix par barre", unit: "€/barre", short: "€/barre" },
      dose: { label: "Prix pour 100 g de protéine", unit: "€/100 g prot.", short: "€/100 g protéine" },
      kg,
    },
    activeName: "protéine", activeShare: "Protéines par barre", filters: ["sweetener", "sucralose"],
  },
  {
    id: "zinc", label: "Zinc", short: "Zinc", group: "vitamins", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par g de zinc réel", unit: "€/g de zinc", short: "€/g zinc" },
      unit: { label: "Prix par gélule ou comprimé", unit: "€/unité", short: "€/unité" },
    },
    activeName: "zinc", activeShare: "Zinc par unité",
  },
  {
    id: "magnesium", label: "Magnésium", short: "Magnésium", group: "vitamins", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par g de magnésium réel", unit: "€/g de Mg", short: "€/g magnésium" },
      unit: { label: "Prix par gélule ou comprimé", unit: "€/unité", short: "€/unité" },
    },
    activeName: "magnésium", activeShare: "Magnésium par unité",
  },
  {
    id: "vitamine_d", label: "Vitamine D", short: "Vitamine D", group: "vitamins", defaultMode: "dose",
    modes: {
      dose: { label: "Prix pour 100 000 UI", unit: "€/100 000 UI", short: "€/100 000 UI" },
      unit: { label: "Prix par gélule ou goutte", unit: "€/unité", short: "€/unité" },
    },
    activeName: "vitamine D", activeShare: "Vitamine D par unité",
  },
  {
    id: "vitamine_c", label: "Vitamine C", short: "Vitamine C", group: "vitamins", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par g de vitamine C", unit: "€/g vit. C", short: "€/g vitamine C" },
      unit: { label: "Prix par gélule ou comprimé", unit: "€/unité", short: "€/unité" },
    },
    activeName: "vitamine C", activeShare: "Vitamine C par unité",
  },
  {
    id: "omega3", label: "Oméga-3", short: "Oméga-3", group: "vitamins", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par g d'EPA + DHA", unit: "€/g EPA+DHA", short: "€/g EPA + DHA" },
      unit: { label: "Prix par capsule", unit: "€/capsule", short: "€/capsule" },
    },
    activeName: "EPA + DHA", activeShare: "EPA + DHA par capsule",
  },
  {
    id: "glutamine", label: "Glutamine", short: "Glutamine", group: "vitamins", defaultMode: "dose",
    modes: { dose: { label: "Prix par kg de glutamine", unit: "€/kg glut.", short: "€/kg glutamine" }, kg },
    activeName: "glutamine", activeShare: "Taux de glutamine",
  },
];

export const CATEGORY_BY_ID: Record<string, Category> = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));
export const MAIN_CATEGORIES = CATEGORIES.filter((c) => c.group === "main");
export const VITAMIN_CATEGORIES = CATEGORIES.filter((c) => c.group === "vitamins");
export const VITAMINS_GROUP = { id: "vitamines", label: "Vitamines & autres", short: "Vitamines & autres" };

export function modeOf(c: Category, m: string | undefined): Mode {
  return m && c.modes[m as Mode] ? (m as Mode) : c.defaultMode;
}

export function modeDef(cat: string, mode: Mode): ModeDef {
  const c = CATEGORY_BY_ID[cat];
  return c.modes[mode] ?? c.modes[c.defaultMode]!;
}

export const MILK_ORIGINS: Record<string, string> = {
  FR: "France", IE: "Irlande", NL: "Pays-Bas", DE: "Allemagne", NZ: "Nouvelle-Zélande", EU: "Union européenne",
};

export function activeLabel(cat: string, amount: number | null, unit: string | null, basis: string | null): string {
  if (amount == null) return "teneur inconnue";
  const c = CATEGORY_BY_ID[cat];
  const n = amount.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
  if (basis === "per_100g" && unit === "g") return `${n} %`;
  if (basis === "per_100g") return `${n} ${unit} pour 100 g`;
  return `${n} ${unit} de ${c?.activeName ?? "actif"} par unité`;
}
