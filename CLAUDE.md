# Morbi Rari — reglas de diseño

Punto de entrada único a la información sobre enfermedades raras, dispersa entre Orphanet,
HPO, MONDO, OMIM, GARD, ClinicalTrials.gov, la EMA y NANDO. **Es una obra de referencia:
no diagnostica ni da consejo médico.**

Estas reglas **prevalecen sobre el comportamiento por defecto**. Las decisiones de fondo
viven en [docs/adr/](docs/adr/); esto es su destilado operativo. Si una regla y el código
se contradicen, es un bug: páralo y avisa, no lo repliques.

## Stack

- **ETL**: Python ≥3.12, SQLAlchemy + Alembic. Comando `mr` (`python -m morbirari_etl`).
- **Datos**: Postgres 16 (fuente de verdad) + Meilisearch 1.11 (índice).
- **Web**: Next.js (App Router, SSR) sobre Node 24, cliente `postgres` (porsager), sin ORM.
- **Idiomas activos**: EN + ES (Orphanet publica 9).

## Datos: las invariantes duras

1. **Postgres es la fuente de verdad. Meilisearch es una proyección reconstruible.**
   Nunca hay escritura dual: se escribe en Postgres y se *reproyecta* a Meilisearch con
   `mr index rebuild`. Si Meilisearch cae, la búsqueda **degrada** a trigramas de Postgres
   ([`searchFallback`](apps/web/src/lib/db.ts)) en vez de romperse. Ese fallback está
   probado a propósito: uno que nunca se ejecuta no funciona.
2. **Índice propio, no federación en vivo** (ADR 0001). Las fuentes aportan *campos a una
   entidad canónica*, no documentos que compiten. No se consulta a Orphanet/otros en tiempo
   de búsqueda.
3. **Borrado lógico, nunca físico.** Lo ausente en una ejecución correcta se marca
   `status='retired'` ([`retire_missing`](etl/src/morbirari_etl/loaders/postgres.py)).
   Orphanet deprecia y fusiona códigos; un borrado en duro rompería enlaces entrantes y
   marcadores de usuario.
4. **Idempotencia por checksum.** Cada artefacto crudo se aterriza en disco y se identifica
   por su `sha256` antes de parsear nada. Si el checksum coincide con la última ejecución,
   no hay trabajo. `--force` reingiere de todos modos.
5. **Procedencia y frescura por fila.** Cada fila lleva su `provenance` (fuente, versión,
   URL, `retrieved_at`); `ingest_run` registra checksum, versión declarada por la fuente y
   recuentos. **La fecha de recuperación se muestra visible en cada ficha** — no es
   decoración: es señal de confianza y mitigación de responsabilidad (ADR 0001).
6. **Validación con umbral.** Si más del 2 % de los registros falla la validación, se
   **aborta** la ingesta y los datos vivos siguen sirviendo
   (`VALIDATION_FAILURE_THRESHOLD`). Mejor obsoleto y correcto que fresco y erróneo.
7. **Contrato de fuente**: `fetch → parse → validate → load`
   ([`sources/base.py`](etl/src/morbirari_etl/sources/base.py)). Los bytes crudos primero a
   disco con su sha256; solo entonces se parsea.

## Esquema y acceso

8. **Alembic es el dueño único del DDL.** El lado TypeScript **nunca emite DDL**, ni por
   accidente: la web usa SQL de solo lectura escrito a mano (ADR 0003). No se instala ningún
   ORM en la web (`drizzle-kit generate` estaría a un comando de crear DDL).
9. **Tipos de fila a mano en [`db.ts`](apps/web/src/lib/db.ts).** No hay introspección ni
   comprobación automática entre migración y tipos: si cambia el esquema de Alembic, hay que
   actualizarlos a mano en la misma tanda. La skill `nueva-migracion` lo cubre.

## Búsqueda

10. **Un índice por idioma.** La tolerancia a erratas y los sinónimos son ajustes por
    índice, y mezclar idiomas envenena el ranking. Nunca meter dos idiomas en un índice.
11. **Multiidioma se ingiere, no se construye.** Añadir un idioma = añadir el locale en
    `i18n/routing.ts`, crear `messages/{lang}.json` e `mr ingest orphanet --lang {lang} &&
    mr index rebuild --lang {lang}`. No se toca el modelo de datos.

## Licencias de datos — leer antes de tocar fuentes

12. **[DATA_LICENSES.md](DATA_LICENSES.md) es de lectura obligatoria antes de añadir o
    modificar cualquier fuente.** Cada fila declara su licencia (`source.license_spdx`,
    `attribution_text`).
13. **OMIM: prohibido derivar.** Sus términos prohíben crear bases de datos derivadas. Se
    guardan **números MIM (hechos) y se enlaza; nunca su texto**. Hay una aserción en el
    loader que lo impide — no la quites.
14. Los datos crudos (`data/raw/`, `data/staging/`) **no se versionan** (ADR 0004): se
    descargan en tiempo de ejecución. Solo se versionan fixtures pequeños de fuentes CC BY
    para tests.

