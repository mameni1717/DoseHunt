// Pays servi par le site. Aujourd'hui la France seule ; demain le pays choisi par le visiteur à l'arrivée
// (cookie), avec les mêmes libellés tirés de cette table.

export interface Country {
  code: string;          // ISO 3166-1 alpha-2, comme products.origin_country et index_rows.country
  name: string;          // « France »
  flag: string;          // drapeau emoji
  madeIn: string;        // mention affichée sur une offre fabriquée dans ce pays
  filter: string;        // libellé du filtre
}

export const COUNTRIES: Record<string, Country> = {
  FR: { code: "FR", name: "France", flag: "🇫🇷", madeIn: "Fabriqué en France", filter: "Fabriqué en France uniquement" },
};

export const DEFAULT_COUNTRY = "FR";

export function currentCountry(): Country {
  const code = (process.env.DOSEHUNT_COUNTRY || DEFAULT_COUNTRY).toUpperCase();
  return COUNTRIES[code] ?? COUNTRIES[DEFAULT_COUNTRY];
}
