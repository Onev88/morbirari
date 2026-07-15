import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { getDiseaseBySlug } from "@/lib/db";
import { sanitizeDefinition } from "@/lib/sanitize";

type Props = {
  params: Promise<{ locale: string; slug: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  const detail = await getDiseaseBySlug(slug, locale);
  if (!detail) return {};

  // El SEO no es cosmético aquí: la gente busca el nombre de su enfermedad en Google,
  // y esa es la principal vía de entrada al sitio.
  const description =
    detail.definition?.replace(/<[^>]+>/g, "").slice(0, 155) ??
    `ORPHA ${detail.disease.orpha_code}`;

  return {
    title: detail.preferredLabel,
    description,
    alternates: {
      canonical: `/${locale}/d/${slug}`,
      languages: { es: `/es/d/${slug}`, en: `/en/d/${slug}` },
    },
  };
}

const OMIM_URL = (id: string) => `https://omim.org/entry/${id}`;

export default async function DiseasePage({ params }: Props) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  const detail = await getDiseaseBySlug(slug, locale);
  if (!detail) notFound();

  const t = await getTranslations("disease");
  const tProv = await getTranslations("provenance");
  const tDisc = await getTranslations("disclaimer");
  const tSearch = await getTranslations("search");

  const labelFellBack = detail.labelLang !== locale;
  const definitionFellBack = detail.definition && detail.definitionLang !== locale;

  return (
    <>
      <a className="back-link" href={`/${locale}`}>
        ← {t("backToSearch")}
      </a>

      <div className="disease-header">
        <h1 lang={detail.labelLang}>{detail.preferredLabel}</h1>
      </div>

      <div className="badges">
        <span className="badge">
          {t("orphaCode")} {detail.disease.orpha_code}
        </span>
        {detail.disease.disease_type && (
          <span className="badge neutral">{detail.disease.disease_type}</span>
        )}
      </div>

      {detail.disease.status === "retired" && (
        <div className="notice">{t("retired")}</div>
      )}

      {labelFellBack && t("labelInEnglish") && (
        <div className="notice inline">{t("labelInEnglish")}</div>
      )}

      {/* Banda compacta en la ficha, además del pie persistente. */}
      <div className="notice">{tDisc("short")}</div>

      <section className="block">
        <h2>{t("definition")}</h2>
        {detail.definition ? (
          <>
            {definitionFellBack && t("definitionInEnglish") && (
              <div className="notice inline">{t("definitionInEnglish")}</div>
            )}
            <p
              className="definition"
              lang={detail.definitionLang ?? undefined}
              dangerouslySetInnerHTML={{
                __html: sanitizeDefinition(detail.definition),
              }}
            />
          </>
        ) : (
          <p className="hint">{t("noDefinition")}</p>
        )}
      </section>

      {detail.synonyms.length > 0 && (
        <section className="block">
          <h2>{t("synonyms")}</h2>
          <ul className="synonym-list">
            {detail.synonyms.map((s) => (
              <li key={s} lang={detail.labelLang}>
                {s}
              </li>
            ))}
          </ul>
        </section>
      )}

      {detail.xrefs.length > 0 && (
        <section className="block">
          <h2>{t("xrefs")}</h2>
          <table className="xref-table">
            <thead>
              <tr>
                <th>Vocabulario</th>
                <th>Identificador</th>
                <th>Relación</th>
              </tr>
            </thead>
            <tbody>
              {detail.xrefs.map((x) => (
                <tr key={`${x.source_ns}:${x.source_id}`}>
                  <td>{x.source_ns}</td>
                  <td>
                    {/*
                      Solo el identificador y un enlace profundo. Nunca el título de
                      OMIM: sus términos prohíben redistribuir su texto, pero un
                      número MIM es un hecho. Ver DATA_LICENSES.md.
                    */}
                    {x.source_ns === "OMIM" ? (
                      <a href={OMIM_URL(x.source_id)} rel="noreferrer nofollow" target="_blank">
                        {x.source_id}
                      </a>
                    ) : (
                      x.source_id
                    )}
                  </td>
                  <td className="xref-rel">
                    {t(`relation.${x.relation}` as never)}
                    {x.validated && ` · ${t("validated")}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {detail.disease.expert_link && (
        <section className="block">
          <a href={detail.disease.expert_link} rel="noreferrer" target="_blank">
            {t("expertLink")} →
          </a>
        </section>
      )}

      {/* La frescura va visible: es señal de confianza y mitigación de
          responsabilidad, y el modelo de procedencia ya nos la da gratis. */}
      <div className="provenance">
        {detail.attribution && <p>{detail.attribution}</p>}
        <p>
          {detail.sourceVersion && `${tProv("version")}: ${detail.sourceVersion} · `}
          {detail.retrievedAt &&
            tProv("retrieved", {
              date: new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(
                new Date(detail.retrievedAt)
              ),
            })}
        </p>
      </div>

      <p className="hint" style={{ marginTop: 24 }}>
        <a href={`/${locale}`}>{tSearch("submit")} →</a>
      </p>
    </>
  );
}
