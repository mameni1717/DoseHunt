import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { countryFromPath } from "@/lib/country";
import { t } from "@/lib/i18n";
import { alternates } from "@/lib/seo";
import { MentionsFr } from "@/components/legal/MentionsFr";
import { MentionsEs } from "@/components/legal/MentionsEs";

type Params = Promise<{ country: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const country = countryFromPath((await params).country);
  if (!country) return {};
  return { title: t(country.lang, "legal.mentions.title"), alternates: alternates(country, "/mentions-legales") };
}

// Texte juridique propre au droit de chaque pays : un composant par langue.
export default async function MentionsLegales({ params }: { params: Params }) {
  const country = countryFromPath((await params).country);
  if (!country) notFound();
  return country.lang === "es" ? <MentionsEs country={country} /> : <MentionsFr country={country} />;
}
