import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CodeVote, CopyCode, GoButton } from "@/components/client";
import { CATEGORY_BY_ID, activeLabel, modeDef } from "@/lib/categories";
import { NutritionTable, attributeLines } from "@/components/ProductFacts";
import { confidenceLabel, effectiveConfidence, percentFor } from "@/lib/codes";
import { getProduct } from "@/lib/data";
import { currentCountry } from "@/lib/country";
import { ago, dateFr, displayName, eur, num, snippet } from "@/lib/format";
import { rerank, formatLabel } from "@/lib/rank";

// Fiche mise en cache 30 min (régénérée à la demande) ; vidée après chaque collecte par /api/revalidate.
export const revalidate = 1800;
// Aucune fiche générée à la construction : chacune l'est à sa première visite, puis servie depuis le cache.
export const dynamicParams = true;
export async function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const id = Number((await params).id);
  const d = Number.isFinite(id) ? await getProduct(id) : null;
  if (!d) return {};
  const name = displayName(d.product.brand, d.product.name, " ");
  const cat = CATEGORY_BY_ID[d.actives[0]?.category ?? ""];
  const title = `${name} : prix, composition et historique`;
  const description = `${name} chez ${d.product.site_name} : vrai prix ${cat ? `(${modeDef(cat.id, cat.defaultMode).label.toLowerCase()})` : ""}, ` +
    `meilleur code promo, composition, valeurs nutritionnelles et historique du prix.`;
  return {
    title, description,
    alternates: { canonical: `/p/${id}` },
    openGraph: { title, description, url: `/p/${id}`, images: d.product.image_url ? [d.product.image_url] : undefined },
  };
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
  const d = points.map((p, i) => i === 0 ? `M${x(p.t.getTime()).toFixed(1)},${y(p.v).toFixed(1)}`
    : `H${x(p.t.getTime()).toFixed(1)} V${y(p.v).toFixed(1)}`).join(" ");     // en escalier : un prix tient jusqu'au suivant
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
  const country = currentCountry();
  if (!d) notFound();
  const { product, actives, rows, offers, history, codes } = d;
  const ranked = rerank(rows, codes, { mode: "dose", allFormats: true, firstOrder: false, useCodes: true });
  const bestByOffer = new Map(ranked.map((r) => [r.offer_id, r]));
  const mainOffer = ranked[0]?.offer_id ?? offers[0]?.id;
  const bestBuy = ranked.find((r) => r.available);
  const fallbackBuy = offers.filter((o) => o.available).sort((a, b) => a.price - b.price)[0];
  const points = history.filter((h) => h.offer_id === mainOffer).map((h) => ({ t: new Date(h.observed_at), v: h.final_price ?? h.price }))
    .sort((a, b) => a.t.getTime() - b.t.getTime());
  // Un relevé n'est enregistré que quand le prix change : le dernier prix vaut jusqu'à aujourd'hui.
  if (points.length && Date.now() - points[points.length - 1].t.getTime() > 3600_000)
    points.push({ t: new Date(), v: points[points.length - 1].v });
  const mainLabel = offers.find((o) => o.id === mainOffer);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
        "@context": "https://schema.org", "@type": "Product", name: displayName(product.brand, product.name, " "),
        ...(product.brand ? { brand: { "@type": "Brand", name: product.brand } } : {}),
        ...(product.image_url ? { image: product.image_url } : {}),
        offers: ranked.slice(0, 1).map((r) => ({
          "@type": "Offer", price: r.final.toFixed(2), priceCurrency: "EUR", url: product.url,
          availability: r.available ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
          seller: { "@type": "Organization", name: product.site_name },
        }))[0],
      }) }} />
      <section className="summary">
        <div>
          <p><Link href={`/c/${actives[0]?.category ?? ""}`}>← {CATEGORY_BY_ID[actives[0]?.category ?? ""]?.label ?? "Catégories"}</Link></p>
          <div className="prodhead">
            {product.image_url && <img src={product.image_url} alt="" width={120} height={120} referrerPolicy="no-referrer" />}
            <div>
              <h1>{displayName(product.brand, product.name)}</h1>
              {product.rating != null && product.review_count ? <p>★ {num(product.rating, 1)} sur 5 · {product.review_count} avis sur le site du marchand</p> : null}
              <p><Link className="btn ghost small" href={`/alertes?product=${product.id}&cat=${actives[0]?.category ?? ""}`}>Créer une alerte prix</Link></p>
            </div>
          </div>
          {product.origin_country === country.code && (
            <p><span className="chip made" title={product.origin_evidence ? `« ${snippet(product.origin_evidence)} »` : undefined}>
              <span aria-hidden="true">{country.flag}</span> {country.madeIn}</span>
              {product.origin_evidence && <span className="note-small"> d'après la fiche : « {snippet(product.origin_evidence)} »</span>}</p>
          )}
          {bestBuy ? (
            <div className="buy">
              <GoButton big offerId={bestBuy.offer_id} code={bestBuy.applied?.code.code}
                label={`Voir sur ${product.site_name} · ${eur(bestBuy.final)}`} />
              {bestBuy.applied?.code.code && <span className="note-small">Code {bestBuy.applied.code.code} copié au clic</span>}
            </div>
          ) : fallbackBuy ? (
            <div className="buy">
              <GoButton big offerId={fallbackBuy.id} label={`Voir sur ${product.site_name} · ${eur(fallbackBuy.price)}`} />
            </div>
          ) : null}
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
                  {SOURCE_LABEL[a.source ?? ""] ?? a.source}{a.evidence ? ` : « ${snippet(a.evidence, 140)} »` : ""}{a.note ? `. ${a.note}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {product.review_topics && Object.keys(product.review_topics.topics).length > 0 && (
        <section className="panel">
          <h2>Ce qu'en disent les acheteurs</h2>
          <div className="topics">
            {Object.entries(product.review_topics.topics).sort((a, b) => b[1].mentions - a[1].mentions).map(([topic, t]) => {
              const judged = t.pos + t.neg;
              const pct = judged ? Math.round((t.pos / judged) * 100) : null;
              return (
                <div key={topic} className="topic">
                  <b>{topic}</b>
                  <span className="bar" aria-hidden="true">
                    <i style={{ width: `${judged ? (t.pos / t.mentions) * 100 : 0}%` }} />
                    <b style={{ width: `${judged ? (t.neg / t.mentions) * 100 : 0}%` }} />
                  </span>
                  <span className="note-small">{pct != null ? `${pct} % positifs` : "avis partagés"} · {t.mentions} avis</span>
                </div>
              );
            })}
          </div>
          <p className="note-small">D'après les {product.review_topics.reviews_read} avis publiés sur la fiche du marchand au dernier relevé
            (tous les avis du site ne sont pas toujours visibles sur sa page). Classement des thèmes automatique.</p>
        </section>
      )}

      {product.attributes?.preworkout && (
        <section className="panel">
          <h2>Actifs par portion</h2>
          <table className="t">
            <thead><tr><th>Actif</th><th className="r">Par portion</th><th className="r">Dose des études</th><th></th></tr></thead>
            <tbody>
              {Object.values(product.attributes.preworkout).map((a) => (
                <tr key={a.label}><td>{a.label}</td><td className="r">{num(a.dose, a.dose % 1 ? 1 : 0)} {a.unit}</td>
                  <td className="r">{num(a.ref, a.ref % 1 ? 1 : 0)} {a.unit}</td><td>{a.ok ? "atteinte" : "en dessous"}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="note-small">Doses de référence utilisées dans les études sur ces actifs, à titre de repère : ce n'est pas un conseil de dosage.</p>
        </section>
      )}

      <section className="panel two">
        <div>
          <h2>Composition</h2>
          {attributeLines(product.attributes).length > 0 && <ul className="facts">{attributeLines(product.attributes).map((l) => <li key={l}>{l}</li>)}</ul>}
          <p className="note-small"><b>Ingrédients</b> : {product.ingredients ?? "non lus sur la fiche"}</p>
        </div>
        <div>
          <h2>Valeurs nutritionnelles</h2>
          <NutritionTable n={product.nutrition} />
        </div>
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
                  <td className="r">{r?.value != null && cat ? `${num(r.value, 2)} ${modeDef(cat.id, "dose").unit}` : "–"}</td>
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
