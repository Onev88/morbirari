"""Tests del parser de Orphanet contra fixtures fijados.

El fixture es el contrato: si Orphanet cambia la forma de su XML, estos tests fallan
y la ingesta se detiene antes de meter datos erróneos en producción.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from morbirari_etl.sources.orphanet.nomenclature import (
    _parse_nomenclature,
    _parse_omim_mapping,
    read_pack_meta,
)

FIXTURES = Path(__file__).parent / "fixtures" / "orphanet"
NOMENCLATURE = FIXTURES / "ORPHAnomenclature_en_2026.xml"
OMIM_MAPPING = FIXTURES / "ORPHA_OMIM_mapping_en_2026.xml"


def test_pack_meta_reads_declared_license():
    """La licencia se lee de lo que el fichero declara, no de lo que recordamos."""
    meta = read_pack_meta(NOMENCLATURE)
    assert meta.license_spdx == "CC-BY-4.0"
    assert meta.extraction_date == "2026-06-23 07:28:38"
    assert "1.3.42" in meta.version


def test_parses_all_disorders():
    diseases = list(_parse_nomenclature(NOMENCLATURE, "en"))
    assert len(diseases) == 3
    assert {d.orpha_code for d in diseases} == {"586", "558", "99999"}


def test_labels_and_synonyms():
    diseases = {d.orpha_code: d for d in _parse_nomenclature(NOMENCLATURE, "en")}
    cf = diseases["586"]

    preferred = [lb for lb in cf.labels if lb.label_type == "preferred"]
    assert len(preferred) == 1
    assert preferred[0].label == "Cystic fibrosis"
    assert preferred[0].lang == "en"

    synonyms = sorted(lb.label for lb in cf.labels if lb.label_type == "synonym")
    assert synonyms == ["CF", "Mucoviscidosis"]


def test_definition_preserves_inline_emphasis():
    """Orphanet usa <i> para términos latinos; se conserva y se sanea al renderizar."""
    diseases = {d.orpha_code: d for d in _parse_nomenclature(NOMENCLATURE, "en")}
    assert "<i>in vivo</i>" in diseases["586"].definition


def test_disease_without_definition():
    diseases = {d.orpha_code: d for d in _parse_nomenclature(NOMENCLATURE, "en")}
    assert diseases["558"].definition is None


def test_inactive_status_is_read():
    diseases = {d.orpha_code: d for d in _parse_nomenclature(NOMENCLATURE, "en")}
    assert diseases["99999"].status == "Inactive"
    assert diseases["586"].status == "Active"


def test_omim_mapping_relations():
    """Los cualificadores E/NTBT no se pueden aplanar a 'es lo mismo'."""
    xrefs = _parse_omim_mapping(OMIM_MAPPING)

    cf = xrefs["586"][0]
    assert cf.source_ns == "OMIM"
    assert cf.source_id == "219700"
    assert cf.relation == "exact"
    assert cf.validated is True

    marfan = xrefs["558"][0]
    assert marfan.relation == "ntbt"
    assert marfan.validated is False


def test_omim_mapping_carries_no_omim_titles():
    """Verificación de licencia: el mapping solo debe traer identificadores.

    Este test documenta el hecho verificado sobre los datos reales de Orphanet y
    fallaría si un cambio futuro empezara a extraer texto propiedad de OMIM.
    """
    xrefs = _parse_omim_mapping(OMIM_MAPPING)
    for refs in xrefs.values():
        for ref in refs:
            assert not hasattr(ref, "label") or getattr(ref, "label", None) is None
            assert ref.source_id.isdigit()


def test_orpha_code_must_be_numeric():
    from morbirari_etl.models.orphanet import StagingDisease

    with pytest.raises(ValueError, match="no numérico"):
        StagingDisease(orpha_code="ORPHA:586")
