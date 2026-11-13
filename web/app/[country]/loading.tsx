"use client";

import { useParams } from "next/navigation";
import fr from "@/messages/fr/common";
import es from "@/messages/es/common";

// loading.tsx ne reçoit pas les paramètres : le pays est lu dans l'adresse, côté navigateur.
const TEXT: Record<string, string> = { fr: fr["common.loading"], es: es["common.loading"] };

export default function Loading() {
  const { country } = useParams<{ country: string }>();
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" /> {TEXT[country] ?? TEXT.fr}
    </div>
  );
}
