# Morbi Rari — Revisión de Arquitectura

> Fecha: 2026-07-28

---

## 1. Patrón Arquitectónico

**ETL off-line + Web App (Next.js SSR).** Dos componentes independientes que comparten PostgreSQL como fuente de verdad. Meilisearch es una proyección reconstruible, no una fuente primaria.

```
┌─────────────────────────────────────────────────────────────────┐
│  ETL (Python 3.12+) — Comando `mr`                             │
│                                                                 │
│  Fuentes externas                                               │
│  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │Orphanet │  │   EMA    │  │Clinical │  │  GARD / NANDO    │  │
│  │  (XML)  │  │  (XLSX)  │  │Trials   │  │  / HPO           │  │
│  └────┬───┘  └────┬─────┘  │  (JSON)  │  └──────┬───────────┘  │
│       │           │        └────┬─────┘         │              │
│       ▼           ▼             ▼               ▼              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  fetch → parse (Pydantic) → validate (threshold 2%)     │   │
│  │  → load (SQLAlchemy upsert) → Postgres 16               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                │                                 │
│  ┌────────────────────────────┘                                 │
│  │                                                               │
│  ▼                                                               │
│  mr index rebuild → Meilisearch 1.11 (1 índice por idioma)      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Web App (Next.js 15, App Router, SSR)                          │
│                                                                  │
│  Búsqueda: Meilisearch SDK (con fallback a pg_trgm en Postgres) │
│  Detalle: SQL directo a Postgres (cliente postgres, porsager)   │
│  i18n: next-intl, locale en URL ([locale]/)                     │
└──────────────────────────────────────────────────────────────────┘
```

### Principios Arquitectónicos Clave

| Principio | Cómo se cumple |
|---|---|
| **Postgres es la fuente de verdad** | Toda escritura va a Postgres. Meilisearch es solo una proyección |
| **No dual-write** | No se escribe a la vez en Postgres y Meilisearch. El índice se reconstruye bajo demanda |
| **Idempotencia por SHA256** | Mismo checksum = mismo contenido = no se reprocesa |
| **Borrado lógico** | `status='retired'`, nunca DELETE físico |
| **Alembic dueño del DDL** | TypeScript nunca emite DDL. La web usa SQL de solo lectura |
| **Un índice por idioma** | Mezclar idiomas envenena el ranking de búsqueda |

---

## 2. Límites entre Módulos

### Separación ETL / Web App: Excelente

| Aspecto | ETL | Web App |
|---|---|---|
| Runtime | Python 3.12+ | Node 24 |
| Entry point | `python -m morbirari_etl` | `next dev / next start` |
| Schema authority | Alembic (dueño del DDL) | Nunca emite DDL |
| Data access | SQLAlchemy ORM | Cliente `postgres` raw (solo SELECT) |
| Search index | Construye Meilisearch | Consume Meilisearch |

### Dependencias ETL (limpias)

```
sources/
  base.py (Protocol Source)
  orphanet/nomenclature.py, science.py, classifications.py
  ema/orphan_drugs.py
  clinicaltrials/trials.py
  gard/organizations.py
  hpo/translations.py
  nando/japan.py
      │
      ▼
loaders/
  postgres.py (CRUD básico)
  science.py (dashboard data)
      │
      ▼
indexers/
  meilisearch.py (reconstrucción de índice)
```

### Problemas detectados

1. **`__main__.py` mezcla responsabilidades**: Hace de CLI, orquestador, manejador de errores, y reportero de progreso. El patrón `upsert_source → start_run → make_provenance → try/except/commit/finish_run` se repite ~9 veces.

2. **Tipos TypeScript manuales**: `db.ts` se mantiene a mano contra el schema de Alembic. No hay generación automática. Si alguien olvida actualizar tipos tras una migración, los tipos se desincronizan silenciosamente.

3. **`dangerouslySetInnerHTML`**: Aunque el sanitizador es conservador (whitelist: `<i>`, `<em>`, `<b>`, `<strong>`, `<sub>`, `<sup>`), es una superficie XSS si la BD se viera comprometida.

