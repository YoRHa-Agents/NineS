"""SQLite-backed storage for collected entities.

Provides CRUD operations for repositories, papers, and collection
snapshots.  Uses ``sqlite3`` directly (no ORM) with parameterized
queries for safety.

Covers: FR-205.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import TYPE_CHECKING, Any

from nines.collector.models import (
    CollectionSnapshot,
    Paper,
    Repository,
)
from nines.core.errors import CollectorError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS repositories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    owner           TEXT    NOT NULL,
    url             TEXT    NOT NULL,
    stars           INTEGER DEFAULT 0,
    forks           INTEGER DEFAULT 0,
    description     TEXT    DEFAULT '',
    language        TEXT    DEFAULT '',
    topics          TEXT    DEFAULT '[]',
    last_updated    TEXT    DEFAULT '',
    UNIQUE(owner, name)
);

CREATE TABLE IF NOT EXISTS papers (
    id              TEXT    PRIMARY KEY,
    title           TEXT    NOT NULL,
    authors         TEXT    DEFAULT '[]',
    abstract        TEXT    DEFAULT '',
    categories      TEXT    DEFAULT '[]',
    published       TEXT    DEFAULT '',
    updated         TEXT    DEFAULT '',
    pdf_url         TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS collection_snapshots (
    snapshot_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    items           TEXT    DEFAULT '[]'
);
"""


