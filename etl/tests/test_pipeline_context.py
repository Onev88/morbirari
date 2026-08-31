"""El contexto `IngestRunContext` de `__main__.py` se comporta.

Fija dos cosas del refactor que reemplaza la repetición del ciclo
`upsert_source → start_run → make_provenance → finish_run`:

- una salida limpia cierra el run como `success` con sus recuentos;
- un fallo revierte, marca el run como `failed` (con el motivo) en una sesión aparte
  y aborta el comando con `typer.Exit(1)`.

Requiere Postgres migrado; se salta si no está, para no romper la CI.
"""

from __future__ import annotations

import typer
import pytest
import sqlalchemy

from morbirari_etl.__main__ import IngestRunContext
from morbirari_etl.db import get_sessionmaker

SOURCE = "test-pipeline-context"


def _ctx(session, sha: str):
    return IngestRunContext(
        session,
        get_sessionmaker(),
        source_name=SOURCE,
        license_spdx=None,
        attribution="atribución de prueba",
        homepage="https://example.test",
        redistributable=True,
        sha=sha,
        version=None,
        url=None,
        fail_label="test",
    )


def _status(session, run_id: int) -> str | None:
    return session.execute(
        sqlalchemy.text("SELECT status FROM ingest_run WHERE id = :i"), {"i": run_id}
    ).scalar()


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
        s.execute(sqlalchemy.text("DELETE FROM source WHERE name = :n"), {"n": SOURCE})
        s.commit()
        s.close()


def test_salida_limpia_cierra_success_con_recuentos(session):
    with _ctx(session, "sha-ok") as ctx:
        ctx.success({"prueba": 7})
        run_id = ctx.run.id
    assert _status(session, run_id) == "success"
    counts = session.execute(
        sqlalchemy.text("SELECT record_counts FROM ingest_run WHERE id = :i"),
        {"i": run_id},
    ).scalar()
    assert counts == {"prueba": 7}


def test_fallo_marca_failed_en_sesion_aparte_y_aborta_con_codigo_1(session):
    # El run se fija antes de que el cuerpo decida fallar (como en trials/gard), para
    # que el aseo del contexto tenga algo que marcar.
    with pytest.raises(typer.Exit) as exc_info:
        with _ctx(session, "sha-fallo") as ctx:
            session.commit()
            run_id = ctx.run.id
            raise RuntimeError("boom de prueba")
    assert exc_info.value.exit_code == 1
    Session = get_sessionmaker()
    with Session() as s:
        assert _status(s, run_id) == "failed"
        error = s.execute(
            sqlalchemy.text("SELECT error FROM ingest_run WHERE id = :i"), {"i": run_id}
        ).scalar()
    assert "boom de prueba" in error


def test_fallo_sin_fijar_run_no_deja_filas_huerfanas(session):
    """Si el run nunca se llegó a persistir, no hay nada que marcar ni que se quede colgado."""
    with pytest.raises(typer.Exit):
        with _ctx(session, "sha-abortado"):
            raise RuntimeError("falló antes del commit")
    n = session.execute(
        sqlalchemy.text(
            "SELECT count(*) FROM ingest_run r JOIN source s ON s.id = r.source_id "
            "WHERE s.name = :n AND r.status = 'running'"
        ),
        {"n": SOURCE},
    ).scalar()
    assert n == 0