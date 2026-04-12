# Collection Guide (V2)

<!-- auto-updated: version from src/nines/__init__.py -->

NineS V2 discovers, fetches, stores, and tracks external information sources relevant to AI agent research. It supports GitHub repositories and arXiv papers with incremental collection and structured change detection.

---

## Supported Sources

| Source | API | Data Types | Rate Limits |
|--------|-----|-----------|-------------|
| **GitHub** | REST v3 + GraphQL v4 | Repositories, releases, commits, contributors | Search: 30 req/min, Core: 5,000 req/hr |
| **arXiv** | Atom XML API | Papers, metadata, version history | 1 req/3 seconds |

---

## Search and Collection Commands

### GitHub Search

```bash
# Basic search
nines collect github "AI agent evaluation" --limit 20

# Filter by language and stars
nines collect github "LLM benchmark" --limit 50

# Incremental (only new items since last run)
nines collect github "AI agent evaluation" --incremental --store ./data/collections
```

GitHub search translates your query into GitHub search qualifiers. Metadata fetched includes: stars, forks, language, topics, README content, recent commits, and releases.

### arXiv Search

```bash
# Basic search
nines collect arxiv "LLM self-improvement" --limit 10

# Category-specific search
nines collect arxiv "agent evaluation" --limit 20
```

arXiv queries support title (`ti:`), author (`au:`), abstract (`abs:`), and category (`cat:`) prefixes. Default categories: `cs.AI`, `cs.SE`, `cs.CL`, `cs.LG`.

---

## Incremental Tracking

Incremental mode fetches only new or changed items since the last collection run:

```bash
nines collect github "AI agent evaluation" --incremental
```

The tracker maintains bookmarks per source item:

| Source | Bookmark Contents | Change Detection |
|--------|------------------|------------------|
| GitHub | ETag, `pushed_at` timestamp, star count | HTTP conditional requests (304 Not Modified) |
| arXiv | `updated_at` timestamp, paper version | Content fingerprint comparison |

Staleness heuristics adapt refresh intervals based on activity:

- **Active repositories** (pushed within 7 days): 15-minute refresh
- **Inactive repositories**: 24-hour refresh
- **arXiv papers**: 6-hour refresh (arXiv updates daily)

---

## Change Detection

NineS detects and categorizes changes between collection snapshots:

```bash
# View recent changes
nines collect status
```

### Change Categories

| Change Pattern | Category | Significance |
|----------------|----------|--------------|
| New release published | `feature` | High |
| Star count change >20% | `metrics` | High |
| Repository archived | `breaking` | High |
| Paper version bumped | `feature` | High |
| README content changed | `docs` | Medium |
| Star count change ≤20% | `metrics` | Low |
| Topics changed | `docs` | Low |

---

## Data Storage (SQLite)

All collected data is stored in SQLite with full-text search:

```bash
# Default location
data/nines.db

# Override via config
[collect]
store_path = "./data/my_collection.db"
```

### Storage Schema

- **`repositories`** — GitHub repos with metadata, metrics, and JSON sub-data
- **`papers`** — arXiv papers with authors, categories, and abstracts
- **`collection_snapshots`** — Point-in-time state snapshots with fingerprints
- **`change_events`** — Structured diffs between snapshots
- **`tracking_bookmarks`** — Cursor state for incremental collection
- **`response_cache`** — TTL-based response cache

Full-text search (FTS5) is enabled on repository names, descriptions, README content, paper titles, abstracts, and authors.

### Export

```bash
# Export as JSON
nines collect export --format json -o repos.json

# Export as Markdown
nines collect export --format markdown -o repos.md
```

---

## Scheduling

Configure periodic collection with refresh intervals:

```toml
[collect.tracking]
default_refresh_interval = "24h"
```

| Source | Default Interval | Notes |
|--------|-----------------|-------|
| GitHub tracked items | 1 hour | High-activity repos get 15-min via staleness heuristic |
| arXiv categories | 6 hours | arXiv updates daily |

Manual full refresh:

```bash
nines collect github "query" --no-incremental
```

---

## Authentication

### GitHub Token

Set a GitHub Personal Access Token for higher rate limits (5,000 req/hr vs. 60):

```bash
export NINES_GITHUB_TOKEN="ghp_your_token_here"
```

Or configure in `nines.toml`:

```toml
[collect.github]
token = "ghp_your_token_here"  # prefer env var
```

Token resolution order:

1. `NINES_GITHUB_TOKEN` environment variable
2. `NINES_COLLECT_GITHUB_TOKEN` environment variable
3. `nines.toml` config value
4. `gh auth token` output (GitHub CLI fallback)

!!! example "Rate Limiting"
    NineS uses a token-bucket rate limiter calibrated per API tier. When approaching limits (remaining < 10%), it doubles the inter-request interval automatically. HTTP 429 responses trigger backoff using the `retry-after` header.
