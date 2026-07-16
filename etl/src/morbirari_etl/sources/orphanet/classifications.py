"""Clasificaciones de Orphanet: la jerarquía por especialidad médica.

Los 33 ficheros ORPHAclassification_*.xml ya vienen dentro del Nomenclature Pack que
descargamos para la nomenclatura, así que esto no añade ni una petición de red.

Convierten el sitio en algo navegable además de buscable: dónde encaja una enfermedad,
qué subtipos tiene y cuáles son sus hermanas.

Estructura del XML: nodos ClassificationNode anidados, cada uno con su Disorder.
El anidamiento *es* la jerarquía.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from lxml import etree

CLASSIFICATION_RE = re.compile(r"ORPHAclassification_(\d+)_(.+?)_(\w+)_(\d+)\.xml$")


@dataclass
class StagedClassification:
    orpha_root: str
    name: str
    lang: str
    edges: list[tuple[str | None, str]]  # (padre, hijo) por código ORPHA


def list_classification_members(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as zf:
        return [n for n in zf.namelist() if CLASSIFICATION_RE.search(n)]


def extract_classifications(zip_path: Path) -> list[Path]:
    out: list[Path] = []
    target_dir = zip_path.parent / "extracted"
    with zipfile.ZipFile(zip_path) as zf:
        for name in list_classification_members(zip_path):
            out.append(Path(zf.extract(name, target_dir)))
    return out


def _text(el: etree._Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    return el.text.strip() or None


def parse_classification(xml_path: Path, lang: str) -> StagedClassification | None:
    """Aplana el árbol anidado a una lista de aristas padre->hijo.

    Se guardan códigos ORPHA en crudo, sin resolver a disease_id: los árboles
    contienen nodos de agrupación que pueden no existir en `disease`, y resolver al
    consultar mantiene la ingesta simple y tolerante a esos huecos.
    """
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    classification_el = root.find(".//Classification")
    if classification_el is None:
        return None

    name = _text(classification_el.find("Name")) or xml_path.stem
    orpha_root = _text(classification_el.find("OrphaNumber")) or _text(
        classification_el.find("OrphaCode")
    )
    if not orpha_root:
        m = CLASSIFICATION_RE.search(xml_path.name)
        orpha_root = m.group(1) if m else xml_path.stem

    edges: list[tuple[str | None, str]] = []

    def walk(node: etree._Element, parent_orpha: str | None) -> None:
        disorder = node.find("Disorder")
        current = _text(disorder.find("OrphaCode")) if disorder is not None else None
        if current:
            edges.append((parent_orpha, current))
        child_list = node.find("ClassificationNodeChildList")
        if child_list is not None:
            for child in child_list.iterfind("ClassificationNode"):
                walk(child, current or parent_orpha)

    for node in classification_el.iterfind(".//ClassificationNodeRootList/ClassificationNode"):
        walk(node, None)

    if not edges:
        return None

    return StagedClassification(orpha_root=orpha_root, name=name, lang=lang, edges=edges)


def parse_all(zip_path: Path, lang: str) -> Iterator[StagedClassification]:
    for xml_path in extract_classifications(zip_path):
        parsed = parse_classification(xml_path, lang)
        if parsed:
            yield parsed
