import type { Metadata } from "next";
import Link from "next/link";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";
import { SITE_URL } from "@/lib/site";
import { MAIN_CATEGORIES, VITAMINS_GROUP } from "@/lib/categories";
import { CompareBar } from "@/components/client";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "DoseHunt · Comparateur de whey, créatine et compléments au vrai prix", template: "%s · DoseHunt" },
  alternates: { canonical: "/" },
  openGraph: { type: "website", locale: "fr_FR", siteName: "DoseHunt", url: SITE_URL },
  twitter: { card: "summary" },
  verification: process.env.GOOGLE_SITE_VERIFICATION ? { google: process.env.GOOGLE_SITE_VERIFICATION } : undefined,
  description:
    "Comparateur indépendant : whey, créatine, pré-workout, collagène, barres, vitamines et minéraux classés au prix réel par gramme d'actif, code promo compris, chez les marchands français.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const demo = process.env.DOSEHUNT_DEMO === "1";
  return (
    <html lang="fr">
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
          <header className="top">
            <Link href="/" className="brand">
              <span className="wordmark">Dose<i>Hunt</i></span>
              <span className="tag">Le vrai prix de ce que tu avales.</span>
            </Link>
            <span className="country" title="D'autres pays arriveront plus tard">France</span>
            <nav className="cats" aria-label="Catégories">
              {MAIN_CATEGORIES.map((c) => (
                <Link key={c.id} href={`/c/${c.id}`}>{c.short}</Link>
              ))}
              <Link href="/vitamines">{VITAMINS_GROUP.short}</Link>
              <Link href="/comparer" className="navtool">Comparer</Link>
              <Link href="/alertes" className="navtool">Alertes prix</Link>
            </nav>
          </header>
          {demo && (
            <p className="demo-banner">
              Données de démonstration : relevé manuel du 11/11/2026 sur 11 sites (whey et zinc). Les collectes
              automatiques remplaceront ces données.
            </p>
          )}
          {children}
          <CompareBar />
          <footer className="foot">
            <span>
              Classement par prix final réel uniquement, aucun emplacement payant. Certains liens sont affiliés :{" "}
              <Link href="/methode">notre méthode</Link>.
            </span>
            <span>DoseHunt compare des prix, il ne donne pas de conseil de dosage.</span>
            <span>
              <Link href="/mentions-legales">Mentions légales</Link> · <Link href="/confidentialite">Confidentialité</Link>
            </span>
          </footer>
        </div>
        <Analytics />
      </body>
    </html>
  );
}
