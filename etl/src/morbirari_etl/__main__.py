"""CLI de Morbi Rari: `mr ingest orphanet`, `mr index rebuild`, `mr status`."""

from __future__ import annotations

from datetime import datetime, timezone

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from morbirari_etl.config import ACTIVE_LANGS, VALIDATION_FAILURE_THRESHOLD
from morbirari_etl.db import (
    Disease,
    DiseaseLabel,
    DiseaseXref,
    IngestRun,
    Provenance,
    Source,
    get_sessionmaker,
)
from morbirari_etl.indexers import meilisearch as mi
from morbirari_etl.loaders import postgres as pg
from morbirari_etl.sources.hpo import translations as hpo_tr
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


@ingest_app.command("science")
def ingest_science(
    lang: str = typer.Option(",".join(ACTIVE_LANGS), help="Idiomas separados por comas"),
    force: bool = typer.Option(False, help="Reingerir aunque el checksum no haya cambiado"),
) -> None:
    """Ingiere los Orphanet Scientific Knowledge Files (CC BY 4.0).

    Epidemiología con geografía, historia natural, signos clínicos y genes: lo que
    convierte la ficha en un dashboard.
    """
    from morbirari_etl.loaders import science as sci_loader
    from morbirari_etl.sources.orphanet import science as sci

    langs = tuple(x.strip() for x in lang.split(",") if x.strip())
    Session = get_sessionmaker()

    # (producto, etiqueta, ¿por idioma?)
    products = [
        # Los alineamientos van primero: MeSH y GARD son lo que permite enlazar con
        # ensayos clínicos y con los textos del NIH.
        ("product1", "alineamientos", False),
        ("product9_prev", "epidemiología", True),
        ("product9_ages", "historia natural", True),
        ("product4", "signos clínicos", True),
        ("product6", "genes", False),
    ]

    for product, label, per_lang in products:
        target_langs = langs if per_lang else ("en",)
        for lang_code in target_langs:
            console.print(f"[bold]{label}[/bold] · {product} · {lang_code}")
            artifact = sci.fetch_product(product, lang_code, force=force)

            with Session() as session:
                if (
                    pg.has_successful_run_for_sha(session, f"orphanet-{product}", artifact.sha256)
                    and not force
                ):
                    console.print(f"  [dim]sin cambios (sha {artifact.sha256[:12]}), se salta[/dim]")
                    continue

                extraction_date, license_spdx = sci.read_meta(artifact.path)
                source = pg.upsert_source(
                    session,
                    name=f"orphanet-{product}",
                    license_spdx=license_spdx,
                    attribution_text=orphanet.ATTRIBUTION,
                    homepage="https://www.orphadata.com",
                    redistributable=(license_spdx or "").upper().startswith("CC-BY"),
                )
                run = pg.start_run(session, source, artifact.sha256, extraction_date)
                prov = pg.make_provenance(session, source, run, extraction_date, artifact.source_url)

                try:
                    index = sci_loader.disease_ids_by_orpha(session)
                    counts: dict[str, int] = {}

                    if product == "product1":
                        counts["referencias"] = sci_loader.load_alignments(
                            session, sci.parse_alignments(artifact.path), prov, index
                        )
                    elif product == "product9_prev":
                        counts["prevalencias"] = sci_loader.load_epidemiology(
                            session, sci.parse_epidemiology(artifact.path), lang_code, prov, index
                        )
                    elif product == "product9_ages":
                        counts["atributos"] = sci_loader.load_attributes(
                            session, sci.parse_natural_history(artifact.path), lang_code, prov, index
                        )
                    elif product == "product4":
                        terms, assoc = sci_loader.load_phenotypes(
                            session, sci.parse_phenotypes(artifact.path), prov, index
                        )
                        counts["terminos_hpo"] = terms
                        counts["anotaciones"] = assoc
                    elif product == "product6":
                        genes, assoc = sci_loader.load_genes(
                            session, sci.parse_genes(artifact.path), prov, index
                        )
                        counts["genes"] = genes
                        counts["asociaciones"] = assoc

                    pg.finish_run(session, run, "success", counts)
                    session.commit()
                    detalle = " · ".join(f"{v} {k}" for k, v in counts.items())
                    console.print(f"  [green]OK[/green] {detalle}")
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    console.print(f"  [red]FALLO[/red] {exc}")
                    raise typer.Exit(1) from exc

    # Los términos HPO llegan en inglés aunque el producto sea es_product4: Orphanet
    # no los traduce. Las traducciones oficiales van aparte.
    for lang_code in langs:
        if lang_code == "en" or lang_code not in hpo_tr.AVAILABLE_LANGS:
            continue
        console.print(f"[bold]traducciones HPO[/bold] · {lang_code}")
        artifact = hpo_tr.fetch(lang_code, force=force)
        if artifact is None:
            continue

        with Session() as session:
            if pg.has_successful_run_for_sha(session, hpo_tr.SOURCE_NAME, artifact.sha256) and not force:
                console.print("  [dim]sin cambios, se salta[/dim]")
                continue

            source = pg.upsert_source(
                session,
                name=hpo_tr.SOURCE_NAME,
                license_spdx=None,  # HPO usa licencia propia, sin identificador SPDX
                attribution_text=hpo_tr.ATTRIBUTION,
                homepage="https://hpo.jax.org",
                redistributable=True,
            )
            run = pg.start_run(session, source, artifact.sha256, None)
            prov = pg.make_provenance(session, source, run, None, artifact.source_url)
            try:
                n = sci_loader.load_phenotype_translations(session, hpo_tr.parse(artifact), prov)
                pg.finish_run(session, run, "success", {"traducciones": n})
                session.commit()
                console.print(f"  [green]OK[/green] {n} términos traducidos")
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                console.print(f"  [red]FALLO[/red] {exc}")
                raise typer.Exit(1) from exc


