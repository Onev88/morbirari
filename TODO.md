# TODO

Trabajo pendiente que no encaja (todavía) en un ADR ni en el código. Las decisiones de
fondo van en [docs/adr/](docs/adr/); esto es la lista de lo que falta por hacer.

## Frescura de datos volátiles

### Caducidad a 30 días en la ingesta de ensayos clínicos

**Estado:** decidido, sin implementar.

Los ensayos clínicos (ClinicalTrials.gov) son **datos volátiles**: un ensayo abre,
cambia de estado de reclutamiento y cierra. La [ADR 0001](docs/adr/0001-own-index-not-federation.md)
ya avisa de que necesitan una cadencia de refresco propia.

Hoy `mr ingest trials` ([`__main__.py:338`](etl/src/morbirari_etl/__main__.py)) solo tiene
`--resume`, que hace `skip_existing`: **salta las enfermedades que ya tienen ensayos
cargados**, sin mirar la fecha. Consecuencia: un ensayo cargado una vez **no se
refresca nunca**. Los datos de «dónde acudir» y «si están reclutando» se quedan
congelados en el momento de la primera carga.

**Lo que se decidió:**

- Añadir `--refresh-after=30` (días): en un `--resume`, volver a consultar todo lo que
  se trajo hace más de 30 días, en vez de saltarlo por existir.
- Si una consulta **falla, no anotar nada** (no marcar como «fresco» algo que no se
  pudo traer): así el siguiente `--resume` lo reintenta.
- Un `--resume` periódico refresca lo viejo por sí solo, sin intervención manual.

**Lo que hace falta para implementarlo:**

- Guardar **cuándo** se trajo cada enfermedad/ensayo (un `fetched_at`), que hoy no
  existe. Comparar contra el umbral en `mesh_ids_by_disease(..., skip_existing=...)`
  ([`loaders/science.py`](etl/src/morbirari_etl/loaders/science.py)).
- Distinguir «cargado y fresco» de «cargado y caducado» de «nunca cargado».
- Programar el `--resume` periódico (ampliar [etl-scheduled.yml](.github/workflows/etl-scheduled.yml),
  que hoy solo reingiere Orphanet una vez al mes).

**Origen:** decisión de la sesión «Morbi Rari rare disease system» (2026-07-16).
