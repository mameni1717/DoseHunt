import Link from "next/link";
import { notFound } from "next/navigation";
import { mainCategories, vitaminCategories, vitaminsGroup } from "@/lib/categories";
import { countryFromPath, href } from "@/lib/country";
import { getHome, lastUpdate } from "@/lib/data";
import { ago } from "@/lib/format";
import { t, tp } from "@/lib/i18n";
import { rich } from "@/lib/rich";
import { CategoryTile } from "@/components/CategoryTiles";

export const dynamic = "force-dynamic";

export default async function Home({ params }: { params: Promise<{ country: string }> }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  const L = country.lang;
  const [home, updated] = await Promise.all([getHome(country), lastUpdate(country)]);
  const vits = vitaminCategories(country);
  const vit = vitaminsGroup(country);
  const vitCount = vits.reduce((n, c) => n + (home[c.id]?.count ?? 0), 0);
  return (
    <>
      <section className="hero">
        <h1>{rich(L, "home.hero.title", { em: (c) => <em>{c}</em> })}</h1>
        <p>{t(L, "home.hero.text", { ago: ago(updated, country) })}</p>
        <form className="search" action={href(country, "/recherche")} role="search">
          <label htmlFor="q" className="ctl-label" style={{ alignSelf: "center" }}>{t(L, "home.search.label")}</label>
          <input id="q" name="q" placeholder={t(L, "home.search.placeholder")} />
          <button type="submit">{t(L, "home.search.button")}</button>
        </form>
      </section>
      <Link href={href(country, "/optimiser")} className="opt-banner">
        <span className="opt-banner-kicker">{t(L, "home.opt.kicker")}</span>
        <strong>{t(L, "home.opt.title")}</strong>
        <span>{t(L, "home.opt.text")}</span>
        <span className="opt-banner-go">{t(L, "home.opt.go")}</span>
      </Link>
      <section className="grid" aria-label={t(L, "home.grid.label")}>
        {mainCategories(country).map((c) => <CategoryTile key={c.id} c={c} h={home[c.id]} country={country} />)}
        <Link href={href(country, "/vitamines")} className="catcard group">
          <h2>{vit.label}</h2>
          <div className="meta">{vits.map((c) => c.short).join(", ")}</div>
          <div className="meta">{tp(L, "home.grid.compared", vitCount)}</div>
        </Link>
      </section>
      <section className="notes">
        <div className="note trapnote">
          <h3>{t(L, "home.note.trap.title")}</h3>
          {t(L, "home.note.trap.text")}
        </div>
        <div className="note">
          <h3>{t(L, "home.note.honest.title")}</h3>
          {rich(L, "home.note.honest.text", { link: (c) => <Link href={href(country, "/methode")}>{c}</Link> })}
        </div>
        <div className="note">
          <h3>{t(L, "home.note.tools.title")}</h3>
          {rich(L, "home.note.tools.text", { link: (c) => <Link href={href(country, "/alertes")}>{c}</Link> })}
        </div>
      </section>
    </>
  );
}
