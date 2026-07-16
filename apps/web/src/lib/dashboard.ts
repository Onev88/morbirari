import { sql } from "./db";

/**
 * Consultas del dashboard de enfermedad.
 *
 * Todas caen a inglés cuando falta la traducción: más vale un dato en inglés que un
 * hueco. Cada bloque sabe en qué idioma acabó, para poder avisar en la interfaz.
 */

export type KeyFacts = {
  inheritance: string[];
  ageOfOnset: string[];
  prevalenceClass: string | null;
  prevalenceType: string | null;
  prevalenceArea: string | null;
};

export type GeoPrevalence = {
  area: string;
  prevalenceClass: string | null;
  value: number;
  validated: boolean;
};

/** Un grupo de prevalencias comparables entre sí: mismo tipo de medida. */
export type GeoGroup = {
  type: string;
  max: number;
  rows: GeoPrevalence[];
};

export type PhenotypeRow = {
  hpoId: string;
  label: string;
  isTranslated: boolean;
  frequencyRank: number | null;
  frequencyId: string | null;
};

export type GeneRow = {
  symbol: string;
  name: string | null;
  associationType: string | null;
  associationStatus: string | null;
  hgncId: string | null;
  ensemblId: string | null;
  uniprotId: string | null;
  omimId: string | null;
  pmids: string[] | null;
};

export type RelatedDisease = {
  slug: string;
  orphaCode: string;
  label: string;
};

export type ClassificationContext = {
  classificationName: string;
  parents: RelatedDisease[];
  children: RelatedDisease[];
};

/** Herencia, edad de inicio y prevalencia mundial: lo que casi todos miran primero. */
export async function getKeyFacts(diseaseId: string, lang: string): Promise<KeyFacts> {
  const attrs = await sql<{ attr_type: string; value: string; lang: string }[]>`
    SELECT attr_type, value, lang FROM disease_attribute
    WHERE disease_id = ${diseaseId} AND lang IN (${lang}, 'en')
  `;

  const pick = (type: string) => {
    const inLang = attrs.filter((a) => a.attr_type === type && a.lang === lang);
    const source = inLang.length > 0 ? inLang : attrs.filter((a) => a.attr_type === type && a.lang === "en");
    return [...new Set(source.map((a) => a.value))];
  };

  /*
   * Prevalencia de resumen, con su ámbito.
   *
   * No basta con buscar "Mundial": Orphanet no publica cifra mundial para muchas
   * enfermedades. La fibrosis quística, por ejemplo, solo tiene datos europeos y por
   * país, así que mirar solo "Mundial" mostraba «Sin datos» en una ficha con 40
   * registros de prevalencia detrás.
   *
   * Se cae a Europa y luego a cualquier ámbito, y siempre se dice cuál es: una cifra
   * sin ámbito no significa nada.
   */
  const prevalence = await sql<
    {
      prevalence_class: string | null;
      prevalence_type: string | null;
      geographic_area: string | null;
    }[]
  >`
    SELECT prevalence_class, prevalence_type, geographic_area FROM epidemiology
    WHERE disease_id = ${diseaseId} AND lang = ${lang}
      AND prevalence_class IS NOT NULL
      AND prevalence_class NOT IN ('Desconocido', 'Unknown')
    ORDER BY
      CASE
        WHEN geographic_area IN ('Mundial', 'Worldwide') THEN 0
        WHEN geographic_area IN ('Europa', 'Europe') THEN 1
        ELSE 2
      END,
      (validation_status = 'Validated') DESC,
      -- La prevalencia puntual describe mejor "cuánta gente la tiene ahora" que la
      -- prevalencia al nacer, que es una tasa de nacimientos.
      CASE WHEN prevalence_type IN ('Prevalencia puntual', 'Point prevalence') THEN 0 ELSE 1 END
    LIMIT 1
  `;

  return {
    inheritance: pick("inheritance"),
    ageOfOnset: pick("age_of_onset"),
    prevalenceClass: prevalence[0]?.prevalence_class ?? null,
    prevalenceType: prevalence[0]?.prevalence_type ?? null,
    prevalenceArea: prevalence[0]?.geographic_area ?? null,
  };
}

/**
 * Prevalencia por país o región, agrupada por tipo de medida.
 *
 * La agrupación no es estética, es correctitud: Orphanet mezcla prevalencia al nacer,
 * prevalencia puntual e incidencia anual para el mismo país. Ponerlas en una sola
 * lista ordenada por valor invita a comparar magnitudes distintas — una tasa de
 * nacimientos contra una prevalencia poblacional — y la barra lo haría parecer
 * legítimo. Cada grupo lleva su propio máximo, así que las barras solo comparan
 * dentro de medidas homogéneas.
 *
 * Se excluyen los agregados (Mundial, Europa): van en la tarjeta de resumen, y aquí
 * lo interesante es la distribución geográfica.
 */
