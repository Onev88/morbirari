"use client";

import { useState } from "react";

type Phenotype = {
  hpoId: string;
  label: string;
  isTranslated: boolean;
  frequencyRank: number | null;
};

type Props = {
  phenotypes: Phenotype[];
  labels: Record<string, string>;
  showAllLabel: string;
  showLessLabel: string;
};

const HPO_URL = (id: string) => `https://hpo.jax.org/browse/term/${id}`;
const INITIAL_GROUPS = 2;

/*
 * Rank 6 es «Excluyente (0%)»: no es el extremo bajo de la escala, es lo contrario
 * de la escala. Significa "este signo NO aparece en esta enfermedad", que es un dato
 * clínicamente útil pero de otra naturaleza. Pintarlo como el azul más pálido de la
 * rampa lo haría leer como "muy poco frecuente", que es justo lo que no es. Va en
 * gris y con su propia explicación.
 */
const EXCLUDED_RANK = 6;

export function PhenotypeList({ phenotypes, labels, showAllLabel, showLessLabel }: Props) {
  const [expanded, setExpanded] = useState(false);

  const groups = new Map<string, Phenotype[]>();
  for (const p of phenotypes) {
    const key = p.frequencyRank ? String(p.frequencyRank) : "unknown";
    const list = groups.get(key) ?? [];
    list.push(p);
    groups.set(key, list);
  }

  const ordered = [...groups.entries()].sort(([a], [b]) => {
    if (a === "unknown") return 1;
    if (b === "unknown") return -1;
    return Number(a) - Number(b);
  });

  const visible = expanded ? ordered : ordered.slice(0, INITIAL_GROUPS);
  const hiddenCount = ordered
    .slice(INITIAL_GROUPS)
    .reduce((acc, [, list]) => acc + list.length, 0);

  const maxInGroup = Math.max(...ordered.map(([, list]) => list.length));

  return (
    <div className="pheno-block">
      {visible.map(([rank, list]) => {
        const isExcluded = rank === String(EXCLUDED_RANK);
        const rampClass = isExcluded || rank === "unknown" ? "ord-none" : `ord-${rank}`;
        return (
          <div key={rank} className="pheno-group">
            <div className="pheno-header">
              {/* La muestra de color es lo que ata el grupo a la escala; sin ella el
                  color de los chips no significaría nada. */}
              <span className={`swatch ${rampClass}`} aria-hidden="true" />
              <span className="pheno-freq">{labels[rank] ?? labels.unknown}</span>
              <span className="pheno-count">{list.length}</span>
              {/* Barra proporcional: cuántos signos hay en cada nivel de frecuencia,
                  legible sin leer los números. */}
              <span className="pheno-bar-track" aria-hidden="true">
                <span
                  className={`pheno-bar ${rampClass}`}
                  style={{ width: `${(list.length / maxInGroup) * 100}%` }}
                />
              </span>
            </div>
            <ul className="pheno-list">
              {list.map((p) => (
                <li key={p.hpoId}>
                  <a
                    href={HPO_URL(p.hpoId)}
                    rel="noreferrer"
                    target="_blank"
                    title={p.hpoId}
                    className={isExcluded ? "excluded" : undefined}
                  >
                    <span lang={p.isTranslated ? undefined : "en"}>{p.label}</span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        );
      })}

      {hiddenCount > 0 && (
        <button
          type="button"
          className="link-button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? showLessLabel : showAllLabel}
        </button>
      )}
    </div>
  );
}