## Contenido médico y régimen regulatorio — línea que no se cruza

15. **No es consejo médico y no diagnostica** ([DISCLAIMER.md](DISCLAIMER.md)). El aviso
    debe estar **traducido a cada idioma soportado y visible** en la interfaz.
16. **La búsqueda por fenotipo es un filtro de catálogo, no una ayuda al diagnóstico**
    (ADR 0002, *ámbito permanente*). Está permitida **solo** así:
    - **Recuperar, no inferir**: consulta booleana sobre anotaciones preexistentes.
    - **Sin puntuación**: ni porcentaje de coincidencia, ni ranking de verosimilitud
      diagnóstica. Orden determinista y neutral.
    - **No se aceptan datos de paciente** (ni edad, ni sexo, ni historia).
    - **Encuadre**: «explorar el catálogo por características clínicas», nunca «averigua qué
      enfermedad tienes».
    - **El scoring es lo que convierte el producto en un dispositivo médico regulado.** El
      disclaimer no protege; lo hace la funcionalidad. Si alguien propone «un pequeño
      ranking de relevancia», esa propuesta es precisamente la que cruza la línea: se
      rechaza.
17. **Matices que no se aplanan**: designación huérfana ≠ aprobación (EMA); centro que
    *investiga* ≠ centro que *trata*; gen causante ≠ gen modificador. La interfaz ya los
    distingue; el contenido nuevo también debe hacerlo.
18. **Sanitización siempre.** El HTML de las fuentes se sanea con lista blanca aunque la
    fuente sea de confianza ([`sanitize.ts`](apps/web/src/lib/sanitize.ts)). Que el origen
    sea fiable no es razón para no escapar.
19. **Avances = actividad, no noticias; imágenes esquemáticas, no clínicas** (ADR 0005). Lo
    «reciente» de una ficha es *actividad investigadora* —publicaciones (solo metadatos,
    nunca el texto), ensayos, designaciones—, en orden **cronológico y sin ranking de
    relevancia** (mismo principio que la regla 16). Nada de prensa scrapeada. **Prohibida la
    fotografía clínica de pacientes**: solo imagen esquemática o derivada de datos (herencia,
    mapas, prevalencia). El porqué, en
    [ADR 0005](docs/adr/0005-actividad-reciente-avances-sin-fotografia-clinica.md).

## Web

20. **Indexable y sin JavaScript.** El contenido va en el HTML (SSR); las pestañas cargan
    todo el contenido para que siga siendo indexable y funcione sin JS.
21. **Bilingüe de serie** (ES/EN) y con **tema claro/oscuro**. Todo texto de interfaz vive
    en `messages/{lang}.json`, nunca incrustado.

## Idioma, estilo y flujo

22. **Todo en español**: código-prosa (comentarios, docstrings), mensajes de commit, ADRs y
    documentación. Los identificadores de esquema pueden ser términos técnicos en inglés,
    pero la prosa que los rodea es española.
23. **Git**: `main` es la principal. El trabajo nuevo va en `develop` y luego se lleva a
    `main` por *fast-forward*. Commits en español, descriptivos. No commitear a `main`
    directo. No commitear ni hacer push salvo que se pida.
24. **Las decisiones de fondo se registran como ADR** en `docs/adr/`, numerados y en el
    estilo de la casa (skill `escribir-adr`). Un TODO puntual va en [TODO.md](TODO.md).
25. **Verificar antes de dar por hecho.** Tests: `cd etl && pytest`; `cd apps/web && npm run
    typecheck && npm run build`. Si algo falla, se dice con la salida; no se maquilla.

## Comandos

| Comando | Qué hace |
|---|---|
| `mr ingest orphanet --lang en,es` | Nomenclatura: nombres, sinónimos, definiciones, xrefs. |
| `mr ingest science --lang en,es` | Genes, signos clínicos (HPO), epidemiología, herencia, edad de inicio. |
| `mr ingest classifications --lang en,es` | Jerarquía por especialidad. |
| `mr ingest trials` | Ensayos abiertos, centros y promotores. Reanudable (`--resume`). |
| `mr ingest drugs` | Designaciones huérfanas de la EMA. |
| `mr ingest nando` | Nombres en japonés y designación nipona. |
| `mr index rebuild --lang es` | Reconstruye el índice desde Postgres. Seguro siempre. |
| `mr status` | Qué hay cargado, de qué versión y desde cuándo. |

## Agentes y skills de este proyecto

Están en `.claude/agents/` y `.claude/skills/`. Úsalos cuando encajen:

- **Agentes**: `traductor-de-idiomas`, `revisor-de-fuentes-licencias`, `adaptador-etl`,
  `esquema-migraciones`, `calidad-de-busqueda`.
- **Skills**: `anadir-fuente`, `nueva-migracion`, `escribir-adr`, `reindexar-y-verificar`,
  `desarrollador`, `especialista-medicina-investigativa`, `publicista`, `redes-sociales`,
  `diseno-web`, `diseno-multimedia`.
