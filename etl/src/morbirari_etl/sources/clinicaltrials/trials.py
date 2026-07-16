"""Adaptador de ClinicalTrials.gov (API v2).

Responde a «¿dónde se investiga esto?» y «¿a dónde puedo acudir?»: cada ensayo trae su
patrocinador, sus centros con ciudad y país, y si está reclutando.

Es la mejor fuente libre para esto. Los centros expertos y las asociaciones de
pacientes de Orphanet serían más completos, pero exigen firmar un acuerdo de
transferencia de datos; ClinicalTrials.gov es obra del gobierno de EE.UU.

Licencia: dominio público. Obliga a atribuir y a **no implicar respaldo** del NIH.

El vínculo con la enfermedad se hace por **código MeSH**, no por texto: Orphanet
publica el MeSH de 3.209 enfermedades, y ClinicalTrials.gov indexa cada estudio con
sus términos MeSH. Sigue siendo una inferencia nuestra, pero de otra categoría que
casar cadenas.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator

import httpx

SOURCE_NAME = "clinicaltrials"
API = "https://clinicaltrials.gov/api/v2/studies"

ATTRIBUTION = (
    "ClinicalTrials.gov, U.S. National Library of Medicine. "
    "Este sitio no está avalado por los NIH ni por la NLM."
)

# Solo los estados que sirven a un paciente que busca dónde acudir. Un ensayo
# terminado no es un sitio al que ir.
OPEN_STATUSES = ("RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION")

# Pausa entre peticiones. Medido: a ~3/s la API responde 429. Este ETL corre una vez
# por semana y no tiene ninguna prisa; el servicio es público y gratuito.
PAUSE = 1.0

FIELDS = ",".join(
    [
        "NCTId",
        "BriefTitle",
        "OverallStatus",
        "Phase",
        "StudyType",
        "LeadSponsorName",
        "LeadSponsorClass",
        "EnrollmentCount",
        "StartDate",
        "LastUpdatePostDate",
        "LocationFacility",
        "LocationCity",
        "LocationCountry",
        "LocationStatus",
    ]
)


def _get_with_backoff(client: httpx.Client, params: dict, attempts: int = 4) -> dict:
    """GET con espera creciente ante 429.

    ClinicalTrials.gov limita el ritmo y devuelve 429. Es un servicio público y
    gratuito: cuando pide que aflojemos, se afloja. Sin esto, una ingesta de ~3.200
    enfermedades se convierte en abuso y además pierde datos silenciosamente.
    """
    delay = 2.0
    for attempt in range(attempts):
        resp = client.get(API, params=params, timeout=60)
        if resp.status_code == 429:
            if attempt == attempts - 1:
                resp.raise_for_status()
            # Se respeta Retry-After si lo manda; si no, espera exponencial.
            retry_after = resp.headers.get("retry-after")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
            time.sleep(wait)
            delay *= 2
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("agotados los reintentos por límite de ritmo")


@dataclass
class StagedLocation:
    facility: str | None
    city: str | None
    country: str | None
    status: str | None


@dataclass
class StagedTrial:
    nct_id: str
    title: str
    status: str
    phase: str | None
    study_type: str | None
    lead_sponsor: str | None
    sponsor_class: str | None
    enrollment: int | None
    start_date: str | None
    last_update: str | None
    locations: list[StagedLocation] = field(default_factory=list)


def _flatten_date(value) -> str | None:
    if isinstance(value, dict):
        return value.get("date")
    return value


def fetch_by_mesh(
    mesh_id: str, client: httpx.Client, page_size: int = 100, max_pages: int = 3
) -> Iterator[StagedTrial]:
    """Ensayos abiertos indexados con este término MeSH.

    `max_pages` acota: una enfermedad con cientos de ensayos abiertos no aporta más
    por listarlos todos, y el objetivo es orientar, no ser un espejo del registro.
    """
    page_token = None
    for _ in range(max_pages):
        params = {
            # AREA[...] busca por el campo indexado, no por texto libre.
            "query.term": f"AREA[ConditionMeshId]{mesh_id}",
            "filter.overallStatus": "|".join(OPEN_STATUSES),
            "fields": FIELDS,
            "pageSize": str(page_size),
        }
        if page_token:
            params["pageToken"] = page_token

        data = _get_with_backoff(client, params)

        for study in data.get("studies", []):
            protocol = study.get("protocolSection", {})
            ident = protocol.get("identificationModule", {})
            status_mod = protocol.get("statusModule", {})
            design = protocol.get("designModule", {})
            sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
            lead = sponsor_mod.get("leadSponsor", {})

            nct_id = ident.get("nctId")
            if not nct_id:
                continue

            phases = design.get("phases") or []
            locations = [
                StagedLocation(
                    facility=loc.get("facility"),
                    city=loc.get("city"),
                    country=loc.get("country"),
                    status=loc.get("status"),
                )
                for loc in protocol.get("contactsLocationsModule", {}).get("locations", [])
            ]

            yield StagedTrial(
                nct_id=nct_id,
                title=ident.get("briefTitle") or nct_id,
                status=status_mod.get("overallStatus") or "UNKNOWN",
                phase=", ".join(phases) if phases else None,
                study_type=design.get("studyType"),
                lead_sponsor=lead.get("name"),
                sponsor_class=lead.get("class"),
                enrollment=(design.get("enrollmentInfo") or {}).get("count"),
                start_date=_flatten_date(status_mod.get("startDateStruct")),
                last_update=_flatten_date(status_mod.get("lastUpdatePostDateStruct")),
                locations=locations,
            )

        page_token = data.get("nextPageToken")
        if not page_token:
            break

        time.sleep(PAUSE)
