"""Adaptadores de los Orphanet Scientific Knowledge Files.

Todos estos productos son CC BY 4.0 (verificado: cada XML declara su licencia en
<Availability><Licence>). Son lo que convierte la ficha en un dashboard:

  product9_prev  epidemiología: prevalencia por área geográfica       EN + ES
  product9_ages  historia natural: herencia y edad de inicio          EN + ES
  product4       signos clínicos (HPO) con frecuencia                 EN + ES
  product6       genes y sus referencias externas                     solo EN

Verificado contra la publicación de julio de 2026.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from lxml import etree

from morbirari_etl.sources.base import (
    RawArtifact,
    download,
    raw_path,
    remote_fingerprint,
    sha256_file,
    version_from_fingerprint,
)

PRODUCT_URL = "https://www.orphadata.com/data/xml/{lang}_{product}.xml"

# product6 (genes) solo existe en inglés: los símbolos de gen son universales y
# Orphanet no traduce los nombres.
ENGLISH_ONLY_PRODUCTS = frozenset({"product6"})


def _text(el: etree._Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    return el.text.strip() or None


def fetch_product(product: str, lang: str, force: bool = False) -> RawArtifact:
    effective_lang = "en" if product in ENGLISH_ONLY_PRODUCTS else lang
    url = PRODUCT_URL.format(lang=effective_lang, product=product)
    etag, last_modified = remote_fingerprint(url)
    version = version_from_fingerprint(etag, last_modified)

    dest = raw_path("orphanet", version, f"{effective_lang}_{product}.xml")
    if not dest.exists() or force:
        download(url, dest)

    return RawArtifact(
        source="orphanet",
        path=dest,
        sha256=sha256_file(dest),
        source_url=url,
        etag=etag,
    )


def read_meta(xml_path: Path) -> tuple[str, str | None]:
    """Devuelve (fecha de extracción, licencia SPDX) declaradas por el propio fichero."""
    context = etree.iterparse(str(xml_path), events=("start", "end"))
    date = license_spdx = None
    for event, el in context:
        if event == "start" and el.tag == "JDBOR":
            date = el.get("date") or el.get("ExtractionDate")
        if event == "end" and el.tag == "ShortIdentifier":
            license_spdx = _text(el)
        if event == "end" and el.tag == "Availability":
            break
    return date or "unknown", license_spdx


def _iter_clear(context) -> Iterator[etree._Element]:
    """iterparse con liberación de memoria: estos XML llegan a 100 MB."""
    for _event, el in context:
        try:
            yield el
        finally:
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]


# ---------------------------------------------------------------- epidemiología


@dataclass
class StagedPrevalence:
    orpha_code: str
    orphanet_prevalence_id: str
    prevalence_type: str | None
    prevalence_qualification: str | None
    prevalence_class: str | None
    val_moy: str | None
    geographic_area: str | None
    validation_status: str | None
    source: str | None


def parse_epidemiology(xml_path: Path) -> Iterator[StagedPrevalence]:
    context = etree.iterparse(str(xml_path), events=("end",), tag="Disorder")
    for el in _iter_clear(context):
        orpha_code = _text(el.find("OrphaCode"))
        if not orpha_code:
            continue
        for prev in el.iterfind("PrevalenceList/Prevalence"):
            prev_id = prev.get("id")
            if not prev_id:
                continue
            yield StagedPrevalence(
                orpha_code=orpha_code,
                orphanet_prevalence_id=prev_id,
                prevalence_type=_text(prev.find("PrevalenceType/Name")),
                prevalence_qualification=_text(prev.find("PrevalenceQualification/Name")),
                prevalence_class=_text(prev.find("PrevalenceClass/Name")),
                val_moy=_text(prev.find("ValMoy")),
                geographic_area=_text(prev.find("PrevalenceGeographic/Name")),
                validation_status=_text(prev.find("PrevalenceValidationStatus/Name")),
                source=_text(prev.find("Source")),
            )


# ------------------------------------------------------------- historia natural


@dataclass
class StagedAttribute:
    orpha_code: str
    attr_type: str  # inheritance | age_of_onset
    orphanet_attr_id: str
    value: str


def parse_natural_history(xml_path: Path) -> Iterator[StagedAttribute]:
    context = etree.iterparse(str(xml_path), events=("end",), tag="Disorder")
    for el in _iter_clear(context):
        orpha_code = _text(el.find("OrphaCode"))
        if not orpha_code:
            continue

        for onset in el.iterfind("AverageAgeOfOnsetList/AverageAgeOfOnset"):
            value = _text(onset.find("Name"))
            if value and onset.get("id"):
                yield StagedAttribute(orpha_code, "age_of_onset", onset.get("id"), value)

        for inh in el.iterfind("TypeOfInheritanceList/TypeOfInheritance"):
            value = _text(inh.find("Name"))
            if value and inh.get("id"):
                yield StagedAttribute(orpha_code, "inheritance", inh.get("id"), value)


# ------------------------------------------------------------------- fenotipos


@dataclass
class StagedPhenotype:
    orpha_code: str
    hpo_id: str
    hpo_term_en: str
    frequency_id: str | None
    diagnostic_criteria: str | None


def parse_phenotypes(xml_path: Path) -> Iterator[StagedPhenotype]:
    """El producto de fenotipos usa HPODisorderSetStatus, no DisorderList.

    Nota de idioma: aunque el fichero sea `es_product4`, el <HPOTerm> viene en inglés.
    Las traducciones se ingieren aparte (ver `hpo_translations.py`).
    """
    context = etree.iterparse(str(xml_path), events=("end",), tag="HPODisorderSetStatus")
    for el in _iter_clear(context):
        orpha_code = _text(el.find("Disorder/OrphaCode"))
        if not orpha_code:
            continue
        for assoc in el.iterfind("Disorder/HPODisorderAssociationList/HPODisorderAssociation"):
            hpo_id = _text(assoc.find("HPO/HPOId"))
            hpo_term = _text(assoc.find("HPO/HPOTerm"))
            if not hpo_id or not hpo_term:
                continue
            freq_el = assoc.find("HPOFrequency")
            yield StagedPhenotype(
                orpha_code=orpha_code,
                hpo_id=hpo_id,
                hpo_term_en=hpo_term,
                frequency_id=freq_el.get("id") if freq_el is not None else None,
                diagnostic_criteria=_text(assoc.find("DiagnosticCriteria/Name")),
            )


# ----------------------------------------------------------------------- genes


@dataclass
class StagedGene:
    orpha_code: str
    symbol: str
    name: str | None
    gene_type: str | None
    association_type: str | None
    association_status: str | None
    hgnc_id: str | None = None
    ensembl_id: str | None = None
    uniprot_id: str | None = None
    omim_id: str | None = None
    synonyms: list[str] = field(default_factory=list)
    source_pmids: list[str] = field(default_factory=list)


# Las referencias externas del gen que nos interesan. OMIM entra solo como
# identificador: el número es un hecho, su texto no se toca. Ver DATA_LICENSES.md.
_GENE_XREF_FIELDS = {
    "HGNC": "hgnc_id",
    "Ensembl": "ensembl_id",
    "SwissProt": "uniprot_id",
    "OMIM": "omim_id",
}


def parse_genes(xml_path: Path) -> Iterator[StagedGene]:
    context = etree.iterparse(str(xml_path), events=("end",), tag="Disorder")
    for el in _iter_clear(context):
        orpha_code = _text(el.find("OrphaCode"))
        if not orpha_code:
            continue

        for assoc in el.iterfind("DisorderGeneAssociationList/DisorderGeneAssociation"):
            gene_el = assoc.find("Gene")
            if gene_el is None:
                continue
            symbol = _text(gene_el.find("Symbol"))
            if not symbol:
                continue

            staged = StagedGene(
                orpha_code=orpha_code,
                symbol=symbol,
                name=_text(gene_el.find("Name")),
                gene_type=_text(gene_el.find("GeneType/Name")),
                association_type=_text(assoc.find("DisorderGeneAssociationType/Name")),
                association_status=_text(assoc.find("DisorderGeneAssociationStatus/Name")),
                synonyms=[s for s in (_text(x) for x in gene_el.iterfind("SynonymList/Synonym")) if s],
            )

            for ref in gene_el.iterfind("ExternalReferenceList/ExternalReference"):
                src = _text(ref.find("Source"))
                val = _text(ref.find("Reference"))
                if src in _GENE_XREF_FIELDS and val:
                    setattr(staged, _GENE_XREF_FIELDS[src], val)

            validation = _text(assoc.find("SourceOfValidation"))
            if validation:
                # "22587682[PMID]_9689990[PMID]" -> ["22587682", "9689990"]
                staged.source_pmids = [
                    part.split("[")[0]
                    for part in validation.split("_")
                    if "[PMID]" in part and part.split("[")[0].isdigit()
                ]

            yield staged
