import { q } from "./db.ts";
import { COUNTRIES, DEFAULT_COUNTRY, countryByIso, href, type Country } from "./country.ts";
import { t } from "./i18n.ts";

// Table créée à la demande : elle appartient au site (les inscrits), jamais remplacée par l'envoi des collectes.
let ready: Promise<unknown> | null = null;
export function ensureAlertsTable() {
  ready ??= q(`create table if not exists price_alerts (
      id serial primary key,
      email varchar(254) not null,
      product_id integer,
      category varchar(40) not null,
      subcategory varchar(40),
      mode varchar(10) not null default 'dose',
      threshold double precision not null,
      country varchar(2) not null default 'FR',
      token varchar(64) not null unique,
      confirmed boolean not null default false,
      active boolean not null default true,
      confirm_sent_at timestamptz,
      last_notified_at timestamptz,
      last_value double precision,
      created_at timestamptz not null default now())`);
  return ready;
}

export async function sendMail(to: string, subject: string, html: string): Promise<boolean> {
  const key = process.env.RESEND_API_KEY;
  if (!key) return false;                                  // e-mails pas encore branchés : la collecte enverra plus tard
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({ from: process.env.ALERT_FROM || "DoseHunt <alertes@dosehunt.com>", to, subject, html }),
  });
  return r.ok;
}

export function siteUrl(): string {
  return (process.env.SITE_URL || "https://dosehunt.com").replace(/\/$/, "");
}

/** Pays enregistré avec l'alerte (colonne country) ; France si inconnu. */
export function alertCountry(iso: string | null | undefined): Country {
  return countryByIso(iso) ?? COUNTRIES[DEFAULT_COUNTRY];
}

/** Page des alertes dans la version du pays, avec un paramètre d'état (?confirmed=1…). */
export function alertsPage(country: Country, query: string): string {
  return `${siteUrl()}${href(country, "/alertes")}?${query}`;
}

/** E-mail de confirmation dans la langue du pays de l'alerte. */
export function confirmMail(country: Country, link: string): { subject: string; html: string } {
  const L = country.lang;
  const activate = t(L, "alerts.mail.activate").replace(/<link>(.*?)<\/link>/, (_, c: string) => `<a href="${link}">${c}</a>`);
  return {
    subject: t(L, "alerts.mail.subject"),
    html: `<p>${t(L, "alerts.mail.hello")}</p><p>${activate}</p>
     <p>${t(L, "alerts.mail.ignore")}</p>`,
  };
}
