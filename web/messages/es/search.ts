import type fr from "../fr/search.ts";

// Textes espagnols (search) : mêmes clés que le français (vérifié par TypeScript et par le test de complétude).
const es: Record<keyof typeof fr, string> = {
  "search.meta.title": "Búsqueda",
  "search.placeholder": "whey isolate chocolate, zinc bisglicinato…",
  "search.label": "Buscar",
  "search.button": "Buscar",
  "search.none": "No hemos encontrado ningún producto para «{q}».",
  "search.results.one": "{n} resultado",
  "search.results.other": "{n} resultados",
};
export default es;
