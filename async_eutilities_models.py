from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EFetchAuthor(BaseModel):
    """Normalized author fields parsed from PubMed XML."""

    last_name: str | None = None
    fore_name: str | None = None
    initials: str | None = None
    collective_name: str | None = None


class EFetchRecord(BaseModel):
    """Single parsed EFetch record."""

    model_config = ConfigDict(extra="allow")

    pmid: str | None = None
    article_title: str | None = None
    abstract: str | None = None
    journal_title: str | None = None
    publication_date: str | None = None
    authors: list[EFetchAuthor] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


__all__ = ["EFetchAuthor", "EFetchRecord"]