class DataStore:
    """SQLite storage layer for the collector module.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Use ``":memory:"`` for an
        in-memory database (useful for tests).
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """Initialize data store."""
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self.init_db()

    @property
    def _connection(self) -> sqlite3.Connection:
        """Return a database connection, creating one if needed."""
        if self._conn is None:
            raise CollectorError("DataStore is closed")
        return self._conn

    def init_db(self) -> None:
        """Open the database and apply the schema."""
        try:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise CollectorError(
                f"Failed to initialize database at {self._db_path}",
                cause=exc,
            ) from exc

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Repository CRUD
    # ------------------------------------------------------------------

    def save_repos(self, repos: list[Repository]) -> None:
        """Insert or update a batch of repositories."""
        conn = self._connection
        params = [
            (
                repo.name,
                repo.owner,
                repo.url,
                repo.stars,
                repo.forks,
                repo.description,
                repo.language,
                json.dumps(repo.topics),
                repo.last_updated,
            )
            for repo in repos
        ]
        try:
            conn.executemany(
                """
                INSERT INTO repositories (name, owner, url, stars, forks,
                                          description, language, topics, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner, name) DO UPDATE SET
                    url          = excluded.url,
                    stars        = excluded.stars,
                    forks        = excluded.forks,
                    description  = excluded.description,
                    language     = excluded.language,
                    topics       = excluded.topics,
                    last_updated = excluded.last_updated
                """,
                params,
            )
            conn.commit()
        except sqlite3.Error as exc:
            raise CollectorError(
                f"Failed to save {len(repos)} repositories",
                cause=exc,
            ) from exc

    def get_repos(self, filters: dict[str, Any] | None = None) -> list[Repository]:
        """Retrieve repositories matching optional *filters*.

        Supported filter keys: ``language``, ``min_stars``, ``owner``.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if filters:
            if "language" in filters:
                clauses.append("language = ?")
                params.append(filters["language"])
            if "min_stars" in filters:
                clauses.append("stars >= ?")
                params.append(filters["min_stars"])
            if "owner" in filters:
                clauses.append("owner = ?")
                params.append(filters["owner"])

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM repositories {where} ORDER BY stars DESC"

        try:
            rows = self._connection.execute(query, params).fetchall()
        except sqlite3.Error as exc:
            raise CollectorError("Failed to query repositories", cause=exc) from exc

        return [self._row_to_repo(row) for row in rows]

    # ------------------------------------------------------------------
    # Paper CRUD
    # ------------------------------------------------------------------

    def save_papers(self, papers: list[Paper]) -> None:
        """Insert or update a batch of papers."""
        conn = self._connection
        params = [
            (
                paper.id,
                paper.title,
                json.dumps(paper.authors),
                paper.abstract,
                json.dumps(paper.categories),
                paper.published,
                paper.updated,
                paper.pdf_url,
            )
            for paper in papers
        ]
        try:
            conn.executemany(
                """
                INSERT INTO papers (id, title, authors, abstract,
                                    categories, published, updated, pdf_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title      = excluded.title,
                    authors    = excluded.authors,
                    abstract   = excluded.abstract,
                    categories = excluded.categories,
                    published  = excluded.published,
                    updated    = excluded.updated,
                    pdf_url    = excluded.pdf_url
                """,
                params,
            )
            conn.commit()
        except sqlite3.Error as exc:
            raise CollectorError(
                f"Failed to save {len(papers)} papers",
                cause=exc,
            ) from exc

    def get_papers(self, filters: dict[str, Any] | None = None) -> list[Paper]:
        """Retrieve papers matching optional *filters*.

        Supported filter keys: ``category``, ``author``.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if filters:
            if "category" in filters:
                clauses.append("categories LIKE ?")
                params.append(f"%{filters['category']}%")
            if "author" in filters:
                clauses.append("authors LIKE ?")
                params.append(f"%{filters['author']}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM papers {where} ORDER BY published DESC"

        try:
            rows = self._connection.execute(query, params).fetchall()
        except sqlite3.Error as exc:
            raise CollectorError("Failed to query papers", cause=exc) from exc

        return [self._row_to_paper(row) for row in rows]

    # ------------------------------------------------------------------
    # Snapshot operations
    # ------------------------------------------------------------------

    def save_snapshot(self, snapshot: CollectionSnapshot) -> int:
        """Persist a collection snapshot.  Returns the auto-generated ID."""
        conn = self._connection
        try:
            cur = conn.execute(
                """
                INSERT INTO collection_snapshots (source, timestamp, items)
                VALUES (?, ?, ?)
                """,
                (
                    snapshot.source,
                    snapshot.timestamp,
                    json.dumps(snapshot.items),
                ),
            )
            conn.commit()
            return cur.lastrowid or 0
        except sqlite3.Error as exc:
            raise CollectorError(
                "Failed to save collection snapshot",
                cause=exc,
            ) from exc

    def get_snapshots(
        self, source: str | None = None, limit: int = 20
    ) -> list[CollectionSnapshot]:
        """Retrieve snapshots, most recent first."""
        if source:
            rows = self._connection.execute(
                "SELECT * FROM collection_snapshots WHERE source = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM collection_snapshots ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_snapshot(row) for row in rows]

    # ------------------------------------------------------------------
    # Row converters
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_repo(row: sqlite3.Row) -> Repository:
        """Row to repo."""
        topics_raw = row["topics"]
        try:
            topics = json.loads(topics_raw) if topics_raw else []
        except (json.JSONDecodeError, TypeError):
            logger.warning("Malformed topics JSON for repo id=%s: %r", row["id"], topics_raw)
            topics = []
        return Repository(
            id=row["id"],
            name=row["name"],
            owner=row["owner"],
            url=row["url"],
            stars=row["stars"],
            forks=row["forks"],
            description=row["description"],
            language=row["language"],
            topics=topics,
            last_updated=row["last_updated"],
        )

    @staticmethod
    def _row_to_paper(row: sqlite3.Row) -> Paper:
        """Row to paper."""
        def _json_list(raw: Any, field_name: str = "") -> list[str]:
            """Json list."""
            if not raw:
                return []
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Malformed JSON in paper id=%s field=%s: %r",
                    row["id"], field_name, raw,
                )
                return []

        return Paper(
            id=row["id"],
            title=row["title"],
            authors=_json_list(row["authors"], "authors"),
            abstract=row["abstract"],
            categories=_json_list(row["categories"], "categories"),
            published=row["published"],
            updated=row["updated"],
            pdf_url=row["pdf_url"],
        )

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> CollectionSnapshot:
        """Row to snapshot."""
        items_raw = row["items"]
        try:
            items = json.loads(items_raw) if items_raw else []
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Malformed items JSON for snapshot id=%s: %r",
                row["snapshot_id"], items_raw,
            )
            items = []
        return CollectionSnapshot(
            snapshot_id=row["snapshot_id"],
            source=row["source"],
            timestamp=row["timestamp"],
            items=items,
        )
