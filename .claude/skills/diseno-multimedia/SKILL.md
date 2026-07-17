---
name: diseno-multimedia
description: Diseño de piezas visuales para Morbi Rari — mapas, diagramas, ilustraciones, tarjetas para redes, infografías. Úsala al crear cualquier material gráfico. Prioriza exactitud de los datos, accesibilidad de color, coherencia claro/oscuro y atribución de fuentes.
---

# Diseño multimedia de Morbi Rari

Creas piezas visuales para un proyecto de datos médicos. La primera regla: **la estética
nunca distorsiona el dato.**

## Fidelidad al dato

- **No exageres ni inventes.** Un mapa, una barra o una infografía debe representar la cifra
  real y su **ámbito** (una prevalencia sin área geográfica ni tipo de medida engaña).
- **Nada de imaginería médica fabricada** que sugiera diagnóstico, tratamiento o resultado
  clínico. Sin curas milagrosas ni dramatización.
- **Cita la fuente en la propia pieza** cuando muestre datos (Orphanet © INSERM 1999,
  orpha.net; y la fuente correspondiente). **Nunca reproduzcas texto de OMIM**
  ([DATA_LICENSES.md](DATA_LICENSES.md)).

## Color y accesibilidad

- **Reutiliza la paleta del sistema** (variables `--ord-*` y demás de
  `apps/web/src/app/globals.css`) para que las piezas casen con la web. No inventes colores
  sueltos.
- **Legible para daltónicos y en escala de grises**: no codifiques información solo por tono
  (las bandas de frecuencia y el mapa de prevalencia deben distinguirse por otra vía además
  del color). Contraste AA.
- **Coherencia claro/oscuro**: entrega o contempla ambas variantes.

## El mapa de prevalencia (contexto ya decidido)

Leaflet **sin teselas** (tile-less), proyección **Natural Earth**, con el **antimeridiano
cortado** (evita la raya que cruzaba por Fiji), tema claro/oscuro. Mantén esas decisiones al
iterar sobre el mapa.

## Formato

- **SVG** siempre que se pueda (nítido, ligero, temable con variables CSS, accesible con
  `<title>`/`<desc>`). Para tarjetas de redes, tamaños de plataforma con **texto alternativo**
  provisto (coordínate con `redes-sociales`).
- Verifica un dato antes de graficarlo con `especialista-medicina-investigativa`. Un gráfico
  bonito con un dato mal es peor que no tener gráfico.
