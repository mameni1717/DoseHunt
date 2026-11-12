import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { OfferCard, unitFor } from "@/components/OfferCard";
import { CATEGORY_BY_ID, type Mode } from "@/lib/categories";
import { getRanking } from "@/lib/data";
import { displayName, num, qs } from "@/lib/format";

export const dynamic = "force-dynamic";

type SP = Record<string, string | undefined>;

export async function generateMetadata({ params }: { params: Promise<{ cat: string }> }): Promise<Metadata> {
  const c = CATEGORY_BY_ID[(await params).cat];
  return c ? { title: `${c.label} : le moins cher au gramme utile` } : {};
}

export default async function CategoryPage({ params, searchParams }: { params: Promise<{ cat: string }>; searchParams: Promise<SP> }) {
  const { cat } = await params;
  const sp = await searchParams;
  const c = CATEGORY_BY_ID[cat];
  if (!c) notFound();
  let mode = (sp.mode as Mode) || c.defaultMode;
  if (!c.modes[mode] || c.modes[mode].disabled) mode = c.defaultMode;
  const opts = { mode, allFormats: sp.all === "1", firstOrder: sp.first === "1", useCodes: sp.codes !== "0" };
  const filters = { sub: sp.sub, site: sp.site, brand: sp.brand, form: sp.form };
  const { rows, facets } = await getRanking(cat, filters, opts);
  const base: SP = { mode: sp.mode, sub: sp.sub, all: sp.all, first: sp.first, codes: sp.codes, site: sp.site, brand: sp.brand, form: sp.form };
  const best = rows[0];
  const worst = rows[rows.length - 1];

  return (
    <>
      <section className="controls" aria-label="Réglages du classement">
        {c.subs && (
          <div className="row">
            <span className="ctl-label">Type</span>
            <div className="seg">
              <Link href={qs(base, { sub: undefined })} aria-current={!sp.sub}>Toutes</Link>
              {Object.entries(c.subs).map(([id, label]) => (
                <Link key={id} href={qs(base, { sub: id })} aria-current={sp.sub === id}>{label}</Link>
              ))}
            </div>
          </div>
        )}
        <div className="row">
          <span className="ctl-label">Comparer</span>
          <div className="seg">
            {(Object.keys(c.modes) as Mode[]).map((m) =>
              c.modes[m].disabled ? (
                <span key={m} className="off" title={c.modes[m].disabled}>{c.modes[m].label}</span>
              ) : (
                <Link key={m} href={qs(base, { mode: m === c.defaultMode ? undefined : m })} aria-current={mode === m}>{c.modes[m].label}</Link>
              ),
            )}
          </div>
        </div>
        <div className="row">
          <Link className="toggle" href={qs(base, { all: opts.allFormats ? undefined : "1" })}><b>{opts.allFormats ? "✓" : ""}</b> Afficher tous les formats</Link>
          <Link className="toggle" href={qs(base, { first: opts.firstOrder ? undefined : "1" })}><b>{opts.firstOrder ? "✓" : ""}</b> J'ai droit aux codes « 1re commande »</Link>
          <Link className="toggle" href={qs(base, { codes: opts.useCodes ? "0" : undefined })}><b>{opts.useCodes ? "✓" : ""}</b> Appliquer les codes promo</Link>
        </div>
        <form className="row" action={`/c/${cat}`}>
          {Object.entries(base).filter(([k, v]) => v && !["site", "brand", "form"].includes(k)).map(([k, v]) => (
            <input key={k} type="hidden" name={k} value={v} />
          ))}
          <span className="ctl-label">Filtrer</span>
          <select className="filter" name="site" defaultValue={sp.site ?? ""} aria-label="Site">
            <option value="">Tous les sites</option>
            {facets.sites.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
          <select className="filter" name="brand" defaultValue={sp.brand ?? ""} aria-label="Marque">
            <option value="">Toutes les marques</option>
            {facets.brands.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
          {facets.forms.length > 0 && (
            <select className="filter" name="form" defaultValue={sp.form ?? ""} aria-label="Forme">
              <option value="">Toutes les formes</option>
              {facets.forms.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          )}
          <button type="submit" className="btn ghost">Appliquer</button>
        </form>
      </section>

      <section className="summary" aria-live="polite">
        <div>
          {best ? (
            <>
              <h1>{displayName(best.brand, best.name, " ")} : <em>{num(best.value ?? 0, 2)} {unitFor(cat, mode, best)}</em></h1>
              <p>
                Meilleure offre en {c.modes[mode].label.toLowerCase()}, chez {best.site_name}
                {best.applied ? `, avec le code ${best.applied.code.code}` : ""}. {rows.length} offre{rows.length > 1 ? "s" : ""} comparée{rows.length > 1 ? "s" : ""} en France.
              </p>
            </>
          ) : (
            <>
              <h1>Aucune offre pour ces réglages</h1>
              <p>Les collectes de cette catégorie n'ont encore rien indexé, ou les filtres sont trop restrictifs.</p>
            </>
          )}
        </div>
        {best && worst && best !== worst && (
          <div className="spread"><b>×{num((worst.value ?? 0) / (best.value ?? 1), 1)}</b><span>d'écart entre la 1re et la dernière offre</span></div>
        )}
      </section>

      {rows.length > 0 ? (
        <ol className="list">
          {rows.map((r, i) => <OfferCard key={r.offer_id} r={r} rank={i + 1} mode={mode} best={i === 0} />)}
        </ol>
      ) : (
        <p className="empty">Aucune offre pour ces réglages.</p>
      )}

      <section className="notes">
        <div className="note">
          <h3>Comment on calcule</h3>
          Prix final = prix affiché − meilleur code applicable, puis division par la quantité d'actif, le poids ou le nombre
          d'unités du contenant entier. Frais de port non inclus.
        </div>
        <div className="note">
          <h3>Produits combinés</h3>
          Un produit qui apporte deux actifs (whey + collagène, zinc + magnésium) figure dans chaque liste ; son prix entier
          est attribué à l'actif de la liste, il paraît donc un peu plus cher qu'il ne l'est.
        </div>
      </section>
    </>
  );
}
