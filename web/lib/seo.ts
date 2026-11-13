import type { Metadata } from "next";
import { ACTIVE_COUNTRIES, href, type Country } from "./country.ts";
import { SITE_URL } from "./site.ts";

/**
 * Canonique + hreflang d'une page qui existe dans chaque pays (accueil, catégories, méthode, Optimiser…) :
 * fr-FR → racine, es-ES → /es/…, x-default → racine. Seuls les pays actifs sont annoncés ; un pays encore caché
 * garde sa canonique mais n'apparaît pas dans les hreflang des autres.
 * Pour une fiche produit (propre à un pays) : shared = false → canonique seule.
 */
export function alternates(country: Country, path: string, shared = true): NonNullable<Metadata["alternates"]> {
  const canonical = `${SITE_URL}${href(country, path)}`;
  if (!shared) return { canonical };
  const list = ACTIVE_COUNTRIES.some((c) => c.code === country.code) ? ACTIVE_COUNTRIES : [];
  if (list.length < 2) return { canonical };
  const languages: Record<string, string> = {};
  for (const c of list) languages[c.hreflang] = `${SITE_URL}${href(c, path)}`;
  const root = list.find((c) => !c.path);
  if (root) languages["x-default"] = `${SITE_URL}${href(root, path)}`;
  return { canonical, languages };
}
