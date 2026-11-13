import type { Attributes } from "@/lib/rank";
import type { Nutrition } from "@/lib/data";
import type { Country } from "@/lib/country";
import { milkOrigin } from "@/lib/categories";
import { formatNumber } from "@/lib/format";
import { t, tp, type MessageKey } from "@/lib/i18n";

const NUTRI: [keyof Nutrition, string][] = [
  ["energy_kcal", "kcal"], ["fat", "g"], ["saturated", "g"], ["carbs", "g"], ["sugars", "g"], ["fibre", "g"], ["protein", "g"], ["salt", "g"],
];

/** Lignes du tableau nutritionnel : [champ, libellé dans la langue du pays, unité]. */
export function nutriLabels(country: Country): [keyof Nutrition, string, string][] {
  return NUTRI.map(([k, u]) => [k, t(country.lang, `product.nutri.${k}` as MessageKey), u]);
}

/** Ce que dit la fiche, en clair : sans lactose, édulcorants, origine du lait, additifs souvent évités. */
export function attributeLines(country: Country, a: Attributes | null | undefined): string[] {
  if (!a) return [];
  const L = country.lang;
  const out: string[] = [];
  if (a.lactose_free) out.push(t(L, "product.attr.lactoseFree"));
  if (a.sweeteners) out.push(a.sweeteners.length ? tp(L, "product.attr.sweeteners", a.sweeteners.length, { list: a.sweeteners.join(", ") }) : t(L, "product.attr.noSweetener"));
  else if (a.no_sweetener) out.push(t(L, "product.attr.noSweetenerSheet"));
  else if (a.no_sucralose) out.push(t(L, "product.attr.noSucralose"));
  if (a.milk_origin) out.push(t(L, a.grass_fed ? "product.attr.milkGrass" : "product.attr.milk", { origin: milkOrigin(country, a.milk_origin) }));
  else if (a.grass_fed) out.push(t(L, "product.attr.grass"));
  if (a.ingredient_count) out.push(tp(L, "product.attr.ingredients", a.ingredient_count));
  if (a.watched_additives?.length) out.push(t(L, "product.attr.additives", { list: a.watched_additives.join(", ") }));
  return out;
}

export function NutritionTable({ n, country }: { n: Nutrition | null; country: Country }) {
  const L = country.lang;
  if (!n || Object.keys(n).length === 0) return <p className="note-small">{t(L, "product.nutri.none")}</p>;
  return (
    <table className="t">
      <thead><tr><th>{t(L, "product.nutri.per100")}</th><th className="r"></th></tr></thead>
      <tbody>
        {nutriLabels(country).filter(([k]) => n[k] != null).map(([k, label, u]) => (
          <tr key={k}><td>{label}</td><td className="r">{formatNumber(n[k] as number, country, (n[k] as number) % 1 ? 1 : 0)} {u}</td></tr>
        ))}
      </tbody>
    </table>
  );
}
