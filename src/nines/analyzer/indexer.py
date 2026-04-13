"""Keyword-based knowledge indexing with TF-IDF-like scoring.

``KnowledgeIndex`` builds an inverted index over ``KnowledgeUnit`` content,
computing term-frequency / inverse-document-frequency weights for keyword
search.

Covers: FR-310.
"""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nines.core.models import KnowledgeUnit

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


def _tokenize(text: str) -> list[str]:
    """Extract lowercased tokens from text."""
    return [m.group().lower() for m in _WORD_RE.finditer(text)]


@dataclass
class _TermEntry:
    """Inverted-index entry for a single term in a single document."""

    unit_id: str
    tf: float = 0.0


class KnowledgeIndex:
    """In-memory inverted index over KnowledgeUnit content with TF-IDF scoring."""

    def __init__(self) -> None:
        """Initialize knowledge index."""
        self._units: dict[str, KnowledgeUnit] = {}
        self._inverted: dict[str, list[_TermEntry]] = defaultdict(list)
        self._doc_count: int = 0
        self._idf_cache: dict[str, float] = {}
        self._built: bool = False

    def add_unit(self, unit: KnowledgeUnit) -> None:
        """Add a knowledge unit to the index. Must call ``build_index()`` afterwards."""
        self._units[unit.id] = unit
        self._built = False

    def remove_unit(self, unit_id: str) -> bool:
        """Remove unit."""
        if unit_id in self._units:
            del self._units[unit_id]
            self._built = False
            return True
        return False

    def get_unit(self, unit_id: str) -> KnowledgeUnit | None:
        """Return unit."""
        return self._units.get(unit_id)

    def list_units(self) -> list[KnowledgeUnit]:
        """List units."""
        return list(self._units.values())

    @property
    def size(self) -> int:
        """Return the number of indexed units."""
        return len(self._units)

    def build_index(self) -> None:
        """Rebuild the inverted index and IDF cache from all stored units."""
        self._inverted.clear()
        self._idf_cache.clear()
        self._doc_count = len(self._units)

        if self._doc_count == 0:
            self._built = True
            return

        for unit in self._units.values():
            meta_tags = unit.metadata.get("tags", "")
            meta_doc = unit.metadata.get("docstring", "")
            text = f"{unit.content} {unit.unit_type} {unit.source} {meta_tags} {meta_doc}"
            tokens = _tokenize(text)
            if not tokens:
                continue

            freq: dict[str, int] = defaultdict(int)
            for tok in tokens:
                freq[tok] += 1

            max_freq = max(freq.values())
            for term, count in freq.items():
                tf = 0.5 + 0.5 * (count / max_freq)
                self._inverted[term].append(_TermEntry(unit_id=unit.id, tf=tf))

        for term, entries in self._inverted.items():
            df = len(entries)
            self._idf_cache[term] = math.log(1 + self._doc_count / df)

        self._built = True

    def query(self, query_str: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search the index and return ``(unit_id, score)`` pairs sorted by relevance."""
        if not self._built:
            self.build_index()

        tokens = _tokenize(query_str)
        if not tokens:
            return []

        scores: dict[str, float] = defaultdict(float)
        for term in tokens:
            idf = self._idf_cache.get(term, 0.0)
            for entry in self._inverted.get(term, []):
                scores[entry.unit_id] += entry.tf * idf

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
