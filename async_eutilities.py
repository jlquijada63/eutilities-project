from __future__ import annotations

import asyncio
import os
from copy import deepcopy
from typing import Any, Iterable

import httpx
from dotenv import load_dotenv

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Load environment values from .env (if present) before reading NCBI settings.
load_dotenv()


def _build_default_config() -> dict[str, Any]:
    return {
        "api_key": os.getenv("NCBI_API_KEY"),
        "email": None,
        "tool": None,
        "base_url": BASE_URL,
        "timeout": 30.0,
        "max_retries": 2,
        "retry_backoff": 0.5,
    }


_DEFAULT_CONFIG: dict[str, Any] = _build_default_config()

_CONFIG: dict[str, Any] = deepcopy(_DEFAULT_CONFIG)


class EUtilitiesError(Exception):
    """Raised when an E-utilities HTTP request fails after retries."""


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
    """Set global request defaults used by all E-utilities functions.

    Use this once at startup to avoid repeating transport and auth options in every tool call.

    Args:
        api_key: NCBI API key for higher request limits. If omitted, `NCBI_API_KEY` from
            `.env`/environment is used when available.
        email: Contact email recommended by NCBI.
        tool: Tool identifier sent to NCBI.
        base_url: Base E-utilities URL.
        timeout: Request timeout in seconds.
        max_retries: Retry attempts on transient failures.
        retry_backoff: Base backoff in seconds for exponential retry delays.
    """
    if timeout <= 0:
        raise ValueError("timeout must be greater than 0")
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if retry_backoff < 0:
        raise ValueError("retry_backoff must be >= 0")

    effective_api_key = api_key if api_key is not None else os.getenv("NCBI_API_KEY")

    _CONFIG.update(
        {
            "api_key": effective_api_key,
            "email": email,
            "tool": tool,
            "base_url": base_url.rstrip("/"),
            "timeout": timeout,
            "max_retries": max_retries,
            "retry_backoff": retry_backoff,
        }
    )


def get_config() -> dict[str, Any]:
    """Return a copy of the current module-level E-utilities configuration."""
    return deepcopy(_CONFIG)


def reset_config() -> None:
    """Reset module-level configuration values to defaults (including `NCBI_API_KEY`)."""
    global _DEFAULT_CONFIG
    _DEFAULT_CONFIG = _build_default_config()
    _CONFIG.clear()
    _CONFIG.update(deepcopy(_DEFAULT_CONFIG))


def _normalize_ids(ids: Iterable[str | int] | str | int | None) -> str | None:
    if ids is None:
        return None
    if isinstance(ids, (str, int)):
        value = str(ids).strip()
        return value or None

    items = [str(value).strip() for value in ids if str(value).strip()]
    return ",".join(items) if items else None


