---
name: pubmed-eutilities-reference
description: Usa este skill cuando el usuario pida búsquedas de literatura médica en PubMed con la API E-utilities implementada en el proyecto (`einfo`, `esearch`, `epost`, `esummary`, `efetch`, `elink`), incluyendo construcción de queries Entrez, recuperación de PMIDs y parsing de registros de PubMed.
---

# PubMed E-utilities Reference Skill

Este skill está alineado con la implementación actual de `async_eutilities.py`.

## Flujo recomendado

1. Definir estrategia de búsqueda (`term`, filtros y campos Entrez).
2. Usar `esearch` para recuperar PMIDs como `list[str]`.
3. Usar `epost`/`esummary` cuando se necesite History server o DocSums.
4. Usar `efetch` por PMID para obtener un `EFetchRecord` parseado.
5. Usar `elink` para explorar relaciones entre registros.

## API vigente

- `einfo(db="pubmed", options=None) -> str`
- `esearch(term, db="pubmed", options=None) -> list[str]`
- `epost(ids, db="pubmed", options=None) -> str`
- `esummary(ids=None, db="pubmed", options=None) -> str`
- `efetch(pmid, db="pubmed", options=None) -> EFetchRecord`
- `elink(ids=None, dbfrom="pubmed", db=None, options=None) -> str`

## Referencias incluidas

- Resumen actualizado de funciones: `references/eutilities_functions.md`
- Conversión del manual original: `references/eutilities_manual.md`

## Cómo usar las referencias

- Cargar primero `references/eutilities_functions.md` para endpoint/parámetros actuales.
- Cargar `references/eutilities_manual.md` solo para detalle histórico o parámetros legacy.
