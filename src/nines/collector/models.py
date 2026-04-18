"""Data models for the information collection pipeline.

Provides typed dataclasses for GitHub repositories, arXiv papers,
collection snapshots, and change events.  All models include
``to_dict()`` / ``from_dict()`` round-trip serialization consistent
with the core model conventions.

Covers: FR-201–FR-208.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Repository:
    """A GitHub repository with tracked metadata.

    Maps to the ``repositories`` SQLite table.
    """

    id: int | None = None
    name: str = ""
    owner: str = ""
    url: str = ""
    stars: int = 0
    forks: int = 0
    description: str = ""
    language: str = ""
    topics: list[str] = field(default_factory=list)
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "url": self.url,
            "stars": self.stars,
            "forks": self.forks,
            "description": self.description,
            "language": self.language,
            "topics": list(self.topics),
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Repository:
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            owner=data.get("owner", ""),
            url=data.get("url", data.get("html_url", "")),
            stars=data.get("stars", data.get("stargazers_count", 0)),
            forks=data.get("forks", data.get("forks_count", 0)),
            description=data.get("description") or "",
            language=data.get("language") or "",
            topics=data.get("topics", []),
            last_updated=data.get("last_updated", data.get("updated_at", "")),
        )


@dataclass
class Paper:
    """An arXiv paper with metadata.

    Maps to the ``papers`` SQLite table.
    """

    id: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    categories: list[str] = field(default_factory=list)
    published: str = ""
    updated: str = ""
    pdf_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "authors": list(self.authors),
            "abstract": self.abstract,
            "categories": list(self.categories),
            "published": self.published,
            "updated": self.updated,
            "pdf_url": self.pdf_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Paper:
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            authors=data.get("authors", []),
            abstract=data.get("abstract", ""),
            categories=data.get("categories", []),
            published=data.get("published", ""),
            updated=data.get("updated", ""),
            pdf_url=data.get("pdf_url", ""),
        )


@dataclass
class CollectionSnapshot:
    """A point-in-time snapshot of a collection run."""

    source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    items: list[dict[str, Any]] = field(default_factory=list)
    snapshot_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "items": list(self.items),
            "snapshot_id": self.snapshot_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollectionSnapshot:
        """Deserialize from dictionary."""
        return cls(
            source=data.get("source", ""),
            timestamp=data.get("timestamp", ""),
            items=data.get("items", []),
            snapshot_id=data.get("snapshot_id"),
        )


@dataclass
class ChangeEvent:
    """A detected change in a tracked source item."""

    entity_id: str = ""
    change_type: str = ""
    old_value: Any = None
    new_value: Any = None
    detected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entity_id": self.entity_id,
            "change_type": self.change_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeEvent:
        """Deserialize from dictionary."""
        return cls(
            entity_id=data.get("entity_id", ""),
            change_type=data.get("change_type", ""),
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            detected_at=data.get("detected_at", ""),
        )
