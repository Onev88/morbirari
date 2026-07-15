import { defineRouting } from "next-intl/routing";
import { createNavigation } from "next-intl/navigation";

/**
 * Fase 1: EN + ES. Orphanet publica en 9 idiomas (cs, nl, en, fr, de, it, pl, pt, es);
 * añadir uno debe ser tocar esta lista, el fichero de mensajes y reindexar.
 *
 * El locale va en la ruta y no en una cookie: además de ser mejor para SEO, mantener
 * el sitio sin estado significa no tener cookies de seguimiento y, por tanto, ningún
 * banner de consentimiento.
 */
export const routing = defineRouting({
  locales: ["en", "es"],
  defaultLocale: "es",
});

export type Locale = (typeof routing.locales)[number];

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
