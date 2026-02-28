from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from async_eutilities_models import EFetchAuthor, EFetchRecord

RequestOptions = dict[str, Any]


class XMLParseError(Exception):
    """Raised when an E-utilities XML payload cannot be parsed."""


def build_default_config(base_url: str) -> RequestOptions:
    return {
        "api_key": os.getenv("NCBI_API_KEY"),
        "email": None,
        "tool": None,
        "base_url": base_url,
        "timeout": 30.0,
        "max_retries": 2,
        "retry_backoff": 0.5,
    }


def require_non_empty(value: str | int | None, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required")
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def normalize_ids(ids: Iterable[str | int] | str | int | None) -> str | None:
    if ids is None:
        return None
    if isinstance(ids, (str, int)):
        normalized = str(ids).strip()
        return normalized or None

    normalized_values = [str(value).strip() for value in ids if str(value).strip()]
    return ",".join(normalized_values) if normalized_values else None


def clean_params(params: RequestOptions) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "y" if value else "n"
        else:
            cleaned[key] = str(value)
    return cleaned


def merge_call_config(current_config: RequestOptions, options: RequestOptions | None) -> tuple[RequestOptions, RequestOptions]:
    runtime_options = dict(options or {})
    config = deepcopy(current_config)

    for key in ("api_key", "email", "tool", "base_url", "timeout", "max_retries", "retry_backoff"):
        if key in runtime_options:
            config[key] = runtime_options.pop(key)

    return config, runtime_options


def validate_transport_config(config: RequestOptions) -> None:
    if float(config["timeout"]) <= 0:
        raise ValueError("timeout must be greater than 0")
    if int(config["max_retries"]) < 0:
        raise ValueError("max_retries must be >= 0")
    if float(config["retry_backoff"]) < 0:
        raise ValueError("retry_backoff must be >= 0")


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _find_text(element: ET.Element, xpath: str) -> str | None:
    node = element.find(xpath)
    if node is None:
        return None
    value = (node.text or "").strip()
    return value or None


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

    title_raw = article_elem.findtext(".//Article/ArticleTitle", default="")
    normalized_title = " ".join(title_raw.split()) or None

    return EFetchRecord(
        pmid=_find_text(article_elem, ".//MedlineCitation/PMID") or _find_text(article_elem, ".//PMID"),
        article_title=normalized_title,
        abstract=abstract,
        journal_title=_find_text(article_elem, ".//Article/Journal/Title"),
        publication_date=_extract_publication_date(article_elem),
        authors=_extract_authors(article_elem),
        data=_xml_element_to_dict(article_elem),
    )


def _parse_xml_root(xml_text: str, source: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise XMLParseError(f"{source} XML parsing failed: {exc}") from exc


def parse_esearch_pmids(xml_text: str) -> list[str]:
    root = _parse_xml_root(xml_text, "ESearch")
    return [node.text.strip() for node in root.findall(".//IdList/Id") if node.text and node.text.strip()]


def parse_efetch_record(xml_text: str, db: str) -> EFetchRecord:
    root = _parse_xml_root(xml_text, "EFetch")

    if db.lower() == "pubmed":
        article = root.find(".//PubmedArticle")
        if article is None:
            raise XMLParseError("No PubmedArticle found in EFetch response")
        return _build_pubmed_record(article)

    first_node = next(iter(root), None)
    if first_node is None:
        raise XMLParseError("No records found in EFetch response")

    return EFetchRecord(data={_strip_namespace(first_node.tag): _xml_element_to_dict(first_node)})


__all__ = [
    "RequestOptions",
    "XMLParseError",
    "build_default_config",
    "clean_params",
    "merge_call_config",
    "normalize_ids",
    "parse_efetch_record",
    "parse_esearch_pmids",
    "require_non_empty",
    "validate_transport_config",
]
