"use client";

import { useState } from "react";

/** Copie le code promo puis ouvre l'offre (cahier des charges : « code copié automatiquement »). */
export function GoButton({ offerId, code, label = "Voir l'offre" }: { offerId: number; code?: string | null; label?: string }) {
  const [msg, setMsg] = useState<string | null>(null);
  const href = `/go/${offerId}${code ? `?code=${encodeURIComponent(code)}` : ""}`;
  async function onClick(e: React.MouseEvent<HTMLAnchorElement>) {
    if (!code) return;
    e.preventDefault();
    try {
      await navigator.clipboard.writeText(code);
      setMsg(`Code ${code} copié`);
    } catch {
      setMsg(`Note le code ${code}`);
    }
    setTimeout(() => window.open(href, "_blank", "noopener"), 350);
    setTimeout(() => setMsg(null), 2500);
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
    <button
      type="button"
      className="btn ghost"
      style={{ padding: "3px 8px", fontSize: 12 }}
      onClick={async () => {
        try { await navigator.clipboard.writeText(code); setDone(true); setTimeout(() => setDone(false), 1500); } catch { /* rien */ }
      }}
      aria-label={`Copier le code ${code}`}
    >
      {done ? "Copié" : "Copier"}
    </button>
  );
}

/** Bouton « ce code marche / ne marche plus » : alimente le score de confiance. */
export function CodeVote({ codeId }: { codeId: number }) {
  const [state, setState] = useState<"idle" | "sent" | "error">("idle");
  const [choice, setChoice] = useState<boolean | null>(null);
  async function vote(works: boolean) {
    setChoice(works);
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
      <button type="button" aria-pressed={choice === true} onClick={() => vote(true)} disabled={state === "sent"}>Oui</button>
      <button type="button" aria-pressed={choice === false} onClick={() => vote(false)} disabled={state === "sent"}>Non, plus valable</button>
      {state === "sent" && <span>Merci, retour enregistré.</span>}
      {state === "error" && <span>Envoi impossible, réessaie plus tard.</span>}
    </span>
  );
}