---

## 3. Diseño de API

**No hay API REST.** La web app lee Postgres y Meilisearch directamente:

- Búsqueda → Meilisearch SDK (con fallback a `pg_trgm`)
- Detalle de enfermedad → SQL directo a Postgres vía `postgres` client

### Trade-offs

| Beneficio | Riesgo |
|---|---|
| Sin latencia HTTP | Acoplamiento fuerte web-BD |
| Sin servidor API que desplegar | Sin consumidores externos (mobile, widgets, partners) |
| SQL completo para queries complejas | Credenciales de BD expuestas al servidor web |
| Sin overhead de serialización | Sin contrato API documentado |

### ☑ Correcto

- El cliente `postgres` (porsager) con tagged template literals parametriza queries por defecto — SQL injection virtualmente imposible
- La decisión está documentada en ADR 0003: "Con 5 queries, un ORM no justifica su costo"

---

## 4. Flujo de Datos

```
Fuente externa (HTTP/XML/JSON)
    │
    ▼
[fetch] → RawArtifact (disco + sha256)
    │
    ▼
[parse] → Staging models (Pydantic BaseModel)
    │
    ▼
[validate] → Umbral 2% (si falla >2%, aborta)
    │
    ▼
[load] → PostgreSQL upsert (ON CONFLICT DO UPDATE/NOTHING)
    │
    ▼
[retire_missing] → Soft-delete (status='retired')
    │
    ▼
[mr index rebuild] → Meilisearch (por idioma)
    │
    ▼
[Web search] → Meilisearch SDK → Fallback → pg_trgm en Postgres
[Web detail] → SQL directo a Postgres
```

### ☑ Correcto

- Provenance tracking completo: cada fila tiene `provenance_id` → `ingest_run` → `source`
- La fecha de recuperación se muestra visible en cada ficha de enfermedad
- Soft deletes (nunca DELETE físico) preservan enlaces entrantes
- Validación con umbral: "mejor obsoleto y correcto que fresco y erróneo"

### Problemas detectados

1. **Sin caché**: Cada page request va a Postgres + Meilisearch. Para datos que cambian semestralmente, no hay `stale-while-revalidate`, ISR, ni caching en React.

2. **ETL secuencial y mono-hilo**: Las fuentes se procesan una por una. `trials` y `gard` iteran ~3200 enfermedades con `time.sleep()` entre llamadas API — ~1 hora mínimo para trials.

---

## 5. Arquitectura Web (Next.js)

### Stack

- **Framework**: Next.js 15 App Router, SSR
- **i18n**: next-intl con locale en URL (`[locale]/`)
- **Data fetching**: Server Components con queries SQL directas
- **Búsqueda**: Meilisearch SDK (TypeScript) + fallback pg_trgm
- **Sin JavaScript requerido**: Todo el contenido se renderiza en SSR

### Fetching de datos (página de detalle)

Ejemplo de fetching paralelo en `d/[slug]/page.tsx`:

```typescript
const [keyFacts, geography, phenotypes, genes, classifications,
       trials, drugs, organizations, otherLangs, jpDesignation] =
  await Promise.all([...]);
```

10 queries en paralelo. Cada sección se renderiza condicionalmente (si no hay datos, no se muestra).

### ☑ Correcto

- SSR puro (indexable, funciona sin JS)
- Fetching paralelo
- Secciones condicionales (no muestra tabs vacías)
- Locale en URL (sin cookies → sin GDPR consent banner)

### Problemas detectados

1. **Página de detalle 921 líneas**: `d/[slug]/page.tsx` es demasiado grande. Debería dividirse en un hook `useDiseaseData(slug)` y componentes por sección.

2. **Sin API layer**: No hay ruta de API en Next.js. La app no puede servir consumidores externos.

3. **Sin ISR/SSG**: Todas las páginas son dinámicas (no hay `generateStaticParams` + `revalidate`), a pesar de que los datos cambian semestralmente.

