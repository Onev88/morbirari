"""La guarda de licencia es la prueba más importante de este repositorio.

Si esto se rompe, el proyecto puede acabar redistribuyendo material propietario de
OMIM desde un repositorio público. Ver DATA_LICENSES.md y ADR 0002.
"""

from __future__ import annotations

import pytest

from morbirari_etl.loaders.postgres import (
    LicenseViolation,
    assert_no_omim_text,
    slugify,
)


def test_omim_identifier_is_allowed():
    """Un número MIM desnudo es un hecho, no expresión protegible."""
    assert_no_omim_text("OMIM", None)


def test_omim_text_raises():
    """La trampa real: `disease_name` de phenotype.hpoa es el título de OMIM."""
    with pytest.raises(LicenseViolation, match="OMIM"):
        assert_no_omim_text("OMIM", "CYSTIC FIBROSIS; CF")


def test_omim_text_raises_lowercase_namespace():
    with pytest.raises(LicenseViolation):
        assert_no_omim_text("omim", "MARFAN SYNDROME; MFS")


def test_other_namespaces_may_carry_text():
    """Orphanet, MONDO y HPO son CC BY: su texto sí se puede almacenar."""
    assert_no_omim_text("MONDO", "cystic fibrosis")
    assert_no_omim_text("ICD10", "E84")


@pytest.mark.parametrize(
    "label,code,expected",
    [
        ("Cystic fibrosis", "586", "cystic-fibrosis-orpha-586"),
        ("Fibrosis quística", "586", "fibrosis-quistica-orpha-586"),
        ("Síndrome de Marfan", "558", "sindrome-de-marfan-orpha-558"),
        ("", "999", "orpha-999"),
        ("A/B  ---  C", "1", "a-b-c-orpha-1"),
    ],
)
def test_slugify(label, code, expected):
    assert slugify(label, code) == expected
