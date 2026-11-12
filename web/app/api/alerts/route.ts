import { randomBytes } from "node:crypto";
import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { ensureAlertsTable, sendMail, siteUrl } from "@/lib/alerts";
import { CATEGORY_BY_ID } from "@/lib/categories";
import { currentCountry } from "@/lib/country";

export async function POST(req: Request) {
  const b = await req.json().catch(() => null);
  const email = String(b?.email ?? "").trim().toLowerCase();
  const threshold = Number(b?.threshold);
  const category = String(b?.category ?? "");
  const mode = ["price", "dose", "kg", "unit"].includes(b?.mode) ? b.mode : "dose";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) || email.length > 254)
    return NextResponse.json({ message: "Adresse e-mail invalide." }, { status: 400 });
  if (!CATEGORY_BY_ID[category]) return NextResponse.json({ message: "Catégorie inconnue." }, { status: 400 });
  if (!(threshold > 0 && threshold < 100000)) return NextResponse.json({ message: "Seuil invalide." }, { status: 400 });
  await ensureAlertsTable();
  const [{ n }] = await q<{ n: number }>(`select count(*)::int as n from price_alerts where email = $1 and active`, [email]);
  if (n >= 20) return NextResponse.json({ message: "Tu as déjà 20 alertes actives avec cette adresse." }, { status: 429 });
  const token = randomBytes(24).toString("hex");
  const productId = Number.isFinite(Number(b?.product_id)) && b?.product_id ? Number(b.product_id) : null;
  await q(`insert into price_alerts (email, product_id, category, subcategory, mode, threshold, country, token)
           values ($1, $2, $3, $4, $5, $6, $7, $8)`,
    [email, productId, category, b?.subcategory || null, mode, threshold, currentCountry().code, token]);
  const link = `${siteUrl()}/api/alerts/confirm?token=${token}`;
  const sent = await sendMail(email, "Confirme ton alerte prix DoseHunt",
    `<p>Bonjour,</p><p>Pour activer ton alerte prix, clique ici : <a href="${link}">confirmer l'alerte</a>.</p>
     <p>Si tu n'es pas à l'origine de cette demande, ignore ce message : aucune alerte ne sera envoyée.</p>`);
  if (sent) await q(`update price_alerts set confirm_sent_at = now() where token = $1`, [token]);
  return NextResponse.json({ message: "Alerte enregistrée. Confirme-la grâce à l'e-mail que tu vas recevoir (pense à regarder dans les indésirables)." });
}
