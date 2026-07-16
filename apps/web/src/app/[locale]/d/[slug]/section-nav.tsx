"use client";

import { useEffect, useState } from "react";

type Section = { id: string; label: string; count?: number };

/**
 * Navegación lateral de la ficha, con resaltado de la sección visible.
 *
 * La ficha de una enfermedad con datos completos mide varias pantallas: sin un índice
 * hay que recorrerla entera para saber si hay genes. Esto convierte "hacer scroll a
 * ver qué hay" en "ver de un vistazo qué hay y saltar".
 *
 * Progresivamente mejorable: los enlaces son anclas normales y funcionan sin
 * JavaScript; el resaltado es lo único que necesita el observer.
 */
export function SectionNav({ sections }: { sections: Section[] }) {
  const [active, setActive] = useState<string | null>(sections[0]?.id ?? null);

  useEffect(() => {
    const elements = sections
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null);

    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // La sección activa es la más alta de las visibles: al hacer scroll hacia
        // abajo, marcar la última que entra da la sensación de ir un paso por delante.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      // El margen superior descuenta la cabecera; el inferior evita que una sección
      // que apenas asoma por abajo se lleve el foco.
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 }
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav className="section-nav" aria-label="Secciones">
      <ul>
        {sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              className={active === s.id ? "active" : undefined}
              aria-current={active === s.id ? "true" : undefined}
            >
              {s.label}
              {s.count !== undefined && <span className="nav-count">{s.count}</span>}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
