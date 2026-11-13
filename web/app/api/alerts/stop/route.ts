import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { alertCountry, alertsPage, ensureAlertsTable } from "@/lib/alerts";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token") ?? "";
  await ensureAlertsTable();
  const rows = await q<{ country: string }>(`update price_alerts set active = false where token = $1 returning country`, [token]);
  return NextResponse.redirect(alertsPage(alertCountry(rows[0]?.country), "stopped=1"), 303);
}
