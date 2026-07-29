"use client";

// El CSS de Leaflet es un import estático: el bundler lo trata como efecto de estilo,
// no se ejecuta en el servidor, así que es seguro aquí. El *JavaScript* de Leaflet, en
// cambio, toca `window` al cargarse y rompería el render en servidor: se importa de
// forma dinámica dentro del efecto (solo cliente). Ver más abajo.
import "leaflet/dist/leaflet.css";

import { useEffect, useRef, useState } from "react";
import type { GeoJsonObject } from "geojson";
import * as d3 from "d3-geo";
import * as d3proj from "d3-geo-projection";
import { feature } from "topojson-client";
import worldData from "world-atlas/countries-110m.json";

export type CountryDatum = {
  /** ISO numérico (el id de world-atlas), como string. Coincide con `feature.id`. */
  numericId: string;
  name: string;
  value: number;
  step: number;
};

type Labels = {
  zoomIn: string;
  zoomOut: string;
  reset: string;
  hint: string;
  noData: string;
  activateMap: string;
  deactivateMap: string;
};

/**
 * Mapa coroplético de prevalencia con Leaflet, como MEJORA PROGRESIVA.
 *
 * El SVG servido desde el servidor llega como `children` y es lo que se ve sin
 * JavaScript, lo que indexa un buscador y lo que lee un lector de pantalla. Este
 * componente monta un mapa Leaflet encima y, solo cuando está listo, oculta el SVG.
 * Si Leaflet falla o no hay JS, el SVG se queda: nunca hay pantalla en blanco.
 *
 * Decisiones:
 *  - Sin *tiles* ni peticiones a terceros: la geometría sale de `world-atlas` (Natural
 *    Earth, dominio público), que ya viene empaquetado. El «mapa base» es la propia
 *    tierra coloreada; el océano es el fondo del contenedor.
 *  - Colores por `className` (`step-N` / `no-data`), no por JS: así el modo claro/oscuro
 *    se hereda de las variables CSS del tema sin tener que restilar al cambiarlo.
 *  - CRS equirectangular (EPSG:4326): evita la inflación polar de Mercator y conserva
 *    coordenadas lat/lng para futuros marcadores (p. ej. centros de ensayos).
 */