export async function getGeographicPrevalence(
  diseaseId: string,
  lang: string
): Promise<GeoGroup[]> {
  const rows = await sql<
    {
      geographic_area: string;
      prevalence_type: string | null;
      prevalence_class: string | null;
      val_moy: string;
      validation_status: string | null;
    }[]
  >`
    SELECT geographic_area, prevalence_type, prevalence_class, val_moy, validation_status
    FROM epidemiology
    WHERE disease_id = ${diseaseId} AND lang = ${lang}
      AND geographic_area IS NOT NULL
      AND geographic_area NOT IN ('Mundial', 'Worldwide', 'Europa', 'Europe')
      AND val_moy IS NOT NULL AND val_moy <> '0.0'
      AND prevalence_type IS NOT NULL
    ORDER BY prevalence_type, (val_moy)::float DESC
  `;

  const groups = new Map<string, GeoPrevalence[]>();
  for (const r of rows) {
    const type = r.prevalence_type!;
    const list = groups.get(type) ?? [];
    list.push({
      area: r.geographic_area,
      prevalenceClass: r.prevalence_class,
      value: Number(r.val_moy),
      validated: r.validation_status === "Validated",
    });
    groups.set(type, list);
  }

  return [...groups.entries()]
    .map(([type, list]) => ({
      type,
      max: Math.max(...list.map((x) => x.value)),
      rows: list,
    }))
    // El grupo con más países primero: es el que mejor describe la distribución.
    .sort((a, b) => b.rows.length - a.rows.length);
}

/** Signos clínicos ordenados de más a menos frecuente. */
export async function getPhenotypes(diseaseId: string, lang: string): Promise<PhenotypeRow[]> {
  const rows = await sql<
    {
      hpo_id: string;
      label_en: string;
      translated: string | null;
      frequency_rank: number | null;
      frequency_id: string | null;
    }[]
  >`
    SELECT p.hpo_id, p.label_en, pl.label AS translated,
           dp.frequency_rank, dp.frequency_id
    FROM disease_phenotype dp
    JOIN phenotype p ON p.hpo_id = dp.hpo_id
    LEFT JOIN phenotype_label pl ON pl.hpo_id = p.hpo_id AND pl.lang = ${lang}
    WHERE dp.disease_id = ${diseaseId}
    ORDER BY dp.frequency_rank NULLS LAST, COALESCE(pl.label, p.label_en)
  `;

  return rows.map((r) => ({
    hpoId: r.hpo_id,
    label: r.translated ?? r.label_en,
    isTranslated: r.translated !== null,
    frequencyRank: r.frequency_rank,
    frequencyId: r.frequency_id,
  }));
}

/**
 * Genes asociados.
 *
 * El orden importa clínicamente: un gen causante y un gen modificador no son lo
 * mismo, y hay enfermedades con más de cien asociados. Los causantes van primero.
 */
export async function getGenes(diseaseId: string): Promise<GeneRow[]> {
  const rows = await sql<
    {
      symbol: string;
      name: string | null;
      association_type: string | null;
      association_status: string | null;
      hgnc_id: string | null;
      ensembl_id: string | null;
      uniprot_id: string | null;
      omim_id: string | null;
      source_pmids: string[] | null;
    }[]
  >`
    SELECT g.symbol, g.name, dg.association_type, dg.association_status,
           g.hgnc_id, g.ensembl_id, g.uniprot_id, g.omim_id, dg.source_pmids
    FROM disease_gene dg
    JOIN gene g ON g.id = dg.gene_id
    WHERE dg.disease_id = ${diseaseId}
    ORDER BY
      CASE WHEN dg.association_type ILIKE '%disease-causing%' THEN 0 ELSE 1 END,
      g.symbol
  `;

  return rows.map((r) => ({
    symbol: r.symbol,
    name: r.name,
    associationType: r.association_type,
    associationStatus: r.association_status,
    hgncId: r.hgnc_id,
    ensemblId: r.ensembl_id,
    uniprotId: r.uniprot_id,
    omimId: r.omim_id,
    pmids: r.source_pmids,
  }));
}

export type SubtypeGene = GeneRow & {
  fromDiseaseSlug: string;
  fromDiseaseLabel: string;
};

/**
 * Genes que Orphanet asocia a los subtipos, no a la enfermedad padre.
 *
 * Existe porque Orphanet modela así muchas enfermedades: el síndrome de Marfan
 * (ORPHA 558) no tiene ningún gen asociado, pero «Marfan tipo 1» tiene FBN1 y
 * «Marfan tipo 2» tiene TGFBR1/TGFBR2. Mostrar la ficha del padre sin genes es
 * técnicamente fiel al dato y engañoso para quien la lee: el gen está a un clic.
 *
 * Se muestran atribuidos a su subtipo, nunca fusionados con los del padre: decir que
 * FBN1 causa «síndrome de Marfan» a secas sería inventar una asociación que la fuente
 * no hace.
 */
