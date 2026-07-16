import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { ThemeToggle } from "./theme-toggle";
import { DisclaimerBanner } from "./disclaimer-banner";
import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "site" });
  return {
    title: { default: t("name"), template: `%s · ${t("name")}` },
    description: t("tagline"),
  };
}

/*
 * Fija el tema antes del primer pintado, leyendo la elección guardada. Va en línea y
 * como primer nodo del <body> para que corra antes de que se pinte el contenido: si
 * esperara a React, habría un parpadeo de tema claro→oscuro en cada carga. Si no hay
 * nada guardado no toca nada y manda `prefers-color-scheme` (modo automático).
 */
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark'){document.documentElement.dataset.theme=t;}}catch(e){}})();`;

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as never)) notFound();

  setRequestLocale(locale);
  const messages = await getMessages();
  const t = await getTranslations({ locale, namespace: "disclaimer" });
  const tSite = await getTranslations({ locale, namespace: "site" });
  const tNav = await getTranslations({ locale, namespace: "nav" });
  const tTheme = await getTranslations({ locale, namespace: "theme" });

  return (
    <html lang={locale}>
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />

        {/* Primer elemento tabulable: saltar la cabecera y la navegación e ir al
            contenido. Solo visible al recibir foco con el teclado. */}
        <a className="skip-link" href="#content">
          {tNav("skipToContent")}
        </a>

        <NextIntlClientProvider messages={messages}>
          <header className="site-header">
            <div className="wrap">
              <a className="brand" href={`/${locale}`}>
                {tSite("name")}
              </a>
              <span className="tagline">{tSite("tagline")}</span>
              <div className="header-tools">
                <ThemeToggle
                  labels={{
                    toggle: tTheme("toggle"),
                    auto: tTheme("auto"),
                    light: tTheme("light"),
                    dark: tTheme("dark"),
                  }}
                />
                <nav className="lang-switch" aria-label={tNav("language")}>
                  {routing.locales.map((l) => (
                    <a key={l} href={`/${l}`} className={l === locale ? "active" : ""}>
                      {l.toUpperCase()}
                    </a>
                  ))}
                </nav>
              </div>
            </div>
          </header>

          {/*
            El ancho lo fija cada página: el buscador quiere una columna estrecha y
            legible; la ficha necesita sitio para el mapa y las tablas.
          */}
          <main id="content" tabIndex={-1}>
            {children}
          </main>

          {/*
            El aviso legal aparece como banner una vez por sesión y, al aceptarse, se
            pliega. La copia completa vive siempre en el footer (HTML del servidor):
            un modal perjudica el SEO y la usabilidad, y este sitio necesita ser
            encontrable porque la gente busca el nombre de su enfermedad en Google.
          */}
          <DisclaimerBanner
            labels={{
              title: t("title"),
              lead: t("bannerLead"),
              accept: t("accept"),
              items: [t("notAdvice"), t("noDiagnosis"), t("noRelationship"), t("thirdParty"), t("consult")],
              emergency: t("emergency"),
            }}
          />

          <footer className="site-footer">
            <div className="wrap">
              {/* Plegado por defecto: ocupa una línea salvo que se quiera releer. */}
              <details className="footer-disclaimer">
                <summary>{t("title")}</summary>
                <ul>
                  <li>{t("notAdvice")}</li>
                  <li>{t("noDiagnosis")}</li>
                  <li>{t("noRelationship")}</li>
                  <li>{t("thirdParty")}</li>
                  <li>{t("consult")}</li>
                  <li>
                    <strong>{t("emergency")}</strong>
                  </li>
                </ul>
              </details>
              <p className="footer-attribution">
                Orphanet: an online rare disease and orphan drug data base. © INSERM
                1999. Available on{" "}
                <a href="http://www.orpha.net" rel="noreferrer">
                  http://www.orpha.net
                </a>
                . CC BY 4.0.
              </p>
            </div>
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
