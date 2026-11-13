import type { MetadataRoute } from "next";
import { ALL_COUNTRIES } from "@/lib/country";
import { SITE_URL } from "@/lib/site";

// Mêmes règles pour la France (racine) et chaque préfixe de pays (/es/recherche…).
export default function robots(): MetadataRoute.Robots {
  const disallow = ["/go/", "/api/", "/recherche", "/comparer?"];
  for (const c of ALL_COUNTRIES) if (c.path) disallow.push(`/${c.path}/recherche`, `/${c.path}/comparer?`);
  return {
    rules: [{ userAgent: "*", allow: "/", disallow }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
