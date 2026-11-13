import Link from "next/link";
import type { Category } from "@/lib/categories";
import { modeDef } from "@/lib/categories";
import { href, type Country } from "@/lib/country";
import type { Ranked } from "@/lib/rank";
import { displayName, formatNumber } from "@/lib/format";
import { t, tp } from "@/lib/i18n";

export function CategoryTile({ c, h, country }: { c: Category; h?: { count: number; best: Ranked | null }; country: Country }) {
  const L = country.lang;
  const best = h?.best;
  return (
    <Link href={href(country, `/c/${c.id}`)} className={`catcard${best ? "" : " empty"}`}>
      <h2>{c.label}</h2>
      {best ? (
        <>
          <div className="unit"><span className="from">{t(L, "category.tile.from")}</span>{formatNumber(best.value ?? 0, country, 2)}<small>{modeDef(country, c.id, c.defaultMode).unit}</small></div>
          <div className="meta">{displayName(best.brand, best.name, " ")} · {best.site_name}</div>
          <div className="meta">{tp(L, "category.tile.compared", h!.count)}</div>
        </>
      ) : (
        <div className="meta">{t(L, "category.tile.empty")}</div>
      )}
    </Link>
  );
}
