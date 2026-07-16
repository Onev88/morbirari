import { geoNaturalEarth1, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import worldData from "world-atlas/countries-110m.json";
import { alpha2ToNumeric, areaToAlpha2, localizeArea } from "@/lib/geo";
import type { GeoPrevalence } from "@/lib/dashboard";
import { LeafletMap, type CountryDatum } from "./leaflet-map";

/**
 * Mapa coroplético de prevalencia.
 *
 * Se renderiza entero en el servidor: SVG inline, sin JavaScript de cliente y sin
 * peticiones a terceros. El tooltip es un <title> nativo, que además leen los
 * lectores de pantalla.
 *
 * Escala secuencial de un solo hue (más oscuro = más frecuente), validada con
 * `validate_palette.js` contra las superficies clara y oscura del sitio. Una escala
 * secuencial es la forma correcta aquí: el dato es magnitud, no identidad.
 */

/*
 * Lienzo interno al doble de la escala de presentación, con coordenadas enteras.
 *
 * Medido: a 800×330 con un decimal son 110 KB; a 1600×660 con enteros son 77 KB y
 * con el DOBLE de precisión efectiva (0,46 px frente a 0,93 px al renderizar a
 * 740 px). Un dígito más de parte entera cuesta menos que un punto y un decimal.
 *
 * La altura es 660 y no 760 porque la Antártida se excluye (ver más abajo).
 */
const WIDTH = 1600;
const HEIGHT = 660;

// Rampa secuencial azul, 100→700. La usa el <defs> del gradiente de la leyenda y el
// relleno de cada país. Validada: hue único, luminosidad monótona.
const RAMP_LIGHT = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281"];

type Props = {
  groups: { type: string; max: number; rows: GeoPrevalence[] }[];
  lang: string;
  labels: {
    noData: string;
    legendLow: string;
    legendHigh: string;
    zoomIn: string;
    zoomOut: string;
    reset: string;
    hint: string;
  };
};

const world = worldData as unknown as Topology;
const rawFc = feature(world, world.objects.countries) as unknown as {
  type: string;
  features: { id?: string | number; properties: { name: string } }[];
};

/*
 * Fuera la Antártida.
 *
 * No es una opinión geopolítica: no hay ni habrá datos de prevalencia allí, y su
 * geometría ocupa la franja inferior del lienzo y una porción notable de los bytes.
 * Quitarla deja el mismo mapa más alto y más ligero.
 */
const countriesFc = {
  type: "FeatureCollection",
  features: rawFc.features.filter((f) => f.properties.name !== "Antarctica"),
};

const projection = geoNaturalEarth1().fitSize([WIDTH, HEIGHT], countriesFc as never);
const pathGen = geoPath(projection);

/** Coordenadas a entero. Ver la nota del lienzo: es donde está el peso del mapa. */
function roundPath(d: string): string {
  return d.replace(/-?\d+\.\d+/g, (m) => Number(m).toFixed(0));
}

// El SVG base es idéntico en todas las fichas: se calcula una vez por proceso.
const BASE_PATHS: { numericId: string; name: string; d: string }[] = countriesFc.features
  .map((f) => {
    const d = pathGen(f as never);
    return d
      ? { numericId: String(f.id ?? ""), name: f.properties.name, d: roundPath(d) }
      : null;
  })
  .filter((x): x is { numericId: string; name: string; d: string } => x !== null);

/** Índice del paso de la rampa para un valor, en escala de raíz cuadrada. */
function rampIndex(value: number, max: number): number {
  if (max <= 0) return 0;
  // Raíz cuadrada y no lineal: las prevalencias tienen colas largas (un país con un
  // valor extremo dejaría a todos los demás en el mismo tono más claro).
  const t = Math.sqrt(value) / Math.sqrt(max);
  return Math.min(RAMP_LIGHT.length - 1, Math.max(0, Math.round(t * (RAMP_LIGHT.length - 1))));
}

export function PrevalenceMap({ groups, lang, labels }: Props) {
  // Se mapea el grupo con más países: mezclar tipos de medida en un mismo mapa
  // repetiría el problema que la agrupación resolvió.
  const group = groups[0];
  if (!group) return null;

  const byNumeric = new Map<string, { name: string; value: number; step: number }>();
  for (const row of group.rows) {
    const alpha2 = areaToAlpha2(row.area);
    if (!alpha2) continue;
    const numeric = alpha2ToNumeric(alpha2);
    if (!numeric) continue;
    const existing = byNumeric.get(numeric);
    // Un país puede tener varias entradas; se queda la mayor.
    if (existing && existing.value >= row.value) continue;
    byNumeric.set(numeric, {
      name: localizeArea(row.area, lang),
      value: row.value,
      step: rampIndex(row.value, group.max),
    });
  }

  if (byNumeric.size === 0) return null;

  // Datos que viajan al cliente: solo los países CON dato (pequeño). La geometría del
  // resto del mundo la carga el cliente desde `world-atlas`, ya empaquetado, así que no
  // se serializa el mapamundi entero en el HTML.
  const countryData: CountryDatum[] = Array.from(byNumeric, ([numericId, v]) => ({
    numericId,
    name: v.name,
    value: v.value,
    step: v.step,
  }));

  return (
    <figure className="map-figure">
      <figcaption className="map-caption">
        {group.type}
        <span className="dim"> · {byNumeric.size}</span>
      </figcaption>

      {/* La leyenda es obligatoria: sin ella el color no significa nada. Va sobre el
          mapa, junto al título, para que se lea antes de mirar los países. */}
      <div className="map-legend" aria-hidden="true">
        <span className="dim small">{labels.legendLow}</span>
        <span className="legend-ramp" />
        <span className="dim small">
          {labels.legendHigh} · {group.max.toFixed(1)}
        </span>
      </div>

      {/*
        El SVG se sirve entero desde el servidor y se pasa como children a la capa de
        interacción, que añade tooltip, zoom y desplazamiento. Sin JavaScript el mapa
        se ve igual (estático) y cada país conserva su <title> nativo.
      */}
      <LeafletMap
        data={countryData}
        ariaLabel={`${group.type}: ${byNumeric.size} países`}
        labels={{
          noData: labels.noData,
          zoomIn: labels.zoomIn,
          zoomOut: labels.zoomOut,
          reset: labels.reset,
          hint: labels.hint,
        }}
      >
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="prevalence-map"
          role="img"
          aria-label={`${group.type}: ${byNumeric.size} países`}
          preserveAspectRatio="xMidYMid meet"
        >
          <g id="prevalence-map-layer">
            {BASE_PATHS.map((c) => {
              const datum = byNumeric.get(c.numericId);
              return (
                <path
                  key={c.numericId + c.name}
                  d={c.d}
                  className={datum ? `country step-${datum.step}` : "country no-data"}
                  data-name={datum ? datum.name : c.name}
                  data-value={datum ? datum.value.toFixed(1) : ""}
                >
                  {/* <title> nativo: tooltip sin JavaScript y accesible. */}
                  <title>
                    {datum
                      ? `${datum.name}: ${datum.value.toFixed(1)}`
                      : `${c.name}: ${labels.noData}`}
                  </title>
                </path>
              );
            })}
          </g>
        </svg>
      </LeafletMap>
    </figure>
  );
}
