import { ACTIVE_COUNTRIES, href, type Country } from "./country.ts";
import { CATEGORY_SPECS } from "./categories.ts";
import { qc } from "./db.ts";
import { SITE_URL } from "./site.ts";

// Sitemaps : un index (/sitemap.xml) qui pointe vers un sitemap par pays actif (/sitemap-fr.xml, /sitemap-es.xml…).
// Chaque page qui existe dans tous les pays porte ses alternatives de langue (hreflang) ; les fiches produit non.

type Freq = "hourly" | "daily" | "weekly" | "monthly" | "yearly";
interface Entry { path: string; freq: Freq; priority: number; lastmod?: Date; shared: boolean }

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function sitemapName(c: Country): string {
  return `sitemap-${c.path || "fr"}.xml`;
}

export function sitemapIndex(): string {
  const now = new Date().toISOString();
  return `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    ACTIVE_COUNTRIES.map((c) => `<sitemap><loc>${SITE_URL}/${sitemapName(c)}</loc><lastmod>${now}</lastmod></sitemap>`).join("\n") +
    `\n</sitemapindex>\n`;
}

export async function countrySitemap(country: Country): Promise<string> {
  const now = new Date();
  const entries: Entry[] = [
    { path: "/", freq: "hourly", priority: 1, shared: true },
    { path: "/vitamines", freq: "daily", priority: 0.8, shared: true },
    { path: "/comparer", freq: "weekly", priority: 0.5, shared: true },
    { path: "/optimiser", freq: "weekly", priority: 0.6, shared: true },
    { path: "/alertes", freq: "monthly", priority: 0.4, shared: true },
    { path: "/methode", freq: "monthly", priority: 0.4, shared: true },
    { path: "/mentions-legales", freq: "yearly", priority: 0.1, shared: false },
    { path: "/confidentialite", freq: "yearly", priority: 0.1, shared: false },
  ];
  for (const c of CATEGORY_SPECS) {
    entries.push({ path: `/c/${c.id}`, freq: "hourly", priority: 0.9, shared: true });
    for (const sub of c.subs ?? []) entries.push({ path: `/c/${c.id}?sub=${sub}`, freq: "hourly", priority: 0.7, shared: true });
  }
  const products = await qc<{ id: number; t: Date | null }>(
    `select p.id, max(o.collected_at) as t from products p join offers o on o.product_id = p.id
       join index_rows i on i.offer_id = o.id where i.country = $1 and o.country = $1 and p.active and o.active group by p.id`,
    [country.code]).catch(() => []);
  for (const p of products) entries.push({ path: `/p/${p.id}`, freq: "daily", priority: 0.6, lastmod: p.t ?? now, shared: false });

  const others = ACTIVE_COUNTRIES.length > 1 && ACTIVE_COUNTRIES.some((c) => c.code === country.code) ? ACTIVE_COUNTRIES : [];
  const root = others.find((c) => !c.path);
  const urls = entries.map((e) => {
    const alt = e.shared && others.length
      ? others.map((c) => `<xhtml:link rel="alternate" hreflang="${c.hreflang}" href="${esc(SITE_URL + href(c, e.path))}"/>`).join("") +
        (root ? `<xhtml:link rel="alternate" hreflang="x-default" href="${esc(SITE_URL + href(root, e.path))}"/>` : "")
      : "";
    return `<url><loc>${esc(SITE_URL + href(country, e.path))}</loc>${alt}<lastmod>${(e.lastmod ?? now).toISOString()}</lastmod>` +
      `<changefreq>${e.freq}</changefreq><priority>${e.priority}</priority></url>`;
  });
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n` +
    urls.join("\n") + `\n</urlset>\n`;
}
