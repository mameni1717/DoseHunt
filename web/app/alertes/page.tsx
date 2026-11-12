import type { Metadata } from "next";
import Link from "next/link";
import { AlertForm } from "@/components/client";
import { CATEGORIES, CATEGORY_BY_ID, modeDef, type Mode } from "@/lib/categories";
import { getProduct, getRanking } from "@/lib/data";
import { rerank } from "@/lib/rank";
import { displayName } from "@/lib/format";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Alertes prix" };

type SP = Record<string, string | undefined>;

export default async function Alerts({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const productId = Number(sp.product) || undefined;
  const d = productId ? await getProduct(productId) : null;
  const cat = (sp.cat && CATEGORY_BY_ID[sp.cat]) ? sp.cat : d?.actives[0]?.category ?? "whey";
  const c = CATEGORY_BY_ID[cat];
  const modes = Object.keys(c.modes) as Mode[];
  const units = [
    ...(d ? [{ mode: "price", label: "le prix du produit (€)" }] : []),
    ...modes.map((m) => ({ mode: m, label: `le ${modeDef(cat, m).label.toLowerCase()} (${modeDef(cat, m).unit})` })),
  ];
  const defaults: Record<string, number> = {};
  if (d) {
    const r = rerank(d.rows, d.codes, { mode: c.defaultMode, allFormats: true, firstOrder: false, useCodes: true }).find((x) => x.available);
    if (r) { defaults.price = r.final; if (r.doseNow) defaults.dose = r.doseNow; if (r.kgNow) defaults.kg = r.kgNow; if (r.unitNow) defaults.unit = r.unitNow; }
  } else {
    const { rows } = await getRanking(cat, { sub: sp.sub }, { mode: c.defaultMode, allFormats: false, firstOrder: false, useCodes: true });
    const best = rows.find((x) => x.available);
    if (best) { if (best.doseNow) defaults.dose = best.doseNow; if (best.kgNow) defaults.kg = best.kgNow; if (best.unitNow) defaults.unit = best.unitNow; }
  }

  return (
    <>
      <section className="summary"><div>
        <h1>Alertes prix</h1>
        {sp.confirmed && <p className="ok">Alerte confirmée : tu recevras un e-mail dès que le prix passera sous ton seuil.</p>}
        {sp.stopped && <p className="ok">C'est noté, cette alerte est désactivée.</p>}
        {sp.invalid && <p className="err">Lien invalide ou alerte déjà désactivée.</p>}
        <p>Reçois un e-mail quand {d ? <b>{displayName(d.product.brand, d.product.name, " ")}</b> : <>le meilleur produit de <b>{c.label}</b>{sp.sub && c.subs?.[sp.sub] ? ` (${c.subs[sp.sub]})` : ""}</>} passe
          sous le prix de ton choix. Les prix sont vérifiés toutes les 4 à 8 heures.</p>
      </div></section>

      {!d && (
        <form className="controls" action="/alertes">
          <div className="row">
            <label className="ctl-label" htmlFor="cat">Catégorie</label>
            <select id="cat" className="filter" name="cat" defaultValue={cat}>
              {CATEGORIES.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
            </select>
            {c.subs && (
              <select className="filter" name="sub" defaultValue={sp.sub ?? ""} aria-label="Type">
                <option value="">Tous les types</option>
                {Object.entries(c.subs).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            )}
            <button className="btn ghost" type="submit">Choisir</button>
          </div>
        </form>
      )}

      <section className="panel">
        <AlertForm product={productId} cat={cat} sub={d ? undefined : sp.sub} units={units} defaults={defaults} />
        <p className="note-small">Le champ est pré-rempli 5 % sous le prix actuel. {d ? <Link href={`/p/${productId}`}>Retour au produit</Link> : null}</p>
      </section>
    </>
  );
}
