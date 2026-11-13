"use client";

import { useEffect, useState } from "react";
import type { QtyKind } from "@/lib/optimize";
import { GoButton, type GoButtonText } from "@/components/client";

export interface CatChoice { id: string; label: string; subs: Record<string, string>; kind: QtyKind; kindLabel: string; defaultQty: number }

interface Item { cat: string; sub: string; qty: number; pin: string | null; pinLabel: string | null; minActive?: number | null }

interface ResLine {
  cat: string; copies: number; covered: number; cost: number; offer_id: number; product_id: number;
  brand: string | null; name: string; flavour: string | null; grams: number | null; units: number | null;
  unit_word: string | null; variant_title: string | null; price: number; compare_at_price: number | null;
}
interface ResBasket {
  site_id: string; site_name: string; lines: ResLine[]; subtotal: number; total: number;
  code: { code: string; discount: number; pct: number | null; firstOrder: boolean } | null;
  freeFrom: number | null; freeShipping: boolean; missingForFree: number | null; freeCode: string | null;
}

/** Textes de l'Optimiseur, déjà traduits par la page (messages/<lang>/optimizer.ts, sans le préfixe « optimizer. »). */
export type OptimizerMessages = Record<string, string>;

// Liste enregistrée dans le navigateur, une par pays. Ancienne clé sans pays : relue en repli pour la France.
const STORE_PREFIX = "dosehunt.optimiser.v1";
const LEGACY_STORE = "dosehunt.optimiser.v1";

