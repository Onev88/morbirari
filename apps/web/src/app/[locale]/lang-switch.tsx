"use client";

import { Link, usePathname, routing } from "@/i18n/routing";

/**
 * Conmutador de idioma que **conserva la página actual**.
 *
 * Antes era un `<a href="/en">` fijo: cambiar de idioma llevaba siempre al home. Aquí
 * `usePathname()` de next-intl da la ruta sin el prefijo de idioma (p. ej.
 * `/d/behcet-disease-orpha-117`), y `<Link locale>` la vuelve a prefijar con el otro
 * idioma, así que se recarga la misma ficha traducida.
 *
 * No arrastra la query (`?q=…` del buscador): traería un `useSearchParams` que obliga a
 * un límite de Suspense en las páginas estáticas. El caso que molesta —perder la ficha al
 * cambiar de idioma— queda resuelto.
 */
export function LangSwitch({ current, label }: { current: string; label: string }) {
  const pathname = usePathname();

  return (
    <nav className="lang-switch" aria-label={label}>
      {routing.locales.map((l) => (
        <Link
          key={l}
          href={pathname}
          locale={l}
          className={l === current ? "active" : undefined}
        >
          {l.toUpperCase()}
        </Link>
      ))}
    </nav>
  );
}
