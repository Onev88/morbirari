# Licencias de las fuentes de datos

Morbi Rari agrega datos de terceros. **El código** de este repositorio es Apache-2.0
(ver `LICENSE`). **Los datos** no: cada fuente tiene sus propios términos, y algunos
son restrictivos.

Este documento es normativo, no informativo. Las reglas de aquí se reflejan en la tabla
`source` de la base de datos (columnas `license_spdx`, `attribution_text`,
`redistributable`) para que la aplicación pueda hacerlas cumplir automáticamente. Un
documento que nadie lee se desincroniza; la columna no.

## Resumen por fuente

| Fuente | Licencia | ¿Redistribuible? | Estado |
|---|---|---|---|
| Orphanet / Orphadata / ORDO | CC BY 4.0 | Sí | En uso (Fase 1) |
| MONDO | CC BY 4.0 | Sí, con matices | Fase 3 |
| HPO | Custom (no SPDX) | Sí, sin alterar | Fase 2+ |
| GARD (NCATS/NIH) | Dominio público EE.UU. | Sí | Fase 3 |
| ClinicalTrials.gov | Dominio público EE.UU. | Sí | Fase 4 |
| PubMed | Mixto | Solo metadatos | Fase 4 |
| **OMIM** | **Propietario (JHU)** | **NO** | **Solo identificadores** |

---

## Orphanet / Orphadata / ORDO

- **Licencia:** CC BY 4.0.
- **Permite:** uso comercial, redistribución e integración en recursos de terceros.
- **Obliga a:** citar la fuente e **indicar los cambios realizados**.
- **Atribución obligatoria, literal:**

  > Orphanet: an online rare disease and orphan drug data base. © INSERM 1999.
  > Available on http://www.orpha.net

- **Cuidado:** algunos productos del catálogo de Orphadata están marcados como
  "conditions may apply". Antes de ingerir un producto nuevo más allá del Nomenclature
  Pack, revisar sus términos concretos.

## MONDO

- **Licencia:** CC BY 4.0.
- **Matiz importante:** MONDO armoniza fuentes de aguas arriba y **arrastra etiquetas
  derivadas de OMIM**. Usar las referencias cruzadas propias de Orphanet como primarias
  y MONDO solo para rellenar huecos, suprimiendo en pantalla las etiquetas de origen OMIM.

## HPO (Human Phenotype Ontology)

- **Licencia:** propia, sin identificador SPDX (OBO Foundry la lista literalmente como `hpo`).
- **Obliga a:** citar al HPO Consortium y **no alterar el contenido ni las relaciones
  lógicas**. Se almacena verbatim; nunca se sintetizan aristas padre/hijo propias.
- **⚠️ Trampa de OMIM:** el fichero `phenotype.hpoa` tiene una columna `disease_name` y,
  en las filas `OMIM:xxxxxx`, ese valor **es el título preferido de OMIM**, protegido por
  copyright. Al parsear se descarta ese campo para las filas `OMIM:`. Esto está
  implementado como aserción dura en el loader, no como convención.

## GARD / ClinicalTrials.gov (NIH)

- Obra del gobierno de EE.UU., de libre uso.
- **Obliga a:** atribuir, y **no implicar respaldo de NIH/NCATS**.

## PubMed

- Los **metadatos** (PMID, título, autores, revista) se pueden usar.
- Los **abstracts son copyright del editor**. Se guarda solo PMID + título + enlace.
  Nunca el texto del abstract.

## OMIM — restricciones estrictas

Los términos de Johns Hopkins establecen que OMIM no puede copiarse, distribuirse,
transmitirse, duplicarse, reducirse ni alterarse con fines comerciales o de
redistribución sin licencia de JHU, y que los usuarios se comprometen a **no desarrollar
una base de datos derivada** ni a distribuir los datos a terceros. El uso permitido es
personal, educativo, académico o de investigación.

Reglas para este proyecto:

1. **Nunca ingerir descargas de omim.org** (`genemap2.txt`, `mim2gene.txt`,
   `mimTitles.txt`). No en un repositorio público. Ni una vez.
2. **Los números MIM como identificadores desnudos sí** — son hechos, no expresión
   protegible. `disease_xref(source_ns='OMIM', source_id='219700')` más un enlace a
   `omim.org/entry/219700` es exactamente lo que Orphanet y MONDO publican bajo CC BY.
3. **Nunca almacenar ni mostrar títulos ni texto de OMIM.**
4. Las Fases 1–2 esquivan el asunto por completo usando el producto de fenotipos propio
   de Orphanet (CC BY) en lugar de `phenotype.hpoa`.

## Higiene del repositorio

- `data/raw/` y `data/staging/` están en `.gitignore`. Los datasets fuente **no se
  versionan**: se descargan en ejecución.
- Solo se versionan fixtures pequeños para tests, y **solo de fuentes CC BY**
  (Orphanet sí; OMIM jamás).
