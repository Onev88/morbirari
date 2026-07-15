# Morbi Rari

Búsqueda centralizada de información sobre enfermedades raras.

La información sobre enfermedades raras existe, pero está dispersa entre Orphanet,
NIH/GARD, ontologías (MONDO, HPO), registros de ensayos clínicos y literatura — cada
una con su vocabulario, sus identificadores y su idioma. Un paciente que busca el
nombre de su enfermedad mal escrito y en español no encuentra nada; un clínico que
busca por código OMIM va a otra fuente distinta. Morbi Rari es el punto de entrada
único.

> **Morbi Rari no proporciona consejo médico y no diagnostica.** Es una obra de
> referencia. Ver [DISCLAIMER.md](DISCLAIMER.md).

## Estado

**Fase 1 funcionando**: Orphanet (EN + ES) ingerido, indexado y consultable.

- 11.645 enfermedades · ~53.000 etiquetas en dos idiomas · 8.745 referencias cruzadas
  · ~6.900 definiciones por idioma
- Búsqueda tolerante a erratas y sin acentos: «fibrosis quistika» encuentra
  *Fibrosis quística*
- Búsqueda por identificador: «OMIM:219700» o «219700» encuentran *Cystic fibrosis*

## Arquitectura

```
Orphanet (CC BY 4.0)  ──ETL(Python)──>  Postgres  ──proyección──>  Meilisearch
                                           │                            │
                                           └────────  Next.js  ─────────┘
                                                    (SSR, ES/EN)
```

- **Postgres es la fuente de verdad.** Meilisearch es una proyección reconstruible en
  cualquier momento; nunca hay escritura dual. Si Meilisearch cae, la búsqueda degrada
  a trigramas de Postgres en vez de romperse.
- **Alembic es el dueño único del DDL.** El lado TypeScript es de solo lectura.
- **Un índice de búsqueda por idioma**: la tolerancia a erratas y los sinónimos son
  ajustes por índice, y mezclar idiomas envenena el ranking.

Decisiones de fondo en [docs/adr/](docs/adr/).

## Puesta en marcha

Requisitos: Docker, Python ≥3.12, Node 24 (la CI usa la misma).

```bash
# 1. Infraestructura
docker compose up -d

# 2. ETL
cd etl
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/python
./.venv/Scripts/python.exe -m alembic upgrade head

# 3. Ingerir e indexar (~2 min desde cero: descarga ~17 MB de Orphanet,
#    parsea 2 XML de 21 MB y carga 11.645 enfermedades)
./.venv/Scripts/python.exe -m morbirari_etl ingest orphanet --lang en,es
./.venv/Scripts/python.exe -m morbirari_etl index rebuild --lang en,es
./.venv/Scripts/python.exe -m morbirari_etl status

# 4. Web
cd ../apps/web
npm install
npm run dev
```

Abrir http://localhost:3000/es y buscar `fibrosis quistica`.

## Comandos

| Comando | Qué hace |
|---|---|
| `mr ingest orphanet --lang en,es` | Ingiere el Nomenclature Pack. Salta si el checksum no cambió. |
| `mr ingest orphanet --force` | Reingiere aunque no haya cambios. |
| `mr index rebuild --lang es` | Reconstruye el índice desde Postgres. Seguro siempre. |
| `mr status` | Qué hay cargado, de qué versión y desde cuándo. |

## Tests

```bash
cd etl && ./.venv/Scripts/python.exe -m pytest
cd apps/web && npm run typecheck && npm run build
```

## Añadir un idioma

Orphanet publica en 9 idiomas (`cs, nl, en, fr, de, it, pl, pt, es`). Para activar uno:

1. Añadirlo a `routing.locales` en `apps/web/src/i18n/routing.ts`
2. Crear `apps/web/messages/{lang}.json`
3. `mr ingest orphanet --lang {lang} && mr index rebuild --lang {lang}`

No hay que tocar el modelo de datos: el multiidioma no se construye, se ingiere.

## Licencias

El **código** es Apache-2.0 ([LICENSE](LICENSE)). Los **datos** no: cada fuente tiene
sus términos, y algunos son restrictivos. Ver **[DATA_LICENSES.md](DATA_LICENSES.md)**
antes de añadir cualquier fuente.

Lo esencial:

- Orphanet es CC BY 4.0: se puede redistribuir citando e indicando cambios.
- **OMIM no.** Sus términos prohíben crear bases de datos derivadas. Guardamos números
  MIM (hechos) y enlazamos; nunca su texto. Hay una aserción en el loader que lo impide.
- `data/raw/` está en `.gitignore`: los datasets se descargan, no se versionan.
  Reconstruir desde cero cuesta ~2 minutos, y Orphanet ya archiva sus versiones
  anteriores. El porqué, en [ADR 0004](docs/adr/0004-no-versionar-los-datos-en-el-repo.md).

Este proyecto usa datos de Orphanet:

> Orphanet: an online rare disease and orphan drug data base. © INSERM 1999.
> Available on http://www.orpha.net