@ingest_app.command("drugs")
def ingest_drugs(force: bool = typer.Option(False, help="Reingerir aunque no haya cambios")) -> None:
    """Ingiere las designaciones de medicamento huérfano de la EMA (datos abiertos).

    Aviso: una designación huérfana no es un fármaco aprobado ni disponible. Muchas
    nunca llegan a serlo.
    """
    from morbirari_etl.loaders import science as sci_loader
    from morbirari_etl.sources.ema import orphan_drugs as ema

    Session = get_sessionmaker()
    console.print("[bold]EMA[/bold] · designaciones de medicamento huérfano")

    artifact = ema.fetch(force=force)

    with Session() as session:
        if pg.has_successful_run_for_sha(session, ema.SOURCE_NAME, artifact.sha256) and not force:
            console.print(f"  [dim]sin cambios (sha {artifact.sha256[:12]}), se salta[/dim]")
            return

        source = pg.upsert_source(
            session,
            name=ema.SOURCE_NAME,
            license_spdx=None,
            attribution_text=ema.ATTRIBUTION,
            homepage="https://www.ema.europa.eu",
            redistributable=True,
        )
        run = pg.start_run(session, source, artifact.sha256, None)
        prov = pg.make_provenance(session, source, run, None, artifact.source_url)

        try:
            n_drugs, n_links = sci_loader.load_orphan_drugs(
                session, ema.parse(artifact), ema.AGENCY, prov
            )
            pg.finish_run(session, run, "success", {"designaciones": n_drugs, "vinculos": n_links})
            session.commit()
            pct = (n_links / n_drugs * 100) if n_drugs else 0
            console.print(
                f"  [green]OK[/green] {n_drugs} designaciones · {n_links} enlazadas "
                f"a una enfermedad ({pct:.0f}%)"
            )
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            console.print(f"  [red]FALLO[/red] {exc}")
            raise typer.Exit(1) from exc


@ingest_app.command("nando")
def ingest_nando(force: bool = typer.Option(False, help="Reingerir aunque no haya cambios")) -> None:
    """Ingiere NANDO: el registro japonés de enfermedades intratables (CC BY 4.0).

    Aporta nombres en japonés y la designación oficial nipona, que determina la
    cobertura sanitaria allí. Es la única fuente que tenemos fuera del ámbito europeo.
    """
    from morbirari_etl.loaders import science as sci_loader
    from morbirari_etl.sources.nando import japan as nando

    Session = get_sessionmaker()
    console.print("[bold]NANDO[/bold] · registro japonés de enfermedades intratables")

    mapping_art, labels_art = nando.fetch(force=force)

    with Session() as session:
        if pg.has_successful_run_for_sha(session, nando.SOURCE_NAME, mapping_art.sha256) and not force:
            console.print(f"  [dim]sin cambios (sha {mapping_art.sha256[:12]}), se salta[/dim]")
            return

        source = pg.upsert_source(
            session,
            name=nando.SOURCE_NAME,
            license_spdx="CC-BY-4.0",
            attribution_text=nando.ATTRIBUTION,
            homepage="https://nanbyodata.jp",
            redistributable=True,
        )
        run = pg.start_run(session, source, mapping_art.sha256, None)
        prov = pg.make_provenance(session, source, run, None, mapping_art.source_url)

        try:
            index = sci_loader.disease_ids_by_orpha(session)
            n_labels, n_attrs = sci_loader.load_nando(
                session, nando.parse(mapping_art, labels_art), prov, index
            )
            pg.finish_run(session, run, "success", {"etiquetas_ja": n_labels, "designaciones": n_attrs})
            session.commit()
            console.print(
                f"  [green]OK[/green] {n_labels} etiquetas en japonés · "
                f"{n_attrs} designaciones oficiales"
            )
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            console.print(f"  [red]FALLO[/red] {exc}")
            raise typer.Exit(1) from exc


