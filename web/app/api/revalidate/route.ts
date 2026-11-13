import { timingSafeEqual } from "node:crypto";
import { revalidatePath, revalidateTag } from "next/cache";
import { NextResponse } from "next/server";
import { DATA_TAG, clearMemoryCache } from "@/lib/db";

export const dynamic = "force-dynamic";

// Appelée par la collecte GitHub une fois les données à jour : vide le cache des lectures Neon et les pages en
// cache, pour que les nouveaux prix s'affichent tout de suite au lieu d'attendre l'expiration (30 min).
// Protégée par un jeton (REVALIDATE_TOKEN) ; sans jeton configuré, la route n'existe pas.
function authorized(req: Request, token: string): boolean {
  const given = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  const a = Buffer.from(given), b = Buffer.from(token);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function POST(req: Request) {
  const token = process.env.REVALIDATE_TOKEN;
  if (!token) return new NextResponse("Not found", { status: 404 });
  if (!authorized(req, token)) return new NextResponse("Unauthorized", { status: 401 });
  revalidateTag(DATA_TAG, { expire: 0 });
  revalidatePath("/", "layout");
  clearMemoryCache();
  return NextResponse.json({ revalidated: true, at: new Date().toISOString() });
}
