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
 * Conmutador de tema de tres estados: Automático → Claro → Oscuro → Automático.
 *
 * Diseño:
 *  - «Automático» no fija atributo y deja mandar a `prefers-color-scheme`; es el
 *    estado por defecto y el que ve quien no ha tocado nada.
 *  - Claro/Oscuro fijan `data-theme` en <html> y se recuerdan en localStorage, así
 *    que la elección sobrevive a la recarga y a la navegación.
 *  - El primer pintado ya trae el tema correcto gracias al script en línea del
 *    layout; este componente solo sincroniza el icono y gestiona el clic. Por eso no
 *    renderiza nada hasta montarse (`mounted`): evita un desajuste de hidratación
 *    entre el HTML del servidor (que no conoce localStorage) y el cliente.
 */
export function ThemeToggle({ labels }: { labels: Labels }) {
  const [mode, setMode] = useState<Mode>("auto");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem("theme");
    } catch {
      /* almacenamiento no disponible: se queda en automático */
    }
    setMode(stored === "light" || stored === "dark" ? stored : "auto");
    setMounted(true);
  }, []);

  function apply(next: Mode) {
    setMode(next);
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
  }

  function cycle() {
    apply(mode === "auto" ? "light" : mode === "light" ? "dark" : "auto");
  }

  const current = mode === "auto" ? labels.auto : mode === "light" ? labels.light : labels.dark;

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={cycle}
      aria-label={`${labels.toggle} · ${current}`}
      title={`${labels.toggle} · ${current}`}
    >
      <span className="theme-icon" aria-hidden="true">
        {mounted && mode === "light" && <SunIcon />}
        {mounted && mode === "dark" && <MoonIcon />}
        {(!mounted || mode === "auto") && <AutoIcon />}
      </span>
      <span className="theme-label">{mounted ? current : labels.auto}</span>
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

function AutoIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none" />
    </svg>
  );
}
