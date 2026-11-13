import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Pays du visiteur d'après l'en-tête Vercel, lu par le bandeau de suggestion côté navigateur : les pages elles-mêmes
// ne varient jamais selon le visiteur (elles restent en cache). Aucune donnée enregistrée.
export async function GET(req: Request) {
  const country = req.headers.get("x-vercel-ip-country");
  return NextResponse.json({ country: country && /^[A-Z]{2}$/i.test(country) ? country.toUpperCase() : null },
    { headers: { "cache-control": "private, no-store" } });
}
