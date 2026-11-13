import type { Country } from "./country.ts";
import { t } from "./i18n.ts";

/** Prix dans la devise et le format du pays (« 12,34 € », « £12.34 »). */
export function formatMoney(n: number | null | undefined, country: Country): string {
  return n == null ? "–" : n.toLocaleString(country.locale, { style: "currency", currency: country.currency, minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatNumber(n: number, country: Country, d = 0): string {
  return n.toLocaleString(country.locale, { minimumFractionDigits: d, maximumFractionDigits: d });
}

/** « il y a 5 min », « hace 5 min »… */
export function ago(d: Date | string | null | undefined, country: Country): string {
  if (!d) return t(country.lang, "common.ago.unknown");
  const tm = typeof d === "string" ? new Date(d) : d;
  const mins = Math.round((Date.now() - tm.getTime()) / 60000);
  if (mins < 60) return t(country.lang, "common.ago.min", { n: Math.max(1, mins) });
  const h = Math.round(mins / 60);
  if (h < 48) return t(country.lang, "common.ago.h", { n: h });
  return t(country.lang, "common.ago.date", { date: tm.toLocaleDateString(country.locale) });
}

/** Date courte jj/mm/aaaa dans le format du pays. */
export function formatDate(d: Date | string | null | undefined, country: Country): string {
  if (!d) return "–";
  const tm = typeof d === "string" ? new Date(d) : d;
  return tm.toLocaleDateString(country.locale, { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function qs(base: Record<string, string | undefined>, change: Record<string, string | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...base, ...change })) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** « Grenade » + « Grenade Soft Core Protein Bar » → pas de marque répétée. */
export function displayName(brand: string | null | undefined, name: string, sep = " · "): string {
  if (!brand) return name;
  const norm = (s: string) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  return norm(name).startsWith(norm(brand)) ? name : `${brand}${sep}${name}`;
}

/** Nom sans la marque en tête (la marque est affichée à part sur les cartes). */
export function stripBrand(brand: string | null | undefined, name: string): string {
  if (!brand) return name;
  const norm = (x: string) => x.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const n = norm(name), b = norm(brand).trim();
  if (b && n.startsWith(b)) {
    const rest = name.slice(brand.length).replace(/^[\s·:|–-]+/, "");
    return rest || name;
  }
  return name;
}

/** Extrait de fiche affiché entre guillemets : sans mot coupé au début ni à la fin. */
export function snippet(s: string | null | undefined, max = 160): string {
  if (!s) return "";
  let t = s.replace(/\s*\|\s*/g, " · ").replace(/\s+/g, " ").trim();
  const cutStart = /^[a-zà-ÿ]/.test(t) && !/^(?:fabriqu|made|produit|con[çc]u|formul|lait|sans|avec|hecho|elaborad|producid|leche|sin|con)/i.test(t);
  if (cutStart && t.includes(" ")) t = "…" + t.slice(t.indexOf(" ") + 1);
  if (t.length > max) t = t.slice(0, t.lastIndexOf(" ", max)) + "…";
  return t;
}
