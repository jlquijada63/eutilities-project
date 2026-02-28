from __future__ import annotations

import asyncio
import os
from copy import deepcopy
from typing import Any, Iterable
from xml.etree import ElementTree as ET

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

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


class EFetchAuthor(BaseModel):
    """Normalized author fields parsed from PubMed XML."""

    last_name: str | None = None
    fore_name: str | None = None
    initials: str | None = None
    collective_name: str | None = None


class EFetchRecord(BaseModel):
    """One record parsed from an EFetch XML response."""

    model_config = ConfigDict(extra="allow")

    pmid: str | None = None
    article_title: str | None = None
    abstract: str | None = None
    journal_title: str | None = None
    publication_date: str | None = None
    authors: list[EFetchAuthor] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


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
    """Set global request defaults used by all E-utilities functions."""
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
    values = [str(value).strip() for value in ids if str(value).strip()]
    return ",".join(values) if values else None


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
    """Execute a request against one E-utilities endpoint with retry logic."""
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


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _xml_element_to_dict(element: ET.Element) -> Any:
    children = list(element)
    text = (element.text or "").strip()

    if not children:
        if element.attrib:
            payload: dict[str, Any] = {"_attributes": dict(element.attrib)}
            if text:
                payload["_text"] = text
            return payload
        return text

    payload: dict[str, Any] = {}
    if element.attrib:
        payload["_attributes"] = dict(element.attrib)
    if text:
        payload["_text"] = text

    for child in children:
        child_tag = _strip_namespace(child.tag)
        child_value = _xml_element_to_dict(child)
        if child_tag in payload:
            existing = payload[child_tag]
            if isinstance(existing, list):
                existing.append(child_value)
            else:
                payload[child_tag] = [existing, child_value]
        else:
            payload[child_tag] = child_value

    return payload


def _find_text(element: ET.Element, xpath: str) -> str | None:
    node = element.find(xpath)
    if node is None:
        return None
    value = (node.text or "").strip()
    return value or None


def _extract_publication_date(article_elem: ET.Element) -> str | None:
    pub_date = article_elem.find(".//Article/Journal/JournalIssue/PubDate")
    if pub_date is None:
        return None

    year = _find_text(pub_date, "./Year")
    month = _find_text(pub_date, "./Month")
    day = _find_text(pub_date, "./Day")
    medline_date = _find_text(pub_date, "./MedlineDate")

    if year and month and day:
        return f"{year}-{month}-{day}"
    if year and month:
        return f"{year}-{month}"
    if year:
        return year
    return medline_date


def _extract_authors(article_elem: ET.Element) -> list[EFetchAuthor]:
    authors: list[EFetchAuthor] = []
    for author_elem in article_elem.findall(".//Article/AuthorList/Author"):
        authors.append(
            EFetchAuthor(
                last_name=_find_text(author_elem, "./LastName"),
                fore_name=_find_text(author_elem, "./ForeName"),
                initials=_find_text(author_elem, "./Initials"),
                collective_name=_find_text(author_elem, "./CollectiveName"),
            )
        )
    return authors


def _build_pubmed_record(article_elem: ET.Element) -> EFetchRecord:
    abstract_nodes = article_elem.findall(".//Article/Abstract/AbstractText")
    abstract_parts = [" ".join(node.itertext()).strip() for node in abstract_nodes]
    abstract = " ".join(part for part in abstract_parts if part).strip() or None

    return EFetchRecord(
        pmid=_find_text(article_elem, ".//MedlineCitation/PMID") or _find_text(article_elem, ".//PMID"),
        article_title=" ".join(article_elem.findtext(".//Article/ArticleTitle", default="").split()) or None,
        abstract=abstract,
        journal_title=_find_text(article_elem, ".//Article/Journal/Title"),
        publication_date=_extract_publication_date(article_elem),
        authors=_extract_authors(article_elem),
        data=_xml_element_to_dict(article_elem),
    )


def _parse_efetch_record(xml_text: str, db: str) -> EFetchRecord:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise EUtilitiesError(f"EFetch XML parsing failed: {exc}") from exc

    if db.lower() == "pubmed":
        first_article = root.find(".//PubmedArticle")
        if first_article is None:
            raise EUtilitiesError("No PubmedArticle found in EFetch response")
        return _build_pubmed_record(first_article)

    first_node = next(iter(list(root)), None)
    if first_node is None:
        raise EUtilitiesError("No records found in EFetch response")
    return EFetchRecord(data={_strip_namespace(first_node.tag): _xml_element_to_dict(first_node)})


def _parse_esearch_pmids(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise EUtilitiesError(f"ESearch XML parsing failed: {exc}") from exc

    return [node.text.strip() for node in root.findall(".//IdList/Id") if node.text and node.text.strip()]


async def einfo(db: str = "pubmed", options: dict[str, Any] | None = None) -> str:
    """Return metadata and search field information for an Entrez database."""
    if not db or not db.strip():
        raise ValueError("db is required")
    return await _request("einfo.fcgi", params={"db": db.strip()}, options=options)


async def esearch(term: str, db: str = "pubmed", options: dict[str, Any] | None = None) -> list[str]:
    """Search an Entrez database and return only the list of PMIDs."""
    if not term or not term.strip():
        raise ValueError("term is required")
    if not db or not db.strip():
        raise ValueError("db is required")

    xml_text = await _request(
        "esearch.fcgi",
        params={"db": db.strip(), "term": term.strip()},
        options=options,
    )
    return _parse_esearch_pmids(xml_text)


async def epost(ids: str | int | Iterable[str | int], db: str = "pubmed", options: dict[str, Any] | None = None) -> str:
    """Upload IDs to Entrez History server for later chained requests."""
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
    """Fetch document summaries (DocSums) for IDs or a history set."""
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


async def efetch(pmid: str | int, db: str = "pubmed", options: dict[str, Any] | None = None) -> EFetchRecord:
    """Fetch one full record by PMID and return a parsed Pydantic record."""
    if str(pmid).strip() == "":
        raise ValueError("pmid is required")
    if not db or not db.strip():
        raise ValueError("db is required")

    params = {"db": db.strip(), "id": str(pmid).strip(), "retmax": 1}
    xml_text = await _request("efetch.fcgi", params=params, options=dict(options or {}))
    return _parse_efetch_record(xml_text, db.strip())


async def elink(
    ids: str | int | Iterable[str | int] | None = None,
    dbfrom: str = "pubmed",
    db: str | None = None,
    options: dict[str, Any] | None = None,
) -> str:
    """Find linked/related records across Entrez databases."""
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
    """Run a global Entrez search and return counts per database."""
    if not term or not term.strip():
        raise ValueError("term is required")
    return await _request("egquery.fcgi", params={"term": term.strip()}, options=options)


async def espell(term: str, db: str = "pubmed", options: dict[str, Any] | None = None) -> str:
    """Return spelling suggestions for a search term."""
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
    """Resolve citation metadata to PMID matches."""
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
    "EFetchAuthor",
    "EFetchRecord",
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
