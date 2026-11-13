"use client";

import { useState } from "react";

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
