---
name: desarrollador
description: Cómo se desarrolla en Morbi Rari — stack, arranque, tests, flujo de git y las invariantes de diseño. Úsala al empezar cualquier tarea de código en este proyecto para trabajar según sus convenciones.
---

# Desarrollar en Morbi Rari

Antes de tocar nada, ten presentes las **reglas de diseño** de [CLAUDE.md](CLAUDE.md): son
la fuente de verdad. Esto es el resumen operativo para trabajar.

## Puesta en marcha

```bash
docker compose up -d                      # Postgres + Meilisearch
cd etl && python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m morbirari_etl ingest orphanet --lang en,es
./.venv/Scripts/python.exe -m morbirari_etl index rebuild --lang en,es
cd ../apps/web && npm install && npm run dev   # http://localhost:3000/es
```

## Dónde vive cada cosa

- `etl/` — pipeline Python (fuentes, loaders, indexadores, migraciones Alembic).
- `apps/web/` — Next.js (App Router, SSR). Lectura de datos en `src/lib/` (SQL a mano).
- `docs/adr/` — decisiones de fondo. `DATA_LICENSES.md` — licencias por fuente.

## Invariantes que no se negocian (detalle en CLAUDE.md)

- **Postgres = fuente de verdad; Meilisearch = proyección reconstruible.** Sin escritura dual.
- **Alembic es el único dueño del DDL.** La web es solo lectura, tipos a mano en `db.ts`.
- **Borrado lógico, idempotencia por checksum, procedencia y frescura por fila.**
- **Un índice por idioma; el multiidioma se ingiere, no se construye.**
- **Licencias**: leer `DATA_LICENSES.md` antes de tocar fuentes; guarda de OMIM.
- **No es consejo médico; la búsqueda por fenotipo no puntúa** (ADR 0002).

## Tests y verificación

```bash
cd etl && ./.venv/Scripts/python.exe -m pytest
cd apps/web && npm run typecheck && npm run build
```

No des algo por hecho sin verificarlo end-to-end. Si un test falla, dilo con la salida.

## Git

- `main` es la principal. El trabajo nuevo va en **`develop`** y se lleva a `main` por
  **fast-forward**. No commitees a `main` directo.
- Commits **en español**, descriptivos. No commitees ni hagas push salvo que se pida.
- Decisión con trade-offs → **ADR** (skill `escribir-adr`). Pendiente puntual → `TODO.md`.

## Agentes y skills a mano

`adaptador-etl`, `esquema-migraciones`, `calidad-de-busqueda`, `traductor-de-idiomas`,
`revisor-de-fuentes-licencias`; skills `anadir-fuente`, `escribir-adr`, `reindexar-y-verificar`.
Úsalos cuando la tarea encaje en su especialidad.
