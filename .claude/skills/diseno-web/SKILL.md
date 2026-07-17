---
name: diseno-web
description: Diseño de interfaz y experiencia para la web de Morbi Rari (Next.js). Úsala al crear o modificar pantallas, componentes o estilos. Cubre SSR indexable, funcionar sin JavaScript, tema claro/oscuro, bilingüe, accesibilidad y el encuadre regulatorio de la interfaz.
---

# Diseño web de Morbi Rari

Diseñas para una obra de referencia médica bilingüe. La interfaz no es solo estética: **su
texto y su encuadre forman parte de la finalidad prevista que lee un regulador** (ADR 0002).

## Reglas técnicas de la casa

- **SSR e indexable.** El contenido va en el HTML servido. Las pestañas del dashboard cargan
  **todo** su contenido en el HTML (una sección visible a la vez) para que siga siendo
  indexable y **funcione sin JavaScript**. No escondas contenido tras carga cliente.
- **Bilingüe de serie (ES/EN).** Ningún texto incrustado: todo en `apps/web/messages/{lang}.json`
  vía `next-intl`. Diseña para que ambos idiomas quepan (el español suele ser más largo).
- **Tema claro/oscuro** en todo. Usa las variables CSS de `globals.css`
  (incluida la paleta ordinal `--ord-*` de bandas de frecuencia); no hardcodees colores.
- **Solo lectura.** La web nunca escribe ni emite DDL; los datos llegan de `src/lib/` (SQL a
  mano). El diseño no asume formularios de escritura de datos clínicos.

## Encuadre regulatorio (parte del diseño, no un extra)

- **«Explorar el catálogo por características clínicas», nunca «averigua qué enfermedad
  tienes».** El copy de la búsqueda por fenotipo es lo que la mantiene legal.
- **Sin puntuación ni «% de coincidencia»** en resultados de fenotipo: orden neutro. No
  diseñes barras de «probabilidad de diagnóstico».
- **El disclaimer es visible** y traducido en cada idioma.
- **La frescura es visible**: cada ficha muestra fuente y fecha de recuperación. Trátalo como
  elemento de diseño de primer nivel (confianza), no como letra pequeña.

## Accesibilidad y matiz de datos

- Contraste AA como mínimo; no depender solo del color (las bandas de frecuencia y el mapa de
  prevalencia deben leerse sin distinguir tonos). Coordínate con `diseno-multimedia`.
- Respeta los matices del dominio en la jerarquía visual: gen causante vs modificador,
  designación ≠ aprobación, «reclutando» sin connotación de recomendación.

## Verificación

Usa el preview del proyecto (`.claude/launch.json`, servidor `web`): comprueba en claro y
oscuro, en ES y EN, con y sin JS, y en móvil. Verifica de verdad en el navegador antes de dar
un cambio por bueno; no lo asumas.
