import { Pool as PgPool, types as pgTypes } from "pg";
import { Pool as NeonPool, neon, types as neonTypes } from "@neondatabase/serverless";

// Base Neon : pilote serverless de Neon en HTTP (port 443) — une requête = un appel HTTP, aucune connexion
// gardée ouverte entre deux visites. Neon peut ainsi se mettre en veille (scale to zero) dès que le site ne
// l'interroge plus, au lieu de rester allumé tant qu'une fonction Vercel « chaude » garde une connexion.
// Autre PostgreSQL (développement local) : pilote pg classique, pool réduit qui se ferme quand il est inactif.
const url = process.env.DATABASE_URL ?? "";
const isNeon = /neon\.tech/.test(url);

for (const t of [pgTypes, neonTypes]) {
  t.setTypeParser(1700, (v: string) => (v == null ? null : parseFloat(v))); // numeric
  t.setTypeParser(20, (v: string) => (v == null ? null : parseInt(v, 10))); // bigint (count)
}

const globalForDb = globalThis as unknown as { __dosehuntPool?: PgPool };

const sql = isNeon ? neon(url, { types: neonTypes }) : null;

function pgPool(): PgPool {
  return (globalForDb.__dosehuntPool ??= new PgPool({
    connectionString: url, max: 3, idleTimeoutMillis: 10_000, allowExitOnIdle: true,
  }));
}

export async function q<T = Record<string, unknown>>(query: string, params: unknown[] = []): Promise<T[]> {
  if (sql) return (await sql.query(query, params)) as T[];
  const res = await pgPool().query(query, params);
  return res.rows as T[];
}

/** Transaction (votes) : connexion ouverte pour cet appel seulement, puis fermée — rien ne reste ouvert ensuite. */
export async function withClient<R>(fn: (client: { query: PgPool["query"] }) => Promise<R>): Promise<R> {
  if (isNeon) {
    const p = new NeonPool({ connectionString: url, max: 1 });
    const client = await p.connect();
    try {
      return await fn(client as unknown as { query: PgPool["query"] });
    } finally {
      client.release();
      await p.end();
    }
  }
  const client = await pgPool().connect();
  try {
    return await fn(client);
  } finally {
    client.release();
  }
}
