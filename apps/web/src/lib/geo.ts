import countries from "i18n-iso-countries";
import enLocale from "i18n-iso-countries/langs/en.json";
import esLocale from "i18n-iso-countries/langs/es.json";

countries.registerLocale(enLocale);
countries.registerLocale(esLocale);

/**
 * Traducción de las áreas geográficas de Orphanet.
 *
 * Orphanet publica los países con su nombre oficial ISO 3166 en inglés incluso en los
 * ficheros en español ("Romania", "Korea, Republic of"), y solo traduce los agregados
 * ("Mundial", "Europa"). Mapeando a código ISO conseguimos dos cosas de una vez: el
 * país para el mapa y su nombre traducido.
 */

/**
 * Nombres que `i18n-iso-countries` no reconoce porque Orphanet usa formas antiguas o
 * variantes de la norma. Son 8 de 131 países; el resto mapea directo.
 */
const NAME_ALIASES: Record<string, string> = {
  "Viet Nam": "VN",
  "Iran, Islamic Republic of": "IR",
  "Tanzania, United Republic of": "TZ",
  "Palestinian Territory, occupied": "PS",
  "Macedonia, the former Yugoslav Republic of": "MK",
  "Libyan Arab Jamahiriya": "LY",
  "Korea, Democratic People's Republic of": "KP",
  "Korea, Republic of": "KR",
};

/** Áreas que no son países: agregados y regiones. No van al mapa. */
const NON_COUNTRY_AREAS = new Set([
  "Mundial",
  "Worldwide",
  "Europa",
  "Europe",
  "África",
  "Africa",
  "Latinoamérica",
  "Latin America",
  "Norteamérica",
  "North America",
  "Oceanía",
  "Oceania",
  "Asia occidental",
  "Western Asia",
  "Sudeste asiático",
  "South-East Asia",
  "Mediterráneo oriental asiático",
  "Eastern Mediterranean",
  "Población específic",
  "Población específica",
  "Specific population",
]);

export function isCountryArea(area: string): boolean {
  return !NON_COUNTRY_AREAS.has(area.trim());
}

/** Código ISO alpha-2, o null si el área no es un país reconocible. */
export function areaToAlpha2(area: string): string | null {
  const trimmed = area.trim();
  if (NON_COUNTRY_AREAS.has(trimmed)) return null;
  if (NAME_ALIASES[trimmed]) return NAME_ALIASES[trimmed];
  return countries.getAlpha2Code(trimmed, "en") ?? null;
}

/**
 * Nombre del área para mostrar, traducido cuando es un país.
 *
 * Los agregados ya vienen traducidos por Orphanet, así que se devuelven tal cual.
 */
export function localizeArea(area: string, lang: string): string {
  const alpha2 = areaToAlpha2(area);
  if (!alpha2) return area;
  return countries.getName(alpha2, lang) ?? area;
}

/** ISO numérico (el id que usa world-atlas), como string con ceros a la izquierda. */
export function alpha2ToNumeric(alpha2: string): string | null {
  return countries.alpha2ToNumeric(alpha2) ?? null;
}

/** Nombre traducido de un país a partir de su código ISO alpha-2. */
export function countryName(alpha2: string, lang: string): string {
  return countries.getName(alpha2, lang) ?? alpha2;
}
