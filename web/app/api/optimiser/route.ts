import { NextResponse } from "next/server";
import { getOptimizerData, searchPinnable } from "@/lib/data";
import { SPEC_BY_ID } from "@/lib/categories";
import { COUNTRIES, DEFAULT_COUNTRY, countryByIso } from "@/lib/country";
import { KIND_BY_CATEGORY, optimize, type Need } from "@/lib/optimize";

export const dynamic = "force-dynamic";

// Recherche d'un produit à épingler : /api/optimiser?country=FR&cat=whey&q=impact (pays inconnu ou absent : France)
export async function GET(req: Request) {
  const sp = new URL(req.url).searchParams;
  const country = countryByIso(sp.get("country")) ?? COUNTRIES[DEFAULT_COUNTRY];
  const cat = sp.get("cat") ?? "";
  if (!SPEC_BY_ID[cat]) return NextResponse.json([]);
  return NextResponse.json(await searchPinnable(country, cat, (sp.get("q") ?? "").slice(0, 80)));
}

// Calcul : { country, needs: [{ cat, sub, qty, pin }], firstOrder, useCodes } → les 3 meilleurs paniers sur un seul site.
export async function POST(req: Request) {
  const body = await req.json().catch(() => null) as { country?: string; needs?: Need[]; firstOrder?: boolean; useCodes?: boolean } | null;
  const country = countryByIso(typeof body?.country === "string" ? body.country : null) ?? COUNTRIES[DEFAULT_COUNTRY];
  const needs = (body?.needs ?? []).slice(0, 12).filter((n) =>
    n && KIND_BY_CATEGORY[n.cat] && Number.isFinite(Number(n.qty)) && Number(n.qty) > 0)
    .map((n) => ({ cat: n.cat, sub: typeof n.sub === "string" && SPEC_BY_ID[n.cat]?.subs?.includes(n.sub) ? n.sub : null,
                   qty: Math.min(Number(n.qty), 100_000), pin: typeof n.pin === "string" ? n.pin.slice(0, 300) : null,
                   minActive: Number.isFinite(Number(n.minActive)) && Number(n.minActive) > 0 ? Math.min(Number(n.minActive), 100) : null }));
  if (!needs.length) return NextResponse.json({ baskets: [] });
  const { rows, codes, shipping } = await getOptimizerData(country, [...new Set(needs.map((n) => n.cat))]);
  const opts = { firstOrder: !!body?.firstOrder, useCodes: body?.useCodes !== false };
  const baskets = optimize(needs, rows, codes, shipping, opts).map((b) => ({
    ...b,
    lines: b.lines.map((l) => ({
      cat: l.need.cat, copies: l.copies, covered: l.covered, cost: l.cost,
      offer_id: l.row.offer_id, product_id: l.row.product_id, brand: l.row.brand, name: l.row.name,
      flavour: l.row.flavour, grams: l.row.grams, units: l.row.units, unit_word: l.row.unit_word,
      variant_title: l.row.variant_title, price: l.row.price, compare_at_price: l.row.compare_at_price,
      image_url: l.row.image_url ?? null,
    })),
  }));
  return NextResponse.json({ baskets });
}
