import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { getDiseaseBySlug } from "@/lib/db";
import {
  getClassificationContext,
  getGenes,
  getGeographicPrevalence,
  getKeyFacts,
  getPhenotypes,
  getSubtypeGenes,
} from "@/lib/dashboard";
import { sanitizeDefinition } from "@/lib/sanitize";
import { PhenotypeList } from "./phenotype-list";

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

export default async function DiseasePage({ params }: Props) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  const detail = await getDiseaseBySlug(slug, locale);
  if (!detail) notFound();

  const [keyFacts, geography, phenotypes, genes, classifications] = await Promise.all([
    getKeyFacts(detail.disease.id, locale),
    getGeographicPrevalence(detail.disease.id, locale),
    getPhenotypes(detail.disease.id, locale),
    getGenes(detail.disease.id),
    getClassificationContext(detail.disease.orpha_code, locale),
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

  const definitionFellBack = detail.definition && detail.definitionLang !== locale;
  const untranslatedTerms = phenotypes.some((p) => !p.isTranslated);

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
        {detail.synonyms.slice(0, 3).map((s) => (
          <span key={s} className="badge neutral" lang={detail.labelLang}>
            {s}
          </span>
        ))}
      </div>

      {detail.disease.status === "retired" && <div className="notice">{t("retired")}</div>}
      <div className="notice">{tDisc("short")}</div>

      {/* Datos clave arriba: herencia, edad de inicio y prevalencia son lo que casi
          todo el mundo quiere saber antes que nada. */}
      <section className="block">
        <h2>{td("keyFacts")}</h2>
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
                  <div>{keyFacts.prevalenceClass}</div>
                  {/* El ámbito va siempre: una cifra de prevalencia sin decir dónde
                      ni qué mide no significa nada. */}
                  <div className="dim small">
                    {[keyFacts.prevalenceArea, keyFacts.prevalenceType]
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
      </section>

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
              dangerouslySetInnerHTML={{ __html: sanitizeDefinition(detail.definition) }}
            />
          </>
        ) : (
          <p className="hint">{t("noDefinition")}</p>
        )}
      </section>

      {geography.length > 0 && (
        <section className="block">
          <h2>{td("geography")}</h2>
          {/* Este matiz importa: sin él, un mapa de prevalencia se lee como "aquí no
              existe la enfermedad" cuando en realidad dice "aquí nadie la ha estudiado". */}
          <p className="section-intro">{td("geographyIntro")}</p>
          {/* Un bloque por tipo de medida. Mezclar prevalencia al nacer con
              prevalencia puntual en una sola tabla ordenada por valor haría que la
              barra comparase magnitudes que no son comparables. */}
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
                        {g.area}
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
        </section>
      )}

      {phenotypes.length > 0 && (
        <section className="block">
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
          />
        </section>
      )}

      {genes.length > 0 && (
        <section className="block">
          <h2>{td("genes")}</h2>
          {/* Distinguir causante de modificador no es un adorno: decir que 19 genes
              "causan" la fibrosis quística cuando solo CFTR lo hace sería falso. */}
          <p className="section-intro">{td("genesIntro")}</p>
          <ul className="gene-list">
            {genes.map((g) => {
              const causing = g.associationType?.toLowerCase().includes("disease-causing");
              const candidate = g.associationType?.toLowerCase().includes("candidate");
              return (
                <li key={g.symbol} className="gene">
                  <div className="gene-head">
                    <span className="gene-symbol">{g.symbol}</span>
                    <span className={`badge ${causing ? "" : "neutral"}`}>
                      {causing
                        ? td("geneCausing")
                        : candidate
                          ? td("geneCandidate")
                          : td("geneModifier")}
                    </span>
                  </div>
                  {g.name && <div className="gene-name" lang="en">{g.name}</div>}
                  <div className="gene-links">
                    {g.hgncId && <a href={HGNC_URL(g.hgncId)} rel="noreferrer" target="_blank">HGNC</a>}
                    {g.ensemblId && <a href={ENSEMBL_URL(g.ensemblId)} rel="noreferrer" target="_blank">Ensembl</a>}
                    {g.uniprotId && <a href={UNIPROT_URL(g.uniprotId)} rel="noreferrer" target="_blank">UniProt</a>}
                    {/* Solo el número MIM y un enlace. Nunca el texto de OMIM. */}
                    {g.omimId && <a href={OMIM_URL(g.omimId)} rel="noreferrer nofollow" target="_blank">OMIM {g.omimId}</a>}
                    {g.pmids?.map((p) => (
                      <a key={p} href={PUBMED_URL(p)} rel="noreferrer" target="_blank" className="pmid">
                        PMID {p}
                      </a>
                    ))}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {subtypeGenes.length > 0 && (
        <section className="block">
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

      {classifications.length > 0 && (
        <section className="block">
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
    </>
  );
}
