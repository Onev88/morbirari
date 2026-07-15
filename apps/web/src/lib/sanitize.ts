/**
 * Las definiciones de Orphanet traen HTML incrustado, pero solo de énfasis: usan
 * <i> para términos latinos ("genu valgum", "pectus excavatum"). Permitimos ese
 * subconjunto y escapamos todo lo demás. Que la fuente sea de confianza no es razón
 * para renderizar HTML arbitrario que venga de un fichero externo.
 */

const ALLOWED_TAGS = "i|em|b|strong|sub|sup";

export function sanitizeDefinition(html: string): string {
  const escaped = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return (
    escaped
      // Restaurar las entidades que ya venían codificadas en el origen. Orphanet
      // publica algunas definiciones con entidades escapadas dos veces (p. ej.
      // "&#160;" literal), y escapar el '&' otra vez las mostraría como texto
      // crudo en la página.
      .replace(/&amp;#(\d+);/g, "&#$1;")
      .replace(/&amp;#x([0-9a-fA-F]+);/g, "&#x$1;")
      .replace(/&amp;(nbsp|amp|lt|gt|quot|apos);/g, "&$1;")
      // Re-permitir solo las etiquetas de énfasis.
      .replace(new RegExp(`&lt;(/?)(${ALLOWED_TAGS})&gt;`, "gi"), "<$1$2>")
  );
}