@ingest_app.command("trials")
def ingest_trials(
    limit: int = typer.Option(0, help="Máximo de enfermedades a consultar (0 = todas)"),
    resume: bool = typer.Option(
        True, help="Saltar las enfermedades que ya tienen ensayos cargados"
    ),
    only: str = typer.Option("", help="Códigos ORPHA concretos, separados por comas"),
) -> None:
    """Ingiere ensayos clínicos abiertos desde ClinicalTrials.gov (dominio público).

    Responde a «dónde se investiga» y «a dónde acudir»: patrocinadores y centros con
    ciudad y país, solo de ensayos que siguen abiertos.

    El vínculo se hace por código MeSH, que Orphanet publica para 3.209 enfermedades.
    """
    import httpx

    from morbirari_etl.loaders import science as sci_loader
    from morbirari_etl.sources.clinicaltrials import trials as ct

    Session = get_sessionmaker()

    with Session() as session:
        targets = sci_loader.mesh_ids_by_disease(session, skip_existing=resume and not only)

    if only:
        wanted = {c.strip() for c in only.split(",") if c.strip()}
        with Session() as session:
            targets = [t for t in sci_loader.mesh_ids_by_disease(session) if t[1] in wanted]
    if limit:
        targets = targets[:limit]

    console.print(
        f"[bold]ClinicalTrials.gov[/bold] · {len(targets)} enfermedades por consultar"
        + (" (reanudando)" if resume and not only else "")
    )
    if not targets:
        console.print("  [dim]nada que hacer[/dim]")
        return

    with Session() as session:
        source = pg.upsert_source(
            session,
            name=ct.SOURCE_NAME,
            license_spdx=None,  # obra del gobierno de EE.UU., sin identificador SPDX
            attribution_text=ct.ATTRIBUTION,
            homepage="https://clinicaltrials.gov",
            redistributable=True,
        )
        run = pg.start_run(session, source, "n/a", None)
        prov = pg.make_provenance(session, source, run, None, ct.API)
        session.commit()
        run_id, prov_id = run.id, prov.id

    total_trials = 0
    with_trials = 0
    errors = 0

    import time

    with httpx.Client(follow_redirects=True) as client:
        for i, (disease_id, orpha_code, mesh_id) in enumerate(targets, 1):
            # Una pausa por enfermedad, no solo entre páginas: son ~3.200 consultas a
            # un servicio público y gratuito.
            if i > 1:
                time.sleep(ct.PAUSE)
            try:
                trials = list(ct.fetch_by_mesh(mesh_id, client))
            except Exception as exc:  # noqa: BLE001
                # Una enfermedad que falla no debe tumbar la ingesta entera: se anota
                # y se sigue. El resto de los datos siguen sirviendo.
                errors += 1
                if errors <= 3:
                    console.print(f"  [yellow]ORPHA {orpha_code} ({mesh_id}): {exc}[/yellow]")
                continue

            if not trials:
                continue

            with Session() as session:
                prov_obj = session.get(Provenance, prov_id)
                n = sci_loader.load_trials(session, trials, disease_id, mesh_id, prov_obj)
                session.commit()
            total_trials += n
            with_trials += 1

            if i % 200 == 0:
                console.print(
                    f"  [dim]{i}/{len(targets)} · {with_trials} con ensayos · "
                    f"{total_trials} ensayos[/dim]"
                )

    with Session() as session:
        run_obj = session.get(IngestRun, run_id)
        pg.finish_run(
            session,
            run_obj,
            "success",
            {"enfermedades_con_ensayos": with_trials, "ensayos": total_trials, "errores": errors},
        )
        session.commit()

    console.print(
        f"  [green]OK[/green] {with_trials} enfermedades con ensayos abiertos · "
        f"{total_trials} ensayos · {errors} errores"
    )


