import type { MetadataRoute } from "next";
import { CATEGORIES } from "@/lib/categories";
import { q } from "@/lib/db";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-dynamic";
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const pages: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, lastModified: now, changeFrequency: "hourly", priority: 1 },
    { url: `${SITE_URL}/vitamines`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/comparer`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
    { url: `${SITE_URL}/optimiser`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${SITE_URL}/alertes`, lastModified: now, changeFrequency: "monthly", priority: 0.4 },
    { url: `${SITE_URL}/methode`, lastModified: now, changeFrequency: "monthly", priority: 0.4 },
    { url: `${SITE_URL}/mentions-legales`, lastModified: now, changeFrequency: "yearly", priority: 0.1 },
    { url: `${SITE_URL}/confidentialite`, lastModified: now, changeFrequency: "yearly", priority: 0.1 },
  ];
  for (const c of CATEGORIES) {
    pages.push({ url: `${SITE_URL}/c/${c.id}`, lastModified: now, changeFrequency: "hourly", priority: 0.9 });
    for (const sub of Object.keys(c.subs ?? {}))
      pages.push({ url: `${SITE_URL}/c/${c.id}?sub=${sub}`, lastModified: now, changeFrequency: "hourly", priority: 0.7 });
  }
  const products = await q<{ id: number; t: Date | null }>(
    `select p.id, max(o.collected_at) as t from products p join offers o on o.product_id = p.id
       join index_rows i on i.offer_id = o.id where p.active and o.active group by p.id`).catch(() => []);
  for (const p of products)
    pages.push({ url: `${SITE_URL}/p/${p.id}`, lastModified: p.t ?? now, changeFrequency: "daily", priority: 0.6 });
  return pages;
}
