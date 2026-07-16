"""Calidad de búsqueda, contra el índice real.

Estos casos son regresiones de bugs reales, no ejemplos inventados. Cada uno se rompió
de verdad durante el desarrollo:

- «cistic fibrosis» devolvía un síndrome compuesto largo en vez de la fibrosis
  quística, porque Meilisearch no normaliza por longitud de campo como haría BM25.
- «mucoviscidosis» devolvía otra enfermedad, porque el orden por defecto valora el
  atributo antes que la exactitud y un sinónimo exacto perdía contra un nombre
  preferido que solo contenía la palabra.
- «CFTR» devolvía una enfermedad donde ese gen es solo candidato, porque Meilisearch
  evalúa la exactitud sobre el array completo y la fibrosis quística tiene 19 genes.

Requiere Meilisearch y datos cargados; se salta si no están, para no romper la CI.
"""

from __future__ import annotations

import pytest

meilisearch = pytest.importorskip("meilisearch")

from morbirari_etl.indexers.meilisearch import get_client, index_name  # noqa: E402


@pytest.fixture(scope="module")
def client():
    try:
        c = get_client()
        c.health()
        # Sin datos no hay nada que probar: mejor saltar que fallar en rojo.
        if c.index(index_name("es")).get_stats().number_of_documents == 0:
            pytest.skip("índice vacío: ejecuta `mr ingest` y `mr index rebuild`")
        return c
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Meilisearch no disponible: {exc}")


def top_hit(client, lang: str, query: str) -> str | None:
    res = client.index(index_name(lang)).search(
        query, {"limit": 1, "attributesToRetrieve": ["orpha_code"]}
    )
    hits = res["hits"]
    return hits[0]["orpha_code"] if hits else None


@pytest.mark.parametrize(
    "lang,query,expected,reason",
    [
        # Acentos y erratas: el caso de uso central del producto.
        ("es", "fibrosis quistica", "586", "sin tilde"),
        ("es", "fibrosis quistika", "586", "errata"),
        ("en", "cistic fibrosis", "586", "errata en inglés"),
        # Un sinónimo exacto gana a una coincidencia parcial en el nombre preferido.
        ("es", "mucoviscidosis", "586", "sinónimo exacto"),
        ("en", "CF", "586", "abreviatura"),
        # Identificadores: los clínicos buscan así.
        ("en", "OMIM:219700", "586", "xref con espacio de nombres"),
        ("en", "219700", "586", "xref desnudo"),
        # Genes: debe llevar a la enfermedad que el gen causa.
        ("es", "CFTR", "586", "gen causante, no candidato"),
        ("es", "FBN1", "284963", "gen causante"),
        ("en", "TGFBR2", "284973", "gen causante"),
        ("en", "DMD", "98896", "gen causante"),
        # Nombres normales.
        ("es", "sindrome de marfan", "558", "sin tilde"),
        ("en", "huntington disease", "399", "exacto"),
        ("en", "progeria", "740", "término común"),
    ],
)
def test_top_hit(client, lang, query, expected, reason):
    assert top_hit(client, lang, query) == expected, f"{reason}: «{query}»"
