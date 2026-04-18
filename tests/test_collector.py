"""Tests for the nines.collector package.

All HTTP interactions are mocked via ``httpx.MockTransport`` so tests
run without network access and without rate-limit delays.
"""

from __future__ import annotations

from typing import Any

import httpx

from nines.collector.arxiv import ArxivCollector, ArxivConfig
from nines.collector.github import GitHubCollector, GitHubConfig
from nines.collector.models import (
    ChangeEvent,
    CollectionSnapshot,
    Paper,
    Repository,
)
from nines.collector.store import DataStore

# ======================================================================
# Helpers
# ======================================================================


def _json_response(data: Any, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        headers={"content-type": "application/json"},
    )


def _text_response(text: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        text=text,
        headers={"content-type": "application/xml"},
    )


SAMPLE_REPO_JSON = {
    "id": 123456,
    "name": "nines",
    "owner": {"login": "testorg"},
    "html_url": "https://github.com/testorg/nines",
    "stargazers_count": 42,
    "forks_count": 7,
    "description": "A multi-vertex evaluation system",
    "language": "Python",
    "topics": ["ai", "evaluation"],
    "updated_at": "2026-04-10T12:00:00Z",
}

SAMPLE_SEARCH_JSON = {
    "total_count": 1,
    "incomplete_results": False,
    "items": [SAMPLE_REPO_JSON],
}

SAMPLE_COMMITS_JSON = [
    {
        "sha": "abc123",
        "commit": {"message": "Initial commit", "author": {"date": "2026-04-10T12:00:00Z"}},
    }
]

SAMPLE_RELEASES_JSON = [
    {
        "tag_name": "v0.1.0",
        "name": "First release",
        "published_at": "2026-04-10T12:00:00Z",
    }
]

SAMPLE_ARXIV_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>Test Paper on AI Agents</title>
    <summary>This paper explores AI agent evaluation.</summary>
    <published>2023-01-15T00:00:00Z</published>
    <updated>2023-01-16T00:00:00Z</updated>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <arxiv:primary_category term="cs.AI" />
    <category term="cs.AI" />
    <category term="cs.SE" />
    <link title="pdf" href="http://arxiv.org/pdf/2301.12345v1" />
  </entry>
