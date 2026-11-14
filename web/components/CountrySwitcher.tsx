"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

// Choix du pays : le visiteur choisit, le site suggère. Aucune redirection automatique (Google explore depuis les
// États-Unis et doit voir chaque version à son adresse). Les textes arrivent tout traduits depuis le serveur.

export interface CountryChoice {
  iso: string;
  path: string;        // "" pour la France
  flag: string;
  name: string;
  suggest: string;     // « ¿Estás en España? » dans la langue du pays
  go: string;          // « Ir a la versión española → »
  stay: string;        // « Quedarme aquí »
}

const COOKIE = "dosehunt_country";

function remember(iso: string) {
  // Cookie fonctionnel, sans donnée personnelle : seulement le code du pays choisi, un an.
  document.cookie = `${COOKIE}=${iso}; path=/; max-age=31536000; samesite=lax`;
}

function go(url: string, iso: string) {
  remember(iso);
  window.location.href = url;
}

function chosen(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)dosehunt_country=([A-Z]{2})/);
  return m ? m[1] : null;
}

/** Même page dans un autre pays : catégorie → même catégorie ; fiche produit → accueil du pays. */
export function equivalentPath(pathname: string, search: string, from: CountryChoice | undefined, to: CountryChoice): string {
  let rest = pathname;
  // La France est servie par réécriture : côté navigateur, le chemin peut apparaître avec le segment interne /fr.
  if (rest === "/fr" || rest.startsWith("/fr/")) rest = rest.slice(3) || "/";
  if (from?.path && (rest === `/${from.path}` || rest.startsWith(`/${from.path}/`))) rest = rest.slice(from.path.length + 1) || "/";
  if (rest.startsWith("/p/")) rest = "/";
  const q = rest.startsWith("/c/") ? search : "";
  const base = to.path ? (rest === "/" ? `/${to.path}` : `/${to.path}${rest}`) : rest;
  return base + q;
}

export function CountrySwitcher({ current, choices, label, soloTitle }: { current: string; choices: CountryChoice[]; label: string; soloTitle?: string }) {
  const pathname = usePathname() ?? "/";
  const cur = choices.find((c) => c.iso === current);
  if (!cur) return null;
  // Un seul pays proposé : simple mention, comme avant l'ouverture des autres pays.
  if (choices.length < 2) return <span className="country" title={soloTitle}>{cur.name}</span>;
  return (
    <details className="country-switch">
      <summary aria-label={label}><span aria-hidden="true">{cur.flag}</span> {cur.name}</summary>
      <ul>
        {choices.map((c) => (
          <li key={c.iso}>
            <a href={equivalentPath(pathname, "", cur, c)} aria-current={c.iso === current ? "true" : undefined}
               onClick={(e) => { e.preventDefault(); go(equivalentPath(pathname, window.location.search, cur, c), c.iso); }}>
              <span aria-hidden="true">{c.flag}</span> {c.name}
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Bandeau discret si le pays détecté (en-tête Vercel, lu côté navigateur) est un autre pays actif. */
export function CountryBanner({ current, choices }: { current: string; choices: CountryChoice[] }) {
  const pathname = usePathname() ?? "/";
  const [target, setTarget] = useState<CountryChoice | null>(null);
  useEffect(() => {
    if (chosen()) return;
    let off = false;
    fetch("/api/geo", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { country?: string | null } | null) => {
        const iso = j?.country?.toUpperCase();
        const c = iso && iso !== current ? choices.find((x) => x.iso === iso) : undefined;
        if (!off && c) setTarget(c);
      })
      .catch(() => {});
    return () => { off = true; };
  }, [current, choices]);
  if (!target) return null;
  const cur = choices.find((c) => c.iso === current);
  return (
    <div className="country-banner" role="region">
      <span><span aria-hidden="true">{target.flag}</span> {target.suggest}</span>
      <a className="btn blaze small" href={equivalentPath(pathname, "", cur, target)}
         onClick={(e) => { e.preventDefault(); go(equivalentPath(pathname, window.location.search, cur, target), target.iso); }}>
        {target.go}
      </a>
      <button type="button" className="btn ghost small" onClick={() => { remember(current); setTarget(null); }}>{target.stay}</button>
    </div>
  );
}
