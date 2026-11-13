import { Pool as PgPool, types as pgTypes } from "pg";
import { Pool as NeonPool, neon, types as neonTypes } from "@neondatabase/serverless";
import { unstable_cache } from "next/cache";

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

// ------------------------------------------------------------------ lectures en cache
// Chaque visite interrogeait Neon, et la base restait allumée (et facturée) tant qu'il y avait du trafic.
// Les lectures du site passent maintenant par `qc` : un cache partagé entre les instances Vercel (cache de
// données Next.js, 30 min, étiquette DATA_TAG vidée après chaque collecte par /api/revalidate), doublé d'un
// petit cache en mémoire par instance. Neon n'est réveillée qu'après une collecte ou au plus toutes les 30 min.
// Les écritures (votes, alertes, clics) et les lectures qui doivent être fraîches restent sur `q`.
export const DATA_TAG = "dosehunt-data";
export const DATA_TTL_SECONDS = 1800;

const MEMORY_MAX = 300;
const memory = new Map<string, { at: number; rows: unknown[] }>();

/** Vide le cache en mémoire de cette instance (les autres expirent d'elles-mêmes, 30 min au plus). */
export function clearMemoryCache(): void {
  memory.clear();
}

// Le cache partagé sérialise en JSON : les dates reviennent en texte. On les remet en Date pour que le code
// lise exactement les mêmes valeurs qu'avec une requête directe.
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
function revive<T>(rows: T[]): T[] {
  for (const row of rows as Record<string, unknown>[]) {
    if (!row || typeof row !== "object") continue;
    for (const k of Object.keys(row)) {
      const v = row[k];
      if (typeof v === "string" && v.length <= 35 && ISO.test(v)) row[k] = new Date(v);
    }
  }
  return rows;
}

/** Lecture mise en cache 30 min (voir plus haut). La clé couvre la requête et tous ses paramètres. */
export async function qc<T = Record<string, unknown>>(sql: string, params: unknown[] = []): Promise<T[]> {
  if (process.env.DOSEHUNT_NO_CACHE === "1") return q<T>(sql, params);
  const key = sql + "\u0000" + JSON.stringify(params);
  const hit = memory.get(key);
  if (hit && Date.now() - hit.at < DATA_TTL_SECONDS * 1000) return structuredClone(hit.rows) as T[];
  let rows: T[];
  try {
    const cached = unstable_cache(() => q<T>(sql, params), ["dosehunt-q", key],
                                  { revalidate: DATA_TTL_SECONDS, tags: [DATA_TAG] });
    rows = revive(await cached());
  } catch (err) {
    // Hors contexte Next (tests, scripts) ou cache indisponible : lecture directe.
    if (err instanceof Error && /incrementalCache missing|static generation store/i.test(err.message)) rows = await q<T>(sql, params);
    else throw err;
  }
  if (memory.size >= MEMORY_MAX) memory.delete(memory.keys().next().value as string);
  memory.set(key, { at: Date.now(), rows });
  return structuredClone(rows) as T[];
}
