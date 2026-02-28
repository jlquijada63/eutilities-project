# Funciones E-utilities (Estado Actual del Proyecto)

Fuente de verdad: `async_eutilities.py`

## Funciones activas

- `einfo` -> `einfo.fcgi`
- `esearch` -> `esearch.fcgi`
- `epost` -> `epost.fcgi`
- `esummary` -> `esummary.fcgi`
- `efetch` -> `efetch.fcgi`
- `elink` -> `elink.fcgi`

## Contrato actual de la API async

### `einfo(db="pubmed", options=None) -> str`

- Propósito: metadata de base Entrez (campos, enlaces, estadísticas).
- Parámetros frecuentes en `options`: `version`.

### `esearch(term, db="pubmed", options=None) -> list[str]`

- Propósito: buscar literatura y devolver PMIDs.
- Retorno: lista de PMIDs (`list[str]`), no XML crudo.
- Parámetros frecuentes en `options`: `retmax`, `retstart`, `sort`, `usehistory`, `datetype`, `mindate`, `maxdate`.

### `epost(ids, db="pubmed", options=None) -> str`

- Propósito: subir IDs al History server.
- Retorno: XML crudo del endpoint.

### `esummary(ids=None, db="pubmed", options=None) -> str`

- Propósito: recuperar DocSums por IDs o por history.
- Requisito: `ids` o (`query_key` y `WebEnv`).

### `efetch(pmid, db="pubmed", options=None) -> EFetchRecord`

- Propósito: recuperar un solo registro por PMID y parsearlo.
- Retorno: objeto Pydantic `EFetchRecord`.
- Campos relevantes: `pmid`, `article_title`, `abstract`, `journal_title`, `publication_date`, `authors`, `data`.

### `elink(ids=None, dbfrom="pubmed", db=None, options=None) -> str`

- Propósito: obtener enlaces/relaciones entre bases Entrez.
- Requisito: `ids` o (`query_key` y `WebEnv`).

## Notas de compatibilidad

- No están disponibles en el módulo actual: `egquery`, `espell`, `ecitmatch`.
- Si se requieren, deben reintroducirse explícitamente en `async_eutilities.py`.
