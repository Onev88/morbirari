"use client";

import { useEffect, useState, useRef } from "react";
import { Link, usePathname, routing } from "@/i18n/routing";
import { useTranslations } from "next-intl";

/**
 * Conmutador de idioma en cascada (dropdown) que conserva la página actual, la búsqueda (?q=...)
 * y el hash (#...) de sección activa.
 *
 * Utiliza 'usePathname' de next-intl para resolver la página limpia en el servidor (evitando
 * hydration mismatch), y concatena la query y el hash del cliente asíncronamente tras el montaje.
 */
export function LangSwitch({ current, label }: { current: string; label: string }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [urlSuffix, setUrlSuffix] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Captura del sufijo del cliente (search params + hash) y cierre al hacer clic fuera
  useEffect(() => {
    const search = window.location.search || "";
    const hash = window.location.hash || "";
    setUrlSuffix(`${search}${hash}`);

    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div
      className="lang-switch-container"
      ref={containerRef}
      onKeyDown={(e) => {
        if (e.key === "Escape") setIsOpen(false);
      }}
    >
      <button
        type="button"
        className="lang-switch-trigger"
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-label={label}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="lang-icon" aria-hidden="true">🌐</span>
        <span className="lang-current-label">{current.toUpperCase()}</span>
        <span className="lang-arrow" aria-hidden="true">▾</span>
      </button>

      <ul className={`lang-switch-menu ${isOpen ? "open" : ""}`} role="menu">
        {routing.locales.map((l) => {
          // El href se compone del pathname (sin locale) + la búsqueda/hash.
          // El componente Link de next-intl le inyecta el locale correspondiente automáticamente.
          const href = `${pathname}${urlSuffix}`;
          return (
            <li key={l} role="none">
              <Link
                href={href}
                locale={l}
                className={current === l ? "active" : undefined}
                lang={l}
                role="menuitem"
                onClick={() => setIsOpen(false)}
              >
                <span className="lang-code">{l.toUpperCase()}</span>
                <span className="lang-full-name">{t(`lang.${l}`)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
