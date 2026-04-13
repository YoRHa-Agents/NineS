"""Search engine over the knowledge index.

``SearchEngine`` wraps ``KnowledgeIndex`` and returns ``SearchResult`` objects
with score and contextual snippet.

Covers: FR-311.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nines.analyzer.indexer import KnowledgeIndex

if TYPE_CHECKING:
    from nines.core.models import KnowledgeUnit

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search hit with relevance score and snippet."""

    unit_id: str
    score: float
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "unit_id": self.unit_id,
            "score": self.score,
            "snippet": self.snippet,
        }


class SearchEngine:
    """High-level search interface over the knowledge index."""

    def __init__(self, index: KnowledgeIndex | None = None) -> None:
        """Initialize search engine."""
        self._index = index or KnowledgeIndex()

    @property
    def index(self) -> KnowledgeIndex:
        """Return the underlying knowledge index."""
        return self._index

    def add_unit(self, unit: KnowledgeUnit) -> None:
        """Add unit."""
        self._index.add_unit(unit)

    def build(self) -> None:
        """Build the search index from current units."""
        self._index.build_index()

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """Search the knowledge index and return ranked results with snippets."""
        hits = self._index.query(query, top_k=top_k)
        results: list[SearchResult] = []

        for unit_id, score in hits:
            unit = self._index.get_unit(unit_id)
            snippet = self._extract_snippet(unit, query) if unit else ""
            results.append(SearchResult(
                unit_id=unit_id,
                score=score,
                snippet=snippet,
            ))

        return results

    @staticmethod
    def _extract_snippet(unit: KnowledgeUnit, query: str, max_len: int = 200) -> str:
        """Extract a contextual snippet from the unit content around query terms."""
        content = unit.content
        if not content:
            return ""

        query_lower = query.lower()
        content_lower = content.lower()

        best_pos = content_lower.find(query_lower)
        if best_pos == -1:
            for word in query_lower.split():
                pos = content_lower.find(word)
                if pos != -1:
                    best_pos = pos
                    break

        if best_pos == -1:
            return content[:max_len] + ("..." if len(content) > max_len else "")

        start = max(0, best_pos - max_len // 4)
        end = min(len(content), start + max_len)
        snippet = content[start:end]

        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""
        return f"{prefix}{snippet}{suffix}"
