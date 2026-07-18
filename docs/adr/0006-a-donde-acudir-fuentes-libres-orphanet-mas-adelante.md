# ADR 0006 — «A dónde acudir»: fuentes libres ahora, Orphanet bajo acuerdo más adelante

- **Fecha:** 2026-07-17
- **Estado:** Aceptada
- **Ámbito:** restringe el roadmap a propósito (qué fuentes sí y cuáles no) y fija encuadre
  regulatorio.

## Contexto

Se quiere enriquecer «Dónde acudir» para que las personas sepan a dónde ir: más datos de
los centros (web, redes) y, sobre todo, un listado de **fundaciones y asociaciones de
pacientes**.

El directorio más completo —centros expertos, asociaciones, registros, biobancos— es el de
**Orphanet**, pero su catálogo de recursos expertos **no es de descarga libre**: exige
firmar un Data Transfer Agreement (academia) o un contrato de servicio (comercial). Ya está
recogido en [DATA_LICENSES.md](../../DATA_LICENSES.md) como «descartado hasta firmar», y lo
confirma el propio Orphadata.

ClinicalTrials.gov, nuestra fuente actual de centros, **no publica web ni redes**; sí un
*contacto de estudio* (nombre, email, teléfono; dominio público) que hoy no traemos.
Fuentes libres y estructuradas disponibles: **GARD** (NCATS/NIH, dominio público, del que
**ya tenemos los identificadores** vía Orphanet), **ROR** (CC0, web institucional y cruces a
Wikidata) y **Wikidata** (CC0, web y redes de algunas organizaciones).

## Decisión

1. **Por ahora, solo fuentes libres:**
   - **Asociaciones y recursos por enfermedad: GARD** (dominio público). Semilla del listado
     de «a dónde acudir» de tipo no clínico.
   - **Web institucional de un centro: ROR/Wikidata** (CC0), emparejando el texto libre de
     ClinicalTrials.gov de forma conservadora y marcándolo como inferido.
   - **Contacto del ensayo: ClinicalTrials.gov** (dominio público), encuadrado como contacto
     de investigación, no de atención.
   - **No** se scrapean directorios propietarios (NORD, EURORDIS) ni redes sociales. A las
     organizaciones paraguas se **enlaza**, no se ingiere su contenido.
2. **Orphanet queda pendiente de una solicitud** (DTA académico o contrato de servicio) más
   adelante. Hasta firmar, **no se ingiere** su directorio. El patrón de ingesta ya existe;
   solo faltaría el adaptador. La acción concreta queda anotada en [TODO.md](../../TODO.md).
3. **Encuadre — parte del diseño, no un extra (regla 17):**
   - Sede de ensayo = investigación, **no atención**. No se presenta un centro de ensayo como
     «aquí te tratan».
   - Asociación de pacientes = apoyo e información, **no consejo médico**.
   - El emparejamiento centro→web/organización es **inferencia nuestra**: conservador,
     marcado como tal (`match_method`, como con MeSH o la EMA), con procedencia y fecha de
     recuperación visibles. Un enlace muerto o una organización extinta desorienta justo a
     quien más lo necesita: hay **deber de exactitud**.

## Razones

- **Libres primero:** sin bloqueo legal, coste cero y se puede empezar ya. Orphanet es mejor,
  pero su valor no justifica parar el resto hasta que haya acuerdo.
- **Orphanet después:** es la respuesta más completa de Europa; cuando exista el acuerdo,
  complementa o reemplaza las fuentes libres **sin rehacer la arquitectura** (índice propio,
  campos a una entidad canónica — [ADR 0001](0001-own-index-not-federation.md)).
- **Encuadre:** es lo que mantiene la función del lado correcto. Como en la
  [ADR 0002](0002-phenotype-filter-not-diagnostic.md), lo que protege es la funcionalidad y el
  texto, no un aviso legal.

## Consecuencias

- **Cobertura parcial y desigual:** GARD es US-céntrico; ROR/Wikidata cubren bien las
  instituciones grandes y mal la cola larga. Se asume el **hueco honesto** frente a inventar o
  a un mal emparejamiento.
- **Emparejamiento difuso** centro→ROR/Wikidata: conservador; ante la duda, no se enlaza.
- **Cada fuente que se integre actualiza [DATA_LICENSES.md](../../DATA_LICENSES.md) antes de
  ingerir** (obligatorio, regla 12).
- **Frescura:** enlaces y organizaciones cambian; entra en la disciplina de refresco de datos
  volátiles (ver [TODO.md](../../TODO.md)).
- Si más adelante se firma Orphanet, la consecuencia no es rehacer nada: es añadir el
  adaptador y decidir la precedencia entre fuentes.
- **Esto no es asesoría legal:** el uso de GARD (dominio público), ROR y Wikidata (CC0) es
  estándar, pero antes de publicar conviene revisar la atribución de cada una.
