"""Live evaluators for NineS V2 Collection dimensions (D06–D10).

These evaluators measure the collection subsystem's capabilities:
source coverage (importability of collectors), source freshness,
change detection, data model completeness, and storage throughput
via the SQLite-backed ``DataStore``.

Covers: D06, D07, D08, D09, D10.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC

from nines.iteration.self_eval import DimensionScore

logger = logging.getLogger(__name__)

_CONFIGURED_SOURCES: dict[str, dict[str, str]] = {
    "github": {
        "module": "nines.collector.github",
        "class": "GitHubCollector",
    },
    "arxiv": {
        "module": "nines.collector.arxiv",
        "class": "ArxivCollector",
    },
}

_REPO_EXPECTED_FIELDS = [
    "name",
    "owner",
    "url",
    "stars",
    "forks",
    "description",
    "language",
    "topics",
    "last_updated",
]

_PAPER_EXPECTED_FIELDS = [
    "id",
    "title",
    "authors",
    "abstract",
    "categories",
    "published",
    "updated",
    "pdf_url",
]


# ---------------------------------------------------------------------------
# D06: Source Coverage
# ---------------------------------------------------------------------------


class SourceCoverageEvaluator:
    """D06: Measures how many configured collector sources are active.

    For each configured source (github, arxiv), checks whether the
    collector class can be imported and has the required ``search``
    and ``fetch`` async methods.

    Score = active_sources / configured_sources.
    """

    def evaluate(self) -> DimensionScore:
        """Enumerate configured sources and check importability."""
        import importlib

        total = len(_CONFIGURED_SOURCES)
        active = 0
        details: dict[str, dict[str, bool]] = {}

        for source_name, spec in _CONFIGURED_SOURCES.items():
            result: dict[str, bool] = {
                "importable": False,
                "has_search": False,
                "has_fetch": False,
            }
            try:
                mod = importlib.import_module(spec["module"])
                cls = getattr(mod, spec["class"])
                result["importable"] = True
                result["has_search"] = callable(getattr(cls, "search", None))
                result["has_fetch"] = callable(getattr(cls, "fetch", None))
            except Exception as exc:
                logger.warning(
                    "Source '%s' not available: %s",
                    source_name,
                    exc,
                )

            if all(result.values()):
                active += 1
            details[source_name] = result

        score = active / total if total > 0 else 0.0

        return DimensionScore(
            name="source_coverage",
            value=round(score, 4),
            max_value=1.0,
            metadata={
                "configured_sources": total,
                "active_sources": active,
                "details": details,
            },
        )


# ---------------------------------------------------------------------------
# D07: Source Freshness
# ---------------------------------------------------------------------------


class SourceFreshnessEvaluator:
    """D07: Measures whether collection sources provide fresh data.

    Creates an in-memory DataStore, saves a synthetic repo with a
    recent timestamp, then checks that the stored timestamp is within
    the configured staleness window (default 30 days).

    Score = fresh_sources / total_sources.
    """

    _STALENESS_DAYS = 30

    def evaluate(self) -> DimensionScore:
        try:
            from datetime import datetime, timedelta

            from nines.collector.models import Repository
            from nines.collector.store import DataStore
        except Exception as exc:
            logger.error("Cannot import collection components: %s", exc)
            return DimensionScore(
                name="source_freshness",
                value=0.0,
                max_value=1.0,
                metadata={"error": str(exc)},
            )

        store = None
        try:
            store = DataStore(db_path=":memory:")
            now = datetime.now(UTC)
            fresh_ts = (now - timedelta(days=1)).isoformat()
            stale_ts = (now - timedelta(days=60)).isoformat()

            repos = [
                Repository(
                    name="fresh-repo",
                    owner="test",
                    url="https://github.com/test/fresh",
                    stars=10,
                    forks=1,
                    description="Fresh",
                    language="Python",
                    topics=["test"],
                    last_updated=fresh_ts,
                ),
                Repository(
                    name="stale-repo",
                    owner="test",
                    url="https://github.com/test/stale",
                    stars=5,
                    forks=0,
                    description="Stale",
                    language="Python",
                    topics=["test"],
                    last_updated=stale_ts,
                ),
            ]
            store.save_repos(repos)
            retrieved = store.get_repos()

            cutoff = now - timedelta(days=self._STALENESS_DAYS)
            fresh_count = 0
            for repo in retrieved:
                try:
                    ts_str = repo.last_updated.replace("Z", "+00:00") if repo.last_updated else ""
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str)
                        if ts >= cutoff:
                            fresh_count += 1
                except (ValueError, AttributeError):
                    pass

            total = len(retrieved)
            score = fresh_count / total if total > 0 else 0.0

            return DimensionScore(
                name="source_freshness",
                value=round(score, 4),
                max_value=1.0,
                metadata={
                    "fresh_count": fresh_count,
                    "total": total,
                    "staleness_days": self._STALENESS_DAYS,
                },
            )
        except Exception as exc:
            logger.error(
                "SourceFreshnessEvaluator failed: %s",
                exc,
                exc_info=True,
            )
            return DimensionScore(
                name="source_freshness",
                value=0.0,
                max_value=1.0,
                metadata={"error": str(exc)},
            )
        finally:
            if store is not None:
                store.close()


# ---------------------------------------------------------------------------
# D08: Change Detection
# ---------------------------------------------------------------------------


class ChangeDetectionEvaluator:
    """D08: Measures whether the collection system can detect data changes.

    Creates an in-memory DataStore, saves repos, updates one, re-saves,
    and verifies the update is reflected on retrieval.

    Score = 1.0 if change detected, 0.0 otherwise.
    """

    def evaluate(self) -> DimensionScore:
        try:
            from nines.collector.models import Repository
            from nines.collector.store import DataStore
        except Exception as exc:
            logger.error("Cannot import collection components: %s", exc)
            return DimensionScore(
                name="change_detection",
                value=0.0,
                max_value=1.0,
                metadata={"error": str(exc)},
            )

        store = None
        try:
            store = DataStore(db_path=":memory:")
            original = Repository(
                name="change-test",
                owner="test",
                url="https://github.com/test/change",
                stars=10,
                forks=1,
                description="Original",
                language="Python",
                topics=["test"],
                last_updated="2025-01-01T00:00:00Z",
            )
            store.save_repos([original])

            updated = Repository(
                name="change-test",
                owner="test",
                url="https://github.com/test/change",
                stars=20,
                forks=5,
                description="Updated description",
                language="Python",
                topics=["test", "updated"],
                last_updated="2025-06-01T00:00:00Z",
            )
            store.save_repos([updated])

            retrieved = store.get_repos()
            change_detected = False
            for repo in retrieved:
                if repo.name == "change-test":
                    change_detected = repo.stars == 20 and repo.description == "Updated description"
                    break

            score = 1.0 if change_detected else 0.0
            return DimensionScore(
                name="change_detection",
                value=score,
                max_value=1.0,
                metadata={"change_detected": change_detected},
            )
        except Exception as exc:
            logger.error(
                "ChangeDetectionEvaluator failed: %s",
                exc,
                exc_info=True,
            )
            return DimensionScore(
                name="change_detection",
                value=0.0,
                max_value=1.0,
                metadata={"error": str(exc)},
            )
        finally:
            if store is not None:
                store.close()


# ---------------------------------------------------------------------------
# D09: Data Completeness
# ---------------------------------------------------------------------------


class DataCompletenessEvaluator:
    """D09: Measures schema completeness of collector data models.

    Imports ``Repository`` and ``Paper``, creates fully-populated
    sample instances, and checks that the expected fields exist on
    each model and that round-trip ``to_dict`` / ``from_dict``
    preserves them.

    Score = valid_schema_fields / total_expected_fields.
    """

    def evaluate(self) -> DimensionScore:
        """Check model schemas and round-trip serialization."""
        try:
            from nines.collector.models import Paper, Repository
        except Exception as exc:
            logger.error("Cannot import collector models: %s", exc)
            return DimensionScore(
                name="data_completeness",
                value=0.0,
                max_value=1.0,
                metadata={"error": str(exc)},
            )

        valid = 0
        total = len(_REPO_EXPECTED_FIELDS) + len(_PAPER_EXPECTED_FIELDS)
        field_details: dict[str, bool] = {}

        repo = Repository(
            name="test-repo",
            owner="test-owner",
            url="https://github.com/test/repo",
            stars=42,
            forks=7,
            description="A test repository",
            language="Python",
            topics=["testing", "ci"],
            last_updated="2025-01-01T00:00:00Z",
        )
        repo_dict = repo.to_dict()
        repo_rt = Repository.from_dict(repo_dict)

        for f in _REPO_EXPECTED_FIELDS:
            key = f"repo.{f}"
            has_attr = hasattr(repo_rt, f)
            non_empty = bool(getattr(repo_rt, f, None)) if has_attr else False
            ok = has_attr and non_empty
            field_details[key] = ok
            if ok:
                valid += 1

        paper = Paper(
            id="2401.00001",
            title="Test Paper",
            authors=["Author A", "Author B"],
            abstract="This is a test abstract.",
            categories=["cs.AI", "cs.SE"],
            published="2025-01-01",
            updated="2025-01-02",
            pdf_url="https://arxiv.org/pdf/2401.00001",
        )
        paper_dict = paper.to_dict()
        paper_rt = Paper.from_dict(paper_dict)

        for f in _PAPER_EXPECTED_FIELDS:
            key = f"paper.{f}"
            has_attr = hasattr(paper_rt, f)
            non_empty = bool(getattr(paper_rt, f, None)) if has_attr else False
            ok = has_attr and non_empty
            field_details[key] = ok
            if ok:
                valid += 1

        score = valid / total if total > 0 else 0.0

        return DimensionScore(
            name="data_completeness",
            value=round(score, 4),
            max_value=1.0,
            metadata={
                "valid_fields": valid,
                "total_fields": total,
                "field_details": field_details,
            },
        )


# ---------------------------------------------------------------------------
# D10: Collection Throughput
# ---------------------------------------------------------------------------


class CollectionThroughputEvaluator:
    """D10: Measures write/read throughput of the SQLite DataStore.

    Creates an in-memory ``DataStore``, inserts N synthetic
    ``Repository`` objects, queries them back, and scores based on
    elapsed time.  No network access required.

    Score = 1.0 - min(elapsed_seconds, 5.0) / 5.0.
    """

    _BATCH_SIZE = 200

    def evaluate(self) -> DimensionScore:
        """Run throughput benchmark against an in-memory DataStore."""
        try:
            from nines.collector.models import Repository
            from nines.collector.store import DataStore
        except Exception as exc:
            logger.error("Cannot import store components: %s", exc)
            return DimensionScore(
                name="collection_throughput",
                value=0.0,
                max_value=1.0,
                metadata={"error": str(exc)},
            )

        store = None
        try:
            store = DataStore(db_path=":memory:")
            repos = [
                Repository(
                    name=f"repo-{i}",
                    owner=f"owner-{i % 10}",
                    url=f"https://github.com/owner-{i % 10}/repo-{i}",
                    stars=i * 10,
                    forks=i,
                    description=f"Synthetic repository {i}",
                    language="Python",
                    topics=["bench", "test"],
                    last_updated="2025-01-01T00:00:00Z",
                )
                for i in range(self._BATCH_SIZE)
            ]

            start = time.monotonic()
            store.save_repos(repos)
            retrieved = store.get_repos()
            elapsed = time.monotonic() - start

            score = 1.0 - min(elapsed, 5.0) / 5.0

            return DimensionScore(
                name="collection_throughput",
                value=round(max(score, 0.0), 4),
                max_value=1.0,
                metadata={
                    "elapsed_seconds": round(elapsed, 4),
                    "inserted": len(repos),
                    "retrieved": len(retrieved),
                    "batch_size": self._BATCH_SIZE,
                },
            )
        except Exception as exc:
            logger.error(
                "CollectionThroughputEvaluator failed: %s",
                exc,
                exc_info=True,
            )
            return DimensionScore(
                name="collection_throughput",
                value=0.0,
                max_value=1.0,
                metadata={"error": str(exc)},
            )
        finally:
            if store is not None:
                store.close()
