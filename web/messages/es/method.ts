import type fr from "../fr/method.ts";

// Textes espagnols (method) : mêmes clés que le français (vérifié par TypeScript et par le test de complétude).
const es: Record<keyof typeof fr, string> = {
  "method.meta.title": "Nuestro método",
  "method.title": "Nuestro método",
  "method.intro": "DoseHunt ordena los complementos alimenticios por su <b>precio final real por unidad de activo</b>: lo que pagas de verdad, con el código descuento aplicado, dividido entre lo que el producto contiene de verdad.",

  "method.criterion.title": "El criterio del ranking",
  "method.criterion.text": "Un único criterio: el precio comparado, del más barato al más caro. Tres formas de comparar, a tu elección:",
  "method.criterion.dose": "<b>Por dosis de activo</b>: {cur} por kg de proteína, de creatina, de colágeno o de glutamina, por 100 mg de cafeína (pre-entreno), por g de zinc o de magnesio elemental, por 100 000 UI de vitamina D, por g de vitamina C, por g de EPA + DHA.",
  "method.criterion.kg": "<b>Por kg de producto</b>: el precio por peso, como en la tienda (polvos).",
  "method.criterion.unit": "<b>Por unidad</b>: {cur} por barrita, cápsula o comprimido.",
  "method.criterion.default": "Modo por defecto: {list}.",

  "method.group.title": "Un producto, una línea",
  "method.group.text": "En una misma tienda, los sabores y formatos de un mismo producto se agrupan: solo se muestra el más barato para el modo elegido («desde»). «Todos los formatos y sabores», en «+ filtros», los muestra todos. Los productos agotados se ocultan por defecto.",

  "method.calc.title": "El cálculo",
  "method.calc.final": "Precio final = precio mostrado − descuento del mejor código aplicable",
  "method.calc.compared": "Precio comparado = precio final ÷ cantidad de activo, peso o número de unidades del envase completo",
  "method.calc.text": "El cálculo se hace sobre el envase completo, nunca sobre la dosis declarada. Se muestra entero debajo de cada oferta («Ver el cálculo»). Los gastos de envío todavía no se tienen en cuenta.",

  "method.real.title": "El contenido real",
  "method.real.text": "Solo cuenta la cantidad de activo que aparece en la tabla nutricional o en la composición. «Gluconato de zinc 120 mg» es el peso de la sal: el comprimido solo aporta 15 mg de zinc. Un contenido fuera del rango esperado (por ejemplo 900 mg de zinc por cápsula) lo revisa una persona antes de publicarse. Un contenido supuesto se indica como tal.",
  "method.real.combined": "Un producto que aporta varios activos (whey + colágeno, zinc + magnesio) aparece en cada lista correspondiente, con su precio completo atribuido al activo de esa lista y la etiqueta «producto combinado».",
  "method.real.claims": "«Fabricado en España», «sin lactosa», «sin edulcorantes» o el origen de la leche solo se muestran si la ficha de la tienda lo dice con todas las letras, o si su lista de ingredientes lo demuestra. «Diseñado en España» o «marca española» no bastan. Una ficha que no dice nada queda fuera del filtro correspondiente.",

  "method.codes.title": "Los códigos descuento",
  "method.codes.text": "El mejor código válido se aplica automáticamente, aunque no le reporte nada a DoseHunt. Cada código se guarda con sus condiciones (descuento, tramos, pedido mínimo, primer pedido, fecha de fin) y la fecha de su última comprobación. Su fiabilidad baja con el tiempo y con los avisos de «ya no funciona»; por debajo de cierto umbral, se sigue mostrando pero ya no entra en el precio. Los códigos de «primer pedido» están excluidos por defecto. El precio sin código siempre está visible.",

  "method.data.title": "De dónde salen los datos",
  "method.data.text": "Los precios y contenidos se recogen automáticamente en las tiendas online: cada 4 horas para los 50 mejores productos de cada categoría, cada 8 horas para todos los demás y para los códigos descuento que muestran las tiendas. La fecha de la última actualización aparece debajo de cada oferta. Recogemos datos objetivos (precios, formatos, contenidos, ingredientes, valores nutricionales, nota media de las opiniones); la foto se muestra desde la web de la tienda.",

  "method.neutral.title": "Neutralidad y remuneración",
  "method.neutral.paid": "Ninguna posición de pago en el ranking: una tienda no puede comprar un puesto mejor.",
  "method.neutral.nonAffiliated": "Las tiendas no afiliadas aparecen exactamente igual que las demás.",
  "method.neutral.affiliation": "DoseHunt se financia con la afiliación: cuando compras después de hacer clic en «Ver la oferta», la tienda puede pagarnos una comisión, sin coste extra para ti. Estos enlaces están señalados (<code>rel=\"sponsored\"</code>).",
  "method.neutral.partners": "Pueden aparecer códigos de colaboración negociados con marcas; se ordenan con la misma regla.",

  "method.not.title": "Lo que DoseHunt no hace",
  "method.not.text": "DoseHunt compara precios. No da ningún consejo de dosis ni opinión médica, y no comprueba la conformidad normativa de los productos: un producto que se puede enviar a España se considera vendido legalmente.",

  "method.error.title": "¿Un error?",
  "method.error.text": "Un precio, un contenido o un código incorrecto: escríbenos a contact@dosehunt.fr, o avisa debajo de la oferta si un código ya no funciona. Lo corregimos rápido, porque basta un solo dato erróneo para perder tu confianza.",
};
export default es;