function load(iso: string): { items: Item[]; firstOrder: boolean; useCodes: boolean } | null {
  try {
    const raw = localStorage.getItem(`${STORE_PREFIX}.${iso}`) ?? (iso === "FR" ? localStorage.getItem(LEGACY_STORE) : null);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function fill(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

export function Optimizer({ cats, shippingEstimate, m, go, country, locale, currency, productPrefix }: {
  cats: CatChoice[]; shippingEstimate: number; m: OptimizerMessages; go: GoButtonText;
  country: string; locale: string; currency: string; productPrefix: string;
}) {
  const byId = Object.fromEntries(cats.map((c) => [c.id, c]));
  const store = `${STORE_PREFIX}.${country}`;
  const plural = new Intl.PluralRules(locale);
  const money = (n: number | null | undefined) =>
    n == null ? "–" : n.toLocaleString(locale, { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const qtyText = (kind: QtyKind, n: number): string => {
    if (kind === "grams") return n >= 1000 ? fill(m["qty.kg"], { n: (n / 1000).toLocaleString(locale, { maximumFractionDigits: 2 }) }) : fill(m["qty.g"], { n });
    return fill(m[kind === "portions" ? "qty.portions" : "qty.units"], { n });
  };
  // Format d'une ligne (« 1 kg », « 12 barres ») : même règle que formatLabel (lib/rank), dans le format du pays.
  const formatLabel = (r: Pick<ResLine, "grams" | "units" | "unit_word" | "variant_title">): string => {
    if (r.units && r.unit_word && r.unit_word !== "dose") return `${r.units} ${r.unit_word}${r.units > 1 ? "s" : ""}`;
    if (r.grams) return r.grams >= 1000 ? `${(r.grams / 1000).toLocaleString(locale, { maximumFractionDigits: 2 })} kg` : `${r.grams} g`;
    return r.variant_title ?? "";
  };
  const [items, setItems] = useState<Item[]>([{ cat: "whey", sub: "classique", qty: byId.whey?.defaultQty ?? 1000, pin: null, pinLabel: null, minActive: 70 }]);
  const [firstOrder, setFirstOrder] = useState(false);
  const [useCodes, setUseCodes] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [result, setResult] = useState<ResBasket[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<{ idx: number; q: string; hits: { key: string; label: string; sites: number }[] } | null>(null);

  useEffect(() => {
    const s = load(country);
    if (s?.items?.length) { setItems(s.items.filter((i) => byId[i.cat])); setFirstOrder(!!s.firstOrder); setUseCodes(s.useCodes !== false); }
    setLoaded(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!loaded) return;
    try { localStorage.setItem(store, JSON.stringify({ items, firstOrder, useCodes })); } catch { /* navigation privée */ }
  }, [items, firstOrder, useCodes, loaded, store]);

  const update = (i: number, patch: Partial<Item>) => { setItems((xs) => xs.map((x, k) => (k === i ? { ...x, ...patch } : x))); setResult(null); };
  const add = () => {
    const free = cats.find((c) => !items.some((i) => i.cat === c.id)) ?? cats[0];
    setItems((xs) => [...xs, { cat: free.id, sub: free.id === "whey" ? "classique" : "", qty: free.defaultQty, pin: null, pinLabel: null, minActive: free.id === "whey" ? 70 : null }]);
    setResult(null);
  };
  const remove = (i: number) => { setItems((xs) => xs.filter((_, k) => k !== i)); setResult(null); };

  async function find(idx: number, q: string) {
    setSearch({ idx, q, hits: search?.idx === idx ? search.hits : [] });
    if (q.trim().length < 2) return;
    try {
      const r = await fetch(`/api/optimiser?country=${encodeURIComponent(country)}&cat=${encodeURIComponent(items[idx].cat)}&q=${encodeURIComponent(q)}`);
      const hits = await r.json();
      setSearch((s) => (s && s.idx === idx && s.q === q ? { ...s, hits } : s));
    } catch { /* recherche indisponible */ }
  }

  async function run() {
    setBusy(true); setError(null);
    try {
      const r = await fetch("/api/optimiser", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ country, needs: items.map((i) => ({ cat: i.cat, sub: i.sub || null, qty: i.qty, pin: i.pin, minActive: i.cat === "whey" && !i.pin ? i.minActive ?? null : null })), firstOrder, useCodes }),
      });
      if (!r.ok) throw new Error(String(r.status));
      setResult((await r.json()).baskets);
    } catch {
      setError(m["error"]);
    } finally { setBusy(false); }
  }

  return (
    <>
      <div className="controls opt-list">
        {items.map((it, i) => {
          const c = byId[it.cat];
          return (
            <div key={i} className="opt-item">
              <div className="row">
                <select className="filter" aria-label={m["cat"]} value={it.cat}
                  onChange={(e) => update(i, { cat: e.target.value, sub: e.target.value === "whey" ? "classique" : "", qty: byId[e.target.value].defaultQty, pin: null, pinLabel: null, minActive: e.target.value === "whey" ? 70 : null })}>
                  {cats.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </select>
                {Object.keys(c.subs).length > 0 && !it.pin && (
                  <select className="filter" aria-label={m["type"]} value={it.sub} onChange={(e) => update(i, { sub: e.target.value })}>
                    <option value="">{m["allTypes"]}</option>
                    {Object.entries(c.subs).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                )}
                {it.cat === "whey" && !it.pin && (
                  <select className="filter" aria-label={m["minActive"]} value={it.minActive ?? ""}
                    onChange={(e) => update(i, { minActive: e.target.value ? Number(e.target.value) : null })}>
                    <option value="">{m["minActive.any"]}</option>
                    {[60, 70, 75, 80, 85, 90].map((v) => <option key={v} value={v}>{fill(m["minActive.value"], { v })}</option>)}
                  </select>
                )}
                <label className="opt-qty">
                  <input type="number" min={1} step={c.kind === "grams" ? 100 : 1} value={it.qty}
                    onChange={(e) => update(i, { qty: Math.max(0, Number(e.target.value)) })} />
                  <span>{c.kindLabel}</span>
                </label>
                <button type="button" className="btn ghost small" onClick={() => remove(i)} aria-label={m["remove.label"]}
                  disabled={items.length === 1}>{m["remove"]}</button>
              </div>
              <div className="row opt-pin">
                {it.pin ? (
                  <span className="chip">{fill(m["pinned"], { label: it.pinLabel ?? "" })}
                    <button type="button" className="linkish" onClick={() => update(i, { pin: null, pinLabel: null })}>{m["unpin"]}</button>
                  </span>
                ) : (
                  <>
                    <input className="filter grow" placeholder={m["search"]}
                      value={search?.idx === i ? search.q : ""} onChange={(e) => find(i, e.target.value)} />
                    {search?.idx === i && search.hits.length > 0 && (
                      <ul className="opt-hits">
                        {search.hits.map((h) => (
                          <li key={h.key}>
                            <button type="button" onClick={() => { update(i, { pin: h.key, pinLabel: h.label, sub: "" }); setSearch(null); }}>
                              {h.label} <small>· {fill(m[plural.select(h.sites) === "one" ? "sites.one" : "sites.other"], { n: h.sites })}</small>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
        <div className="row">
          <button type="button" className="btn ghost" onClick={add}>{m["add"]}</button>
          <label className="check"><input type="checkbox" checked={firstOrder} onChange={(e) => { setFirstOrder(e.target.checked); setResult(null); }} /> {m["firstOrder"]}</label>
          <label className="check"><input type="checkbox" checked={!useCodes} onChange={(e) => { setUseCodes(!e.target.checked); setResult(null); }} /> {m["noCodes"]}</label>
          <button type="button" className="btn blaze" onClick={run} disabled={busy || !items.length}>{busy ? m["busy"] : m["run"]}</button>
        </div>
      </div>

      {error && <p className="empty">{error}</p>}
      {result && result.length === 0 && (
        <p className="empty">{m["none"]}</p>
      )}
      {result && result.length > 0 && (
        <ol className="opt-results">
          {result.map((b, k) => (
            <li key={b.site_id} className={`card opt-basket${k === 0 ? " best" : ""}`}>
              <header className="opt-head">
                <span className="rank">{k + 1}</span>
                <h2>{b.site_name}</h2>
                <div className="opt-total">
                  <strong>{money(b.total)}</strong>
                  {b.total < b.subtotal && <s>{money(b.subtotal)}</s>}
                </div>
              </header>
              <div className="subline">
                {b.code && <span className="chip code">{fill(m["code"], { code: b.code.code, amount: money(b.code.discount) })}{b.code.pct ? fill(m["code.pct"], { pct: b.code.pct }) : ""}{b.code.firstOrder ? m["code.firstOrder"] : ""}</span>}
                {b.freeShipping && <span className="chip good">{m["ship.free"]}</span>}
                {!b.freeShipping && b.freeCode && <span className="chip good">{fill(m["ship.freeCode"], { code: b.freeCode })}</span>}
                {!b.freeShipping && !b.freeCode && b.missingForFree != null && <span>{fill(m["ship.missing"], { missing: money(b.missingForFree), from: money(b.freeFrom) })}</span>}
                {!b.freeShipping && !b.freeCode && b.missingForFree == null && <span>{m["ship.unknown"]}</span>}
              </div>
              <table className="opt-lines">
                <tbody>
                  {b.lines.map((l) => (
                    <tr key={`${l.cat}-${l.offer_id}`}>
                      <td><a href={`${productPrefix}/${l.product_id}`}>{l.brand ? `${l.brand} · ` : ""}{l.name}</a>
                        <small> · {formatLabel(l)}{l.flavour ? ` · ${l.flavour}` : ""}</small></td>
                      <td className="num opt-unit">{l.copies > 1 ? `${l.copies} × ${money(l.price)}` : money(l.price)}</td>
                      <td className="num">{l.copies > 1 && <small className="opt-copies">{l.copies} × </small>}{money(l.cost)}</td>
                      <td><GoButton offerId={l.offer_id} code={b.code?.code} label={m["go"]} m={go} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="opt-note">{fill(m["covers"], { list: [...new Set(b.lines.map((l) => l.cat))].map((cat) =>
                `${byId[cat]?.label ?? cat} ${qtyText(byId[cat]?.kind ?? "grams", b.lines.filter((l) => l.cat === cat).reduce((s, l) => s + l.covered, 0))}`).join(" · ") })}</p>
            </li>
          ))}
        </ol>
      )}
      {result && result.length > 0 && (
        <p className="opt-note">{fill(m["note"], { estimate: money(shippingEstimate) })}</p>
      )}
    </>
  );
}
