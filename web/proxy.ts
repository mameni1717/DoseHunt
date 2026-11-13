import { NextResponse, type NextRequest } from "next/server";
import { ALL_COUNTRIES, ROOT_SEGMENT } from "./lib/country.ts";

// Routage par pays (fichier d'interception des requêtes de Next 16) :
// - /es, /es/... (code de chemin connu) : servi tel quel par app/[country]/ ;
// - /fr, /fr/... : redirection 308 vers l'adresse sans préfixe (une seule adresse par page française) ;
// - toute autre page : réécrite en interne vers /fr/... ; l'adresse affichée ne change pas.
// Aucune décision selon le visiteur (ni pays détecté, ni cookie) : les pages restent les mêmes pour tous, donc
// en cache. Le bandeau de suggestion de pays est calculé côté navigateur.

const PREFIXES = new Set(ALL_COUNTRIES.map((c) => c.path).filter(Boolean));

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const first = pathname.split("/")[1]?.toLowerCase() ?? "";
  if (PREFIXES.has(first)) return NextResponse.next();
  if (first === ROOT_SEGMENT) {
    const rest = pathname.slice(ROOT_SEGMENT.length + 1) || "/";
    const url = req.nextUrl.clone();
    url.pathname = rest;
    url.search = search;
    return NextResponse.redirect(url, 308);
  }
  const url = req.nextUrl.clone();
  url.pathname = `/${ROOT_SEGMENT}${pathname === "/" ? "" : pathname}`;
  return NextResponse.rewrite(url);
}

export const config = {
  // Hors réécriture : API, redirection marchand, fichiers de Next, robots, sitemaps, favicon et fichiers statiques.
  matcher: ["/((?!api/|api$|go/|_next/|robots\\.txt|sitemap.*\\.xml|favicon|.*\\.[a-zA-Z0-9]{2,5}$).*)"],
};
