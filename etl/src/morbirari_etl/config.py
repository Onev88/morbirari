"""Configuración por entorno."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# La raíz del repo, subiendo desde etl/src/morbirari_etl/config.py
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = Path(os.getenv("MORBIRARI_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://morbirari:morbirari_dev@localhost:5432/morbirari",
)

MEILI_URL = os.getenv("MEILI_URL", "http://localhost:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "morbirari_dev_master_key")

# Idiomas activos. Fase 1: EN + ES. Orphanet publica 9.
# Añadir un idioma aquí debe ser lo único necesario para soportarlo.
ACTIVE_LANGS = tuple(os.getenv("MORBIRARI_LANGS", "en,es").split(","))

ORPHANET_LANGS = ("cs", "nl", "en", "fr", "de", "it", "pl", "pt", "es")

# Si más de este porcentaje de registros falla la validación, se aborta la ingesta
# y los datos vivos siguen sirviendo. Mejor obsoleto y correcto que fresco y erróneo.
VALIDATION_FAILURE_THRESHOLD = 0.02
