import Link from "next/link";
import { CATEGORY_BY_ID, activeLabel, modeDef, type Mode } from "@/lib/categories";
import { confidenceLabel } from "@/lib/codes";
import { ago, dateFr, displayName, eur, num, snippet, stripBrand } from "@/lib/format";
import { formatLabel, type Ranked } from "@/lib/rank";
import { CodeVote, CompareToggle, GoButton, ProductImage } from "./client";
import { currentCountry } from "@/lib/country";

export function unitFor(cat: string, mode: Mode, r: Ranked): string {
  if (mode === "unit" && r.unit_label && CATEGORY_BY_ID[cat].group === "vitamins") return r.unit_label;
  return modeDef(cat, mode).unit;
}

function valueFor(r: Ranked, m: Mode): number | null {
  return m === "dose" ? r.doseNow : m === "kg" ? r.kgNow : r.unitNow;
}

export function OfferCard({ r, rank, mode, best }: { r: Ranked; rank: number; mode: Mode; best: boolean }) {
  const a = r.applied;
  const cat = CATEGORY_BY_ID[r.category];
  const country = currentCountry();
  const original = r.compare_at_price ?? r.price;           // avant promo du site et avant code
  const ratio = r.final > 0 ? original / r.final : 1;
  const discounted = original > r.final + 0.005;
  const modes = (Object.keys(cat.modes) as Mode[]);

  const tags: React.ReactNode[] = [];
  if (r.subcategory && cat.subs?.[r.subcategory]) tags.push(<span key="sub" className="chip type">{cat.subs[r.subcategory]}</span>);
  if (r.origin_country === country.code)
    tags.push(<span key="made" className="chip made" title={r.origin_evidence ? `D'après la fiche : « ${snippet(r.origin_evidence)} »` : undefined}>
      <span aria-hidden="true">{country.flag}</span> {country.madeIn}</span>);
  tags.push(r.available
    ? <span key="stock" className="chip instock">En stock</span>
    : <span key="stock" className="chip out">Rupture de stock</span>);
  if (a) tags.push(<span key="code" className="chip code">Code {a.code.code}{a.pct != null ? ` −${a.pct} %` : ""}</span>);
  if (a?.code.first_order_only) tags.push(<span key="first" className="chip first">1re commande</span>);
  if (a && a.confidence < 0.75) tags.push(<span key="conf" className="chip low">Code : fiabilité {confidenceLabel(a.confidence)}</span>);
  if (r.combined) tags.push(<span key="combo" className="chip trap" title="Le prix entier est compté pour cet actif">Produit combiné</span>);
  if (r.source === "assumed" || (r.confidence ?? 1) < 0.8)
    tags.push(<span key="assume" className="chip low" title="Teneur calculée ou supposée, voir le calcul">Teneur estimée</span>);

  const facts: string[] = [];
  if (r.amount != null) facts.push(`${cat.activeShare ?? "Teneur"} : ${activeLabel(r.category, r.amount, r.unit, r.basis).replace(/ de .* par unité$/, " par unité")}`);
  facts.push(formatLabel(r) + (r.variants > 1 ? ` · ${r.variants} arômes ou formats` : r.flavour ? ` · ${r.flavour}` : ""));
  facts.push(`chez ${r.site_name}`);

  // Historique : bon moment pour acheter ?
  const since = r.hist_since ? new Date(r.hist_since) : null;
  const sinceLabel = since ? (Date.now() - since.getTime() > 85 * 86400_000 ? "sur 90 jours" : `depuis le ${dateFr(since)}`) : "";
  const atLow = r.hist_min != null && (r.hist_n ?? 0) > 1 && r.final <= r.hist_min + 0.01;
  const belowUsual = r.hist_avg30 != null && (r.hist_n ?? 0) > 1 && r.final < r.hist_avg30 * 0.95
    ? Math.round((1 - r.final / r.hist_avg30) * 100) : 0;
  if (atLow) tags.push(<span key="low" className="chip good">Au plus bas {sinceLabel}</span>);
  else if (belowUsual >= 5) tags.push(<span key="usual" className="chip good">−{belowUsual} % sous le prix habituel</span>);

  // Livraison offerte
  let ship = "";
  if (r.free_code) ship = `Livraison offerte avec le code ${r.free_code}`;
  else if (r.free_from === 0) ship = "Livraison offerte";
  else if (r.free_from != null) ship = r.final >= r.free_from ? `Livraison offerte (dès ${eur(r.free_from)})` : `Livraison offerte dès ${eur(r.free_from)} d'achat`;

  // Pré-workout : actifs de la portion comparés aux doses des études
  const pre = r.category === "preworkout" ? Object.values(r.attributes?.preworkout ?? {}) : [];

  const content = (r.calc ?? []).find((l) => l.startsWith("Contenu"));
  const calc = [
    `Prix affiché : ${eur(r.price)}${r.compare_at_price ? ` (au lieu de ${eur(r.compare_at_price)})` : ""}`,
    a ? `Code ${a.code.code}${a.pct != null ? ` −${a.pct} %` : ""} → ${eur(r.final)}` : `Sans code → ${eur(r.final)}`,
    ...(content ? [content] : []),
    `${modeDef(r.category, mode).label} : ${r.value != null ? num(r.value, 2) : "–"} ${unitFor(r.category, mode, r)}`,
  ];
  const sources: string[] = [];
  if (r.evidence) sources.push(`Teneur lue sur la fiche : « ${snippet(r.evidence, 140)} ».`);
  if (r.note) sources.push(`${r.note[0].toUpperCase()}${r.note.slice(1)}.`);
  if (a) sources.push(`Code : ${a.code.source ?? "source non précisée"}${a.code.last_confirmed ? `, vérifié ${ago(String(a.code.last_confirmed))}` : ""}.`);
  sources.push(`Prix relevé ${ago(r.collected_at)}.`);

  return (
    <li id={`r${rank}`} className={`offer${best ? " best" : ""}${r.available ? "" : " soldout"}`}>
      <div className="rank">{rank}</div>
      <div className="pic">
        <ProductImage src={r.image_url} letter={cat.short.slice(0, 1)} />
      </div>
      <div className="prod">
        {r.brand && <div className="brandline">{r.brand}</div>}
        <h2><Link href={`/p/${r.product_id}`}>{stripBrand(r.brand, r.name)}</Link></h2>
        <div className="meta">{facts.join(" · ")}
          {r.rating != null && r.review_count ? <> · <span title={`${r.review_count} avis sur le site du marchand`}>★ {num(r.rating, 1)} ({r.review_count} avis)</span></> : null}
        </div>
        {pre.length > 0 && (
          <div className="pre" title="Dose de la portion comparée à la dose utilisée dans les études">
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
          {r.hist_min != null && (r.hist_n ?? 0) > 1 && !atLow && <span>Plus bas {sinceLabel} : {eur(r.hist_min)}</span>}
        </div>
      </div>
      <div className="price">
        <div className="unit">
          {r.variants > 1 && <span className="from">À partir de</span>}
          {r.value != null ? num(r.value, 2) : "–"}<small>{unitFor(r.category, mode, r)}</small>
          {discounted && r.value != null && <span className="before"><s>{num(r.value * ratio, 2)}</s> avant promo</span>}
        </div>
        <table className="pricegrid">
          <tbody>
            {modes.filter((m) => m !== mode).map((m) => {
              const v = valueFor(r, m);
              return v == null ? null : (
                <tr key={m}><th>{modeDef(r.category, m).short}</th>
                  <td><b>{num(v, 2)} €</b>{discounted && <s>{num(v * ratio, 2)} €</s>}</td></tr>
              );
            })}
            <tr><th>Prix du produit</th><td><b>{eur(r.final)}</b>{discounted && <s>{eur(original)}</s>}</td></tr>
          </tbody>
        </table>
        <div className="actions">
          <GoButton offerId={r.offer_id} code={a?.code.code} />
          <Link className="btn ghost small" href={`/alertes?product=${r.product_id}&cat=${r.category}`}>Alerte prix</Link>
          <CompareToggle id={r.product_id} cat={r.category} label={displayName(r.brand, r.name, " ")} />
        </div>
      </div>
      <details>
        <summary>Voir le calcul</summary>
        <div className="calc">{calc.join("\n")}</div>
        <p className="note-small">{sources.join(" ")}</p>
        {a && <CodeVote codeId={a.code.id} />}
      </details>
    </li>
  );
}
