"""Protocolo común a todas las fuentes.

Cada fuente implementa fetch -> parse -> validate -> load. El contrato importante:
los bytes crudos se aterrizan en disco y se identifican por su sha256 antes de
parsear nada. Si el checksum coincide con la última ejecución, no hay trabajo que
hacer. Esa es toda la historia de idempotencia.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

import httpx

from morbirari_etl.config import RAW_DIR


@dataclass(frozen=True)
class RawArtifact:
    """Bytes crudos aterrizados en disco, con su procedencia."""

    source: str
    path: Path
    sha256: str
    source_url: str
    # Versión declarada por la propia fuente (p. ej. ExtractionDate del XML de
    # Orphanet), no inventada por nosotros.
    source_version: str | None = None
    etag: str | None = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def remote_fingerprint(url: str) -> tuple[str | None, str | None]:
    """Huella remota (etag, last-modified) vía HEAD, sin descargar el cuerpo.

    Orphanet publica una vez al año, pero el mes ha variado entre junio y julio según
    la fuente que consultes. En vez de fijar un mes en código, sondeamos y actuamos
    cuando la huella cambia.
    """
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.head(url)
        resp.raise_for_status()
        return resp.headers.get("etag"), resp.headers.get("last-modified")


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=300) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in resp.iter_bytes(1024 * 256):
                    fh.write(chunk)
    return dest


def raw_path(source: str, version: str, filename: str) -> Path:
    return RAW_DIR / source / version / filename


def version_from_fingerprint(etag: str | None, last_modified: str | None) -> str:
    """Deriva un nombre de versión usable como directorio, a partir de la huella HTTP.

    Se prefiere Last-Modified porque da una fecha legible ("2026-07-02"). Si no lo
    hay, se cae al ETag, que hay que sanear: GitHub devuelve ETags débiles con la
    forma `W/"abc123"`, y tanto la barra como las comillas son ilegales en nombres de
    fichero en Windows.
    """
    if last_modified:
        from email.utils import parsedate_to_datetime

        try:
            return parsedate_to_datetime(last_modified).date().isoformat()
        except (TypeError, ValueError):
            pass
    if etag:
        safe = re.sub(r"[^A-Za-z0-9._-]", "", etag)
        if safe:
            return safe[:32]
    return "unknown"


class Source(Protocol):
    """Contrato de una fuente de datos."""

    name: str

    def fetch(self) -> list[RawArtifact]:
        """Descarga los artefactos crudos y los aterriza en disco."""
        ...

    def parse(self, artifact: RawArtifact) -> Iterator[object]:
        """Convierte bytes crudos en registros de staging."""
        ...
