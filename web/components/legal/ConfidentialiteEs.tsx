import Link from "next/link";
import { href, type Country } from "@/lib/country";

// Política de privacidad, version espagnole (RGPD + Ley Orgánica 3/2018, LOPDGDD ; cookies : LSSI-CE art. 22.2 ;
// autorité : AEPD). Mêmes traitements que la version française.
export function ConfidentialiteEs({ country }: { country: Country }) {
  return (
    <article className="prose">
      <h1>Política de privacidad</h1>
      <p>
        DoseHunt recoge los mínimos datos posibles. El sitio no utiliza ninguna cookie de seguimiento ni de publicidad,
        y no pide crear ninguna cuenta. Esta política se rige por el Reglamento (UE) 2016/679 (RGPD) y por la Ley
        Orgánica 3/2018, de Protección de Datos Personales y garantía de los derechos digitales (LOPDGDD).
      </p>

      <h2>Responsable del tratamiento</h2>
      <p>El titular del sitio (consulta el <Link href={href(country, "/mentions-legales")}>aviso legal</Link>). Contacto: mameni1717@gmail.com.</p>

      <h2>Datos que tratamos</h2>
      <ul>
        <li>
          <b>Medición de audiencia</b>: usamos Vercel Analytics, que cuenta las visitas sin cookies y sin identificar a
          las personas. Base jurídica: interés legítimo (medir el tráfico del sitio).
        </li>
        <li>
          <b>Clics hacia las tiendas</b>: registramos qué oferta se ha pulsado, cuándo y el código descuento, si lo hay.
          No se guarda ni la dirección IP ni ninguna cookie.
        </li>
        <li>
          <b>Alertas de precio</b>: si creas una alerta, guardamos tu dirección de e-mail, tu país y los criterios de la
          alerta hasta que la elimines. Tu dirección solo sirve para enviarte esa alerta (e-mail de confirmación y
          después las alertas). Cada mensaje incluye un enlace para darte de baja. Base jurídica: tu consentimiento,
          confirmado por e-mail. Los e-mails los envía Resend.
        </li>
        <li>
          <b>Votos sobre los códigos descuento</b>: para evitar votos duplicados, calculamos una huella irreversible
          (dirección IP, navegador y día, cifrados con un secreto mediante una función hash). La dirección IP no se
          guarda en claro.
        </li>
      </ul>

      <h2>Cookies</h2>
      <p>
        Solo usamos una cookie técnica, <code>dosehunt_country</code>, que guarda el código del país que has elegido
        durante 1 año. No contiene ningún dato personal y, al ser estrictamente necesaria para recordar la preferencia
        que tú mismo has pedido, está exenta de consentimiento (artículo 22.2 de la LSSI-CE).
      </p>

      <h2>Encargados del tratamiento</h2>
      <p>
        Alojamiento: Vercel. Base de datos: Neon. Envío de e-mails: Resend. Estos proveedores pueden tratar datos fuera
        de la Unión Europea, con garantías contractuales (cláusulas contractuales tipo).
      </p>

      <h2>Tus derechos</h2>
      <p>
        Puedes solicitar el acceso, la rectificación o la supresión de tus datos, u oponerte a su tratamiento,
        escribiendo a mameni1717@gmail.com. También puedes eliminar una alerta en cualquier momento con el enlace que
        aparece en cada e-mail. Si no estás de acuerdo con la respuesta, puedes presentar una reclamación ante la
        Agencia Española de Protección de Datos (AEPD, aepd.es).
      </p>

      <h2>Enlaces a otros sitios</h2>
      <p>Las tiendas online tienen su propia política de privacidad y sus propias cookies.</p>
    </article>
  );
}
