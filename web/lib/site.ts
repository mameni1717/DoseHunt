import type { Country } from "./country.ts";

export const SITE_URL = (process.env.SITE_URL || "https://dosehunt.com").replace(/\/$/, "");
export const SITE_NAME = "DoseHunt";

/** Mois en toutes lettres pour les titres (« novembre 2026 », « noviembre de 2026 ») : signale une page à jour. */
export function monthYear(country: Country, d = new Date()): string {
  return d.toLocaleDateString(country.locale, { month: "long", year: "numeric" });
}
