"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/** Copie le code promo et ouvre l'offre dans le même clic (un window.open différé est bloqué par les navigateurs). */
export function GoButton({ offerId, code, label = "Voir l'offre", big = false }: { offerId: number; code?: string | null; label?: string; big?: boolean }) {
  const [msg, setMsg] = useState<string | null>(null);
  const href = `/go/${offerId}${code ? `?code=${encodeURIComponent(code)}` : ""}`;
  function onClick() {
    if (!code) return;
    navigator.clipboard?.writeText(code).then(() => setMsg(`Code ${code} copié`), () => setMsg(`Note le code ${code}`));
    setTimeout(() => setMsg(null), 3000);
  }
  return (
    <>
      <a className={big ? "btn blaze big" : "btn blaze"} href={href} target="_blank" rel="nofollow sponsored noopener" onClick={onClick}>
        {label} ↗
      </a>
      {msg && <span className="toast" role="status">{msg}</span>}
    </>
  );
}

export function CopyCode({ code }: { code: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="btn ghost small" aria-label={`Copier le code ${code}`}
      onClick={() => navigator.clipboard?.writeText(code).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }, () => {})}>
      {done ? "Copié" : "Copier"}
    </button>
  );
}

/** Bouton « ce code marche / ne marche plus » : alimente le score de confiance. */
export function CodeVote({ codeId }: { codeId: number }) {
  const [state, setState] = useState<"idle" | "busy" | "sent" | "error">("idle");
  const [choice, setChoice] = useState<boolean | null>(null);
  async function vote(works: boolean) {
    if (state === "busy" || state === "sent") return;
    setChoice(works);
    setState("busy");
    try {
      const r = await fetch(`/api/codes/${codeId}/vote`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ works }),
      });
      setState(r.ok ? "sent" : "error");
    } catch {
      setState("error");
    }
  }
  return (
    <span className="vote">
      Ce code a marché pour toi ?
      <button type="button" aria-pressed={choice === true} onClick={() => vote(true)} disabled={state === "sent" || state === "busy"}>Oui</button>
      <button type="button" aria-pressed={choice === false} onClick={() => vote(false)} disabled={state === "sent" || state === "busy"}>Non, plus valable</button>
      {state === "sent" && <span>Merci, retour enregistré.</span>}
      {state === "error" && <span>Envoi impossible, réessaie plus tard.</span>}
    </span>
  );
}

/** Filtres du formulaire parent : rien ne s'applique avant « Appliquer » ; le bouton signale les changements en attente. */
export function ApplyFilters({ children }: { children?: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pending, setPending] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const form = ref.current?.closest("form");
    if (!form) return;
    const fields = () => Array.from(form.querySelectorAll<HTMLInputElement | HTMLSelectElement>("select, input[type=checkbox]"));
    const initial = new Map(fields().map((f) => [f, f instanceof HTMLInputElement ? String(f.checked) : f.value]));
    const onChange = () => setPending(fields().filter((f) =>
      initial.get(f) !== (f instanceof HTMLInputElement ? String(f.checked) : f.value)).length);
    const onSubmit = () => setBusy(true);
    form.addEventListener("change", onChange);
    form.addEventListener("submit", onSubmit);
    return () => { form.removeEventListener("change", onChange); form.removeEventListener("submit", onSubmit); };
  }, []);
  return (
    <div ref={ref} className="row apply-row">
      <button type="submit" className={pending ? "btn primary" : "btn ghost"}>
        {busy ? "Mise à jour…" : "Appliquer"}
      </button>
      {pending > 0 && !busy && <span className="pending" aria-live="polite">{pending} filtre{pending > 1 ? "s" : ""} non appliqué{pending > 1 ? "s" : ""}</span>}
      {children}
    </div>
  );
}

// ------------------------------------------------------------------ comparateur : sélection gardée dans le navigateur

type Picked = { id: number; cat: string; label: string };
// Une sélection par pays : un produit espagnol ne se compare pas sur la version française.
const keyFor = (country: string) => `dosehunt-compare-${country}`;
const EVENT = "dosehunt-compare-change";

function readPicked(country: string): Picked[] {
  try { return JSON.parse(localStorage.getItem(keyFor(country)) || (country === "FR" ? localStorage.getItem("dosehunt-compare") : null) || "[]"); }
  catch { return []; }
}
function writePicked(country: string, list: Picked[]) {
  try { localStorage.setItem(keyFor(country), JSON.stringify(list)); } catch { /* stockage indisponible */ }
  window.dispatchEvent(new Event(EVENT));
}

function usePicked(country: string): Picked[] {
  const [list, setList] = useState<Picked[]>([]);
  useEffect(() => {
    const sync = () => setList(readPicked(country));
    sync();
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener(EVENT, sync); window.removeEventListener("storage", sync); };
  }, [country]);
  return list;
}

export function CompareToggle({ id, cat, label, country, m }: Picked & { country: string; m: { add: string; added: string } }) {
  const list = usePicked(country);
  const on = list.some((p) => p.id === id);
  return (
    <button type="button" className={`btn ghost small${on ? " on" : ""}`} aria-pressed={on}
      onClick={() => {
        const cur = readPicked(country);
        writePicked(country, on ? cur.filter((p) => p.id !== id) : [...cur.filter((p) => p.id !== id), { id, cat, label }].slice(-6));
      }}>
      {on ? m.added : m.add}
    </button>
  );
}

export interface CompareBarText { toCompare: string; toCompareMany: string; pickTwo: string; compare: string; clear: string; region: string }

export function CompareBar({ country, prefix, m }: { country: string; lang?: string; prefix: string; m: CompareBarText }) {
  const list = usePicked(country);
  if (list.length === 0) return null;
  return (
    <div className="comparebar" role="region" aria-label={m.region}>
      <span><b>{list.length}</b> {list.length > 1 ? m.toCompareMany : m.toCompare}{list.length < 2 ? m.pickTwo : ""}</span>
      <span className="names">{list.map((p) => p.label).join(" · ")}</span>
      {list.length >= 2 && <a className="btn blaze" href={`${prefix}/comparer?ids=${list.map((p) => p.id).join(",")}`}>{m.compare}</a>}
      <button type="button" className="btn ghost small" onClick={() => writePicked(country, [])}>{m.clear}</button>
    </div>
  );
}

/** Photo du marchand ; si elle ne se charge pas (lien protégé, image retirée), une vignette neutre la remplace. */
export function ProductImage({ src, letter, size = 72 }: { src?: string | null; letter: string; size?: number }) {
  const [broken, setBroken] = useState(!src);
  if (broken) return <span className="nopic" aria-hidden="true">{letter}</span>;
  const url = src!.startsWith("http://") ? "https://" + src!.slice(7) : src!;
  return <img src={url} alt="" loading="lazy" width={size} height={size} referrerPolicy="no-referrer" onError={() => setBroken(true)} />;
}
