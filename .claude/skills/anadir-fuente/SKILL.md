---
name: anadir-fuente
description: Andamiaje de una fuente de datos nueva en el ETL de Morbi Rari. Úsala al integrar un origen nuevo (una API, un pack descargable, un dataset) — cubre la comprobación de licencia, el adaptador fetch→parse→validate→load, la procedencia, los tests y el enganche del comando mr ingest.
---

# Añadir una fuente de datos

Sigue estos pasos **en orden**. El primero es un portón: si no se pasa, no se escribe código.

## 0. Licencia primero (portón)

- Lee [DATA_LICENSES.md](DATA_LICENSES.md) **antes de nada**.
- Confirma que la licencia permite lo que vas a hacer (ingerir, almacenar, redistribuir).
  - CC BY (como Orphanet): se puede, citando la fuente e indicando cambios.
  - **OMIM y similares restrictivos**: prohibido crear bases derivadas. Solo se guardan
    **identificadores (hechos) y se enlaza; nunca el texto**. Si la fuente es así, el diseño
    cambia: campos de IDs + enlace, y una **aserción en el loader** que impida persistir texto.
- Si la licencia no está clara, **para y pregunta**. No integres una fuente de licencia dudosa.

## 1. Adaptador de fuente — contrato `fetch → parse → validate → load`

Crea `etl/src/morbirari_etl/sources/<fuente>/` implementando el `Source` protocol de
[`sources/base.py`](etl/src/morbirari_etl/sources/base.py):

- **fetch**: descarga con `download`, aterriza el crudo en `raw_path(...)` y calcula su
  `sha256` (`sha256_file`). Usa `remote_fingerprint` (HEAD) + `version_from_fingerprint`
  para la versión. Si el checksum coincide con la última corrida, no hay trabajo (`--force`
  lo salta).
- **parse**: crudo → registros de staging. Sin tocar la base.
- **validate**: aborta si falla >2 % (`VALIDATION_FAILURE_THRESHOLD`); los datos viejos
  siguen sirviendo.

## 2. Loader idempotente con procedencia

En `etl/src/morbirari_etl/loaders/`:

- `upsert_source(...)` con `name`, `license_spdx` y `attribution_text` (la atribución exacta
  que exige la fuente).
- Abre un `ingest_run` (checksum, versión declarada, estado `running` → `success`).
- Upsert por clave natural; escribe un `provenance` por fila (fuente, versión, URL,
  `retrieved_at`). Reejecutar con los mismos datos no cambia nada salvo `last_seen`.
- **Borrado lógico**: `retire_missing` marca `status='retired'` lo ausente; nunca borres en
  duro.
- Si la fuente es restrictiva (OMIM), incluye la **aserción anti-texto**.

## 3. Esquema (si hace falta)

Columnas/tablas nuevas = **migración Alembic** (agente `esquema-migraciones`), nunca DDL
desde el loader. Si la web va a leer lo nuevo, actualiza los tipos de `db.ts`.

## 4. Comando `mr ingest <fuente>`

Añádelo en `etl/src/morbirari_etl/__main__.py` siguiendo el patrón de los existentes.
Hazlo **reanudable** (`--resume`) si son muchas peticiones a una API ajena.

## 5. Tests

Fixtures **pequeños y de fuentes CC BY** (los crudos no se versionan, ADR 0004). Cubre
parse, idempotencia (dos corridas → sin cambios salvo `last_seen`) y el retiro por ausencia.

## 6. Cierre

- Actualiza la tabla de fuentes del [README](README.md) y `DATA_LICENSES.md`.
- Verifica: `cd etl && pytest` y `mr status`.
- Pásale el agente `revisor-de-fuentes-licencias` antes de commitear.
