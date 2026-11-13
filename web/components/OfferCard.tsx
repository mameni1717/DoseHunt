import Link from "next/link";
import { activeLabel, categoryById, modeDef, type Mode } from "@/lib/categories";
import { href, type Country, type Lang } from "@/lib/country";
import { ago, displayName, formatDate, formatMoney, formatNumber, snippet, stripBrand } from "@/lib/format";
import { t, tp } from "@/lib/i18n";
import { formatLabel, type Ranked } from "@/lib/rank";
import {
  CodeVote, CompareToggle, GoButton, ProductImage,
  type ApplyFiltersText, type CodeVoteText, type CopyCodeText, type GoButtonText,
} from "./client";

// Textes des composants client, traduits côté serveur (les composants client n'importent pas lib/i18n).
export function goButtonText(L: Lang): GoButtonText {
  return { view: t(L, "offer.go.view"), copied: t(L, "offer.go.copied"), note: t(L, "offer.go.note") };
}
export function copyCodeText(L: Lang): CopyCodeText {
  return { aria: t(L, "offer.copy.aria"), copy: t(L, "offer.copy.copy"), copied: t(L, "offer.copy.copied") };
}
export function codeVoteText(L: Lang): CodeVoteText {
  return { question: t(L, "offer.vote.question"), yes: t(L, "offer.vote.yes"), no: t(L, "offer.vote.no"),
    thanks: t(L, "offer.vote.thanks"), error: t(L, "offer.vote.error") };
}
export function applyFiltersText(L: Lang): ApplyFiltersText {
  return { apply: t(L, "offer.apply.apply"), busy: t(L, "offer.apply.busy"),
    pendingOne: t(L, "offer.apply.pending.one"), pendingMany: t(L, "offer.apply.pending.other") };
}

/** Fiabilité d'un code dans la langue du pays (mêmes seuils que confidenceLabel de lib/codes). */
function confidenceText(L: Lang, conf: number): string {
  return t(L, conf >= 0.75 ? "offer.conf.high" : conf >= 0.55 ? "offer.conf.medium" : "offer.conf.low");
}

export function unitFor(country: Country, cat: string, mode: Mode, r: Ranked): string {
  if (mode === "unit" && r.unit_label && categoryById(country)[cat].group === "vitamins") return r.unit_label;
  return modeDef(country, cat, mode).unit;
}

function valueFor(r: Ranked, m: Mode): number | null {
  return m === "dose" ? r.doseNow : m === "kg" ? r.kgNow : r.unitNow;
}

