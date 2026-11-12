"use client";

import { useEffect, useRef, useState } from "react";

/** Copie le code promo et ouvre l'offre dans le même clic (un window.open différé est bloqué par les navigateurs). */
export function GoButton({ offerId, code, label = "Voir l'offre" }: { offerId: number; code?: string | null; label?: string }) {
  const [msg, setMsg] = useState<string | null>(null);
  const href = `/go/${offerId}${code ? `?code=${encodeURIComponent(code)}` : ""}`;
  function onClick() {
    if (!code) return;
    navigator.clipboard?.writeText(code).then(() => setMsg(`Code ${code} copié`), () => setMsg(`Note le code ${code}`));
    setTimeout(() => setMsg(null), 3000);
  }
  return (
    <>
      <a className="btn blaze" href={href} target="_blank" rel="nofollow sponsored noopener" onClick={onClick}>
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

/** Soumet le formulaire parent dès qu'un filtre change (le bouton « Appliquer » reste pour les navigateurs sans JS). */
export function AutoSubmit() {
  const ref = useRef<HTMLSpanElement>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const form = ref.current?.closest("form");
    if (!form) return;
    const onChange = (e: Event) => {
      const t = e.target as HTMLElement;
      if (t.matches("select, input[type=checkbox], input[type=radio]")) {
        setBusy(true);
        form.requestSubmit();
      }
    };
    form.addEventListener("change", onChange);
    return () => form.removeEventListener("change", onChange);
  }, []);
  return <span ref={ref} className="busy" aria-live="polite">{busy ? "Mise à jour…" : ""}</span>;
}

// ------------------------------------------------------------------ comparateur : sélection gardée dans le navigateur

type Picked = { id: number; cat: string; label: string };
const KEY = "dosehunt-compare";
const EVENT = "dosehunt-compare-change";

function readPicked(): Picked[] {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
}
function writePicked(list: Picked[]) {
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* stockage indisponible */ }
  window.dispatchEvent(new Event(EVENT));
}

function usePicked(): Picked[] {
  const [list, setList] = useState<Picked[]>([]);
  useEffect(() => {
    const sync = () => setList(readPicked());
    sync();
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener(EVENT, sync); window.removeEventListener("storage", sync); };
  }, []);
  return list;
}

export function CompareToggle({ id, cat, label }: Picked) {
  const list = usePicked();
  const on = list.some((p) => p.id === id);
  return (
    <button type="button" className={`btn ghost small${on ? " on" : ""}`} aria-pressed={on}
      onClick={() => {
        const cur = readPicked();
        writePicked(on ? cur.filter((p) => p.id !== id) : [...cur.filter((p) => p.id !== id), { id, cat, label }].slice(-6));
      }}>
      {on ? "✓ Comparé" : "Comparer"}
    </button>
  );
}

export function CompareBar() {
  const list = usePicked();
  if (list.length === 0) return null;
  return (
    <div className="comparebar" role="region" aria-label="Produits à comparer">
      <span><b>{list.length}</b> produit{list.length > 1 ? "s" : ""} à comparer{list.length < 2 ? " (choisis-en au moins 2)" : ""}</span>
      <span className="names">{list.map((p) => p.label).join(" · ")}</span>
      {list.length >= 2 && <a className="btn blaze" href={`/comparer?ids=${list.map((p) => p.id).join(",")}`}>Comparer</a>}
      <button type="button" className="btn ghost small" onClick={() => writePicked([])}>Vider</button>
    </div>
  );
}

/** Formulaire d'alerte prix (e-mail + seuil + unité). */
export function AlertForm({ product, cat, sub, units, defaults }: {
  product?: number; cat: string; sub?: string;
  units: { mode: string; label: string }[];             // « prix du produit (€) », « €/kg de protéine »…
  defaults?: Record<string, number>;                    // valeur actuelle par mode, pour pré-remplir
}) {
  const [state, setState] = useState<"idle" | "busy" | "ok" | "error">("idle");
  const [msg, setMsg] = useState("");
  const [mode, setMode] = useState(units[0]?.mode ?? "dose");
  const fmt = (v?: number) => (v ? (Math.floor(v * 0.95 * 100) / 100).toFixed(2).replace(".", ",") : "");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setState("busy");
    try {
      const r = await fetch("/api/alerts", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: fd.get("email"), threshold: Number(String(fd.get("threshold")).replace(",", ".")),
                               product_id: product ?? null, category: cat, subcategory: sub ?? null, mode }),
      });
      const j = await r.json().catch(() => ({}));
      setState(r.ok ? "ok" : "error");
      setMsg(j.message ?? (r.ok ? "Alerte enregistrée." : "Enregistrement impossible."));
    } catch {
      setState("error");
      setMsg("Enregistrement impossible, réessaie plus tard.");
    }
  }
  if (state === "ok") return <p className="ok" role="status">{msg}</p>;
  return (
    <form className="alertform" onSubmit={submit}>
      <label>Ton e-mail <input type="email" name="email" required autoComplete="email" placeholder="toi@exemple.fr" /></label>
      <label>Me prévenir quand
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          {units.map((u) => <option key={u.mode} value={u.mode}>{u.label}</option>)}
        </select>
      </label>
      <label>passe sous <input key={mode} name="threshold" inputMode="decimal" required defaultValue={fmt(defaults?.[mode])} /></label>
      <button type="submit" className="btn blaze" disabled={state === "busy"}>{state === "busy" ? "Envoi…" : "Créer l'alerte"}</button>
      {state === "error" && <p className="err" role="alert">{msg}</p>}
      <p className="note-small">Un e-mail de confirmation t'est envoyé avant toute alerte. Ton adresse ne sert qu'à ça et chaque
        e-mail contient un lien de désinscription.</p>
    </form>
  );
}
