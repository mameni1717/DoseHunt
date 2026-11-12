// Libellés et modes des 8 catégories (miroir de config/categories.yaml côté collecte).

export type Mode = "dose" | "kg" | "unit";

export interface Category {
  id: string;
  label: string;
  short: string;
  defaultMode: Mode;
  modes: Record<Mode, { label: string; unit: string; disabled?: string }>;
  subs?: Record<string, string>;
}

const perUnitNoKg = "Non pertinent pour des gélules ou comprimés";

export const CATEGORIES: Category[] = [
  {
    id: "whey", label: "Whey protéine", short: "Whey", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par kg de protéine", unit: "€/kg prot." },
      kg: { label: "Prix par kg de produit", unit: "€/kg" },
      unit: { label: "Prix par portion de 30 g", unit: "€/portion" },
    },
    subs: { classique: "Whey classique", isolate: "Whey isolate", vegane: "Whey végane" },
  },
  {
    id: "collagene", label: "Collagène", short: "Collagène", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par kg de collagène", unit: "€/kg coll." },
      kg: { label: "Prix par kg de produit", unit: "€/kg" },
      unit: { label: "Prix par portion", unit: "€/portion" },
    },
  },
  {
    id: "barres", label: "Barres protéinées", short: "Barres", defaultMode: "unit",
    modes: {
      dose: { label: "Prix pour 100 g de protéine", unit: "€/100 g prot." },
      kg: { label: "Prix par kg de produit", unit: "€/kg" },
      unit: { label: "Prix par barre", unit: "€/barre" },
    },
  },
  {
    id: "creatine", label: "Créatine", short: "Créatine", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par kg de créatine", unit: "€/kg créat." },
      kg: { label: "Prix par kg de produit", unit: "€/kg" },
      unit: { label: "Prix par portion", unit: "€/portion" },
    },
  },
  {
    id: "zinc", label: "Zinc", short: "Zinc", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par g de zinc réel", unit: "€/g de zinc" },
      kg: { label: "Prix par kg", unit: "€/kg", disabled: perUnitNoKg },
      unit: { label: "Prix par gélule ou comprimé", unit: "€/unité" },
    },
  },
  {
    id: "magnesium", label: "Magnésium", short: "Magnésium", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par g de magnésium réel", unit: "€/g de Mg" },
      kg: { label: "Prix par kg", unit: "€/kg", disabled: perUnitNoKg },
      unit: { label: "Prix par gélule ou comprimé", unit: "€/unité" },
    },
  },
  {
    id: "vitamine_d", label: "Vitamine D", short: "Vitamine D", defaultMode: "dose",
    modes: {
      dose: { label: "Prix pour 100 000 UI", unit: "€/100 000 UI" },
      kg: { label: "Prix par kg", unit: "€/kg", disabled: perUnitNoKg },
      unit: { label: "Prix par gélule ou goutte", unit: "€/unité" },
    },
  },
  {
    id: "omega3", label: "Oméga-3", short: "Oméga-3", defaultMode: "dose",
    modes: {
      dose: { label: "Prix par g d'EPA + DHA", unit: "€/g EPA+DHA" },
      kg: { label: "Prix par kg", unit: "€/kg", disabled: perUnitNoKg },
      unit: { label: "Prix par capsule", unit: "€/capsule" },
    },
  },
];

export const CATEGORY_BY_ID: Record<string, Category> = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));

export function activeLabel(cat: string, amount: number | null, unit: string | null, basis: string | null): string {
  if (amount == null) return "teneur inconnue";
  const n = amount.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
  const what: Record<string, string> = {
    whey: "protéine", barres: "protéine", collagene: "collagène", creatine: "créatine", zinc: "zinc",
    magnesium: "magnésium", vitamine_d: "vitamine D", omega3: "EPA + DHA",
  };
  return basis === "per_100g" ? `${n} ${unit} de ${what[cat]} pour 100 g` : `${n} ${unit} de ${what[cat]} par unité`;
}
