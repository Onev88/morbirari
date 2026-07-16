"""NANDO — Nanbyo Disease Ontology (Japón).

Por qué está aquí: Orphanet publica en 9 idiomas, todos europeos. NANDO es el
registro oficial japonés de enfermedades intratables (難病, *nanbyo*), es CC BY 4.0,
y — lo decisivo — **mapea a códigos Orphanet directamente**. Verificado: sus 1.824
mapeos traen los tres campos que hacen falta (código Orphanet, etiqueta japonesa y
número de designación).

Aporta dos cosas que ninguna fuente europea da:

1. **Nombres en japonés**, en kanji y en hiragana. Un hablante de japonés puede buscar
   表皮水疱症 y llegar a la enfermedad.
2. **La designación oficial japonesa**. En Japón, que una enfermedad esté en la lista
   de nanbyo designadas determina la cobertura sanitaria del paciente. Es un dato de
   política sanitaria que no existe en Orphanet.

Atribución: NANDO / NanbyoData, DBCLS. CC BY 4.0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator

from morbirari_etl.sources.base import (
    RawArtifact,
    download,
    raw_path,
    remote_fingerprint,
    sha256_file,
    version_from_fingerprint,
)

SOURCE_NAME = "nando"

BASE = "https://nanbyodata.jp/download/latest"
MAPPING_URL = f"{BASE}/nando-orphanet.json"
LABELS_URL = f"{BASE}/nando.json"

ATTRIBUTION = (
    "NANDO (Nanbyo Disease Ontology), NanbyoData, DBCLS. CC BY 4.0. "
    "https://nanbyodata.jp"
)


@dataclass(frozen=True)
class StagedNando:
    orpha_code: str
    nando_id: str
    label_ja: str
    label_hira: str | None
    notification_number: str | None
    category: str | None


def fetch(force: bool = False) -> tuple[RawArtifact, RawArtifact]:
    artifacts = []
    for url, name in ((MAPPING_URL, "nando-orphanet.json"), (LABELS_URL, "nando.json")):
        etag, last_modified = remote_fingerprint(url)
        version = version_from_fingerprint(etag, last_modified)
        dest = raw_path(SOURCE_NAME, version, name)
        if not dest.exists() or force:
            download(url, dest)
        artifacts.append(
            RawArtifact(
                source=SOURCE_NAME,
                path=dest,
                sha256=sha256_file(dest),
                source_url=url,
                etag=etag,
            )
        )
    return artifacts[0], artifacts[1]


def parse(mapping_artifact: RawArtifact, labels_artifact: RawArtifact) -> Iterator[StagedNando]:
    """Une el mapeo a Orphanet con los detalles de cada enfermedad japonesa."""
    with labels_artifact.path.open(encoding="utf-8") as fh:
        labels_raw = json.load(fh)

    # nando.json trae hiragana, número de designación y categoría; el fichero de
    # mapeo, el código Orphanet. Se cruzan por NANDO id.
    details = {row["id"]: row for row in labels_raw if row.get("id")}

    with mapping_artifact.path.open(encoding="utf-8") as fh:
        mapping = json.load(fh)

    for row in mapping:
        orpha_raw = row.get("orphanetid")
        label_ja = row.get("nando_label_ja")
        nando_id = row.get("nando_id")
        if not orpha_raw or not label_ja or not nando_id:
            continue

        # "Orphanet:68380" -> "68380"
        orpha_code = orpha_raw.split(":")[-1].strip()
        if not orpha_code.isdigit():
            continue

        detail = details.get(nando_id, {})
        yield StagedNando(
            orpha_code=orpha_code,
            nando_id=nando_id,
            label_ja=label_ja,
            label_hira=detail.get("label_hira"),
            notification_number=detail.get("notification_number"),
            category=detail.get("category"),
        )
