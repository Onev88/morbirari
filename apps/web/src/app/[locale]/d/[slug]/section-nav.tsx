"use client";

import { useEffect, useState } from "react";

type Section = { id: string; label: string; count?: number };

/**
 * Navegación de la ficha: muestra una sección a la vez.
 *
 * Por qué así y no ocultando en el servidor: **todo el contenido está en el HTML**, y
 * solo se oculta con CSS. Eso mantiene tres cosas que importan:
 *
 * 1. Google indexa la ficha entera. Es la principal vía de entrada al sitio: la gente
 *    busca el nombre de su enfermedad, y si los signos clínicos no están en el HTML,
 *    no se encuentran.
 * 2. Sin JavaScript se ve todo seguido, que es peor pero funciona. El fallo abre, no
 *    cierra.
 * 3. Ctrl+F del navegador encuentra lo que está en la sección visible; el resto sigue
 *    a un clic.
 *
 * La sección activa va en el hash de la URL, así que un enlace a una sección concreta
 * es compartible.
 */
export function SectionNav({ sections }: { sections: Section[] }) {
  const [active, setActive] = useState<string>(sections[0]?.id ?? "");
  // Hasta que el JS arranca no se oculta nada: si falla, la página queda completa en
  // vez de quedar en blanco.
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const fromHash = window.location.hash.slice(1);
    const initial = sections.some((s) => s.id === fromHash) ? fromHash : sections[0]?.id;
    if (initial) setActive(initial);
    setReady(true);
  }, [sections]);

  useEffect(() => {
    if (!ready) return;

    // El ocultado vive en el <body> vía atributo, y no en cada sección, para que el
    // CSS lo resuelva de una vez y no haya parpadeo.
    document.body.dataset.activeSection = active;
    document.body.dataset.tabsReady = "true";

    return () => {
      delete document.body.dataset.activeSection;
    };
  }, [active, ready]);

  useEffect(() => {
    const onHashChange = () => {
      const id = window.location.hash.slice(1);
      if (sections.some((s) => s.id === id)) setActive(id);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [sections]);

  function select(id: string) {
    setActive(id);
    // replaceState y no un salto de ancla: cambiar de pestaña no debe mover el scroll
    // ni llenar el historial de entradas.
    window.history.replaceState(null, "", `#${id}`);
  }

  return (
    <nav className="section-nav" aria-label="Secciones">
      <ul role="tablist">
        {sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              role="tab"
              aria-selected={ready && active === s.id}
              aria-controls={s.id}
              className={ready && active === s.id ? "active" : undefined}
              onClick={(e) => {
                e.preventDefault();
                select(s.id);
              }}
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
