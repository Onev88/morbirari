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
| Orphanet Nomenclature Pack | CC BY 4.0 | Sí | **En uso** |
| Orphadata `product9_prev` (epidemiología) | CC BY 4.0 | Sí | **En uso** |
| Orphadata `product9_ages` (historia natural) | CC BY 4.0 | Sí | **En uso** |
| Orphadata `product4` (signos clínicos) | CC BY 4.0 | Sí | **En uso** |
| Orphadata `product6` (genes) | CC BY 4.0 | Sí | **En uso** |
| Orphanet Classifications | CC BY 4.0 | Sí | **En uso** |
| Orphadata `product1` (alineamientos) | CC BY 4.0 | Sí | **En uso** |
| HPO translations | Custom (no SPDX) | Sí, sin alterar | **En uso** |
| **ClinicalTrials.gov** | Dominio público EE.UU. | Sí | **En uso** |
| **EMA** (designaciones huérfanas) | Datos abiertos | Sí | **En uso** |
| **NANDO / NanbyoData** (Japón) | CC BY 4.0 | Sí | **En uso** |
| MONDO | CC BY 4.0 | Sí, con matices | Pendiente |
| **GARD (NCATS/NIH)** | Dominio público EE.UU. | Sí | **En uso** (asociaciones de pacientes) |
| PubMed | Mixto | Solo metadatos | Pendiente |
| **Orphanet: centros expertos, asociaciones de pacientes, fármacos** | **Requiere acuerdo** | **NO sin firmar** | **Descartado** |
| **OMIM** | **Propietario (JHU)** | **NO** | **Solo identificadores** |

Verificado sobre los ficheros reales: cada XML de Orphanet declara su licencia en
`<Availability><Licence>`, y el ingestor la lee de ahí para poblar `source.license_spdx`
en vez de fiarse de esta tabla. Ninguno de los productos de Orphadata que usamos está
marcado con condiciones especiales.

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
- **Qué usamos:** solo `babelon/hp-{lang}.babelon.tsv` del repositorio
  `obophenotype/hpo-translations`, que contiene **términos HPO traducidos y nada más**.
  Hace falta porque Orphanet publica las anotaciones de fenotipo en 9 idiomas pero no
  traduce los términos: en `es_product4` el síntoma sigue siendo «Macrocephaly».
- **⚠️ Trampa de OMIM — qué NO usamos:** el fichero `phenotype.hpoa` tiene una columna
  `disease_name` y, en las filas `OMIM:xxxxxx`, ese valor **es el título preferido de
  OMIM**, protegido por copyright. **No ingerimos `phenotype.hpoa`**: las anotaciones de
  fenotipo salen del producto propio de Orphanet (CC BY), que las trae con la misma
  información y sin ese campo. El fichero de traducciones no contiene datos de
  enfermedades, así que no arrastra el problema.
- La aserción del loader (`assert_no_omim_text`) sigue vigente como red de seguridad por
  si alguien añade `phenotype.hpoa` en el futuro.

## Orphanet: los productos que NO podemos usar

El directorio de **centros expertos**, **asociaciones de pacientes**, **registros** y
**medicamentos** de Orphanet **no es de descarga libre**. Requiere firmar un Data
Transfer Agreement (uso académico) o un contrato de servicio (uso comercial).

Es el directorio más completo de Europa y sería la mejor respuesta a «¿a dónde acudo?».
Mientras no exista ese acuerdo, esa necesidad se cubre con ClinicalTrials.gov, que es
público. Si algún día se firma, el patrón de ingesta ya está y solo hace falta el
adaptador.

## ClinicalTrials.gov (NIH)

- Obra del gobierno de EE.UU., de libre uso.
- **Obliga a:** atribuir y **no implicar respaldo de NIH/NCATS/NLM**. La interfaz lo
  dice explícitamente en la sección «Dónde acudir».
- **Ritmo:** la API responde 429 si se la aprieta. El adaptador espera 1 s entre
  consultas y reintenta con espera creciente. Es un servicio público y gratuito.
- **Vínculo con la enfermedad:** por código MeSH (que publica Orphanet), no por texto.
  Es una inferencia nuestra y se marca como tal en `disease_trial.match_method`.

## EMA — designaciones de medicamento huérfano

- Datos abiertos, tabla actualizada a diario.
- **No publica códigos ORPHA**: la enfermedad es texto libre («Treatment of Wilson's
  disease»). El emparejamiento es nuestro, solo por coincidencia exacta normalizada, y
  llega al 51%. Se prefiere perder la mitad a atribuir un fármaco a la enfermedad
  equivocada.
- **Aviso obligatorio en la interfaz:** una designación huérfana no es un fármaco
  aprobado ni disponible.

## NANDO / NanbyoData (Japón)

- **Licencia:** CC BY 4.0. Uso libre, incluido el comercial, citando.
- **Atribución:** NANDO (Nanbyo Disease Ontology), NanbyoData, DBCLS. https://nanbyodata.jp
- Es la única fuente que tenemos fuera del ámbito europeo. Aporta nombres en japonés
  (kanji e hiragana) y el número de designación oficial nipona, que allí determina la
  cobertura sanitaria. Mapea a códigos Orphanet directamente.

## GARD (NIH)

- Obra del gobierno de EE.UU., de libre uso. **No implicar respaldo** del NIH/NCATS.
- **Qué usamos (ADR 0006):** el directorio de **asociaciones de pacientes** por enfermedad.
  El sitio de GARD sirve JSON estáticos; se ingiere la lista de cuentas
  (`all-account-data.json`) y, por enfermedad, sus organizaciones (`singles/{gardId}.json`).
  El vínculo con nuestra enfermedad se hace por el **ID de GARD que Orphanet publica**
  (3.825), no por texto.
- **Encuadre:** apoyo e información, **no atención médica**. El buscador de especialistas o
  el registro de pacientes que se enlaza son de la propia organización, no una recomendación
  nuestra (regla 17).

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
