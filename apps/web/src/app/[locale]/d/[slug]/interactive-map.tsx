"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Labels = {
  zoomIn: string;
  zoomOut: string;
  reset: string;
  hint: string;
  noData: string;
};

// Deben coincidir con el viewBox del SVG servido en prevalence-map.tsx.
const WIDTH = 1600;
const HEIGHT = 660;
const MIN_SCALE = 1;
const MAX_SCALE = 8;

/**
 * Capa de interacción sobre el mapa coroplético.
 *
 * El SVG llega ya renderizado desde el servidor como `children` (sin d3 en el
 * cliente, y sigue estando entero en el HTML para quien no tiene JavaScript). Este
 * componente solo añade comportamiento:
 *
 *  - Tooltip flotante con el nombre del país y su cifra, leídos de `data-name` /
 *    `data-value` en cada <path>. Sin JS, esos datos siguen en el <title> nativo.
 *  - Zoom con la rueda (hacia el cursor) y con botones; desplazamiento arrastrando.
 *    Se aplica como atributo `transform` sobre el grupo interno, que es barato y no
 *    reflowa la página.
 *
 * El zoom/pan es manipulación directa: no hay animación automática, así que respeta
 * de serie a quien pide movimiento reducido.
 */
export function InteractiveMap({ children, labels }: { children: React.ReactNode; labels: Labels }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const layerRef = useRef<SVGGElement | null>(null);
  const view = useRef({ scale: 1, tx: 0, ty: 0 });
  const drag = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);

  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);

  const apply = useCallback(() => {
    const layer = layerRef.current;
    if (!layer) return;
    const { scale, tx, ty } = view.current;
    layer.setAttribute("transform", `translate(${tx} ${ty}) scale(${scale})`);
  }, []);

  useEffect(() => {
    const vp = viewportRef.current;
    if (!vp) return;
    // El SVG servido tiene un grupo con este id que es el que transformamos.
    layerRef.current = vp.querySelector<SVGGElement>("#prevalence-map-layer");
  }, []);

  /** Coordenada del puntero en unidades del viewBox del SVG. */
  function toViewBox(clientX: number, clientY: number) {
    const svg = viewportRef.current?.querySelector("svg");
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    return {
      x: ((clientX - rect.left) / rect.width) * WIDTH,
      y: ((clientY - rect.top) / rect.height) * HEIGHT,
    };
  }

  function zoomAbout(vbX: number, vbY: number, factor: number) {
    const v = view.current;
    const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor));
    if (next === v.scale) return;
    // Mantener fijo el punto (vbX,vbY) bajo el cursor: tx = X - s·((X - tx)/s0).
    v.tx = vbX - (next / v.scale) * (vbX - v.tx);
    v.ty = vbY - (next / v.scale) * (vbY - v.ty);
    v.scale = next;
    clampPan();
    apply();
  }

  /** Evita arrastrar el mapa fuera de su marco cuando hay zoom. */
  function clampPan() {
    const v = view.current;
    const maxX = 0;
    const minX = WIDTH - WIDTH * v.scale;
    const maxY = 0;
    const minY = HEIGHT - HEIGHT * v.scale;
    v.tx = Math.min(maxX, Math.max(minX, v.tx));
    v.ty = Math.min(maxY, Math.max(minY, v.ty));
  }

  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    const { x, y } = toViewBox(e.clientX, e.clientY);
    zoomAbout(x, y, e.deltaY < 0 ? 1.2 : 1 / 1.2);
  }

  function onPointerDown(e: React.PointerEvent) {
    const v = view.current;
    drag.current = { x: e.clientX, y: e.clientY, tx: v.tx, ty: v.ty };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: React.PointerEvent) {
    // Tooltip: el objetivo es un <path> del mapa con sus datos.
    const target = e.target as SVGElement;
    if (!drag.current && target.tagName.toLowerCase() === "path") {
      const name = target.getAttribute("data-name");
      const value = target.getAttribute("data-value");
      const vpRect = viewportRef.current!.getBoundingClientRect();
      setTooltip({
        x: e.clientX - vpRect.left,
        y: e.clientY - vpRect.top,
        text: name ? `${name}: ${value ?? labels.noData}` : "",
      });
    } else if (!drag.current) {
      setTooltip(null);
    }

    if (!drag.current) return;
    const svg = viewportRef.current?.querySelector("svg");
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const dx = ((e.clientX - drag.current.x) / rect.width) * WIDTH;
    const dy = ((e.clientY - drag.current.y) / rect.height) * HEIGHT;
    view.current.tx = drag.current.tx + dx;
    view.current.ty = drag.current.ty + dy;
    clampPan();
    apply();
  }

  function onPointerUp(e: React.PointerEvent) {
    drag.current = null;
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* el puntero ya no está capturado */
    }
  }

  function reset() {
    view.current = { scale: 1, tx: 0, ty: 0 };
    apply();
  }

  return (
    <div className="map-interactive">
      <div
        ref={viewportRef}
        className="map-viewport"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={() => {
          setTooltip(null);
          drag.current = null;
        }}
      >
        {children}
        {tooltip && tooltip.text && (
          <div
            className="map-tooltip"
            style={{ left: tooltip.x, top: tooltip.y }}
            role="status"
          >
            {tooltip.text}
          </div>
        )}
      </div>

      <div className="map-controls">
        <button
          type="button"
          onClick={() => zoomAbout(WIDTH / 2, HEIGHT / 2, 1.4)}
          aria-label={labels.zoomIn}
          title={labels.zoomIn}
        >
          +
        </button>
        <button
          type="button"
          onClick={() => zoomAbout(WIDTH / 2, HEIGHT / 2, 1 / 1.4)}
          aria-label={labels.zoomOut}
          title={labels.zoomOut}
        >
          −
        </button>
        <button type="button" onClick={reset} className="map-reset" title={labels.reset}>
          {labels.reset}
        </button>
      </div>
      <p className="hint map-hint">{labels.hint}</p>
    </div>
  );
}
