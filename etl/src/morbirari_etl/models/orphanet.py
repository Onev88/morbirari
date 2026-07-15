"""Modelos de staging para Orphanet.

Modelan la forma real del XML de ORPHAnomenclature_{lang}_{year}.xml, verificada
contra el pack de julio de 2026.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

LabelType = Literal["preferred", "synonym", "abbreviation"]

# Los cualificadores de mapeo de Orphanet. Aplanarlos a "es lo mismo" es como acabas
# diciéndole a un paciente que una categoría amplia y un subtipo concreto son la
# misma enfermedad.
XrefRelation = Literal["exact", "ntbt", "btnt", "nd", "unknown"]

ORPHANET_RELATION_MAP: dict[str, XrefRelation] = {
    "E": "exact",
    "NTBT": "ntbt",  # narrower term maps to broader term
    "BTNT": "btnt",  # broader term maps to narrower term
    "ND": "nd",  # not decided / not defined
}


class StagingLabel(BaseModel):
    lang: str
    label: str
    label_type: LabelType


class StagingXref(BaseModel):
    source_ns: str
    source_id: str
    relation: XrefRelation = "unknown"
    validated: bool = False

    @field_validator("source_id")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class StagingDisease(BaseModel):
    """Una enfermedad tal y como la publica Orphanet, antes de canonicalizar."""

    orpha_code: str
    # id interno de Orphanet: estable entre idiomas y entre productos del pack,
    # lo que lo hace la clave natural para unir EN con ES.
    orphanet_internal_id: str | None = None
    disease_type: str | None = None
    classification_level: str | None = None
    status: str | None = None
    expert_link: str | None = None
    labels: list[StagingLabel] = Field(default_factory=list)
    definition: str | None = None
    definition_lang: str | None = None
    xrefs: list[StagingXref] = Field(default_factory=list)

    @field_validator("orpha_code")
    @classmethod
    def _numeric(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError(f"orpha_code no numérico: {v!r}")
        return v
