import { Pool as PgPool, types as pgTypes } from "pg";
import { Pool as NeonPool, types as neonTypes } from "@neondatabase/serverless";

// Base Neon : pilote serverless de Neon (WebSocket sur le port 443), recommandé sur Vercel et utilisable
// derrière un pare-feu qui ne laisse passer que le web. Autre PostgreSQL : pilote pg classique.
const url = process.env.DATABASE_URL ?? "";
const isNeon = /neon\.tech/.test(url);

for (const t of [pgTypes, neonTypes]) {
  t.setTypeParser(1700, (v: string) => (v == null ? null : parseFloat(v))); // numeric
  t.setTypeParser(20, (v: string) => (v == null ? null : parseInt(v, 10))); // bigint (count)
}

type AnyPool = PgPool | NeonPool;
const globalForPool = globalThis as unknown as { __dosehuntPool?: AnyPool };

export const pool: AnyPool =
  globalForPool.__dosehuntPool ??
  (globalForPool.__dosehuntPool = isNeon
    ? new NeonPool({ connectionString: url, max: 5 })
    : new PgPool({ connectionString: url, max: 5 }));

export async function q<T = Record<string, unknown>>(sql: string, params: unknown[] = []): Promise<T[]> {
  const res = await (pool as PgPool).query(sql, params);
  return res.rows as T[];
}
