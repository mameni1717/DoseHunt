import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Analytics } from "@vercel/analytics/next";
import "../globals.css";
import { SITE_URL } from "@/lib/site";
import { mainCategories, vitaminsGroup } from "@/lib/categories";
import { ACTIVE_COUNTRIES, ALL_COUNTRIES, countryFromPath, href, segmentOf } from "@/lib/country";
import { t } from "@/lib/i18n";
import { rich } from "@/lib/rich";
import { alternates } from "@/lib/seo";
import { CompareBar } from "@/components/client";
import { CountryBanner, CountrySwitcher, type CountryChoice } from "@/components/CountrySwitcher";

// Un segment par pays connu ; tout autre code donne une page 404.
export const dynamicParams = false;
export function generateStaticParams() {
  return ALL_COUNTRIES.map((c) => ({ country: segmentOf(c) }));
}

type Params = Promise<{ country: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const country = countryFromPath((await params).country);
  if (!country) return {};
  const L = country.lang;
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: t(L, "common.meta.title"), template: "%s · DoseHunt" },
    alternates: alternates(country, "/"),
    openGraph: { type: "website", locale: country.ogLocale, siteName: "DoseHunt", url: `${SITE_URL}${href(country, "/")}` },
    twitter: { card: "summary" },
    verification: process.env.GOOGLE_SITE_VERIFICATION ? { google: process.env.GOOGLE_SITE_VERIFICATION } : undefined,
    description: t(L, "common.meta.description"),
  };
}

export default async function CountryLayout({ children, params }: { children: React.ReactNode; params: Params }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  const L = country.lang;
  const demo = process.env.DOSEHUNT_DEMO === "1";
  const vit = vitaminsGroup(country);
  // Pays proposés : les pays actifs, plus le pays affiché (un pays encore caché reste visible sur ses propres pages).
  const listed = ACTIVE_COUNTRIES.some((c) => c.code === country.code) ? ACTIVE_COUNTRIES : [...ACTIVE_COUNTRIES, country];
  const choices: CountryChoice[] = listed.map((c) => ({
    iso: c.code, path: c.path, flag: c.flag, name: c.name,
    suggest: t(c.lang, "common.banner.suggest", { country: c.name }),
    go: t(c.lang, "common.banner.go"), stay: t(c.lang, "common.banner.stay"),
  }));
  return (
    <html lang={L}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="wrap">
          <CountryBanner current={country.code} choices={choices.filter((c) => ACTIVE_COUNTRIES.some((a) => a.code === c.iso))} />
          <header className="top">
            <Link href={href(country, "/")} className="brand">
              <span className="wordmark">Dose<i>Hunt</i></span>
              <span className="tag">{t(L, "common.tagline")}</span>
            </Link>
            <CountrySwitcher current={country.code} choices={choices} label={t(L, "common.country.label")}
              soloTitle={t(L, "common.country.soon")} />
            <nav className="cats" aria-label={t(L, "common.nav.categories")}>
              {mainCategories(country).map((c) => (
                <Link key={c.id} href={href(country, `/c/${c.id}`)}>{c.short}</Link>
              ))}
              <Link href={href(country, "/vitamines")}>{vit.short}</Link>
              <Link href={href(country, "/comparer")} className="navtool">{t(L, "common.nav.compare")}</Link>
              <Link href={href(country, "/alertes")} className="navtool">{t(L, "common.nav.alerts")}</Link>
              <Link href={href(country, "/optimiser")} className="navtool cta">{t(L, "common.nav.optimize")}</Link>
            </nav>
          </header>
          {demo && <p className="demo-banner">{t(L, "common.demo")}</p>}
          {children}
          <CompareBar country={country.code} lang={L} prefix={country.path ? `/${country.path}` : ""}
            m={{ toCompare: t(L, "common.compareBar.toCompare"), toCompareMany: t(L, "common.compareBar.toCompareMany"),
                 pickTwo: t(L, "common.compareBar.pickTwo"), compare: t(L, "common.compareBar.compare"),
                 clear: t(L, "common.compareBar.clear"), region: t(L, "common.compareBar.region") }} />
          <footer className="foot">
            <span>{rich(L, "common.footer.ranking", { link: (c) => <Link href={href(country, "/methode")}>{c}</Link> })}</span>
            <span>{t(L, "common.footer.noAdvice")}</span>
            <span>
              <Link href={href(country, "/mentions-legales")}>{t(L, "common.footer.legal")}</Link> ·{" "}
              <Link href={href(country, "/confidentialite")}>{t(L, "common.footer.privacy")}</Link>
            </span>
          </footer>
        </div>
        <Analytics />
      </body>
    </html>
  );
}
