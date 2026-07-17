---
name: escribir-adr
description: Redactar un Architecture Decision Record en el estilo de Morbi Rari. Úsala cuando una decisión tenga trade-offs que valga la pena registrar (arquitectura, datos, licencias, alcance regulatorio). Numerada, en español, en docs/adr/.
---

# Escribir un ADR

Un ADR registra **una decisión con trade-offs y su porqué**, para que dentro de un año se
entienda no solo qué se hizo sino por qué se descartó lo demás. En Morbi Rari van en
`docs/adr/`, numerados y en español.

## Cuándo escribir uno

- Elecciones de arquitectura o de modelo de datos con alternativas reales descartadas.
- Decisiones de licencia o de alcance regulatorio (p. ej. ADR 0002, fenotipo no diagnóstico).
- Restricciones deliberadas del roadmap («esto no se hace, y por qué»).

Un TODO puntual **no** es un ADR: va en [TODO.md](TODO.md). Un ADR es una *decisión*, no una
tarea.

## Formato de la casa

Numera con el siguiente correlativo (`docs/adr/000N-titulo-en-kebab.md`). Estructura:

```markdown
# ADR 000N — Título en una frase que diga la decisión

- **Fecha:** AAAA-MM-DD
- **Estado:** Aceptada | Propuesta | Reemplaza a 000M | Reemplazada por 000M
- **Ámbito:** (opcional) p. ej. «permanente. Restringe el roadmap a propósito.»

## Contexto

Qué problema o disyuntiva lo motiva. Las alternativas que había sobre la mesa.

## Decisión

Qué se decide, en concreto. Si son restricciones, enuméralas.

## Razones

Por qué esta y no las otras. Con datos cuando los haya (tiempos, tamaños, precedentes).

## Consecuencias

Qué se asume a cambio: lo que ahora cuesta más, lo que hay que vigilar, qué habría que hacer
si la decisión se revierte.
```

## Tono

- **Español, directo, honesto sobre el coste.** Los ADR existentes admiten sus contras
  abiertamente («no hay comprobación automática entre migración y tipos»). Imítalo.
- Cuando aplique, cita datos reales de este repo, no genéricos.
- Si el ADR toca algo que ya vive en [CLAUDE.md](CLAUDE.md), enlázalos para que no diverjan.
