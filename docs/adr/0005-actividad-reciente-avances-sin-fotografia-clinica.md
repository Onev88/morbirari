# ADR 0005 — Actividad reciente: avances como metadatos abiertos, sin fotografía clínica

- **Fecha:** 2026-07-17
- **Estado:** Aceptada
- **Ámbito:** parcialmente permanente. La política de imágenes restringe el roadmap a
  propósito (como [ADR 0002](0002-phenotype-filter-not-diagnostic.md)).

## Contexto

Cada ficha de enfermedad presenta hoy datos de referencia estables (nomenclatura,
epidemiología, genes, fenotipos). Se quiere que además muestre **qué se mueve** en esa
enfermedad —publicaciones, ensayos, designaciones— y que la ficha se sienta viva, no como
una entrada de wiki. Al plantearlo surgen dos disyuntivas con trade-offs reales.

**Primera: «noticias» vs «avances».** Una sección de *noticias* en sentido periodístico
—artículos de prensa sobre un «avance» en la enfermedad X— no tiene dato abierto
redistribuible detrás. Son obras con copyright del medio; ni EURORDIS, NORD u OrphaNews
publican un feed reindexable. Traerlo chocaría de frente con la disciplina de licencias
([DATA_LICENSES.md](../../DATA_LICENSES.md)). Lo que sí es dato abierto y estructurado es
la **actividad de investigación**: literatura (Europe PMC/PubMed), ensayos
(ClinicalTrials.gov, ya ingerido) y designaciones (EMA, ya ingerida).

**Segunda: imágenes.** El deseo de «que no se sienta wiki» invita a poner imágenes. La
tentación evidente es la **fotografía clínica** («así se ve la enfermedad»). Ese es
justamente el terreno que genera morbo, arrastra problemas de consentimiento y dignidad, y
empuja al usuario hacia el diagnóstico — la línea del ADR 0002.

## Decisión

### A. La sección se llama «actividad reciente», no «noticias», y se nutre solo de metadatos abiertos

1. **Se prohíbe el scraping de prensa o de boletines editoriales.** No hay fuente de
   noticias periodísticas.
2. **Fuente nueva: Europe PMC**, enganchada **por código MeSH** que Orphanet ya publica —el
   mismo patrón que [ClinicalTrials.gov](../../etl/src/morbirari_etl/sources/clinicaltrials/trials.py)
   (`AREA[ConditionMeshId]`), inferencia nuestra marcada con `match_method`.
3. **Solo metadatos, nunca el texto.** Título, autores, revista, fecha, PMID/DOI y enlace.
   El abstract **no se almacena ni se muestra** salvo en registros marcados por Europe PMC
   como acceso abierto/CC, y aun así con atribución. Es la misma disciplina que aplicamos a
   OMIM (hechos y enlace, no expresión protegida) y lo que ya declara la fila «PubMed» de
   `DATA_LICENSES.md`.
4. **Preprints (bioRxiv/medRxiv) fuera** del feed por defecto: material sin revisión por
   pares en una obra de referencia médica alimenta falsas esperanzas (regla 15). Si algún
   día entra, va etiquetado como no revisado y separado.
5. **Orden cronológico, determinista, sin ranking de relevancia ni curación editorial.**
   Igual que el ADR 0002 prohíbe puntuar candidatos de fenotipo, aquí se prohíbe puntuar
   «importancia» de un avance: ordenar por relevancia es emitir un juicio médico. Fecha
   descendente y basta.
6. **Encuadre neutral:** «publicaciones recientes / actividad investigadora», nunca
   «avances hacia la cura» ni nada que insinúe tratamiento disponible o esperanza clínica.
   Se preservan los matices ya establecidos (regla 17): una designación EMA **no** es un
   fármaco aprobado; «reclutando» **no** es una recomendación.
7. **La fecha de recuperación es visible** en el feed, como en el resto de la ficha
   (ADR 0001). En datos volátiles «reciente» es una promesa, y la frescura es la señal que
   la respalda.

