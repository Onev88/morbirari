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


class Gene(Base):
    """Un gen. Los símbolos HGNC son universales, así que no llevan idioma.

    Orphanet no traduce los nombres de gen: `name` queda en inglés siempre.
    """

    __tablename__ = "gene"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    gene_type: Mapped[str | None] = mapped_column(String(64))
    hgnc_id: Mapped[str | None] = mapped_column(String(32))
    ensembl_id: Mapped[str | None] = mapped_column(String(32))
    uniprot_id: Mapped[str | None] = mapped_column(String(32))
    # Identificador MIM del gen: un número desnudo es un hecho. Nunca su texto.
    omim_id: Mapped[str | None] = mapped_column(String(16))
    synonyms: Mapped[list | None] = mapped_column(JSONB)

    __table_args__ = (Index("ix_gene_symbol", "symbol"),)


class DiseaseGene(Base):
    """Asociación enfermedad-gen, con el tipo de relación y su respaldo.

    `source_pmids` guarda los PMID con que Orphanet respalda la asociación: es lo que
    convierte un dato en algo verificable en vez de una afirmación.
    """

    __tablename__ = "disease_gene"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    gene_id: Mapped[int] = mapped_column(ForeignKey("gene.id", ondelete="CASCADE"), index=True)
    association_type: Mapped[str | None] = mapped_column(String(128))
    association_status: Mapped[str | None] = mapped_column(String(64))
    source_pmids: Mapped[list | None] = mapped_column(JSONB)
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    gene: Mapped[Gene] = relationship()

    __table_args__ = (UniqueConstraint("disease_id", "gene_id", name="uq_disease_gene"),)


class Phenotype(Base):
    """Término HPO. El label canónico es el inglés que publica Orphanet."""

    __tablename__ = "phenotype"

    hpo_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    label_en: Mapped[str] = mapped_column(Text)


class PhenotypeLabel(Base):
    """Traducción oficial de un término HPO.

    Orphanet publica las anotaciones de fenotipo pero NO traduce los términos HPO:
    en `es_product4` el término sigue siendo "Macrocephaly". Las traducciones vienen
    del proyecto oficial hpo-translations (obophenotype/hpo-translations), que sí las
    publica revisadas. Sin esto, el modo español mostraría los síntomas en inglés.
    """

    __tablename__ = "phenotype_label"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hpo_id: Mapped[str] = mapped_column(
        ForeignKey("phenotype.hpo_id", ondelete="CASCADE"), index=True
    )
    lang: Mapped[str] = mapped_column(String(8), index=True)
    label: Mapped[str] = mapped_column(Text)
    translation_status: Mapped[str | None] = mapped_column(String(32))
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    __table_args__ = (UniqueConstraint("hpo_id", "lang", name="uq_phenotype_label"),)


# Ids de frecuencia de Orphanet -> orden de presentación. Los ids son estables entre
# versiones; el texto no (cambia con el idioma). Ordenar por el texto sería frágil.
# Un id desconocido cae a rank NULL y se muestra al final, en vez de romper.
HPO_FREQUENCY_RANK: dict[str, int] = {
    "28405": 1,  # Obligate (100%)
    "28412": 2,  # Very frequent (99-80%)
    "28419": 3,  # Frequent (79-30%)
    "28426": 4,  # Occasional (29-5%)
    "28433": 5,  # Very rare (<4-1%)
    "28440": 6,  # Excluded (0%)
}


class DiseasePhenotype(Base):
    """Signo clínico asociado a una enfermedad, con su frecuencia.

    Esto describe la enfermedad; no diagnostica a nadie. La búsqueda inversa
    (síntomas -> enfermedades) está restringida por el ADR 0002.
    """

    __tablename__ = "disease_phenotype"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    hpo_id: Mapped[str] = mapped_column(
        ForeignKey("phenotype.hpo_id", ondelete="CASCADE"), index=True
    )
    frequency_id: Mapped[str | None] = mapped_column(String(16))
    frequency_rank: Mapped[int | None] = mapped_column(Integer)
    diagnostic_criteria: Mapped[str | None] = mapped_column(String(64))
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    phenotype: Mapped[Phenotype] = relationship()

    __table_args__ = (
        UniqueConstraint("disease_id", "hpo_id", name="uq_disease_phenotype"),
        Index("ix_disease_phenotype_rank", "disease_id", "frequency_rank"),
    )


