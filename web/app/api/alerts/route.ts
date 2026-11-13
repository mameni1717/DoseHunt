import { randomBytes } from "node:crypto";
import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { alertCountry, confirmMail, ensureAlertsTable, sendMail, siteUrl } from "@/lib/alerts";
import { SPEC_BY_ID } from "@/lib/categories";
import { t } from "@/lib/i18n";

export async function POST(req: Request) {
  const b = await req.json().catch(() => null);
  const country = alertCountry(typeof b?.country === "string" ? b.country : null);   // pays de la page d'origine, défaut FR
  const L = country.lang;
  const email = String(b?.email ?? "").trim().toLowerCase();
  const threshold = Number(b?.threshold);
  const category = String(b?.category ?? "");
  const mode = ["price", "dose", "kg", "unit"].includes(b?.mode) ? b.mode : "dose";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) || email.length > 254)
    return NextResponse.json({ message: t(L, "alerts.api.email") }, { status: 400 });
  if (!SPEC_BY_ID[category]) return NextResponse.json({ message: t(L, "alerts.api.category") }, { status: 400 });
  if (!(threshold > 0 && threshold < 100000)) return NextResponse.json({ message: t(L, "alerts.api.threshold") }, { status: 400 });
  await ensureAlertsTable();
  const [{ n }] = await q<{ n: number }>(`select count(*)::int as n from price_alerts where email = $1 and active`, [email]);
  if (n >= 20) return NextResponse.json({ message: t(L, "alerts.api.tooMany") }, { status: 429 });
  const token = randomBytes(24).toString("hex");
  const productId = Number.isFinite(Number(b?.product_id)) && b?.product_id ? Number(b.product_id) : null;
  await q(`insert into price_alerts (email, product_id, category, subcategory, mode, threshold, country, token)
           values ($1, $2, $3, $4, $5, $6, $7, $8)`,
    [email, productId, category, b?.subcategory || null, mode, threshold, country.code, token]);
  // Lien sans préfixe de pays : confirm lit le pays de l'alerte et redirige vers la bonne version.
  const link = `${siteUrl()}/api/alerts/confirm?token=${token}`;
  const mail = confirmMail(country, link);
  const sent = await sendMail(email, mail.subject, mail.html);
  if (sent) await q(`update price_alerts set confirm_sent_at = now() where token = $1`, [token]);
  return NextResponse.json({ message: t(L, "alerts.api.ok") });
}
