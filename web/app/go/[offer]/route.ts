import { NextResponse } from "next/server";
import { q } from "@/lib/db";

// Redirection vers le marchand : lien affilié si le site en a un, sinon lien direct. Le clic est compté sans
// donnée personnelle (ni IP ni cookie).
export async function GET(req: Request, { params }: { params: Promise<{ offer: string }> }) {
  const id = Number((await params).offer);
  if (!Number.isInteger(id)) return new NextResponse("Offre inconnue", { status: 404 });
  const [o] = await q<{ url: string; affiliate_template: string | null }>(
    `select o.url, s.affiliate_template from offers o join sites s on s.id = o.site_id where o.id = $1`, [id]);
  if (!o) return new NextResponse("Offre inconnue", { status: 404 });
  const code = new URL(req.url).searchParams.get("code");
  await q(`insert into click_log (offer_id, code, clicked_at) values ($1, $2, now())`, [id, code ? code.slice(0, 60) : null]);
  const target = o.affiliate_template ? o.affiliate_template.replace("{url}", encodeURIComponent(o.url)) : o.url;
  const res = NextResponse.redirect(target, 302);
  res.headers.set("X-Robots-Tag", "noindex, nofollow");
  res.headers.set("Referrer-Policy", "no-referrer-when-downgrade");
  return res;
}
