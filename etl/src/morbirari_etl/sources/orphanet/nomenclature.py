"""Adaptador del Orphanet Nomenclature Pack.

La columna vertebral multiidioma del sistema. Orphanet publica este pack en 9 idiomas
(CS, NL, EN, FR, DE, IT, PL, PT, ES) bajo CC BY 4.0, con etiquetas, sinónimos y
definiciones traducidas. El multiidioma de Morbi Rari no se construye: se ingiere.

Verificado contra el pack de julio de 2026 (11.645 enfermedades).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from lxml import etree

from morbirari_etl.config import ACTIVE_LANGS
from morbirari_etl.models.orphanet import (
    ORPHANET_RELATION_MAP,
    StagingDisease,
    StagingLabel,
    StagingXref,
)
from morbirari_etl.sources.base import (
    RawArtifact,
    download,
    raw_path,
    remote_fingerprint,
    sha256_file,
)

SOURCE_NAME = "orphanet"

PACK_URL = "https://www.orphacode.org/data/packs/Orphanet_Nomenclature_Pack_{LANG}.zip"

ATTRIBUTION = (
    "Orphanet: an online rare disease and orphan drug data base. © INSERM 1999. "
    "Available on http://www.orpha.net"
)

# Las definiciones traen HTML inline (<i>genu valgum</i>). Orphanet lo usa para
# términos latinos. Lo conservamos en el texto pero la web debe sanitizarlo:
# permitir énfasis, nada más.
_NOMENCLATURE_RE = re.compile(r"ORPHAnomenclature_(\w+)_(\d+)\.xml$")
_OMIM_MAPPING_RE = re.compile(r"ORPHA_OMIM_mapping_(\w+)_(\d+)\.xml$")


@dataclass(frozen=True)
class PackMeta:
    """Metadatos que el propio XML declara sobre sí mismo."""

    extraction_date: str
    version: str
    license_spdx: str | None


def _text(el: etree._Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


def read_pack_meta(xml_path: Path) -> PackMeta:
    """Lee la cabecera del XML: fecha de extracción, versión y licencia declarada.

    Orphanet declara su licencia dentro del propio fichero (<Availability><Licence>).
    La leemos del dato en vez de codificarla a mano, para que la tabla `source`
    refleje lo que la fuente dice de sí misma y no lo que nosotros creímos recordar.
    """
    context = etree.iterparse(str(xml_path), events=("start", "end"))
    extraction_date = version = license_spdx = None
    for event, el in context:
        if event == "start" and el.tag == "JDBOR":
            extraction_date = el.get("ExtractionDate")
            version = el.get("version")
        if event == "end" and el.tag == "ShortIdentifier":
            license_spdx = _text(el)
        if event == "end" and el.tag == "Availability":
            break
    return PackMeta(
        extraction_date=extraction_date or "unknown",
        version=version or "unknown",
        license_spdx=license_spdx,
    )


def fetch(langs: tuple[str, ...] = ACTIVE_LANGS, force: bool = False) -> list[RawArtifact]:
    """Descarga los packs por idioma, saltando los que no han cambiado."""
    artifacts: list[RawArtifact] = []
    for lang in langs:
        url = PACK_URL.format(LANG=lang.upper())
        etag, last_modified = remote_fingerprint(url)
        # La huella remota nombra el directorio: artefactos direccionados por contenido.
        version = _version_from_fingerprint(etag, last_modified)
        dest = raw_path(SOURCE_NAME, version, f"Orphanet_Nomenclature_Pack_{lang.upper()}.zip")

        if dest.exists() and not force:
            digest = sha256_file(dest)
        else:
            download(url, dest)
            digest = sha256_file(dest)

        artifacts.append(
            RawArtifact(
                source=SOURCE_NAME,
                path=dest,
                sha256=digest,
                source_url=url,
                etag=etag,
            )
        )
    return artifacts


def _version_from_fingerprint(etag: str | None, last_modified: str | None) -> str:
    if last_modified:
        # "Thu, 02 Jul 2026 07:06:46 GMT" -> "2026-07-02"
        from email.utils import parsedate_to_datetime

        try:
            return parsedate_to_datetime(last_modified).date().isoformat()
        except (TypeError, ValueError):
            pass
    if etag:
        return etag.strip('"').replace("/", "_")[:32]
    return "unknown"


def _extract_member(zip_path: Path, pattern: re.Pattern[str]) -> Path | None:
    """Extrae del zip el primer miembro que casa con el patrón."""
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if pattern.search(name):
                target_dir = zip_path.parent / "extracted"
                target_dir.mkdir(parents=True, exist_ok=True)
                extracted = Path(zf.extract(name, target_dir))
                return extracted
    return None


def parse(artifact: RawArtifact, lang: str) -> Iterator[StagingDisease]:
    """Parsea nomenclatura + mapping OMIM del pack de un idioma.

    Streaming con iterparse: el XML son ~21 MB por idioma y no hay razón para
    cargarlo entero.
    """
    nomenclature_xml = _extract_member(artifact.path, _NOMENCLATURE_RE)
    if nomenclature_xml is None:
        raise FileNotFoundError(f"No hay ORPHAnomenclature en {artifact.path}")

    omim_xml = _extract_member(artifact.path, _OMIM_MAPPING_RE)
    xrefs_by_orpha = _parse_omim_mapping(omim_xml) if omim_xml else {}

    for disease in _parse_nomenclature(nomenclature_xml, lang):
        disease.xrefs = xrefs_by_orpha.get(disease.orpha_code, [])
        yield disease


def _parse_nomenclature(xml_path: Path, lang: str) -> Iterator[StagingDisease]:
    context = etree.iterparse(str(xml_path), events=("end",), tag="Disorder")
    for _event, el in context:
        try:
            orpha_code = _text(el.find("OrphaCode"))
            if not orpha_code:
                continue

            labels: list[StagingLabel] = []
            name = _text(el.find("Name"))
            if name:
                labels.append(StagingLabel(lang=lang, label=name, label_type="preferred"))
            for syn in el.iterfind("SynonymList/Synonym"):
                s = _text(syn)
                if s:
                    labels.append(StagingLabel(lang=lang, label=s, label_type="synonym"))

            definition = None
            for section in el.iterfind("SummaryInformationList/SummaryInformation/"
                                       "TextSectionList/TextSection"):
                contents = _text(section.find("Contents"))
                if contents:
                    definition = contents
                    break

            yield StagingDisease(
                orpha_code=orpha_code,
                orphanet_internal_id=el.get("id"),
                disease_type=_text(el.find("DisorderType/Name")),
                classification_level=_text(el.find("ClassificationLevel/Name")),
                status=_text(el.find("Totalstatus")),
                expert_link=_text(el.find("ExpertLink")),
                labels=labels,
                definition=definition,
                definition_lang=lang if definition else None,
            )
        finally:
            # Liberar memoria: sin esto, iterparse retiene el árbol completo.
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]


def _parse_omim_mapping(xml_path: Path) -> dict[str, list[StagingXref]]:
    """Referencias cruzadas a OMIM, tal y como las publica Orphanet.

    Nota de licencia, verificada sobre el fichero real: este mapping contiene
    únicamente el número MIM, la relación de equivalencia y el estado de validación.
    No contiene ni un solo título de OMIM. Por eso es ingerible sin problema: los
    identificadores desnudos son hechos, y este fichero es CC BY 4.0 de Orphanet.
    Ver DATA_LICENSES.md.
    """
    out: dict[str, list[StagingXref]] = {}
    context = etree.iterparse(str(xml_path), events=("end",), tag="Disorder")
    for _event, el in context:
        try:
            orpha_code = _text(el.find("OrphaCode"))
            if not orpha_code:
                continue
            refs: list[StagingXref] = []
            for ext in el.iterfind("ExternalReferenceList/ExternalReference"):
                source_ns = _text(ext.find("Source"))
                reference = _text(ext.find("Reference"))
                if not source_ns or not reference:
                    continue
                relation_name = _text(ext.find("DisorderMappingRelation/Name")) or ""
                # "E (Exact mapping: the two concepts are equivalent)" -> "E"
                code = relation_name.split(" ", 1)[0].strip()
                validation = _text(ext.find("DisorderMappingValidationStatus/Name")) or ""
                refs.append(
                    StagingXref(
                        source_ns=source_ns,
                        source_id=reference,
                        relation=ORPHANET_RELATION_MAP.get(code, "unknown"),
                        validated=validation.lower().startswith("validated"),
                    )
                )
            if refs:
                out[orpha_code] = refs
        finally:
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]
    return out
