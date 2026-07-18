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
