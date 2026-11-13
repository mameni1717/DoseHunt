"use client";

import { useEffect, useState } from "react";
import { eur } from "@/lib/format";
import { formatLabel } from "@/lib/rank";
import type { QtyKind } from "@/lib/optimize";
import { GoButton } from "@/components/client";

export interface CatChoice { id: string; label: string; subs: Record<string, string>; kind: QtyKind; kindLabel: string; defaultQty: number }

interface Item { cat: string; sub: string; qty: number; pin: string | null; pinLabel: string | null }

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

const STORE = "dosehunt.optimiser.v1";

function load(): { items: Item[]; firstOrder: boolean; useCodes: boolean } | null {
  try {
    const raw = localStorage.getItem(STORE);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function qtyText(kind: QtyKind, n: number): string {
  if (kind === "grams") return n >= 1000 ? `${(n / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 2 })} kg` : `${n} g`;
  return `${n} ${kind === "portions" ? "portions" : "unités"}`;
}

export function Optimizer({ cats, shippingEstimate }: { cats: CatChoice[]; shippingEstimate: number }) {
  const byId = Object.fromEntries(cats.map((c) => [c.id, c]));
  const [items, setItems] = useState<Item[]>([{ cat: "whey", sub: "", qty: byId.whey?.defaultQty ?? 1000, pin: null, pinLabel: null }]);
  const [firstOrder, setFirstOrder] = useState(false);
  const [useCodes, setUseCodes] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [result, setResult] = useState<ResBasket[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<{ idx: number; q: string; hits: { key: string; label: string; sites: number }[] } | null>(null);

  useEffect(() => {
    const s = load();
    if (s?.items?.length) { setItems(s.items.filter((i) => byId[i.cat])); setFirstOrder(!!s.firstOrder); setUseCodes(s.useCodes !== false); }
    setLoaded(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!loaded) return;
    try { localStorage.setItem(STORE, JSON.stringify({ items, firstOrder, useCodes })); } catch { /* navigation privée */ }
  }, [items, firstOrder, useCodes, loaded]);

  const update = (i: number, patch: Partial<Item>) => { setItems((xs) => xs.map((x, k) => (k === i ? { ...x, ...patch } : x))); setResult(null); };
  const add = () => {
    const free = cats.find((c) => !items.some((i) => i.cat === c.id)) ?? cats[0];
    setItems((xs) => [...xs, { cat: free.id, sub: "", qty: free.defaultQty, pin: null, pinLabel: null }]);
    setResult(null);
  };
  const remove = (i: number) => { setItems((xs) => xs.filter((_, k) => k !== i)); setResult(null); };

  async function find(idx: number, q: string) {
    setSearch({ idx, q, hits: search?.idx === idx ? search.hits : [] });
    if (q.trim().length < 2) return;
    try {
      const r = await fetch(`/api/optimiser?cat=${encodeURIComponent(items[idx].cat)}&q=${encodeURIComponent(q)}`);
      const hits = await r.json();
      setSearch((s) => (s && s.idx === idx && s.q === q ? { ...s, hits } : s));
    } catch { /* recherche indisponible */ }
  }

  async function run() {
    setBusy(true); setError(null);
    try {
      const r = await fetch("/api/optimiser", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ needs: items.map((i) => ({ cat: i.cat, sub: i.sub || null, qty: i.qty, pin: i.pin })), firstOrder, useCodes }),
      });
      if (!r.ok) throw new Error(String(r.status));
      setResult((await r.json()).baskets);
    } catch {
      setError("Le calcul n'a pas abouti. Réessaie dans un instant.");
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
                <select className="filter" aria-label="Catégorie" value={it.cat}
                  onChange={(e) => update(i, { cat: e.target.value, sub: "", qty: byId[e.target.value].defaultQty, pin: null, pinLabel: null })}>
                  {cats.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </select>
                {Object.keys(c.subs).length > 0 && !it.pin && (
                  <select className="filter" aria-label="Type" value={it.sub} onChange={(e) => update(i, { sub: e.target.value })}>
                    <option value="">Tous types</option>
                    {Object.entries(c.subs).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                )}
                <label className="opt-qty">
                  <input type="number" min={1} step={c.kind === "grams" ? 100 : 1} value={it.qty}
                    onChange={(e) => update(i, { qty: Math.max(0, Number(e.target.value)) })} />
                  <span>{c.kindLabel}</span>
                </label>
                <button type="button" className="btn ghost small" onClick={() => remove(i)} aria-label="Retirer cette ligne"
                  disabled={items.length === 1}>Retirer</button>
              </div>
              <div className="row opt-pin">
                {it.pin ? (
                  <span className="chip">Produit précis : {it.pinLabel}
                    <button type="button" className="linkish" onClick={() => update(i, { pin: null, pinLabel: null })}>× le moins cher de la catégorie</button>
                  </span>
                ) : (
                  <>
                    <input className="filter grow" placeholder="Le moins cher de la catégorie, ou cherche un produit précis (marque, nom)…"
                      value={search?.idx === i ? search.q : ""} onChange={(e) => find(i, e.target.value)} />
                    {search?.idx === i && search.hits.length > 0 && (
                      <ul className="opt-hits">
                        {search.hits.map((h) => (
                          <li key={h.key}>
                            <button type="button" onClick={() => { update(i, { pin: h.key, pinLabel: h.label, sub: "" }); setSearch(null); }}>
                              {h.label} <small>· {h.sites} site{h.sites > 1 ? "s" : ""}</small>
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
          <button type="button" className="btn ghost" onClick={add}>+ Ajouter un produit</button>
          <label className="check"><input type="checkbox" checked={firstOrder} onChange={(e) => { setFirstOrder(e.target.checked); setResult(null); }} /> J&apos;ai droit aux codes « 1re commande »</label>
          <label className="check"><input type="checkbox" checked={!useCodes} onChange={(e) => { setUseCodes(!e.target.checked); setResult(null); }} /> Ignorer les codes promo</label>
          <button type="button" className="btn blaze" onClick={run} disabled={busy || !items.length}>{busy ? "Calcul…" : "Trouver les 3 meilleurs sites"}</button>
        </div>
      </div>

      {error && <p className="empty">{error}</p>}
      {result && result.length === 0 && (
        <p className="empty">Aucun marchand n&apos;a toute ta liste en stock. Retire une ligne, élargis le type ou enlève un produit précis.</p>
      )}
      {result && result.length > 0 && (
        <ol className="opt-results">
          {result.map((b, k) => (
            <li key={b.site_id} className={`card opt-basket${k === 0 ? " best" : ""}`}>
              <header className="opt-head">
                <span className="rank">{k + 1}</span>
                <h2>{b.site_name}</h2>
                <div className="opt-total">
                  <strong>{eur(b.total)}</strong>
                  {b.total < b.subtotal && <s>{eur(b.subtotal)}</s>}
                </div>
              </header>
              <div className="subline">
                {b.code && <span className="chip code">Code {b.code.code} : −{eur(b.code.discount)}{b.code.pct ? ` (−${b.code.pct} %)` : ""}{b.code.firstOrder ? " · 1re commande" : ""}</span>}
                {b.freeShipping && <span className="chip good">🚚 Livraison offerte</span>}
                {!b.freeShipping && b.freeCode && <span className="chip good">🚚 Livraison offerte avec le code {b.freeCode}</span>}
                {!b.freeShipping && !b.freeCode && b.missingForFree != null && <span>🚚 + frais de port · encore {eur(b.missingForFree)} pour la livraison offerte (dès {eur(b.freeFrom)})</span>}
                {!b.freeShipping && !b.freeCode && b.missingForFree == null && <span>🚚 + frais de port (seuil de livraison offerte non trouvé)</span>}
              </div>
              <table className="opt-lines">
                <tbody>
                  {b.lines.map((l) => (
                    <tr key={l.offer_id}>
                      <td><a href={`/p/${l.product_id}`}>{l.brand ? `${l.brand} · ` : ""}{l.name}</a>
                        <small> · {formatLabel(l)}{l.flavour ? ` · ${l.flavour}` : ""}</small></td>
                      <td className="num opt-unit">{l.copies > 1 ? `${l.copies} × ${eur(l.price)}` : eur(l.price)}</td>
                      <td className="num">{l.copies > 1 && <small className="opt-copies">{l.copies} × </small>}{eur(l.cost)}</td>
                      <td><GoButton offerId={l.offer_id} code={b.code?.code} label="Voir" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="opt-note">Couvre : {b.lines.map((l) => `${byId[l.cat]?.label ?? l.cat} ${qtyText(byId[l.cat]?.kind ?? "grams", l.covered)}`).join(" · ")}</p>
            </li>
          ))}
        </ol>
      )}
      {result && result.length > 0 && (
        <p className="opt-note">Prix relevés au dernier passage, arôme le moins cher en stock. Les sites sans livraison offerte sont
          départagés avec une estimation de {eur(shippingEstimate)} de port, jamais ajoutée au total affiché. Vérifie le panier sur le site avant de payer.</p>
      )}
    </>
  );
}
