import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { OfferCard } from "@/components/OfferCard";
import { AutoSubmit } from "@/components/client";
import { CATEGORY_BY_ID, MILK_ORIGINS, VITAMINS_GROUP, modeDef, modeOf, type Mode } from "@/lib/categories";
import { getRanking } from "@/lib/data";
import { displayName, num, qs } from "@/lib/format";
import { currentCountry } from "@/lib/country";
import { SITE_URL, monthYear } from "@/lib/site";

export const dynamic = "force-dynamic";

const PAGE = 20;
type SP = Record<string, string | undefined>;

const SEO_TITLE: Record<string, string> = {
  whey: "Whey pas chère : comparatif au prix du kg de protéine",
  creatine: "Créatine pas chère : comparatif au prix du kg de créatine",
  preworkout: "Pré-workout : comparatif au prix de la portion",
  collagene: "Collagène pas cher : comparatif au prix du kg de collagène",
  barres: "Barres protéinées pas chères : comparatif au prix par barre",
  zinc: "Zinc : comparatif au prix du zinc réel (pas du sel)",
  magnesium: "Magnésium : comparatif au prix du magnésium réel",
  vitamine_d: "Vitamine D3 : comparatif au prix des 100 000 UI",
  vitamine_c: "Vitamine C : comparatif au prix du gramme",
  omega3: "Oméga-3 : comparatif au prix de l'EPA + DHA",
  glutamine: "Glutamine : comparatif au prix du kg",
};

export async function generateMetadata({ params, searchParams }: { params: Promise<{ cat: string }>; searchParams: Promise<SP> }): Promise<Metadata> {
  const c = CATEGORY_BY_ID[(await params).cat];
  if (!c) return {};
  const sp = await searchParams;
  const sub = sp.sub && c.subs?.[sp.sub];
  const filtered = Object.keys(sp).some((k) => k !== "sub" && sp[k]);
  const title = `${sub ? `${sub} : ` : ""}${SEO_TITLE[c.id] ?? c.label} (${monthYear()})`;
  const description = `${c.label}${sub ? ` (${sub})` : ""} : toutes les offres des marchands français classées au vrai prix ` +
    `(${modeDef(c.id, c.defaultMode).label.toLowerCase()}), meilleur code promo appliqué, prix mis à jour plusieurs fois par jour.`;
  const path = `/c/${c.id}${sub ? `?sub=${sp.sub}` : ""}`;
  return {
    title, description,
    alternates: { canonical: path },
    openGraph: { title, description, url: path },
    robots: filtered ? { index: false, follow: true } : undefined,   // vues filtrées : pas de doublons dans Google
  };
}