def _clean_params(params: dict[str, Any]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "y" if value else "n"
            continue
        cleaned[key] = str(value)
    return cleaned


def _merge_call_config(options: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    opts = dict(options or {})
    config = deepcopy(_CONFIG)

    for config_key in ("api_key", "email", "tool", "base_url", "timeout", "max_retries", "retry_backoff"):
        if config_key in opts:
            config[config_key] = opts.pop(config_key)

    return config, opts


async def _request(
    endpoint: str,
    *,
    params: dict[str, Any] | None = None,
    method: str = "GET",
    options: dict[str, Any] | None = None,
) -> str:
    """Execute a request against one E-utilities endpoint with retry logic.

    Retry behavior:
    - Retries transient HTTP errors (429 and 5xx)
    - Retries network/timeout errors from `httpx`
    - Uses exponential backoff based on configured `retry_backoff`
    """
    config, extra_params = _merge_call_config(options)

    if float(config["timeout"]) <= 0:
        raise ValueError("timeout must be greater than 0")
    if int(config["max_retries"]) < 0:
        raise ValueError("max_retries must be >= 0")
    if float(config["retry_backoff"]) < 0:
        raise ValueError("retry_backoff must be >= 0")

    merged: dict[str, Any] = {
        "api_key": config.get("api_key"),
        "tool": config.get("tool"),
        "email": config.get("email"),
    }
    if params:
        merged.update(params)
    if extra_params:
        merged.update(extra_params)

    request_params = _clean_params(merged)
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
            is_retryable = status == 429 or 500 <= status < 600
            if is_retryable and attempt < attempts - 1:
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


async def einfo(db: str = "pubmed", options: dict[str, Any] | None = None) -> str:
    """Return metadata and search field information for an Entrez database.

    Use this to inspect available fields and link names before building advanced queries.

    Args:
        db: Entrez database name. Defaults to `pubmed`.
        options: Optional advanced params, e.g. `{"version": "2.0"}` plus transport overrides.

    Returns:
        Raw response text from `einfo.fcgi`.

    Raises:
        ValueError: If `db` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await einfo("pubmed")
    """
    if not db or not db.strip():
        raise ValueError("db is required")
    return await _request("einfo.fcgi", params={"db": db.strip()}, options=options)


async def esearch(term: str, db: str = "pubmed", options: dict[str, Any] | None = None) -> str:
    """Search an Entrez database and return matching IDs.

    Primary tool for literature search in PubMed. Advanced controls (pagination/history/sort)
    are passed through `options`.

    Args:
        term: Entrez query string.
        db: Entrez database. Defaults to `pubmed`.
        options: Optional endpoint params such as `retmax`, `retstart`, `usehistory`,
            `sort`, `field`, `datetype`, `mindate`, `maxdate`, `retmode`.

    Returns:
        Raw response text from `esearch.fcgi`.

    Raises:
        ValueError: If `term` or `db` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await esearch("asthma AND 2024[pdat]", options={"retmax": 20, "usehistory": True})
    """
    if not term or not term.strip():
        raise ValueError("term is required")
    if not db or not db.strip():
        raise ValueError("db is required")

    return await _request(
        "esearch.fcgi",
        params={"db": db.strip(), "term": term.strip()},
        options=options,
    )


async def epost(
    ids: str | int | Iterable[str | int],
    db: str = "pubmed",
    options: dict[str, Any] | None = None,
) -> str:
    """Upload IDs to Entrez History server for later chained requests.

    Use this when you already have a large UID set and want to reference it via `WebEnv/query_key`.

    Args:
        ids: Single UID or iterable of UIDs to upload.
        db: Entrez database. Defaults to `pubmed`.
        options: Optional endpoint params such as `WebEnv` plus transport overrides.

    Returns:
        Raw response text from `epost.fcgi`.

    Raises:
        ValueError: If `ids` is empty or `db` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await epost([12345, 67890])
    """
    normalized_ids = _normalize_ids(ids)
    if not normalized_ids:
        raise ValueError("ids is required")
    if not db or not db.strip():
        raise ValueError("db is required")

    return await _request(
        "epost.fcgi",
        method="POST",
        params={"db": db.strip(), "id": normalized_ids},
        options=options,
    )


async def esummary(
    ids: str | int | Iterable[str | int] | None = None,
    db: str = "pubmed",
    options: dict[str, Any] | None = None,
) -> str:
    """Fetch document summaries (DocSums) for IDs or a history set.

    Use after `esearch` or `epost` for lightweight metadata (titles, dates, journal, etc.).

    Args:
        ids: Optional single UID or iterable. If omitted, provide `query_key` and `WebEnv` in `options`.
        db: Entrez database. Defaults to `pubmed`.
        options: Optional endpoint params such as `query_key`, `WebEnv`, `retstart`,
            `retmax`, `retmode`, `version` plus transport overrides.

    Returns:
        Raw response text from `esummary.fcgi`.

    Raises:
        ValueError: If neither `ids` nor history parameters are provided, or `db` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await esummary(options={"query_key": 1, "WebEnv": "...", "retmax": 10})
    """
    if not db or not db.strip():
        raise ValueError("db is required")

    normalized_ids = _normalize_ids(ids)
    opts = dict(options or {})
    has_history = bool(opts.get("query_key")) and bool(opts.get("WebEnv"))
    if not normalized_ids and not has_history:
        raise ValueError("provide ids or options with query_key and WebEnv")

    params = {"db": db.strip()}
    if normalized_ids:
        params["id"] = normalized_ids

    return await _request("esummary.fcgi", params=params, options=opts)


async def efetch(
    ids: str | int | Iterable[str | int] | None = None,
    db: str = "pubmed",
    options: dict[str, Any] | None = None,
) -> str:
    """Fetch full records for IDs or a history set.

    Use this for full PubMed/XML/MEDLINE content after selecting a set with `esearch` or `epost`.

    Args:
        ids: Optional single UID or iterable. If omitted, provide `query_key` and `WebEnv` in `options`.
        db: Entrez database. Defaults to `pubmed`.
        options: Optional endpoint params such as `query_key`, `WebEnv`, `rettype`,
            `retmode`, `retstart`, `retmax`, `strand`, `seq_start`, `seq_stop`.

    Returns:
        Raw response text from `efetch.fcgi`.

    Raises:
        ValueError: If neither `ids` nor history parameters are provided, or `db` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await efetch(options={"query_key": 1, "WebEnv": "...", "rettype": "abstract"})
    """
    if not db or not db.strip():
        raise ValueError("db is required")

    normalized_ids = _normalize_ids(ids)
    opts = dict(options or {})
    has_history = bool(opts.get("query_key")) and bool(opts.get("WebEnv"))
    if not normalized_ids and not has_history:
        raise ValueError("provide ids or options with query_key and WebEnv")

    params = {"db": db.strip()}
    if normalized_ids:
        params["id"] = normalized_ids

    return await _request("efetch.fcgi", params=params, options=opts)


async def elink(
    ids: str | int | Iterable[str | int] | None = None,
    dbfrom: str = "pubmed",
    db: str | None = None,
    options: dict[str, Any] | None = None,
) -> str:
    """Find linked/related records across Entrez databases.

    Use this to navigate from PubMed records to related records or linked resources.

    Args:
        ids: Optional single UID or iterable. If omitted, provide `query_key` and `WebEnv` in `options`.
        dbfrom: Source database. Defaults to `pubmed`.
        db: Destination database (optional depending on `cmd/linkname`).
        options: Optional endpoint params such as `query_key`, `WebEnv`, `linkname`,
            `cmd`, `term`, `holding` plus transport overrides.

    Returns:
        Raw response text from `elink.fcgi`.

    Raises:
        ValueError: If neither `ids` nor history parameters are provided, or `dbfrom` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await elink(ids=[12345], db="pmc", options={"cmd": "neighbor"})
    """
    if not dbfrom or not dbfrom.strip():
        raise ValueError("dbfrom is required")

    normalized_ids = _normalize_ids(ids)
    opts = dict(options or {})
    has_history = bool(opts.get("query_key")) and bool(opts.get("WebEnv"))
    if not normalized_ids and not has_history:
        raise ValueError("provide ids or options with query_key and WebEnv")

    params: dict[str, Any] = {"dbfrom": dbfrom.strip()}
    if db and db.strip():
        params["db"] = db.strip()
    if normalized_ids:
        params["id"] = normalized_ids

    return await _request("elink.fcgi", params=params, options=opts)


async def egquery(term: str, options: dict[str, Any] | None = None) -> str:
    """Run a global Entrez search and return counts per database.

    Useful to estimate where a topic is concentrated before narrowing to PubMed.

    Args:
        term: Entrez query string.
        options: Optional endpoint params plus transport overrides.

    Returns:
        Raw response text from `egquery.fcgi`.

    Raises:
        ValueError: If `term` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await egquery("diabetes mellitus")
    """
    if not term or not term.strip():
        raise ValueError("term is required")

    return await _request("egquery.fcgi", params={"term": term.strip()}, options=options)


async def espell(term: str, db: str = "pubmed", options: dict[str, Any] | None = None) -> str:
    """Return spelling suggestions for a search term.

    Use this to detect likely misspellings before executing broad literature queries.

    Args:
        term: Query term to check.
        db: Entrez database. Defaults to `pubmed`.
        options: Optional endpoint params plus transport overrides.

    Returns:
        Raw response text from `espell.fcgi`.

    Raises:
        ValueError: If `term` or `db` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await espell("diabtes mellitus")
    """
    if not term or not term.strip():
        raise ValueError("term is required")
    if not db or not db.strip():
        raise ValueError("db is required")

    return await _request(
        "espell.fcgi",
        params={"term": term.strip(), "db": db.strip()},
        options=options,
    )


async def ecitmatch(bdata: str, db: str = "pubmed", options: dict[str, Any] | None = None) -> str:
    """Resolve citation metadata to PMID matches.

    Use this when you have citation fields (journal/year/volume/page/author) and need PMIDs.

    Args:
        bdata: Citation payload in the ECitMatch expected format.
        db: Database name (ECitMatch is typically used with `pubmed`).
        options: Optional endpoint params such as `rettype` plus transport overrides.

    Returns:
        Raw response text from `ecitmatch.cgi`.

    Raises:
        ValueError: If `bdata` or `db` is empty.
        EUtilitiesError: If the request fails.

    Example:
        xml = await ecitmatch("proc natl acad sci u s a|1991|88|7|3248|mann bj|")
    """
    if not bdata or not bdata.strip():
        raise ValueError("bdata is required")
    if not db or not db.strip():
        raise ValueError("db is required")

    opts = dict(options or {})
    opts.setdefault("rettype", "xml")

    return await _request(
        "ecitmatch.cgi",
        params={"db": db.strip(), "bdata": bdata.strip()},
        options=opts,
    )


__all__ = [
    "BASE_URL",
    "EUtilitiesError",
    "configure",
    "get_config",
    "reset_config",
    "einfo",
    "esearch",
    "epost",
    "esummary",
    "efetch",
    "elink",
    "egquery",
    "espell",
    "ecitmatch",
]
