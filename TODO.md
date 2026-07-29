# TODO

Trabajo pendiente que no encaja (todavía) en un ADR ni en el código. Las decisiones de
fondo van en [docs/adr/](docs/adr/); esto es la lista de lo que falta por hacer.

## Frescura de datos volátiles

### Programar el `--resume` periódico de ensayos clínicos

**Estado:** la caducidad ya está **implementada**; falta **programar** la ejecución periódica.

Los ensayos clínicos (ClinicalTrials.gov) son **datos volátiles**: un ensayo abre,
cambia de estado de reclutamiento y cierra. La [ADR 0001](docs/adr/0001-own-index-not-federation.md)
ya avisa de que necesitan una cadencia de refresco propia.

**Ya hecho** (commit «Registrar la consulta de ensayos, no solo el resultado»): la tabla
`trial_query` anota **cuándo** se consultó cada enfermedad —con resultado o sin él, porque
«no hay ensayos abiertos» también es una respuesta que hay que recordar—, y solo un error de
la fuente queda sin anotar para reintentarse. `mr ingest trials` gana `--refresh-after=30`
(días): en un `--resume`, vuelve a consultar lo caducado en vez de saltarlo por existir. El
filtro vive en `mesh_ids_by_disease(..., fresh_for_days=...)`
([`loaders/science.py`](etl/src/morbirari_etl/loaders/science.py)); la migración de estreno
rellena las enfermedades ya cargadas fechándolas por la procedencia de sus vínculos.

**Lo que falta:** disparar ese `--resume` de forma **periódica**. Hoy
[etl-scheduled.yml](.github/workflows/etl-scheduled.yml) solo reingiere Orphanet una vez al
mes; hay que ampliarlo con un `mr ingest trials --resume` en una cadencia propia (más frecuente
que la anual de Orphanet), para que el refresco de «dónde acudir» y «si están reclutando»
ocurra sin intervención manual.

**Origen:** decisión de la sesión «Morbi Rari rare disease system» (2026-07-16); caducidad
implementada e integrada el 2026-07-18.

## Fuentes bajo acuerdo

### Solicitud a Orphanet para el directorio de recursos expertos

**Estado:** decidido ([ADR 0006](docs/adr/0006-a-donde-acudir-fuentes-libres-orphanet-mas-adelante.md)), sin iniciar.

El directorio de Orphanet (centros expertos, asociaciones de pacientes, registros,
biobancos) es la mejor respuesta a «a dónde acudir», pero **no es de descarga libre**:
requiere un Data Transfer Agreement (uso académico) o un contrato de servicio (comercial).

La ADR 0006 decide ir primero con **fuentes libres** (GARD, ROR, Wikidata) y **más
adelante cursar la solicitud a Orphanet** para ver qué acceso es posible.

**Lo que hace falta:**

