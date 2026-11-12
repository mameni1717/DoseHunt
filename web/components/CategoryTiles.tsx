import Link from "next/link";
import type { Category } from "@/lib/categories";
import { modeDef } from "@/lib/categories";
import type { Ranked } from "@/lib/rank";
import { displayName, num } from "@/lib/format";

export function CategoryTile({ c, h }: { c: Category; h?: { count: number; best: Ranked | null } }) {
  const best = h?.best;
  return (
    <Link href={`/c/${c.id}`} className={`catcard${best ? "" : " empty"}`}>
      <h2>{c.label}</h2>
      {best ? (
        <>
          <div className="unit"><span className="from">À partir de</span>{num(best.value ?? 0, 2)}<small>{modeDef(c.id, c.defaultMode).unit}</small></div>
          <div className="meta">{displayName(best.brand, best.name, " ")} · {best.site_name}</div>
          <div className="meta">{h!.count} produit{h!.count > 1 ? "s" : ""} comparé{h!.count > 1 ? "s" : ""}</div>
        </>
      ) : (
        <div className="meta">Pas encore d'offre relevée</div>
      )}
    </Link>
  );
}
