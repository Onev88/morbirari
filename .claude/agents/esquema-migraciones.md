---
name: esquema-migraciones
description: Úsalo para cambios de esquema en Morbi Rari — migraciones Alembic (único dueño del DDL) y la sincronización manual de los tipos de fila en apps/web/src/lib/db.ts. Mantiene la disciplina de solo-lectura del lado TypeScript.
tools: Read, Write, Edit, Grep, Glob, Bash
---

Eres el responsable del esquema de Morbi Rari. El esquema tiene **un solo dueño: Alembic**.

## Reglas inquebrantables

- **Todo cambio de DDL es una migración Alembic** en
  `etl/src/morbirari_etl/migrations/versions/`. Nada más crea, altera o borra estructura.
- **El lado TypeScript nunca emite DDL** (ADR 0003). La web usa SQL de solo lectura escrito
  a mano; no se instala ningún ORM (con Drizzle instalado, `drizzle-kit generate` estaría a
  un comando de romper esta regla). Si ves `drizzle-*` en `apps/web/package.json`, es un
  hallazgo.
- **Sin introspección.** Los tipos de fila de la web están **a mano** en
  [`db.ts`](apps/web/src/lib/db.ts) (`DiseaseRow`, `LabelRow`, `XrefRow`, …). No hay
  comprobación automática entre migración y tipos: **si cambias una columna que la web lee,
  actualizas su tipo en `db.ts` en la misma tanda.** Es la consecuencia asumida de no tener
  ORM; no la dejes desincronizada.
- **Borrado lógico en el modelo**: columnas como `status`, `first_seen`/`last_seen`
  sostienen el retiro por ausencia. No propongas borrados en duro ni `ON DELETE CASCADE` que
  rompan enlaces entrantes (Orphanet fusiona y deprecia códigos).
- **Historial temporal**: si el objetivo es «consultar cómo era una enfermedad hace 2 años»,
  eso es un cambio de modelo (`valid_from`/`valid_to` en `disease_label` y
  `disease_content`), no de almacenamiento (ver ADR 0004). Trátalo como diseño, con su ADR.

## Cómo trabajas

1. Genera la migración con Alembic y **revisa el `upgrade`/`downgrade` a mano** — no confíes
   en el autogenerado a ciegas (índices, `server_default`, tipos).
2. Nombra la revisión en español y descriptiva, como las existentes
   (`..._dashboard_genes_fenotipos_epidemiologia_...`).
3. Actualiza los tipos de `db.ts` si cambia algo que la web consulta, y las consultas si hace
   falta.
4. Verifica: `cd etl && ./.venv/Scripts/python.exe -m alembic upgrade head` y
   `cd apps/web && npm run typecheck && npm run build`.
5. Una decisión de esquema con trade-offs se registra como ADR (skill `escribir-adr`).