**Fase A (barata):** el feed puede existir *ya* combinando ensayos y designaciones que **ya
se ingieren**, ordenados por fecha, sin abrir ningún frente de licencias.
**Fase B:** añadir Europe PMC como fuente propia vía la skill `anadir-fuente`
(tabla `disease_publication` con procedencia y `match_method`).

### B. Imágenes: esquemáticas y derivadas de datos sí; fotografía clínica de pacientes, no

8. **Prohibida la fotografía clínica de pacientes** (rasgos dismórficos, lesiones, rostros),
   con o sin rostro visible. No se ingiere, no se aloja, no se muestra.
9. **Permitida la imagen esquemática o generada a partir de datos que ya poseemos:**
   diagramas de herencia, mapa de centros de ensayo (ya existe el Leaflet), gráficos de
   prevalencia/bandas de frecuencia (paleta `--ord-*`), esquemas de sistemas afectados. Es
   el ámbito de la skill `diseno-multimedia`, con su atribución y accesibilidad.

## Razones

- **Por qué metadatos y no texto:** replicar abstracts es crear una base derivada de
  contenido con copyright del editor. Enlazar es gratis, legal y además manda tráfico a la
  fuente. El coste —no poder mostrar el resumen— es real pero asumible.
- **Por qué cronológico y no relevancia:** el precedente del ADR 0002 es exacto. Lo que
  convierte una herramienta de referencia en algo que aconseja es el juicio automatizado de
  importancia. No puntuar es lo que mantiene la función del lado seguro.
- **Por qué no fotografía clínica**, en tres frentes que fallan a la vez:
  - *Ético:* son datos de salud de categoría especial; el historial de fotografiar
    fenotipos raros —sobre todo de menores— con consentimiento dudoso es largo, y reduce a
    la persona a su enfermedad. Es literalmente **generar morbo**, contrario a la dignidad
    de una obra de referencia.
  - *Regulatorio:* una galería «así se ve X» empuja al «¿mi hijo se parece a esto?» — uso
    diagnóstico, la línea del ADR 0002.
  - *Viable:* no existe corpus abierto y redistribuible de fotos clínicas mapeado a las
    ~6.000 enfermedades de Orphanet. Habría imágenes para cuatro enfermedades conocidas y
    nada para la cola larga; esa inconsistencia se ve peor que la ausencia. La imagen
    generada, en cambio, es consistente porque sale de datos que ya tenemos para todas.

## Consecuencias

- **Cadencia de refresco alta** para literatura y ensayos, muy por encima de las ontologías
  (Orphanet publica dos veces al año). Es la consecuencia que ya anticipaba el ADR 0001 para
  la Fase 4: hay que decidir periodicidad de `mr ingest` y vigilar límites de tasa de
  Europe PMC como ya se hace con ClinicalTrials.gov.
- **El emparejamiento por MeSH es una inferencia** y se marca como tal; no toda enfermedad
  tiene MeSH (Orphanet lo publica para ~3.200), así que habrá fichas sin feed de
  publicaciones. Se prefiere el hueco honesto a un emparejamiento por texto libre.
- **Esto no es asesoría legal.** El uso de metadatos de PubMed/Europe PMC es estándar, pero
  el encuadre no-clínico y la ausencia de scoring son, igual que en el ADR 0002, lo que
  sostiene la calificación. Revisión específica antes de publicar en la UE.
- Si algún día se quisiera revertir la política de imágenes clínicas, la consecuencia no es
  «quitar este ADR»: es asumir el debate ético y de consentimiento, y el riesgo regulatorio,
  que aquí se decidieron evitar.

## Enlaces

- Refuerza [CLAUDE.md](../../CLAUDE.md) reglas 5 (frescura visible), 15–17 (encuadre
  regulatorio y matices), 18 (sanitización).
- Se apoya en [ADR 0001](0001-own-index-not-federation.md) (campos a una entidad canónica;
  frescura visible) y [ADR 0002](0002-phenotype-filter-not-diagnostic.md) (sin scoring = no
  diagnóstico).
- Actualizar la fila «PubMed» de [DATA_LICENSES.md](../../DATA_LICENSES.md) al integrar
  Europe PMC.