export async function getSubtypeGenes(orphaCode: string, lang: string): Promise<SubtypeGene[]> {
  const rows = await sql<
    {
      symbol: string;
      name: string | null;
      association_type: string | null;
      association_status: string | null;
      hgnc_id: string | null;
      ensembl_id: string | null;
      uniprot_id: string | null;
      omim_id: string | null;
      source_pmids: string[] | null;
      slug: string;
      label: string;
    }[]
  >`
    SELECT DISTINCT ON (g.symbol, child.slug)
           g.symbol, g.name, dg.association_type, dg.association_status,
           g.hgnc_id, g.ensembl_id, g.uniprot_id, g.omim_id, dg.source_pmids,
           child.slug,
           COALESCE(dl_lang.label, dl_en.label, 'ORPHA ' || child.orpha_code) AS label
    FROM classification_edge e
    JOIN disease child ON child.orpha_code = e.child_orpha AND child.status = 'active'
    JOIN disease_gene dg ON dg.disease_id = child.id
    JOIN gene g ON g.id = dg.gene_id
    LEFT JOIN disease_label dl_lang ON dl_lang.disease_id = child.id
      AND dl_lang.lang = ${lang} AND dl_lang.label_type = 'preferred'
    LEFT JOIN disease_label dl_en ON dl_en.disease_id = child.id
      AND dl_en.lang = 'en' AND dl_en.label_type = 'preferred'
    WHERE e.parent_orpha = ${orphaCode}
      AND dg.association_type ILIKE '%disease-causing%'
    ORDER BY g.symbol, child.slug
    LIMIT 30
  `;

  return rows.map((r) => ({
    symbol: r.symbol,
    name: r.name,
    associationType: r.association_type,
    associationStatus: r.association_status,
    hgncId: r.hgnc_id,
    ensemblId: r.ensembl_id,
    uniprotId: r.uniprot_id,
    omimId: r.omim_id,
    pmids: r.source_pmids,
    fromDiseaseSlug: r.slug,
    fromDiseaseLabel: r.label,
  }));
}

/**
 * Dónde encaja la enfermedad y qué cuelga de ella.
 *
 * Las aristas se guardan por código ORPHA porque los árboles incluyen nodos de
 * agrupación que no están en `disease`; el JOIN aquí descarta esos huecos.
 */
export async function getClassificationContext(
  orphaCode: string,
  lang: string
): Promise<ClassificationContext[]> {
  const rows = await sql<
    {
      classification_name: string;
      parent_orpha: string | null;
      child_orpha: string;
      direction: string;
      slug: string;
      label: string;
      orpha_code: string;
    }[]
  >`
    WITH ctx AS (
      SELECT c.name AS classification_name, e.parent_orpha, e.child_orpha, 'parent' AS direction,
             e.parent_orpha AS other
      FROM classification_edge e
      JOIN classification c ON c.id = e.classification_id
      WHERE e.child_orpha = ${orphaCode} AND c.lang = ${lang} AND e.parent_orpha IS NOT NULL
      UNION ALL
      SELECT c.name, e.parent_orpha, e.child_orpha, 'child', e.child_orpha
      FROM classification_edge e
      JOIN classification c ON c.id = e.classification_id
      WHERE e.parent_orpha = ${orphaCode} AND c.lang = ${lang}
    )
    SELECT ctx.classification_name, ctx.parent_orpha, ctx.child_orpha, ctx.direction,
           d.slug, d.orpha_code,
           COALESCE(dl_lang.label, dl_en.label, 'ORPHA ' || d.orpha_code) AS label
    FROM ctx
    JOIN disease d ON d.orpha_code = ctx.other AND d.status = 'active'
    LEFT JOIN disease_label dl_lang ON dl_lang.disease_id = d.id
      AND dl_lang.lang = ${lang} AND dl_lang.label_type = 'preferred'
    LEFT JOIN disease_label dl_en ON dl_en.disease_id = d.id
      AND dl_en.lang = 'en' AND dl_en.label_type = 'preferred'
    ORDER BY ctx.classification_name, ctx.direction, label
  `;

  const byClassification = new Map<string, ClassificationContext>();
  for (const r of rows) {
    let entry = byClassification.get(r.classification_name);
    if (!entry) {
      entry = { classificationName: r.classification_name, parents: [], children: [] };
      byClassification.set(r.classification_name, entry);
    }
    const item: RelatedDisease = { slug: r.slug, orphaCode: r.orpha_code, label: r.label };
    const bucket = r.direction === "parent" ? entry.parents : entry.children;
    if (!bucket.some((x) => x.slug === item.slug)) bucket.push(item);
  }

  return [...byClassification.values()];
}
