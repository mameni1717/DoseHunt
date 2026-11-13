import { sitemapIndex } from "@/lib/sitemap";

export const revalidate = 3600;

export function GET() {
  return new Response(sitemapIndex(), { headers: { "content-type": "application/xml; charset=utf-8" } });
}
