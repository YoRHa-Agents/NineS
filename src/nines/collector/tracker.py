"""Change tracking for collected data sources.

``ChangeTracker`` records bookmarks for tracked entities and detects
additions, modifications, and deletions between snapshots.

Covers: FR-209, FR-210.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from nines.collector.models import ChangeEvent, CollectionSnapshot

logger = logging.getLogger(__name__)


@dataclass
class Bookmark:
    """A tracking bookmark for a source entity."""

    source: str
    entity_id: str
    tracked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_seen: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ChangeTracker:
    """Tracks entities across sources and detects changes between snapshots."""

    def __init__(self) -> None:
        self._bookmarks: dict[str, dict[str, Bookmark]] = {}

    def track(self, source: str, entity_id: str, metadata: dict[str, Any] | None = None) -> Bookmark:
        """Record a tracking bookmark for a source entity."""
        if source not in self._bookmarks:
            self._bookmarks[source] = {}

        now = datetime.now(timezone.utc).isoformat()
        bookmark = Bookmark(
            source=source,
            entity_id=entity_id,
            tracked_at=now,
            last_seen=now,
            metadata=metadata or {},
        )
        self._bookmarks[source][entity_id] = bookmark
        return bookmark

    def get_bookmark(self, source: str, entity_id: str) -> Bookmark | None:
        return self._bookmarks.get(source, {}).get(entity_id)

    def list_tracked(self, source: str) -> list[Bookmark]:
        return list(self._bookmarks.get(source, {}).values())

    def untrack(self, source: str, entity_id: str) -> bool:
        source_bookmarks = self._bookmarks.get(source, {})
        if entity_id in source_bookmarks:
            del source_bookmarks[entity_id]
            return True
        return False

    def detect_changes(
        self,
        old_snapshot: CollectionSnapshot,
        new_snapshot: CollectionSnapshot,
    ) -> list[ChangeEvent]:
        """Compare two snapshots and return a list of change events.

        Detects additions, deletions, and modifications based on item ``id``
        fields within each snapshot's ``items`` list.
        """
        old_by_id = self._index_items(old_snapshot.items)
        new_by_id = self._index_items(new_snapshot.items)

        old_ids = set(old_by_id.keys())
        new_ids = set(new_by_id.keys())

        events: list[ChangeEvent] = []

        for eid in sorted(new_ids - old_ids):
            events.append(ChangeEvent(
                entity_id=eid,
                change_type="addition",
                old_value=None,
                new_value=new_by_id[eid],
            ))

        for eid in sorted(old_ids - new_ids):
            events.append(ChangeEvent(
                entity_id=eid,
                change_type="deletion",
                old_value=old_by_id[eid],
                new_value=None,
            ))

        for eid in sorted(old_ids & new_ids):
            if old_by_id[eid] != new_by_id[eid]:
                events.append(ChangeEvent(
                    entity_id=eid,
                    change_type="modification",
                    old_value=old_by_id[eid],
                    new_value=new_by_id[eid],
                ))

        return events

    @staticmethod
    def _index_items(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Build a lookup from item id to item dict."""
        index: dict[str, dict[str, Any]] = {}
        for item in items:
            item_id = str(item.get("id", item.get("name", "")))
            if item_id:
                index[item_id] = item
        return index
