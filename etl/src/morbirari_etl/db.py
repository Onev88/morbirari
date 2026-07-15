"""Esquema de base de datos. Alembic es el dueño único del DDL.

El lado TypeScript lee este esquema por introspección (drizzle-kit pull) y nunca
emite migraciones. Dos ORMs escribiendo DDL sobre una misma base es un desastre
conocido; aquí solo hay uno.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from morbirari_etl.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Source(Base):
    """Una fuente de datos y sus términos de licencia.

    `redistributable` no es documentación: existe para que la aplicación pueda
    filtrar automáticamente lo que no puede republicar. Un DATA_LICENSES.md que
    nadie lee se desincroniza; una columna que el código consulta, no.
    """

    __tablename__ = "source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    license_spdx: Mapped[str | None] = mapped_column(String(64))
    attribution_text: Mapped[str | None] = mapped_column(Text)
    homepage: Mapped[str | None] = mapped_column(Text)
    redistributable: Mapped[bool] = mapped_column(Boolean, default=False)


class IngestRun(Base):
    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|success|failed|skipped
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(String(128))
    record_counts: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship()


class Provenance(Base):
    """Quién dijo qué y cuándo. Toda fila de hecho apunta aquí."""

    __tablename__ = "provenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id", ondelete="CASCADE"))
    ingest_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingest_run.id", ondelete="SET NULL")
    )
    source_version: Mapped[str | None] = mapped_column(String(128))
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source_url: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship()


class Disease(Base):
    """La entidad canónica.

    ORPHA es el ancla en Fase 1; MONDO pasa a ser el eje de reconciliación en Fase 3.
    Los borrados son lógicos: Orphanet deprecia y fusiona códigos, y borrar en duro
    rompe todo enlace entrante y todo marcador de usuario.
    """

    __tablename__ = "disease"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    orpha_code: Mapped[str] = mapped_column(String(16), unique=True)
    mondo_id: Mapped[str | None] = mapped_column(String(32))
    disease_type: Mapped[str | None] = mapped_column(String(64))
    classification_level: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|retired
    expert_link: Mapped[str | None] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    labels: Mapped[list["DiseaseLabel"]] = relationship(
        back_populates="disease", cascade="all, delete-orphan"
    )
    xrefs: Mapped[list["DiseaseXref"]] = relationship(
        back_populates="disease", cascade="all, delete-orphan"
    )
    contents: Mapped[list["DiseaseContent"]] = relationship(
        back_populates="disease", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_disease_status", "status"),)


class DiseaseLabel(Base):
    """La columna vertebral multiidioma. La tabla de mayor valor del sistema."""

    __tablename__ = "disease_label"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    lang: Mapped[str] = mapped_column(String(8), index=True)
    label: Mapped[str] = mapped_column(Text)
    label_type: Mapped[str] = mapped_column(String(16))  # preferred|synonym|abbreviation
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    disease: Mapped[Disease] = relationship(back_populates="labels")

    __table_args__ = (
        UniqueConstraint("disease_id", "lang", "label", "label_type", name="uq_label"),
        Index("ix_disease_label_lang_type", "lang", "label_type"),
    )


class DiseaseXref(Base):
    """Referencias cruzadas a otros vocabularios.

    `relation` no es opcional a propósito: Orphanet publica cualificadores
    E/NTBT/BTNT/ND y aplanarlos a "es lo mismo" equivale a afirmar que una categoría
    amplia y un subtipo concreto son la misma enfermedad.

    Sobre OMIM: aquí solo van números MIM desnudos (hechos, no expresión protegible),
    nunca títulos ni texto de OMIM. Ver DATA_LICENSES.md.
    """

    __tablename__ = "disease_xref"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    source_ns: Mapped[str] = mapped_column(String(16), index=True)  # OMIM|ICD10|ICD11|MONDO|...
    source_id: Mapped[str] = mapped_column(String(64))
    relation: Mapped[str] = mapped_column(String(16), default="unknown")
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    disease: Mapped[Disease] = relationship(back_populates="xrefs")

    __table_args__ = (UniqueConstraint("disease_id", "source_ns", "source_id", name="uq_xref"),)


class DiseaseContent(Base):
    """Bloques de texto por idioma y audiencia.

    Las dos audiencias son un filtro de presentación, no un segundo dataset:
    un índice, una URL canónica.
    """

    __tablename__ = "disease_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    lang: Mapped[str] = mapped_column(String(8), index=True)
    audience: Mapped[str] = mapped_column(String(16), default="both")  # patient|clinician|both
    block_type: Mapped[str] = mapped_column(String(32))  # definition|...
    body: Mapped[str] = mapped_column(Text)
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    disease: Mapped[Disease] = relationship(back_populates="contents")

    __table_args__ = (
        UniqueConstraint("disease_id", "lang", "block_type", name="uq_content"),
    )


def get_engine(url: str | None = None):
    return create_engine(url or DATABASE_URL, future=True)


def get_sessionmaker(url: str | None = None):
    return sessionmaker(bind=get_engine(url), future=True, expire_on_commit=False)
