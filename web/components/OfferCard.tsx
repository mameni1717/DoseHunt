import Link from "next/link";
import { CATEGORY_BY_ID, activeLabel, type Mode } from "@/lib/categories";
import { confidenceLabel } from "@/lib/codes";
import { ago, displayName, eur, num } from "@/lib/format";
import { formatLabel, type Ranked } from "@/lib/rank";
import { CodeVote, GoButton } from "./client";
import { currentCountry } from "@/lib/country";

export function unitFor(cat: string, mode: Mode, r: Ranked): string {
  const c = CATEGORY_BY_ID[cat];
  if (mode === "unit" && r.unit_label) return r.unit_label;
  return c.modes[mode].unit;
}

export function OfferCard({ r, rank, mode, best }: { r: Ranked; rank: number; mode: Mode; best: boolean }) {
  const a = r.applied;
  const country = currentCountry();
  const chips: React.ReactNode[] = [];
  if (r.origin_country === country.code)
    chips.push(<span key="made" className="chip made" title={r.origin_evidence ? `« ${r.origin_evidence} »` : undefined}>
      <span aria-hidden="true">{country.flag}</span> {country.madeIn}</span>);
  if (a) chips.push(<span key="code" className="chip code">{a.code.code}{a.pct != null ? ` -${a.pct} %` : ""}</span>);
  if (a?.code.first_order_only) chips.push(<span key="first" className="chip first">1re commande uniquement</span>);
  if (a && a.confidence < 0.75) chips.push(<span key="conf" className="chip low">Fiabilité {confidenceLabel(a.confidence)}</span>);
  if (r.variants > 1) chips.push(<span key="tastes" className="chip">{r.variants} arômes ou formats · le moins cher affiché</span>);
  if (r.compare_at_price) chips.push(<span key="sale" className="chip auto">Promo du site incluse</span>);
  if (r.combined) chips.push(<span key="combo" className="chip trap">Produit combiné</span>);
  if (r.salt_label_mg && r.amount != null)
    chips.push(<span key="salt" className="chip trap">Affiché : {num(r.salt_label_mg)} mg · réel : {num(r.amount, r.amount % 1 ? 1 : 0)} mg</span>);
  if (r.source === "assumed" || (r.confidence ?? 1) < 0.8)
    chips.push(<span key="assume" className="chip low">Teneur supposée</span>);

  const content = (r.calc ?? []).find((l) => l.startsWith("Contenu"));
  const cat = CATEGORY_BY_ID[r.category];
  const calc = [
    `Prix affiché : ${eur(r.price)}${r.compare_at_price ? ` (au lieu de ${eur(r.compare_at_price)})` : ""}`,
    a ? `Code ${a.code.code}${a.pct != null ? ` -${a.pct} %` : ""} → ${eur(r.final)}` : `Code : aucun → ${eur(r.final)}`,
    ...(content ? [content] : []),
    `${cat.modes[mode].label} : ${r.value != null ? num(r.value, 2) : "–"} ${unitFor(r.category, mode, r)}`,
  ];
  const sources: string[] = [];
  if (r.evidence) sources.push(`Teneur lue sur la fiche : « ${r.evidence.slice(0, 160)} ».`);
  if (r.note) sources.push(`Note : ${r.note}.`);
  if (r.origin_country === country.code && r.origin_evidence) sources.push(`Origine lue sur la fiche : « ${r.origin_evidence} ».`);
  if (a) sources.push(`Code : ${a.code.source ?? "source non précisée"}${a.code.last_confirmed ? `, vérifié ${ago(String(a.code.last_confirmed))}` : ""}.`);

  return (
    <li className={`offer${best ? " best" : ""}`}>
      <div className="rank">{rank}</div>
      <div className="prod">
        <h2><Link href={`/p/${r.product_id}`}>{displayName(r.brand, r.name)}</Link></h2>
        <div className="meta">
          {formatLabel(r)}{r.flavour ? ` · ${r.flavour}` : ""} · {activeLabel(r.category, r.amount, r.unit, r.basis)}
          {r.form ? ` · ${r.form}` : ""} · {r.site_name} · relevé {ago(r.collected_at)}
        </div>
        <div className="chips">{chips}</div>
      </div>
      <div className="price">
        <div className="unit">
          {r.variants > 1 && <span className="from">À partir de</span>}
          {r.value != null ? num(r.value, 2) : "–"}
          <small>{unitFor(r.category, mode, r)}</small>
        </div>
        <div className="sticker">
          {r.final < r.price && <s>{eur(r.price)}</s>}
          {r.compare_at_price && r.final >= r.price && <s>{eur(r.compare_at_price)}</s>}
          <b>{eur(r.final)}</b> le contenant
        </div>
        <GoButton offerId={r.offer_id} code={a?.code.code} />
      </div>
      <details>
        <summary>Voir le calcul</summary>
        <div className="calc">{calc.join("\n")}</div>
        {sources.length > 0 && <p className="note-small">{sources.join(" ")}</p>}
        {a && <CodeVote codeId={a.code.id} />}
      </details>
    </li>
  );
}
