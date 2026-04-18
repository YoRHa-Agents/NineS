"""Tests for change detection, diff analysis, and collection scheduler."""

from __future__ import annotations

import pytest

from nines.collector.diff import DiffAnalyzer, PaperChanges, RepoChanges
from nines.collector.models import (
    CollectionSnapshot,
    Paper,
    Repository,
)
from nines.collector.scheduler import CollectionScheduler, ScheduledJob
from nines.collector.tracker import ChangeTracker

# ---------------------------------------------------------------------------
# ChangeTracker
# ---------------------------------------------------------------------------


class TestChangeTracker:
    def test_track_creates_bookmark(self) -> None:
        tracker = ChangeTracker()
        bm = tracker.track("github", "repo-1")
        assert bm.source == "github"
        assert bm.entity_id == "repo-1"

    def test_get_bookmark(self) -> None:
        tracker = ChangeTracker()
        tracker.track("github", "repo-1")
        bm = tracker.get_bookmark("github", "repo-1")
        assert bm is not None
        assert bm.entity_id == "repo-1"

    def test_get_bookmark_missing(self) -> None:
        tracker = ChangeTracker()
        assert tracker.get_bookmark("github", "nope") is None

    def test_list_tracked(self) -> None:
        tracker = ChangeTracker()
        tracker.track("github", "repo-1")
        tracker.track("github", "repo-2")
        tracked = tracker.list_tracked("github")
        assert len(tracked) == 2

    def test_untrack(self) -> None:
        tracker = ChangeTracker()
        tracker.track("github", "repo-1")
        assert tracker.untrack("github", "repo-1") is True
        assert tracker.get_bookmark("github", "repo-1") is None

    def test_untrack_missing(self) -> None:
        tracker = ChangeTracker()
        assert tracker.untrack("github", "nope") is False

    def test_detect_additions(self) -> None:
        tracker = ChangeTracker()
        old = CollectionSnapshot(source="gh", items=[])
        new = CollectionSnapshot(
            source="gh",
            items=[{"id": "r1", "name": "repo1"}],
        )
        events = tracker.detect_changes(old, new)
        assert len(events) == 1
        assert events[0].change_type == "addition"
        assert events[0].entity_id == "r1"

    def test_detect_deletions(self) -> None:
        tracker = ChangeTracker()
        old = CollectionSnapshot(
            source="gh",
            items=[{"id": "r1", "name": "repo1"}],
        )
        new = CollectionSnapshot(source="gh", items=[])
        events = tracker.detect_changes(old, new)
        assert len(events) == 1
        assert events[0].change_type == "deletion"

    def test_detect_modifications(self) -> None:
        tracker = ChangeTracker()
        old = CollectionSnapshot(
            source="gh",
            items=[{"id": "r1", "stars": 10}],
        )
        new = CollectionSnapshot(
            source="gh",
            items=[{"id": "r1", "stars": 20}],
        )
        events = tracker.detect_changes(old, new)
        assert len(events) == 1
        assert events[0].change_type == "modification"

    def test_detect_no_changes(self) -> None:
        tracker = ChangeTracker()
        items = [{"id": "r1", "name": "same"}]
        old = CollectionSnapshot(source="gh", items=items)
        new = CollectionSnapshot(source="gh", items=list(items))
        events = tracker.detect_changes(old, new)
        assert events == []

    def test_detect_mixed_changes(self) -> None:
        tracker = ChangeTracker()
        old = CollectionSnapshot(
            source="gh",
            items=[
                {"id": "keep", "val": 1},
                {"id": "modify", "val": 10},
                {"id": "remove", "val": 99},
            ],
        )
        new = CollectionSnapshot(
            source="gh",
            items=[
                {"id": "keep", "val": 1},
                {"id": "modify", "val": 20},
                {"id": "add", "val": 42},
            ],
        )
        events = tracker.detect_changes(old, new)
        types = {e.change_type for e in events}
        assert "addition" in types
        assert "deletion" in types
        assert "modification" in types

    def test_track_with_metadata(self) -> None:
        tracker = ChangeTracker()
        bm = tracker.track("arxiv", "paper-1", metadata={"topic": "ML"})
        assert bm.metadata["topic"] == "ML"


# ---------------------------------------------------------------------------
# DiffAnalyzer
# ---------------------------------------------------------------------------