@ingest_app.command("gard")
def ingest_gard(
    limit: int = typer.Option(0, help="Máximo de enfermedades a consultar (0 = todas)"),
    resume: bool = typer.Option(
        True, help="Saltar las enfermedades que ya tienen organizaciones cargadas"
    ),
    only: str = typer.Option("", help="IDs de GARD concretos, separados por comas"),
    force: bool = typer.Option(False, help="Reingerir aunque nada haya cambiado"),  # noqa: ARG001
) -> None:
    """Ingiere organizaciones de pacientes desde GARD (NCATS/NIH, dominio público).

    Apoyo e información para pacientes, **no atención médica** (ADR 0006). El vínculo con
    la enfermedad se hace por el ID de GARD que Orphanet publica, no por texto.
    """
    import httpx

    from morbirari_etl.loaders import science as sci_loader
    from morbirari_etl.sources.gard import organizations as gard

    Session = get_sessionmaker()
    console.print("[bold]GARD[/bold] · organizaciones de pacientes")

    artifact = gard.fetch_accounts()
    accounts = gard.account_index(artifact)

    with Session() as session:
        source = pg.upsert_source(
            session,
            name=gard.SOURCE_NAME,
            license_spdx=None,  # obra del gobierno de EE.UU., sin identificador SPDX
            attribution_text=gard.ATTRIBUTION,
            homepage="https://rarediseases.info.nih.gov",
            redistributable=True,
        )
        run = pg.start_run(session, source, artifact.sha256, artifact.source_version)
        prov = pg.make_provenance(session, source, run, artifact.source_version, artifact.source_url)
        session.commit()
        run_id, prov_id = run.id, prov.id

    with Session() as session:
        targets = sci_loader.gard_ids_by_disease(session, skip_existing=resume and not only)
    if only:
        wanted = {c.strip() for c in only.split(",") if c.strip()}
        with Session() as session:
            targets = [t for t in sci_loader.gard_ids_by_disease(session) if t[1] in wanted]
    if limit:
        targets = targets[:limit]

    console.print(
        f"[bold]{len(targets)}[/bold] enfermedades por consultar"
        + (" (reanudando)" if resume and not only else "")
    )
    if not targets:
        console.print("  [dim]nada que hacer[/dim]")
        return

    total_links = with_orgs = errors = 0
    with httpx.Client(follow_redirects=True) as client:
        for i, (disease_id, gard_id) in enumerate(targets, 1):
            try:
                pairs = list(gard.fetch_disease_orgs(gard_id, client))
            except Exception as exc:  # noqa: BLE001
                errors += 1
                if errors <= 3:
                    console.print(f"  [yellow]GARD {gard_id}: {exc}[/yellow]")
                continue

            staged = [gard.build_org(name, website, accounts) for name, website in pairs]
            if not staged:
                continue

            with Session() as session:
                prov_obj = session.get(Provenance, prov_id)
                org_id_by_sid = sci_loader.load_organizations(session, staged, prov_obj)
                org_ids = [
                    org_id_by_sid[s.source_id] for s in staged if s.source_id in org_id_by_sid
                ]
                n = sci_loader.link_disease_organizations(session, disease_id, org_ids, prov_obj)
                session.commit()
            total_links += n
            with_orgs += 1

            if i % 200 == 0:
                console.print(
                    f"  [dim]{i}/{len(targets)} · {with_orgs} con orgs · {total_links} vínculos[/dim]"
                )

    with Session() as session:
        run_obj = session.get(IngestRun, run_id)
        pg.finish_run(
            session,
            run_obj,
            "success",
            {"enfermedades_con_orgs": with_orgs, "vinculos": total_links, "errores": errors},
        )
        session.commit()

    console.print(
        f"  [green]OK[/green] {with_orgs} enfermedades con organizaciones · "
        f"{total_links} vínculos · {errors} errores"
    )


@ingest_app.command("classifications")
def ingest_classifications(
    lang: str = typer.Option(",".join(ACTIVE_LANGS), help="Idiomas separados por comas"),
    force: bool = typer.Option(False, help="Reingerir aunque el checksum no haya cambiado"),
) -> None:
    """Ingiere la jerarquía de clasificaciones desde el Nomenclature Pack ya descargado."""
    from morbirari_etl.loaders import science as sci_loader
    from morbirari_etl.sources.orphanet import classifications as cl

    langs = tuple(x.strip() for x in lang.split(",") if x.strip())
    Session = get_sessionmaker()
    artifacts = orphanet.fetch(langs=langs, force=False)

    for lang_code, artifact in zip(langs, artifacts):
        console.print(f"[bold]clasificaciones[/bold] · {lang_code}")
        with Session() as session:
            source = pg.upsert_source(
                session,
                name="orphanet-classifications",
                license_spdx="CC-BY-4.0",
                attribution_text=orphanet.ATTRIBUTION,
                homepage="https://www.orpha.net",
                redistributable=True,
            )
            run = pg.start_run(session, source, artifact.sha256, None)
            prov = pg.make_provenance(session, source, run, None, artifact.source_url)
            try:
                n_class, n_edges = sci_loader.load_classifications(
                    session, cl.parse_all(artifact.path, lang_code), prov
                )
                pg.finish_run(session, run, "success", {"clasificaciones": n_class, "aristas": n_edges})
                session.commit()
                console.print(f"  [green]OK[/green] {n_class} clasificaciones · {n_edges} aristas")
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                console.print(f"  [red]FALLO[/red] {exc}")
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
