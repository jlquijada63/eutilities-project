# Funciones E-utilities Extraídas del Manual

Fuente: `eutilities_manual.pdf`

## Conjunto de funciones identificado

- `EInfo` (`einfo.fcgi`)
- `ESearch` (`esearch.fcgi`)
- `EPost` (`epost.fcgi`)
- `ESummary` (`esummary.fcgi`)
- `EFetch` (`efetch.fcgi`)
- `ELink` (`elink.fcgi`)
- `EGQuery` (`egquery.fcgi`)
- `ESpell` (`espell.fcgi`)
- `ECitMatch` (`ecitmatch.cgi`)

## Detalle por función

### EInfo

- Endpoint: `einfo.fcgi`
- Endpoint detectado en texto: `einfo.fcgi?db=<database>`
- Propósito: Obtiene estadísticas de una base de datos Entrez (campos, enlaces, últimos updates).
- Parámetros clave: `db`, `version`
- Salida típica: lista de campos de búsqueda, enlaces disponibles y metadatos de la base
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi`

### ESearch

- Endpoint: `esearch.fcgi`
- Endpoint detectado en texto: `esearch.fcgi?db=<database>&term=<query>`
- Propósito: Busca en una base de datos Entrez y devuelve UIDs; puede guardar resultados en History server.
- Parámetros clave: `db`, `term`, `retmax`, `retstart`, `sort`, `usehistory`
- Salida típica: `Count`, `IdList`, y opcionalmente `WebEnv`/`QueryKey`
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi`

### EPost

- Endpoint: `epost.fcgi`
- Endpoint detectado en texto: `epost.fcgi?db=<database>&id=<uid_list>`
- Propósito: Sube listas de UIDs al History server para usarlas en llamadas posteriores.
- Parámetros clave: `db`, `id` (o `WebEnv` existente para anexar)
- Salida típica: `WebEnv` y `QueryKey` para consultas encadenadas
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/epost.fcgi`

### ESummary

- Endpoint: `esummary.fcgi`
- Endpoint detectado en texto: `esummary.fcgi?db=<database>&id=<uid_list>`
- Propósito: Recupera resúmenes de documentos (DocSums) para uno o varios UIDs.
- Parámetros clave: `db`, `id` o (`query_key` + `WebEnv`), `retmode`
- Salida típica: `DocSum` por UID con campos resumidos
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi`

### EFetch

- Endpoint: `efetch.fcgi`
- Endpoint detectado en texto: `efetch.fcgi?db=<database>&id=<uid_list>&rettype=<retrieval_type>`
- Propósito: Recupera registros completos en distintos formatos (por ejemplo XML, MEDLINE, FASTA).
- Parámetros clave: `db`, `id` o (`query_key` + `WebEnv`), `rettype`, `retmode`, `retstart`, `retmax`
- Salida típica: registros completos del recurso solicitado (p. ej., PubMed XML/MEDLINE)
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi`

### ELink

- Endpoint: `elink.fcgi`
- Endpoint detectado en texto: `elink.fcgi?dbfrom=<source_db>&db=<destination_db>&id=<uid_list>`
- Propósito: Obtiene registros relacionados y enlaces entre bases de datos Entrez.
- Parámetros clave: `dbfrom`, `db`, `id` o (`query_key` + `WebEnv`), `linkname`, `cmd`
- Salida típica: conjuntos de UIDs relacionados y metadatos de enlace
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi`

### EGQuery

- Endpoint: `egquery.fcgi`
- Endpoint detectado en texto: `egquery.fcgi?term=<query>`
- Propósito: Ejecuta una búsqueda global en todas las bases Entrez y devuelve conteos por base.
- Parámetros clave: `term`
- Salida típica: conteo de resultados por base de datos Entrez
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/egquery.fcgi`

### ESpell

- Endpoint: `espell.fcgi`
- Endpoint detectado en texto: `espell.fcgi?term=<query>&db=<database>`
- Propósito: Obtiene sugerencias ortográficas para términos de búsqueda Entrez.
- Parámetros clave: `term`, `db`
- Salida típica: término original y término sugerido
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/espell.fcgi`

### ECitMatch

- Endpoint: `ecitmatch.cgi`
- Endpoint detectado en texto: `ecitmatch.cgi?db=pubmed&rettype=xml&bdata=<citations>`
- Propósito: Busca PMIDs a partir de datos de cita (journal, año, volumen, páginas, autor, etc.).
- Parámetros clave: `db=pubmed`, `bdata`, `rettype`
- Salida típica: mapeo de cita de entrada a PMID (cuando hay coincidencia)
- URL base de ejemplo: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ecitmatch.cgi`
