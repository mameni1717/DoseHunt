import type { Metadata } from "next";
import { dataText } from "@/lib/datatext";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CodeVote, CopyCode, GoButton } from "@/components/client";
import { codeVoteText, copyCodeText, goButtonText } from "@/components/OfferCard";
import { activeLabel, categoryById, modeDef } from "@/lib/categories";
import { NutritionTable, attributeLines } from "@/components/ProductFacts";
import { effectiveConfidence, percentFor } from "@/lib/codes";
import { getProduct } from "@/lib/data";
import { countryFromPath, href, type Country } from "@/lib/country";
import { ago, displayName, formatDate, formatMoney, formatNumber, snippet } from "@/lib/format";
import { t, tp, type MessageKey } from "@/lib/i18n";
import { rich } from "@/lib/rich";
import { rerank, formatLabel } from "@/lib/rank";
import { alternates } from "@/lib/seo";
import { SITE_URL } from "@/lib/site";

// Fiche mise en cache 30 min (régénérée à la demande) ; vidée après chaque collecte par /api/revalidate.
export const revalidate = 1800;
// Aucune fiche générée à la construction : chacune l'est à sa première visite, puis servie depuis le cache.
export const dynamicParams = true;
export async function generateStaticParams() {
  return [];
}

type Params = Promise<{ country: string; id: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const p = await params;
  const country = countryFromPath(p.country);
  const id = Number(p.id);
  const d = country && Number.isFinite(id) ? await getProduct(country, id) : null;
  if (!country || !d) return {};
  const L = country.lang;
  const name = displayName(d.product.brand, d.product.name, " ");
  const cat = categoryById(country)[d.actives[0]?.category ?? ""];
  const title = t(L, "product.meta.title", { name });
  const description = t(L, "product.meta.description", {
    name, site: d.product.site_name, mode: cat ? `(${modeDef(country, cat.id, cat.defaultMode).label.toLowerCase()})` : "",
  });
  return {
    title, description,
    alternates: alternates(country, `/p/${id}`, false),        // fiche propre à un pays : pas de hreflang
    openGraph: { title, description, url: href(country, `/p/${id}`), locale: country.ogLocale, images: d.product.image_url ? [d.product.image_url] : undefined },
  };
}

/** Niveau de fiabilité d'un code (mêmes seuils que confidenceLabel de lib/codes). */
function confLevel(conf: number): "high" | "medium" | "low" {
  return conf >= 0.75 ? "high" : conf >= 0.55 ? "medium" : "low";
}

function History({ points, country }: { points: { t: Date; v: number }[]; country: Country }) {
  const L = country.lang;
  const date = (d: Date) => formatDate(d, country);
  const money = (v: number) => formatMoney(v, country);
  if (points.length < 2) {
    return <p className="note-small">{tp(L, "product.history.few", points.length, { detail: points[0] ? ` (${date(points[0].t)}, ${money(points[0].v)})` : "" })}</p>;
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
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
      aria-label={t(L, "product.history.aria", { from: date(points[0].t), to: date(points[points.length - 1].t), min: money(min.v) })}>
      <path d={d} fill="none" stroke="var(--blaze)" strokeWidth="2.5" />
      {points.map((p, i) => <circle key={i} cx={x(p.t.getTime())} cy={y(p.v)} r="3" fill="var(--blaze)" />)}
      <text x={P} y={14} fontSize="12" fill="var(--muted)">{money(hi / 1.03)}</text>
      <text x={P} y={H - 6} fontSize="12" fill="var(--muted)">{date(points[0].t)}</text>
      <text x={W - P} y={H - 6} fontSize="12" fill="var(--muted)" textAnchor="end">{date(points[points.length - 1].t)}</text>
      <text x={x(min.t.getTime())} y={y(min.v) + 16} fontSize="12" fill="var(--ink)" textAnchor="middle">{t(L, "product.history.min", { price: money(min.v) })}</text>
    </svg>
  );
}

