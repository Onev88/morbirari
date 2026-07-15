"""CLI de Morbi Rari: `mr ingest orphanet`, `mr index rebuild`, `mr status`."""

from __future__ import annotations

from datetime import datetime, timezone

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from morbirari_etl.config import ACTIVE_LANGS, VALIDATION_FAILURE_THRESHOLD
from morbirari_etl.db import Disease, DiseaseLabel, DiseaseXref, IngestRun, Source, get_sessionmaker
from morbirari_etl.indexers import meilisearch as mi
from morbirari_etl.loaders import postgres as pg
from morbirari_etl.sources.orphanet import nomenclature as orphanet

app = typer.Typer(help="Morbi Rari — ingesta e indexación de fuentes de enfermedades raras")
ingest_app = typer.Typer(help="Ingerir fuentes")
index_app = typer.Typer(help="Gestionar el índice de búsqueda")
app.add_typer(ingest_app, name="ingest")
app.add_typer(index_app, name="index")

console = Console()


@ingest_app.command("orphanet")
def ingest_orphanet(
    lang: str = typer.Option(",".join(ACTIVE_LANGS), help="Idiomas separados por comas"),
    force: bool = typer.Option(False, help="Reingerir aunque el checksum no haya cambiado"),
) -> None:
    """Ingiere el Orphanet Nomenclature Pack (CC BY 4.0)."""
    langs = tuple(x.strip() for x in lang.split(",") if x.strip())
    Session = get_sessionmaker()

    console.print(f"[bold]Orphanet[/bold] · idiomas: {', '.join(langs)}")
    artifacts = orphanet.fetch(langs=langs, force=force)

    for lang_code, artifact in zip(langs, artifacts):
        with Session() as session:
            already = pg.has_successful_run_for_sha(
                session, orphanet.SOURCE_NAME, artifact.sha256
            )
            if already and not force:
                console.print(
                    f"  [dim]{lang_code}: sin cambios (sha {artifact.sha256[:12]}), se salta[/dim]"
                )
                continue

            nomenclature_xml = orphanet._extract_member(
                artifact.path, orphanet._NOMENCLATURE_RE
            )
            meta = orphanet.read_pack_meta(nomenclature_xml)

            # La licencia se lee de lo que el propio fichero declara, no de lo que
            # creímos recordar.
            source = pg.upsert_source(
                session,
                name=orphanet.SOURCE_NAME,
                license_spdx=meta.license_spdx,
                attribution_text=orphanet.ATTRIBUTION,
                homepage="https://www.orpha.net",
                redistributable=(meta.license_spdx or "").upper().startswith("CC-BY"),
            )
            run = pg.start_run(session, source, artifact.sha256, meta.extraction_date)
            prov = pg.make_provenance(
                session, source, run, meta.extraction_date, artifact.source_url
            )
            run_started = datetime.now(timezone.utc)

            try:
                parsed, failed = [], 0
                for item in orphanet.parse(artifact, lang_code):
                    parsed.append(item)

                total = len(parsed) + failed
                if total and (failed / total) > VALIDATION_FAILURE_THRESHOLD:
                    raise RuntimeError(
                        f"{failed}/{total} registros fallaron la validación "
                        f"(umbral {VALIDATION_FAILURE_THRESHOLD:.0%}). Se aborta; "
                        f"los datos vivos siguen sirviendo."
                    )

                counts = pg.load_diseases(session, parsed, lang_code, prov, run_started)
                retired = pg.retire_missing(session, orphanet.SOURCE_NAME, run_started)
                counts["retired"] = retired
                pg.finish_run(session, run, "success", counts)
                session.commit()

                console.print(
                    f"  [green]{lang_code}[/green]: {counts['diseases']} enfermedades · "
                    f"{counts['labels']} etiquetas · {counts['xrefs']} xrefs · "
                    f"{counts['definitions']} definiciones · {retired} retiradas"
                )
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                with Session() as err_session:
                    err_run = err_session.get(IngestRun, run.id)
                    if err_run:
                        pg.finish_run(err_session, err_run, "failed", None, str(exc))
                        err_session.commit()
                console.print(f"  [red]{lang_code}: FALLO[/red] {exc}")
                raise typer.Exit(1) from exc


@index_app.command("rebuild")
def index_rebuild(
    lang: str = typer.Option(",".join(ACTIVE_LANGS), help="Idiomas separados por comas"),
) -> None:
    """Reconstruye el índice desde Postgres. Seguro en cualquier momento."""
    langs = tuple(x.strip() for x in lang.split(",") if x.strip())
    Session = get_sessionmaker()
    with Session() as session:
        for lang_code in langs:
            n = mi.rebuild(session, lang_code)
            console.print(f"  [green]{mi.index_name(lang_code)}[/green]: {n} documentos")


@app.command("status")
def status() -> None:
    """Estado de los datos: qué hay cargado, de qué versión y desde cuándo."""
    Session = get_sessionmaker()
    with Session() as session:
        table = Table(title="Morbi Rari — estado")
        table.add_column("Métrica")
        table.add_column("Valor", justify="right")

        table.add_row("Enfermedades activas", str(
            session.execute(
                select(func.count()).select_from(Disease).where(Disease.status == "active")
            ).scalar_one()
        ))
        table.add_row("Enfermedades retiradas", str(
            session.execute(
                select(func.count()).select_from(Disease).where(Disease.status == "retired")
            ).scalar_one()
        ))
        table.add_row("Etiquetas", str(
            session.execute(select(func.count()).select_from(DiseaseLabel)).scalar_one()
        ))
        table.add_row("Referencias cruzadas", str(
            session.execute(select(func.count()).select_from(DiseaseXref)).scalar_one()
        ))

        for lang_code, count in session.execute(
            select(DiseaseLabel.lang, func.count()).group_by(DiseaseLabel.lang)
        ):
            # Rich interpreta los corchetes como marcado de estilo; hay que escaparlos
            # o "[es]" desaparece de la salida.
            table.add_row(rf"  etiquetas \[{lang_code}]", str(count))

        console.print(table)

        runs = session.execute(
            select(IngestRun, Source)
            .join(Source)
            .order_by(IngestRun.started_at.desc())
            .limit(5)
        ).all()
        if runs:
            rt = Table(title="Últimas ingestas")
            rt.add_column("Fuente")
            rt.add_column("Estado")
            rt.add_column("Versión")
            rt.add_column("Cuándo")
            for run, src in runs:
                color = {"success": "green", "failed": "red"}.get(run.status, "yellow")
                rt.add_row(
                    src.name,
                    f"[{color}]{run.status}[/{color}]",
                    run.source_version or "—",
                    run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "—",
                )
            console.print(rt)


if __name__ == "__main__":
    app()
