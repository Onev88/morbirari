"use client";

import { useEffect, useState } from "react";

type Mode = "auto" | "light" | "dark";

type Labels = {
  toggle: string;
  auto: string;
  light: string;
  dark: string;
};

/**
 * Interruptor de tema de dos estados: Claro ↔ Oscuro.
 *
 * Diseño:
 *  - Cada clic fija `data-theme` en <html> (claro u oscuro) y lo recuerda en
 *    localStorage, así que la elección sobrevive a la recarga y a la navegación.
 *  - En la PRIMERA visita, sin elección guardada, no se fija atributo y manda
 *    `prefers-color-scheme` (el sistema). No es un estado «Automático» seleccionable:
 *    es solo el punto de partida hasta el primer clic, que ya deja un tema explícito.
 *  - El primer pintado ya trae el tema correcto gracias al script en línea del
 *    layout; este componente solo sincroniza el icono y gestiona el clic. Por eso no
 *    decide el icono hasta montarse (`mounted`): evita un desajuste de hidratación
 *    entre el HTML del servidor (que no conoce localStorage) y el cliente.
 *  - El botón es solo icono, sin texto: sol (claro) o luna (oscuro). Mientras no haya
 *    elección, muestra el icono del tema EFECTIVO del sistema. El nombre del tema se
 *    conserva en `aria-label`/`title` para accesibilidad.
 */
export function ThemeToggle({ labels }: { labels: Labels }) {
  const [mode, setMode] = useState<Mode>("auto");
  const [mounted, setMounted] = useState(false);
  const [systemDark, setSystemDark] = useState(false);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem("theme");
    } catch {
      /* almacenamiento no disponible: se queda en automático */
    }
    setMode(stored === "light" || stored === "dark" ? stored : "auto");
    setMounted(true);

    // En modo «Automático» el icono debe reflejar lo que decide el sistema, y seguir
    // reflejándolo si el usuario cambia el tema del SO con la página abierta.
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setSystemDark(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  /**
   * Tema realmente aplicado ahora mismo, leído del <html> (la fuente de verdad).
   * El atributo lo fija el script en línea del layout en la primera carga y este
   * componente en cada clic, así que refleja el estado antes que el `state` de React.
   */
  function appliedTheme(): Mode {
    const t = document.documentElement.dataset.theme;
    return t === "light" || t === "dark" ? t : "auto";
  }

  function apply(next: Mode) {
    const root = document.documentElement;
    try {
      if (next === "auto") {
        delete root.dataset.theme;
        localStorage.removeItem("theme");
      } else {
        root.dataset.theme = next;
        localStorage.setItem("theme", next);
      }
    } catch {
      // Sin persistencia, al menos el cambio en memoria surte efecto en esta página.
      if (next === "auto") delete root.dataset.theme;
      else root.dataset.theme = next;
    }
    // El icono y la etiqueta se pintan desde el estado de React; se sincroniza al final.
    setMode(next);
  }

  function cycle() {
    // Interruptor de dos estados: se fija SIEMPRE el tema contrario al efectivo actual.
    // El «efectivo» se lee del DOM (o del sistema si aún no hay elección), no de `mode`,
    // que puede ir un render por detrás: así al pulsar rápido no se atasca ni se salta.
    const applied = appliedTheme();
    const effDark = applied === "dark" || (applied === "auto" && systemDark);
    apply(effDark ? "light" : "dark");
  }

  // Tema efectivo mostrado: el elegido, o el del sistema mientras no haya elección. Solo
  // sol o luna. Antes de montar se asume claro (sol), lo que casa con el HTML servido.
  const effectiveDark = mounted && (mode === "dark" || (mode === "auto" && systemDark));
  const currentLabel = effectiveDark ? labels.dark : labels.light;

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={cycle}
      aria-label={`${labels.toggle} · ${currentLabel}`}
      title={`${labels.toggle} · ${currentLabel}`}
    >
      <span className="theme-icon" aria-hidden="true">
        {effectiveDark ? <MoonIcon /> : <SunIcon />}
      </span>
    </button>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}

