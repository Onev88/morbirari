"""Carga a Postgres: upsert idempotente, barrido de last_seen y guarda de licencia.

Reglas que se hacen cumplir aquí, no en la documentación:
- Ningún texto propiedad de OMIM entra en la base (ver `assert_no_omim_text`).
- Los borrados son lógicos: lo ausente en una ejecución correcta se marca 'retired'.
- Nada toca las tablas vivas hasta que la validación pasa.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from morbirari_etl.db import (
    Disease,
    DiseaseContent,
    DiseaseLabel,
    DiseaseXref,
    IngestRun,
    Provenance,
    Source,
)
from morbirari_etl.models.orphanet import StagingDisease


class LicenseViolation(RuntimeError):
    """Se ha intentado cargar contenido que no tenemos derecho a almacenar."""


# Fuentes cuyo texto no podemos almacenar ni republicar. Los identificadores desnudos
# de estas fuentes sí son admisibles: un número MIM es un hecho, no expresión
# protegible. Lo que no entra es el título o el texto. Ver DATA_LICENSES.md.
TEXT_FORBIDDEN_NAMESPACES = frozenset({"OMIM"})


def assert_no_omim_text(source_ns: str, payload: str | None) -> None:
    """Guarda dura contra importar texto de OMIM a un repositorio público.

    La trampa concreta que esto ataja: `phenotype.hpoa` del HPO trae una columna
    `disease_name` y, en las filas `OMIM:xxxxxx`, ese valor *es* el título preferido
    de OMIM, protegido por copyright de Johns Hopkins. Ingerirlo sin pensar mete
    material propietario en una base pública.

    Esto es una aserción, no un comentario, precisamente porque un comentario no
    detiene a nadie.
    """
    if source_ns.upper() in TEXT_FORBIDDEN_NAMESPACES and payload:
        raise LicenseViolation(
            f"Intento de almacenar texto de {source_ns}: {payload[:60]!r}. "
            f"Solo se admiten identificadores desnudos de {source_ns}. "
            f"Ver DATA_LICENSES.md."
        )


def slugify(text: str, orpha_code: str) -> str:
    """Slug estable y legible. Lleva el código ORPHA para garantizar unicidad."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    ascii_text = re.sub(r"-{2,}", "-", ascii_text)[:180]
    return f"{ascii_text}-orpha-{orpha_code}" if ascii_text else f"orpha-{orpha_code}"


def upsert_source(
    session: Session,
    name: str,
    license_spdx: str | None,
    attribution_text: str,
    homepage: str,
    redistributable: bool,
) -> Source:
    stmt = (
        insert(Source)
        .values(
            name=name,
            license_spdx=license_spdx,
            attribution_text=attribution_text,
            homepage=homepage,
            redistributable=redistributable,
        )
        .on_conflict_do_update(
            index_elements=[Source.name],
            set_={
                "license_spdx": license_spdx,
                "attribution_text": attribution_text,
                "homepage": homepage,
                "redistributable": redistributable,
            },
        )
        .returning(Source.id)
    )
    source_id = session.execute(stmt).scalar_one()
    session.flush()
    return session.get(Source, source_id)


def start_run(session: Session, source: Source, sha256: str, version: str | None) -> IngestRun:
    run = IngestRun(
        source_id=source.id, artifact_sha256=sha256, source_version=version, status="running"
    )
    session.add(run)
    session.flush()
    return run


def finish_run(
    session: Session, run: IngestRun, status: str, counts: dict | None = None, error: str | None = None
) -> None:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    run.record_counts = counts
    run.error = error
    session.flush()


