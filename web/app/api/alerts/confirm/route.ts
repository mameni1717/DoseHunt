import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { alertCountry, alertsPage, ensureAlertsTable } from "@/lib/alerts";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token") ?? "";
  await ensureAlertsTable();
  const rows = await q<{ country: string }>(`update price_alerts set confirmed = true where token = $1 and active returning country`, [token]);
  // Alerte désactivée ou inconnue : la langue reste celle de l'alerte si elle existe encore.
  const iso = rows[0]?.country ?? (await q<{ country: string }>(`select country from price_alerts where token = $1`, [token]))[0]?.country;
  return NextResponse.redirect(alertsPage(alertCountry(iso), rows.length ? "confirmed=1" : "invalid=1"), 303);
}
