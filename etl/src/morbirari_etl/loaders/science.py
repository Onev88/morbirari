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
    DiseaseDrug,
    DiseaseGene,
    DiseaseLabel,
    DiseasePhenotype,
    DiseaseTrial,
    DiseaseXref,
    Epidemiology,
    Gene,
    OrphanDrug,
    Phenotype,
    PhenotypeLabel,
    Provenance,
    Trial,
    TrialLocation,
)
from morbirari_etl.loaders.postgres import assert_no_omim_text
from morbirari_etl.sources.clinicaltrials.trials import StagedTrial
from morbirari_etl.sources.ema.orphan_drugs import StagedDrug, normalize
from morbirari_etl.sources.hpo.translations import StagedTranslation
from morbirari_etl.sources.nando.japan import StagedNando
from morbirari_etl.sources.orphanet.classifications import StagedClassification
from morbirari_etl.sources.orphanet.science import (
    StagedAlignment,
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


def load_alignments(
    session: Session,
    rows: Iterable[StagedAlignment],
    prov: Provenance,
    index: dict[str, object],
) -> int:
    """Carga referencias cruzadas a otros vocabularios."""
    count = 0
    for batch in _batched(rows, 2000):
        values = []
        for r in batch:
            disease_id = index.get(r.orpha_code)
            if disease_id is None:
                continue
            # Solo identificadores cruzan esta frontera; nunca texto de OMIM.
            assert_no_omim_text(r.source_ns, None)
            values.append(
                {
                    "disease_id": disease_id,
                    "source_ns": r.source_ns,
                    "source_id": r.source_id,
                    "relation": r.relation,
                    "validated": r.validated,
                    "provenance_id": prov.id,
                }
            )
        values = _dedupe(values, "disease_id", "source_ns", "source_id")
        if values:
            session.execute(
                insert(DiseaseXref)
                .values(values)
                .on_conflict_do_update(
                    constraint="uq_xref",
                    set_={
                        "relation": insert(DiseaseXref).excluded.relation,
                        "validated": insert(DiseaseXref).excluded.validated,
                    },
                )
            )
            count += len(values)
    return count


def load_trials(
    session: Session,
    trials: Iterable[StagedTrial],
    disease_id,
    mesh_id: str,
    prov: Provenance,
) -> int:
    """Carga ensayos, sus centros y el vínculo con la enfermedad."""
    count = 0
    for batch in _batched(trials, 200):
        trial_values = _dedupe(
            [
                {
                    "nct_id": t.nct_id,
                    "title": t.title,
                    "status": t.status,
                    "phase": t.phase,
                    "study_type": t.study_type,
                    "lead_sponsor": t.lead_sponsor,
                    "sponsor_class": t.sponsor_class,
                    "enrollment": t.enrollment,
                    "start_date": t.start_date,
                    "last_update": t.last_update,
                    "provenance_id": prov.id,
                }
                for t in batch
            ],
            "nct_id",
        )
        if not trial_values:
            continue

        session.execute(
            insert(Trial)
            .values(trial_values)
            .on_conflict_do_update(
                index_elements=[Trial.nct_id],
                set_={
                    "status": insert(Trial).excluded.status,
                    "title": insert(Trial).excluded.title,
                    "last_update": insert(Trial).excluded.last_update,
                },
            )
        )

        loc_values = _dedupe(
            [
                {
                    "nct_id": t.nct_id,
                    "facility": loc.facility,
                    "city": loc.city,
                    "country": loc.country,
                    "status": loc.status,
                }
                for t in batch
                for loc in t.locations
                if loc.facility or loc.city
            ],
            "nct_id",
            "facility",
            "city",
        )
        if loc_values:
            session.execute(
                insert(TrialLocation)
                .values(loc_values)
                .on_conflict_do_nothing(constraint="uq_trial_location")
            )

        link_values = _dedupe(
            [
                {
                    "disease_id": disease_id,
                    "nct_id": t.nct_id,
                    # El vínculo es por código MeSH, no por texto: más fiable, pero
                    # sigue siendo inferencia nuestra y la interfaz lo dice.
                    "match_method": "mesh",
                    "match_confidence": "high",
                    "matched_on": mesh_id,
                    "provenance_id": prov.id,
                }
                for t in batch
            ],
            "disease_id",
            "nct_id",
        )
        session.execute(
            insert(DiseaseTrial)
            .values(link_values)
            .on_conflict_do_nothing(constraint="uq_disease_trial")
        )
        count += len(trial_values)

    return count


def load_nando(
    session: Session,
    rows: Iterable[StagedNando],
    prov: Provenance,
    index: dict[str, object],
) -> tuple[int, int]:
    """Etiquetas japonesas y designación oficial. Devuelve (etiquetas, designaciones)."""
    labels: list[dict] = []
    attrs: list[dict] = []

    for r in rows:
        disease_id = index.get(r.orpha_code)
        if disease_id is None:
            continue

        labels.append(
            {
                "disease_id": disease_id,
                "lang": "ja",
                "label": r.label_ja,
                "label_type": "preferred",
                "provenance_id": prov.id,
            }
        )
        # El hiragana entra como sinónimo: es la misma enfermedad escrita de otro
        # modo, y es como la busca mucha gente en japonés.
        if r.label_hira:
            labels.append(
                {
                    "disease_id": disease_id,
                    "lang": "ja",
                    "label": r.label_hira,
                    "label_type": "synonym",
                    "provenance_id": prov.id,
                }
            )

        if r.notification_number:
            attrs.append(
                {
                    "disease_id": disease_id,
                    "lang": "ja",
                    "attr_type": "jp_designation",
                    "orphanet_attr_id": r.nando_id,
                    "value": r.notification_number,
                    "provenance_id": prov.id,
                }
            )

    n_labels = 0
    for batch in _batched(labels):
        batch = _dedupe(batch, "disease_id", "lang", "label", "label_type")
        session.execute(
            insert(DiseaseLabel).values(batch).on_conflict_do_nothing(constraint="uq_label")
        )
        n_labels += len(batch)

    n_attrs = 0
    for batch in _batched(attrs):
        batch = _dedupe(batch, "disease_id", "lang", "attr_type", "orphanet_attr_id")
        session.execute(
            insert(DiseaseAttribute)
            .values(batch)
            .on_conflict_do_update(
                constraint="uq_disease_attribute",
                set_={"value": insert(DiseaseAttribute).excluded.value},
            )
        )
        n_attrs += len(batch)

    return n_labels, n_attrs


def load_orphan_drugs(
    session: Session,
    drugs: Iterable[StagedDrug],
    agency: str,
    prov: Provenance,
) -> tuple[int, int]:
    """Carga designaciones huérfanas y las empareja con enfermedades.

    Devuelve (designaciones, vínculos).

    Sobre el emparejamiento: solo coincidencia **exacta** del texto normalizado
    contra una etiqueta de la enfermedad. Nada de aproximado, a propósito. Un
    fármaco atribuido a la enfermedad equivocada es peor que un fármaco no
    mostrado: el primero desinforma a alguien que busca tratamiento para lo suyo,
    el segundo solo omite. Ante la duda, no se enlaza.
    """
    staged = list(drugs)

    n_drugs = 0
    for batch in _batched(staged):
        values = _dedupe(
            [
                {
                    "agency": agency,
                    "designation_number": d.designation_number,
                    "medicine_name": d.medicine_name,
                    "active_substance": d.active_substance,
                    "intended_use": d.intended_use,
                    "status": d.status,
                    "designation_date": d.designation_date,
                    "url": d.url,
                    "provenance_id": prov.id,
                }
                for d in batch
            ],
            "agency",
            "designation_number",
        )
        if values:
            session.execute(
                insert(OrphanDrug)
                .values(values)
                .on_conflict_do_update(
                    constraint="uq_orphan_drug",
                    set_={
                        "status": insert(OrphanDrug).excluded.status,
                        "medicine_name": insert(OrphanDrug).excluded.medicine_name,
                    },
                )
            )
            n_drugs += len(values)

    # Índice etiqueta normalizada -> disease_id. Se usan todas las etiquetas en
    # inglés (preferidas y sinónimos): la EMA escribe en inglés, y muchas veces usa
    # el sinónimo y no el nombre preferido.
    label_index: dict[str, object] = {}
    for disease_id, label in session.execute(
        select(DiseaseLabel.disease_id, DiseaseLabel.label).where(DiseaseLabel.lang == "en")
    ):
        key = normalize(label)
        if key and key not in label_index:
            label_index[key] = disease_id

    drug_ids = {
        (agency_, number): did
        for agency_, number, did in session.execute(
            select(OrphanDrug.agency, OrphanDrug.designation_number, OrphanDrug.id)
        ).all()
    }

    links: list[dict] = []
    for d in staged:
        if not d.intended_use:
            continue
        key = normalize(d.intended_use)
        disease_id = label_index.get(key)
        drug_id = drug_ids.get((agency, d.designation_number))
        if disease_id is None or drug_id is None:
            continue
        links.append(
            {
                "disease_id": disease_id,
                "drug_id": drug_id,
                "match_method": "exact_label",
                "match_confidence": "medium",
                "matched_on": d.intended_use,
            }
        )

    n_links = 0
    for batch in _batched(links):
        batch = _dedupe(batch, "disease_id", "drug_id")
        session.execute(
            insert(DiseaseDrug).values(batch).on_conflict_do_nothing(constraint="uq_disease_drug")
        )
        n_links += len(batch)

    return n_drugs, n_links


def mesh_ids_by_disease(
    session: Session, skip_existing: bool = False
) -> list[tuple[object, str, str]]:
    """(disease_id, orpha_code, mesh_id) de las enfermedades con MeSH publicado.

    `skip_existing` deja fuera las que ya tienen ensayos cargados, lo que hace la
    ingesta reanudable. Importa: son ~3.200 peticiones a una API ajena, y un proceso
    interrumpido a la mitad no debe obligar a empezar de cero ni a machacar a la
    fuente repitiendo trabajo hecho.
    """
    stmt = (
        select(Disease.id, Disease.orpha_code, DiseaseXref.source_id)
        .join(DiseaseXref, DiseaseXref.disease_id == Disease.id)
        .where(DiseaseXref.source_ns == "MESH", Disease.status == "active")
    )
    if skip_existing:
        stmt = stmt.where(
            ~select(DiseaseTrial.id)
            .where(DiseaseTrial.disease_id == Disease.id)
            .exists()
        )
    rows = session.execute(stmt.order_by(Disease.orpha_code)).all()
    return [(r[0], r[1], r[2]) for r in rows]


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
