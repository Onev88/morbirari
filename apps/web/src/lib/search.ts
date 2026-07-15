import { MeiliSearch } from "meilisearch";
import { searchFallback, type SearchHit } from "./db";

const client = new MeiliSearch({
  host: process.env.MEILI_URL ?? "http://localhost:7700",
  apiKey: process.env.MEILI_MASTER_KEY ?? "morbirari_dev_master_key",
});

export type SearchResult = {
  hits: SearchHit[];
  degraded: boolean;
};

function indexName(lang: string) {
  return `diseases_${lang}`;
}

/**
 * Busca en el índice del idioma y, si el idioma no es inglés, federa con el índice
 * inglés.
 *
 * La federación no es un extra: los clínicos usan los nombres en inglés en cualquier
 * idioma de interfaz, y muchas enfermedades solo tienen literatura en inglés.
 * No detectamos el idioma de la consulta — el locale de la interfaz elige el índice.
 */
export async function search(
  query: string,
  lang: string,
  limit = 20
): Promise<SearchResult> {
  if (!query.trim()) return { hits: [], degraded: false };

  try {
    const indexes = lang === "en" ? [lang] : [lang, "en"];
    const responses = await Promise.all(
      indexes.map((l) =>
        client.index(indexName(l)).search(query, {
          limit,
          attributesToRetrieve: [
            "slug",
            "orpha_code",
            "preferred_label",
            "synonyms",
            "definition",
          ],
        })
      )
    );

    // Fusión preservando el orden de cada índice y priorizando el idioma de la
    // interfaz: el primer índice ya viene ordenado por relevancia.
    const seen = new Set<string>();
    const hits: SearchHit[] = [];
    for (const response of responses) {
      for (const hit of response.hits as unknown as SearchHit[]) {
        if (seen.has(hit.slug)) continue;
        seen.add(hit.slug);
        hits.push(hit);
      }
    }
    return { hits: hits.slice(0, limit), degraded: false };
  } catch {
    // Meilisearch caído: degradar a Postgres en vez de romper la página.
    const hits = await searchFallback(query, lang, limit);
    return { hits, degraded: true };
  }
}
