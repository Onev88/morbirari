"use client";

// El CSS de Leaflet es un import estático: el bundler lo trata como efecto de estilo,
// no se ejecuta en el servidor, así que es seguro aquí. El *JavaScript* de Leaflet, en
// cambio, toca `window` al cargarse y rompería el render en servidor: se importa de
// forma dinámica dentro del efecto (solo cliente). Ver más abajo.
import "leaflet/dist/leaflet.css";

import { useEffect, useRef, useState } from "react";
import type { GeoJsonObject } from "geojson";

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
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let cancelled = false;
    let built = false;
    let map: import("leaflet").Map | null = null;

    async function build() {
      if (built || cancelled || !el) return;
      built = true;
      try {
        const L = await import("leaflet");
        const { feature } = await import("topojson-client");
        const worldMod = await import("world-atlas/countries-110m.json");
        if (cancelled || !el) return;

        const world = (worldMod.default ?? worldMod) as unknown as {
          objects: { countries: unknown };
        } & Parameters<typeof feature>[0];

        const fc = feature(world, world.objects.countries as never) as unknown as {
          type: "FeatureCollection";
          features: {
            id?: string | number;
            properties: { name: string };
          }[];
        };
        // Fuera la Antártida, igual que en el SVG servido: ni hay datos ni aporta nada.
        fc.features = fc.features.filter((f) => f.properties.name !== "Antarctica");

        const byId = new Map(data.map((d) => [d.numericId, d]));

        map = L.map(el, {
          crs: L.CRS.EPSG4326,
          zoomControl: false, // usamos nuestros propios botones, coherentes con el resto
          attributionControl: false, // sin tiles no hay atribución de mapa que mostrar
          zoomSnap: 0.25,
          minZoom: 0,
          maxZoom: 6,
          worldCopyJump: false,
          // El coroplético es el contenido; sin inercia agresiva se lee mejor.
          inertia: true,
        });

        const layer = L.geoJSON(fc as unknown as GeoJsonObject, {
          style: (featObj) => {
            const datum = featObj ? byId.get(String((featObj as { id?: unknown }).id)) : undefined;
            return {
              className: datum ? `mr-country step-${datum.step}` : "mr-country no-data",
              // El color de relleno y trazo lo pone el CSS (por className) para heredar el
              // tema; Leaflet solo controla grosor y opacidad.
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

        const bounds = layer.getBounds();
        map.fitBounds(bounds, { padding: [8, 8] });
        // No dejar arrastrar el mundo fuera de cuadro ni alejar más allá del encuadre.
        map.setMaxBounds(bounds.pad(0.15));
        map.setMinZoom(map.getZoom());
        map.invalidateSize();

        mapRef.current = map;
        if (!cancelled) setReady(true);
      } catch {
        // Silencio deliberado: el SVG servido sigue visible como fallback.
      }
    }

    // La sección va en una pestaña que arranca oculta (display:none), así que al montar
    // el contenedor mide 0. Inicializar Leaflet ahí lo dejaría en blanco. Se difiere la
    // construcción hasta que el contenedor es visible, y en cambios de tamaño
    // posteriores (mostrar la pestaña, redimensionar la ventana) se revalida el lienzo.
    const visible = () => el.clientWidth > 0 && el.clientHeight > 0;
    const ro = new ResizeObserver(() => {
      if (!visible()) return;
      if (!built) build();
      else mapRef.current?.invalidateSize();
    });
    ro.observe(el);
    if (visible()) build();

    return () => {
      cancelled = true;
      ro.disconnect();
      if (map) map.remove();
      mapRef.current = null;
    };
  }, [data, labels]);

  return (
    <div className="map-interactive prevalence-leaflet">
      <div className="map-viewport leaflet-viewport">
        {/* Leaflet monta aquí. El contenedor está siempre dimensionado por CSS
            (aspect-ratio) para que Leaflet conozca su tamaño al inicializarse. */}
        <div
          ref={containerRef}
          className="leaflet-canvas"
          role="img"
          aria-label={ariaLabel}
        />
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
          onClick={() => {
            const m = mapRef.current;
            if (m) m.setZoom(m.getMinZoom());
          }}
          title={labels.reset}
        >
          {labels.reset}
        </button>
      </div>
      <p className="hint map-hint">{labels.hint}</p>
    </div>
  );
}
