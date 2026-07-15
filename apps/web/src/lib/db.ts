import postgres from "postgres";

/**
 * Acceso de solo lectura a Postgres.
 *
 * Este lado nunca emite DDL: Alembic (en el ETL) es el dueño único del esquema.
 * Ver docs/adr y etl/src/morbirari_etl/migrations/.
 */
const connectionString =
  process.env.DATABASE_URL ??
  "postgres://morbirari:morbirari_dev@localhost:5432/morbirari";

declare global {
  // eslint-disable-next-line no-var
  var __morbirari_sql: ReturnType<typeof postgres> | undefined;
}

export const sql =
  globalThis.__morbirari_sql ?? postgres(connectionString, { max: 5 });

if (process.env.NODE_ENV !== "production") {
  globalThis.__morbirari_sql = sql;
}

export type DiseaseRow = {
  id: string;
  slug: string;
  orpha_code: string;
  disease_type: string | null;
  status: string;
  expert_link: string | null;
};

export type LabelRow = {
  lang: string;
  label: string;
  label_type: string;
};

export type XrefRow = {
  source_ns: string;
  source_id: string;
  relation: string;
  validated: boolean;
};

export type DiseaseDetail = {
  disease: DiseaseRow;
  preferredLabel: string;
  labelLang: string;
  synonyms: string[];
  definition: string | null;
  definitionLang: string | null;
  xrefs: XrefRow[];
  attribution: string | null;
  sourceVersion: string | null;
  retrievedAt: Date | null;
};

/** Devuelve la etiqueta en el idioma pedido, cayendo a inglés si no existe. */
function pickLabels(rows: LabelRow[], lang: string) {
  const inLang = rows.filter((r) => r.lang === lang);
  const source = inLang.length > 0 ? inLang : rows.filter((r) => r.lang === "en");
  const preferred = source.find((r) => r.label_type === "preferred");
  const synonyms = source.filter((r) => r.label_type === "synonym").map((r) => r.label);
  return {
    preferred: preferred?.label ?? null,
    labelLang: source[0]?.lang ?? "en",
    synonyms,
  };
}

export async function getDiseaseBySlug(
  slug: string,
  lang: string
): Promise<DiseaseDetail | null> {
  const diseases = await sql<DiseaseRow[]>`
    SELECT id, slug, orpha_code, disease_type, status, expert_link
    FROM disease WHERE slug = ${slug} LIMIT 1
  `;
  const disease = diseases[0];
  if (!disease) return null;

  const labels = await sql<LabelRow[]>`
    SELECT lang, label, label_type FROM disease_label
    WHERE disease_id = ${disease.id} AND lang IN (${lang}, 'en')
  `;

  const contents = await sql<{ lang: string; body: string }[]>`
    SELECT lang, body FROM disease_content
    WHERE disease_id = ${disease.id} AND block_type = 'definition'
      AND lang IN (${lang}, 'en')
  `;

  const xrefs = await sql<XrefRow[]>`
    SELECT source_ns, source_id, relation, validated FROM disease_xref
    WHERE disease_id = ${disease.id} ORDER BY source_ns, source_id
  `;

  // La procedencia sostiene el aviso de frescura. Mostrarla no es decoración:
  // es señal de confianza y mitigación de responsabilidad.
  const prov = await sql<
    { attribution_text: string | null; source_version: string | null; retrieved_at: Date }[]
  >`
    SELECT s.attribution_text, p.source_version, p.retrieved_at
    FROM provenance p
    JOIN source s ON s.id = p.source_id
    JOIN disease_label dl ON dl.provenance_id = p.id
    WHERE dl.disease_id = ${disease.id}
    ORDER BY p.retrieved_at DESC LIMIT 1
  `;

  const { preferred, labelLang, synonyms } = pickLabels(labels, lang);
  const definition =
    contents.find((c) => c.lang === lang)?.body ??
    contents.find((c) => c.lang === "en")?.body ??
    null;
  const definitionLang = contents.find((c) => c.lang === lang)
    ? lang
    : contents.find((c) => c.lang === "en")
      ? "en"
      : null;

  return {
    disease,
    preferredLabel: preferred ?? `ORPHA ${disease.orpha_code}`,
    labelLang,
    synonyms,
    definition,
    definitionLang,
    xrefs,
    attribution: prov[0]?.attribution_text ?? null,
    sourceVersion: prov[0]?.source_version ?? null,
    retrievedAt: prov[0]?.retrieved_at ?? null,
  };
}

export type SearchHit = {
  slug: string;
  orpha_code: string;
  preferred_label: string;
  synonyms: string[];
  definition: string | null;
};

/**
 * Búsqueda de emergencia sobre Postgres con trigramas.
 *
 * Existe para que una caída de Meilisearch degrade el servicio en vez de romperlo.
 * Es peor que Meilisearch (sin tolerancia real a erratas, ranking pobre), pero
 * encuentra la enfermedad. Está codificada y probada a propósito: un fallback que
 * nunca se ejecuta es un fallback que no funciona.
 */
export async function searchFallback(
  query: string,
  lang: string,
  limit = 20
): Promise<SearchHit[]> {
  const rows = await sql<
    { slug: string; orpha_code: string; label: string; similarity: number }[]
  >`
    SELECT DISTINCT ON (d.id) d.slug, d.orpha_code, dl.label,
           similarity(mr_unaccent(lower(dl.label)), mr_unaccent(lower(${query}))) AS similarity
    FROM disease_label dl
    JOIN disease d ON d.id = dl.disease_id
    WHERE d.status = 'active'
      AND dl.lang IN (${lang}, 'en')
      AND mr_unaccent(lower(dl.label)) % mr_unaccent(lower(${query}))
    ORDER BY d.id, similarity DESC
    LIMIT ${limit}
  `;

  return rows
    .sort((a, b) => b.similarity - a.similarity)
    .map((r) => ({
      slug: r.slug,
      orpha_code: r.orpha_code,
      preferred_label: r.label,
      synonyms: [],
      definition: null,
    }));
}
