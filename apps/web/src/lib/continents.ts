import { areaToAlpha2 } from "./geo";

/**
 * Clasificación geográfica para los filtros de búsqueda por continente y país.
 *
 * Es la **única** sede de la lógica geográfica de los filtros. El indexador de
 * Meilisearch (Python) no clasifica nada: guarda por enfermedad la lista de áreas
 * **crudas** de Orphanet (`geo_areas`, nombres en inglés y agregados). La clasificación
 * país→continente y la expansión de un continente a sus áreas viven aquí, en el web, y
 * las comparten la consulta a Meilisearch y el fallback de Postgres. Así no hay dos mapas
 * que se desincronicen entre Python y TypeScript.
 *
 * Encuadre (regla 16, ADR 0002): esto filtra el catálogo por la geografía **documentada**
 * de cada enfermedad —dónde se ha estudiado o registrado su epidemiología—, no por dónde
 * «ocurre». La ausencia de un país casi siempre significa falta de estudios, no ausencia
 * de la enfermedad.
 */

export type Continent = "africa" | "americas" | "asia" | "europe" | "oceania";

/** Orden estable para la interfaz. */
export const CONTINENTS: Continent[] = ["africa", "americas", "asia", "europe", "oceania"];

/**
 * País (ISO alpha-2) → continente.
 *
 * Cubre los países que aparecen en la epidemiología de Orphanet. Los transcontinentales
 * se asignan por convención mayoritaria (Rusia→Europa, Turquía→Asia, Chipre→Europa). Un
 * país no listado no es filtrable por continente hasta añadirlo: se prefiere el hueco a
 * una clasificación inventada.
 */
export const ISO2_TO_CONTINENT: Record<string, Continent> = {
  // África
  DZ: "africa", CM: "africa", EG: "africa", ER: "africa", KE: "africa", LS: "africa",
  LY: "africa", MR: "africa", MA: "africa", NG: "africa", SN: "africa", SL: "africa",
  ZA: "africa", SD: "africa", TZ: "africa", TG: "africa", TN: "africa", UG: "africa",
  ZW: "africa", RE: "africa",
  // América
  AR: "americas", BZ: "americas", BO: "americas", BR: "americas", CA: "americas",
  CL: "americas", CO: "americas", CR: "americas", CU: "americas", DO: "americas",
  EC: "americas", SV: "americas", GP: "americas", GT: "americas", GY: "americas",
  HT: "americas", HN: "americas", JM: "americas", MQ: "americas", MX: "americas",
  NI: "americas", PA: "americas", PY: "americas", PE: "americas", PR: "americas",
  US: "americas", UY: "americas", VE: "americas", GL: "americas",
  // Asia
  AM: "asia", AZ: "asia", BH: "asia", BD: "asia", BN: "asia", CN: "asia", GE: "asia",
  HK: "asia", IN: "asia", ID: "asia", IR: "asia", IQ: "asia", IL: "asia", JP: "asia",
  JO: "asia", KP: "asia", KR: "asia", KW: "asia", LB: "asia", MY: "asia", MN: "asia",
  NP: "asia", OM: "asia", PK: "asia", PS: "asia", PH: "asia", QA: "asia", SA: "asia",
  SG: "asia", LK: "asia", TW: "asia", TH: "asia", TR: "asia", AE: "asia", UZ: "asia",
  VN: "asia",
  // Europa
  AL: "europe", AT: "europe", BY: "europe", BE: "europe", BA: "europe", BG: "europe",
  HR: "europe", CY: "europe", CZ: "europe", DK: "europe", EE: "europe", FO: "europe",
  FI: "europe", FR: "europe", DE: "europe", GR: "europe", HU: "europe", IS: "europe",
  IE: "europe", IT: "europe", LV: "europe", LI: "europe", LT: "europe", LU: "europe",
  MT: "europe", MD: "europe", NL: "europe", MK: "europe", NO: "europe", PL: "europe",
  PT: "europe", RO: "europe", RU: "europe", RS: "europe", SK: "europe", SI: "europe",
  ES: "europe", SE: "europe", CH: "europe", UA: "europe", GB: "europe",
  // Oceanía
  AU: "oceania", PF: "oceania", NC: "oceania", NZ: "oceania",
};

/**
 * Agregados que Orphanet publica como área (no son países) → continente(s).
 *
 * Se corresponde con las cadenas **reales** del dato (p. ej. «South East Asia» sin guion,
 * «Eastern Mediterranean Asia»). «Worldwide» y «Specific population» no localizan nada y
 * se omiten a propósito: un dato mundial no es señal de un continente.
 */
export const AGGREGATE_AREA_TO_CONTINENTS: Record<string, Continent[]> = {
  Africa: ["africa"],
  Europe: ["europe"],
  "North America": ["americas"],
  "Latin America": ["americas"],
  Oceania: ["oceania"],
  "Western Asia": ["asia"],
  "South East Asia": ["asia"],
  "Eastern Mediterranean Asia": ["asia"],
};

/** true si el área es un país mapeable (no un agregado ni «Worldwide»). */
export function isMappableCountry(area: string): boolean {
  return areaToAlpha2(area) !== null;
}

/**
 * Continente(s) a los que apunta un área cualquiera (país o agregado), o vacío si no se
 * reconoce (p. ej. «Worldwide», «Specific population»).
 */
export function areaToContinents(area: string): Continent[] {
  const aggregate = AGGREGATE_AREA_TO_CONTINENTS[area.trim()];
  if (aggregate) return aggregate;
  const alpha2 = areaToAlpha2(area);
  const continent = alpha2 ? ISO2_TO_CONTINENT[alpha2] : undefined;
  return continent ? [continent] : [];
}

/** De una lista de áreas crudas, las que pertenecen a un continente (países + agregado). */
export function areasInContinent(continent: Continent, areas: string[]): string[] {
  return areas.filter((a) => areaToContinents(a).includes(continent));
}