</feed>
"""


# ======================================================================
# GitHub tests
# ======================================================================


class TestGitHubSearch:
    """AC: GitHub search returns results."""

    def test_search_repos_returns_repositories(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/search/repositories" in str(request.url)
            return _json_response(SAMPLE_SEARCH_JSON)

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, base_url="https://api.github.com")
        config = GitHubConfig(token="fake-token")
        collector = GitHubCollector(config=config, client=client)

        repos = collector.search_repos("ai agents", per_page=5)

        assert len(repos) == 1
        repo = repos[0]
        assert isinstance(repo, Repository)
        assert repo.name == "nines"
        assert repo.owner == "testorg"
        assert repo.stars == 42
        assert repo.forks == 7
        assert repo.language == "Python"
        assert "ai" in repo.topics

    def test_search_repos_passes_sort_params(self) -> None:
        captured_params: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key in ("q", "sort", "order"):
                val = request.url.params.get(key)
                if val:
                    captured_params[key] = val
            return _json_response(SAMPLE_SEARCH_JSON)

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, base_url="https://api.github.com")
        collector = GitHubCollector(config=GitHubConfig(), client=client)

        collector.search_repos("test", sort="updated", order="asc")

        assert captured_params["sort"] == "updated"
        assert captured_params["order"] == "asc"


class TestGitHubFetchRepo:
    """AC: GitHub fetch returns a single repository."""

    def test_fetch_repo_returns_repository(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/repos/testorg/nines" in str(request.url)
            return _json_response(SAMPLE_REPO_JSON)

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, base_url="https://api.github.com")
        collector = GitHubCollector(config=GitHubConfig(), client=client)

        repo = collector.fetch_repo("testorg", "nines")

        assert isinstance(repo, Repository)
        assert repo.name == "nines"
        assert repo.url == "https://github.com/testorg/nines"
        assert repo.description == "A multi-vertex evaluation system"

    def test_get_commits(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(SAMPLE_COMMITS_JSON)

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, base_url="https://api.github.com")
        collector = GitHubCollector(config=GitHubConfig(), client=client)

        commits = collector.get_commits("testorg", "nines")

        assert len(commits) == 1
        assert commits[0]["sha"] == "abc123"

    def test_get_releases(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(SAMPLE_RELEASES_JSON)

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, base_url="https://api.github.com")
        collector = GitHubCollector(config=GitHubConfig(), client=client)

        releases = collector.get_releases("testorg", "nines")

        assert len(releases) == 1
        assert releases[0]["tag_name"] == "v0.1.0"


# ======================================================================
# arXiv tests
# ======================================================================


class TestArxivSearch:
    """AC: arXiv search works."""

    def test_search_papers_returns_papers(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _text_response(SAMPLE_ARXIV_XML)

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        config = ArxivConfig(
            base_url="http://test.local/api/query",
            delay_seconds=0.0,
        )
        collector = ArxivCollector(config=config, client=client)

        papers = collector.search_papers("ai agents", max_results=5)

        assert len(papers) == 1
        paper = papers[0]
        assert isinstance(paper, Paper)
        assert paper.id == "2301.12345v1"
        assert paper.title == "Test Paper on AI Agents"
        assert "Alice Smith" in paper.authors
        assert "Bob Jones" in paper.authors
        assert "cs.AI" in paper.categories
        assert paper.pdf_url == "http://arxiv.org/pdf/2301.12345v1"

    def test_search_papers_with_categories(self) -> None:
        captured_query: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            q = request.url.params.get("search_query", "")
            captured_query.append(q)
            return _text_response(SAMPLE_ARXIV_XML)

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        config = ArxivConfig(
            base_url="http://test.local/api/query",
            delay_seconds=0.0,
        )
        collector = ArxivCollector(config=config, client=client)

        collector.search_papers("test", categories=["cs.AI", "cs.SE"])

        assert captured_query
        assert "cat:cs.AI" in captured_query[0]
        assert "cat:cs.SE" in captured_query[0]

    def test_fetch_paper(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "id_list" in str(request.url)
            return _text_response(SAMPLE_ARXIV_XML)

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        config = ArxivConfig(
            base_url="http://test.local/api/query",
            delay_seconds=0.0,
        )
        collector = ArxivCollector(config=config, client=client)

        paper = collector.fetch_paper("2301.12345")

        assert paper.title == "Test Paper on AI Agents"
        assert paper.published == "2023-01-15T00:00:00Z"
        assert paper.updated == "2023-01-16T00:00:00Z"


# ======================================================================
# DataStore tests
# ======================================================================


class TestStoreCrud:
    """AC: Data stores and retrieves."""

    def test_save_and_get_repos(self) -> None:
        store = DataStore(":memory:")
        try:
            repo = Repository(
                name="nines",
                owner="testorg",
                url="https://github.com/testorg/nines",
                stars=42,
                forks=7,
                description="Eval system",
                language="Python",
                topics=["ai"],
                last_updated="2026-04-10",
            )
            store.save_repos([repo])

            repos = store.get_repos()
            assert len(repos) == 1
            assert repos[0].name == "nines"
            assert repos[0].owner == "testorg"
            assert repos[0].stars == 42
            assert repos[0].topics == ["ai"]
        finally:
            store.close()

    def test_save_and_get_papers(self) -> None:
        store = DataStore(":memory:")
        try:
            paper = Paper(
                id="2301.12345",
                title="Test Paper",
                authors=["Alice", "Bob"],
                abstract="Abstract text",
                categories=["cs.AI"],
                published="2023-01-15",
                updated="2023-01-16",
                pdf_url="http://arxiv.org/pdf/2301.12345",
            )
            store.save_papers([paper])

            papers = store.get_papers()
            assert len(papers) == 1
            assert papers[0].id == "2301.12345"
            assert papers[0].title == "Test Paper"
            assert papers[0].authors == ["Alice", "Bob"]
            assert papers[0].categories == ["cs.AI"]
        finally:
            store.close()

    def test_get_repos_with_filters(self) -> None:
        store = DataStore(":memory:")
        try:
            repos = [
                Repository(name="py-repo", owner="org", url="u1", stars=100, language="Python"),
                Repository(name="js-repo", owner="org", url="u2", stars=50, language="JavaScript"),
                Repository(name="py-small", owner="org2", url="u3", stars=10, language="Python"),
            ]
            store.save_repos(repos)

            python_repos = store.get_repos({"language": "Python"})
            assert len(python_repos) == 2

            high_star_repos = store.get_repos({"min_stars": 50})
            assert len(high_star_repos) == 2

            filtered = store.get_repos({"language": "Python", "min_stars": 50})
            assert len(filtered) == 1
            assert filtered[0].name == "py-repo"
        finally:
            store.close()

    def test_get_papers_with_filters(self) -> None:
        store = DataStore(":memory:")
        try:
            papers = [
                Paper(id="1", title="AI Paper", categories=["cs.AI"], authors=["Alice"]),
                Paper(id="2", title="SE Paper", categories=["cs.SE"], authors=["Bob"]),
            ]
            store.save_papers(papers)

            ai_papers = store.get_papers({"category": "cs.AI"})
            assert len(ai_papers) == 1
            assert ai_papers[0].title == "AI Paper"
        finally:
            store.close()

    def test_upsert_repos_updates_existing(self) -> None:
        store = DataStore(":memory:")
        try:
            repo_v1 = Repository(name="repo", owner="org", url="u1", stars=10)
            store.save_repos([repo_v1])

            repo_v2 = Repository(name="repo", owner="org", url="u1", stars=100)
            store.save_repos([repo_v2])

            repos = store.get_repos()
            assert len(repos) == 1
            assert repos[0].stars == 100
        finally:
            store.close()


class TestSnapshotSaveLoad:
    """AC: Snapshots persist and can be retrieved."""

    def test_save_and_retrieve_snapshot(self) -> None:
        store = DataStore(":memory:")
        try:
            snapshot = CollectionSnapshot(
                source="github",
                timestamp="2026-04-10T12:00:00Z",
                items=[
                    {"type": "repo", "name": "nines"},
                    {"type": "repo", "name": "other"},
                ],
            )
            sid = store.save_snapshot(snapshot)
            assert sid > 0

            snapshots = store.get_snapshots(source="github")
            assert len(snapshots) == 1
            loaded = snapshots[0]
            assert loaded.source == "github"
            assert loaded.timestamp == "2026-04-10T12:00:00Z"
            assert len(loaded.items) == 2
            assert loaded.items[0]["name"] == "nines"
        finally:
            store.close()

    def test_multiple_snapshots_ordered_by_time(self) -> None:
        store = DataStore(":memory:")
        try:
            for ts in ["2026-04-08T00:00:00Z", "2026-04-10T00:00:00Z", "2026-04-09T00:00:00Z"]:
                store.save_snapshot(CollectionSnapshot(source="arxiv", timestamp=ts, items=[]))

            snapshots = store.get_snapshots(source="arxiv")
            assert len(snapshots) == 3
            timestamps = [s.timestamp for s in snapshots]
            assert timestamps == sorted(timestamps, reverse=True)
        finally:
            store.close()


# ======================================================================
# Model round-trip tests
# ======================================================================


class TestModelSerialization:
    def test_repository_round_trip(self) -> None:
        repo = Repository(name="r", owner="o", stars=5, topics=["a", "b"])
        assert Repository.from_dict(repo.to_dict()) == repo

    def test_paper_round_trip(self) -> None:
        paper = Paper(id="123", title="T", authors=["A"])
        assert Paper.from_dict(paper.to_dict()) == paper

    def test_snapshot_round_trip(self) -> None:
        snap = CollectionSnapshot(source="gh", timestamp="t", items=[{"k": 1}])
        assert CollectionSnapshot.from_dict(snap.to_dict()) == snap

    def test_change_event_round_trip(self) -> None:
        evt = ChangeEvent(entity_id="e1", change_type="modified", old_value=1, new_value=2)
        assert ChangeEvent.from_dict(evt.to_dict()) == evt
