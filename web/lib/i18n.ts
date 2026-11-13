// Traductions : un objet par langue (web/messages/<lang>), mêmes clés partout ; le français est la référence.
// t(lang, clé, variables) remplace {nom} par la variable ; tp() choisit la forme du pluriel (clé.one / clé.other).

import fr from "../messages/fr/index.ts";
import es from "../messages/es/index.ts";
import type { Lang } from "./country.ts";

export type MessageKey = keyof typeof fr;
export type Vars = Record<string, string | number>;

export const MESSAGES: Record<Lang, Record<MessageKey, string>> = { fr, es };

function fill(s: string, vars?: Vars): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

export function t(lang: Lang, key: MessageKey, vars?: Vars): string {
  const s = MESSAGES[lang]?.[key] ?? MESSAGES.fr[key] ?? key;
  return fill(s, vars);
}

/** Pluriel : clés « x.one » et « x.other » (règles de la langue ; en français 0 et 1 sont au singulier). */
export function tp(lang: Lang, key: string, n: number, vars?: Vars): string {
  const form = new Intl.PluralRules(lang).select(n) === "one" ? "one" : "other";
  return t(lang, `${key}.${form}` as MessageKey, { n, ...vars });
}

/** Traducteur lié à une langue, pour alléger les composants : const { t, tp } = translator(lang). */
export function translator(lang: Lang) {
  return {
    t: (key: MessageKey, vars?: Vars) => t(lang, key, vars),
    tp: (key: string, n: number, vars?: Vars) => tp(lang, key, n, vars),
  };
}
