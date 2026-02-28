---
name: pubmed-eutilities-reference
description: Usa este skill cuando el usuario pida búsquedas de literatura médica en PubMed con E-utilities (ESearch, ESummary, EFetch, ELink, EInfo, EPost, EGQuery, ESpell, ECitMatch), diseño de pipelines de consulta o resolución de parámetros de Entrez basados en el manual.
---

# PubMed E-utilities Reference Skill

## Cuándo usar este skill

Usa este skill cuando el usuario solicite:

- búsquedas bibliográficas en PubMed mediante E-utilities
- construcción de queries Entrez (`term`) para literatura médica
- pipelines con `ESearch -> ESummary/EFetch` o con `History Server` (`WebEnv`, `query_key`)
- identificación de endpoints y parámetros correctos de funciones E-utilities
- estrategias para recuperar PMIDs, resúmenes y registros completos

## Flujo recomendado

1. Confirma objetivo clínico/científico del usuario (tema, población, intervención, fecha, tipo de estudio).
2. Diseña la estrategia de búsqueda Entrez para PubMed (`db=pubmed`) usando campos (`[Title/Abstract]`, `[MeSH Terms]`, `[pdat]`, etc.).
3. Ejecuta `ESearch` para obtener PMIDs y, si aplica, activa `usehistory=y`.
4. Usa `ESummary` para inspección rápida o `EFetch` para detalle completo.
5. Si el usuario necesita registros relacionados, aplica `ELink`.
6. Si hay dudas ortográficas o de cobertura, usa `ESpell` y/o `EGQuery`.
7. Entrega resultados con reproducibilidad: URL usada, parámetros clave y fecha de consulta.

## Reglas prácticas

- Prioriza `db=pubmed` para literatura médica, salvo que el usuario pida otra base.
- Para conjuntos grandes, usa paginación (`retstart`, `retmax`) y/o `History server`.
- Explicita siempre los operadores booleanos (`AND`, `OR`, `NOT`) y filtros de fecha.
- Si el usuario busca evidencia clínica, sugiere filtros por tipo de estudio cuando corresponda.
- Incluye advertencias sobre límites de tasa y uso de `api_key` cuando haya alto volumen de llamadas.

## Referencias incluidas

- Resumen de funciones y endpoints: `references/eutilities_functions.md`
- Conversión completa del manual a Markdown: `references/eutilities_manual.md`

## Cómo usar las referencias

- Carga `references/eutilities_functions.md` primero para respuestas rápidas de funciones y endpoints.
- Carga `references/eutilities_manual.md` solo cuando se requiera detalle profundo de parámetros/sintaxis.
