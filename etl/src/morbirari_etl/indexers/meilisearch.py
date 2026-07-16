"""Indexación en Meilisearch: un índice por idioma.

Postgres es la verdad; esto es una proyección reconstruible. Nunca hay escritura dual:
`mr index rebuild` debe ser seguro en cualquier momento.

Un índice por idioma y no uno global porque la tolerancia a erratas y los sinónimos son
ajustes *por índice*, y mezclar tokens de varios idiomas envenena el ranking. Nueve
índices de ~11k documentos no son nada.
"""

from __future__ import annotations

from typing import Any, Iterable

import meilisearch
from sqlalchemy import select
from sqlalchemy.orm import Session

from morbirari_etl.config import MEILI_MASTER_KEY, MEILI_URL
from morbirari_etl.db import (
    Disease,
    DiseaseContent,
    DiseaseGene,
    DiseaseLabel,
    DiseaseXref,
    Gene,
)

INDEX_PREFIX = "diseases"

# Orden de prioridad de atributos: quien casa en el nombre preferido gana a quien casa
# en la definición. `exactness` alto porque un nombre exacto debe batir a un difuso.
SEARCHABLE_ATTRIBUTES = [
    "preferred_label",
    "abbreviations",
    "synonyms",
    # Los genes causantes van en su propio atributo, por delante del resto de genes.
    # Buscar "CFTR" debe llevar a la fibrosis quística (que ese gen causa) y no a una
    # enfermedad donde CFTR solo se probó como candidato.
    "causing_genes",
    "gene_symbols",
    "xref_ids",
    "definition",
]

RANKING_RULES = [
    "words",
    "typo",
    "proximity",
    # `exactness` va ANTES que `attribute`, invirtiendo el orden por defecto de
    # Meilisearch. Motivo: un sinónimo que coincide exactamente con toda la consulta
    # debe ganar a un nombre preferido que solo la contiene como una palabra suelta.
    # Buscar "mucoviscidosis" tiene que llevar a Fibrosis quística (cuyo sinónimo
    # histórico es exactamente eso) y no al "Síndrome de mucoviscidosis-gastritis-
    # anemia megaloblástica", que con el orden por defecto ganaba por casar en el
    # nombre preferido.
    "exactness",
    "attribute",
    "sort",
    # Desempate final por longitud del nombre. Meilisearch no normaliza por longitud
    # de campo como haría BM25, así que "Cystic fibrosis-gastritis-megaloblastic
    # anemia syndrome" empata con "Cystic fibrosis" al buscar "cystic fibrosis" y
    # puede ganar por orden arbitrario. Entre dos coincidencias equivalentes, la del
    # nombre más corto es el término canónico y la más larga es un subtipo.
    #
    # Esto ordena por especificidad del acierto, no por prevalencia: ordenar por
    # prevalencia favorecería a las enfermedades comunes, que es justo lo contrario
    # de lo que este producto necesita.
    "label_length:asc",
]

# Sinónimos de morfología del dominio, no de enfermedades concretas. Este ajuste es
# global por índice: los sinónimos específicos de cada enfermedad van en el campo
# `synonyms[]`, que es lo que Orphanet nos da y lo que hay que indexar como dato.
DOMAIN_SYNONYMS: dict[str, dict[str, list[str]]] = {
    "en": {
        "syndrome": ["sd", "syndr"],
        "deficiency": ["def"],
        "disease": ["dis"],
        "congenital": ["cong"],
    },
    "es": {
        "sindrome": ["sd", "síndrome"],
        "deficiencia": ["def", "déficit"],
        "enfermedad": ["enf"],
        "congenito": ["congénito", "cong"],
    },
}


def get_client() -> meilisearch.Client:
    return meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)


def index_name(lang: str) -> str:
    return f"{INDEX_PREFIX}_{lang}"


def configure_index(client: meilisearch.Client, lang: str) -> None:
    index = client.index(index_name(lang))
    index.update_settings(
        {
            "searchableAttributes": SEARCHABLE_ATTRIBUTES,
            "filterableAttributes": ["disease_type", "status", "has_definition", "xref_ns"],
            "sortableAttributes": ["preferred_label", "label_length"],
            "rankingRules": RANKING_RULES,
            "synonyms": DOMAIN_SYNONYMS.get(lang, {}),
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {"oneTypo": 5, "twoTypos": 9},
                # Aplicar difuso a un identificador devuelve basura con aires de
                # certeza: "OMIM:219700" no debe casar con "OMIM:219701", ni "CFTR"
                # con "CFTR2".
                "disableOnAttributes": ["xref_ids", "gene_symbols", "causing_genes"],
            },
            "pagination": {"maxTotalHits": 1000},
        }
    )