class Epidemiology(Base):
    """Prevalencia con su ámbito geográfico.

    Orphanet publica cada dato de prevalencia atado a un área (Mundial, Europa,
    España, Japón…) y a veces a una población concreta. Guardar solo un número
    global perdería justo lo interesante: dónde se documenta la enfermedad.
    """

    __tablename__ = "epidemiology"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    lang: Mapped[str] = mapped_column(String(8), index=True)
    # id estable de Orphanet, para poder cruzar idiomas sin depender del texto
    orphanet_prevalence_id: Mapped[str] = mapped_column(String(16))
    prevalence_type: Mapped[str | None] = mapped_column(String(64))
    prevalence_qualification: Mapped[str | None] = mapped_column(String(64))
    prevalence_class: Mapped[str | None] = mapped_column(String(64))
    val_moy: Mapped[str | None] = mapped_column(String(32))
    geographic_area: Mapped[str | None] = mapped_column(String(128))
    validation_status: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(Text)
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("orphanet_prevalence_id", "lang", name="uq_epidemiology"),
        Index("ix_epidemiology_geo", "geographic_area"),
    )


class DiseaseAttribute(Base):
    """Atributos multivalor y traducidos: herencia y edad de inicio.

    Van juntos en una tabla porque comparten forma exacta (lista de términos
    traducidos por enfermedad) y porque Orphanet los publica en el mismo producto.
    """

    __tablename__ = "disease_attribute"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    lang: Mapped[str] = mapped_column(String(8), index=True)
    attr_type: Mapped[str] = mapped_column(String(32))  # inheritance | age_of_onset
    orphanet_attr_id: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(128))
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint(
            "disease_id", "lang", "attr_type", "orphanet_attr_id", name="uq_disease_attribute"
        ),
    )


class Trial(Base):
    """Un ensayo clínico registrado en ClinicalTrials.gov.

    Es la mejor respuesta libre a «dónde se investiga esto» y «a dónde puedo acudir»:
    los centros expertos y las asociaciones de pacientes de Orphanet exigen firmar un
    acuerdo de transferencia de datos, mientras que ClinicalTrials.gov es obra del
    gobierno de EE.UU. y publica quién investiga, dónde y si está reclutando.
    """

    __tablename__ = "trial"

    nct_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    phase: Mapped[str | None] = mapped_column(String(32))
    study_type: Mapped[str | None] = mapped_column(String(32))
    lead_sponsor: Mapped[str | None] = mapped_column(Text)
    sponsor_class: Mapped[str | None] = mapped_column(String(32))
    enrollment: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[str | None] = mapped_column(String(16))
    last_update: Mapped[str | None] = mapped_column(String(16))
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    locations: Mapped[list["TrialLocation"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan"
    )


class TrialLocation(Base):
    """Un centro donde se lleva a cabo un ensayo. Esto es el «a dónde acudir»."""

    __tablename__ = "trial_location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(
        ForeignKey("trial.nct_id", ondelete="CASCADE"), index=True
    )
    facility: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str | None] = mapped_column(String(32))

    trial: Mapped[Trial] = relationship(back_populates="locations")

    __table_args__ = (
        UniqueConstraint("nct_id", "facility", "city", name="uq_trial_location"),
    )


