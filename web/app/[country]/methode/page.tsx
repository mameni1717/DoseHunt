import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { categories } from "@/lib/categories";
import { countryFromPath } from "@/lib/country";
import { t, type MessageKey } from "@/lib/i18n";
import { rich } from "@/lib/rich";
import { alternates } from "@/lib/seo";

type Params = Promise<{ country: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const country = countryFromPath((await params).country);
  if (!country) return {};
  return { title: t(country.lang, "method.meta.title"), alternates: alternates(country, "/methode") };
}

// Page exigée par les règles de loyauté des plateformes (Code de la consommation, art. L111-7 et D111-7) :
// critères de classement, existence de liens rémunérés, référencement payant.
export default async function Methode({ params }: { params: Params }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  const L = country.lang;
  const cur = { cur: country.symbol };
  const tags = { b: (c: ReactNode) => <b>{c}</b>, code: (c: ReactNode) => <code>{c}</code> };
  const r = (key: MessageKey, vars?: Record<string, string>) => rich(L, key, tags, vars);
  const lower = (s: string) => s.toLocaleLowerCase(country.locale);
  const defaults = categories(country).map((c) => `${lower(c.label)} (${lower(c.modes[c.defaultMode]!.label)})`).join(", ");
  return (
    <article className="prose">
      <h1>{t(L, "method.title")}</h1>
      <p>{r("method.intro")}</p>

      <h2>{t(L, "method.criterion.title")}</h2>
      <p>{t(L, "method.criterion.text")}</p>
      <ul>
        <li>{r("method.criterion.dose", cur)}</li>
        <li>{r("method.criterion.kg")}</li>
        <li>{r("method.criterion.unit", cur)}</li>
      </ul>
      <p>{t(L, "method.criterion.default", { list: defaults })}</p>

      <h2>{t(L, "method.group.title")}</h2>
      <p>{t(L, "method.group.text")}</p>

      <h2>{t(L, "method.calc.title")}</h2>
      <p><code>{t(L, "method.calc.final")}</code></p>
      <p><code>{t(L, "method.calc.compared")}</code></p>
      <p>{t(L, "method.calc.text")}</p>

      <h2>{t(L, "method.real.title")}</h2>
      <p>{t(L, "method.real.text")}</p>
      <p>{t(L, "method.real.combined")}</p>
      <p>{t(L, "method.real.claims")}</p>

      <h2>{t(L, "method.codes.title")}</h2>
      <p>{t(L, "method.codes.text")}</p>

      <h2>{t(L, "method.data.title")}</h2>
      <p>{t(L, "method.data.text")}</p>

      <h2>{t(L, "method.neutral.title")}</h2>
      <ul>
        <li>{t(L, "method.neutral.paid")}</li>
        <li>{t(L, "method.neutral.nonAffiliated")}</li>
        <li>{r("method.neutral.affiliation")}</li>
        <li>{t(L, "method.neutral.partners")}</li>
      </ul>

      <h2>{t(L, "method.not.title")}</h2>
      <p>{t(L, "method.not.text")}</p>

      <h2>{t(L, "method.error.title")}</h2>
      <p>{t(L, "method.error.text")}</p>
    </article>
  );
}
