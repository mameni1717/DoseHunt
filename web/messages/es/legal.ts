import type fr from "../fr/legal.ts";

// Textes espagnols (legal) : mêmes clés que le français (vérifié par TypeScript et par le test de complétude).
const es: Record<keyof typeof fr, string> = {
  "legal.mentions.title": "Aviso legal",
  "legal.privacy.title": "Política de privacidad",
};
export default es;
