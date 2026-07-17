---
name: nueva-migracion
description: Crear una migración de esquema en Morbi Rari con Alembic (único dueño del DDL) y mantener sincronizados a mano los tipos de fila de apps/web/src/lib/db.ts. Úsala siempre que cambie el esquema de la base.
---

# Nueva migración de esquema

En Morbi Rari **el DDL tiene un solo dueño: Alembic**. La web nunca emite DDL y sus tipos de
fila están escritos **a mano** (ADR 0003): no hay comprobación automática entre migración y
tipos, así que la sincronización es responsabilidad tuya, en la misma tanda.

## Pasos

1. **Genera la revisión** en `etl/`:
   ```bash
   ./.venv/Scripts/python.exe -m alembic revision --autogenerate -m "descripcion_en_espanol"
   ```
   Nombra la revisión en español y descriptiva, como las existentes
   (`..._dashboard_genes_fenotipos_epidemiologia_...`).

2. **Revisa el archivo generado a mano.** El autogenerado se equivoca con: índices,
   `server_default`, tipos custom, `nullable`, y no ve datos. Ajusta `upgrade()` **y**
   escribe un `downgrade()` real.

3. **Respeta el borrado lógico.** Nada de `ON DELETE CASCADE` ni borrados en duro que rompan
   enlaces entrantes — Orphanet deprecia y fusiona códigos. Columnas de estado
   (`status`, `first_seen`/`last_seen`) sostienen el retiro por ausencia.

4. **Aplica y prueba:**
   ```bash
   ./.venv/Scripts/python.exe -m alembic upgrade head
   ./.venv/Scripts/python.exe -m alembic downgrade -1   # verifica que baja limpio
   ./.venv/Scripts/python.exe -m alembic upgrade head
   ```

5. **Sincroniza la web (si aplica).** Si cambiaste algo que la web **lee**, actualiza:
   - El tipo de fila correspondiente en [`db.ts`](apps/web/src/lib/db.ts) (`DiseaseRow`,
     `LabelRow`, `XrefRow`, …).
   - La consulta SQL que lo usa.
   - Comprueba: `cd apps/web && npm run typecheck && npm run build`.

6. **Verifica el ETL:** `cd etl && ./.venv/Scripts/python.exe -m pytest`.

## Cuándo NO es una migración

Si el objetivo es «poder consultar cómo era una enfermedad hace 2 años», eso es un
**rediseño temporal** (`valid_from`/`valid_to`), con su propio ADR (skill `escribir-adr`),
no una migración suelta. Ver ADR 0004.
