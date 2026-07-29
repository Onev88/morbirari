"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { routing } from "@/i18n/routing";

/**
 * Conmutador de idioma que conserva la página actual, la búsqueda y la pestaña activa.
 *
 * Resolviendo la ruta completa (incluyendo query y hash) únicamente en el cliente tras el montaje,
 * evitamos desajustes de hidratación (hydration mismatch) y mantenemos soporte para múltiples
 * idiomas dinámicamente configurados en 'routing.locales'.
 */
export function LangSwitch({ current, label }: { current: string; label: string }) {
  const [paths, setPaths] = useState<Record<string, string>>({});

  useEffect(() => {
    const pathname = window.location.pathname;
    const search = window.location.search || "";
    const hash = window.location.hash || "";

    const getLocalizedPath = (targetLocale: string) => {
      if (!pathname) return `/${targetLocale}${search}${hash}`;

      const segments = pathname.split("/");
      // segments[1] es el prefijo de idioma (es / en / etc.)
      const knownLocales = routing.locales;
      if (segments[1] && knownLocales.includes(segments[1] as any)) {
        segments[1] = targetLocale;
        return `${segments.join("/")}${search}${hash}`;
      }

      const cleanPath = pathname === "/" ? "" : pathname;
      return `/${targetLocale}${cleanPath}${search}${hash}`;
    };

    const newPaths: Record<string, string> = {};
    routing.locales.forEach((l) => {
      newPaths[l] = getLocalizedPath(l);
    });
    setPaths(newPaths);
  }, []);

  return (
    <nav className="lang-switch" aria-label={label}>
      {routing.locales.map((l) => {
        // En el primer render (SSR y cliente antes del montaje), usamos el fallback
        // /l para no romper la hidratación y permitir que funcione sin JS.
        const href = paths[l] || `/${l}`;
        return (
          <Link
            key={l}
            href={href}
            className={current === l ? "active" : undefined}
            lang={l}
          >
            {l.toUpperCase()}
          </Link>
        );
      })}
    </nav>
  );
}
