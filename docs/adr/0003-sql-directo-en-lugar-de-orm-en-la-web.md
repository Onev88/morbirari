# ADR 0003 — SQL directo en la web, sin ORM

- **Fecha:** 2026-07-15
- **Estado:** Aceptada
- **Modifica:** el plan inicial contemplaba Drizzle con introspección (`drizzle-kit pull`).

## Contexto

El requisito de fondo es que **el lado TypeScript nunca emita DDL**: Alembic, en el ETL,
es el dueño único del esquema. Dos ORMs escribiendo DDL sobre una misma base es un
desastre conocido.

El plan proponía Drizzle en modo solo lectura, con el esquema obtenido por
introspección. Al implementar la Fase 1 quedó claro que la web hace exactamente cinco
consultas, todas de lectura y ninguna dinámica.

## Decisión

Usar el cliente `postgres` (porsager) con SQL escrito a mano en `apps/web/src/lib/db.ts`.
Sin ORM.

## Razones

- **Cumple el requisito de forma más estricta, no más laxa.** Un cliente SQL de solo
  lectura no puede emitir DDL ni por accidente; con un ORM instalado, `drizzle-kit
  generate` está siempre a un comando de distancia.
- Elimina el paso de introspección, que es una fuente de desincronización silenciosa
  entre el esquema real y los tipos.
- Cinco consultas no justifican un ORM ni su cadena de generación de tipos.

## Consecuencias

- Los tipos de fila se declaran a mano en `db.ts`. Si el esquema de Alembic cambia, hay
  que actualizarlos: no hay comprobación automática entre migración y tipos de la web.
  Con cinco consultas es asumible; si la superficie de lectura crece mucho, reconsiderar
  la introspección.
- `drizzle-orm` y `drizzle-kit` se retiraron de `package.json`: una dependencia
  declarada y no usada es deuda que confunde al siguiente lector.
