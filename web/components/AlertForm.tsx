"use client";

import { useState } from "react";

/** Textes du formulaire, traduits par la page (messages alerts.form.*). */
export interface AlertFormText {
  email: string; placeholder: string; when: string; under: string; sending: string; create: string;
  saved: string; failed: string; failedLater: string; privacy: string;
}

/** Formulaire d'alerte prix (e-mail + seuil + unité). */
export function AlertForm({ country, product, cat, sub, units, defaults, m }: {
  country: string;                                      // code ISO du pays de la page, enregistré avec l'alerte
  product?: number; cat: string; sub?: string;
  units: { mode: string; label: string }[];             // « prix du produit (€) », « €/kg de protéine »…
  defaults?: Record<string, number>;                    // valeur actuelle par mode, pour pré-remplir
  m: AlertFormText;
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
                               product_id: product ?? null, category: cat, subcategory: sub ?? null, mode, country }),
      });
      const j = await r.json().catch(() => ({}));
      setState(r.ok ? "ok" : "error");
      setMsg(j.message ?? (r.ok ? m.saved : m.failed));
    } catch {
      setState("error");
      setMsg(m.failedLater);
    }
  }
  if (state === "ok") return <p className="ok" role="status">{msg}</p>;
  return (
    <form className="alertform" onSubmit={submit}>
      <label>{m.email} <input type="email" name="email" required autoComplete="email" placeholder={m.placeholder} /></label>
      <label>{m.when}
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          {units.map((u) => <option key={u.mode} value={u.mode}>{u.label}</option>)}
        </select>
      </label>
      <label>{m.under} <input key={mode} name="threshold" inputMode="decimal" required defaultValue={fmt(defaults?.[mode])} /></label>
      <button type="submit" className="btn blaze" disabled={state === "busy"}>{state === "busy" ? m.sending : m.create}</button>
      {state === "error" && <p className="err" role="alert">{msg}</p>}
      <p className="note-small">{m.privacy}</p>
    </form>
  );
}
