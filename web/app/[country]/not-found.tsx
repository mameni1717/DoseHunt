"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import fr from "@/messages/fr/common";
import es from "@/messages/es/common";

// not-found.tsx ne reçoit pas les paramètres : le pays est lu dans l'adresse.
const TEXT: Record<string, { text: string; home: string; href: string }> = {
  fr: { text: fr["common.notFound.text"], home: fr["common.notFound.home"], href: "/" },
  es: { text: es["common.notFound.text"], home: es["common.notFound.home"], href: "/es" },
};

export default function NotFound() {
  const { country } = useParams<{ country: string }>() ?? {};
  const m = TEXT[country ?? "fr"] ?? TEXT.fr;
  return (
    <section className="empty">
      <p>{m.text}</p>
      <p><Link href={m.href}>{m.home}</Link></p>
    </section>
  );
}
