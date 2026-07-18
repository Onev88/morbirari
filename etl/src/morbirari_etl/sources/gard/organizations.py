"""Adaptador de GARD: organizaciones de pacientes por enfermedad.

GARD (Genetic and Rare Diseases Information Center, NCATS/NIH) es **dominio público**.
Obliga a atribuir y a **no implicar respaldo del NIH** (igual que ClinicalTrials.gov).

Es apoyo e información para pacientes, **no atención médica ni consejo clínico**
(ADR 0006, regla 17). El buscador de especialistas o el registro de pacientes que enlaza
son de la propia organización, no una recomendación nuestra.

De dónde salen los datos: el sitio de GARD es una SPA que sirve JSON estáticos.
- `all-account-data.json`: cuentas ricas (~1.200) con web, país, y URLs de registro de
  pacientes y de buscador de especialistas. Está curado en inglés/EE.UU.
- `singles/{gardId}.json`: por enfermedad, **qué organizaciones la apoyan**
  (`Organization_Supported_Diseases__c`, con nombre y web). Es la lista autoritativa por
  enfermedad e incluye organizaciones que no están en el fichero de cuentas (p. ej. las
  federaciones en español). Se guardan todas; las que además están en el fichero de
  cuentas se enriquecen con país y directorios.

La enfermedad se une a nuestro catálogo por el ID de GARD que Orphanet publica (no es
inferencia de texto). La unión org-cuenta sí es por nombre normalizado.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Iterator

import httpx

from morbirari_etl.sources.base import (
    RawArtifact,
    download,
    raw_path,
    remote_fingerprint,
    sha256_file,
    version_from_fingerprint,
)
from morbirari_etl.sources.ema.orphan_drugs import normalize

SOURCE_NAME = "gard"
BASE = "https://rarediseases.info.nih.gov"
ACCOUNTS_URL = f"{BASE}/assets/related/all-account-data.json"


def single_url(gard_id: str) -> str:
    return f"{BASE}/assets/singles/{gard_id}.json"


ATTRIBUTION = (
    "Genetic and Rare Diseases Information Center (GARD), "
    "National Center for Advancing Translational Sciences (NCATS), NIH. "
    "Este sitio no está avalado por los NIH ni por NCATS."
)

# Los JSON son ficheros estáticos cacheados (CDN), no una API con límite estricto. Aun
# así se pausa: son ~3.800 consultas a un servicio público, y no hay ninguna prisa.
PAUSE = 0.2


@dataclass(frozen=True)
class StagedOrg:
    source_id: str
    name: str
    website: str | None
    country: str | None
    patient_registry_url: str | None
    expert_directory_url: str | None
    record_type: str | None


def fetch_accounts() -> RawArtifact:
    """Descarga la lista completa de cuentas y la aterriza con su sha256."""
    etag, last_modified = remote_fingerprint(ACCOUNTS_URL)
    version = version_from_fingerprint(etag, last_modified)
    dest = raw_path(SOURCE_NAME, version, "all-account-data.json")
    if not dest.exists():
        download(ACCOUNTS_URL, dest)
    return RawArtifact(
        source=SOURCE_NAME,
        path=dest,
        sha256=sha256_file(dest),
        source_url=ACCOUNTS_URL,
        source_version=version,
        etag=etag,
    )


def account_index(artifact: RawArtifact) -> dict[str, dict]:
    """`normalize(nombre)` → campos ricos de la cuenta de GARD (para enriquecer)."""
    data = json.loads(artifact.path.read_text(encoding="utf-8"))
    idx: dict[str, dict] = {}
    for row in data:
        acct = row.get("acct") or {}
        name = (acct.get("Name") or "").strip()
        key = normalize(name)
        if not key or key in idx:
            continue
        idx[key] = {
            "id": acct.get("Id"),
            "website": acct.get("Website") or None,
            "country": acct.get("Country__c") or None,
            "patient_registry_url": acct.get("Patient_Registry_URL__c") or None,
            "expert_directory_url": acct.get("Expert_Directory_URL__c") or None,
            "record_type": (acct.get("RecordType") or {}).get("Name"),
        }
    return idx


def fetch_disease_orgs(gard_id: str, client: httpx.Client) -> Iterator[tuple[str, str | None]]:
    """(nombre, web) de las organizaciones que apoyan a esta enfermedad.

    Un 404 (enfermedad de GARD sin ficha estática) o la ausencia de la sección se tratan
    como «sin organizaciones», no como error: la mayoría de enfermedades no tienen.
    """
    resp = client.get(single_url(gard_id), timeout=60)
    if resp.status_code == 404:
        return
    resp.raise_for_status()
    data = resp.json()
    for org in data.get("Organization_Supported_Diseases__c") or []:
        name = (org.get("Account_Name__c") or "").strip()
        if name:
            yield name, (org.get("Website__c") or None)
    time.sleep(PAUSE)


def build_org(name: str, website: str | None, accounts: dict[str, dict]) -> StagedOrg:
    """Une una organización de una enfermedad con su cuenta rica de GARD por nombre.

    Clave natural: el ID de cuenta de GARD si la organización está en el fichero de
    cuentas; si no (típico de las federaciones en español, que GARD lista pero no cura como
    cuenta), un identificador estable derivado del nombre. Así se guardan también esas —con
    nombre y web—, aunque sin país ni directorios.
    """
    key = normalize(name)
    acct = accounts.get(key) or {}
    source_id = acct.get("id") or ("name:" + hashlib.sha1(key.encode()).hexdigest()[:24])
    return StagedOrg(
        source_id=source_id,
        name=name,
        website=acct.get("website") or website,
        country=acct.get("country"),
        patient_registry_url=acct.get("patient_registry_url"),
        expert_directory_url=acct.get("expert_directory_url"),
        record_type=acct.get("record_type"),
    )
