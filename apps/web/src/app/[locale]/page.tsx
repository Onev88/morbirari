import { getTranslations, setRequestLocale } from "next-intl/server";
import { search } from "@/lib/search";
import { sanitizeDefinition } from "@/lib/sanitize";
import { getHomeRecentUpdates } from "@/lib/dashboard";

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
  const tDisease = await getTranslations("disease");
  const tDashboard = await getTranslations("dashboard");
  const tHome = await getTranslations("home");

  const query = (q ?? "").trim();
  const { hits, degraded } = query
    ? await search(query, locale)
    : { hits: [], degraded: false };

  const recentUpdates = !query ? await getHomeRecentUpdates(locale, 3) : { trials: [], drugs: [] };

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

      {!query && (
        <>
          <p className="hint">{t("empty")}</p>

          <section className="recent-updates-section" aria-labelledby="recent-updates-heading">
            <h2 id="recent-updates-heading">{tHome("recentUpdates")}</h2>

            <div className="recent-updates-grid">
              {/* Ensayos clínicos */}
              <div className="updates-column">
                <h3>{tHome("recentTrials")}</h3>
                {recentUpdates.trials.map((trial) => (
                  <a
                    key={trial.nct_id}
                    href={`/${locale}/d/${trial.disease_slug}`}
                    className="update-card update-card-trial"
                  >
                    <div className="update-disease-title">{trial.disease_label}</div>
                    <div className="update-content">{trial.trial_title}</div>
                    <div className="update-meta-row">
                      <span className={`update-badge update-badge-status-${trial.trial_status.toLowerCase() === 'recruiting' ? 'recruiting' : 'other'}`}>
                        {trial.trial_status.toLowerCase() === 'recruiting' ? tDashboard("statusRecruiting") : tDashboard("statusOther")}
                      </span>
                      <span className="update-date">
                        {tHome("updatedAt", { date: trial.trial_last_update ?? trial.trial_start_date ?? '—' })}
                      </span>
                    </div>
                  </a>
                ))}
                {recentUpdates.trials.length === 0 && (
                  <p className="dim">{tHome("noRecentUpdates")}</p>
                )}
              </div>

              {/* Designaciones de fármacos */}
              <div className="updates-column">
                <h3>{tHome("recentDrugs")}</h3>
                {recentUpdates.drugs.map((drug) => (
                  <a
                    key={drug.drug_id}
                    href={`/${locale}/d/${drug.disease_slug}`}
                    className="update-card update-card-drug"
                  >
                    <div className="update-disease-title">{drug.disease_label}</div>
                    <div className="update-content">
                      {drug.medicine_name ? `${drug.medicine_name} (${drug.active_substance})` : drug.active_substance}
                    </div>
                    <div className="update-meta-row">
                      <span className="update-badge update-badge-agency">{drug.agency}</span>
                      <span className="update-date">
                        {tHome("designatedAt", { date: drug.designation_date ?? '—' })}
                      </span>
                    </div>
                  </a>
                ))}
                {recentUpdates.drugs.length === 0 && (
                  <p className="dim">{tHome("noRecentUpdates")}</p>
                )}
              </div>
            </div>
          </section>
        </>
      )}

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
                      {tDisease("orphaCode")} {hit.orpha_code}
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
