"use client";

import { Link, usePathname, useRouter, routing } from "@/i18n/routing";

/**
 * Conmutador de idioma que **conserva la página actual y la pestaña abierta**.
 *
 * Antes era un `<a href="/en">` fijo: cambiar de idioma llevaba siempre al home. Aquí
 * `usePathname()` de next-intl da la ruta sin el prefijo de idioma (p. ej.
 * `/d/behcet-disease-orpha-117`), y `<Link locale>` la vuelve a prefijar con el otro
 * idioma, así que se recarga la misma ficha traducida.
 *
 * La pestaña activa de la ficha vive en el **hash** (`#signos-clinicos`, …), que
 * `usePathname()` no incluye: sin más, cambiar de idioma volvía siempre a la primera
 * sección. Por eso, cuando hay hash, interceptamos el clic y navegamos con el hash
 * incluido; al recargar la ficha, `SectionNav` lo lee y restaura la pestaña.
 *
 * El hash se lee **en el momento del clic**, no en render: lo actualiza `SectionNav` con
 * `history.replaceState`, que no dispara ningún evento al que suscribirse, y leerlo así
 * evita además el `useSearchParams`/Suspense que ensuciaría las páginas estáticas. Sin
 * JavaScript el `<Link>` navega igual (sin hash): se pierde la pestaña, pero el fallo abre.
 *
 * La query (`?q=…` del buscador) sigue sin arrastrarse, por el mismo motivo de Suspense.
 */
export function LangSwitch({ current, label }: { current: string; label: string }) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <nav className="lang-switch" aria-label={label}>
      {routing.locales.map((l) => (
        <Link
          key={l}
          href={pathname}
          locale={l}
          className={l === current ? "active" : undefined}
          onClick={(e) => {
            const hash = window.location.hash;
            if (!hash) return; // sin hash, el Link hace su navegación normal
            e.preventDefault();
            router.push(`${pathname}${hash}`, { locale: l });
          }}
        >
          {l.toUpperCase()}
        </Link>
      ))}
    </nav>
  );
}
