---
name: reindexar-y-verificar
description: Reconstruir el índice Meilisearch desde Postgres y verificar la calidad de búsqueda de Morbi Rari (erratas, identificador, gen) y el fallback de trigramas. Úsala tras cambios en datos, indexador o configuración de búsqueda.
---

# Reindexar y verificar la búsqueda

Meilisearch es una **proyección reconstruible de Postgres**; reconstruirlo es seguro siempre
y nunca implica escritura dual. Esta skill cubre reproyectar y comprobar que la búsqueda
sigue cumpliendo.

## Reindexar

```bash
cd etl
./.venv/Scripts/python.exe -m morbirari_etl index rebuild --lang en,es
./.venv/Scripts/python.exe -m morbirari_etl status
```

- **Un índice por idioma.** Nunca mezcles idiomas en un índice (envenena el ranking). Si
  añadiste un idioma, reindéxalo aparte.
- `index rebuild` es idempotente y no toca Postgres; puedes ejecutarlo cuantas veces quieras.

## Verificar calidad (los casos que definen «bien»)

Ejecuta las pruebas y, si arreglaste una regresión, **añade un caso**:

```bash
./.venv/Scripts/python.exe -m pytest tests/test_search_quality.py
```

Comprueba a mano que siguen valiendo:

- **Errata / sin acentos**: «fibrosis quistika» → *Fibrosis quística*.
- **Identificador**: «OMIM:219700» y «219700» → *Cystic fibrosis*.
- **Gen**: «CFTR» → la enfermedad que ese gen **causa** (no una candidata).

## Verificar el camino degradado

El fallback de trigramas en Postgres ([`searchFallback`](apps/web/src/lib/db.ts)) es parte
del producto, no un extra: si Meilisearch cae, la búsqueda debe **degradar**, no romperse.
De vez en cuando, prueba con Meilisearch parado que la web sigue encontrando enfermedades.

## Regla que no se toca al «mejorar el ranking»

Puedes ajustar sinónimos y ranking textual, pero **la búsqueda por fenotipo no puntúa**
(ADR 0002): sin porcentaje de coincidencia ni verosimilitud diagnóstica, orden determinista.
«Un pequeño score para ordenar mejor» sobre fenotipos convierte el producto en dispositivo
médico regulado: se rechaza.