class DiseaseTrial(Base):
    """Vínculo enfermedad-ensayo. Siempre inferido, nunca afirmado.

    ClinicalTrials.gov no conoce los códigos ORPHA. El vínculo se establece a través
    del código MeSH que Orphanet publica para la enfermedad, que es mucho más fiable
    que casar cadenas de texto — pero sigue siendo una inferencia nuestra, no un dato
    de la fuente. Por eso `match_method` y `match_confidence` existen y la interfaz
    lo dice.
    """

    __tablename__ = "disease_trial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    nct_id: Mapped[str] = mapped_column(ForeignKey("trial.nct_id", ondelete="CASCADE"))
    match_method: Mapped[str] = mapped_column(String(32))  # mesh | text
    match_confidence: Mapped[str] = mapped_column(String(16))  # high | medium | low
    matched_on: Mapped[str | None] = mapped_column(String(64))
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    trial: Mapped[Trial] = relationship()

    __table_args__ = (UniqueConstraint("disease_id", "nct_id", name="uq_disease_trial"),)


class OrphanDrug(Base):
    """Designación de medicamento huérfano de una agencia reguladora.

    Ojo con lo que esto es y no es: una designación huérfana NO significa que el
    fármaco esté aprobado ni disponible. Significa que el regulador ha reconocido que
    se desarrolla para una enfermedad rara. La interfaz debe decirlo, o el dato se
    lee como «hay tratamiento», que es exactamente lo que no dice.
    """

    __tablename__ = "orphan_drug"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency: Mapped[str] = mapped_column(String(16), index=True)  # EMA | FDA
    designation_number: Mapped[str] = mapped_column(String(64))
    medicine_name: Mapped[str | None] = mapped_column(Text)
    active_substance: Mapped[str | None] = mapped_column(Text)
    intended_use: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(32))
    designation_date: Mapped[str | None] = mapped_column(String(16))
    url: Mapped[str | None] = mapped_column(Text)
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("agency", "designation_number", name="uq_orphan_drug"),
    )


class DiseaseDrug(Base):
    """Vínculo enfermedad-fármaco. Inferido por texto, y por eso el más frágil.

    Ni la EMA ni la FDA publican códigos ORPHA: la enfermedad es texto libre
    («Treatment of Wilson's disease»). El emparejamiento es nuestro y puede fallar,
    así que se guarda con qué se emparejó y con cuánta confianza, y la interfaz lo
    presenta como una sugerencia verificable, no como un hecho.
    """

    __tablename__ = "disease_drug"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disease.id", ondelete="CASCADE"), index=True
    )
    drug_id: Mapped[int] = mapped_column(ForeignKey("orphan_drug.id", ondelete="CASCADE"))
    match_method: Mapped[str] = mapped_column(String(32))
    match_confidence: Mapped[str] = mapped_column(String(16))
    matched_on: Mapped[str | None] = mapped_column(Text)

    drug: Mapped[OrphanDrug] = relationship()

    __table_args__ = (UniqueConstraint("disease_id", "drug_id", name="uq_disease_drug"),)


class Classification(Base):
    """Una de las ~33 clasificaciones de Orphanet, por especialidad médica."""

    __tablename__ = "classification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    orpha_root: Mapped[str] = mapped_column(String(16))
    lang: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(Text)
    provenance_id: Mapped[int | None] = mapped_column(
        ForeignKey("provenance.id", ondelete="SET NULL")
    )

    __table_args__ = (UniqueConstraint("orpha_root", "lang", name="uq_classification"),)


class ClassificationEdge(Base):
    """Arista padre->hijo dentro de una clasificación.

    Se guarda por código ORPHA y no por disease_id porque los árboles incluyen nodos
    de agrupación que pueden no estar en `disease`. Resolver a disease_id al consultar
    mantiene la ingesta simple y tolerante a huecos.
    """

    __tablename__ = "classification_edge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classification_id: Mapped[int] = mapped_column(
        ForeignKey("classification.id", ondelete="CASCADE"), index=True
    )
    parent_orpha: Mapped[str | None] = mapped_column(String(16), index=True)
    child_orpha: Mapped[str] = mapped_column(String(16), index=True)

    __table_args__ = (
        UniqueConstraint(
            "classification_id", "parent_orpha", "child_orpha", name="uq_classification_edge"
        ),
    )


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