export function LeafletMap({
  data,
  labels,
  ariaLabel,
  children,
}: {
  data: CountryDatum[];
  labels: Labels;
  ariaLabel: string;
  children: React.ReactNode;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  // Tipado laxo a propósito: Leaflet se carga en tiempo de ejecución y no queremos
  // arrastrar sus tipos al bundle del servidor. Los usos concretos van acotados.
  const mapRef = useRef<import("leaflet").Map | null>(null);
  // Reencuadre al estado inicial (centrar + zoom de ajuste). Lo expone el efecto para
  // que el botón de reinicio lo use; vive en un ref porque `bounds` está en el efecto.
  const fitRef = useRef<(() => void) | null>(null);
  const [ready, setReady] = useState(false);
  const [active, setActive] = useState(false);

  // Sincronizar estado activo de interacción con la instancia de Leaflet
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (active) {
      map.dragging.enable();
      map.scrollWheelZoom.enable();
      map.doubleClickZoom.enable();
      if (map.touchZoom) map.touchZoom.enable();
    } else {
      map.dragging.disable();
      map.scrollWheelZoom.disable();
      map.doubleClickZoom.disable();
      if (map.touchZoom) map.touchZoom.disable();
    }
  }, [active]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let cancelled = false;
    let loading = false;
    let map: import("leaflet").Map | null = null;
    let bounds: import("leaflet").LatLngBounds | null = null;
    let L: typeof import("leaflet") | null = null;

    // Lienzo de proyección (mismas dimensiones que el SVG servido: así el encuadre y la
    // forma coinciden exactamente).
    const PW = 1600;
    const PH = 660;

    const visible = () => el.clientWidth > 0 && el.clientHeight > 0;

    // La sección del mapa (#geografia) vive en una pestaña. Solo se inicializa cuando ESA
    // pestaña está seleccionada, no en el parpadeo inicial en que todas están visibles.
    const sectionId = el.closest("section")?.id ?? null;
    const isSectionActive = () => document.body.dataset.activeSection === sectionId;

    /** Reajusta el lienzo y reencuadra. Necesario porque un mapa dejado con tamaño 0
     *  conserva un zoom/centro inservibles: no basta invalidateSize. */
    function fit() {
      if (!map || !bounds) return;
      map.invalidateSize();
      map.fitBounds(bounds, { padding: [4, 4] });
      map.setMinZoom(map.getZoom());
    }
    fitRef.current = fit;

    /**
     * Construcción SÍNCRONA del mapa (sin await). El truco de proyección: en vez de
     * dejar que Leaflet proyecte lat/lng (equirrectangular o Mercator, que estiran el
     * mundo), se usa la MISMA proyección Natural Earth que el SVG del servidor —vía d3—
     * y se monta sobre un CRS.Simple (plano de píxeles ya proyectados). Así el mapa se ve
     * idéntico al SVG bonito de antes, pero con zoom, desplazamiento y tooltips.
     */
    function build() {
      if (!L || map || !el) return;
      const Leaflet = L;
      const w = worldData as unknown as Parameters<typeof feature>[0] & { objects: { countries: unknown } };
      const raw = feature(w, w.objects.countries as never) as unknown as {
        type: "FeatureCollection";
        features: { id?: string | number; properties: { name: string }; geometry: unknown }[];
      };
      // Fuera la Antártida, igual que en el SVG servido: ni hay datos ni aporta nada.
      const kept = raw.features.filter((f) => f.properties.name !== "Antarctica");

      const projection = d3.geoNaturalEarth1().fitSize([PW, PH], {
        type: "FeatureCollection",
        features: kept,
      } as never);

      // Se proyecta con geoProject (que CORTA en el antimeridiano y recorta a la esfera,
      // igual que geoPath al dibujar), no punto por punto: así países que cruzan ±180°
      // —Fiji, sobre todo— no dibujan una raya horizontal de lado a lado del mapa. Se
      // conservan `id` (para casar con los datos) y `properties` (el nombre del tooltip).
      const projFc = {
        type: "FeatureCollection" as const,
        features: kept
          .map((f) => {
            const geometry = d3proj.geoProject(f.geometry as GeoJsonObject, projection);
            return geometry
              ? { type: "Feature" as const, id: f.id, properties: f.properties, geometry }
              : null;
          })
          .filter((f): f is NonNullable<typeof f> => f !== null),
      };

      const byId = new Map(data.map((d) => [d.numericId, d]));

      map = Leaflet.map(el, {
        crs: Leaflet.CRS.Simple, // plano: las coordenadas ya vienen proyectadas por d3
        zoomControl: false, // usamos nuestros propios botones, coherentes con el resto
        attributionControl: false, // sin tiles no hay atribución de mapa que mostrar
        zoomSnap: 0.25,
        minZoom: -10,
        maxZoom: 6,
        inertia: true,
        dragging: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        touchZoom: false,
      });

      const layer = Leaflet.geoJSON(projFc as unknown as GeoJsonObject, {
        // Coordenadas ya proyectadas (píxeles, y hacia abajo). CRS.Simple: lat=-y para
        // que el norte quede arriba.
        coordsToLatLng: (coords) => Leaflet.latLng(-coords[1], coords[0]),
        style: (featObj) => {
          const datum = featObj ? byId.get(String((featObj as { id?: unknown }).id)) : undefined;
          return {
            // El color de relleno y trazo lo pone el CSS (por className) para heredar el
            // tema; Leaflet solo controla grosor y opacidad.
            className: datum ? `mr-country step-${datum.step}` : "mr-country no-data",
            weight: 0.5,
            fillOpacity: 1,
          };
        },
        onEachFeature: (featObj, lyr) => {
          const id = String((featObj as { id?: unknown }).id);
          const datum = byId.get(id);
          const name = datum ? datum.name : (featObj.properties as { name: string }).name;
          const valueText = datum ? datum.value.toFixed(1) : labels.noData;
          lyr.bindTooltip(`${name}: ${valueText}`, { sticky: true, direction: "top" });
          lyr.on({
            mouseover: (e) => (e.target as import("leaflet").Path).setStyle({ weight: 1.4 }),
            mouseout: (e) => (e.target as import("leaflet").Path).setStyle({ weight: 0.5 }),
          });
        },
      }).addTo(map);

      bounds = layer.getBounds();
      map.setMaxBounds(bounds.pad(0.1)); // no dejar arrastrar el mundo fuera de cuadro
      mapRef.current = map;
      setReady(true);
    }

    async function loadLibs() {
      if (L || loading) return;
      loading = true;
      try {
        const Leaflet = await import("leaflet");
        if (cancelled) return;
        L = Leaflet;
      } finally {
        loading = false;
      }
    }

    /**
     * Punto de entrada: construir/reencuadrar SOLO si la pestaña del mapa está
     * seleccionada y visible. Se carga la librería aquí (perezosa): nada de mapa hasta
     * que el usuario abre «Dónde se documenta». Tras el `await` se vuelve a comprobar la
     * visibilidad, por si se cambió de pestaña mientras cargaba.
     */
    async function activate() {
      if (cancelled || !isSectionActive() || !visible()) return;
      if (!L) {
        await loadLibs();
        if (cancelled || !isSectionActive() || !visible()) return;
      }
      if (!map) build();
      fit();
    }

    // Disparador principal: el cambio de pestaña se refleja en `data-active-section` del
    // <body> (ver section-nav). Es más fiable que observar la visibilidad del elemento:
    // un ResizeObserver/IntersectionObserver no dispara al pasar de display:none a
    // visible cuando quien se oculta es un ancestro.
    const mo = new MutationObserver(() => activate());
    mo.observe(document.body, { attributes: true, attributeFilter: ["data-active-section"] });

    // Complemento: reencuadrar al cambiar el tamaño con el mapa ya visible.
    const ro = new ResizeObserver(() => activate());
    ro.observe(el);

    activate(); // por si ya está seleccionada al montar (carga directa a #geografia)

    return () => {
      cancelled = true;
      mo.disconnect();
      ro.disconnect();
      if (map) map.remove();
      mapRef.current = null;
    };
  }, [data, labels]);

  return (
    <div className="map-interactive prevalence-leaflet">
      <div className="map-viewport leaflet-viewport" style={{ position: "relative" }}>
        {/* Leaflet monta aquí. El contenedor está siempre dimensionado por CSS
            (aspect-ratio) para que Leaflet conozca su tamaño al inicializarse. */}
        <div
          ref={containerRef}
          className="leaflet-canvas"
          role="img"
          aria-label={ariaLabel}
        />
        {ready && !active && (
          <div className="map-overlay-lock">
            <button
              type="button"
              className="map-activate-btn"
              onClick={() => setActive(true)}
            >
              {labels.activateMap}
            </button>
          </div>
        )}
        {/* Fallback: el SVG del servidor. Visible hasta que Leaflet está listo; se
            mantiene en el DOM (indexable) pero se oculta a la vista y a accesibilidad
            cuando el mapa interactivo ya lo sustituye. */}
        <div className="leaflet-fallback" hidden={ready} aria-hidden={ready}>
          {children}
        </div>
      </div>

      <div className="map-controls">
        <button
          type="button"
          onClick={() => mapRef.current?.zoomIn()}
          aria-label={labels.zoomIn}
          title={labels.zoomIn}
        >
          +
        </button>
        <button
          type="button"
          onClick={() => mapRef.current?.zoomOut()}
          aria-label={labels.zoomOut}
          title={labels.zoomOut}
        >
          −
        </button>
        <button
          type="button"
          className="map-reset"
          onClick={() => fitRef.current?.()}
          title={labels.reset}
        >
          {labels.reset}
        </button>
        {ready && active && (
          <button
            type="button"
            className="map-lock-toggle"
            onClick={() => setActive(false)}
            title={labels.deactivateMap}
            aria-label={labels.deactivateMap}
          >
            🔒
          </button>
        )}
      </div>
      <p className="hint map-hint">{labels.hint}</p>
    </div>
  );
}
