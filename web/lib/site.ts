export const SITE_URL = (process.env.SITE_URL || "https://dosehunt.com").replace(/\/$/, "");
export const SITE_NAME = "DoseHunt";

/** Mois en toutes lettres pour les titres (« novembre 2026 ») : signale aux moteurs une page à jour. */
export function monthYear(d = new Date()): string {
  return d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
}
