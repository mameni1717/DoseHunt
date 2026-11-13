// Test anti-oubli : toute requête sur une table par pays doit filtrer par pays, sinon un pays affiche les données
// d'un autre. On lit le code source et on vérifie chaque requête SQL écrite en clair.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const TABLES = /\b(?:from|join)\s+(index_rows|offers|promo_codes|shipping)\b/gi;

function queries(src: string): string[] {
  return [...src.matchAll(/`([^`]*)`/g)].map((m) => m[1]).filter((q) => /\bselect\b/i.test(q));
}

for (const file of ["lib/data.ts", "lib/sitemap.ts"]) {
  test(`${file} : chaque requête sur une table par pays filtre par pays`, () => {
    const src = readFileSync(new URL(`../${file}`, import.meta.url), "utf8");
    assert.doesNotMatch(src, /\bconst COUNTRY\b|currentCountry|DOSEHUNT_COUNTRY/, "pays global interdit");
    for (const q of queries(src)) {
      if (!TABLES.test(q)) continue;
      TABLES.lastIndex = 0;
      assert.match(q, /\bcountry\s*=/i, `requête sans condition de pays :\n${q.trim().slice(0, 300)}`);
    }
  });
}

test("ROW_SELECT filtre par pays", () => {
  const src = readFileSync(new URL("./data.ts", import.meta.url), "utf8");
  const row = src.match(/const ROW_SELECT = `([^`]*)`/);
  assert.ok(row);
  assert.match(row[1], /i\.country = \$1/);
});
