"""Normalización para emparejar fármacos con enfermedades.

Esta es la pieza más frágil del sistema y por eso está aquí. Ni la EMA ni la FDA
publican códigos ORPHA: la enfermedad llega como texto libre («Treatment of Wilson's
disease»). Un fallo aquí atribuye un fármaco a la enfermedad equivocada, que es peor
que no mostrar nada — desinforma a quien busca tratamiento para lo suyo.

Por eso el emparejamiento solo acepta coincidencia exacta del texto normalizado.
"""

from __future__ import annotations

import pytest

from morbirari_etl.sources.ema.orphan_drugs import normalize


@pytest.mark.parametrize(
    "raw,expected",
    [
        # El prefijo de la EMA se recorta: lo que importa es la enfermedad.
        ("Treatment of Wilson's disease", "wilson disease"),
        ("Treatment of cystic fibrosis", "cystic fibrosis"),
        ("Prevention of graft rejection", "graft rejection"),
        # Mayúsculas y espacios sobrantes no deben cambiar el resultado.
        ("  TREATMENT OF   Cystic   Fibrosis  ", "cystic fibrosis"),
        # Los acentos se pierden a propósito: las fuentes no son consistentes.
        ("Treatment of Ménière's disease", "meniere disease"),
        # Las palabras vacías se caen para que "treatment of the X" == "treatment of X".
        ("Treatment of the acute porphyria", "acute porphyria"),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_normalize_is_stable_for_equivalent_phrasings():
    """Dos formas de decir lo mismo deben normalizar igual, o no se emparejan."""
    assert normalize("Treatment of cystic fibrosis") == normalize("Cystic fibrosis")


def test_possessive_matches_orphanet_style():
    """El caso que motivó el genitivo: la EMA usa posesivo y Orphanet no.

    Sin esto, "Wilson's disease" (EMA) y "Wilson disease" (Orphanet) no casan y el
    fármaco no aparece en la ficha de la enfermedad a la que pertenece.
    """
    assert normalize("Treatment of Wilson's disease") == normalize("Wilson disease")
    assert normalize("Crohn's disease") == normalize("Crohn disease")


def test_normalize_keeps_distinct_diseases_distinct():
    """Lo esencial: dos enfermedades distintas NUNCA deben colisionar.

    Una colisión aquí significa mostrarle a un paciente el fármaco de otra
    enfermedad.
    """
    a = normalize("Treatment of Marfan syndrome")
    b = normalize("Treatment of Marfan syndrome type 2")
    c = normalize("Treatment of Wilson's disease")
    assert a != b
    assert a != c
    assert b != c


def test_normalize_empty():
    assert normalize("") == ""


def test_normalize_without_disease_matches_nothing():
    """Un «Treatment of» sin enfermedad no debe casar con ninguna etiqueta real."""
    # No se normaliza a cadena vacía (el prefijo exige algo detrás), pero lo que
    # importa es que no colisione con una enfermedad.
    assert normalize("Treatment of") != normalize("Cystic fibrosis")
