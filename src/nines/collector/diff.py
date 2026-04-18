"""Structured diff analysis for collected data.

``DiffAnalyzer`` computes structured diffs between repository and paper
collections, producing ``RepoChanges`` and ``PaperChanges`` summaries.

Covers: FR-211.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.collector.models import Paper, Repository

logger = logging.getLogger(__name__)


@dataclass
class FieldDiff:
    """A single field-level change."""

    field_name: str
    old_value: Any = None
    new_value: Any = None


@dataclass
class EntityDiff:
    """Diff summary for a single entity (repo or paper)."""

    entity_id: str
    change_type: str  # "added", "removed", "modified"
    field_diffs: list[FieldDiff] = field(default_factory=list)


@dataclass
class RepoChanges:
    """Structured diff output for repository collections."""

    added: list[Repository] = field(default_factory=list)
    removed: list[Repository] = field(default_factory=list)
    modified: list[EntityDiff] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Return the total changes."""
        return len(self.added) + len(self.removed) + len(self.modified)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "added": [r.to_dict() for r in self.added],
            "removed": [r.to_dict() for r in self.removed],
            "modified": [
                {
                    "entity_id": m.entity_id,
                    "change_type": m.change_type,
                    "field_diffs": [
                        {
                            "field_name": f.field_name,
                            "old_value": f.old_value,
                            "new_value": f.new_value,
                        }
                        for f in m.field_diffs
                    ],
                }
                for m in self.modified
            ],
            "total_changes": self.total_changes,
        }


@dataclass
class PaperChanges:
    """Structured diff output for paper collections."""

    added: list[Paper] = field(default_factory=list)
    removed: list[Paper] = field(default_factory=list)
    modified: list[EntityDiff] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Return the total changes."""
        return len(self.added) + len(self.removed) + len(self.modified)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "added": [p.to_dict() for p in self.added],
            "removed": [p.to_dict() for p in self.removed],
            "modified": [
                {
                    "entity_id": m.entity_id,
                    "change_type": m.change_type,
                    "field_diffs": [
                        {
                            "field_name": f.field_name,
                            "old_value": f.old_value,
                            "new_value": f.new_value,
                        }
                        for f in m.field_diffs
                    ],
                }
                for m in self.modified
            ],
            "total_changes": self.total_changes,
        }


class DiffAnalyzer:
    """Computes structured diffs between old and new collections."""

    REPO_COMPARE_FIELDS = ("stars", "forks", "description", "language", "topics", "last_updated")
    PAPER_COMPARE_FIELDS = ("title", "authors", "abstract", "categories", "updated")

    def diff_repos(self, old: list[Repository], new: list[Repository]) -> RepoChanges:
        """Diff repos."""
        old_by_key = {self._repo_key(r): r for r in old}
        new_by_key = {self._repo_key(r): r for r in new}

        old_keys = set(old_by_key.keys())
        new_keys = set(new_by_key.keys())

        added = [new_by_key[k] for k in sorted(new_keys - old_keys)]
        removed = [old_by_key[k] for k in sorted(old_keys - new_keys)]

        modified: list[EntityDiff] = []
        for key in sorted(old_keys & new_keys):
            diffs = self._compare_fields(
                old_by_key[key].to_dict(),
                new_by_key[key].to_dict(),
                self.REPO_COMPARE_FIELDS,
            )
            if diffs:
                modified.append(
                    EntityDiff(entity_id=key, change_type="modified", field_diffs=diffs)
                )

        return RepoChanges(added=added, removed=removed, modified=modified)

    def diff_papers(self, old: list[Paper], new: list[Paper]) -> PaperChanges:
        """Diff papers."""
        old_by_id = {p.id: p for p in old}
        new_by_id = {p.id: p for p in new}

        old_ids = set(old_by_id.keys())
        new_ids = set(new_by_id.keys())

        added = [new_by_id[pid] for pid in sorted(new_ids - old_ids)]
        removed = [old_by_id[pid] for pid in sorted(old_ids - new_ids)]

        modified: list[EntityDiff] = []
        for pid in sorted(old_ids & new_ids):
            diffs = self._compare_fields(
                old_by_id[pid].to_dict(),
                new_by_id[pid].to_dict(),
                self.PAPER_COMPARE_FIELDS,
            )
            if diffs:
                modified.append(
                    EntityDiff(entity_id=pid, change_type="modified", field_diffs=diffs)
                )

        return PaperChanges(added=added, removed=removed, modified=modified)

    @staticmethod
    def _repo_key(repo: Repository) -> str:
        """Repo key."""
        return f"{repo.owner}/{repo.name}" if repo.owner else repo.name

    @staticmethod
    def _compare_fields(
        old_dict: dict[str, Any],
        new_dict: dict[str, Any],
        fields: tuple[str, ...],
    ) -> list[FieldDiff]:
        """Compare fields."""
        diffs: list[FieldDiff] = []
        for f in fields:
            old_val = old_dict.get(f)
            new_val = new_dict.get(f)
            if old_val != new_val:
                diffs.append(FieldDiff(field_name=f, old_value=old_val, new_value=new_val))
        return diffs
