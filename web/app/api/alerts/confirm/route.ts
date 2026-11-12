import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { ensureAlertsTable, siteUrl } from "@/lib/alerts";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token") ?? "";
  await ensureAlertsTable();
  const rows = await q<{ id: number }>(`update price_alerts set confirmed = true where token = $1 and active returning id`, [token]);
  return NextResponse.redirect(`${siteUrl()}/alertes?${rows.length ? "confirmed=1" : "invalid=1"}`, 303);
}
