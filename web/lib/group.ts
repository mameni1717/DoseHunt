// Regroupement des arômes : « EAFIT Pure Whey Fraise 850g » et « Pure Whey Myrtille 750g » sont un même produit
// chez le même marchand. On retire du nom la marque, les formats et les mots d'arôme ; ce qui reste identifie le produit.

const STATIC_FLAVOURS = `nature naturel neutre aromatise aromatisee non sans arome saveur saveurs gout gouts flavour flavor unflavoured unflavored
chocolat chocolate choco cacao cocoa noir blanc white dark lait milk vanille vanilla vanilla bourbon fraise strawberry framboise raspberry
myrtille myrtilles blueberry banane banana cafe coffee cappuccino latte mocha caramel sale salted biscuit biscuitee cookie cookies cream creme
noisette hazelnut cacahuete cacahuetes peanut butter beurre pistache pistachio coco coconut mangue mango peche peach abricot citron lemon lime
orange pamplemousse cerise cherry pomme apple poire fruits fruit rouges rouge exotique tropical passion ananas pineapple pasteque watermelon
cola menthe mint the tea glace iced intense gourmand gourmande gourmet delice speculoos brownie cheesecake tiramisu praline pecan amande almond
cannelle cinnamon miel honey yaourt yoghurt yogurt stracciatella oreo fudge milkshake punch berry berries cassis blackcurrant raisin grape
matcha creamy smooth double rich delicious original classique classic et and au aux a la le de du avec with alt retail new nouveau nouvelle`;

// Mots qui distinguent de vrais produits différents : jamais retirés, même s'ils apparaissent dans un arôme.
const PROTECTED = new Set(`whey isolate isolat iso clear native natif hydro hydrolysat hydrolyse concentre concentree vegan vegane vegetale
pois riz soja pea rice soy proteine proteines protein zero gold pure elite pro creatine creapure monohydrate micronisee collagene collagen
peptides peptan naticol marin bovin barre barres bar bars crispy crunchy zinc magnesium bisglycinate citrate vitamine d3 omega epa dha krill
gelules capsules comprimes poudre powder impact advanced premium ultra max mega light`.split(/\s+/));

export function norm(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/&amp;|&#x27;|&#39;/g, " ");
}

export function brandKey(brand: string | null): string {
  return norm(brand ?? "").replace(/[^a-z0-9]/g, "");
}

export function flavourWords(flavours: (string | null)[]): Set<string> {
  const out = new Set(STATIC_FLAVOURS.split(/\s+/).filter(Boolean));
  for (const f of flavours) {
    if (!f) continue;
    for (const w of norm(f).split(/[^a-z]+/)) if (w.length > 2 && !PROTECTED.has(w)) out.add(w);
  }
  return out;
}

const SIZE = /\b\d+(?:[.,]\d+)?\s*(?:kg|g|gr|grammes?|ml|l|lbs?|portions?|doses?|servings?|g[ée]lules?|capsules?|caps|comprim[ée]s?|tabs|sachets?|barres?|x)\b|\b\d+\s*x\s*\d+\s*g?\b|\(\s*\)/g;

export function coreName(name: string, brand: string | null, flavours: Set<string>): string {
  let s = norm(name);
  const b = norm(brand ?? "");
  if (b) for (const w of b.split(/\s+/)) if (w) s = s.replace(new RegExp(`\\b${w.replace(/[^a-z0-9]/g, "")}\\b`, "g"), " ");
  s = s.replace(SIZE, " ");
  return s.split(/[^a-z0-9%]+/).filter((w) => w && !/^\d+$/.test(w) && (PROTECTED.has(w) || !flavours.has(w))).join(" ");
}

export function groupKey(r: { site_id: string; category: string; subcategory: string | null; brand: string | null; name: string },
                         flavours: Set<string>): string {
  return [r.site_id, r.category, r.subcategory ?? "", brandKey(r.brand), coreName(r.name, r.brand, flavours)].join("|");
}
