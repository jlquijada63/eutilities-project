from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Iterable

import httpx
from dotenv import load_dotenv

from async_eutilities_helpers import (
    RequestOptions,
    XMLParseError,
    build_default_config,
    clean_params,
    merge_call_config,
    normalize_ids,
    parse_efetch_record,
    parse_esearch_pmids,
    require_non_empty,
    validate_transport_config,
)
from async_eutilities_models import EFetchAuthor, EFetchRecord

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

load_dotenv()


class EUtilitiesError(Exception):
    """Raised when an E-utilities request or XML parsing step fails."""


_DEFAULT_CONFIG: RequestOptions = build_default_config(BASE_URL)
_CONFIG: RequestOptions = deepcopy(_DEFAULT_CONFIG)


def configure(
    *,
    api_key: str | None = None,
    email: str | None = None,
    tool: str | None = None,
    base_url: str = BASE_URL,
    timeout: float = 30.0,
    max_retries: int = 2,
    retry_backoff: float = 0.5,
) -> None:
    """Set module-level defaults used by all E-utilities calls."""
    if timeout <= 0:
        raise ValueError("timeout must be greater than 0")
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if retry_backoff < 0:
        raise ValueError("retry_backoff must be >= 0")

    defaults = build_default_config(base_url.rstrip("/"))
    _CONFIG.update(
        {
            "api_key": api_key if api_key is not None else defaults.get("api_key"),
            "email": email,
            "tool": tool,
            "base_url": base_url.rstrip("/"),
            "timeout": timeout,
            "max_retries": max_retries,
            "retry_backoff": retry_backoff,
        }
    )


def get_config() -> RequestOptions:
    """Return a copy of the active module-level configuration."""
    return deepcopy(_CONFIG)


def reset_config() -> None:
    """Reset module configuration to defaults, reloading `NCBI_API_KEY` from env."""
    global _DEFAULT_CONFIG
    _DEFAULT_CONFIG = build_default_config(BASE_URL)
    _CONFIG.clear()
    _CONFIG.update(deepcopy(_DEFAULT_CONFIG))


async def _request(
    endpoint: str,
    *,
    params: RequestOptions | None = None,
    method: str = "GET",
    options: RequestOptions | None = None,
) -> str:
    """Execute an HTTP request with retry/backoff using merged config and per-call options."""
    config, extra_params = merge_call_config(_CONFIG, options)
    validate_transport_config(config)

    merged_params: RequestOptions = {
        "api_key": config.get("api_key"),
        "tool": config.get("tool"),
        "email": config.get("email"),
    }
    if params:
        merged_params.update(params)
    if extra_params:
        merged_params.update(extra_params)

    request_params = clean_params(merged_params)
    url = f"{str(config['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"

    attempts = int(config["max_retries"]) + 1
    backoff = float(config["retry_backoff"])
    last_exc: Exception | None = None

    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=float(config["timeout"])) as client:
                if method.upper() == "POST":
                    response = await client.post(url, data=request_params)
                else:
                    response = await client.get(url, params=request_params)

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt < attempts - 1:
                    if backoff > 0:
                        await asyncio.sleep(backoff * (2**attempt))
                    continue

            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            retryable = status == 429 or 500 <= status < 600
            if retryable and attempt < attempts - 1:
                if backoff > 0:
                    await asyncio.sleep(backoff * (2**attempt))
                continue
            break
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                if backoff > 0:
                    await asyncio.sleep(backoff * (2**attempt))
                continue
            break

    raise EUtilitiesError(f"Request failed for {url}: {last_exc}") from last_exc


async def einfo(db: str = "pubmed", options: RequestOptions | None = None) -> str:
    """Return metadata and search fields for an Entrez database."""
    db_name = require_non_empty(db, "db")
    return await _request("einfo.fcgi", params={"db": db_name}, options=options)


async def esearch(term: str, db: str = "pubmed", options: RequestOptions | None = None) -> list[str]:
    """Search Entrez and return only the list of PMIDs from XML response."""
    query = require_non_empty(term, "term")
    db_name = require_non_empty(db, "db")

    xml_text = await _request("esearch.fcgi", params={"db": db_name, "term": query}, options=options)
    try:
        return parse_esearch_pmids(xml_text)
    except XMLParseError as exc:
        raise EUtilitiesError(str(exc)) from exc


async def epost(
    ids: str | int | Iterable[str | int],
    db: str = "pubmed",
    options: RequestOptions | None = None,
) -> str:
    """Upload IDs to Entrez History server."""
    normalized_ids = normalize_ids(ids)
    if not normalized_ids:
        raise ValueError("ids is required")

    db_name = require_non_empty(db, "db")
    return await _request(
        "epost.fcgi",
        method="POST",
        params={"db": db_name, "id": normalized_ids},
        options=options,
    )


async def esummary(
    ids: str | int | Iterable[str | int] | None = None,
    db: str = "pubmed",
    options: RequestOptions | None = None,
) -> str:
    """Fetch document summaries by IDs or history (`query_key` + `WebEnv`)."""
    db_name = require_non_empty(db, "db")

    normalized_ids = normalize_ids(ids)
    runtime_options = dict(options or {})
    has_history = bool(runtime_options.get("query_key")) and bool(runtime_options.get("WebEnv"))
    if not normalized_ids and not has_history:
        raise ValueError("provide ids or options with query_key and WebEnv")

    params: RequestOptions = {"db": db_name}
    if normalized_ids:
        params["id"] = normalized_ids

    return await _request("esummary.fcgi", params=params, options=runtime_options)


async def efetch(pmid: str | int, db: str = "pubmed", options: RequestOptions | None = None) -> EFetchRecord:
    """Fetch a single record by PMID and return it as `EFetchRecord`."""
    pmid_value = require_non_empty(pmid, "pmid")
    db_name = require_non_empty(db, "db")

    xml_text = await _request(
        "efetch.fcgi",
        params={"db": db_name, "id": pmid_value, "retmax": 1},
        options=dict(options or {}),
    )
    try:
        return parse_efetch_record(xml_text, db_name)
    except XMLParseError as exc:
        raise EUtilitiesError(str(exc)) from exc


async def elink(
    ids: str | int | Iterable[str | int] | None = None,
    dbfrom: str = "pubmed",
    db: str | None = None,
    options: RequestOptions | None = None,
) -> str:
    """Find linked/related records across Entrez databases."""
    source_db = require_non_empty(dbfrom, "dbfrom")

    normalized_ids = normalize_ids(ids)
    runtime_options = dict(options or {})
    has_history = bool(runtime_options.get("query_key")) and bool(runtime_options.get("WebEnv"))
    if not normalized_ids and not has_history:
        raise ValueError("provide ids or options with query_key and WebEnv")

    params: RequestOptions = {"dbfrom": source_db}
    if db is not None:
        params["db"] = require_non_empty(db, "db")
    if normalized_ids:
        params["id"] = normalized_ids

    return await _request("elink.fcgi", params=params, options=runtime_options)





__all__ = [
    "BASE_URL",
    "EUtilitiesError",
    "EFetchAuthor",
    "EFetchRecord",
    "configure",
    "get_config",
    "reset_config",
    "einfo",
    "esearch",
    "epost",
    "esummary",
    "efetch",
    "elink",
]
