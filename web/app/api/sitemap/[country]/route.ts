import { ACTIVE_COUNTRIES } from "@/lib/country";
import { countrySitemap } from "@/lib/sitemap";

export const dynamic = "force-dynamic";

// Servi sous /sitemap-<code>.xml (réécriture dans next.config.ts). Seuls les pays actifs ont un sitemap.
export async function GET(_req: Request, { params }: { params: Promise<{ country: string }> }) {
  const seg = (await params).country.toLowerCase();
  const country = ACTIVE_COUNTRIES.find((c) => (c.path || "fr") === seg);
  if (!country) return new Response("Not found", { status: 404 });
  return new Response(await countrySitemap(country), {
    headers: { "content-type": "application/xml; charset=utf-8", "cache-control": "public, s-maxage=3600, stale-while-revalidate=86400" },
  });
}
