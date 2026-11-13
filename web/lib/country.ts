// Pays servis par le site. Le pays vient de l'adresse (/es/..., rien pour la France) et voyage explicitement
// jusqu'aux requêtes SQL : aucune valeur globale, aucune lecture au chargement d'un module.

export type Lang = "fr" | "es";

export interface Country {
  code: string;          // ISO 3166-1 alpha-2, comme products.origin_country et index_rows.country
  path: string;          // code de chemin lisible : "" pour la France (racine), "es", "uk"…
  lang: Lang;            // langue de toute la version du site
  locale: string;        // formats des nombres, prix et dates
  hreflang: string;      // balise hreflang (fr-FR, es-ES…)
  ogLocale: string;      // Open Graph (fr_FR…)
  currency: string;      // EUR, GBP, CHF…
  symbol: string;        // symbole affiché dans les unités (« €/kg prot. »)
  name: string;          // nom du pays dans sa langue
  flag: string;          // drapeau emoji
  madeIn: string;        // mention affichée sur une offre fabriquée dans ce pays
  filter: string;        // libellé du filtre
  inCountry: string;     // « en France », « en España » (phrases du résumé)
  active: boolean;       // visible dans le sélecteur, le sitemap et les hreflang
}

export const COUNTRIES: Record<string, Country> = {
  FR: {
    code: "FR", path: "", lang: "fr", locale: "fr-FR", hreflang: "fr-FR", ogLocale: "fr_FR", currency: "EUR", symbol: "€",
    name: "France", flag: "🇫🇷", madeIn: "Fabriqué en France", filter: "Fabriqué en France uniquement", inCountry: "en France",
    active: true,
  },
  ES: {
    code: "ES", path: "es", lang: "es", locale: "es-ES", hreflang: "es-ES", ogLocale: "es_ES", currency: "EUR", symbol: "€",
    name: "España", flag: "🇪🇸", madeIn: "Fabricado en España", filter: "Solo fabricados en España", inCountry: "en España",
    // Caché tant que l'Espagne n'a pas de marchands : la version existe à son adresse mais n'est annoncée nulle part.
    active: false,
  },
};

export const DEFAULT_COUNTRY = "FR";

/** Segment interne de la France (réécriture invisible depuis la racine). */
export const ROOT_SEGMENT = "fr";

export const ALL_COUNTRIES: Country[] = Object.values(COUNTRIES);
export const ACTIVE_COUNTRIES: Country[] = ALL_COUNTRIES.filter((c) => c.active);

/** Segment de route interne d'un pays (France : "fr", les autres : leur code de chemin). */
export function segmentOf(c: Country): string {
  return c.path || ROOT_SEGMENT;
}

/** Pays d'après le segment de route ([country]) ; null si inconnu (→ 404). */
export function countryFromPath(segment: string | undefined | null): Country | null {
  if (!segment) return null;
  const s = segment.toLowerCase();
  return ALL_COUNTRIES.find((c) => segmentOf(c) === s) ?? null;
}

export function countryByIso(iso: string | undefined | null): Country | null {
  if (!iso) return null;
  return COUNTRIES[iso.toUpperCase()] ?? null;
}

/** Adresse interne d'une page dans un pays : France sans préfixe, autres pays /<code> + chemin. */
export function href(country: Country, path = "/"): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (!country.path) return p;
  return p === "/" ? `/${country.path}` : `/${country.path}${p}`;
}