export default async function ProductPage({ params }: { params: Params }) {
  const p = await params;
  const country = countryFromPath(p.country);
  if (!country) notFound();
  const L = country.lang;
  const id = Number(p.id);
  if (!Number.isFinite(id)) notFound();
  const d = await getProduct(country, id);               // null si le produit n'est pas vendu dans ce pays
  if (!d) notFound();
  const byId = categoryById(country);
  const money = (v: number) => formatMoney(v, country);
  const quote = (text: string) => t(L, "product.quote", { text });
  const goM = goButtonText(L), copyM = copyCodeText(L), voteM = codeVoteText(L);
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
  const firstCat = actives[0]?.category ?? "";
  const facts = attributeLines(country, product.attributes);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
        "@context": "https://schema.org", "@type": "Product", name: displayName(product.brand, product.name, " "),
        url: `${SITE_URL}${href(country, `/p/${product.id}`)}`,
        ...(product.brand ? { brand: { "@type": "Brand", name: product.brand } } : {}),
        ...(product.image_url ? { image: product.image_url } : {}),
        offers: ranked.slice(0, 1).map((r) => ({
          "@type": "Offer", price: r.final.toFixed(2), priceCurrency: country.currency, url: product.url,
          availability: r.available ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
          seller: { "@type": "Organization", name: product.site_name },
        }))[0],
      }) }} />
      <section className="summary">
        <div>
          <p><Link href={href(country, `/c/${firstCat}`)}>← {byId[firstCat]?.label ?? t(L, "product.back.fallback")}</Link></p>
          <div className="prodhead">
            {product.image_url && <img src={product.image_url} alt="" width={120} height={120} referrerPolicy="no-referrer" />}
            <div>
              <h1>{displayName(product.brand, product.name)}</h1>
              {product.rating != null && product.review_count
                ? <p>{tp(L, "product.rating", product.review_count, { rating: formatNumber(product.rating, country, 1) })}</p> : null}
              <p><Link className="btn ghost small" href={href(country, `/alertes?product=${product.id}&cat=${firstCat}`)}>{t(L, "product.alert")}</Link></p>
            </div>
          </div>
          {product.origin_country === country.code && (
            <p><span className="chip made" title={product.origin_evidence ? quote(snippet(product.origin_evidence)) : undefined}>
              <span aria-hidden="true">{country.flag}</span> {country.madeIn}</span>
              {product.origin_evidence && <span className="note-small"> {t(L, "product.origin.from", { text: snippet(product.origin_evidence) })}</span>}</p>
          )}
          {bestBuy ? (
            <div className="buy">
              <GoButton big offerId={bestBuy.offer_id} code={bestBuy.applied?.code.code} m={goM}
                label={t(L, "product.buy", { site: product.site_name, price: money(bestBuy.final) })} />
              {bestBuy.applied?.code.code && <span className="note-small">{t(L, "product.buy.code", { code: bestBuy.applied.code.code })}</span>}
            </div>
          ) : fallbackBuy ? (
            <div className="buy">
              <GoButton big offerId={fallbackBuy.id} m={goM} label={t(L, "product.buy", { site: product.site_name, price: money(fallbackBuy.price) })} />
            </div>
          ) : null}
          <p>{rich(L, "product.soldBy", { link: (c) => <a href={product.url} rel="nofollow noopener" target="_blank">{c}</a> },
            { site: product.site_name, ago: ago(product.last_seen, country) })}</p>
        </div>
      </section>

      <section className="panel">
        <h2>{t(L, "product.contents.title")}</h2>
        <table className="t">
          <thead><tr><th>{t(L, "product.contents.list")}</th><th>{t(L, "product.contents.real")}</th><th>{t(L, "product.contents.source")}</th></tr></thead>
          <tbody>
            {actives.map((a) => {
              const src = a.source ? (t(L, `product.source.${a.source}` as MessageKey) === `product.source.${a.source}` ? a.source : t(L, `product.source.${a.source}` as MessageKey)) : "";
              return (
                <tr key={a.category}>
                  <td><Link href={href(country, `/c/${a.category}`)}>{byId[a.category]?.label}</Link>{a.combined ? ` ${t(L, "product.contents.combined")}` : ""}</td>
                  <td>
                    {a.status === "review" ? t(L, "product.contents.review") : activeLabel(country, a.category, a.amount, a.unit, a.basis)}
                    {a.salt_label_mg ? ` ${t(L, "product.contents.label", { mg: formatNumber(a.salt_label_mg, country) })}` : ""}
                    {a.form ? ` · ${t(L, "product.contents.form", { form: a.form })}` : ""}
                  </td>
                  <td className="note-small">
                    {a.evidence ? t(L, "product.contents.evidence", { source: src, text: snippet(a.evidence, 140) }) : src}{a.note ? `. ${dataText(L, a.note)}` : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {product.review_topics && Object.keys(product.review_topics.topics).length > 0 && (
        <section className="panel">
          <h2>{t(L, "product.reviews.title")}</h2>
          <div className="topics">
            {Object.entries(product.review_topics.topics).sort((a, b) => b[1].mentions - a[1].mentions).map(([topic, s]) => {
              const judged = s.pos + s.neg;
              const pct = judged ? Math.round((s.pos / judged) * 100) : null;
              return (
                <div key={topic} className="topic">
                  <b>{dataText(L, topic)}</b>
                  <span className="bar" aria-hidden="true">
                    <i style={{ width: `${judged ? (s.pos / s.mentions) * 100 : 0}%` }} />
                    <b style={{ width: `${judged ? (s.neg / s.mentions) * 100 : 0}%` }} />
                  </span>
                  <span className="note-small">{pct != null ? t(L, "product.reviews.positive", { pct }) : t(L, "product.reviews.mixed")} · {tp(L, "product.reviews.count", s.mentions)}</span>
                </div>
              );
            })}
          </div>
          <p className="note-small">{tp(L, "product.reviews.note", product.review_topics.reviews_read)}</p>
        </section>
      )}

      {product.attributes?.preworkout && (
        <section className="panel">
          <h2>{t(L, "product.pre.title")}</h2>
          <table className="t">
            <thead><tr><th>{t(L, "product.pre.active")}</th><th className="r">{t(L, "product.pre.perServing")}</th><th className="r">{t(L, "product.pre.ref")}</th><th></th></tr></thead>
            <tbody>
              {Object.values(product.attributes.preworkout).map((a) => (
                <tr key={a.label}><td>{dataText(L, a.label)}</td><td className="r">{formatNumber(a.dose, country, a.dose % 1 ? 1 : 0)} {a.unit}</td>
                  <td className="r">{formatNumber(a.ref, country, a.ref % 1 ? 1 : 0)} {a.unit}</td><td>{a.ok ? t(L, "product.pre.ok") : t(L, "product.pre.low")}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="note-small">{t(L, "product.pre.note")}</p>
        </section>
      )}

      <section className="panel two">
        <div>
          <h2>{t(L, "product.composition")}</h2>
          {facts.length > 0 && <ul className="facts">{facts.map((l) => <li key={l}>{l}</li>)}</ul>}
          <p className="note-small">{rich(L, "product.ingredients", { b: (c) => <b>{c}</b> }, { text: product.ingredients ?? t(L, "product.ingredients.none") })}</p>
        </div>
        <div>
          <h2>{t(L, "product.nutrition")}</h2>
          <NutritionTable n={product.nutrition} country={country} />
        </div>
      </section>

      <section className="panel">
        <h2>{t(L, "product.offers.title")}</h2>
        <table className="t">
          <thead><tr><th>{t(L, "product.offers.format")}</th><th className="r">{t(L, "product.offers.shown")}</th><th className="r">{t(L, "product.offers.final")}</th>
            <th className="r">{t(L, "product.offers.compared")}</th><th>{t(L, "product.offers.seen")}</th><th></th></tr></thead>
          <tbody>
            {offers.map((o) => {
              const r = bestByOffer.get(o.id);
              const cat = r ? byId[r.category] : null;
              return (
                <tr key={o.id}>
                  <td>{formatLabel(o as never, country.locale) || o.variant_title}{o.flavour ? ` · ${o.flavour}` : ""}{!o.available ? ` · ${t(L, "product.offers.unavailable")}` : ""}</td>
                  <td className="r">{o.compare_at_price ? <s>{money(o.compare_at_price)}</s> : null} {money(o.price)}</td>
                  <td className="r">{r ? money(r.final) : "–"}{r?.applied ? ` (${r.applied.code.code})` : ""}</td>
                  <td className="r">{r?.value != null && cat ? `${formatNumber(r.value, country, 2)} ${modeDef(country, cat.id, "dose").unit}` : "–"}</td>
                  <td>{ago(o.collected_at, country)}</td>
                  <td>{o.available && <GoButton offerId={o.id} code={r?.applied?.code.code} m={goM} label={t(L, "product.offers.go")} />}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>{t(L, "product.history.title")}{mainLabel ? ` · ${formatLabel(mainLabel as never, country.locale) || mainLabel.variant_title}` : ""}</h2>
        <History points={points} country={country} />
      </section>

      <section className="panel">
        <h2>{t(L, "product.codes.title", { site: product.site_name })}</h2>
        {codes.length === 0 ? (
          <p className="note-small">{t(L, "product.codes.none")}</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
            {codes.map((c) => {
              const conf = effectiveConfidence(c);
              const level = t(L, `product.code.level.${confLevel(conf)}`);
              const pct = c.tiers?.length
                ? c.tiers.map((x) => `${t(L, "product.code.pct", { pct: x.pct })}${x.min ? ` ${t(L, "product.code.from", { min: x.min, cur: country.symbol })}` : ""}`).join(", ")
                : c.value != null ? t(L, "product.code.pct", { pct: c.value }) : "";
              return (
                <li key={c.id} style={{ display: "grid", gap: 4 }}>
                  <span className="chips" style={{ marginTop: 0 }}>
                    <span className="chip code">{c.code} {pct}</span> <CopyCode code={c.code} m={copyM} />
                    {c.first_order_only && <span className="chip first">{t(L, "product.code.first")}</span>}
                    <span className={`chip${conf < 0.5 ? " low" : ""}`}>{t(L, conf < 0.5 ? "product.code.notApplied" : "product.code.reliability", { level })}</span>
                    {c.ends_on && <span className="chip">{t(L, "product.code.until", { date: formatDate(String(c.ends_on), country) })}</span>}
                    {!c.stackable_with_sale && <span className="chip low">{t(L, "product.code.noStack")}</span>}
                  </span>
                  <span className="note-small">{c.last_confirmed ? t(L, "product.code.verified", { source: dataText(L, c.source), ago: ago(String(c.last_confirmed), country) }) : dataText(L, c.source)}
                    {percentFor(c, 50) == null ? ` · ${t(L, "product.code.minOrder")}` : ""}</span>
                  <CodeVote codeId={c.id} m={voteM} />
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}
