"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

/*
 * Lista de ensayos con filtro por lugar (país o continente), como mejora progresiva.
 *
 * Todo el HTML de los ensayos se sirve desde el servidor (indexable, regla 19). El filtro
 * es un <select> que oculta los que no tienen un centro en el lugar elegido; **sin
 * JavaScript no filtra y se ven todos** — el fallo abre, no cierra. El filtro mira dónde
 * están los centros (un hecho literal), no dónde "ocurre" la enfermedad, así que aquí no
 * hace falta el encuadre epidemiológico de la búsqueda.
 *
 * La geografía viene ya resuelta del servidor: cada ensayo trae sus códigos ISO y cada
 * opción del desplegable los códigos que empareja. El cliente solo hace intersección de
 * conjuntos, sin librería de países en el bundle.
 */

export type TrialLocationVM = {
  facility: string | null;
  city: string | null;
  countryLabel: string | null;
  countryCode: string | null;
};

export type TrialVM = {
  nctId: string;
  title: string;
  status: string;
  phase: string | null;
  leadSponsor: string | null;
  countryCodes: string[];
  countryLabels: string[];
  locations: TrialLocationVM[];
};

export type TrialFilterGroup = {
  continent: string;
  label: string;
  allLabel: string;
  codes: string[];
  countries: { code: string; label: string }[];
};

type Props = {
  trials: TrialVM[];
  filterGroups: TrialFilterGroup[];
  labels: { geoLabel: string; geoAll: string };
};

export function TrialList({ trials, filterGroups, labels }: Props) {
  const t = useTranslations("dashboard");
  const [codes, setCodes] = useState<string[]>([]);

  // Solo tiene sentido filtrar si hay al menos dos países entre los centros.
  const distinctCodes = new Set(trials.flatMap((tr) => tr.countryCodes));
  const showFilter = filterGroups.length > 0 && distinctCodes.size >= 2;

  const filtering = codes.length > 0;
  const visible = filtering
    ? trials.filter((tr) => tr.countryCodes.some((c) => codes.includes(c)))
    : trials;

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const selected = e.target.selectedOptions[0];
    const value = selected?.dataset.codes ?? "";
    setCodes(value ? value.split(" ") : []);
  }

  function renderLocation(l: TrialLocationVM, key: string, highlight: boolean) {
    return (
      <li key={key} className={highlight ? "location-match" : undefined}>
        {l.facility && <span className="facility">{l.facility}</span>}
        <span className="dim">{[l.city, l.countryLabel].filter(Boolean).join(", ")}</span>
      </li>
    );
  }

  return (
    <>
      {showFilter && (
        <div className="trial-filter">
          <label className="trial-filter-label">
            {labels.geoLabel}
            <select
              className="geo-select"
              defaultValue=""
              onChange={onChange}
              aria-label={labels.geoLabel}
            >
              <option value="" data-codes="">
                {labels.geoAll}
              </option>
              {filterGroups.map((g) => (
                <optgroup key={g.continent} label={g.label}>
                  <option value={`c:${g.continent}`} data-codes={g.codes.join(" ")}>
                    {g.allLabel}
                  </option>
                  {g.countries.map((c) => (
                    <option key={c.code} value={`a:${c.code}`} data-codes={c.code}>
                      {c.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          {codes.length > 0 && (
            <span className="trial-filter-count dim small">
              {t("trialsShowing", { shown: visible.length, total: trials.length })}
            </span>
          )}
        </div>
      )}

      {visible.length === 0 ? (
        <p className="hint">{t("trialsFilterEmpty")}</p>
      ) : (
        <ul className="trial-list">
          {visible.map((tr) => {
            // Al filtrar, se separan los centros que coinciden del resto.
            const matching = filtering
              ? tr.locations.filter((l) => l.countryCode && codes.includes(l.countryCode))
              : [];
            const rest = filtering
              ? tr.locations.filter((l) => !(l.countryCode && codes.includes(l.countryCode)))
              : tr.locations;
            const highlight = filtering && matching.length > 0;

            return (
              <li key={tr.nctId} className="trial">
                <div className="trial-head">
                  <span className={`badge ${tr.status === "RECRUITING" ? "" : "neutral"}`}>
                    {tr.status === "RECRUITING"
                      ? t("statusRecruiting")
                      : tr.status === "NOT_YET_RECRUITING"
                        ? t("statusNotYet")
                        : t("statusOther")}
                  </span>
                  {tr.phase && <span className="badge neutral">{tr.phase}</span>}
                </div>
                <a
                  className="trial-title"
                  href={`https://clinicaltrials.gov/study/${tr.nctId}`}
                  rel="noreferrer"
                  target="_blank"
                  lang="en"
                >
                  {tr.title}
                </a>
                {tr.leadSponsor && (
                  <div className="trial-sponsor">
                    {t("sponsor")}: <strong>{tr.leadSponsor}</strong>
                  </div>
                )}

                {/* El centro que coincide con el filtro se muestra directo y destacado,
                    para no obligar a abrir 108 centros a buscar el que importa. El resto
                    queda plegado. Sin filtro, todos van juntos como antes. */}
                {highlight && (
                  <ul className="location-list location-list--match">
                    {matching.map((l, i) => renderLocation(l, `m-${tr.nctId}-${i}`, true))}
                  </ul>
                )}

                {rest.length > 0 &&
                  (highlight ? (
                    <details className="trial-locations trial-locations--rest">
                      <summary>{t("otherCentres", { count: rest.length })}</summary>
                      <ul className="location-list">
                        {rest.map((l, i) => renderLocation(l, `r-${tr.nctId}-${i}`, false))}
                      </ul>
                    </details>
                  ) : (
                    <details className="trial-locations">
                      <summary>
                        {t("centres", { count: tr.locations.length })}
                        {tr.countryLabels.length > 0 && (
                          <span className="dim">
                            {" · "}
                            {tr.countryLabels.slice(0, 4).join(", ")}
                            {tr.countryLabels.length > 4 && ` +${tr.countryLabels.length - 4}`}
                          </span>
                        )}
                      </summary>
                      <ul className="location-list">
                        {tr.locations.map((l, i) => renderLocation(l, `a-${tr.nctId}-${i}`, false))}
                      </ul>
                    </details>
                  ))}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
