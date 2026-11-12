import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CodeVote, CopyCode, GoButton } from "@/components/client";
import { CATEGORY_BY_ID, activeLabel } from "@/lib/categories";
import { confidenceLabel, effectiveConfidence, percentFor } from "@/lib/codes";
import { getProduct } from "@/lib/data";
import { ago, dateFr, displayName, eur, num } from "@/lib/format";
import { rerank, formatLabel } from "@/lib/rank";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const id = Number((await params).id);
  const d = Number.isFinite(id) ? await getProduct(id) : null;
  return d ? { title: `${d.product.brand ?? ""} ${d.product.name}`.trim() } : {};
}

const SOURCE_LABEL: Record<string, string> = {
  regex_table: "lue dans le tableau nutritionnel", regex_text: "lue dans la description", llm: "lue par l'IA (citation vérifiée)",
  manual: "vérifiée à la main", assumed: "supposée (voir la note)",
};

function History({ points }: { points: { t: Date; v: number }[] }) {
  if (points.length < 2) {
    return <p className="note-small">Historique : {points.length} relevé{points.length > 1 ? "s" : ""}{points[0] ? ` (${dateFr(points[0].t)}, ${eur(points[0].v)})` : ""}. La courbe apparaîtra avec les relevés suivants.</p>;
  }
  const W = 640, H = 160, P = 28;
  const t0 = points[0].t.getTime(), t1 = points[points.length - 1].t.getTime() || t0 + 1;
  const vs = points.map((p) => p.v);
  const lo = Math.min(...vs) * 0.97, hi = Math.max(...vs) * 1.03;
  const x = (t: number) => P + ((t - t0) / Math.max(1, t1 - t0)) * (W - 2 * P);
  const y = (v: number) => H - P - ((v - lo) / Math.max(0.01, hi - lo)) * (H - 2 * P);
  const d = points.map((p, i) => `${i ? "L" : "M"}${x(p.t.getTime()).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const min = points.reduce((a, b) => (b.v < a.v ? b : a));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Prix entre le ${dateFr(points[0].t)} et le ${dateFr(points[points.length - 1].t)}, minimum ${eur(min.v)}`}>
      <path d={d} fill="none" stroke="var(--blaze)" strokeWidth="2.5" />
      {points.map((p, i) => <circle key={i} cx={x(p.t.getTime())} cy={y(p.v)} r="3" fill="var(--blaze)" />)}
      <text x={P} y={14} fontSize="12" fill="var(--muted)">{eur(hi / 1.03)}</text>
      <text x={P} y={H - 6} fontSize="12" fill="var(--muted)">{dateFr(points[0].t)}</text>
      <text x={W - P} y={H - 6} fontSize="12" fill="var(--muted)" textAnchor="end">{dateFr(points[points.length - 1].t)}</text>
      <text x={x(min.t.getTime())} y={y(min.v) + 16} fontSize="12" fill="var(--ink)" textAnchor="middle">min {eur(min.v)}</text>
    </svg>
  );
}

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isFinite(id)) notFound();
  const d = await getProduct(id);
  if (!d) notFound();
  const { product, actives, rows, offers, history, codes } = d;
  const ranked = rerank(rows, codes, { mode: "dose", allFormats: true, firstOrder: false, useCodes: true });
  const bestByOffer = new Map(ranked.map((r) => [r.offer_id, r]));
  const mainOffer = ranked[0]?.offer_id ?? offers[0]?.id;
  const points = history.filter((h) => h.offer_id === mainOffer).map((h) => ({ t: new Date(h.observed_at), v: h.final_price ?? h.price }));
  const mainLabel = offers.find((o) => o.id === mainOffer);

  return (
    <>
      <section className="summary">
        <div>
          <p><Link href={`/c/${actives[0]?.category ?? ""}`}>← {CATEGORY_BY_ID[actives[0]?.category ?? ""]?.label ?? "Catégories"}</Link></p>
          <h1>{displayName(product.brand, product.name)}</h1>
          <p>Vendu par {product.site_name} · relevé {ago(product.last_seen)} · <a href={product.url} rel="nofollow noopener" target="_blank">fiche du marchand</a></p>
        </div>
      </section>

      <section className="panel">
        <h2>Ce que contient le produit</h2>
        <table className="t">
          <thead><tr><th>Liste</th><th>Teneur réelle</th><th>Source</th></tr></thead>
          <tbody>
            {actives.map((a) => (
              <tr key={a.category}>
                <td><Link href={`/c/${a.category}`}>{CATEGORY_BY_ID[a.category]?.label}</Link>{a.combined ? " (produit combiné)" : ""}</td>
                <td>
                  {a.status === "review" ? "en cours de vérification" : activeLabel(a.category, a.amount, a.unit, a.basis)}
                  {a.salt_label_mg ? ` (étiquette : ${num(a.salt_label_mg)} mg, poids du sel)` : ""}
                  {a.form ? ` · forme ${a.form}` : ""}
                </td>
                <td className="note-small">
                  {SOURCE_LABEL[a.source ?? ""] ?? a.source}{a.evidence ? ` : « ${a.evidence.slice(0, 140)} »` : ""}{a.note ? `. ${a.note}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>Toutes les offres</h2>
        <table className="t">
          <thead><tr><th>Format</th><th className="r">Prix affiché</th><th className="r">Prix final</th><th className="r">Prix comparé</th><th>Relevé</th><th></th></tr></thead>
          <tbody>
            {offers.map((o) => {
              const r = bestByOffer.get(o.id);
              const cat = r ? CATEGORY_BY_ID[r.category] : null;
              return (
                <tr key={o.id}>
                  <td>{formatLabel(o as never) || o.variant_title}{o.flavour ? ` · ${o.flavour}` : ""}{!o.available ? " · indisponible" : ""}</td>
                  <td className="r">{o.compare_at_price ? <s>{eur(o.compare_at_price)}</s> : null} {eur(o.price)}</td>
                  <td className="r">{r ? eur(r.final) : "–"}{r?.applied ? ` (${r.applied.code.code})` : ""}</td>
                  <td className="r">{r?.value != null && cat ? `${num(r.value, 2)} ${cat.modes.dose.unit}` : "–"}</td>
                  <td>{ago(o.collected_at)}</td>
                  <td>{o.available && <GoButton offerId={o.id} code={r?.applied?.code.code} label="Voir" />}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>Historique du prix{mainLabel ? ` · ${formatLabel(mainLabel as never) || mainLabel.variant_title}` : ""}</h2>
        <History points={points} />
      </section>

      <section className="panel">
        <h2>Codes promo connus chez {product.site_name}</h2>
        {codes.length === 0 ? (
          <p className="note-small">Aucun code connu pour ce site.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
            {codes.map((c) => {
              const conf = effectiveConfidence(c);
              const pct = c.tiers?.length ? c.tiers.map((t) => `-${t.pct} %${t.min ? ` dès ${t.min} €` : ""}`).join(", ") : c.value != null ? `-${c.value} %` : "";
              return (
                <li key={c.id} style={{ display: "grid", gap: 4 }}>
                  <span className="chips" style={{ marginTop: 0 }}>
                    <span className="chip code">{c.code} {pct}</span> <CopyCode code={c.code} />
                    {c.first_order_only && <span className="chip first">1re commande</span>}
                    <span className={`chip${conf < 0.5 ? " low" : ""}`}>Fiabilité {confidenceLabel(conf)}{conf < 0.5 ? " : non appliqué au prix" : ""}</span>
                    {c.ends_on && <span className="chip">jusqu'au {dateFr(String(c.ends_on))}</span>}
                    {!c.stackable_with_sale && <span className="chip low">non cumulable avec un prix barré</span>}
                  </span>
                  <span className="note-small">{c.source}{c.last_confirmed ? `, vérifié ${ago(String(c.last_confirmed))}` : ""}{percentFor(c, 50) == null ? " · minimum de commande" : ""}</span>
                  <CodeVote codeId={c.id} />
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}
