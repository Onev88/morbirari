# ADR 0004 — Los datos no se versionan en el repositorio

- **Fecha:** 2026-07-15
- **Estado:** Aceptada

## Contexto

Surgió la pregunta de si convenía guardar los ficheros de las fuentes en el repositorio
para versionarlos y tener copia.

**Legalmente se podría**, al menos con Orphanet: es CC BY 4.0 y permite redistribuir
citando la fuente e indicando cambios. Así que la decisión es técnica, no jurídica.
(Con OMIM no se podría en ningún caso; ver `DATA_LICENSES.md`.)

## Decisión

`data/raw/` y `data/staging/` siguen en `.gitignore`. Los datasets se descargan en
tiempo de ejecución. Solo se versionan fixtures pequeños para tests, y solo de fuentes
CC BY.

## Razones

1. **La inicialización es barata: ~2 min 12 s** desde cero para EN+ES, descarga
   incluida (~17 MB), parseo de dos XML de 21 MB y carga de 11.645 enfermedades. Nada
   que justifique convertir el repositorio en un almacén de binarios.
2. **Orphanet ya archiva sus versiones anteriores.** Verificado: hay packs
   descargables de 2019 a 2025 en
   `https://www.orphacode.org/data/previous_versions/Orphanet_Nomenclature_Pack_{LANG}_{YEAR}.zip`.
   No hace falta ser el archivo de Orphanet, porque Orphanet ya lo es.
3. **El coste en Git sería permanente.** ~8,5 MB por idioma y versión, es decir unos
   77 MB al año con los 9 idiomas. Al ser ZIP (ya comprimidos), Git no puede hacer
   deltas: cada versión se guarda entera, la historia es inmutable, y todo el que clone
   se lo lleva.
4. **No resolvería lo que parece resolver.** Un ZIP en Git no permite responder «qué
   decía esta enfermedad hace dos años» sin descomprimir dos versiones y comparar XML a
   mano. Eso es un problema de modelo de datos (validez temporal por fila), no de
   almacenamiento.

## Ya existe trazabilidad

Sin versionar un solo byte de datos, el sistema ya registra:

- `ingest_run`: checksum del artefacto, versión declarada por la fuente, fecha y
  recuentos de cada ingesta.
- `provenance`: qué fuente, versión y URL respaldan cada fila.
- `disease.first_seen` / `last_seen`, y borrado lógico (`status='retired'`) en vez de
  borrado real.

## Si esto cambia

- **Archivar los ficheros originales** (por si Orphanet los retirase): usar GitHub
  Releases, no commits. Los adjuntos de release no entran en la historia de Git, no
  inflan el clone y se pueden borrar.
- **Historial consultable desde la web**: es un cambio de modelo (`valid_from` /
  `valid_to` en `disease_label` y `disease_content`), no de almacenamiento.
- **Copia de seguridad de la base**: `pg_dump` a un almacén externo. Git no es una
  herramienta de backup.
