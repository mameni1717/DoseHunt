import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { ensureAlertsTable, siteUrl } from "@/lib/alerts";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token") ?? "";
  await ensureAlertsTable();
  await q(`update price_alerts set active = false where token = $1`, [token]);
  return NextResponse.redirect(`${siteUrl()}/alertes?stopped=1`, 303);
}
