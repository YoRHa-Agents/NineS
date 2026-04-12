# Information Collection Pipeline Design

> **Task**: T13 (Design Team L3) | **Generated**: 2026-04-11 | **Status**: Complete
> **Requirements**: FR-201 through FR-212 (`docs/design/requirements.md` §1.2)
> **Domain Knowledge**: `docs/research/domain_knowledge.md` (Area 1)
> **Consumed by**: S04 (Architecture Review), S06 (Feature Implementation — T27, T30)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Source Protocol](#2-source-protocol)
3. [GitHub Collector](#3-github-collector)
4. [arXiv Collector](#4-arxiv-collector)
5. [Data Models](#5-data-models)
6. [SQLite Storage Layer](#6-sqlite-storage-layer)
7. [Incremental Tracking](#7-incremental-tracking)
8. [Change Detection & Diff](#8-change-detection--diff)
9. [Scheduler](#9-scheduler)
10. [Error Handling & Resilience](#10-error-handling--resilience)
11. [Module Layout](#11-module-layout)
12. [Requirement Traceability](#12-requirement-traceability)

---

## 1. Overview

The information collection pipeline is NineS's V2 capability vertex — responsible for discovering, fetching, tracking, and diffing external data sources relevant to AI agent evaluation. For MVP, the pipeline targets two sources: **GitHub** (repositories) and **arXiv** (papers). The architecture is designed around a `SourceProtocol` abstraction so additional sources (RSS feeds, blogs, package registries) can be added with ≤1 file + ≤20 lines of registration code (NFR-13).

### Data Flow

```
User Query / Schedule Trigger
        │
        ▼
┌─────────────────┐
│   Scheduler      │──── manual trigger / cron-style tick
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  SourceRegistry  │────▶│  GitHubCollector  │     │  ArxivCollector   │
│  (dispatches to  │────▶│  (REST + GraphQL) │     │  (Atom XML API)   │
│   collectors)    │     └────────┬─────────┘     └────────┬─────────┘
└─────────────────┘              │                         │
                                 ▼                         ▼
                      ┌────────────────────────────────────────┐
                      │         RateLimiter (token-bucket)      │
                      │  github_rest_search: 30 req/min         │
                      │  github_rest_core:   5,000 req/hr       │
                      │  github_graphql:     5,000 pts/hr       │
                      │  arxiv:              1 req/3s            │
                      └────────────────┬───────────────────────┘
                                       │
                                       ▼
                      ┌────────────────────────────────────────┐
                      │        ResponseCache (TTL-based)        │
                      └────────────────┬───────────────────────┘
                                       │
                                       ▼
                      ┌────────────────────────────────────────┐
                      │             DataStore (SQLite)           │
                      │  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
                      │  │ repos   │ │ papers  │ │ snapshots │ │
                      │  └─────────┘ └─────────┘ └───────────┘ │
                      └────────────────┬───────────────────────┘
                                       │
                                       ▼
                      ┌────────────────────────────────────────┐
                      │          IncrementalTracker             │
                      │  (bookmark state, cursor management)    │
                      └────────────────┬───────────────────────┘
                                       │
                                       ▼
                      ┌────────────────────────────────────────┐
                      │          ChangeDetector                 │
                      │  (snapshot diff, structured output)     │
                      └────────────────────────────────────────┘
```

---

## 2. Source Protocol

The `SourceProtocol` is the central abstraction for all data sources. It uses Python's structural subtyping (`typing.Protocol`) so implementations need no base class inheritance — they only need to match the method signatures (CON-09).

### 2.1 Core Types

```python
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


class SourceType(enum.Enum):
    GITHUB = "github"
    ARXIV = "arxiv"
    RSS = "rss"


@dataclass(frozen=True)
class SourceItem:
    """A single item returned by a data source."""
    source_type: SourceType
    source_id: str
    title: str
    url: str
    metadata: dict[str, Any]
    fetched_at: datetime
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class SearchQuery:
    """Parameterized search across any source."""
    query: str
    source_type: SourceType
    filters: dict[str, Any] = field(default_factory=dict)
    sort_by: str = "relevance"
    sort_order: str = "desc"
    limit: int = 30
    offset: int = 0


@dataclass(frozen=True)
class SearchResult:
    """Paginated search result."""
    items: list[SourceItem]
    total_count: int
    has_more: bool
    query: SearchQuery


@dataclass(frozen=True)
class TrackingHandle:
    """Opaque handle representing a tracked item."""
    source_type: SourceType
    source_id: str
    tracked_since: datetime
    last_checked: datetime | None = None
    bookmark: str | None = None


class ChangeType(enum.Enum):
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


@dataclass(frozen=True)
class ChangeEvent:
    """A detected change in a tracked source item."""
    source_type: SourceType
    source_id: str
    change_type: ChangeType
    timestamp: datetime
    changed_fields: list[str]
    old_values: dict[str, Any]
    new_values: dict[str, Any]
    summary: str


@dataclass(frozen=True)
class HealthStatus:
    """Result of a source health check."""
    source_type: SourceType
    reachable: bool
    latency_ms: float
    message: str
    checked_at: datetime
```

### 2.2 Protocol Definition

```python
@runtime_checkable
class SourceProtocol(Protocol):
    """
    Abstract interface for any data source.

    Implementations must satisfy structural subtyping — no inheritance required.
    Use @runtime_checkable to enable isinstance() verification at registration.

    Satisfies: FR-204
    """

    @property
    def source_type(self) -> SourceType:
        """The type identifier for this source."""
        ...

    def search(self, query: SearchQuery) -> SearchResult:
        """
        Search this source for items matching the query.

        Respects rate limits internally. Returns a paginated SearchResult.
        Raises CollectionError on unrecoverable failure.
        """
        ...

    def fetch(self, source_id: str) -> SourceItem:
        """
        Fetch a single item by its source-specific identifier.

        For GitHub: "owner/repo". For arXiv: "2301.12345".
        Raises NotFoundError if the item does not exist.
        """
        ...

    def track(self, source_id: str) -> TrackingHandle:
        """
        Begin tracking an item for incremental updates.

        Creates a bookmark entry in the data store. Subsequent calls to
        check_updates() will use this bookmark to detect changes.
        """
        ...

    def check_updates(self, since: datetime) -> list[ChangeEvent]:
        """
        Check for changes across all tracked items since the given timestamp.

        Returns a list of ChangeEvent instances, one per detected change.
        """
        ...

    def health_check(self) -> HealthStatus:
        """
        Verify source reachability and data availability.

        Executes a lightweight probe (e.g., a small search or API ping).
        Never raises — returns HealthStatus with reachable=False on failure.
        Satisfies: FR-211
        """
        ...
```

### 2.3 Source Registry

A central registry manages collector instances by source type and handles dispatch:

```python
from nines.core.errors import CollectionError

class SourceRegistry:
    """
    Registry of SourceProtocol implementations.

    Provides a single dispatch point for the scheduler and CLI.
    New sources are registered with register(), which validates
    Protocol conformance at registration time.
    """

    def __init__(self) -> None:
        self._sources: dict[SourceType, SourceProtocol] = {}

    def register(self, source: SourceProtocol) -> None:
        if not isinstance(source, SourceProtocol):
            raise TypeError(
                f"{type(source).__name__} does not satisfy SourceProtocol"
            )
        self._sources[source.source_type] = source

    def get(self, source_type: SourceType) -> SourceProtocol:
        try:
            return self._sources[source_type]
        except KeyError:
            raise CollectionError(
                code="E_SOURCE_NOT_FOUND",
                message=f"No collector registered for {source_type.value}",
                hint=f"Register a collector via registry.register()",
            )

    def list_sources(self) -> list[SourceType]:
        return list(self._sources.keys())

    def health_check_all(self) -> dict[SourceType, HealthStatus]:
        return {st: src.health_check() for st, src in self._sources.items()}
```

---

## 3. GitHub Collector

The GitHub collector implements `SourceProtocol` using both REST API v3 (for simple lookups and search) and GraphQL API v4 (for deep multi-field fetches). The choice of API is internal to the collector — callers always interact through the protocol.

### 3.1 Architecture

```
GitHubCollector
├── _rest_client: httpx.Client     (REST API v3)
├── _graphql_client: httpx.Client  (GraphQL API v4)
├── _rate_limiter: RateLimiter     (token-bucket, per-tier)
├── _cache: ResponseCache          (TTL-based)
└── _config: GitHubConfig
```

### 3.2 Configuration

```python
@dataclass(frozen=True)
class GitHubConfig:
    """Configuration for the GitHub collector."""
    token: str
    api_version: str = "2022-11-28"
    base_url: str = "https://api.github.com"
    graphql_url: str = "https://api.github.com/graphql"
    timeout_seconds: float = 30.0
    max_retries: int = 3
    use_graphql_for_deep_fetch: bool = True
    cache_ttl_seconds: int = 300
```

### 3.3 Interface Definition

```python
class GitHubCollector:
    """
    GitHub data collector using REST API v3 + GraphQL API v4.

    Capabilities:
    - Repository search by topic, language, star count (FR-201)
    - Deep metadata fetch: stars, forks, commits, releases, topics,
      README content, file tree, contributor info (FR-202)
    - Rate limiting via token bucket with adaptive back-off (FR-206)
    - Authentication via Personal Access Token (PAT)

    API selection strategy:
    - search() → REST /search/repositories (paginated, 30 req/min tier)
    - fetch() with deep=False → REST /repos/{owner}/{repo} (5,000 req/hr tier)
    - fetch() with deep=True → GraphQL single query (5,000 pts/hr tier)
    """

    def __init__(
        self,
        config: GitHubConfig,
        rate_limiter: RateLimiter,
        cache: ResponseCache,
    ) -> None:
        self._config = config
        self._rate_limiter = rate_limiter
        self._cache = cache
        self._rest_client = self._build_rest_client()
        self._graphql_client = self._build_graphql_client()

    @property
    def source_type(self) -> SourceType:
        return SourceType.GITHUB

    # --- SourceProtocol methods ---

    def search(self, query: SearchQuery) -> SearchResult:
        """
        Search GitHub repositories via REST API v3.

        Translates SearchQuery.filters into GitHub search qualifiers:
          - language → "language:python"
          - min_stars → "stars:>N"
          - topic → "topic:NAME"
          - created_after → "created:>YYYY-MM-DD"

        Rate limit tier: github_rest_search (30 req/min)
        """
        ...

    def fetch(self, source_id: str) -> SourceItem:
        """
        Fetch full repository metadata.

        source_id format: "owner/repo"

        Uses GraphQL when config.use_graphql_for_deep_fetch is True,
        falling back to REST for simpler lookups. A single GraphQL query
        retrieves: stars, forks, commit history (last 10), releases (last 5),
        topics, README content, open issues/PRs count, primary language.

        Rate limit tier: github_graphql (5,000 pts/hr) or
                         github_rest_core (5,000 req/hr)
        """
        ...

    def track(self, source_id: str) -> TrackingHandle:
        """Begin tracking a repository for incremental updates."""
        ...

    def check_updates(self, since: datetime) -> list[ChangeEvent]:
        """
        Check all tracked repositories for changes since the given timestamp.

        Detects: star count changes, new releases, new commits on default
        branch, README modifications, topic changes, fork count changes.
        """
        ...

    def health_check(self) -> HealthStatus:
        """Ping the GitHub API rate_limit endpoint."""
        ...

    # --- GitHub-specific public methods ---

    def fetch_readme(self, owner: str, repo: str) -> str:
        """Fetch decoded README content. Returns empty string if absent."""
        ...

    def fetch_file_tree(
        self, owner: str, repo: str, path: str = "", depth: int = 2
    ) -> list[dict[str, Any]]:
        """Fetch repository file tree up to given depth."""
        ...

    def fetch_contributors(
        self, owner: str, repo: str, limit: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch top contributors with commit counts."""
        ...

    def fetch_releases(
        self, owner: str, repo: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch recent releases with tag, date, and body."""
        ...

    def fetch_commit_activity(
        self, owner: str, repo: str
    ) -> list[dict[str, Any]]:
        """Fetch weekly commit counts for the last year (52 data points)."""
        ...
```

### 3.4 GraphQL Query Design

The deep fetch uses a single GraphQL query to minimize rate limit point consumption (target: ≤2 points per query, FR-202):

```graphql
query RepoDeepFetch($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    name
    nameWithOwner
    description
    url
    homepageUrl
    stargazerCount
    forkCount
    primaryLanguage { name }
    licenseInfo { spdxId name }
    isArchived
    isFork
    createdAt
    updatedAt
    pushedAt
    diskUsage

    defaultBranchRef {
      name
      target {
        ... on Commit {
          history(first: 10) {
            totalCount
            nodes {
              oid
              messageHeadline
              committedDate
              author { name email }
            }
          }
        }
      }
    }

    releases(last: 5, orderBy: {field: CREATED_AT, direction: DESC}) {
      totalCount
      nodes {
        tagName
        name
        publishedAt
        description
        isPrerelease
      }
    }

    repositoryTopics(first: 20) {
      nodes { topic { name } }
    }

    issues(states: OPEN) { totalCount }
    pullRequests(states: OPEN) { totalCount }

    object(expression: "HEAD:README.md") {
      ... on Blob { text }
    }

    languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
      edges {
        size
        node { name }
      }
      totalSize
    }
  }
}
```

### 3.5 REST API Endpoints Used

| Endpoint | Rate Tier | Use Case |
|----------|-----------|----------|
| `GET /search/repositories` | search (30/min) | Repository search with qualifiers |
| `GET /repos/{owner}/{repo}` | core (5,000/hr) | Single repo metadata |
| `GET /repos/{owner}/{repo}/readme` | core | README content (base64) |
| `GET /repos/{owner}/{repo}/git/trees/{sha}` | core | File tree traversal |
| `GET /repos/{owner}/{repo}/contributors` | core | Top contributors |
| `GET /repos/{owner}/{repo}/releases` | core | Release list |
| `GET /repos/{owner}/{repo}/stats/commit_activity` | core | Weekly commit counts |
| `GET /repos/{owner}/{repo}/stargazers` | core | Stargazers with dates (star+json) |
| `GET /rate_limit` | — (not counted) | Health check / rate limit status |
| `POST /graphql` | graphql (5,000 pts/hr) | Deep multi-field fetch |

### 3.6 Rate Limiting Strategy

The GitHub collector uses a two-tier rate limiting approach:

1. **Proactive**: Token-bucket rate limiter gates requests *before* they are sent, calibrated per tier.
2. **Reactive**: Response headers (`x-ratelimit-remaining`, `x-ratelimit-reset`, `retry-after`) trigger adaptive back-off when approaching limits.

```python
@dataclass
class RateLimiter:
    """
    Thread-safe token-bucket rate limiter.

    Calibrated per source tier:
    - github_rest_search: max_tokens=30, refill_rate=0.5/s (30/min)
    - github_rest_core:   max_tokens=5000, refill_rate=1.389/s (5000/hr)
    - github_graphql:     max_tokens=5000, refill_rate=1.389/s (5000 pts/hr)
    - arxiv:              max_tokens=1, refill_rate=0.333/s (1/3s)

    Satisfies: FR-206
    """
    max_tokens: float
    refill_rate: float  # tokens per second
    _tokens: float
    _last_refill: float
    _lock: threading.Lock

    def acquire(self, tokens: float = 1.0) -> float:
        """
        Block until enough tokens are available.
        Returns the time spent waiting (seconds).
        """
        ...

    def update_from_headers(self, headers: dict[str, str]) -> None:
        """
        Adapt internal state from API response headers.

        Reads x-ratelimit-remaining and x-ratelimit-reset to sync
        token count with server-reported state. When remaining drops
        below 10% of the limit, doubles the inter-request interval.
        """
        ...
```

### 3.7 Authentication

MVP uses a GitHub Personal Access Token (fine-grained) with `public_repo` read scope. The token is loaded from:

1. `NinesConfig.collector.github.token` (TOML config)
2. `NINES_GITHUB_TOKEN` environment variable (runtime override)
3. `gh auth token` output (fallback via GitHub CLI, if available)

---

## 4. arXiv Collector

### 4.1 Interface Definition

```python
@dataclass(frozen=True)
class ArxivConfig:
    """Configuration for the arXiv collector."""
    base_url: str = "http://export.arxiv.org/api/query"
    delay_seconds: float = 3.0
    max_results_per_page: int = 50
    max_retries: int = 3
    timeout_seconds: float = 30.0
    default_categories: list[str] = field(
        default_factory=lambda: ["cs.AI", "cs.SE", "cs.CL", "cs.LG"]
    )


class ArxivCollector:
    """
    arXiv paper collector using the Atom XML API.

    Capabilities:
    - Paper search by title, author, abstract, category (FR-203)
    - Metadata extraction: title, authors, abstract, categories,
      published date, updated date, PDF URL
    - Batch collection with pagination and rate limiting
    - Category filtering against configurable default categories

    Rate limiting: 1 request per 3 seconds (enforced by arXiv,
    respected via token-bucket limiter).

    Query syntax:
      - ti:keyword       (title search)
      - au:author         (author search)
      - abs:keyword       (abstract search)
      - cat:cs.AI         (category filter)
      - all:keyword       (all fields)
      - Combine with AND, OR, ANDNOT
    """

    def __init__(
        self,
        config: ArxivConfig,
        rate_limiter: RateLimiter,
        cache: ResponseCache,
    ) -> None:
        self._config = config
        self._rate_limiter = rate_limiter
        self._cache = cache

    @property
    def source_type(self) -> SourceType:
        return SourceType.ARXIV

    def search(self, query: SearchQuery) -> SearchResult:
        """
        Search arXiv papers.

        Translates SearchQuery.filters into arXiv query syntax:
          - category → "cat:cs.AI"
          - title_contains → "ti:keyword"
          - author → "au:name"
          - date_from → submittedDate range filter (post-fetch)

        Pagination: uses start/max_results parameters.
        Parses Atom XML response into SourceItem instances.
        """
        ...

    def fetch(self, source_id: str) -> SourceItem:
        """
        Fetch a single paper by arXiv ID (e.g., "2301.12345" or "2301.12345v2").

        Uses id_list parameter for exact lookup.
        """
        ...

    def track(self, source_id: str) -> TrackingHandle:
        """Begin tracking a paper for version updates."""
        ...

    def check_updates(self, since: datetime) -> list[ChangeEvent]:
        """
        Check tracked papers for new versions or metadata changes.

        arXiv papers can be updated (v1 → v2). Detects version bumps
        and metadata changes (title, abstract, categories).
        """
        ...

    def health_check(self) -> HealthStatus:
        """Execute a minimal search query to verify API reachability."""
        ...

    # --- arXiv-specific public methods ---

    def collect_by_category(
        self,
        categories: list[str] | None = None,
        max_total: int = 500,
        since: datetime | None = None,
    ) -> list[SourceItem]:
        """
        Bulk collection of papers by category with pagination.

        Uses configurable delay between pages to respect rate limits.
        Filters results to the specified categories (or config defaults).
        """
        ...

    def fetch_paper_metadata(self, arxiv_id: str) -> dict[str, Any]:
        """Fetch detailed paper metadata including all versions."""
        ...
```

### 4.2 XML Parsing Strategy

arXiv returns Atom XML. The parsing flow:

1. Fetch raw XML via `httpx.get()` with rate-limited timing
2. Parse with `xml.etree.ElementTree` (stdlib, no external dependency)
3. Extract fields using Atom namespace `http://www.w3.org/2005/Atom`
4. Map to `SourceItem` with arXiv-specific metadata in `metadata` dict
5. Store `raw_data` for later re-parsing if needed

### 4.3 Pagination Design

```
Page 1: start=0,  max_results=50 → fetch → parse → store
  (delay 3s)
Page 2: start=50, max_results=50 → fetch → parse → store
  (delay 3s)
...
Page N: start=N*50, max_results=50 → fetch → parse → store (or empty → stop)
```

The collector terminates pagination when: (a) an empty page is returned, (b) `max_total` items have been collected, or (c) an unrecoverable error occurs.

---

## 5. Data Models

All data models are Python `dataclass` instances with full type annotations. They serve as the bridge between collectors, the storage layer, and downstream consumers (change detection, analysis vertex).

### 5.1 Repository

```python
@dataclass
class Repository:
    """
    A GitHub repository with all tracked metadata.

    Maps to the `repositories` SQLite table.
    """
    # Identity
    id: int | None = None
    source_id: str = ""           # "owner/repo"
    name: str = ""
    full_name: str = ""           # "owner/repo"
    owner: str = ""
    url: str = ""

    # Descriptive
    description: str = ""
    readme_content: str = ""
    topics: list[str] = field(default_factory=list)
    primary_language: str = ""
    languages: dict[str, int] = field(default_factory=dict)
    license_spdx: str = ""

    # Metrics
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    open_prs: int = 0
    total_commits: int = 0
    disk_usage_kb: int = 0

    # Temporal
    created_at: datetime | None = None
    updated_at: datetime | None = None
    pushed_at: datetime | None = None
    fetched_at: datetime | None = None

    # State
    is_archived: bool = False
    is_fork: bool = False

    # Structured sub-data (JSON-serialized in SQLite)
    recent_commits: list[dict[str, Any]] = field(default_factory=list)
    recent_releases: list[dict[str, Any]] = field(default_factory=list)
    top_contributors: list[dict[str, Any]] = field(default_factory=list)

    # Tracking
    tracking_enabled: bool = False
    last_tracked_at: datetime | None = None
    bookmark: str | None = None
```

### 5.2 Paper

```python
@dataclass
class Paper:
    """
    An arXiv paper with metadata.

    Maps to the `papers` SQLite table.
    """
    # Identity
    id: int | None = None
    source_id: str = ""           # arXiv ID, e.g. "2301.12345"
    arxiv_id: str = ""            # canonical arXiv ID
    version: int = 1              # paper version (v1, v2, ...)
    url: str = ""
    pdf_url: str = ""

    # Descriptive
    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    categories: list[str] = field(default_factory=list)
    primary_category: str = ""

    # Temporal
    published_at: datetime | None = None
    updated_at: datetime | None = None
    fetched_at: datetime | None = None

    # Tracking
    tracking_enabled: bool = False
    last_tracked_at: datetime | None = None
    bookmark: str | None = None
```

### 5.3 Article (Generic)

```python
@dataclass
class Article:
    """
    A generic article/blog post/announcement.

    Used for RSS feed entries and other non-structured sources.
    Maps to the `articles` SQLite table.
    """
    id: int | None = None
    source_id: str = ""
    source_type: str = ""         # "rss", "blog", etc.
    source_feed: str = ""         # originating feed URL

    title: str = ""
    url: str = ""
    summary: str = ""
    content: str = ""
    author: str = ""

    published_at: datetime | None = None
    fetched_at: datetime | None = None

    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 5.4 CollectionSnapshot

```python
@dataclass
class CollectionSnapshot:
    """
    A point-in-time snapshot of a collection run.

    Captures the complete state of all items collected in a single run.
    Used as input to ChangeDetector for incremental diff computation.
    Maps to the `collection_snapshots` SQLite table.
    """
    id: int | None = None
    snapshot_id: str = ""         # UUID hex
    source_type: str = ""         # "github", "arxiv"
    created_at: datetime | None = None

    # Aggregate stats
    total_items: int = 0
    new_items: int = 0
    updated_items: int = 0

    # Item references (source_ids in this snapshot)
    item_ids: list[str] = field(default_factory=list)

    # Per-item field hashes for change detection
    # Maps source_id → sha256 of serialized metadata
    item_fingerprints: dict[str, str] = field(default_factory=dict)

    # Bookmark state at the time of this snapshot
    bookmark: str | None = None
    query_params: dict[str, Any] = field(default_factory=dict)
```

### 5.5 ChangeEvent (Detailed)

```python
@dataclass
class ChangeEvent:
    """
    A detected change between two collection snapshots.

    Maps to the `change_events` SQLite table.
    """
    id: int | None = None
    source_type: str = ""
    source_id: str = ""
    change_type: str = ""         # "added", "modified", "removed"
    detected_at: datetime | None = None

    # Snapshot references
    before_snapshot_id: str | None = None
    after_snapshot_id: str | None = None

    # Change details
    changed_fields: list[str] = field(default_factory=list)
    old_values: dict[str, Any] = field(default_factory=dict)
    new_values: dict[str, Any] = field(default_factory=dict)

    # Categorization
    change_category: str = ""     # "breaking", "feature", "fix", "docs", "metrics"
    significance: str = ""        # "high", "medium", "low"
    summary: str = ""
```

---

## 6. SQLite Storage Layer

### 6.1 Schema Design

SQLite is the sole storage backend (CON-04). The schema uses WAL mode for read concurrency and foreign keys for referential integrity.

```sql
-- Pragma configuration (applied on every connection open)
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

-- ============================================================
-- Core entity tables
-- ============================================================

CREATE TABLE IF NOT EXISTS repositories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       TEXT    NOT NULL UNIQUE,   -- "owner/repo"
    name            TEXT    NOT NULL,
    full_name       TEXT    NOT NULL,
    owner           TEXT    NOT NULL,
    url             TEXT    NOT NULL,

    description     TEXT    DEFAULT '',
    readme_content  TEXT    DEFAULT '',
    topics          TEXT    DEFAULT '[]',       -- JSON array
    primary_language TEXT   DEFAULT '',
    languages       TEXT    DEFAULT '{}',       -- JSON object {lang: bytes}
    license_spdx    TEXT    DEFAULT '',

    stars           INTEGER DEFAULT 0,
    forks           INTEGER DEFAULT 0,
    watchers        INTEGER DEFAULT 0,
    open_issues     INTEGER DEFAULT 0,
    open_prs        INTEGER DEFAULT 0,
    total_commits   INTEGER DEFAULT 0,
    disk_usage_kb   INTEGER DEFAULT 0,

    created_at      TEXT,                       -- ISO 8601
    updated_at      TEXT,
    pushed_at       TEXT,
    fetched_at      TEXT    NOT NULL,

    is_archived     INTEGER DEFAULT 0,
    is_fork         INTEGER DEFAULT 0,

    recent_commits  TEXT    DEFAULT '[]',       -- JSON array
    recent_releases TEXT    DEFAULT '[]',
    top_contributors TEXT   DEFAULT '[]',

    tracking_enabled INTEGER DEFAULT 0,
    last_tracked_at  TEXT,
    bookmark         TEXT
);

CREATE TABLE IF NOT EXISTS papers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       TEXT    NOT NULL UNIQUE,   -- arXiv ID "2301.12345"
    arxiv_id        TEXT    NOT NULL,
    version         INTEGER DEFAULT 1,
    url             TEXT    NOT NULL,
    pdf_url         TEXT    DEFAULT '',

    title           TEXT    NOT NULL,
    authors         TEXT    DEFAULT '[]',       -- JSON array
    abstract        TEXT    DEFAULT '',
    categories      TEXT    DEFAULT '[]',       -- JSON array
    primary_category TEXT   DEFAULT '',

    published_at    TEXT,
    updated_at      TEXT,
    fetched_at      TEXT    NOT NULL,

    tracking_enabled INTEGER DEFAULT 0,
    last_tracked_at  TEXT,
    bookmark         TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       TEXT    NOT NULL UNIQUE,
    source_type     TEXT    NOT NULL,
    source_feed     TEXT    DEFAULT '',

    title           TEXT    NOT NULL,
    url             TEXT    NOT NULL,
    summary         TEXT    DEFAULT '',
    content         TEXT    DEFAULT '',
    author          TEXT    DEFAULT '',

    published_at    TEXT,
    fetched_at      TEXT    NOT NULL,

    tags            TEXT    DEFAULT '[]',       -- JSON array
    metadata        TEXT    DEFAULT '{}'        -- JSON object
);

-- ============================================================
-- Tracking & change detection tables
-- ============================================================

CREATE TABLE IF NOT EXISTS collection_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id     TEXT    NOT NULL UNIQUE,    -- UUID hex
    source_type     TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,

    total_items     INTEGER DEFAULT 0,
    new_items       INTEGER DEFAULT 0,
    updated_items   INTEGER DEFAULT 0,

    item_ids        TEXT    DEFAULT '[]',       -- JSON array
    item_fingerprints TEXT  DEFAULT '{}',       -- JSON {source_id: sha256}

    bookmark        TEXT,
    query_params    TEXT    DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS change_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type     TEXT    NOT NULL,
    source_id       TEXT    NOT NULL,
    change_type     TEXT    NOT NULL,           -- "added"/"modified"/"removed"
    detected_at     TEXT    NOT NULL,

    before_snapshot_id TEXT,
    after_snapshot_id  TEXT,

    changed_fields  TEXT    DEFAULT '[]',       -- JSON array
    old_values      TEXT    DEFAULT '{}',
    new_values      TEXT    DEFAULT '{}',

    change_category TEXT    DEFAULT '',
    significance    TEXT    DEFAULT '',
    summary         TEXT    DEFAULT '',

    FOREIGN KEY (before_snapshot_id) REFERENCES collection_snapshots(snapshot_id),
    FOREIGN KEY (after_snapshot_id) REFERENCES collection_snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS tracking_bookmarks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type     TEXT    NOT NULL,
    source_id       TEXT    NOT NULL,
    tracked_since   TEXT    NOT NULL,
    last_checked    TEXT,
    bookmark        TEXT,                       -- opaque cursor string
    is_active       INTEGER DEFAULT 1,

    UNIQUE(source_type, source_id)
);

-- ============================================================
-- Cache table
-- ============================================================

CREATE TABLE IF NOT EXISTS response_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key       TEXT    NOT NULL UNIQUE,    -- sha256(method + url + params)
    response_data   TEXT    NOT NULL,           -- JSON-serialized response
    created_at      TEXT    NOT NULL,
    expires_at      TEXT    NOT NULL,
    source_type     TEXT    NOT NULL
);

-- ============================================================
-- Indices
-- ============================================================

-- Repository search and filtering
CREATE INDEX IF NOT EXISTS idx_repos_owner ON repositories(owner);
CREATE INDEX IF NOT EXISTS idx_repos_language ON repositories(primary_language);
CREATE INDEX IF NOT EXISTS idx_repos_stars ON repositories(stars DESC);
CREATE INDEX IF NOT EXISTS idx_repos_updated ON repositories(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_repos_fetched ON repositories(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_repos_tracking ON repositories(tracking_enabled)
    WHERE tracking_enabled = 1;

-- Paper search and filtering
CREATE INDEX IF NOT EXISTS idx_papers_category ON papers(primary_category);
CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_fetched ON papers(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_tracking ON papers(tracking_enabled)
    WHERE tracking_enabled = 1;

-- Article search
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_type);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);

-- Snapshot lookups
CREATE INDEX IF NOT EXISTS idx_snapshots_source ON collection_snapshots(source_type);
CREATE INDEX IF NOT EXISTS idx_snapshots_created ON collection_snapshots(created_at DESC);

-- Change event lookups
CREATE INDEX IF NOT EXISTS idx_changes_source ON change_events(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_changes_detected ON change_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_changes_type ON change_events(change_type);
CREATE INDEX IF NOT EXISTS idx_changes_snapshot ON change_events(after_snapshot_id);

-- Bookmark lookups
CREATE INDEX IF NOT EXISTS idx_bookmarks_source ON tracking_bookmarks(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_bookmarks_active ON tracking_bookmarks(is_active)
    WHERE is_active = 1;

-- Cache expiry
CREATE INDEX IF NOT EXISTS idx_cache_expires ON response_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_cache_source ON response_cache(source_type);

-- Full-text search (virtual tables)
CREATE VIRTUAL TABLE IF NOT EXISTS repos_fts USING fts5(
    source_id,
    name,
    description,
    readme_content,
    topics,
    content='repositories',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    source_id,
    title,
    abstract,
    authors,
    categories,
    content='papers',
    content_rowid='id'
);
```

### 6.2 DataStore Class

```python
class DataStore:
    """
    SQLite-backed storage for collected entities.

    Provides CRUD operations, keyword search (via FTS5), and faceted
    filtering. All operations use parameterized queries.

    Satisfies: FR-205

    Thread safety: uses one connection per thread via threading.local().
    WAL mode allows concurrent reads.
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        Open or create the SQLite database at db_path.

        Applies schema migrations on first open. Sets WAL mode
        and foreign key enforcement.
        """
        ...

    def close(self) -> None:
        """Close all database connections."""
        ...

    # --- Repository CRUD ---

    def upsert_repository(self, repo: Repository) -> int:
        """
        Insert or update a repository.

        Uses INSERT ... ON CONFLICT(source_id) DO UPDATE to merge
        new data with existing records. Returns the row ID.
        Also updates the FTS index.
        """
        ...

    def get_repository(self, source_id: str) -> Repository | None:
        """Fetch a repository by source_id ("owner/repo")."""
        ...

    def list_repositories(
        self,
        *,
        language: str | None = None,
        min_stars: int | None = None,
        topic: str | None = None,
        tracked_only: bool = False,
        sort_by: str = "stars",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Repository]:
        """
        List repositories with faceted filtering.

        Supports filtering by language, minimum stars, topic, and
        tracking status. Results are sorted by the given field.
        """
        ...

    def search_repositories(self, keyword: str, limit: int = 20) -> list[Repository]:
        """
        Full-text keyword search over repository names, descriptions,
        README content, and topics via FTS5.
        """
        ...

    def delete_repository(self, source_id: str) -> bool:
        """Delete a repository and its FTS entry. Returns True if found."""
        ...

    # --- Paper CRUD ---

    def upsert_paper(self, paper: Paper) -> int:
        """Insert or update a paper. Returns the row ID."""
        ...

    def get_paper(self, source_id: str) -> Paper | None:
        """Fetch a paper by arXiv ID."""
        ...

    def list_papers(
        self,
        *,
        category: str | None = None,
        since: datetime | None = None,
        tracked_only: bool = False,
        sort_by: str = "published_at",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Paper]:
        """List papers with faceted filtering."""
        ...

    def search_papers(self, keyword: str, limit: int = 20) -> list[Paper]:
        """Full-text keyword search over paper titles, abstracts, and authors."""
        ...

    def delete_paper(self, source_id: str) -> bool:
        """Delete a paper and its FTS entry."""
        ...

    # --- Article CRUD ---

    def upsert_article(self, article: Article) -> int: ...
    def get_article(self, source_id: str) -> Article | None: ...
    def list_articles(self, *, source_type: str | None = None,
                      limit: int = 50, offset: int = 0) -> list[Article]: ...
    def search_articles(self, keyword: str, limit: int = 20) -> list[Article]: ...
    def delete_article(self, source_id: str) -> bool: ...

    # --- Snapshot operations ---

    def save_snapshot(self, snapshot: CollectionSnapshot) -> int:
        """Persist a collection snapshot."""
        ...

    def get_snapshot(self, snapshot_id: str) -> CollectionSnapshot | None:
        """Retrieve a snapshot by UUID."""
        ...

    def get_latest_snapshot(self, source_type: str) -> CollectionSnapshot | None:
        """Get the most recent snapshot for a source type."""
        ...

    def list_snapshots(
        self,
        source_type: str | None = None,
        limit: int = 20,
    ) -> list[CollectionSnapshot]:
        """List snapshots, most recent first."""
        ...

    # --- Change event operations ---

    def save_change_events(self, events: list[ChangeEvent]) -> int:
        """Bulk-insert change events. Returns count inserted."""
        ...

    def list_change_events(
        self,
        *,
        source_type: str | None = None,
        source_id: str | None = None,
        change_type: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[ChangeEvent]:
        """Query change events with optional filters."""
        ...

    # --- Bookmark operations ---

    def upsert_bookmark(self, bookmark: TrackingBookmark) -> None:
        """Create or update a tracking bookmark."""
        ...

    def get_bookmark(
        self, source_type: str, source_id: str
    ) -> TrackingBookmark | None:
        """Retrieve a bookmark for a specific tracked item."""
        ...

    def list_active_bookmarks(
        self, source_type: str | None = None
    ) -> list[TrackingBookmark]:
        """List all active tracking bookmarks."""
        ...

    # --- Cache operations (FR-212) ---

    def cache_get(self, cache_key: str) -> str | None:
        """
        Retrieve a cached response if present and not expired.

        Returns None if the key is missing or TTL has expired.
        Expired entries are lazily deleted.
        """
        ...

    def cache_set(
        self, cache_key: str, data: str, source_type: str, ttl_seconds: int
    ) -> None:
        """Store a response in the cache with the given TTL."""
        ...

    def cache_invalidate(self, cache_key: str | None = None,
                         source_type: str | None = None) -> int:
        """
        Invalidate cache entries.

        If cache_key is provided, deletes that specific entry.
        If source_type is provided, deletes all entries for that source.
        If neither is provided, clears the entire cache.
        Returns count of deleted entries.
        """
        ...

    def cache_cleanup(self) -> int:
        """Delete all expired cache entries. Returns count deleted."""
        ...

    # --- Aggregate queries ---

    def get_collection_status(self) -> list[dict[str, Any]]:
        """
        Summary status for each tracked source type.

        Returns list of dicts with keys:
          source_type, item_count, tracked_count, last_collected,
          last_snapshot_id, next_refresh (estimated)

        Satisfies: FR-209
        """
        ...

    def count_by_source(self) -> dict[str, int]:
        """Count total items per source type."""
        ...

    # --- Export (FR-210) ---

    def export_json(self, source_type: str | None = None) -> str:
        """Export all entities as JSON."""
        ...

    def export_csv(self, source_type: str) -> str:
        """Export entities of a given source type as CSV."""
        ...

    def export_markdown(self, source_type: str | None = None) -> str:
        """Export entities as Markdown tables."""
        ...
```

### 6.3 Common Query Patterns

| Use Case | Query Strategy |
|----------|---------------|
| Search repos by language + min stars | `WHERE primary_language = ? AND stars >= ? ORDER BY stars DESC` |
| Full-text search repos | `SELECT ... FROM repos_fts WHERE repos_fts MATCH ? ORDER BY rank` |
| Tracked repos needing refresh | `WHERE tracking_enabled = 1 AND (last_tracked_at IS NULL OR last_tracked_at < ?)` |
| Recent changes for a source | `SELECT ... FROM change_events WHERE source_type = ? AND detected_at > ? ORDER BY detected_at DESC` |
| Latest snapshot for diff | `WHERE source_type = ? ORDER BY created_at DESC LIMIT 1` |
| Cache lookup (non-expired) | `WHERE cache_key = ? AND expires_at > datetime('now')` |
| Collection status summary | `SELECT source_type, COUNT(*), MAX(fetched_at) ... GROUP BY source_type` joined with `tracking_bookmarks` |

### 6.4 FTS Synchronization

FTS5 `content=` tables require explicit sync on INSERT/UPDATE/DELETE. The `DataStore` handles this by wrapping mutations in a transaction that updates both the base table and the FTS index:

```python
def _sync_repo_fts(self, conn: sqlite3.Connection, repo: Repository) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO repos_fts(rowid, source_id, name, "
        "description, readme_content, topics) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (repo.id, repo.source_id, repo.name, repo.description,
         repo.readme_content, json.dumps(repo.topics)),
    )
```

---

## 7. Incremental Tracking

Incremental tracking ensures that subsequent collection runs only fetch new or changed items, minimizing API calls and storage churn.

### 7.1 Bookmark/Cursor Model

Each tracked item maintains a **bookmark** — an opaque cursor string that encodes the state at the time of last successful collection. The bookmark format is source-specific:

| Source | Bookmark Format | Semantics |
|--------|----------------|-----------|
| GitHub | `"etag:{etag}\|pushed:{iso_timestamp}\|stars:{count}"` | ETag for conditional requests + last known pushed_at + star count for change detection |
| arXiv | `"updated:{iso_timestamp}\|version:{N}"` | Last known updated timestamp + paper version |

### 7.2 Tracking Algorithm

```
IncrementalTracker.collect_updates(source_type):

  1. Load active bookmarks from tracking_bookmarks table
     WHERE source_type = ? AND is_active = 1

  2. For each bookmark:
     a. Compute "needs refresh" using staleness heuristic:
        - GitHub: pushed_at changed OR fetched_at > refresh_interval
        - arXiv: updated_at changed OR fetched_at > refresh_interval

     b. If stale, call collector.fetch(source_id) with conditional headers
        - GitHub REST: If-None-Match: {etag} → 304 Not Modified = skip
        - GitHub GraphQL: compare pushed_at/stargazerCount in response
        - arXiv: compare updated timestamp with bookmark

     c. If changed:
        i.   Compute field-level diff (old bookmark state vs new data)
        ii.  Update entity in DataStore
        iii. Update bookmark with new cursor values
        iv.  Emit ChangeEvent(s) for each changed field
        v.   Update FTS index

     d. If not changed:
        i.   Update bookmark.last_checked timestamp only

  3. Check for new items via search query with since parameter:
     - GitHub: "pushed:>{last_snapshot_timestamp}"
     - arXiv: submittedDate sort, filter client-side

  4. Create CollectionSnapshot capturing the post-update state

  5. Return (new_snapshot, list[ChangeEvent])
```

### 7.3 Staleness Heuristic

```python
@dataclass(frozen=True)
class RefreshPolicy:
    """Configurable refresh policy for incremental tracking."""
    default_interval_seconds: int = 3600       # 1 hour default
    high_activity_interval_seconds: int = 900  # 15 minutes for active repos
    low_activity_interval_seconds: int = 86400 # 24 hours for stale repos
    activity_threshold_days: int = 7           # repos pushed within N days are "active"

def is_stale(
    bookmark: TrackingBookmark,
    policy: RefreshPolicy,
    now: datetime,
) -> bool:
    """Determine if a tracked item needs refreshing."""
    if bookmark.last_checked is None:
        return True

    elapsed = (now - bookmark.last_checked).total_seconds()

    # Parse bookmark to determine activity level
    fields = _parse_bookmark(bookmark.bookmark)
    last_pushed = fields.get("pushed")
    if last_pushed:
        days_since_push = (now - last_pushed).days
        if days_since_push <= policy.activity_threshold_days:
            return elapsed >= policy.high_activity_interval_seconds
        else:
            return elapsed >= policy.low_activity_interval_seconds

    return elapsed >= policy.default_interval_seconds
```

### 7.4 Conditional Fetch (GitHub)

For GitHub REST endpoints, use HTTP conditional requests to avoid counting against rate limits when data hasn't changed:

```
Request:
  GET /repos/owner/repo
  If-None-Match: "abc123"       ← from stored ETag

Response (unchanged):
  304 Not Modified              ← does NOT count against rate limit
  → skip processing, update last_checked only

Response (changed):
  200 OK
  ETag: "def456"                ← store new ETag in bookmark
  → process changes, update entity + bookmark
```

### 7.5 Fingerprint-Based Change Detection

For items where conditional requests aren't available (arXiv, GraphQL results), the tracker uses content fingerprinting:

```python
import hashlib
import json

def compute_fingerprint(item: SourceItem, tracked_fields: list[str]) -> str:
    """
    Compute a deterministic SHA-256 fingerprint of selected fields.

    Only tracked fields participate in the fingerprint, so cosmetic
    changes (e.g., fetched_at timestamp) don't trigger false changes.
    """
    data = {}
    for field_name in sorted(tracked_fields):
        value = item.metadata.get(field_name)
        data[field_name] = value
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()

# Tracked fields per source type
TRACKED_FIELDS = {
    SourceType.GITHUB: [
        "stars", "forks", "open_issues", "open_prs", "pushed_at",
        "topics", "description", "primary_language", "is_archived",
        "latest_release_tag", "total_commits",
    ],
    SourceType.ARXIV: [
        "title", "abstract", "authors", "categories", "version", "updated_at",
    ],
}
```

### 7.6 Bookmark Persistence

Bookmarks persist in the `tracking_bookmarks` SQLite table with UNIQUE(source_type, source_id) constraint. They survive process restarts (FR-207 acceptance criterion). The `IncrementalTracker` loads bookmarks at the start of each collection run and commits updates within the same transaction as entity updates, ensuring atomicity.

---

## 8. Change Detection & Diff

The `ChangeDetector` compares two `CollectionSnapshot` instances and produces structured diff output identifying additions, modifications, and deletions.

### 8.1 ChangeDetector Interface

```python
class ChangeDetector:
    """
    Compare two collection snapshots to produce structured diffs.

    Algorithm:
    1. Compute set difference on item_ids to find additions and removals
    2. For items present in both snapshots, compare fingerprints
    3. For fingerprint mismatches, perform field-level diff
    4. Categorize changes by type and significance

    Satisfies: FR-208
    """

    def __init__(self, store: DataStore) -> None:
        self._store = store

    def compare_snapshots(
        self,
        before: CollectionSnapshot,
        after: CollectionSnapshot,
    ) -> DiffResult:
        """
        Compare two snapshots and return a structured diff.

        Both snapshots must be for the same source_type.
        """
        ...

    def detect_changes_since(
        self,
        source_type: str,
        since: datetime,
    ) -> DiffResult:
        """
        Compare the latest snapshot against the snapshot closest to
        the given timestamp. Convenience wrapper around compare_snapshots.
        """
        ...

    def categorize_change(
        self,
        source_type: str,
        changed_fields: list[str],
        old_values: dict[str, Any],
        new_values: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Classify a change into (category, significance).

        Categories: "breaking", "feature", "fix", "docs", "metrics"
        Significance: "high", "medium", "low"
        """
        ...
```

### 8.2 Snapshot Comparison Algorithm

```
compare_snapshots(before, after):

  Input:
    before.item_ids        = {A, B, C, D}
    before.item_fingerprints = {A: "h1", B: "h2", C: "h3", D: "h4"}
    after.item_ids         = {A, B, C, E}
    after.item_fingerprints  = {A: "h1", B: "h5", C: "h3", E: "h6"}

  Step 1: Set operations
    added_ids    = after.item_ids - before.item_ids     = {E}
    removed_ids  = before.item_ids - after.item_ids     = {D}
    common_ids   = before.item_ids & after.item_ids     = {A, B, C}

  Step 2: Fingerprint comparison on common items
    unchanged = []
    modified  = []
    for id in common_ids:
        if before.item_fingerprints[id] == after.item_fingerprints[id]:
            unchanged.append(id)     → {A, C}
        else:
            modified.append(id)      → {B}

  Step 3: Field-level diff for modified items
    for id in modified:
        old_entity = store.get_entity(source_type, id)  (from before snapshot)
        new_entity = store.get_entity(source_type, id)  (current)
        field_diff = compute_field_diff(old_entity, new_entity)
        category, significance = categorize_change(...)
        → ChangeEvent for B: modified, changed_fields=[...], etc.

  Step 4: Emit events
    For added_ids:   ChangeEvent(change_type="added", ...)
    For removed_ids: ChangeEvent(change_type="removed", ...)
    For modified:    ChangeEvent(change_type="modified", changed_fields=..., ...)

  Output:
    DiffResult(
        before_snapshot_id = before.snapshot_id,
        after_snapshot_id  = after.snapshot_id,
        additions = [E],
        modifications = [B with field details],
        removals = [D],
        unchanged_count = 2,
    )
```

### 8.3 DiffResult Model

```python
@dataclass
class FieldDiff:
    """A single field-level change within a modified item."""
    field_name: str
    old_value: Any
    new_value: Any
    change_pct: float | None = None   # for numeric fields: (new-old)/old

@dataclass
class ItemDiff:
    """All changes detected for a single modified item."""
    source_id: str
    field_diffs: list[FieldDiff]
    category: str                      # "breaking", "feature", etc.
    significance: str                  # "high", "medium", "low"
    summary: str                       # human-readable one-line summary

@dataclass
class DiffResult:
    """Complete result of comparing two collection snapshots."""
    before_snapshot_id: str
    after_snapshot_id: str
    source_type: str
    computed_at: datetime

    additions: list[str]               # source_ids of new items
    removals: list[str]                # source_ids of removed items
    modifications: list[ItemDiff]      # detailed per-item diffs
    unchanged_count: int

    @property
    def total_changes(self) -> int:
        return len(self.additions) + len(self.removals) + len(self.modifications)

    @property
    def has_changes(self) -> bool:
        return self.total_changes > 0

    def to_change_events(self) -> list[ChangeEvent]:
        """Convert DiffResult into a list of ChangeEvent instances for storage."""
        ...

    def to_markdown(self) -> str:
        """Generate a human-readable Markdown summary of changes."""
        ...
```

### 8.4 Change Categorization Rules

| Change Pattern | Category | Significance |
|----------------|----------|-------------|
| New repo/paper appears | `feature` | `medium` |
| Item removed from results | `removal` | `low` (may reappear) |
| Star count change >20% | `metrics` | `high` |
| Star count change ≤20% | `metrics` | `low` |
| New release published | `feature` | `high` |
| README content changed | `docs` | `medium` |
| Description changed | `docs` | `low` |
| Topics changed | `docs` | `low` |
| Language distribution changed | `feature` | `medium` |
| Repository archived | `breaking` | `high` |
| Paper version bumped | `feature` | `high` |
| Paper abstract/title changed | `docs` | `medium` |
| Paper categories changed | `docs` | `low` |

---

## 9. Scheduler

The scheduler orchestrates collection jobs with support for manual triggers and cron-style periodic scheduling.

### 9.1 Scheduler Interface

```python
class CollectionJobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CollectionJob:
    """A scheduled or manually triggered collection job."""
    job_id: str
    source_type: SourceType
    query: SearchQuery | None = None
    incremental: bool = True
    status: CollectionJobStatus = CollectionJobStatus.PENDING
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_snapshot_id: str | None = None
    error_message: str | None = None
    change_count: int = 0


@dataclass(frozen=True)
class ScheduleConfig:
    """Cron-style schedule for periodic collection."""
    source_type: SourceType
    interval_seconds: int          # minimum interval between runs
    query: SearchQuery | None      # default search query (None = tracked items only)
    incremental: bool = True
    enabled: bool = True


class CollectionScheduler:
    """
    Manages collection job scheduling and execution.

    Supports two modes:
    1. Manual trigger: immediate one-off collection
    2. Periodic schedule: cron-style interval-based collection

    Jobs are queued and executed serially per source type (to respect
    rate limits) but different source types can run concurrently.

    MVP uses a simple interval-based scheduler with in-process execution.
    No external job queue dependency.
    """

    def __init__(
        self,
        registry: SourceRegistry,
        tracker: IncrementalTracker,
        store: DataStore,
    ) -> None:
        self._registry = registry
        self._tracker = tracker
        self._store = store
        self._schedules: dict[SourceType, ScheduleConfig] = {}
        self._job_queue: list[CollectionJob] = []
        self._running: bool = False

    # --- Schedule management ---

    def add_schedule(self, config: ScheduleConfig) -> None:
        """Register a periodic collection schedule."""
        ...

    def remove_schedule(self, source_type: SourceType) -> None:
        """Remove a periodic schedule."""
        ...

    def list_schedules(self) -> list[ScheduleConfig]:
        """List all configured schedules."""
        ...

    # --- Manual triggers ---

    def trigger_collection(
        self,
        source_type: SourceType,
        query: SearchQuery | None = None,
        incremental: bool = True,
    ) -> CollectionJob:
        """
        Manually trigger a collection job.

        If query is None, performs an incremental update of tracked items.
        Returns the created job (status=PENDING). Call run_pending()
        or execute_job() to process it.
        """
        ...

    def trigger_full_refresh(self, source_type: SourceType) -> CollectionJob:
        """Trigger a non-incremental full refresh of all tracked items."""
        ...

    # --- Job execution ---

    def execute_job(self, job: CollectionJob) -> CollectionJob:
        """
        Execute a single collection job synchronously.

        Workflow:
        1. Set status = RUNNING
        2. If job.query exists → collector.search(query)
        3. If job.incremental → tracker.collect_updates(source_type)
        4. Create CollectionSnapshot
        5. Run ChangeDetector against previous snapshot
        6. Persist change events
        7. Set status = COMPLETED (or FAILED on error)
        """
        ...

    def run_pending(self) -> list[CollectionJob]:
        """Execute all pending jobs in queue order. Returns completed jobs."""
        ...

    # --- Periodic execution ---

    def start(self) -> None:
        """
        Start the periodic scheduler in a background thread.

        Checks every 60 seconds whether any schedule is due for execution.
        A schedule is due when: now - last_run >= interval_seconds.
        """
        ...

    def stop(self) -> None:
        """Stop the periodic scheduler."""
        ...

    # --- Status queries ---

    def get_job_status(self, job_id: str) -> CollectionJob | None:
        """Get the status of a specific job."""
        ...

    def list_recent_jobs(self, limit: int = 20) -> list[CollectionJob]:
        """List recent jobs, most recent first."""
        ...

    def next_scheduled_run(self, source_type: SourceType) -> datetime | None:
        """Calculate when the next scheduled run will occur."""
        ...
```

### 9.2 Execution Workflow

```
Manual Trigger                              Periodic Tick
     │                                           │
     ▼                                           ▼
trigger_collection()                    _check_schedules()
     │                                           │
     ▼                                           ▼
┌─────────────┐                       ┌───────────────────┐
│ Create Job  │                       │ For each schedule: │
│ (PENDING)   │                       │   if due:          │
└──────┬──────┘                       │     create job     │
       │                              └─────────┬─────────┘
       ▼                                        │
  execute_job()  ◄──────────────────────────────┘
       │
       ├── job.status = RUNNING
       │
       ├── if query: collector.search(query)
       │   └── upsert results to DataStore
       │
       ├── if incremental: tracker.collect_updates()
       │   └── conditional fetch each tracked item
       │
       ├── create CollectionSnapshot (fingerprints of current state)
       │
       ├── compare with previous snapshot via ChangeDetector
       │   └── produce DiffResult → list[ChangeEvent]
       │
       ├── persist ChangeEvents to DataStore
       │
       └── job.status = COMPLETED (or FAILED)
```

### 9.3 Default Schedules

| Source | Default Interval | Query | Notes |
|--------|-----------------|-------|-------|
| GitHub | 1 hour | tracked items only | Incremental; high-activity repos get 15-min refresh via staleness heuristic |
| arXiv | 6 hours | default categories | arXiv updates daily; no benefit to checking more often |

---

## 10. Error Handling & Resilience

### 10.1 Error Hierarchy

All collection errors derive from `NinesError` → `CollectionError` (NFR-20):

```python
class CollectionError(NinesError):
    """Base error for the collection subsystem."""
    pass

class SourceNotFoundError(CollectionError):
    """No collector registered for the requested source type."""
    pass

class RateLimitExceededError(CollectionError):
    """Rate limit hit after all retries exhausted."""
    pass

class AuthenticationError(CollectionError):
    """Invalid or expired authentication credentials."""
    pass

class SourceUnavailableError(CollectionError):
    """Data source is unreachable or returning errors."""
    pass

class ParseError(CollectionError):
    """Failed to parse API response."""
    pass

class StorageError(CollectionError):
    """SQLite operation failed."""
    pass
```

### 10.2 Retry Strategy

Transient HTTP errors (429, 500, 502, 503) trigger automatic retry with exponential back-off (NFR-19):

```
Attempt 1: immediate
Attempt 2: wait 2^1 = 2 seconds
Attempt 3: wait 2^2 = 4 seconds
(max_retries = 3)
```

For 429 responses, the `retry-after` header overrides the exponential delay. For GitHub 403 responses with rate-limit messaging, the collector waits until `x-ratelimit-reset`.

### 10.3 Graceful Degradation

Collection pipeline skips failed sources and returns partial results (NFR-18). A `CollectionResult` always includes a `partial_failures` list:

```python
@dataclass
class CollectionResult:
    """Result of a collection run across one or more sources."""
    source_type: SourceType
    items_collected: int
    items_updated: int
    snapshot: CollectionSnapshot | None
    diff: DiffResult | None
    partial_failures: list[CollectionError]
    duration_ms: float
```

---

## 11. Module Layout

```
src/nines/collector/
├── __init__.py          # Public API: SourceRegistry, collect(), status()
├── protocols.py         # SourceProtocol, SourceType, core types
├── models.py            # Repository, Paper, Article, CollectionSnapshot, ChangeEvent
├── github.py            # GitHubCollector, GitHubConfig
├── arxiv.py             # ArxivCollector, ArxivConfig
├── store.py             # DataStore (SQLite layer)
├── schema.sql           # DDL statements (loaded by DataStore.__init__)
├── tracker.py           # IncrementalTracker, RefreshPolicy
├── diff.py              # ChangeDetector, DiffResult, FieldDiff
├── scheduler.py         # CollectionScheduler, CollectionJob, ScheduleConfig
├── rate_limiter.py      # RateLimiter (token-bucket)
├── cache.py             # ResponseCache (TTL-based, backed by DataStore)
└── errors.py            # CollectionError hierarchy
```

---

## 12. Requirement Traceability

| Requirement | Design Section | Key Component |
|-------------|---------------|---------------|
| **FR-201** GitHub REST | §3 GitHub Collector | `GitHubCollector.search()`, `.fetch()` (REST path) |
| **FR-202** GitHub GraphQL | §3.4 GraphQL Query | `GitHubCollector.fetch()` (GraphQL path), `RepoDeepFetch` query |
| **FR-203** arXiv Collector | §4 arXiv Collector | `ArxivCollector.search()`, `.collect_by_category()` |
| **FR-204** Source Protocol | §2 Source Protocol | `SourceProtocol`, `SourceRegistry`, `SourceItem`, `ChangeEvent` |
| **FR-205** Data Store | §6 SQLite Storage | `DataStore` class, schema DDL, FTS5 virtual tables |
| **FR-206** Rate Limiter | §3.6 Rate Limiting | `RateLimiter`, per-tier calibration, adaptive header reading |
| **FR-207** Incremental Tracking | §7 Incremental Tracking | `IncrementalTracker`, `TrackingBookmark`, fingerprint-based detection |
| **FR-208** Change Detection | §8 Change Detection | `ChangeDetector.compare_snapshots()`, `DiffResult`, categorization rules |
| **FR-209** Collection Status | §6.2 DataStore.get_collection_status() | Aggregate query joining entities + bookmarks |
| **FR-210** Data Export | §6.2 DataStore export methods | `.export_json()`, `.export_csv()`, `.export_markdown()` |
| **FR-211** Source Health Check | §2.2 SourceProtocol.health_check() | Per-source lightweight probe, `HealthStatus` result |
| **FR-212** Local Caching | §6.2 DataStore cache operations | `ResponseCache` with TTL, `cache_get/set/invalidate/cleanup` |
| **NFR-03** GitHub throughput | §3.6 Rate Limiting | Token-bucket calibrated to 50+ entities/min |
| **NFR-04** arXiv throughput | §4.1 ArxivConfig | 3s delay → ~20 entities/min |
| **NFR-13** Source plugin cost | §2.3 SourceRegistry | 1 file implementing `SourceProtocol` + `registry.register()` call |
| **NFR-18** Graceful degradation | §10.3 | `CollectionResult.partial_failures` |
| **NFR-19** Retry transient errors | §10.2 | Exponential back-off, `retry-after` respect |
| **NFR-20** Error hierarchy | §10.1 | `CollectionError` subtree under `NinesError` |

---

*Last modified: 2026-04-11T00:00:00Z*
