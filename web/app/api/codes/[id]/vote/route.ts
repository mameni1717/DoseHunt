import { createHash } from "node:crypto";
import { NextResponse } from "next/server";
import { pool } from "@/lib/db";

// « Ce code marche / ne marche plus ». Une empreinte anonyme (hachée, renouvelée chaque jour) limite à un vote
// par personne, par code et par jour. Aucune donnée personnelle n'est conservée.
export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id)) return NextResponse.json({ error: "code inconnu" }, { status: 404 });
  let works: unknown;
  try {
    ({ works } = await req.json());
  } catch {
    return NextResponse.json({ error: "requête invalide" }, { status: 400 });
  }
  if (typeof works !== "boolean") return NextResponse.json({ error: "works doit valoir true ou false" }, { status: 400 });

  const ip = (req.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "inconnu";
  const day = new Date().toISOString().slice(0, 10);
  const salt = process.env.VOTE_SALT ?? "dosehunt";
  const fingerprint = createHash("sha256").update(`${salt}|${ip}|${req.headers.get("user-agent") ?? ""}|${day}`).digest("hex");

  const client = await (pool as import("pg").Pool).connect();
  try {
    await client.query("begin");
    const exists = await client.query(`select 1 from promo_codes where id = $1`, [id]);
    if (!exists.rowCount) {
      await client.query("rollback");
      return NextResponse.json({ error: "code inconnu" }, { status: 404 });
    }
    const dup = await client.query(
      `select 1 from code_votes where code_id = $1 and fingerprint = $2 and voted_at > now() - interval '1 day'`, [id, fingerprint]);
    if (dup.rowCount) {
      await client.query("rollback");
      return NextResponse.json({ ok: true, duplicate: true });
    }
    await client.query(`insert into code_votes (code_id, works, voted_at, fingerprint) values ($1, $2, now(), $3)`, [id, works, fingerprint]);
    await client.query(
      works
        ? `update promo_codes set votes_ok = coalesce(votes_ok, 0) + 1, last_confirmed = current_date where id = $1`
        : `update promo_codes set votes_ko = coalesce(votes_ko, 0) + 1 where id = $1`, [id]);
    await client.query("commit");
    return NextResponse.json({ ok: true });
  } catch (e) {
    await client.query("rollback");
    throw e;
  } finally {
    client.release();
  }
}
