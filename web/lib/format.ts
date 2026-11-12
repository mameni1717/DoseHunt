export const eur = (n: number | null | undefined) =>
  n == null ? "–" : n.toLocaleString("fr-FR", { style: "currency", currency: "EUR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const num = (n: number, d = 0) => n.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });

export function ago(d: Date | string | null | undefined): string {
  if (!d) return "date inconnue";
  const t = typeof d === "string" ? new Date(d) : d;
  const mins = Math.round((Date.now() - t.getTime()) / 60000);
  if (mins < 60) return `il y a ${Math.max(1, mins)} min`;
  const h = Math.round(mins / 60);
  if (h < 48) return `il y a ${h} h`;
  return `le ${t.toLocaleDateString("fr-FR")}`;
}

export function dateFr(d: Date | string | null | undefined): string {
  if (!d) return "–";
  const t = typeof d === "string" ? new Date(d) : d;
  return t.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function qs(base: Record<string, string | undefined>, change: Record<string, string | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...base, ...change })) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** « Grenade » + « Grenade Soft Core Protein Bar » → pas de marque répétée. */
export function displayName(brand: string | null | undefined, name: string, sep = " · "): string {
  if (!brand) return name;
  const norm = (s: string) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  return norm(name).startsWith(norm(brand)) ? name : `${brand}${sep}${name}`;
}
