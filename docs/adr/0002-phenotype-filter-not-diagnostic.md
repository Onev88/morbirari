# ADR 0002 — La búsqueda por fenotipo es un filtro de catálogo, no una ayuda al diagnóstico

- **Fecha:** 2026-07-15
- **Estado:** Aceptada
- **Ámbito:** permanente. Restringe el roadmap a propósito.

## Contexto

Con anotaciones de fenotipos (HPO) en la base, es técnicamente trivial construir
"introduce síntomas → te sugiero enfermedades". Es también la función que más fácilmente
convierte el proyecto en un producto sanitario regulado.

La guía europea **MDCG 2019-11** establece que la "búsqueda simple" — recuperar registros
comparando metadatos contra criterios de búsqueda — **no** califica como software
sanitario (MDSW). Lo que cruza la línea es **crear o modificar información médica** bajo
una finalidad médica.

Precedente real: Orphanet ofrece búsqueda por signos clínicos en su web pública sin estar
regulado como dispositivo. Phenomizer y Face2Gene sí lo están. **La diferencia es el
scoring.**

## Decisión

Se permite la búsqueda por fenotipo **solo como filtro de catálogo**, con estas
restricciones. No son preferencias de diseño: son la razón por la que la función es legal.

1. **Recuperar, no inferir.** Consulta booleana de conjuntos sobre anotaciones
   preexistentes: "enfermedades anotadas con estos términos HPO". Es un hecho sobre el
   catálogo, no una predicción sobre una persona.
2. **Sin puntuación de probabilidad, sin porcentaje de coincidencia, sin ranking de
   verosimilitud diagnóstica.** Orden determinista y neutral (alfabético, o por recuento
   crudo de anotaciones coincidentes).
3. **No se aceptan datos de paciente.** Ni edad, ni sexo, ni historia clínica. Es una
   consulta a un catálogo, no un caso clínico.
4. **Encuadre en la interfaz:** "explorar el catálogo por características clínicas".
   Nunca "averigua qué enfermedad tienes". El texto de la interfaz forma parte de la
   *finalidad prevista* y es lo que un regulador lee.

## El punto que se olvida

**El disclaimer no es lo que protege. Lo que decide la calificación regulatoria es la
funcionalidad.** Un aviso de "esto no es un diagnóstico" bajo un motor que puntúa
candidatos no cambia nada. Lo que la cambia es no puntuar.

Por eso esta ADR existe: cuando alguien (incluidos nosotros) proponga "añadir un pequeño
ranking de relevancia, total es solo ordenar mejor", esa propuesta es precisamente lo que
convierte el producto en un dispositivo médico. Rechazarla no es conservadurismo: es la
decisión que ya se tomó aquí.

## Consecuencias

- La función entra en **Fase 4**, no antes, y se construye sobre el producto de fenotipos
  propio de Orphanet (CC BY), no sobre `phenotype.hpoa` (ver ADR de licencias y
  `DATA_LICENSES.md`).
- **Esto no es asesoría legal.** La calificación depende de la finalidad prevista y de
  cómo se presenta el producto en conjunto. Antes de publicar esta función en la UE hace
  falta una revisión legal específica.
- Si en el futuro se decide que el scoring es imprescindible, la consecuencia no es
  "quitar esta ADR": es asumir el proceso de conformidad MDR que corresponda.