class TestDiffAnalyzer:
    def test_diff_repos_added(self) -> None:
        old: list[Repository] = []
        new = [Repository(name="new-repo", owner="org")]
        changes = DiffAnalyzer().diff_repos(old, new)
        assert len(changes.added) == 1
        assert changes.removed == []

    def test_diff_repos_removed(self) -> None:
        old = [Repository(name="old-repo", owner="org")]
        new: list[Repository] = []
        changes = DiffAnalyzer().diff_repos(old, new)
        assert len(changes.removed) == 1
        assert changes.added == []

    def test_diff_repos_modified(self) -> None:
        old = [Repository(name="repo", owner="org", stars=10)]
        new = [Repository(name="repo", owner="org", stars=20)]
        changes = DiffAnalyzer().diff_repos(old, new)
        assert len(changes.modified) == 1
        assert changes.modified[0].field_diffs[0].field_name == "stars"

    def test_diff_repos_no_changes(self) -> None:
        repos = [Repository(name="repo", owner="org", stars=10)]
        changes = DiffAnalyzer().diff_repos(repos, list(repos))
        assert changes.total_changes == 0

    def test_diff_papers_added(self) -> None:
        old: list[Paper] = []
        new = [Paper(id="2401.001", title="New Paper")]
        changes = DiffAnalyzer().diff_papers(old, new)
        assert len(changes.added) == 1

    def test_diff_papers_modified(self) -> None:
        old = [Paper(id="2401.001", title="Draft")]
        new = [Paper(id="2401.001", title="Final")]
        changes = DiffAnalyzer().diff_papers(old, new)
        assert len(changes.modified) == 1
        assert changes.modified[0].field_diffs[0].field_name == "title"

    def test_repo_changes_to_dict(self) -> None:
        changes = RepoChanges(added=[Repository(name="r", owner="o")])
        d = changes.to_dict()
        assert d["total_changes"] == 1
        assert len(d["added"]) == 1

    def test_paper_changes_to_dict(self) -> None:
        changes = PaperChanges(removed=[Paper(id="p1")])
        d = changes.to_dict()
        assert d["total_changes"] == 1


# ---------------------------------------------------------------------------
# CollectionScheduler
# ---------------------------------------------------------------------------


class TestCollectionScheduler:
    def test_schedule_creates_job(self) -> None:
        sched = CollectionScheduler()
        job = sched.schedule("github", 3600)
        assert job.source == "github"
        assert job.interval_seconds == 3600

    def test_get_job(self) -> None:
        sched = CollectionScheduler()
        sched.schedule("github", 3600)
        assert sched.get_job("github") is not None
        assert sched.get_job("missing") is None

    def test_list_jobs(self) -> None:
        sched = CollectionScheduler()
        sched.schedule("github", 3600)
        sched.schedule("arxiv", 7200)
        assert len(sched.list_jobs()) == 2

    def test_unschedule(self) -> None:
        sched = CollectionScheduler()
        sched.schedule("github", 3600)
        assert sched.unschedule("github") is True
        assert sched.get_job("github") is None

    def test_unschedule_missing(self) -> None:
        sched = CollectionScheduler()
        assert sched.unschedule("nope") is False

    def test_get_pending_new_job_is_due(self) -> None:
        sched = CollectionScheduler()
        sched.schedule("github", 3600)
        pending = sched.get_pending()
        assert len(pending) == 1

    def test_run_once(self) -> None:
        sched = CollectionScheduler()
        collected = []

        def collector(source: str) -> str:
            collected.append(source)
            return f"collected-{source}"

        sched.schedule("github", 3600, collector=collector)
        result = sched.run_once("github")
        assert result == "collected-github"
        assert len(collected) == 1

        job = sched.get_job("github")
        assert job is not None
        assert job.run_count == 1

    def test_run_once_no_collector_raises(self) -> None:
        from nines.core.errors import CollectorError

        sched = CollectionScheduler()
        sched.schedule("github", 3600)
        with pytest.raises(CollectorError, match="No collector"):
            sched.run_once("github")

    def test_run_once_missing_job_raises(self) -> None:
        from nines.core.errors import CollectorError

        sched = CollectionScheduler()
        with pytest.raises(CollectorError, match="No scheduled job"):
            sched.run_once("nonexistent")

    def test_scheduled_job_to_dict(self) -> None:
        job = ScheduledJob(source="gh", interval_seconds=60)
        d = job.to_dict()
        assert d["source"] == "gh"
        assert d["interval_seconds"] == 60