- Contactar al equipo de Orphadata (https://www.orphadata.com/expert-resources/) y
  determinar la vía aplicable (DTA académico vs contrato de servicio).
- Al firmar: actualizar [DATA_LICENSES.md](DATA_LICENSES.md) y escribir el adaptador —el
  patrón `fetch → parse → validate → load` ya existe—.

**Origen:** sesión de 2026-07-17.

---

## Hallazgos de revisión de calidad de código (2026-07-28)

### 🔴 Alta

#### 1. Extraer patrón repetido de `__main__.py` a decorador o context manager

**Archivo:** `etl/src/morbirari_etl/__main__.py`

El patrón `upsert_source → start_run → make_provenance → try/except/commit/finish_run` se repite ~9 veces (ingest_orphanet, ingest_science ×~3, ingest_drugs, ingest_nando, ingest_classifications, ingest_trials, ingest_gard). Cada repetición incluye:
```python
Session = get_sessionmaker()
pg.upsert_source(...)
pg.start_run(...)
pg.make_provenance(...)
try: ...; session.commit()
except Exception as exc: session.rollback(); raise typer.Exit(1)
pg.finish_run(...)
```

**Propuesta:** Extraer un decorador `@ingest_pipeline(source_name, license_spdx, attribution)` o un context manager que envuelva el ciclo completo. Esto reduce ~200 líneas y elimina 9 fuentes de error (olvidar rollback, no cerrar run, etc.).

---

#### 2. Agregar tests para la web app (`apps/web/`)

Actualmente **no hay ningún test** en `apps/web/`. El frontend no tiene:
- Tests de componentes (React Testing Library)
- Tests de integración de páginas
- Tests de los módulos `lib/dashboard.ts`, `lib/search.ts`, `lib/db.ts`

**Propuesta:** Agregar al menos tests de humo para:
- `lib/search.ts` — búsqueda con Meilisearch y fallback a trigramas
- `lib/dashboard.ts` — consultas SQL de dashboard (mockeando postgres)
- `lib/sanitize.ts` — sanitización HTML (datos de entrada)
- Tests de componentes para las páginas de enfermedad (`d/[slug]/page.tsx`) y búsqueda (`page.tsx`)

---

### 🟡 Media

#### 3. Reducir `except Exception` con `# noqa: BLE001`

**Archivo:** `etl/src/morbirari_etl/__main__.py` (~9 ocurrencias)

El linter (Ruff) emite BLE001 por `except Exception` porque atrapa `KeyboardInterrupt` y `SystemExit`. Aunque el código re-lanza con `typer.Exit(1)`, un `Ctrl+C` durante una ingesta larga no abortaría limpiamente.

**Propuesta:** Capturar `KeyboardInterrupt` primero para permitir aborto limpio, luego `Exception` como fallback. O refactorizar (ver punto 1).

---

#### 4. Dividir `d/[slug]/page.tsx` (921 líneas)

**Archivo:** `apps/web/src/app/[locale]/d/[slug]/page.tsx`

El componente `DiseasePage` maneja:
- 10+ fetching de datos en paralelo
- 10+ transformaciones a view models
- 12+ renderizados condicionales de secciones
- Lógica de filtrado (`trialFilterGroups`)

**Propuesta:** Extraer por responsabilidad:
- Hook personalizado `useDiseaseData(slug)` para el fetching (SSR con `searchParams`)
- Componente `DiseaseSections` que orqueste las secciones
- Un componente por sección (KeyFacts, Geography, ClinicalSigns, Genes, Trials, Drugs, etc.)
- Meta: página principal < 200 líneas, cada sección < 150 líneas

---

#### 5. Dividir `science.py` (860 líneas)

**Archivo:** `etl/src/morbirari_etl/loaders/science.py`

Carga 5 productos científicos (genes, fenotipos, epidemiología, herencia, edad de inicio) + traducciones HPO. Cada loader sigue el mismo patrón pero está en un solo archivo.

**Propuesta:** Mover a subpaquete `loaders/dashboard/` con un archivo por dominio:
- `genes.py`
- `phenotypes.py`
- `epidemiology.py`
- `clinical_attributes.py`
- `hpo_translations.py`

---

#### 6. Remover credenciales de desarrollo del código fuente

**Archivos:**
- `etl/src/morbirari_etl/config.py:20` — `DATABASE_URL` default con contraseña `morbirari_dev`
- `apps/web/src/lib/db.ts:11` — default URL con contraseña `morbirari_dev`

Aunque son sobreescribibles por variable de entorno, tener contraseñas en el código fuente es una mala práctica. Un despliegue que olvide configurar `DATABASE_URL` usará credenciales débiles y públicas.

**Propuesta:** Hacer que la aplicación valide que `DATABASE_URL` está definida al arrancar y falle con un mensaje claro si no. Mover los defaults a un `docker-compose.override.yml` o `.env.example`.

---

#### 7. Eliminar triplicación del helper `_text()`

**Archivos:**
- `nomenclature.py:61-64`
- `science.py:39-42`
- `classifications.py:48-51`

El helper `_text(el)` que extrae texto de elementos XML está definido idénticamente en 3 archivos.

**Propuesta:** Mover a un módulo compartido (ej. `etl/src/morbirari_etl/sources/_xml_helpers.py` o en `base.py`).

---

### 🟢 Baja

#### 8. Reemplazar números mágicos por constantes nombradas

- `base.py:39` — `1024 * 1024` (chunk size para sha256 → `SHA256_CHUNK_SIZE`)
- `base.py:63` — `1024 * 256` (chunk size para descarga → `DOWNLOAD_CHUNK_SIZE`)
- `science.py:63` — `1000` (batch size default → `DEFAULT_BATCH_SIZE`)
- `science.py:384` — `2000` (batch size para alignments)
- `science.py:428` — `200` (batch size para trials)
- `meilisearch.py:114` — `5, 9` (minWordSizeForTypos)
- `meilisearch.py:116` — `1000` (maxTotalHits)

---

#### 9. Agregar logging estructurado al ETL

Actualmente la salida de errores usa `console.print` (Rich) solo para consumo humano. No hay logs en formato JSON, sin niveles, sin integración con `logging`.

**Propuesta:** Agregar `structlog` o configurar `logging` con formato JSON para facilitar ingestión en sistemas de monitoreo. `console.print` puede coexistir para la salida interactiva.

---

#### 10. Agregar test de integración ETL completo

No existe un test que ejecute `fetch → parse → validate → load → index → query` end-to-end. Los tests actuales prueban componentes aislados.

**Propuesta:** Crear un test de integración que:
1. Use fixtures pequeños (ya existen en `tests/fixtures/orphanet/`)
2. Corra el pipeline completo contra una base de datos PostgreSQL de prueba (usando `testcontainers` o SQLite)
3. Verifique que los datos cargados sean consultables
