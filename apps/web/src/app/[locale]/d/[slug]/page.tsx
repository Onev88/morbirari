import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { getDiseaseBySlug } from "@/lib/db";
import {
  buildRecentActivity,
  getClassificationContext,
  getDrugs,
  getGenes,
  getGeographicPrevalence,
  getJapanDesignation,
  getKeyFacts,
  getOrganizations,
  getOtherLanguageLabels,
  getPhenotypes,
  getSubtypeGenes,
  getTrials,
} from "@/lib/dashboard";
import { routing } from "@/i18n/routing";
import { sanitizeDefinition } from "@/lib/sanitize";
import { areaToAlpha2, countryName, isCountryArea, localizeArea } from "@/lib/geo";
import { CONTINENTS, ISO2_TO_CONTINENT } from "@/lib/continents";
import { parsePrevalenceClass } from "@/lib/prevalence";
import { PhenotypeList } from "./phenotype-list";
import { PrevalenceMap } from "./prevalence-map";
import { SectionNav } from "./section-nav";
import { TrialList, type TrialFilterGroup, type TrialVM } from "./trial-list";

type Props = {
  params: Promise<{ locale: string; slug: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  const detail = await getDiseaseBySlug(slug, locale);
  if (!detail) return {};

  // El SEO no es cosmético: la gente busca el nombre de su enfermedad en Google, y
  // esa es la principal vía de entrada al sitio.
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
const HGNC_URL = (id: string) => `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:${id}`;
const ENSEMBL_URL = (id: string) => `https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${id}`;
const UNIPROT_URL = (id: string) => `https://www.uniprot.org/uniprotkb/${id}`;
const PUBMED_URL = (id: string) => `https://pubmed.ncbi.nlm.nih.gov/${id}/`;

// Las fechas de las fuentes llegan como texto ISO parcial ('AAAA', 'AAAA-MM' o
// 'AAAA-MM-DD'). Para el feed basta mes y año, y se parsean los enteros a mano para no
// depender de husos: `new Date('2026-06')` interpretaría UTC y podría cambiar de mes.
function formatActivityDate(iso: string, locale: string): string {
  const [y, m] = iso.split("-");
  const year = Number(y);
  if (!year) return iso;
  const month = m ? Number(m) : null;
  const date = new Date(Date.UTC(year, month ? month - 1 : 0, 1));
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: month ? "short" : undefined,
    timeZone: "UTC",
  }).format(date);
}

