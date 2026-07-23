"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

/**
 * Conmutador de idioma robusto en el cliente.
 *
 * Utiliza 'window.location' en un hook 'useEffect' para obtener la ruta, los parámetros
 * de búsqueda (?q=...) y el hash/pestaña (#...) reales del navegador en tiempo de ejecución.
 *
 * Esto evita los problemas de hidratación de Next.js y los desajustes del lado del servidor (SSR),
 * garantizando que al cambiar de idioma:
 *   1. Se permanezca en la misma ficha (ej. de /es/d/slug a /en/d/slug).
 *   2. Se preserve el término de búsqueda actual (ej. ?q=cystic+fibrosis).
 *   3. Se conserve la pestaña o sección activa (ej. #ensayos).
 */
export function LangSwitch({ current, label }: { current: string; label: string }) {
  const [paths, setPaths] = useState<{ es: string; en: string }>({
    es: "/es",
    en: "/en",
  });

  useEffect(() => {
    const pathname = window.location.pathname;
    const search = window.location.search || "";
    const hash = window.location.hash || "";

    const getLocalizedPath = (targetLocale: string) => {
      if (!pathname) return `/${targetLocale}${search}${hash}`;
      
      const segments = pathname.split("/");
      // segments[1] es el prefijo de idioma (es / en)
      if (segments[1] === "es" || segments[1] === "en") {
        segments[1] = targetLocale;
        return `${segments.join("/")}${search}${hash}`;
      }
      
      const cleanPath = pathname === "/" ? "" : pathname;
      return `/${targetLocale}${cleanPath}${search}${hash}`;
    };

    setPaths({
      es: getLocalizedPath("es"),
      en: getLocalizedPath("en"),
    });
  }, []);

  return (
    <nav className="lang-switch" aria-label={label}>
      <Link
        href={paths.es}
        className={current === "es" ? "active" : undefined}
      >
        ES
      </Link>
      <Link
        href={paths.en}
        className={current === "en" ? "active" : undefined}
      >
        EN
      </Link>
    </nav>
  );
}