export default async function CategoryPage({ params, searchParams }: { params: Promise<{ cat: string }>; searchParams: Promise<SP> }) {
  const { cat } = await params;
  const sp = await searchParams;
  if (cat === "caseine") redirect("/c/whey?sub=caseine");          // ancienne catégorie, désormais un type de whey
  const c = CATEGORY_BY_ID[cat];
  if (!c) notFound();
  const country = currentCountry();
  const mode: Mode = modeOf(c, sp.mode);
  const opts = { mode, allFormats: sp.all === "1", firstOrder: sp.first === "1", useCodes: sp.codes !== "0" };
  const filters = {
    sub: sp.sub, site: sp.site, brand: sp.brand, form: sp.form, madeIn: sp.made === "1",
    lactose: sp.lactose === "1", noSweetener: sp.nosweet === "1", noSucralose: sp.nosucra === "1",
    minActive: sp.min ? Number(sp.min) : undefined, milk: sp.milk,
  };
  const { rows: all, facets } = await getRanking(cat, filters, opts);
  const showOut = sp.stock === "all";
  const outCount = all.filter((r) => !r.available).length;
  const rows = showOut ? all : all.filter((r) => r.available);
  const shown = Math.max(PAGE, Number(sp.n) || PAGE);
  const visible = rows.slice(0, shown);
  const inStock = rows.filter((r) => r.available);
  const best = inStock[0];
  const base: SP = { ...sp, n: undefined };
  const md = modeDef(cat, mode);
  const has = (f: string) => (c.filters ?? []).includes(f as never);
  const extraActive = [sp.site, sp.brand, sp.form, sp.lactose, sp.nosweet, sp.nosucra, sp.min, sp.milk, sp.all, sp.first, sp.codes, sp.stock].filter(Boolean).length;

  return (
    <>
      {c.group === "vitamins" && <p className="crumb"><Link href="/vitamines">← {VITAMINS_GROUP.label}</Link></p>}
      <section className="summary" aria-live="polite">
        <div>
          <h1>{c.label}</h1>
          {best ? (
            <p>
              Meilleure offre : <b>{displayName(best.brand, best.name, " ")}</b> chez {best.site_name}, {best.variants > 1 ? "à partir de " : ""}
              <b>{num(best.value ?? 0, 2)} {md.unit.replace(/\.$/, "")}</b>{best.applied ? ` avec le code ${best.applied.code.code}` : ""}.
              {" "}{inStock.length} produit{inStock.length > 1 ? "s" : ""} en stock{filters.madeIn ? `, fabriqué${inStock.length > 1 ? "s" : ""} en ${country.name}` : ""}.
            </p>
          ) : (
            <p>{outCount ? `Aucune offre en stock pour ces réglages ; ${outCount} en rupture (case « Afficher les ruptures » dans « + de filtres »).` : "Aucune offre pour ces réglages."}</p>
          )}
        </div>
      </section>

      <form className="controls" action={`/c/${cat}`} aria-label="Réglages du classement">
        <AutoSubmit />
        {c.subs && (
          <div className="row">
            <span className="ctl-label">Type</span>
            <div className="seg">
              <Link href={qs(base, { sub: undefined })} aria-current={!sp.sub}>Tous</Link>
              {Object.entries(c.subs).map(([id, label]) => (
                <Link key={id} href={qs(base, { sub: id })} aria-current={sp.sub === id}>{label}</Link>
              ))}
            </div>
            {sp.sub && <input type="hidden" name="sub" value={sp.sub} />}
          </div>
        )}
        <div className="row">
          <span className="ctl-label">Classer par</span>
          <div className="seg">
            {(Object.keys(c.modes) as Mode[]).map((m) => (
              <Link key={m} href={qs(base, { mode: m === c.defaultMode ? undefined : m })} aria-current={mode === m}>{c.modes[m]!.label}</Link>
            ))}
          </div>
          {sp.mode && <input type="hidden" name="mode" value={sp.mode} />}
          <label className="check made">
            <input type="checkbox" name="made" value="1" defaultChecked={filters.madeIn} />
            <span aria-hidden="true">{country.flag}</span> {country.madeIn}<small> ({facets.madeIn})</small>
          </label>
        </div>
        <details className="more" open={extraActive > 0}>
          <summary>+ de filtres{extraActive ? ` (${extraActive} actif${extraActive > 1 ? "s" : ""})` : ""}</summary>
          <div className="row">
            <select className="filter" name="brand" defaultValue={sp.brand ?? ""} aria-label="Marque">
              <option value="">Toutes les marques</option>
              {facets.brands.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
            <select className="filter" name="site" defaultValue={sp.site ?? ""} aria-label="Marchand">
              <option value="">Tous les marchands</option>
              {facets.sites.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            </select>
            {facets.forms.length > 0 && (
              <select className="filter" name="form" defaultValue={sp.form ?? ""} aria-label="Forme">
                <option value="">Toutes les formes</option>
                {facets.forms.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            )}
            {has("minActive") && (
              <select className="filter" name="min" defaultValue={sp.min ?? ""} aria-label={`${c.activeShare} minimum`}>
                <option value="">{c.activeShare} : tous</option>
                {[60, 70, 75, 80, 85, 90].map((v) => <option key={v} value={v}>{c.activeShare} ≥ {v} %</option>)}
              </select>
            )}
            {has("milk") && facets.milk.length > 0 && (
              <select className="filter" name="milk" defaultValue={sp.milk ?? ""} aria-label="Origine du lait">
                <option value="">Origine du lait : toutes</option>
                {facets.milk.map((m) => <option key={m} value={m}>Lait : {MILK_ORIGINS[m] ?? m}</option>)}
              </select>
            )}
          </div>
          <div className="row">
            {has("lactose") && <label className="check"><input type="checkbox" name="lactose" value="1" defaultChecked={filters.lactose} /> Sans lactose</label>}
            {has("sweetener") && <label className="check"><input type="checkbox" name="nosweet" value="1" defaultChecked={filters.noSweetener} /> Sans édulcorant</label>}
            {has("sucralose") && <label className="check"><input type="checkbox" name="nosucra" value="1" defaultChecked={filters.noSucralose} /> Sans sucralose</label>}
            <label className="check"><input type="checkbox" name="stock" value="all" defaultChecked={showOut} /> Afficher les ruptures ({outCount})</label>
            <label className="check"><input type="checkbox" name="all" value="1" defaultChecked={opts.allFormats} /> Tous les formats et arômes</label>
            <label className="check"><input type="checkbox" name="first" value="1" defaultChecked={opts.firstOrder} /> J'ai droit aux codes « 1re commande »</label>
            <label className="check"><input type="checkbox" name="codes" value="0" defaultChecked={!opts.useCodes} /> Ignorer les codes promo</label>
          </div>
          {(has("lactose") || has("sweetener")) && (
            <p className="note-small">Les filtres « sans… » ne retiennent que les fiches qui le disent ou dont la liste d'ingrédients le montre ;
              une fiche muette est exclue.</p>
          )}
          <div className="row"><button type="submit" className="btn ghost">Appliquer</button>
            {extraActive > 0 && <Link className="btn ghost" href={qs({ sub: sp.sub, mode: sp.mode }, {})}>Tout réinitialiser</Link>}</div>
        </details>
      </form>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
        "@context": "https://schema.org", "@type": "ItemList", name: c.label,
        itemListElement: inStock.slice(0, 20).map((r, i) => ({
          "@type": "ListItem", position: i + 1, url: `${SITE_URL}/p/${r.product_id}`, name: displayName(r.brand, r.name, " "),
        })),
      }) }} />

      {visible.length > 0 ? (
        <ol className="list">
          {visible.map((r, i) => <OfferCard key={r.offer_id} r={r} rank={i + 1} mode={mode} best={i === 0 && r.available} />)}
        </ol>
      ) : (
        <p className="empty">Aucune offre pour ces réglages.</p>
      )}
      {rows.length > shown && (
        <p className="more-results">
          <Link className="btn ghost" href={`${qs(base, { n: String(shown + PAGE) })}#r${shown + 1}`} scroll={false}>
            Voir {Math.min(PAGE, rows.length - shown)} produits de plus ({shown} sur {rows.length})
          </Link>
        </p>
      )}

      <section className="notes">
        <div className="note">
          <h3>Comment on calcule</h3>
          Prix final = prix affiché − meilleur code applicable, divisé par la quantité d'actif ou le poids du contenant entier.
          Pour chaque produit, seul l'arôme ou le format le moins cher est affiché. Frais de port non inclus.
        </div>
        <div className="note">
          <h3>Être prévenu d'une baisse</h3>
          Bouton « Alerte prix » sur chaque produit, ou <Link href={`/alertes?cat=${cat}`}>une alerte sur toute la catégorie</Link>.
        </div>
      </section>
    </>
  );
}
