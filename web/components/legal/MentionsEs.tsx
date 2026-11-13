import Link from "next/link";
import { href, type Country } from "@/lib/country";

// Aviso legal, version espagnole (Ley 34/2002, LSSI-CE, art. 10). Données d'éditeur identiques à la version française.
export function MentionsEs({ country }: { country: Country }) {
  return (
    <article className="prose">
      <h1>Aviso legal</h1>
      <p>
        En cumplimiento del artículo 10 de la Ley 34/2002, de 11 de julio, de Servicios de la Sociedad de la Información
        y de Comercio Electrónico (LSSI-CE), estos son los datos del titular de este sitio web.
      </p>

      <h2>Titular del sitio web</h2>
      <p>
        DoseHunt, sitio web editado a título personal por Marc Duris, 34 place de Roche Noire, 73450 Valmeinier, Francia.<br />
        Contacto: mameni1717@gmail.com<br />
        Responsable de la publicación: Marc Duris.
      </p>

      <h2>Alojamiento</h2>
      <p>
        El sitio está alojado por Vercel Inc., 440 N Barranca Ave #4133, Covina, CA 91723, Estados Unidos (vercel.com).
        Los datos se almacenan en una base de datos Neon (neon.tech).
      </p>

      <h2>Naturaleza del sitio y enlaces de afiliación</h2>
      <p>
        DoseHunt es un comparador de precios de complementos alimenticios. El sitio no vende ningún producto. Algunos
        enlaces a las tiendas pueden ser enlaces de afiliación: si compras después de hacer clic, DoseHunt puede recibir
        una comisión, sin coste extra para ti. El ranking depende solo del precio comparado; ninguna tienda puede pagar
        para aparecer mejor posicionada (consulta <Link href={href(country, "/methode")}>nuestro método</Link>).
      </p>

      <h2>Contenido y responsabilidad</h2>
      <p>
        Los precios, contenidos y códigos descuento se recogen automáticamente en las tiendas online y pueden cambiar en
        cualquier momento: comprueba siempre el precio final en la web de la tienda antes de comprar. DoseHunt no da
        ningún consejo médico ni de dosis; si tienes dudas, consulta a un profesional sanitario.
      </p>

      <h2>Propiedad intelectual</h2>
      <p>
        La estructura, los textos y el código del sitio son propiedad del titular. Las marcas y nombres de productos
        mencionados pertenecen a sus respectivos propietarios.
      </p>

      <h2>Datos personales</h2>
      <p>Consulta la <Link href={href(country, "/confidentialite")}>política de privacidad</Link>.</p>
    </article>
  );
}
