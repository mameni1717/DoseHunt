// Test de complétude des traductions : chaque langue a toutes les clés du français, non vides, avec les mêmes
// variables ({n}, {cur}…) et les mêmes balises (<link>…</link>).

import { test } from "node:test";
import assert from "node:assert/strict";
import fr from "../messages/fr/index.ts";
import es from "../messages/es/index.ts";

const LANGS: Record<string, Record<string, string>> = { es };

const vars = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
const tags = (s: string) => [...s.matchAll(/<(\w+)>/g)].map((m) => m[1]).sort().join(",");

for (const [lang, msgs] of Object.entries(LANGS)) {
  test(`${lang} : toutes les clés du français, non vides`, () => {
    for (const key of Object.keys(fr)) {
      assert.ok(key in msgs, `${lang} : clé manquante ${key}`);
      assert.ok(String(msgs[key]).trim().length > 0, `${lang} : clé vide ${key}`);
    }
    for (const key of Object.keys(msgs)) assert.ok(key in fr, `${lang} : clé inconnue du français ${key}`);
  });

  test(`${lang} : mêmes variables et balises que le français`, () => {
    for (const [key, s] of Object.entries(fr as Record<string, string>)) {
      assert.equal(vars(msgs[key] ?? ""), vars(s), `${lang} : variables différentes pour ${key}`);
      assert.equal(tags(msgs[key] ?? ""), tags(s), `${lang} : balises différentes pour ${key}`);
    }
  });
}

import { dataText } from "./datatext.ts";
test("textes de la collecte : inchangés en France, traduits en Espagne", () => {
  const note = "créatine monohydrate pure supposée (100 %), sans autre ingrédient déclaré dans le titre";
  assert.equal(dataText("fr", note), note);
  assert.match(dataText("es", note), /^creatina monohidrato pura supuesta/);
  assert.equal(dataText("es", "calculé : 24 g pour 30 g"), "calculado: 24 g por cada 30 g");
  assert.equal(dataText("es", "Caféine"), "Cafeína");
  assert.equal(dataText("es", "Phrase inconnue"), "Phrase inconnue");
});
