"""Carga de los productos que alimentan el dashboard.

Todo lo de aquí se cuelga de enfermedades que ya existen (cargadas por el adaptador de
nomenclatura). Un producto científico que menciona un ORPHA desconocido se ignora en
silencio: es señal de que la nomenclatura va desfasada, no un motivo para romper.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from morbirari_etl.db import (
    HPO_FREQUENCY_RANK,
    Classification,
    ClassificationEdge,
    Disease,
    DiseaseAttribute,
    DiseaseGene,
    DiseasePhenotype,
    Epidemiology,
    Gene,
    Phenotype,
    PhenotypeLabel,
    Provenance,
)
from morbirari_etl.loaders.postgres import assert_no_omim_text
from morbirari_etl.sources.hpo.translations import StagedTranslation
from morbirari_etl.sources.orphanet.classifications import StagedClassification
from morbirari_etl.sources.orphanet.science import (
    StagedAttribute,
    StagedGene,
    StagedPhenotype,
    StagedPrevalence,
)


def disease_ids_by_orpha(session: Session) -> dict[str, object]:
    """Índice ORPHA -> id interno. El corpus son ~11.600 filas: cabe en memoria."""
    return {
        code: did
        for code, did in session.execute(select(Disease.orpha_code, Disease.id)).all()
    }


def _batched(items: Iterable, size: int = 1000) -> Iterator[list]:
    batch: list = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _dedupe(values: list[dict], *key_fields: str) -> list[dict]:
    """Elimina duplicados por clave, quedándose con la última aparición.

    Postgres rechaza un ON CONFLICT DO UPDATE que afecte a la misma fila dos veces en
    la misma sentencia (CardinalityViolation). Como las fuentes sí traen registros
    repetidos, hay que resolverlo antes de enviar el lote.
    """
    seen: dict[tuple, dict] = {}
    for v in values:
        seen[tuple(v[k] for k in key_fields)] = v
    return list(seen.values())


def load_epidemiology(
    session: Session,
    rows: Iterable[StagedPrevalence],
    lang: str,
    prov: Provenance,
    index: dict[str, object],
) -> int:
    count = 0
    for batch in _batched(rows):
        values = []
        for r in batch:
            disease_id = index.get(r.orpha_code)
            if disease_id is None:
                continue
            values.append(
                {
                    "disease_id": disease_id,
                    "lang": lang,
                    "orphanet_prevalence_id": r.orphanet_prevalence_id,
                    "prevalence_type": r.prevalence_type,
                    "prevalence_qualification": r.prevalence_qualification,
                    "prevalence_class": r.prevalence_class,
                    "val_moy": r.val_moy,
                    "geographic_area": r.geographic_area,
                    "validation_status": r.validation_status,
                    "source": r.source,
                    "provenance_id": prov.id,
                }
            )
        values = _dedupe(values, "orphanet_prevalence_id", "lang")
        if values:
            session.execute(
                insert(Epidemiology)
                .values(values)
                .on_conflict_do_update(
                    constraint="uq_epidemiology",
                    set_={
                        "prevalence_class": insert(Epidemiology).excluded.prevalence_class,
                        "val_moy": insert(Epidemiology).excluded.val_moy,
                        "geographic_area": insert(Epidemiology).excluded.geographic_area,
                        "provenance_id": prov.id,
                    },
                )
            )
            count += len(values)
    return count


def load_attributes(
    session: Session,
    rows: Iterable[StagedAttribute],
    lang: str,
    prov: Provenance,
    index: dict[str, object],
) -> int:
    count = 0
    for batch in _batched(rows):
        values = []
        for r in batch:
            disease_id = index.get(r.orpha_code)
            if disease_id is None:
                continue
            values.append(
                {
                    "disease_id": disease_id,
                    "lang": lang,
                    "attr_type": r.attr_type,
                    "orphanet_attr_id": r.orphanet_attr_id,
                    "value": r.value,
                    "provenance_id": prov.id,
                }
            )
        values = _dedupe(values, "disease_id", "lang", "attr_type", "orphanet_attr_id")
        if values:
            session.execute(
                insert(DiseaseAttribute)
                .values(values)
                .on_conflict_do_update(
                    constraint="uq_disease_attribute",
                    set_={"value": insert(DiseaseAttribute).excluded.value},
                )
            )
            count += len(values)
    return count


def load_phenotypes(
    session: Session,
    rows: Iterable[StagedPhenotype],
    prov: Provenance,
    index: dict[str, object],
) -> tuple[int, int]:
    """Carga términos HPO y sus asociaciones. Devuelve (términos, asociaciones).

    Orphanet publica algunas anotaciones repetidas con frecuencias contradictorias:
    en la versión de julio de 2026 hay 38 parejas (enfermedad, término) de 116.664 que
    aparecen dos veces, por ejemplo el mismo signo marcado a la vez como «Frecuente» y
    «Ocasional». Postgres además rechaza un ON CONFLICT DO UPDATE que toque la misma
    fila dos veces en la misma sentencia, así que hay que resolver el conflicto aquí.

    Nos quedamos con la frecuencia más alta (rank menor). Es una elección: ante datos
    contradictorios preferimos no minimizar un signo que la fuente considera común. Lo
    importante es que sea determinista, no que sea perfecta — afecta al 0,03% de las
    anotaciones.
    """
    terms: dict[str, str] = {}
    # clave (disease_id, hpo_id) -> fila, resolviendo duplicados sobre la marcha
    resolved: dict[tuple, dict] = {}

    for r in rows:
        terms.setdefault(r.hpo_id, r.hpo_term_en)

        disease_id = index.get(r.orpha_code)
        if disease_id is None:
            continue

        key = (disease_id, r.hpo_id)
        rank = HPO_FREQUENCY_RANK.get(r.frequency_id or "")
        existing = resolved.get(key)
        if existing is not None:
            # rank menor = más frecuente. None (desconocido) nunca gana a un rank real.
            old = existing["frequency_rank"]
            if rank is None or (old is not None and old <= rank):
                continue

        resolved[key] = {
            "disease_id": disease_id,
            "hpo_id": r.hpo_id,
            "frequency_id": r.frequency_id,
            "frequency_rank": rank,
            "diagnostic_criteria": r.diagnostic_criteria,
            "provenance_id": prov.id,
        }

    # Los términos primero: las asociaciones tienen FK contra ellos.
    for batch in _batched(({"hpo_id": k, "label_en": v} for k, v in terms.items())):
        session.execute(
            insert(Phenotype)
            .values(batch)
            .on_conflict_do_update(
                index_elements=[Phenotype.hpo_id],
                set_={"label_en": insert(Phenotype).excluded.label_en},
            )
        )

    assoc_count = 0
    for batch in _batched(resolved.values()):
        session.execute(
            insert(DiseasePhenotype)
            .values(batch)
            .on_conflict_do_update(
                constraint="uq_disease_phenotype",
                set_={
                    "frequency_id": insert(DiseasePhenotype).excluded.frequency_id,
                    "frequency_rank": insert(DiseasePhenotype).excluded.frequency_rank,
                },
            )
        )
        assoc_count += len(batch)

    return len(terms), assoc_count


def load_phenotype_translations(
    session: Session, rows: Iterable[StagedTranslation], prov: Provenance
) -> int:
    """Solo traduce términos HPO que ya usamos; el fichero trae toda la ontología."""
    known = {
        hpo_id for (hpo_id,) in session.execute(select(Phenotype.hpo_id)).all()
    }
    count = 0
    for batch in _batched(rows):
        values = _dedupe(
            [
                {
                    "hpo_id": r.hpo_id,
                    "lang": r.lang,
                    "label": r.label,
                    "translation_status": r.status,
                    "provenance_id": prov.id,
                }
                for r in batch
                if r.hpo_id in known
            ],
            "hpo_id",
            "lang",
        )
        if values:
            session.execute(
                insert(PhenotypeLabel)
                .values(values)
                .on_conflict_do_update(
                    constraint="uq_phenotype_label",
                    set_={"label": insert(PhenotypeLabel).excluded.label},
                )
            )
            count += len(values)
    return count


def load_genes(
    session: Session,
    rows: Iterable[StagedGene],
    prov: Provenance,
    index: dict[str, object],
) -> tuple[int, int]:
    """Carga genes y asociaciones. Devuelve (genes, asociaciones)."""
    staged = list(rows)

    # Un gen aparece en muchas enfermedades: deduplicar por símbolo antes de insertar.
    by_symbol: dict[str, StagedGene] = {}
    for g in staged:
        by_symbol.setdefault(g.symbol, g)

    for batch in _batched(by_symbol.values()):
        values = []
        for g in batch:
            # El número MIM del gen es un identificador; su texto nunca entra.
            assert_no_omim_text("OMIM", None)
            values.append(
                {
                    "symbol": g.symbol,
                    "name": g.name,
                    "gene_type": g.gene_type,
                    "hgnc_id": g.hgnc_id,
                    "ensembl_id": g.ensembl_id,
                    "uniprot_id": g.uniprot_id,
                    "omim_id": g.omim_id,
                    "synonyms": g.synonyms or None,
                }
            )
        if values:
            session.execute(
                insert(Gene)
                .values(values)
                .on_conflict_do_update(
                    index_elements=[Gene.symbol],
                    set_={
                        "name": insert(Gene).excluded.name,
                        "hgnc_id": insert(Gene).excluded.hgnc_id,
                        "ensembl_id": insert(Gene).excluded.ensembl_id,
                        "uniprot_id": insert(Gene).excluded.uniprot_id,
                        "omim_id": insert(Gene).excluded.omim_id,
                        "synonyms": insert(Gene).excluded.synonyms,
                    },
                )
            )

    gene_ids = {
        symbol: gid for symbol, gid in session.execute(select(Gene.symbol, Gene.id)).all()
    }

    assoc = 0
    for batch in _batched(staged):
        values = []
        for g in batch:
            disease_id = index.get(g.orpha_code)
            gene_id = gene_ids.get(g.symbol)
            if disease_id is None or gene_id is None:
                continue
            values.append(
                {
                    "disease_id": disease_id,
                    "gene_id": gene_id,
                    "association_type": g.association_type,
                    "association_status": g.association_status,
                    "source_pmids": g.source_pmids or None,
                    "provenance_id": prov.id,
                }
            )
        values = _dedupe(values, "disease_id", "gene_id")
        if values:
            session.execute(
                insert(DiseaseGene)
                .values(values)
                .on_conflict_do_update(
                    constraint="uq_disease_gene",
                    set_={
                        "association_type": insert(DiseaseGene).excluded.association_type,
                        "association_status": insert(DiseaseGene).excluded.association_status,
                        "source_pmids": insert(DiseaseGene).excluded.source_pmids,
                    },
                )
            )
            assoc += len(values)

    return len(by_symbol), assoc


def load_classifications(
    session: Session, items: Iterable[StagedClassification], prov: Provenance
) -> tuple[int, int]:
    """Carga clasificaciones y sus aristas. Devuelve (clasificaciones, aristas)."""
    n_class = n_edges = 0

    for item in items:
        classification_id = session.execute(
            insert(Classification)
            .values(
                orpha_root=item.orpha_root,
                lang=item.lang,
                name=item.name,
                provenance_id=prov.id,
            )
            .on_conflict_do_update(
                constraint="uq_classification",
                set_={"name": item.name, "provenance_id": prov.id},
            )
            .returning(Classification.id)
        ).scalar_one()
        n_class += 1

        for batch in _batched(item.edges, 2000):
            values = [
                {
                    "classification_id": classification_id,
                    "parent_orpha": parent,
                    "child_orpha": child,
                }
                for parent, child in batch
            ]
            if values:
                session.execute(
                    insert(ClassificationEdge)
                    .values(values)
                    .on_conflict_do_nothing(constraint="uq_classification_edge")
                )
                n_edges += len(values)

    return n_class, n_edges