def build_documents(session: Session, lang: str) -> Iterable[dict[str, Any]]:
    """Proyecta las tablas canónicas a documentos de búsqueda de un idioma.

    Cae a inglés para las etiquetas cuando falta la traducción: más vale un resultado
    en inglés que ningún resultado.
    """
    diseases = session.execute(
        select(Disease).where(Disease.status == "active").order_by(Disease.orpha_code)
    ).scalars().all()

    labels_by_disease: dict[Any, list[DiseaseLabel]] = {}
    for lb in session.execute(
        select(DiseaseLabel).where(DiseaseLabel.lang.in_([lang, "en"]))
    ).scalars():
        labels_by_disease.setdefault(lb.disease_id, []).append(lb)

    xrefs_by_disease: dict[Any, list[DiseaseXref]] = {}
    for xr in session.execute(select(DiseaseXref)).scalars():
        xrefs_by_disease.setdefault(xr.disease_id, []).append(xr)

    defs_by_disease: dict[Any, dict[str, str]] = {}
    for ct in session.execute(
        select(DiseaseContent).where(
            DiseaseContent.block_type == "definition", DiseaseContent.lang.in_([lang, "en"])
        )
    ).scalars():
        defs_by_disease.setdefault(ct.disease_id, {})[ct.lang] = ct.body

    # Los símbolos de gen son una vía de entrada real: un clínico busca "CFTR" igual
    # que busca "fibrosis quística".
    #
    # Se separan causantes del resto por una razón concreta de ranking: Meilisearch
    # evalúa `exactness` sobre el atributo completo, y trata un array como un campo
    # concatenado. Con todos los genes en un solo atributo, la fibrosis quística
    # (19 genes) puntuaba `matchesStart` para "CFTR" mientras una enfermedad con
    # CFTR como único gen candidato puntuaba `exactMatch` y ganaba. Con los causantes
    # en su propio atributo, ['CFTR'] vuelve a ser coincidencia exacta ahí, y ese
    # atributo pesa más.
    causing_by_disease: dict[Any, list[str]] = {}
    other_genes_by_disease: dict[Any, list[str]] = {}
    for disease_id, symbol, assoc_type in session.execute(
        select(DiseaseGene.disease_id, Gene.symbol, DiseaseGene.association_type).join(
            Gene, Gene.id == DiseaseGene.gene_id
        )
    ):
        causing = "disease-causing" in (assoc_type or "").lower()
        bucket = causing_by_disease if causing else other_genes_by_disease
        bucket.setdefault(disease_id, []).append(symbol)

    for disease in diseases:
        labels = labels_by_disease.get(disease.id, [])

        def pick(label_type: str) -> list[str]:
            preferred_lang = [lb.label for lb in labels if lb.lang == lang and lb.label_type == label_type]
            if preferred_lang:
                return preferred_lang
            return [lb.label for lb in labels if lb.lang == "en" and lb.label_type == label_type]

        preferred = pick("preferred")
        if not preferred:
            continue

        synonyms = pick("synonym")
        # Orphanet no distingue abreviaturas de sinónimos, pero un sinónimo corto y
        # en mayúsculas ("CF") se comporta como abreviatura: merece más peso que un
        # sinónimo largo, y por eso va a su propio atributo.
        abbreviations = [s for s in synonyms if len(s) <= 6 and s.isupper()]
        long_synonyms = [s for s in synonyms if s not in abbreviations]

        xrefs = xrefs_by_disease.get(disease.id, [])
        definitions = defs_by_disease.get(disease.id, {})
        definition = definitions.get(lang) or definitions.get("en")

        yield {
            "id": str(disease.id),
            "orpha_code": disease.orpha_code,
            "slug": disease.slug,
            "preferred_label": preferred[0],
            "label_length": len(preferred[0]),
            "synonyms": long_synonyms,
            "abbreviations": abbreviations,
            # Ambas formas ("219700" y "OMIM:219700") porque los clínicos escriben
            # las dos.
            "xref_ids": [x.source_id for x in xrefs]
            + [f"{x.source_ns}:{x.source_id}" for x in xrefs],
            "xref_ns": sorted({x.source_ns for x in xrefs}),
            "causing_genes": sorted(causing_by_disease.get(disease.id, [])),
            "gene_symbols": sorted(other_genes_by_disease.get(disease.id, [])),
            "definition": definition,
            "has_definition": definition is not None,
            "disease_type": disease.disease_type,
            "status": disease.status,
        }


def rebuild(session: Session, lang: str) -> int:
    client = get_client()
    name = index_name(lang)

    try:
        client.create_index(name, {"primaryKey": "id"})
    except meilisearch.errors.MeilisearchApiError as exc:
        if getattr(exc, "code", None) != "index_already_exists":
            raise

    configure_index(client, lang)
    docs = list(build_documents(session, lang))
    if docs:
        task = client.index(name).add_documents(docs)
        client.wait_for_task(task.task_uid, timeout_in_ms=300_000)
    return len(docs)
