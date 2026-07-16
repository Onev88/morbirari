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
};

const HPO_URL = (id: string) => `https://hpo.jax.org/browse/term/${id}`;
const INITIAL_GROUPS = 2;

/**
 * Signos clínicos agrupados por frecuencia.
 *
 * Se agrupa en lugar de listar en plano porque hay enfermedades con más de sesenta
 * signos y sin la frecuencia todos parecen igual de importantes, que es justo la
 * lectura equivocada. Por defecto se muestran los grupos más frecuentes; el resto
 * queda a un clic.
 */
export function PhenotypeList({ phenotypes, labels, showAllLabel }: Props) {
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

  return (
    <>
      {visible.map(([rank, list]) => (
        <div key={rank} className="pheno-group">
          <div className="pheno-freq">
            {labels[rank] ?? labels.unknown}
            <span className="dim"> · {list.length}</span>
          </div>
          <ul className="pheno-list">
            {list.map((p) => (
              <li key={p.hpoId}>
                <a href={HPO_URL(p.hpoId)} rel="noreferrer" target="_blank" title={p.hpoId}>
                  <span lang={p.isTranslated ? undefined : "en"}>{p.label}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {!expanded && hiddenCount > 0 && (
        <button type="button" className="link-button" onClick={() => setExpanded(true)}>
          {showAllLabel}
        </button>
      )}
    </>
  );
}
