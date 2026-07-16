import { getTranslations, setRequestLocale } from "next-intl/server";
import { search } from "@/lib/search";
import { sanitizeDefinition } from "@/lib/sanitize";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string }>;
};

export default async function SearchPage({ params, searchParams }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  const { q } = await searchParams;
  const t = await getTranslations("search");
  const tDisc = await getTranslations("disclaimer");

  const query = (q ?? "").trim();
  const { hits, degraded } = query
    ? await search(query, locale)
    : { hits: [], degraded: false };

  return (
    <div className="wrap">
      {/* Un formulario GET simple: sin JavaScript de cliente, la búsqueda es
          enlazable y compartible, y funciona sin cookies. */}
      <form className="search-form" action={`/${locale}`} method="get" role="search">
        <input
          type="search"
          name="q"
          defaultValue={query}
          placeholder={t("placeholder")}
          aria-label={t("submit")}
          autoFocus
        />
        <button type="submit">{t("submit")}</button>
      </form>
      <p className="hint">{t("hint")}</p>

      {degraded && <div className="notice">{t("degraded")}</div>}

      {!query && <p className="hint">{t("empty")}</p>}

      {query && (
        <>
          <p className="result-count">
            {t("count", { count: hits.length })} · {t("resultsFor", { query })}
          </p>

          {hits.length === 0 ? (
            <p>{t("noResults")}</p>
          ) : (
            <ul className="result-list">
              {hits.map((hit) => (
                <li key={hit.slug} className="result-item">
                  <a href={`/${locale}/d/${hit.slug}`}>
                    <div className="result-title">{hit.preferred_label}</div>
                    <div className="result-meta">
                      ORPHA {hit.orpha_code}
                      {hit.synonyms?.length > 0 && ` · ${hit.synonyms.slice(0, 3).join(" · ")}`}
                    </div>
                    {hit.definition && (
                      <div
                        className="result-snippet"
                        dangerouslySetInnerHTML={{
                          __html: sanitizeDefinition(hit.definition),
                        }}
                      />
                    )}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <p className="hint" style={{ marginTop: 32 }}>
        {tDisc("short")}
      </p>
    </div>
  );
}