export default async function DiseasePage({ params }: Props) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  const detail = await getDiseaseBySlug(slug, locale);
  if (!detail) notFound();

  const [
    keyFacts,
    geography,
    phenotypes,
    genes,
    classifications,
    trials,
    drugs,
    organizations,
    otherLangs,
    jpDesignation,
  ] = await Promise.all([
    getKeyFacts(detail.disease.id, locale),
    getGeographicPrevalence(detail.disease.id, locale),
    getPhenotypes(detail.disease.id, locale),
    getGenes(detail.disease.id),
    getClassificationContext(detail.disease.orpha_code, locale),
    getTrials(detail.disease.id),
    getDrugs(detail.disease.id),
    getOrganizations(detail.disease.id),
    getOtherLanguageLabels(detail.disease.id, [...routing.locales]),
    getJapanDesignation(detail.disease.id),
  ]);

  // Orphanet cuelga los genes de los subtipos, no siempre de la enfermedad padre.
  // Solo se consulta si el padre no tiene genes propios: así la ficha del síndrome de
  // Marfan deja de aparentar que no se conoce ningún gen implicado.
  const subtypeGenes =
    genes.length === 0 ? await getSubtypeGenes(detail.disease.orpha_code, locale) : [];

  const t = await getTranslations("disease");
  const td = await getTranslations("dashboard");
  const tProv = await getTranslations("provenance");
  const tDisc = await getTranslations("disclaimer");
  const tSearch = await getTranslations("search");

  const definitionFellBack = detail.definition && detail.definitionLang !== locale;
  const untranslatedTerms = phenotypes.some((p) => !p.isTranslated);
  const countryCount = new Set(
    geography.flatMap((g) => g.rows.map((r) => r.area).filter(isCountryArea))
  ).size;

  // El contador de la pestaña cuenta solo lo reclutando: es lo único a lo que alguien
  // puede acudir hoy. Prometer 40 ensayos y que estén todos cerrados es peor que no
  // prometer nada.
  const recruiting = trials.filter((t) => t.status === "RECRUITING");

  // Feed de actividad reciente: se compone de los ensayos y designaciones ya cargados,
  // ordenados por fecha. No es una fuente nueva ni una consulta extra (ADR 0005).
  const activity = buildRecentActivity(trials, drugs);

  // Vista de los ensayos para el filtro por lugar: cada uno con sus códigos ISO (para
  // filtrar en cliente) y sus nombres de país ya localizados (para pintar). La geografía
  // se resuelve aquí, en el servidor, para no llevar la librería de países al cliente.
  const trialVMs: TrialVM[] = trials.map((tr) => ({
    nctId: tr.nctId,
    title: tr.title,
    status: tr.status,
    phase: tr.phase,
    leadSponsor: tr.leadSponsor,
    countryCodes: [
      ...new Set(tr.countries.map((c) => areaToAlpha2(c)).filter((c): c is string => c !== null)),
    ],
    countryLabels: [...new Set(tr.countries.map((c) => localizeArea(c, locale)))],
    locations: tr.locations.map((l) => ({
      facility: l.facility,
      city: l.city,
      countryLabel: l.country ? localizeArea(l.country, locale) : null,
      countryCode: l.country ? areaToAlpha2(l.country) : null,
    })),
  }));

  // Opciones del filtro, agrupadas por continente y solo con los países presentes en los
  // centros de esta enfermedad.
  const presentCodes = new Set(trialVMs.flatMap((tr) => tr.countryCodes));
  const trialFilterGroups: TrialFilterGroup[] = CONTINENTS.flatMap((continent) => {
    const memberCodes = [...presentCodes].filter((c) => ISO2_TO_CONTINENT[c] === continent);
    if (memberCodes.length === 0) return [];
    return [
      {
        continent,
        label: tSearch(`continent.${continent}`),
        allLabel: tSearch("geoContinentAll", { name: tSearch(`continent.${continent}`) }),
        codes: memberCodes,
        countries: memberCodes
          .map((code) => ({ code, label: countryName(code, locale) }))
          .sort((a, b) => a.label.localeCompare(b.label, locale)),
      },
    ];
  });

  // Prevalencia en lenguaje llano («≈ 1 de cada N personas»); la cifra exacta de la
  // fuente se sigue enseñando aparte.
  const prevalencePlain = parsePrevalenceClass(keyFacts.prevalenceClass);
  const prevalencePer = prevalencePlain
    ? new Intl.NumberFormat(locale).format(prevalencePlain.per)
    : null;

  // El índice solo lista lo que existe: una sección vacía en la navegación es una
  // promesa incumplida.
  const sections = [
    // Definición y datos clave, unificados: la definición abre y los datos clave
    // (herencia, edad de inicio, prevalencia) van justo debajo, en la misma pestaña.
    // Se renderiza siempre, aunque no haya texto de definición.
    { id: "definicion", label: t("definition") },
    ...(activity.length > 0
      ? [{ id: "actividad", label: td("recentActivity"), count: activity.length }]
      : []),
    ...(geography.length > 0
      ? [{ id: "geografia", label: td("geography"), count: countryCount }]
      : []),
    ...(phenotypes.length > 0
      ? [{ id: "signos", label: td("phenotypes"), count: phenotypes.length }]
      : []),
    ...(genes.length > 0 || subtypeGenes.length > 0
      ? [{ id: "genes", label: td("genes"), count: genes.length || subtypeGenes.length }]
      : []),
    ...(trials.length > 0 || organizations.length > 0
      ? [
          {
            id: "donde-acudir",
            label: td("whereToGo"),
            count: trials.length > 0 ? recruiting.length : organizations.length,
          },
        ]
      : []),
    ...(drugs.length > 0 ? [{ id: "farmacos", label: td("drugs"), count: drugs.length }] : []),
    ...(classifications.length > 0 ? [{ id: "clasificacion", label: td("classification") }] : []),
    ...(detail.xrefs.length > 0
      ? [{ id: "referencias", label: td("codes"), count: detail.xrefs.length }]
      : []),
    // La bibliografía cierra siempre la ficha: toda página tiene, como mínimo,
    // Orphanet como fuente.
    { id: "fuentes", label: tProv("sources") },
  ];

  return (
    <div className="wrap wrap-wide disease-layout">
      <SectionNav sections={sections} />

      <div className="disease-main">
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
        {detail.synonyms.slice(0, 3).map((s) => (
          <span key={s} className="badge neutral" lang={detail.labelLang}>
            {s}
          </span>
        ))}
      </div>

      {detail.disease.status === "retired" && <div className="notice">{t("retired")}</div>}
      <div className="notice">{tDisc("short")}</div>

      {/* Definición + datos clave en una sola pestaña: primero qué es la enfermedad
          y luego lo que casi todo el mundo quiere saber antes que nada — herencia,
          edad de inicio y prevalencia. */}
      <section className="block" id="definicion">
        <h2>{t("definition")}</h2>
        {detail.definition ? (
          <>
            {definitionFellBack && t("definitionInEnglish") && (
              <div className="notice inline">{t("definitionInEnglish")}</div>
            )}
            <p
              className="definition"
              lang={detail.definitionLang ?? undefined}
              dangerouslySetInnerHTML={{ __html: sanitizeDefinition(detail.definition) }}
            />
          </>
        ) : (
          <p className="hint">{t("noDefinition")}</p>
        )}

        <h3 className="subsection-title">{td("keyFacts")}</h3>
        <div className="fact-grid">
          <div className="fact">
            <div className="fact-label">{td("inheritance")}</div>
            <div className="fact-value">
              {keyFacts.inheritance.length > 0 ? (
                keyFacts.inheritance.map((v) => <div key={v}>{v}</div>)
              ) : (
                <span className="dim">{td("noData")}</span>
              )}
            </div>
          </div>
          <div className="fact">
            <div className="fact-label">{td("ageOfOnset")}</div>
            <div className="fact-value">
              {keyFacts.ageOfOnset.length > 0 ? (
                keyFacts.ageOfOnset.map((v) => <div key={v}>{v}</div>)
              ) : (
                <span className="dim">{td("noData")}</span>
              )}
            </div>
          </div>
          <div className="fact">
            <div className="fact-label">{td("prevalence")}</div>
            <div className="fact-value">
              {keyFacts.prevalenceClass ? (
                <>
                  {/* Lo primero, la forma legible: «≈ 1 de cada N personas». */}
                  {prevalencePlain && prevalencePer ? (
                    <div className="prevalence-plain">
                      {prevalencePlain.kind === "about"
                        ? td("prevalencePlainAbout", { per: prevalencePer })
                        : prevalencePlain.kind === "more"
                          ? td("prevalencePlainMore", { per: prevalencePer })
                          : td("prevalencePlainLess", { per: prevalencePer })}
                    </div>
                  ) : (
                    <div>{keyFacts.prevalenceClass}</div>
                  )}
                  {/* Debajo, la cifra registrada exacta y su ámbito: una cifra sin
                      decir dónde ni qué mide no significa nada, y la aproximación no
                      sustituye al dato de la fuente. */}
                  <div className="dim small">
                    {[
                      prevalencePlain
                        ? `${td("prevalenceExact")}: ${keyFacts.prevalenceClass}`
                        : null,
                      keyFacts.prevalenceArea,
                      keyFacts.prevalenceType,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </div>
                </>
              ) : (
                <span className="dim">{td("noData")}</span>
              )}
            </div>
          </div>
        </div>

        {/* Nombres fuera de los idiomas de la interfaz. Hoy es japonés, de NANDO: el
            registro nipón es la única fuente que tenemos fuera del ámbito europeo, y
            permite que alguien busque 表皮水疱症 y llegue aquí. */}
        {otherLangs.length > 0 && (
          <div className="other-langs">
            {otherLangs.map((o) => (
              <div key={o.lang} className="other-lang">
                <span className="other-lang-tag">{o.lang.toUpperCase()}</span>
                <span lang={o.lang}>{o.labels.slice(0, 3).join(" · ")}</span>
              </div>
            ))}
            {jpDesignation && (
              <div className="other-lang">
                <span className="other-lang-tag">JP</span>
                <span>{td("jpDesignation", { number: jpDesignation })}</span>
              </div>
            )}
          </div>
        )}
      </section>

      {activity.length > 0 && (
        <section className="block" id="actividad">
          <h2>{td("recentActivity")}</h2>
          {/*
            Encuadre neutral (ADR 0005): «actividad investigadora», no «avances hacia la
            cura». Es lo que se mueve alrededor de la enfermedad —ensayos y designaciones—,
            en orden cronológico y sin ranking de relevancia: ordenar por «importancia»
            sería un juicio médico.
          */}
          <p className="section-intro">{td("recentActivityIntro")}</p>

          <ul className="activity-list">
            {activity.map((a) => {
              const date = formatActivityDate(a.date, locale);
              if (a.kind === "trial") {
                return (
                  <li key={`t-${a.nctId}`} className="activity activity--trial">
                    <div className="activity-head">
                      <span className="activity-type">{td("activityTrial")}</span>
                      {a.phase && <span className="badge neutral">{a.phase}</span>}
                      <span className="badge neutral">
                        {a.status === "RECRUITING"
                          ? td("statusRecruiting")
                          : a.status === "NOT_YET_RECRUITING"
                            ? td("statusNotYet")
                            : td("statusOther")}
                      </span>
                      <time className="activity-date" dateTime={a.date}>
                        {date}
                      </time>
                    </div>
                    <a
                      className="activity-title"
                      href={`https://clinicaltrials.gov/study/${a.nctId}`}
                      rel="noreferrer"
                      target="_blank"
                      lang="en"
                    >
                      {a.title}
                    </a>
                  </li>
                );
              }
              return (
                <li key={`d-${a.agency}-${a.name}-${a.date}`} className="activity activity--designation">
                  <div className="activity-head">
                    <span className="activity-type">{td("activityDesignation")}</span>
                    <span className="badge neutral">{a.agency}</span>
                    <time className="activity-date" dateTime={a.date}>
                      {date}
                    </time>
                  </div>
                  <div className="activity-title">
                    {td("activityDesignationLine")}
                    {a.name !== "—" && (
                      <>
                        {" · "}
                        {a.url ? (
                          <a href={a.url} rel="noreferrer" target="_blank" lang="en">
                            {a.name}
                          </a>
                        ) : (
                          <span lang="en">{a.name}</span>
                        )}
                      </>
                    )}
                  </div>
                  {/* La salvedad que no se aplana: designación ≠ aprobación (regla 17). */}
                  <div className="activity-meta">{td("activityDesignationNote")}</div>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {geography.length > 0 && (
        <section className="block" id="geografia">
          <h2>{td("geography")}</h2>
          {/* Este matiz importa: sin él, un mapa de prevalencia se lee como "aquí no
              existe la enfermedad" cuando en realidad dice "aquí nadie la ha estudiado". */}
          <p className="section-intro">{td("geographyIntro")}</p>

          {/* El mapa solo cuando hay bastantes países. Con dos o tres, un mapamundi
              es 117 KB de HTML para decir menos que una barra. */}
          {countryCount >= 4 && (
            <PrevalenceMap
              groups={geography}
              lang={locale}
              labels={{
                noData: td("noData"),
                legendLow: td("legendLow"),
                legendHigh: td("legendHigh"),
                zoomIn: td("mapZoomIn"),
                zoomOut: td("mapZoomOut"),
                reset: td("mapReset"),
                hint: td("mapHint"),
              }}
            />
          )}

          {/*
            La tabla no desaparece: es la lectura exacta, funciona sin color y es lo
            que recorre un lector de pantalla. Pero va plegada cuando hay mapa —
            ocupaba 2.500 px y repetía lo que el mapa ya cuenta. Si no hay mapa, la
            tabla ES la visualización y se muestra abierta.
          */}
          <details className="data-table-details" open={countryCount < 4}>
            <summary>
              {td("showTable")}
              <span className="dim"> · {geography.reduce((a, g) => a + g.rows.length, 0)}</span>
            </summary>
            {geography.map((group) => (
              <div key={group.type} className="geo-group">
                <div className="geo-type">
                  {group.type}
                  <span className="dim"> · {group.rows.length}</span>
                </div>
                <table className="geo-table">
                  <tbody>
                    {group.rows.map((g) => (
                      <tr key={`${group.type}-${g.area}`}>
                        <td>
                          {/* Orphanet deja los países en inglés incluso en los ficheros
                              en español; se traducen vía su código ISO. */}
                          {localizeArea(g.area, locale)}
                          {g.validated && (
                            <span className="tick" title={td("geographyValidated")}> ✓</span>
                          )}
                        </td>
                        <td className="num">
                          <div className="bar-cell">
                            <span className="bar-value">{g.value.toFixed(1)}</span>
                            <span
                              className="bar"
                              style={{ width: `${(g.value / group.max) * 100}%` }}
                              aria-hidden="true"
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </details>
        </section>
      )}

      {phenotypes.length > 0 && (
        <section className="block" id="signos">
          <h2>{td("phenotypes")}</h2>
          <p className="section-intro">{td("phenotypesIntro")}</p>
          {untranslatedTerms && td("termInEnglish") && (
            <div className="notice inline">{td("termInEnglish")}</div>
          )}
          <PhenotypeList
            phenotypes={phenotypes}
            labels={{
              1: td("frequency.1"),
              2: td("frequency.2"),
              3: td("frequency.3"),
              4: td("frequency.4"),
              5: td("frequency.5"),
              6: td("frequency.6"),
              unknown: td("frequency.unknown"),
            }}
            showAllLabel={td("showAllPhenotypes", { count: phenotypes.length })}
            showLessLabel={td("showLessPhenotypes")}
          />
        </section>
      )}

      {genes.length > 0 && (
        <section className="block" id="genes">
          <h2>{td("genes")}</h2>
          {/* Distinguir causante de modificador no es un adorno: decir que 19 genes
              "causan" la fibrosis quística cuando solo CFTR lo hace sería falso. */}
          <p className="section-intro">{td("genesIntro")}</p>
          {/*
            Tabla y no tarjetas: hay enfermedades con más de cien genes, y una tarjeta
            por gen convertía la sección en 2.000 px de scroll. En una tabla, el gen
            causante se localiza de un vistazo y los modificadores quedan como lista
            recorrible. La fila causante va destacada — es la distinción que importa.
          */}
          <table className="gene-table">
            <thead>
              <tr>
                <th>{td("geneSymbol")}</th>
                <th>{td("geneRole")}</th>
                <th>{td("geneLinks")}</th>
              </tr>
            </thead>
            <tbody>
              {genes.map((g) => {
                const causing = g.associationType?.toLowerCase().includes("disease-causing");
                const candidate = g.associationType?.toLowerCase().includes("candidate");
                return (
                  <tr key={g.symbol} className={causing ? "gene-causing" : undefined}>
                    <td>
                      <span className="gene-symbol">{g.symbol}</span>
                      {g.name && (
                        <div className="gene-name" lang="en">
                          {g.name}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${causing ? "" : "neutral"}`}>
                        {causing
                          ? td("geneCausing")
                          : candidate
                            ? td("geneCandidate")
                            : td("geneModifier")}
                      </span>
                    </td>
                    <td>
                      <div className="gene-links">
                        {g.hgncId && <a href={HGNC_URL(g.hgncId)} rel="noreferrer" target="_blank">HGNC</a>}
                        {g.ensemblId && <a href={ENSEMBL_URL(g.ensemblId)} rel="noreferrer" target="_blank">Ensembl</a>}
                        {g.uniprotId && <a href={UNIPROT_URL(g.uniprotId)} rel="noreferrer" target="_blank">UniProt</a>}
                        {/* Solo el número MIM y un enlace. Nunca el texto de OMIM. */}
                        {g.omimId && <a href={OMIM_URL(g.omimId)} rel="noreferrer nofollow" target="_blank">OMIM</a>}
                        {g.pmids?.map((p) => (
                          <a key={p} href={PUBMED_URL(p)} rel="noreferrer" target="_blank" className="pmid">
                            PMID
                          </a>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}

      {subtypeGenes.length > 0 && (
        <section className="block" id="genes">
          <h2>{td("genes")}</h2>
          {/* Atribuidos a su subtipo, nunca fusionados con el padre: Orphanet no dice
              que FBN1 cause "síndrome de Marfan" a secas, sino "Marfan tipo 1". */}
          <p className="section-intro">{td("subtypeGenesIntro")}</p>
          <ul className="gene-list">
            {subtypeGenes.map((g) => (
              <li key={`${g.symbol}-${g.fromDiseaseSlug}`} className="gene">
                <div className="gene-head">
                  <span className="gene-symbol">{g.symbol}</span>
                  <span className="badge">{td("geneCausing")}</span>
                </div>
                {g.name && (
                  <div className="gene-name" lang="en">
                    {g.name}
                  </div>
                )}
                <div className="gene-from">
                  {td("geneFrom")}{" "}
                  <a href={`/${locale}/d/${g.fromDiseaseSlug}`}>{g.fromDiseaseLabel}</a>
                </div>
                <div className="gene-links">
                  {g.hgncId && <a href={HGNC_URL(g.hgncId)} rel="noreferrer" target="_blank">HGNC</a>}
                  {g.ensemblId && <a href={ENSEMBL_URL(g.ensemblId)} rel="noreferrer" target="_blank">Ensembl</a>}
                  {g.uniprotId && <a href={UNIPROT_URL(g.uniprotId)} rel="noreferrer" target="_blank">UniProt</a>}
                  {g.omimId && <a href={OMIM_URL(g.omimId)} rel="noreferrer nofollow" target="_blank">OMIM {g.omimId}</a>}
                  {g.pmids?.map((p) => (
                    <a key={p} href={PUBMED_URL(p)} rel="noreferrer" target="_blank" className="pmid">
                      PMID {p}
                    </a>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(trials.length > 0 || organizations.length > 0) && (
        <section className="block" id="donde-acudir">
          <h2>{td("whereToGo")}</h2>

          {trials.length > 0 && (
            <>
              {/*
                Este encuadre no es un adorno legal: sin él, una lista de ensayos se lee
                como «aquí me curan». Un ensayo es investigación, tiene criterios de
                entrada y no es asistencia.
              */}
              <p className="section-intro">{td("whereToGoIntro")}</p>
              <div className="notice inline">{td("trialsWarning")}</div>

              <TrialList
                trials={trialVMs}
                filterGroups={trialFilterGroups}
                labels={{ geoLabel: tSearch("geoLabel"), geoAll: tSearch("geoAll") }}
              />
              <p className="hint">{td("trialsAttribution")}</p>
            </>
          )}

          {/*
            Asociaciones de pacientes (GARD, dominio público). Apoyo e información, NO
            atención médica (ADR 0006, regla 17). El buscador de especialistas o el
            registro que enlaza son de la propia organización, no una indicación nuestra.
          */}
          {organizations.length > 0 && (
            <>
              <h3 className="subsection-title">{td("organizations")}</h3>
              <p className="section-intro">{td("organizationsIntro")}</p>
              <ul className="org-list">
                {organizations.map((o) => (
                  <li key={o.name} className="org">
                    <div className="org-head">
                      {o.website ? (
                        <a
                          className="org-name"
                          href={o.website}
                          rel="noreferrer nofollow"
                          target="_blank"
                        >
                          {o.name}
                        </a>
                      ) : (
                        <span className="org-name">{o.name}</span>
                      )}
                      {o.country && (
                        <span className="dim small">{localizeArea(o.country, locale)}</span>
                      )}
                    </div>
                    {(o.expertDirectoryUrl || o.patientRegistryUrl) && (
                      <div className="org-links">
                        {o.expertDirectoryUrl && (
                          <a href={o.expertDirectoryUrl} rel="noreferrer nofollow" target="_blank">
                            {td("orgSpecialists")}
                          </a>
                        )}
                        {o.patientRegistryUrl && (
                          <a href={o.patientRegistryUrl} rel="noreferrer nofollow" target="_blank">
                            {td("orgRegistry")}
                          </a>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
              <p className="hint">{td("organizationsAttribution")}</p>
            </>
          )}
        </section>
      )}

      {drugs.length > 0 && (
        <section className="block" id="farmacos">
          <h2>{td("drugs")}</h2>
          {/*
            La advertencia va arriba y en caja, no en letra pequeña: «designación
            huérfana» suena a «hay tratamiento» y significa otra cosa muy distinta.
          */}
          <p className="section-intro">{td("drugsIntro")}</p>
          <div className="notice inline">{td("drugsWarning")}</div>

          <table className="drug-table">
            <thead>
              <tr>
                <th>{td("drugName")}</th>
                <th>{td("drugAgency")}</th>
                <th>{td("drugDate")}</th>
              </tr>
            </thead>
            <tbody>
              {drugs.map((d, i) => (
                <tr key={`${d.agency}-${i}`}>
                  <td>
                    {d.url ? (
                      <a href={d.url} rel="noreferrer" target="_blank" lang="en">
                        {d.medicineName || d.activeSubstance || "—"}
                      </a>
                    ) : (
                      <span lang="en">{d.medicineName || d.activeSubstance || "—"}</span>
                    )}
                    {d.activeSubstance && d.medicineName && (
                      <div className="dim small" lang="en">
                        {d.activeSubstance}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className="badge neutral">{d.agency}</span>
                  </td>
                  <td className="dim small">{d.designationDate}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {/* Se enseña con qué texto se emparejó: el vínculo es inferido y el lector
              tiene derecho a comprobarlo. */}
          {drugs[0]?.matchedOn && (
            <p className="hint">
              {td("drugsMatchedOn")}: <em lang="en">{drugs[0].matchedOn}</em>
            </p>
          )}
        </section>
      )}

      {classifications.length > 0 && (
        <section className="block" id="clasificacion">
          <h2>{td("classification")}</h2>
          <p className="section-intro">{td("classificationIntro")}</p>
          {classifications.map((c) => (
            <div key={c.classificationName} className="classification">
              <div className="classification-name">{c.classificationName}</div>
              {c.parents.length > 0 && (
                <div className="rel-group">
                  <span className="rel-label">{td("parents")}</span>
                  <ul className="rel-list">
                    {c.parents.map((p) => (
                      <li key={p.slug}>
                        <a href={`/${locale}/d/${p.slug}`}>{p.label}</a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {c.children.length > 0 && (
                <div className="rel-group">
                  <span className="rel-label">{td("children")}</span>
                  <ul className="rel-list">
                    {c.children.map((p) => (
                      <li key={p.slug}>
                        <a href={`/${locale}/d/${p.slug}`}>{p.label}</a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </section>
      )}

      {detail.xrefs.length > 0 && (
        <section className="block" id="referencias">
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

      {/*
        Bibliografía al cierre de la ficha: en vez de repartir atribuciones sueltas
        por la página, cada fuente que ha aportado algo se lista aquí, ordenada, con
        su enlace y qué parte de la ficha viene de ella. Solo aparece la fuente que
        de verdad se ha usado en esta enfermedad.
      */}
      <section className="block" id="fuentes">
        <h2>{tProv("sources")}</h2>
        <p className="section-intro">{tProv("sourcesIntro")}</p>
        <ul className="source-list">
          <li className="source">
            <a
              href={detail.disease.expert_link ?? "https://www.orpha.net"}
              rel="noreferrer"
              target="_blank"
            >
              Orphanet
            </a>
            <span className="source-desc">{tProv("src.orphanet")}</span>
          </li>
          {phenotypes.length > 0 && (
            <li className="source">
              <a href="https://hpo.jax.org" rel="noreferrer" target="_blank">
                Human Phenotype Ontology
              </a>
              <span className="source-desc">{tProv("src.hpo")}</span>
            </li>
          )}
          {trials.length > 0 && (
            <li className="source">
              <a href="https://clinicaltrials.gov" rel="noreferrer nofollow" target="_blank">
                ClinicalTrials.gov
              </a>
              <span className="source-desc">{tProv("src.clinicalTrials")}</span>
            </li>
          )}
          {drugs.length > 0 && (
            <li className="source">
              <span className="source-name">EMA · FDA</span>
              <span className="source-desc">{tProv("src.regulators")}</span>
            </li>
          )}
          {organizations.length > 0 && (
            <li className="source">
              <a href="https://rarediseases.info.nih.gov" rel="noreferrer nofollow" target="_blank">
                GARD
              </a>
              <span className="source-desc">{tProv("src.gard")}</span>
            </li>
          )}
          {(jpDesignation || otherLangs.some((o) => o.lang === "ja")) && (
            <li className="source">
              <a href="https://nanbyodata.jp" rel="noreferrer" target="_blank">
                NANDO · NanbyoData
              </a>
              <span className="source-desc">{tProv("src.nando")}</span>
            </li>
          )}
          {(genes.length > 0 || subtypeGenes.length > 0 || detail.xrefs.length > 0) && (
            <li className="source">
              <a href="https://www.genenames.org" rel="noreferrer" target="_blank">
                HGNC · Ensembl · UniProt · OMIM
              </a>
              <span className="source-desc">{tProv("src.identifiers")}</span>
            </li>
          )}
        </ul>

        {/* La frescura, visible: señal de confianza y mitigación de responsabilidad. */}
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
      </section>
      </div>
    </div>
  );
}
