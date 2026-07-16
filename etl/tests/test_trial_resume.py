"""Reanudación de la ingesta de ensayos.

El bug que motiva esto: «ya consultada» se deducía de tener ensayos cargados, así que
las ~1.966 enfermedades con MeSH y sin ensayos abiertos se volvían a consultar en cada
`--resume`. Eran ~1.966 peticiones inútiles a un servicio público y gratuito, en cada
reanudación, para siempre.

La corrección es registrar la consulta y no el resultado. Estos tests fijan esa
distinción: un «no hay nada» tiene que contar como consulta hecha.

Requiere Postgres migrado; se salta si no está, para no romper la CI.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy

from morbirari_etl.db import Disease, DiseaseXref, get_sessionmaker
from morbirari_etl.loaders.science import mesh_ids_by_disease, record_trial_query


@pytest.fixture()
def session():
    """Sesión sobre la base real que revierte al terminar: no ensucia los datos."""
    try:
        Session = get_sessionmaker()
        s = Session()
        s.execute(sqlalchemy.text("SELECT 1 FROM trial_query LIMIT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres no disponible o sin migrar: {exc}")
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def disease(session):
    """Una enfermedad de usar y tirar, con MeSH y sin ensayos."""
    d = Disease(
        id=uuid.uuid4(),
        slug=f"test-resume-{uuid.uuid4().hex[:8]}",
        orpha_code=f"TEST{uuid.uuid4().hex[:6]}",
        status="active",
    )
    session.add(d)
    session.flush()
    session.add(DiseaseXref(disease_id=d.id, source_ns="MESH", source_id="D000000"))
    session.flush()
    return d


def codes(session, **kwargs) -> set[str]:
    return {t[1] for t in mesh_ids_by_disease(session, **kwargs)}


def test_sin_consultar_entra_en_la_seleccion(session, disease):
    assert disease.orpha_code in codes(session, fresh_for_days=30)


def test_consultada_sin_ensayos_no_se_vuelve_a_consultar(session, disease):
    """El caso del bug: cero ensayos es una respuesta, no una consulta pendiente."""
    record_trial_query(session, disease.id, "D000000", trials_found=0)
    session.flush()
    assert disease.orpha_code not in codes(session, fresh_for_days=30)


def test_la_consulta_caduca(session, disease):
    """Los ensayos abren y cierran: una respuesta vieja deja de valer."""
    record_trial_query(session, disease.id, "D000000", trials_found=0)
    session.execute(
        sqlalchemy.text("UPDATE trial_query SET queried_at = :t WHERE disease_id = :d"),
        {"t": datetime.now(timezone.utc) - timedelta(days=31), "d": disease.id},
    )
    session.flush()
    assert disease.orpha_code not in codes(session, fresh_for_days=60)
    assert disease.orpha_code in codes(session, fresh_for_days=30)


def test_sin_reanudar_se_consulta_todo(session, disease):
    """`--no-resume` tiene que ignorar el registro y volver a preguntarlo todo."""
    record_trial_query(session, disease.id, "D000000", trials_found=0)
    session.flush()
    assert disease.orpha_code in codes(session)


def test_registrar_dos_veces_actualiza_en_vez_de_duplicar(session, disease):
    """Hay una fila por enfermedad: la segunda consulta pisa a la primera."""
    record_trial_query(session, disease.id, "D000000", trials_found=0)
    session.flush()
    record_trial_query(session, disease.id, "D000000", trials_found=7)
    session.flush()
    rows = session.execute(
        sqlalchemy.text(
            "SELECT trials_found FROM trial_query WHERE disease_id = :d"
        ),
        {"d": disease.id},
    ).all()
    assert [r[0] for r in rows] == [7]
