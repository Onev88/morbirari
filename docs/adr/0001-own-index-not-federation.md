# ADR 0001 — Índice propio, no federación en vivo

- **Fecha:** 2026-07-15
- **Estado:** Aceptada

## Contexto

Morbi Rari centraliza la búsqueda de información sobre enfermedades raras dispersa entre
Orphanet, GARD, MONDO, HPO, ClinicalTrials.gov y PubMed. Había dos caminos: consultar
esas fuentes en vivo en cada búsqueda (federación), o ingerirlas a una base propia y
buscar ahí.

## Decisión

Ingerimos las fuentes a una base de datos propia mediante ETL y buscamos sobre un índice
propio. Postgres es la fuente de verdad; Meilisearch es una proyección reconstruible.

## Razones

- **Latencia y fiabilidad:** una búsqueda federada es tan lenta como su fuente más lenta,
  y falla cuando cualquiera de ellas cae o aplica límites de tasa.
- **Reconciliación de identificadores:** el valor real del producto es unificar ORPHA,
  OMIM, MONDO, ICD y GARD en una entidad canónica. Eso es imposible de hacer bien en
  tiempo de consulta.
- **El "ranking entre fuentes" desaparece como problema.** Las fuentes aportan *campos a
  una entidad canónica*, no documentos que compiten entre sí. No hay nada que reconciliar
  al buscar.
- **Multiidioma:** los sinónimos por idioma solo son indexables si los tenemos nosotros.
- **Cadencia favorable:** Orphanet publica dos veces al año. Federar en vivo una fuente
  semestral es pagar latencia en cada consulta por datos que casi nunca cambian.

## Consecuencias

- Asumimos la responsabilidad de la frescura de los datos: hay que mostrar la fecha de
  recuperación de forma visible en cada ficha.
- Hay que mantener un pipeline ETL y vigilar cambios de esquema aguas arriba.
- Los datos volátiles (ensayos clínicos, literatura) necesitarán una cadencia de refresco
  mucho más alta que las ontologías, o una consulta en vivo cacheada. Se aborda en Fase 4.
