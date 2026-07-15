import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
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

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          <header className="site-header">
            <div className="wrap">
              <a className="brand" href={`/${locale}`}>
                {tSite("name")}
              </a>
              <span className="tagline">{tSite("tagline")}</span>
              <nav className="lang-switch" aria-label={tNav("language")}>
                {routing.locales.map((l) => (
                  <a key={l} href={`/${l}`} className={l === locale ? "active" : ""}>
                    {l.toUpperCase()}
                  </a>
                ))}
              </nav>
            </div>
          </header>

          <main>
            <div className="wrap">{children}</div>
          </main>

          {/*
            El disclaimer es un pie persistente, no un modal: un modal perjudica el
            SEO y la usabilidad, y este sitio necesita ser encontrable porque la
            gente busca el nombre de su enfermedad en Google.
          */}
          <footer className="site-footer">
            <div className="wrap">
              <h2>{t("title")}</h2>
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
              <p>
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