export function OfferCard({ r, rank, mode, best, country }: { r: Ranked; rank: number; mode: Mode; best: boolean; country: Country }) {
  const L = country.lang;
  const a = r.applied;
  const cat = categoryById(country)[r.category];
  const original = r.compare_at_price ?? r.price;           // avant promo du site et avant code
  const ratio = r.final > 0 ? original / r.final : 1;
  const discounted = original > r.final + 0.005;
  const modes = (Object.keys(cat.modes) as Mode[]);
  const num = (v: number, d: number) => formatNumber(v, country, d);
  const money = (v: number) => formatMoney(v, country);
  const pct = a?.pct != null ? t(L, "offer.code.pct", { n: a.pct }) : "";

  const tags: React.ReactNode[] = [];
  if (r.subcategory && cat.subs?.[r.subcategory]) tags.push(<span key="sub" className="chip type">{cat.subs[r.subcategory]}</span>);
  if (r.origin_country === country.code)
    tags.push(<span key="made" className="chip made" title={r.origin_evidence ? t(L, "offer.made.evidence", { text: snippet(r.origin_evidence) }) : undefined}>
      <span aria-hidden="true">{country.flag}</span> {country.madeIn}</span>);
  tags.push(r.available
    ? <span key="stock" className="chip instock">{t(L, "offer.inStock")}</span>
    : <span key="stock" className="chip out">{t(L, "offer.outOfStock")}</span>);
  if (a) tags.push(<span key="code" className="chip code">{t(L, "offer.code.chip", { code: a.code.code, pct })}</span>);
  if (a?.code.first_order_only) tags.push(<span key="first" className="chip first">{t(L, "offer.firstOrder")}</span>);
  if (a && a.confidence < 0.75) tags.push(<span key="conf" className="chip low">{t(L, "offer.code.lowConf", { level: confidenceText(L, a.confidence) })}</span>);
  if (r.combined) tags.push(<span key="combo" className="chip trap" title={t(L, "offer.combined.title")}>{t(L, "offer.combined")}</span>);
  if (r.source === "assumed" || (r.confidence ?? 1) < 0.8)
    tags.push(<span key="assume" className="chip low" title={t(L, "offer.assumed.title")}>{t(L, "offer.assumed")}</span>);

  const facts: string[] = [];
  if (r.amount != null) {
    // Sur la carte, le nom de l'actif est déjà dans le libellé du taux : « 15 mg par unité » plutôt que « 15 mg de zinc par unité ».
    const value = r.basis === "per_serving" || r.basis === "per_100g"
      ? activeLabel(country, r.category, r.amount, r.unit, r.basis)
      : t(L, "cat.active.perUnitShort", { n: r.amount.toLocaleString(country.locale, { maximumFractionDigits: 1 }), unit: r.unit ?? "" });
    facts.push(t(L, "offer.fact.active", { share: cat.activeShare ?? t(L, "offer.fact.activeFallback"), value }));
  }
  facts.push(formatLabel(r, country.locale) + (r.variants > 1 ? ` · ${t(L, "offer.fact.variants", { n: r.variants })}` : r.flavour ? ` · ${r.flavour}` : ""));
  facts.push(t(L, "offer.fact.site", { site: r.site_name }));

  // Historique : bon moment pour acheter ?
  const since = r.hist_since ? new Date(r.hist_since) : null;
  const sinceLabel = since
    ? (Date.now() - since.getTime() > 85 * 86400_000 ? t(L, "offer.hist.90d") : t(L, "offer.hist.since", { date: formatDate(since, country) }))
    : "";
  const atLow = r.hist_min != null && (r.hist_n ?? 0) > 1 && r.final <= r.hist_min + 0.01;
  const belowUsual = r.hist_avg30 != null && (r.hist_n ?? 0) > 1 && r.final < r.hist_avg30 * 0.95
    ? Math.round((1 - r.final / r.hist_avg30) * 100) : 0;
  if (atLow) tags.push(<span key="low" className="chip good">{t(L, "offer.hist.atLow", { since: sinceLabel })}</span>);
  else if (belowUsual >= 5) tags.push(<span key="usual" className="chip good">{t(L, "offer.hist.belowUsual", { n: belowUsual })}</span>);

  // Livraison offerte
  let ship = "";
  if (r.free_code) ship = t(L, "offer.ship.code", { code: r.free_code });
  else if (r.free_from === 0) ship = t(L, "offer.ship.free");
  else if (r.free_from != null)
    ship = t(L, r.final >= r.free_from ? "offer.ship.reached" : "offer.ship.from", { amount: money(r.free_from) });

  // Pré-workout : actifs de la portion comparés aux doses des études
  const pre = r.category === "preworkout" ? Object.values(r.attributes?.preworkout ?? {}) : [];

  const unit = unitFor(country, r.category, mode, r);
  const content = (r.calc ?? []).find((l) => l.startsWith("Contenu"));
  const calc = [
    t(L, "offer.calc.price", { price: money(r.price) }) + (r.compare_at_price ? t(L, "offer.calc.was", { price: money(r.compare_at_price) }) : ""),
    a ? t(L, "offer.calc.code", { code: a.code.code, pct, final: money(r.final) }) : t(L, "offer.calc.noCode", { final: money(r.final) }),
    ...(content ? [content] : []),
    t(L, "offer.calc.value", { label: modeDef(country, r.category, mode).label, value: r.value != null ? num(r.value, 2) : "–", unit }),
  ];
  const sources: string[] = [];
  if (r.evidence) sources.push(t(L, "offer.src.evidence", { text: snippet(r.evidence, 140) }));
  if (r.note) sources.push(`${r.note[0].toUpperCase()}${r.note.slice(1)}.`);
  if (a) sources.push(t(L, "offer.src.code", {
    source: a.code.source ?? t(L, "offer.src.noSource"),
    checked: a.code.last_confirmed ? t(L, "offer.src.checked", { ago: ago(String(a.code.last_confirmed), country) }) : "",
  }));
  sources.push(t(L, "offer.src.collected", { ago: ago(r.collected_at, country) }));

  return (
    <li id={`r${rank}`} className={`offer${best ? " best" : ""}${r.available ? "" : " soldout"}`}>
      <div className="rank">{rank}</div>
      <div className="pic">
        <ProductImage src={r.image_url} letter={cat.short.slice(0, 1)} />
      </div>
      <div className="prod">
        {r.brand && <div className="brandline">{r.brand}</div>}
        <h2><Link href={href(country, `/p/${r.product_id}`)}>{stripBrand(r.brand, r.name)}</Link></h2>
        <div className="meta">{facts.join(" · ")}
          {r.rating != null && r.review_count ? <> · <span title={tp(L, "offer.reviews.title", r.review_count)}>{tp(L, "offer.reviews", r.review_count, { rating: num(r.rating, 1) })}</span></> : null}
        </div>
        {pre.length > 0 && (
          <div className="pre" title={t(L, "offer.pre.title")}>
            {pre.map((a) => (
              <span key={a.label} className={a.ok ? "ok" : "low"}>
                {a.ok ? "✓" : "↓"} {a.label} {num(a.dose, a.dose % 1 ? 1 : 0)} {a.unit}<small> / {num(a.ref, a.ref % 1 ? 1 : 0)} {a.unit}</small>
              </span>
            ))}
          </div>
        )}
        <div className="chips">{tags}</div>
        <div className="subline">
          {ship && <span>🚚 {ship}</span>}
          {r.hist_min != null && (r.hist_n ?? 0) > 1 && !atLow && <span>{t(L, "offer.hist.min", { since: sinceLabel, price: money(r.hist_min) })}</span>}
        </div>
      </div>
      <div className="price">
        <div className="unit">
          {r.variants > 1 && <span className="from">{t(L, "offer.from")}</span>}
          {r.value != null ? num(r.value, 2) : "–"}<small>{unit}</small>
          {discounted && r.value != null && <span className="before"><s>{num(r.value * ratio, 2)}</s> {t(L, "offer.beforePromo")}</span>}
        </div>
        <table className="pricegrid">
          <tbody>
            {modes.filter((m) => m !== mode).map((m) => {
              const v = valueFor(r, m);
              return v == null ? null : (
                <tr key={m}><th>{modeDef(country, r.category, m).short}</th>
                  <td><b>{num(v, 2)} {country.symbol}</b>{discounted && <s>{num(v * ratio, 2)} {country.symbol}</s>}</td></tr>
              );
            })}
            <tr><th>{t(L, "offer.productPrice")}</th><td><b>{money(r.final)}</b>{discounted && <s>{money(original)}</s>}</td></tr>
          </tbody>
        </table>
        <div className="actions">
          <GoButton offerId={r.offer_id} code={a?.code.code} m={goButtonText(L)} />
          <Link className="btn ghost small" href={href(country, `/alertes?product=${r.product_id}&cat=${r.category}`)}>{t(L, "offer.alert")}</Link>
          <CompareToggle id={r.product_id} cat={r.category} label={displayName(r.brand, r.name, " ")} country={country.code}
            m={{ add: t(L, "offer.compare.add"), added: t(L, "offer.compare.added") }} />
        </div>
      </div>
      <details>
        <summary>{t(L, "offer.calc.show")}</summary>
        <div className="calc">{calc.join("\n")}</div>
        <p className="note-small">{sources.join(" ")}</p>
        {a && <CodeVote codeId={a.code.id} m={codeVoteText(L)} />}
      </details>
    </li>
  );
}