---

## 6. Arquitectura de Búsqueda

### Por qué Meilisearch (no Postgres full-text)

| Razón | Detalle |
|---|---|
| Tolerancia a erratas | Meilisearch tiene typo tolerance nativa configurable (minWordSizeForTypos: 5/9) |
| Ranking por idioma | Índices separados por idioma evita cross-language poisoning |
| Configuración cero | Meilisearch funciona out-of-the-box |
| Reconstruible | Dato que no está en Postgres no se puede indexar |

### Ranking Rules (diseño ingenioso)

```
words → typo → proximity → exactness → attribute → sort → label_length:asc
```

`exactness` ANTES que `attribute` (al revés del default de Meilisearch): un sinónimo que coincide exactamente debe ganarle a un label preferido que contiene el query como substring.

### Fallback (excelente)

Cuando Meilisearch no está disponible:
1. `searchFallback()` usa `pg_trgm` + `mr_unaccent` en Postgres
2. Degradación funcional (sin typo tolerance, sin synonyms)
3. Banner "degradado" visible al usuario
4. "Un fallback que nunca se ejecuta es un fallback que no funciona"

---

## 7. Base de Datos

### Schema: bien normalizado

| Tabla | Propósito |
|---|---|
| `disease` | Entidad canónica (UUID, ORPHA code, soft-delete) |
| `disease_label` | Labels multi-idioma (preferred, synonym, abbreviation) |
| `disease_xref` | Cross-references (OMIM, ICD10, MONDO, UMLS, etc.) |
| `disease_content` | Text blocks multi-idioma (definiciones) |
| `source` / `ingest_run` / `provenance` | Cadena de procedencia completa |
| `epidemiology`, `disease_phenotype`, `disease_gene` | Tablas de hechos |
| `disease_trial`, `disease_drug`, `disease_organization` | Tablas de hechos |
| `classification` + `classification_edge` | Jerarquía de clasificaciones |

### Migraciones (Alembic): bien estructuradas

- `f9df89f2c6c2` — Schema inicial
- `17be4b438c90` — Dashboard tables
- `194f5c3a69c6` — Clinical trials + orphan drugs
- `c3d5f0a1b2e4` — Patient organizations (GARD)

### ☑ Correcto

- `pg_trgm` + GIN index para fallback de búsqueda
- `mr_unaccent` IMMUTABLE function wrapper
- Provenance tracking completo
- OMIM protection: `assert_no_omim_text()` en el loader

### Problemas detectados

1. **Pool de conexiones hardcodeado**: `max: 5` en `db.ts` — debería ser configurable via env var.

2. **Índices faltantes**: Verificar si hay índices en `provenance_id`, `source_id`, y columnas de `WHERE` frecuentes.

---

## 8. Seguridad

| Aspecto | Estado |
|---|---|
| SQL injection | ✅ Prevenido (tagged template literals en web, SQLAlchemy ORM en ETL) |
| XSS | ✅ Sanitización whitelist (solo `<i>`, `<em>`, `<b>`, `<strong>`, `<sub>`, `<sup>`) |
| Licencias | ✅ `assert_no_omim_text()` como aserción de código, no solo documentación |
| OMIM | ✅ Solo números MIM, nunca texto |
| User data | ✅ No se aceptan datos de paciente por diseño (ADR 0002) |
| DB credentials | ⚠️ Web app puede escribir (usa mismo rol que ETL) |
| `dangerouslySetInnerHTML` | ⚠️ Superficie XSS si BD comprometida |

---

## 9. Bugs Identificados

| # | Archivo | Línea | Bug | Severidad |
|---|---|---|---|---|
| 1 | `__main__.py` | ~9 sitios | `except Exception as exc` con `# noqa: BLE001` atrapa `KeyboardInterrupt` | 🟡 Medio |
| 2 | `science.py` | 55 | TypeVar `object` usado como tipo genérico pierde type safety | 🟢 Bajo |
| 3 | `nomenclature.py` | 140 | `FileNotFoundError` sin mensaje descriptivo (no dice qué archivos esperaba) | 🟢 Bajo |
| 4 | `config.py` | 20 | Default URL con contraseña `morbirari_dev` hardcodeada | 🟡 Medio |
| 5 | `db.ts` | 11 | Default URL con contraseña `morbirari_dev` hardcodeada | 🟡 Medio |

