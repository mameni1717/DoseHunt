import { Fragment, type ReactNode } from "react";
import type { Lang } from "./country.ts";
import { t, type MessageKey, type Vars } from "./i18n.ts";

/**
 * Texte traduit avec balises : « Lis <link>notre méthode</link>. » + { link: (c) => <Link href=…>{c}</Link> }.
 * Les balises sont des noms simples (<b>, <link>, <a1>…), non imbriquées.
 */
export function rich(lang: Lang, key: MessageKey, tags: Record<string, (chunk: ReactNode) => ReactNode>, vars?: Vars): ReactNode {
  const s = t(lang, key, vars);
  const out: ReactNode[] = [];
  const re = /<(\w+)>(.*?)<\/\1>/gs;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const render = tags[m[1]];
    out.push(<Fragment key={i++}>{render ? render(m[2]) : m[2]}</Fragment>);
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push(s.slice(last));
  return <>{out}</>;
}
