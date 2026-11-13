import type fr from "../fr/cats.ts";

// Nombres de categorías en España. {cur} = símbolo de la moneda del país.
const es: Record<keyof typeof fr, string> = {
  "cat.kg.label": "Precio por kg de producto", "cat.kg.unit": "{cur}/kg", "cat.kg.short": "{cur}/kg producto",
  "cat.unitMode.label": "Precio por cápsula o comprimido", "cat.unitMode.unit": "{cur}/unidad", "cat.unitMode.short": "{cur}/unidad",

  "cat.whey.label": "Proteína en polvo", "cat.whey.short": "Proteína", "cat.whey.activeName": "proteína", "cat.whey.activeShare": "Proteína",
  "cat.whey.dose.label": "Precio por kg de proteína", "cat.whey.dose.unit": "{cur}/kg prot.", "cat.whey.dose.short": "{cur}/kg proteína",
  "cat.whey.sub.classique": "Whey concentrada", "cat.whey.sub.isolate": "Whey isolate", "cat.whey.sub.clear": "Clear whey",
  "cat.whey.sub.caseine": "Caseína", "cat.whey.sub.vegane": "Proteína vegetal",

  "cat.creatine.label": "Creatina", "cat.creatine.short": "Creatina", "cat.creatine.activeName": "creatina", "cat.creatine.activeShare": "Creatina",
  "cat.creatine.dose.label": "Precio por kg de creatina", "cat.creatine.dose.unit": "{cur}/kg creat.", "cat.creatine.dose.short": "{cur}/kg creatina",

  "cat.preworkout.label": "Pre-entreno", "cat.preworkout.short": "Pre-entreno", "cat.preworkout.activeName": "dosis", "cat.preworkout.activeShare": "Dosis recomendada",
  "cat.preworkout.dose.label": "Precio por dosis", "cat.preworkout.dose.unit": "{cur}/dosis", "cat.preworkout.dose.short": "{cur}/dosis",

  "cat.collagene.label": "Colágeno", "cat.collagene.short": "Colágeno", "cat.collagene.activeName": "colágeno", "cat.collagene.activeShare": "Colágeno",
  "cat.collagene.dose.label": "Precio por kg de colágeno", "cat.collagene.dose.unit": "{cur}/kg colág.", "cat.collagene.dose.short": "{cur}/kg colágeno",

  "cat.barres.label": "Barritas de proteína", "cat.barres.short": "Barritas", "cat.barres.activeName": "proteína", "cat.barres.activeShare": "Proteína por barrita",
  "cat.barres.unit.label": "Precio por barrita", "cat.barres.unit.unit": "{cur}/barrita", "cat.barres.unit.short": "{cur}/barrita",
  "cat.barres.dose.label": "Precio por 100 g de proteína", "cat.barres.dose.unit": "{cur}/100 g prot.", "cat.barres.dose.short": "{cur}/100 g proteína",

  "cat.zinc.label": "Zinc", "cat.zinc.short": "Zinc", "cat.zinc.activeName": "zinc", "cat.zinc.activeShare": "Zinc por unidad",
  "cat.zinc.dose.label": "Precio por g de zinc elemental", "cat.zinc.dose.unit": "{cur}/g de zinc", "cat.zinc.dose.short": "{cur}/g zinc",

  "cat.magnesium.label": "Magnesio", "cat.magnesium.short": "Magnesio", "cat.magnesium.activeName": "magnesio", "cat.magnesium.activeShare": "Magnesio por unidad",
  "cat.magnesium.dose.label": "Precio por g de magnesio elemental", "cat.magnesium.dose.unit": "{cur}/g de Mg", "cat.magnesium.dose.short": "{cur}/g magnesio",

  "cat.vitamine_d.label": "Vitamina D", "cat.vitamine_d.short": "Vitamina D", "cat.vitamine_d.activeName": "vitamina D", "cat.vitamine_d.activeShare": "Vitamina D por unidad",
  "cat.vitamine_d.dose.label": "Precio por 100 000 UI", "cat.vitamine_d.dose.unit": "{cur}/100 000 UI", "cat.vitamine_d.dose.short": "{cur}/100 000 UI",
  "cat.vitamine_d.unit.label": "Precio por cápsula o gota", "cat.vitamine_d.unit.unit": "{cur}/unidad", "cat.vitamine_d.unit.short": "{cur}/unidad",

  "cat.vitamine_c.label": "Vitamina C", "cat.vitamine_c.short": "Vitamina C", "cat.vitamine_c.activeName": "vitamina C", "cat.vitamine_c.activeShare": "Vitamina C por unidad",
  "cat.vitamine_c.dose.label": "Precio por g de vitamina C", "cat.vitamine_c.dose.unit": "{cur}/g vit. C", "cat.vitamine_c.dose.short": "{cur}/g vitamina C",

  "cat.omega3.label": "Omega 3", "cat.omega3.short": "Omega 3", "cat.omega3.activeName": "EPA + DHA", "cat.omega3.activeShare": "EPA + DHA por perla",
  "cat.omega3.dose.label": "Precio por g de EPA + DHA", "cat.omega3.dose.unit": "{cur}/g EPA+DHA", "cat.omega3.dose.short": "{cur}/g EPA + DHA",
  "cat.omega3.unit.label": "Precio por perla", "cat.omega3.unit.unit": "{cur}/perla", "cat.omega3.unit.short": "{cur}/perla",

  "cat.glutamine.label": "Glutamina", "cat.glutamine.short": "Glutamina", "cat.glutamine.activeName": "glutamina", "cat.glutamine.activeShare": "Glutamina",
  "cat.glutamine.dose.label": "Precio por kg de glutamina", "cat.glutamine.dose.unit": "{cur}/kg glut.", "cat.glutamine.dose.short": "{cur}/kg glutamina",

  "cat.vitamins.label": "Vitaminas y más", "cat.vitamins.short": "Vitaminas y más",

  "cat.milk.FR": "Francia", "cat.milk.IE": "Irlanda", "cat.milk.NL": "Países Bajos", "cat.milk.DE": "Alemania",
  "cat.milk.NZ": "Nueva Zelanda", "cat.milk.EU": "Unión Europea", "cat.milk.ES": "España",

  "cat.active.unknown": "cantidad desconocida", "cat.active.perServing": "{n} g por dosis", "cat.active.percent": "{n} %",
  "cat.active.per100": "{n} {unit} por 100 g", "cat.active.perUnit": "{n} {unit} de {active} por unidad", "cat.active.perUnitShort": "{n} {unit} por unidad",
  "cat.active.fallback": "activo",
};
export default es;