def has_successful_run_for_sha(session: Session, source_name: str, sha256: str) -> bool:
    """¿Se ingirió ya con éxito este artefacto exacto?

    La pregunta es por artefacto y no "¿cuál fue el último sha?": una fuente puede
    publicar varios artefactos a la vez (Orphanet, uno por idioma), y comparar contra
    el último visto haría que ninguno coincidiera nunca consigo mismo.
    """
    stmt = (
        select(IngestRun.id)
        .join(Source)
        .where(
            Source.name == source_name,
            IngestRun.status == "success",
            IngestRun.artifact_sha256 == sha256,
        )
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none() is not None


def make_provenance(
    session: Session, source: Source, run: IngestRun, version: str | None, url: str | None
) -> Provenance:
    prov = Provenance(
        source_id=source.id, ingest_run_id=run.id, source_version=version, source_url=url
    )
    session.add(prov)
    session.flush()
    return prov


def load_diseases(
    session: Session,
    diseases: Iterable[StagingDisease],
    lang: str,
    provenance: Provenance,
    run_started: datetime,
) -> dict[str, int]:
    """Upsert idempotente de enfermedades, etiquetas, xrefs y definiciones.

    Reejecutar esto con los mismos datos no debe cambiar nada salvo `last_seen`.
    """
    counts = {"diseases": 0, "labels": 0, "xrefs": 0, "definitions": 0}

    for staged in diseases:
        preferred = next(
            (lb.label for lb in staged.labels if lb.label_type == "preferred"), None
        )
        slug = slugify(preferred or "", staged.orpha_code)

        # La enfermedad es canónica y compartida entre idiomas: el slug solo se fija
        # con el idioma de referencia (EN), para que no cambie al reingerir en ES.
        disease_values = {
            "orpha_code": staged.orpha_code,
            "disease_type": staged.disease_type,
            "classification_level": staged.classification_level,
            "status": "active" if (staged.status or "").lower().startswith(("active", "activo")) else "retired",
            "expert_link": staged.expert_link,
            "last_seen": run_started,
        }
        update_set = dict(disease_values)
        if lang == "en":
            update_set["slug"] = slug

        stmt = (
            insert(Disease)
            .values(slug=slug, **disease_values)
            .on_conflict_do_update(index_elements=[Disease.orpha_code], set_=update_set)
            .returning(Disease.id)
        )
        disease_id = session.execute(stmt).scalar_one()
        counts["diseases"] += 1

        if staged.labels:
            session.execute(
                insert(DiseaseLabel)
                .values(
                    [
                        {
                            "disease_id": disease_id,
                            "lang": lb.lang,
                            "label": lb.label,
                            "label_type": lb.label_type,
                            "provenance_id": provenance.id,
                        }
                        for lb in staged.labels
                    ]
                )
                .on_conflict_do_nothing(constraint="uq_label")
            )
            counts["labels"] += len(staged.labels)

        if staged.xrefs:
            for xr in staged.xrefs:
                # Solo el identificador cruza esta frontera. Nunca texto.
                assert_no_omim_text(xr.source_ns, getattr(xr, "label", None))
            session.execute(
                insert(DiseaseXref)
                .values(
                    [
                        {
                            "disease_id": disease_id,
                            "source_ns": xr.source_ns,
                            "source_id": xr.source_id,
                            "relation": xr.relation,
                            "validated": xr.validated,
                            "provenance_id": provenance.id,
                        }
                        for xr in staged.xrefs
                    ]
                )
                .on_conflict_do_nothing(constraint="uq_xref")
            )
            counts["xrefs"] += len(staged.xrefs)

        if staged.definition:
            session.execute(
                insert(DiseaseContent)
                .values(
                    disease_id=disease_id,
                    lang=lang,
                    audience="both",
                    block_type="definition",
                    body=staged.definition,
                    provenance_id=provenance.id,
                )
                .on_conflict_do_update(
                    constraint="uq_content",
                    set_={"body": staged.definition, "provenance_id": provenance.id},
                )
            )
            counts["definitions"] += 1

    return counts


def retire_missing(session: Session, source_name: str, run_started: datetime) -> int:
    """Marca como retiradas las enfermedades ausentes en esta ejecución.

    Orphanet deprecia y fusiona códigos. Borrar en duro rompería todo enlace entrante
    y todo marcador de usuario, así que el borrado es lógico.
    """
    stmt = (
        update(Disease)
        .where(Disease.last_seen < run_started, Disease.status == "active")
        .values(status="retired")
    )
    return session.execute(stmt).rowcount
