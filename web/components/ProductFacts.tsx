import type { Attributes } from "@/lib/rank";
import type { Nutrition } from "@/lib/data";
import { MILK_ORIGINS } from "@/lib/categories";
import { num } from "@/lib/format";

export const NUTRI_LABELS: [keyof Nutrition, string, string][] = [
  ["energy_kcal", "Énergie", "kcal"], ["fat", "Matières grasses", "g"], ["saturated", "dont acides gras saturés", "g"],
  ["carbs", "Glucides", "g"], ["sugars", "dont sucres", "g"], ["fibre", "Fibres", "g"], ["protein", "Protéines", "g"], ["salt", "Sel", "g"],
];

/** Ce que dit la fiche, en clair : sans lactose, édulcorants, origine du lait, additifs souvent évités. */
export function attributeLines(a: Attributes | null | undefined): string[] {
  if (!a) return [];
  const out: string[] = [];
  if (a.lactose_free) out.push("Sans lactose (d'après la fiche)");
  if (a.sweeteners) out.push(a.sweeteners.length ? `Édulcorant${a.sweeteners.length > 1 ? "s" : ""} : ${a.sweeteners.join(", ")}` : "Sans édulcorant");
  else if (a.no_sweetener) out.push("Sans édulcorant (d'après la fiche)");
  else if (a.no_sucralose) out.push("Sans sucralose (d'après la fiche)");
  if (a.milk_origin) out.push(`Lait : ${MILK_ORIGINS[a.milk_origin] ?? a.milk_origin}${a.grass_fed ? ", vaches nourries à l'herbe" : ""}`);
  else if (a.grass_fed) out.push("Vaches nourries à l'herbe");
  if (a.ingredient_count) out.push(`${a.ingredient_count} ingrédient${a.ingredient_count > 1 ? "s" : ""}`);
  if (a.watched_additives?.length) out.push(`Additifs souvent évités : ${a.watched_additives.join(", ")}`);
  return out;
}

export function NutritionTable({ n }: { n: Nutrition | null }) {
  if (!n || Object.keys(n).length === 0) return <p className="note-small">Valeurs nutritionnelles non lues sur la fiche.</p>;
  return (
    <table className="t">
      <thead><tr><th>Pour 100 g</th><th className="r"></th></tr></thead>
      <tbody>
        {NUTRI_LABELS.filter(([k]) => n[k] != null).map(([k, label, u]) => (
          <tr key={k}><td>{label}</td><td className="r">{num(n[k] as number, (n[k] as number) % 1 ? 1 : 0)} {u}</td></tr>
        ))}
      </tbody>
    </table>
  );
}