---

## 10. Mejoras Sugeridas

### 🔴 Críticas

1. **Crear rol BD read-only para web app**. Un usuario `morbirari_web` con permisos solo SELECT. Elimina el riesgo de que el servidor web modifique datos accidentalmente.

2. **Extraer patrón repetido de `__main__.py`**. Crear un decorador `@ingest_pipeline()` o context manager que envuelva el ciclo `upsert_source → start_run → make_provenance → try/except/commit/finish_run`. Reduce ~200 líneas y elimina 9 fuentes de error.

3. **Agregar `React.cache()` a data fetchers**. Una línea por función en `db.ts` y `dashboard.ts` para deduplicar requests dentro del mismo render.

### 🟡 Importantes

4. **Dividir `d/[slug]/page.tsx` (921 líneas)**. Extraer hook `useDiseaseData(slug)` + componente por sección (KeyFacts, Geography, ClinicalSigns, Genes, Trials, etc.).

5. **Dividir `science.py` (860 líneas)**. Mover a subpaquete `loaders/dashboard/` con un archivo por dominio.

6. **Agregar una API layer delgada**. Incluso un Route Handler simple de Next.js (`/api/diseases/[slug]`) desacoplaría la BD del frontend y permitiría consumidores externos.

7. **Eliminar triplicación de `_text()` helper**. Mover a `base.py` o un módulo `_xml_helpers.py`.

8. **Configurar pool size via env var**. `MORBIRARI_DB_POOL_MAX` en vez del hardcoded `max: 5`.

### 🟢 Recomendadas

9. **Reemplazar `dangerouslySetInnerHTML`** por contenido estructurado. Parsear el HTML limitado de Orphanet a formato JSON en tiempo de ETL (`{type: "italic", children: ["texto"]}`) y renderizar con componentes React.

10. **Agregar ISR** para páginas de detalle de enfermedades populares. `export const dynamic = 'force-static'` + `generateStaticParams` + `revalidate`.

11. **Agregar snippets inteligentes a la búsqueda**. Usar `attributesToCrop` y `attributesToHighlight` de Meilisearch en vez de devolver el HTML crudo de definición.

12. **Paralelizar el ETL**. Usar `asyncio` o `concurrent.futures` para procesar fuentes en paralelo. Para trials, usar batch API calls en vez de queries secuenciales por enfermedad.

13. **Agregar monitoreo al ETL**. Insertar `duration_seconds` en `IngestRun` y exponer timing en `mr status`.

14. **Generar tipos TypeScript automáticamente**. Reintroducir `drizzle-kit pull` o un script custom que lea el schema de Postgres y genere tipos syncronizados.

---

## Resumen

| Categoría | Nota | Comentario |
|---|---|---|
| Patrón arquitectónico | B+ | ETL off-line + Web SSR, principios sólidos y consistentes |
| Límites entre módulos | A | Separación ETL/Web excelente, dependencias limpias |
| Diseño de API | D | No hay API. Acceso directo a BD desde web. No extensible |
| Flujo de datos | A | Idempotencia, validación, soft deletes, procedencia completa |
| Búsqueda | A | Meilisearch bien motivado, ranking ingenioso, fallback robusto |
| Base de datos | B+ | Schema bien normalizado, migraciones, falta role read-only |
| Seguridad | B+ | Licencias enforceadas en código, sanitización whitelist |
| Documentación técnica | A | ADRs, CLAUDE.md, DATA_LICENSES.md — excepcional |
| **Global** | **B+** | Proyecto maduro con fundamentos sólidos. Lo más cercano a producción-ready de los 4 |
