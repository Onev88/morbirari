"""Adaptador de GARD: unión organización-cuenta y clave natural.

El caso que motiva estos tests es un bug real: exigir que la organización estuviera en el
fichero de cuentas perdía las federaciones en español (que GARD lista por enfermedad pero
no cura como cuenta). Ahora se guardan todas; las que además están en el fichero se
enriquecen.
"""

from __future__ import annotations

import json

from morbirari_etl.sources.base import RawArtifact
from morbirari_etl.sources.gard.organizations import account_index, build_org

ACCOUNTS = [
    {
        "acct": {
            "Id": "0013d000ABC",
            "Name": "Cystic Fibrosis Foundation",
            "Website": "https://www.cff.org/",
            "Country__c": "United States",
            "Patient_Registry_URL__c": "https://www.cff.org/registry",
            "Expert_Directory_URL__c": "https://apps.cff.org/ccd",
            "RecordType": {"Name": "Patient Advocacy Group"},
        }
    }
]


def _artifact(tmp_path, data) -> RawArtifact:
    path = tmp_path / "all-account-data.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return RawArtifact(source="gard", path=path, sha256="x", source_url="u")


def test_account_index_keys_by_normalized_name(tmp_path):
    idx = account_index(_artifact(tmp_path, ACCOUNTS))
    # `normalize` baja a minúsculas y quita acentos, pero conserva los espacios.
    assert "cystic fibrosis foundation" in idx
    assert idx["cystic fibrosis foundation"]["id"] == "0013d000ABC"
    assert idx["cystic fibrosis foundation"]["country"] == "United States"


def test_build_org_enriches_when_matched(tmp_path):
    idx = account_index(_artifact(tmp_path, ACCOUNTS))
    org = build_org("Cystic Fibrosis Foundation", "https://www.cff.org/some-page", idx)
    # Clave natural = ID de cuenta de GARD cuando hay coincidencia.
    assert org.source_id == "0013d000ABC"
    assert org.country == "United States"
    assert org.expert_directory_url == "https://apps.cff.org/ccd"
    # La web de la cuenta (raíz) manda sobre la de la ficha (con ruta).
    assert org.website == "https://www.cff.org/"


def test_build_org_keeps_unmatched_orgs(tmp_path):
    idx = account_index(_artifact(tmp_path, ACCOUNTS))
    org = build_org("Federación Española de Fibrosis Quística", "https://fqfed.es", idx)
    # No está en el fichero de cuentas: se guarda igual, con nombre y web, y una clave
    # estable derivada del nombre.
    assert org.source_id.startswith("name:")
    assert org.website == "https://fqfed.es"
    assert org.country is None
    # Estable: el mismo nombre da la misma clave.
    twin = build_org("Federación Española de Fibrosis Quística", None, idx)
    assert org.source_id == twin.source_id
