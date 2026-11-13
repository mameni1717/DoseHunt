// Libellés des catégories (français, référence). {cur} = symbole de la devise du pays (€ en France).
const fr = {
  "cat.kg.label": "Prix par kg de produit", "cat.kg.unit": "{cur}/kg", "cat.kg.short": "{cur}/kg produit",
  "cat.unitMode.label": "Prix par gélule ou comprimé", "cat.unitMode.unit": "{cur}/unité", "cat.unitMode.short": "{cur}/unité",

  "cat.whey.label": "Protéines en poudre", "cat.whey.short": "Whey", "cat.whey.activeName": "protéine", "cat.whey.activeShare": "Taux de protéine",
  "cat.whey.dose.label": "Prix par kg de protéine", "cat.whey.dose.unit": "{cur}/kg prot.", "cat.whey.dose.short": "{cur}/kg protéine",
  "cat.whey.sub.classique": "Whey classique", "cat.whey.sub.isolate": "Whey isolate", "cat.whey.sub.clear": "Clear whey",
  "cat.whey.sub.caseine": "Caséine", "cat.whey.sub.vegane": "Protéine végétale",

  "cat.creatine.label": "Créatine", "cat.creatine.short": "Créatine", "cat.creatine.activeName": "créatine", "cat.creatine.activeShare": "Taux de créatine",
  "cat.creatine.dose.label": "Prix par kg de créatine", "cat.creatine.dose.unit": "{cur}/kg créat.", "cat.creatine.dose.short": "{cur}/kg créatine",

  "cat.preworkout.label": "Pré-workout", "cat.preworkout.short": "Pré-workout", "cat.preworkout.activeName": "portion", "cat.preworkout.activeShare": "Portion recommandée",
  "cat.preworkout.dose.label": "Prix par portion", "cat.preworkout.dose.unit": "{cur}/portion", "cat.preworkout.dose.short": "{cur}/portion",

  "cat.collagene.label": "Collagène", "cat.collagene.short": "Collagène", "cat.collagene.activeName": "collagène", "cat.collagene.activeShare": "Taux de collagène",
  "cat.collagene.dose.label": "Prix par kg de collagène", "cat.collagene.dose.unit": "{cur}/kg coll.", "cat.collagene.dose.short": "{cur}/kg collagène",

  "cat.barres.label": "Barres protéinées", "cat.barres.short": "Barres", "cat.barres.activeName": "protéine", "cat.barres.activeShare": "Protéines par barre",
  "cat.barres.unit.label": "Prix par barre", "cat.barres.unit.unit": "{cur}/barre", "cat.barres.unit.short": "{cur}/barre",
  "cat.barres.dose.label": "Prix pour 100 g de protéine", "cat.barres.dose.unit": "{cur}/100 g prot.", "cat.barres.dose.short": "{cur}/100 g protéine",

  "cat.zinc.label": "Zinc", "cat.zinc.short": "Zinc", "cat.zinc.activeName": "zinc", "cat.zinc.activeShare": "Zinc par unité",
  "cat.zinc.dose.label": "Prix par g de zinc réel", "cat.zinc.dose.unit": "{cur}/g de zinc", "cat.zinc.dose.short": "{cur}/g zinc",

  "cat.magnesium.label": "Magnésium", "cat.magnesium.short": "Magnésium", "cat.magnesium.activeName": "magnésium", "cat.magnesium.activeShare": "Magnésium par unité",
  "cat.magnesium.dose.label": "Prix par g de magnésium réel", "cat.magnesium.dose.unit": "{cur}/g de Mg", "cat.magnesium.dose.short": "{cur}/g magnésium",

  "cat.vitamine_d.label": "Vitamine D", "cat.vitamine_d.short": "Vitamine D", "cat.vitamine_d.activeName": "vitamine D", "cat.vitamine_d.activeShare": "Vitamine D par unité",
  "cat.vitamine_d.dose.label": "Prix pour 100 000 UI", "cat.vitamine_d.dose.unit": "{cur}/100 000 UI", "cat.vitamine_d.dose.short": "{cur}/100 000 UI",
  "cat.vitamine_d.unit.label": "Prix par gélule ou goutte", "cat.vitamine_d.unit.unit": "{cur}/unité", "cat.vitamine_d.unit.short": "{cur}/unité",

  "cat.vitamine_c.label": "Vitamine C", "cat.vitamine_c.short": "Vitamine C", "cat.vitamine_c.activeName": "vitamine C", "cat.vitamine_c.activeShare": "Vitamine C par unité",
  "cat.vitamine_c.dose.label": "Prix par g de vitamine C", "cat.vitamine_c.dose.unit": "{cur}/g vit. C", "cat.vitamine_c.dose.short": "{cur}/g vitamine C",

  "cat.omega3.label": "Oméga-3", "cat.omega3.short": "Oméga-3", "cat.omega3.activeName": "EPA + DHA", "cat.omega3.activeShare": "EPA + DHA par capsule",
  "cat.omega3.dose.label": "Prix par g d'EPA + DHA", "cat.omega3.dose.unit": "{cur}/g EPA+DHA", "cat.omega3.dose.short": "{cur}/g EPA + DHA",
  "cat.omega3.unit.label": "Prix par capsule", "cat.omega3.unit.unit": "{cur}/capsule", "cat.omega3.unit.short": "{cur}/capsule",

  "cat.glutamine.label": "Glutamine", "cat.glutamine.short": "Glutamine", "cat.glutamine.activeName": "glutamine", "cat.glutamine.activeShare": "Taux de glutamine",
  "cat.glutamine.dose.label": "Prix par kg de glutamine", "cat.glutamine.dose.unit": "{cur}/kg glut.", "cat.glutamine.dose.short": "{cur}/kg glutamine",

  "cat.vitamins.label": "Vitamines & autres", "cat.vitamins.short": "Vitamines & autres",

  "cat.milk.FR": "France", "cat.milk.IE": "Irlande", "cat.milk.NL": "Pays-Bas", "cat.milk.DE": "Allemagne",
  "cat.milk.NZ": "Nouvelle-Zélande", "cat.milk.EU": "Union européenne", "cat.milk.ES": "Espagne",

  "cat.active.unknown": "teneur inconnue", "cat.active.perServing": "{n} g par portion", "cat.active.percent": "{n} %",
  "cat.active.per100": "{n} {unit} pour 100 g", "cat.active.perUnit": "{n} {unit} de {active} par unité", "cat.active.perUnitShort": "{n} {unit} par unité",
  "cat.active.fallback": "actif",
} as const;
export default fr;
