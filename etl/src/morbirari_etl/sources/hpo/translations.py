"""Traducciones oficiales de los términos HPO.

Por qué existe esto: Orphanet publica las anotaciones de fenotipo en 9 idiomas, pero
**no traduce los términos HPO**. En `es_product4`, el síntoma sigue siendo
"Macrocephaly". Para un paciente hispanohablante eso no sirve de nada.

El proyecto oficial obophenotype/hpo-translations sí publica traducciones revisadas
(19.932 términos al español, marcadas OFFICIAL). Formato Babelon (TSV).

Licencia: HPO, custom (sin identificador SPDX). Exige citar al HPO Consortium y no
alterar el contenido. Se almacena verbatim.

Nota importante: esto NO es `phenotype.hpoa`. Ese fichero trae una columna
`disease_name` que, en las filas OMIM, es texto propiedad de Johns Hopkins. Este solo
contiene términos HPO traducidos, sin datos de enfermedades, así que no arrastra esa
trampa. Ver DATA_LICENSES.md.
"""

from __future__ import annotations

import csv
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

SOURCE_NAME = "hpo-translations"

URL = (
    "https://raw.githubusercontent.com/obophenotype/hpo-translations/main/"
    "babelon/hp-{lang}.babelon.tsv"
)

ATTRIBUTION = (
    "Human Phenotype Ontology translations, HPO Consortium. "
    "https://github.com/obophenotype/hpo-translations"
)

# Idiomas con traducción publicada. El inglés es el original, no necesita traducción.
AVAILABLE_LANGS = frozenset({"es", "nl", "fr", "de", "it", "cs", "ja", "tr", "zh"})


@dataclass(frozen=True)
class StagedTranslation:
    hpo_id: str
    lang: str
    label: str
    status: str | None


def fetch(lang: str, force: bool = False) -> RawArtifact | None:
    if lang not in AVAILABLE_LANGS:
        return None

    url = URL.format(lang=lang)
    etag, last_modified = remote_fingerprint(url)
    version = version_from_fingerprint(etag, last_modified)

    dest = raw_path(SOURCE_NAME, version, f"hp-{lang}.babelon.tsv")
    if not dest.exists() or force:
        download(url, dest)

    return RawArtifact(
        source=SOURCE_NAME,
        path=dest,
        sha256=sha256_file(dest),
        source_url=url,
        etag=etag,
    )


def parse(artifact: RawArtifact) -> Iterator[StagedTranslation]:
    with artifact.path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            # Solo etiquetas: los sinónimos van en otro fichero y no los usamos aún.
            if row.get("predicate_id") != "rdfs:label":
                continue
            hpo_id = (row.get("subject_id") or "").strip()
            label = (row.get("translation_value") or "").strip()
            lang = (row.get("translation_language") or "").strip()
            if not hpo_id or not label or not lang:
                continue
            yield StagedTranslation(
                hpo_id=hpo_id,
                lang=lang,
                label=label,
                status=(row.get("translation_status") or "").strip() or None,
            )
