# Domain Knowledge Collection — NineS

> **Task**: T04 (Research Team L3) | **Generated**: 2026-04-11 | **Status**: Complete

This document collects domain knowledge across four key technical areas required to build NineS: information retrieval APIs, knowledge decomposition patterns, self-improving system design, and lightweight sandbox solutions. Each section provides concrete technical approaches with runnable code examples.

---

## Table of Contents

1. [Area 1: Information Retrieval APIs](#area-1-information-retrieval-apis)
2. [Area 2: Knowledge Decomposition and Abstraction Patterns](#area-2-knowledge-decomposition-and-abstraction-patterns)
3. [Area 3: Self-Improving System Design Patterns](#area-3-self-improving-system-design-patterns)
4. [Area 4: Lightweight Sandbox Solutions](#area-4-lightweight-sandbox-solutions)

---

## Area 1: Information Retrieval APIs

NineS's information collection subsystem needs to pull data from GitHub (repositories, activity, releases), arXiv (papers), and general web sources (blogs, announcements via RSS). This section covers concrete API usage, authentication, and rate-limiting strategies.

### 1.1 GitHub REST API v3

The REST API is best suited for simple, targeted lookups and paginated list operations.

**Base URL**: `https://api.github.com`
**API Version Header**: `X-GitHub-Api-Version: 2022-11-28` (or `2026-03-10` for latest)

#### Authentication

```python
import httpx

GITHUB_TOKEN = "ghp_..."  # Personal access token or GitHub App token

client = httpx.Client(
    base_url="https://api.github.com",
    headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    },
    timeout=30.0,
)
```

#### Repository Search

Search repositories by topic, language, and minimum star count:

```python
def search_repositories(
    client: httpx.Client,
    query: str,
    sort: str = "stars",
    order: str = "desc",
    per_page: int = 30,
    page: int = 1,
) -> dict:
    """Search GitHub repositories. Returns up to 1000 results total."""
    resp = client.get(
        "/search/repositories",
        params={
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page,
            "page": page,
        },
    )
    resp.raise_for_status()
    return resp.json()

# Search for AI agent evaluation frameworks in Python with 50+ stars
results = search_repositories(
    client,
    query="topic:agent-evaluation language:python stars:>50",
)
for repo in results["items"]:
    print(f"{repo['full_name']}: ★{repo['stargazers_count']} | {repo['description']}")
```

#### Star/Fork/Commit Tracking

Track activity over time for a specific repository:

```python
def get_commit_activity(client: httpx.Client, owner: str, repo: str) -> list[dict]:
    """Weekly commit counts for the last year (52 data points)."""
    resp = client.get(f"/repos/{owner}/{repo}/stats/commit_activity")
    resp.raise_for_status()
    return resp.json()

def get_stargazers_with_dates(
    client: httpx.Client, owner: str, repo: str, per_page: int = 100
) -> list[dict]:
    """Stargazers with timestamps for star-growth tracking."""
    resp = client.get(
        f"/repos/{owner}/{repo}/stargazers",
        headers={"Accept": "application/vnd.github.star+json"},
        params={"per_page": per_page},
    )
    resp.raise_for_status()
    return resp.json()

def get_repo_details(client: httpx.Client, owner: str, repo: str) -> dict:
    """Core metrics: stars, forks, watchers, open issues, language."""
    resp = client.get(f"/repos/{owner}/{repo}")
    resp.raise_for_status()
    data = resp.json()
    return {
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "watchers": data["subscribers_count"],
        "open_issues": data["open_issues_count"],
        "language": data["language"],
        "updated_at": data["updated_at"],
        "pushed_at": data["pushed_at"],
    }
```

#### README Fetching

```python
import base64

def get_readme(client: httpx.Client, owner: str, repo: str) -> str:
    """Fetch decoded README content."""
    resp = client.get(f"/repos/{owner}/{repo}/readme")
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8")
```

#### Release Monitoring

```python
def get_latest_releases(
    client: httpx.Client, owner: str, repo: str, count: int = 5
) -> list[dict]:
    """Fetch recent releases for change tracking."""
    resp = client.get(
        f"/repos/{owner}/{repo}/releases",
        params={"per_page": count},
    )
    resp.raise_for_status()
    return [
        {
            "tag": r["tag_name"],
            "name": r["name"],
            "published_at": r["published_at"],
            "body": r["body"][:500],
        }
        for r in resp.json()
    ]
```

### 1.2 GitHub GraphQL API v4

GraphQL is preferred when NineS needs to fetch multiple related fields in a single request, reducing round-trips and staying within rate limits. GraphQL uses a **point-based** rate limit system (5,000 points/hour) rather than per-request counts.

**Endpoint**: `POST https://api.github.com/graphql`

#### Single Repository Deep Fetch

Retrieve stars, forks, recent commits, and releases in one call:

```python
REPO_DEEP_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    name
    description
    stargazerCount
    forkCount
    primaryLanguage { name }
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 10) {
            totalCount
            nodes {
              messageHeadline
              committedDate
              author { name }
            }
          }
        }
      }
    }
    releases(last: 5, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes { tagName name publishedAt description }
    }
    repositoryTopics(first: 10) {
      nodes { topic { name } }
    }
    issues(states: OPEN) { totalCount }
    pullRequests(states: OPEN) { totalCount }
  }
}
"""

def graphql_query(client: httpx.Client, query: str, variables: dict) -> dict:
    resp = client.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]

result = graphql_query(client, REPO_DEEP_QUERY, {
    "owner": "facebook",
    "name": "react",
})
```

#### Batch Repository Search

Search and compare multiple repositories matching a topic:

```python
SEARCH_QUERY = """
query($searchQuery: String!, $first: Int!) {
  search(query: $searchQuery, type: REPOSITORY, first: $first) {
    repositoryCount
    nodes {
      ... on Repository {
        nameWithOwner
        stargazerCount
        forkCount
        description
        updatedAt
        primaryLanguage { name }
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 1) {
                nodes { committedDate }
              }
            }
          }
        }
      }
    }
  }
}
"""

results = graphql_query(client, SEARCH_QUERY, {
    "searchQuery": "topic:llm-evaluation language:python stars:>100",
    "first": 20,
})
```

#### Multi-Repo Comparison with Fragments

Compare specific repositories side-by-side:

```python
COMPARE_QUERY = """
fragment RepoMetrics on Repository {
  stargazerCount
  forkCount
  issues(states: OPEN) { totalCount }
  pullRequests(states: OPEN) { totalCount }
  releases(last: 1) { nodes { tagName publishedAt } }
}

query {
  swebench: repository(owner: "princeton-nlp", name: "SWE-bench") { ...RepoMetrics }
  humaneval: repository(owner: "openai", name: "human-eval") { ...RepoMetrics }
  bigcode: repository(owner: "bigcode-project", name: "bigcodebench") { ...RepoMetrics }
}
"""
```

### 1.3 arXiv API

arXiv provides an Atom-based API for searching and retrieving paper metadata. NineS uses this to track AI evaluation research.

**Base URL**: `http://export.arxiv.org/api/query`

#### Direct API Usage

```python
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime

import httpx

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}

@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published: datetime
    updated: datetime
    pdf_url: str

def search_arxiv(
    query: str,
    start: int = 0,
    max_results: int = 10,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
) -> list[ArxivPaper]:
    """
    Search arXiv. Query syntax:
      - ti:keyword      (title)
      - au:author        (author)
      - abs:keyword      (abstract)
      - cat:cs.AI        (category)
      - all:keyword      (all fields)
    Combine with AND, OR, ANDNOT.
    """
    params = {
        "search_query": query,
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"http://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

    resp = httpx.get(url, timeout=30.0)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    papers = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        paper = ArxivPaper(
            arxiv_id=entry.find("atom:id", ARXIV_NS).text.split("/abs/")[-1],
            title=entry.find("atom:title", ARXIV_NS).text.strip(),
            authors=[
                a.find("atom:name", ARXIV_NS).text
                for a in entry.findall("atom:author", ARXIV_NS)
            ],
            abstract=entry.find("atom:summary", ARXIV_NS).text.strip(),
            categories=[
                c.get("term")
                for c in entry.findall("{http://arxiv.org/schemas/atom}category")
            ],
            published=datetime.fromisoformat(
                entry.find("atom:published", ARXIV_NS).text.rstrip("Z")
            ),
            updated=datetime.fromisoformat(
                entry.find("atom:updated", ARXIV_NS).text.rstrip("Z")
            ),
            pdf_url=next(
                (
                    link.get("href")
                    for link in entry.findall("atom:link", ARXIV_NS)
                    if link.get("title") == "pdf"
                ),
                "",
            ),
        )
        papers.append(paper)
    return papers

# Search for recent agent evaluation papers in cs.AI
papers = search_arxiv(
    query="cat:cs.AI AND (ti:agent evaluation OR ti:benchmark)",
    max_results=20,
    sort_by="submittedDate",
)
```

#### Using the `arxiv` Python Library

```python
import arxiv

client = arxiv.Client(
    page_size=50,
    delay_seconds=3.0,  # respect rate limits
    num_retries=3,
)

search = arxiv.Search(
    query='ti:"agent evaluation" AND cat:cs.AI',
    max_results=50,
    sort_by=arxiv.SortCriterion.SubmittedDate,
    sort_order=arxiv.SortOrder.Descending,
)

for result in client.results(search):
    print(f"[{result.entry_id}] {result.title}")
    print(f"  Authors: {', '.join(a.name for a in result.authors)}")
    print(f"  Published: {result.published}")
    print(f"  Categories: {result.categories}")
```

#### Bulk Metadata Collection

For NineS's tracking use case, paginate through results with controlled delays:

```python
import time

def collect_all_papers(
    query: str,
    max_total: int = 500,
    page_size: int = 50,
    delay: float = 3.0,
) -> list[ArxivPaper]:
    """Paginated collection respecting arXiv's rate limits (3s between calls)."""
    all_papers: list[ArxivPaper] = []
    for start in range(0, max_total, page_size):
        batch = search_arxiv(query, start=start, max_results=page_size)
        if not batch:
            break
        all_papers.extend(batch)
        if start + page_size < max_total:
            time.sleep(delay)
    return all_papers
```

### 1.4 RSS Feed Parsing

For tracking blog posts, project announcements, and changelogs:

```python
from dataclasses import dataclass
from datetime import datetime

import feedparser

@dataclass
class FeedEntry:
    title: str
    link: str
    published: str
    summary: str
    source_feed: str

def parse_rss_feed(url: str) -> list[FeedEntry]:
    """Parse an RSS/Atom feed and return structured entries."""
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries:
        entries.append(FeedEntry(
            title=entry.get("title", ""),
            link=entry.get("link", ""),
            published=entry.get("published", ""),
            summary=entry.get("summary", "")[:500],
            source_feed=feed.feed.get("title", url),
        ))
    return entries

# Track GitHub release feeds (Atom format)
releases = parse_rss_feed("https://github.com/openai/human-eval/releases.atom")

# Track arXiv new submissions via RSS
arxiv_new = parse_rss_feed("https://rss.arxiv.org/rss/cs.AI")
```

#### Multi-Feed Aggregator

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

TRACKED_FEEDS = [
    "https://github.com/princeton-nlp/SWE-bench/releases.atom",
    "https://github.com/openai/human-eval/releases.atom",
    "https://rss.arxiv.org/rss/cs.AI",
    "https://rss.arxiv.org/rss/cs.SE",
]

def aggregate_feeds(
    feed_urls: list[str],
    max_workers: int = 4,
) -> list[FeedEntry]:
    """Parallel feed fetching with error isolation per feed."""
    all_entries: list[FeedEntry] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(parse_rss_feed, url): url for url in feed_urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                entries = future.result()
                all_entries.extend(entries)
            except Exception as exc:
                import logging
                logging.warning("Feed %s failed: %s", url, exc)
    return sorted(all_entries, key=lambda e: e.published, reverse=True)
```

### 1.5 Rate Limiting Strategies

NineS must respect API rate limits across all data sources. The approach uses a token-bucket algorithm with per-source tracking.

```python
import time
import threading
from dataclasses import dataclass, field

@dataclass
class RateLimiter:
    """Token-bucket rate limiter, thread-safe."""
    max_tokens: float
    refill_rate: float  # tokens per second
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        self._tokens = self.max_tokens
        self._last_refill = time.monotonic()

    def acquire(self, tokens: float = 1.0) -> None:
        """Block until enough tokens are available."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self.max_tokens, self._tokens + elapsed * self.refill_rate)
                self._last_refill = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
            time.sleep(0.1)

# Per-source limiters matching documented rate limits
RATE_LIMITERS = {
    "github_rest_search": RateLimiter(max_tokens=30, refill_rate=30 / 60),      # 30/min
    "github_rest_core": RateLimiter(max_tokens=5000, refill_rate=5000 / 3600),   # 5000/hr
    "github_graphql": RateLimiter(max_tokens=5000, refill_rate=5000 / 3600),     # 5000 pts/hr
    "arxiv": RateLimiter(max_tokens=1, refill_rate=1 / 3),                       # 1 per 3s
}
```

#### Adaptive Back-Off Using Response Headers

```python
def github_request_with_backoff(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """Issue a GitHub API request with rate-limit-aware retry."""
    max_retries = 3
    for attempt in range(max_retries):
        resp = client.request(method, url, **kwargs)

        remaining = int(resp.headers.get("x-ratelimit-remaining", "1"))
        if remaining == 0:
            reset_at = int(resp.headers.get("x-ratelimit-reset", "0"))
            wait = max(0, reset_at - time.time()) + 1
            time.sleep(wait)

        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            reset_at = int(resp.headers.get("x-ratelimit-reset", "0"))
            wait = max(0, reset_at - time.time()) + 1
            time.sleep(wait)
            continue

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("retry-after", "60"))
            time.sleep(retry_after)
            continue

        resp.raise_for_status()
        return resp

    raise RuntimeError(f"Failed after {max_retries} retries: {url}")
```

### 1.6 Authentication Patterns Summary

| Source | Auth Method | Rate Limits (Authenticated) |
|--------|------------|----------------------------|
| GitHub REST | Bearer token (`ghp_...`) or GitHub App JWT | 5,000 req/hr (core), 30 req/min (search) |
| GitHub GraphQL | Bearer token | 5,000 points/hr |
| arXiv | None required | ~1 req/3s (undocumented but enforced) |
| RSS feeds | None required | Varies; respect `Cache-Control` headers |

**Recommended approach for NineS**: Use a GitHub Personal Access Token (fine-grained) for MVP, with scopes limited to `public_repo` read access. Store the token in environment variable `NINES_GITHUB_TOKEN` and load it via the config system.

---

## Area 2: Knowledge Decomposition and Abstraction Patterns

NineS's knowledge analysis engine needs to parse source code, analyze structure, identify architectural patterns, and decompose codebases into reusable knowledge units. This section covers the Python-native tools and algorithms for each step.

### 2.1 AST Analysis in Python

The built-in `ast` module provides full access to Python's abstract syntax tree.

#### Function and Class Extraction

```python
import ast
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class FunctionInfo:
    name: str
    lineno: int
    end_lineno: int
    args: list[str]
    decorators: list[str]
    docstring: str | None
    is_async: bool
    complexity: int = 0

@dataclass
class ClassInfo:
    name: str
    lineno: int
    bases: list[str]
    methods: list[FunctionInfo]
    docstring: str | None

class CodeExtractor(ast.NodeVisitor):
    """Extract functions, classes, and their metadata from Python source."""

    def __init__(self) -> None:
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self.imports: list[str] = []
        self._current_class: ClassInfo | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        info = FunctionInfo(
            name=node.name,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            args=[arg.arg for arg in node.args.args],
            decorators=[ast.dump(d) for d in node.decorator_list],
            docstring=ast.get_docstring(node),
            is_async=False,
            complexity=self._cyclomatic_complexity(node),
        )
        if self._current_class is not None:
            self._current_class.methods.append(info)
        else:
            self.functions.append(info)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # same extraction logic

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        cls = ClassInfo(
            name=node.name,
            lineno=node.lineno,
            bases=[ast.dump(b) for b in node.bases],
            methods=[],
            docstring=ast.get_docstring(node),
        )
        prev = self._current_class
        self._current_class = cls
        self.generic_visit(node)
        self._current_class = prev
        self.classes.append(cls)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")

    @staticmethod
    def _cyclomatic_complexity(node: ast.AST) -> int:
        """McCabe cyclomatic complexity: count decision points + 1."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, (ast.Assert, ast.With)):
                complexity += 1
        return complexity

def analyze_file(path: Path) -> CodeExtractor:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    extractor = CodeExtractor()
    extractor.visit(tree)
    return extractor
```

#### Dependency Graph Construction

Build an intra-project import dependency graph:

```python
from pathlib import Path

def build_dependency_graph(project_root: Path) -> dict[str, set[str]]:
    """
    Map each module to the set of project-internal modules it imports.
    Returns adjacency list: module_path -> {imported_module_paths, ...}
    """
    py_files = list(project_root.rglob("*.py"))
    module_map: dict[str, Path] = {}
    for f in py_files:
        rel = f.relative_to(project_root)
        mod_name = str(rel).replace("/", ".").removesuffix(".py").removesuffix(".__init__")
        module_map[mod_name] = f

    graph: dict[str, set[str]] = {mod: set() for mod in module_map}

    for mod_name, filepath in module_map.items():
        try:
            tree = ast.parse(filepath.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            imported: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = node.module

            if imported is not None:
                for candidate in module_map:
                    if imported == candidate or imported.startswith(candidate + "."):
                        graph[mod_name].add(candidate)
                        break

    return graph
```

#### Coupling Metrics

```python
def compute_coupling_metrics(graph: dict[str, set[str]]) -> dict[str, dict[str, int]]:
    """Afferent (Ca) and efferent (Ce) coupling per module."""
    metrics: dict[str, dict[str, int]] = {}
    for mod in graph:
        ce = len(graph[mod])  # outgoing dependencies
        ca = sum(1 for other in graph if mod in graph[other])  # incoming dependents
        instability = ce / (ca + ce) if (ca + ce) > 0 else 0.0
        metrics[mod] = {"Ca": ca, "Ce": ce, "instability": round(instability, 3)}
    return metrics
```

### 2.2 Directory Structure Analysis

Analyze project layout to detect module boundaries and layering:

```python
from pathlib import Path
from dataclasses import dataclass

@dataclass
class DirectoryNode:
    name: str
    path: Path
    is_package: bool
    children: list["DirectoryNode"]
    py_file_count: int
    total_lines: int

def analyze_directory_structure(root: Path, max_depth: int = 6) -> DirectoryNode:
    """Recursively analyze directory structure and code distribution."""
    def _walk(path: Path, depth: int) -> DirectoryNode:
        children: list[DirectoryNode] = []
        py_count = 0
        total_lines = 0

        if depth < max_depth:
            for child in sorted(path.iterdir()):
                if child.name.startswith((".", "__pycache__", "node_modules")):
                    continue
                if child.is_dir():
                    children.append(_walk(child, depth + 1))
                elif child.suffix == ".py":
                    py_count += 1
                    try:
                        total_lines += len(child.read_text(encoding="utf-8").splitlines())
                    except (OSError, UnicodeDecodeError):
                        pass

        child_py = sum(c.py_file_count for c in children)
        child_lines = sum(c.total_lines for c in children)

        return DirectoryNode(
            name=path.name,
            path=path,
            is_package=(path / "__init__.py").exists(),
            children=children,
            py_file_count=py_count + child_py,
            total_lines=total_lines + child_lines,
        )

    return _walk(root, 0)
```

#### Layer Detection Heuristics

```python
LAYER_INDICATORS = {
    "presentation": {"cli", "api", "web", "ui", "views", "routes", "endpoints", "handlers"},
    "application":  {"services", "usecases", "commands", "orchestrator", "workflows"},
    "domain":       {"models", "entities", "domain", "core", "types"},
    "infrastructure": {"db", "database", "repos", "adapters", "clients", "storage", "external"},
    "testing":      {"tests", "test", "fixtures", "conftest", "mocks"},
}

def detect_layers(root: Path) -> dict[str, list[Path]]:
    """Classify top-level directories into architectural layers."""
    detected: dict[str, list[Path]] = {layer: [] for layer in LAYER_INDICATORS}
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        name_lower = child.name.lower()
        for layer, indicators in LAYER_INDICATORS.items():
            if name_lower in indicators:
                detected[layer].append(child)
    return detected
```

### 2.3 Architecture Pattern Recognition

Detect common architectural patterns from code structure:

```python
@dataclass
class ArchitectureSignal:
    pattern: str
    confidence: float  # 0.0 - 1.0
    evidence: list[str]

def detect_architecture_patterns(
    root: Path,
    dep_graph: dict[str, set[str]],
) -> list[ArchitectureSignal]:
    signals: list[ArchitectureSignal] = []
    dirs = {d.name.lower() for d in root.iterdir() if d.is_dir()}

    # MVC detection
    mvc_dirs = {"models", "views", "controllers"}
    mvc_overlap = mvc_dirs & dirs
    if len(mvc_overlap) >= 2:
        signals.append(ArchitectureSignal(
            pattern="MVC",
            confidence=len(mvc_overlap) / 3,
            evidence=[f"Found directories: {mvc_overlap}"],
        ))

    # Hexagonal / Ports & Adapters detection
    hex_indicators = {"ports", "adapters", "domain", "core"}
    hex_overlap = hex_indicators & dirs
    if len(hex_overlap) >= 2:
        signals.append(ArchitectureSignal(
            pattern="Hexagonal",
            confidence=len(hex_overlap) / 4,
            evidence=[f"Found directories: {hex_overlap}"],
        ))

    # Layered architecture detection
    layer_dirs = {"presentation", "application", "domain", "infrastructure"}
    layer_overlap = layer_dirs & dirs
    if len(layer_overlap) >= 2:
        signals.append(ArchitectureSignal(
            pattern="Layered",
            confidence=len(layer_overlap) / 4,
            evidence=[f"Found directories: {layer_overlap}"],
        ))

    # Microservices indicators
    service_dirs = [d for d in dirs if "service" in d or "svc" in d]
    docker_compose = (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists()
    if len(service_dirs) >= 2 or (docker_compose and len(service_dirs) >= 1):
        signals.append(ArchitectureSignal(
            pattern="Microservices",
            confidence=min(1.0, len(service_dirs) * 0.3 + (0.3 if docker_compose else 0)),
            evidence=[f"Service dirs: {service_dirs}", f"docker-compose: {docker_compose}"],
        ))

    # Plugin / Extension detection (Protocol-based)
    protocol_count = 0
    for mod in dep_graph:
        path = root / mod.replace(".", "/")
        for suffix in [".py", "/__init__.py"]:
            fpath = Path(str(path) + suffix)
            if fpath.exists():
                try:
                    source = fpath.read_text(encoding="utf-8")
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            for base in node.bases:
                                if isinstance(base, ast.Name) and base.id == "Protocol":
                                    protocol_count += 1
                except (SyntaxError, OSError):
                    pass

    if protocol_count >= 3:
        signals.append(ArchitectureSignal(
            pattern="Plugin/Extension",
            confidence=min(1.0, protocol_count * 0.15),
            evidence=[f"Found {protocol_count} Protocol-based interfaces"],
        ))

    return signals
```

### 2.4 Abstraction Strategies

Three decomposition strategies that NineS can apply:

#### Functional Decomposition

Break code into units by what each function/class *does*:

```python
@dataclass
class KnowledgeUnit:
    id: str
    name: str
    category: str  # "function", "class", "module", "pattern"
    abstraction_level: str  # "concrete", "interface", "concept"
    source_path: str
    line_range: tuple[int, int]
    dependencies: list[str]
    description: str
    tags: list[str]

def functional_decomposition(extractor: CodeExtractor, filepath: str) -> list[KnowledgeUnit]:
    """Decompose a file into knowledge units by function/class."""
    units: list[KnowledgeUnit] = []

    for func in extractor.functions:
        units.append(KnowledgeUnit(
            id=f"{filepath}::{func.name}",
            name=func.name,
            category="function",
            abstraction_level="concrete",
            source_path=filepath,
            line_range=(func.lineno, func.end_lineno),
            dependencies=[],  # populated from import analysis
            description=func.docstring or "",
            tags=_infer_tags(func.name, func.docstring),
        ))

    for cls in extractor.classes:
        units.append(KnowledgeUnit(
            id=f"{filepath}::{cls.name}",
            name=cls.name,
            category="class",
            abstraction_level="interface" if _is_abstract(cls) else "concrete",
            source_path=filepath,
            line_range=(cls.lineno, cls.lineno),
            dependencies=cls.bases,
            description=cls.docstring or "",
            tags=_infer_tags(cls.name, cls.docstring),
        ))

    return units

def _infer_tags(name: str, docstring: str | None) -> list[str]:
    """Heuristic tag inference from naming conventions."""
    tags: list[str] = []
    name_lower = name.lower()
    if name_lower.startswith("test"):
        tags.append("test")
    if "parse" in name_lower or "extract" in name_lower:
        tags.append("parsing")
    if "score" in name_lower or "eval" in name_lower:
        tags.append("evaluation")
    if name_lower.startswith("_"):
        tags.append("private")
    return tags

def _is_abstract(cls: ClassInfo) -> bool:
    return any("ABC" in b or "Protocol" in b for b in cls.bases)
```

#### Concern-Based Decomposition

Group code units by cross-cutting concern:

```python
CONCERN_PATTERNS = {
    "error_handling": ["except", "raise", "Error", "Exception"],
    "logging":        ["logger", "logging", "log."],
    "validation":     ["validate", "assert", "check", "verify"],
    "serialization":  ["to_dict", "from_dict", "serialize", "deserialize", "json", "toml"],
    "configuration":  ["config", "settings", "options", "defaults"],
    "io":             ["read", "write", "open", "save", "load", "fetch"],
}

def concern_decomposition(
    units: list[KnowledgeUnit],
    source_map: dict[str, str],
) -> dict[str, list[KnowledgeUnit]]:
    """Group knowledge units by their primary concern."""
    grouped: dict[str, list[KnowledgeUnit]] = {c: [] for c in CONCERN_PATTERNS}
    grouped["core_logic"] = []

    for unit in units:
        source = source_map.get(unit.source_path, "")
        start, end = unit.line_range
        snippet = "\n".join(source.splitlines()[start - 1 : end])

        matched = False
        for concern, patterns in CONCERN_PATTERNS.items():
            if any(p in snippet for p in patterns):
                grouped[concern].append(unit)
                matched = True
                break

        if not matched:
            grouped["core_logic"].append(unit)

    return grouped
```

#### Layer-Based Decomposition

Assign units to architectural layers based on their position and dependencies:

```python
def layer_decomposition(
    units: list[KnowledgeUnit],
    dep_graph: dict[str, set[str]],
) -> dict[str, list[KnowledgeUnit]]:
    """Assign units to layers using dependency direction analysis."""
    layer_assignment: dict[str, list[KnowledgeUnit]] = {
        "interface": [],    # entry points, protocols
        "application": [],  # orchestration, use cases
        "domain": [],       # core business logic
        "infrastructure": [],  # I/O, external services
    }

    for unit in units:
        if unit.abstraction_level == "interface":
            layer_assignment["interface"].append(unit)
        elif "io" in unit.tags or "fetch" in unit.name.lower():
            layer_assignment["infrastructure"].append(unit)
        elif any(kw in unit.name.lower() for kw in ("run", "execute", "pipeline", "orchestrat")):
            layer_assignment["application"].append(unit)
        else:
            layer_assignment["domain"].append(unit)

    return layer_assignment
```

---

## Area 3: Self-Improving System Design Patterns

NineS aims to be a self-iterating tool that measures its own performance, identifies gaps, and plans improvements. This section covers the feedback loop architecture, convergence detection methods, and version-over-version comparison.

### 3.1 Feedback Loop Architecture

The core MAPIM (Measure → Analyze → Plan → Improve → Measure) loop:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class IterationPhase(Enum):
    MEASURE = "measure"
    ANALYZE = "analyze"
    PLAN = "plan"
    IMPROVE = "improve"

@dataclass
class MeasurementSnapshot:
    version: str
    timestamp: datetime
    metrics: dict[str, float]
    dimensions: dict[str, dict[str, float]]

@dataclass
class GapAnalysis:
    dimension: str
    current_score: float
    target_score: float
    gap: float
    severity: str  # "critical", "major", "minor", "acceptable"
    root_causes: list[str]

@dataclass
class ImprovementPlan:
    version: str
    gaps: list[GapAnalysis]
    actions: list["ImprovementAction"]
    priority_order: list[str]
    estimated_impact: dict[str, float]

@dataclass
class ImprovementAction:
    id: str
    target_dimension: str
    description: str
    priority: int
    estimated_effort: str  # "small", "medium", "large"
    expected_metric_delta: dict[str, float]

class SelfImprovementLoop:
    """Orchestrates the MAPIM feedback loop."""

    def __init__(
        self,
        measurer: "Measurer",
        analyzer: "GapAnalyzer",
        planner: "ImprovementPlanner",
        history: list[MeasurementSnapshot] = None,
    ) -> None:
        self.measurer = measurer
        self.analyzer = analyzer
        self.planner = planner
        self.history: list[MeasurementSnapshot] = history or []

    def run_iteration(self, version: str) -> ImprovementPlan:
        snapshot = self.measurer.measure(version)
        self.history.append(snapshot)

        baseline = self.history[0] if len(self.history) > 1 else None
        gaps = self.analyzer.analyze(snapshot, baseline)

        plan = self.planner.plan(gaps, self.history)
        return plan

    def has_converged(self, window: int = 5, threshold: float = 0.01) -> bool:
        """Check if recent iterations show diminishing returns."""
        if len(self.history) < window:
            return False
        recent = self.history[-window:]
        deltas = []
        for i in range(1, len(recent)):
            prev_avg = sum(recent[i - 1].metrics.values()) / len(recent[i - 1].metrics)
            curr_avg = sum(recent[i].metrics.values()) / len(recent[i].metrics)
            deltas.append(abs(curr_avg - prev_avg))
        return max(deltas) < threshold


class Measurer(ABC):
    @abstractmethod
    def measure(self, version: str) -> MeasurementSnapshot: ...

class GapAnalyzer(ABC):
    @abstractmethod
    def analyze(
        self, current: MeasurementSnapshot, baseline: MeasurementSnapshot | None
    ) -> list[GapAnalysis]: ...

class ImprovementPlanner(ABC):
    @abstractmethod
    def plan(
        self, gaps: list[GapAnalysis], history: list[MeasurementSnapshot]
    ) -> ImprovementPlan: ...
```

### 3.2 Meta-Learning Concepts for Tool Improvement

Meta-learning ("learning to learn") applies to NineS as a system that can improve its own evaluation and analysis strategies.

**Key applicable concepts:**

```python
@dataclass
class StrategyPerformance:
    strategy_id: str
    task_type: str
    success_rate: float
    avg_score: float
    sample_count: int

class StrategySelector:
    """
    Select the best analysis/evaluation strategy based on accumulated performance data.
    Implements a simplified multi-armed bandit (epsilon-greedy) approach.
    """

    def __init__(self, epsilon: float = 0.1) -> None:
        self.epsilon = epsilon
        self.performance: dict[str, list[StrategyPerformance]] = {}

    def record(self, perf: StrategyPerformance) -> None:
        self.performance.setdefault(perf.strategy_id, []).append(perf)

    def select(self, task_type: str, available_strategies: list[str]) -> str:
        """Epsilon-greedy selection: exploit best known strategy, explore with probability epsilon."""
        import random

        if random.random() < self.epsilon:
            return random.choice(available_strategies)

        best_strategy = available_strategies[0]
        best_score = -1.0
        for strategy in available_strategies:
            records = [
                p for p in self.performance.get(strategy, [])
                if p.task_type == task_type
            ]
            if records:
                avg = sum(r.avg_score for r in records) / len(records)
                if avg > best_score:
                    best_score = avg
                    best_strategy = strategy

        return best_strategy

    def get_improvement_rate(self, strategy_id: str) -> float | None:
        """Compute the learning rate: how much a strategy improves over time."""
        records = self.performance.get(strategy_id, [])
        if len(records) < 2:
            return None
        first_half = records[: len(records) // 2]
        second_half = records[len(records) // 2 :]
        avg_first = sum(r.avg_score for r in first_half) / len(first_half)
        avg_second = sum(r.avg_score for r in second_half) / len(second_half)
        return (avg_second - avg_first) / max(avg_first, 1e-6)
```

### 3.3 Auto-Curriculum: Progressively Harder Evaluation Tasks

NineS should generate evaluation tasks of increasing difficulty to push its own capabilities:

```python
@dataclass
class DifficultyLevel:
    level: int
    name: str
    criteria: dict[str, float]

DIFFICULTY_SCALE = [
    DifficultyLevel(1, "trivial", {"max_files": 1, "max_complexity": 5, "max_dependencies": 0}),
    DifficultyLevel(2, "simple", {"max_files": 3, "max_complexity": 10, "max_dependencies": 2}),
    DifficultyLevel(3, "moderate", {"max_files": 10, "max_complexity": 20, "max_dependencies": 5}),
    DifficultyLevel(4, "complex", {"max_files": 30, "max_complexity": 50, "max_dependencies": 15}),
    DifficultyLevel(5, "expert", {"max_files": 100, "max_complexity": 100, "max_dependencies": 50}),
]

class AutoCurriculumGenerator:
    """Generate evaluation tasks at the appropriate difficulty level."""

    def __init__(self, mastery_threshold: float = 0.85) -> None:
        self.mastery_threshold = mastery_threshold
        self.level_scores: dict[int, list[float]] = {}

    def record_score(self, level: int, score: float) -> None:
        self.level_scores.setdefault(level, []).append(score)

    def current_level(self) -> int:
        """Find the highest level where mastery has been demonstrated."""
        for level_def in reversed(DIFFICULTY_SCALE):
            scores = self.level_scores.get(level_def.level, [])
            if len(scores) >= 3:
                recent_avg = sum(scores[-3:]) / 3
                if recent_avg >= self.mastery_threshold:
                    next_level = min(level_def.level + 1, DIFFICULTY_SCALE[-1].level)
                    return next_level
        return 1

    def should_advance(self) -> bool:
        """Check if performance at current level justifies advancement."""
        level = self.current_level()
        scores = self.level_scores.get(level, [])
        if len(scores) < 3:
            return False
        return sum(scores[-3:]) / 3 >= self.mastery_threshold
```

### 3.4 Convergence Detection

Statistical methods to determine when improvement has plateaued. This is critical for NineS to know when a particular self-improvement cycle should terminate.

#### Method 1: Sliding Window Variance

```python
import math

def sliding_window_convergence(
    scores: list[float],
    window_size: int = 5,
    variance_threshold: float = 0.001,
) -> bool:
    """
    Converged = the variance of the last `window_size` scores is below threshold.
    Works well for metrics that stabilize around a value.
    """
    if len(scores) < window_size:
        return False
    window = scores[-window_size:]
    mean = sum(window) / len(window)
    variance = sum((x - mean) ** 2 for x in window) / len(window)
    return variance < variance_threshold
```

#### Method 2: Relative Improvement Rate

```python
def relative_improvement_convergence(
    scores: list[float],
    window_size: int = 3,
    min_improvement: float = 0.005,
) -> bool:
    """
    Converged = average relative improvement over last `window_size` steps
    is below `min_improvement` (0.5% default).
    """
    if len(scores) < window_size + 1:
        return False
    improvements = []
    for i in range(-window_size, 0):
        prev = scores[i - 1]
        curr = scores[i]
        if prev != 0:
            improvements.append((curr - prev) / abs(prev))
        else:
            improvements.append(0.0)
    avg_improvement = sum(improvements) / len(improvements)
    return avg_improvement < min_improvement
```

#### Method 3: Mann-Kendall Trend Test

A non-parametric statistical test to determine if there's a monotonic trend:

```python
def mann_kendall_trend(scores: list[float]) -> tuple[float, bool]:
    """
    Mann-Kendall trend test.
    Returns (tau statistic, has_significant_trend).
    tau ≈ 0 and no significant trend → convergence.
    """
    n = len(scores)
    if n < 4:
        return 0.0, False

    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = scores[j] - scores[i]
            if diff > 0:
                s += 1
            elif diff < 0:
                s -= 1

    tau = s / (n * (n - 1) / 2)

    variance_s = n * (n - 1) * (2 * n + 5) / 18
    if s > 0:
        z = (s - 1) / math.sqrt(variance_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(variance_s)
    else:
        z = 0.0

    significant = abs(z) > 1.96  # 95% confidence
    return tau, significant

def is_converged_mk(scores: list[float], window: int = 10) -> bool:
    """Use Mann-Kendall test on recent window to detect convergence."""
    if len(scores) < window:
        return False
    recent = scores[-window:]
    tau, significant = mann_kendall_trend(recent)
    return not significant  # no significant trend = converged
```

#### Method 4: CUSUM (Cumulative Sum) Change Detection

Detect if recent scores have shifted from the running mean, indicating active improvement or degradation:

```python
def cusum_change_detected(
    scores: list[float],
    threshold: float = 1.0,
    drift: float = 0.5,
) -> bool:
    """
    CUSUM change detection. Returns True if a change (improvement or regression)
    is ongoing. Returns False when the process is stable (converged).
    """
    if len(scores) < 5:
        return True  # not enough data

    target = sum(scores[:5]) / 5  # reference mean from initial window
    s_pos = 0.0
    s_neg = 0.0

    for x in scores[5:]:
        s_pos = max(0, s_pos + (x - target) - drift)
        s_neg = max(0, s_neg - (x - target) - drift)

    return s_pos > threshold or s_neg > threshold
```

#### Composite Convergence Checker

NineS should combine multiple methods for robust convergence detection:

```python
@dataclass
class ConvergenceReport:
    is_converged: bool
    confidence: float
    methods_agreeing: int
    total_methods: int
    details: dict[str, bool]

def composite_convergence_check(
    scores: list[float],
    window: int = 5,
) -> ConvergenceReport:
    """Combine multiple statistical methods for robust convergence detection."""
    checks = {
        "sliding_variance": sliding_window_convergence(scores, window_size=window),
        "relative_improvement": relative_improvement_convergence(scores, window_size=min(3, window)),
        "mann_kendall": is_converged_mk(scores, window=max(window, 4)),
        "cusum_stable": not cusum_change_detected(scores),
    }
    agreeing = sum(checks.values())
    total = len(checks)
    return ConvergenceReport(
        is_converged=agreeing >= 3,  # majority vote
        confidence=agreeing / total,
        methods_agreeing=agreeing,
        total_methods=total,
        details=checks,
    )
```

### 3.5 Version-over-Version Comparison

Compare NineS performance across releases:

```python
from dataclasses import dataclass

@dataclass
class VersionComparison:
    base_version: str
    target_version: str
    improved: list[tuple[str, float, float]]   # (metric, old, new) where new > old
    regressed: list[tuple[str, float, float]]   # (metric, old, new) where new < old
    unchanged: list[tuple[str, float, float]]   # within tolerance
    overall_delta: float

def compare_versions(
    base: MeasurementSnapshot,
    target: MeasurementSnapshot,
    tolerance: float = 0.01,
) -> VersionComparison:
    """Compare two version snapshots, classifying each metric as improved/regressed/unchanged."""
    improved, regressed, unchanged = [], [], []

    all_keys = set(base.metrics) | set(target.metrics)
    for key in sorted(all_keys):
        old_val = base.metrics.get(key, 0.0)
        new_val = target.metrics.get(key, 0.0)
        delta = new_val - old_val

        if abs(delta) <= tolerance:
            unchanged.append((key, old_val, new_val))
        elif delta > 0:
            improved.append((key, old_val, new_val))
        else:
            regressed.append((key, old_val, new_val))

    old_avg = sum(base.metrics.values()) / max(len(base.metrics), 1)
    new_avg = sum(target.metrics.values()) / max(len(target.metrics), 1)
    overall_delta = (new_avg - old_avg) / max(abs(old_avg), 1e-6)

    return VersionComparison(
        base_version=base.version,
        target_version=target.version,
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        overall_delta=overall_delta,
    )

def generate_regression_report(comparison: VersionComparison) -> str:
    """Generate a human-readable regression report."""
    lines = [
        f"# Version Comparison: {comparison.base_version} → {comparison.target_version}",
        f"Overall delta: {comparison.overall_delta:+.2%}",
        "",
    ]
    if comparison.regressed:
        lines.append("## ⚠ Regressions")
        for metric, old, new in comparison.regressed:
            lines.append(f"- **{metric}**: {old:.4f} → {new:.4f} ({new - old:+.4f})")
        lines.append("")

    if comparison.improved:
        lines.append("## ✓ Improvements")
        for metric, old, new in comparison.improved:
            lines.append(f"- **{metric}**: {old:.4f} → {new:.4f} ({new - old:+.4f})")
        lines.append("")

    lines.append(f"## Summary: {len(comparison.improved)} improved, "
                 f"{len(comparison.regressed)} regressed, "
                 f"{len(comparison.unchanged)} unchanged")
    return "\n".join(lines)
```

---

## Area 4: Lightweight Sandbox Solutions

NineS needs isolated execution environments for running evaluations without polluting the host system. The design uses a layered approach: process isolation via `subprocess`, filesystem isolation via `tempfile`, and Python environment isolation via `venv`.

### 4.1 Python `venv` Creation and Management (Programmatic)

```python
import venv
import subprocess
import sys
from pathlib import Path

class VenvFactory:
    """Create and manage isolated Python virtual environments."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, name: str, requirements: list[str] | None = None) -> Path:
        """Create a venv and optionally install requirements."""
        venv_path = self.base_dir / name
        builder = venv.EnvBuilder(
            system_site_packages=False,
            clear=True,
            with_pip=True,
        )
        builder.create(str(venv_path))

        if requirements:
            pip = self._pip_path(venv_path)
            subprocess.run(
                [str(pip), "install", "--quiet", *requirements],
                check=True,
                capture_output=True,
                timeout=120,
            )

        return venv_path

    def destroy(self, name: str) -> None:
        """Remove a venv completely."""
        import shutil
        venv_path = self.base_dir / name
        if venv_path.exists():
            shutil.rmtree(venv_path)

    def python_path(self, venv_path: Path) -> Path:
        """Get the Python interpreter path for a venv."""
        if sys.platform == "win32":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"

    def _pip_path(self, venv_path: Path) -> Path:
        if sys.platform == "win32":
            return venv_path / "Scripts" / "pip.exe"
        return venv_path / "bin" / "pip"

    def list_installed(self, venv_path: Path) -> list[str]:
        """List packages installed in the venv."""
        pip = self._pip_path(venv_path)
        result = subprocess.run(
            [str(pip), "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().splitlines()
```

### 4.2 `subprocess` Isolation

Run evaluation code in isolated processes with resource limits:

```python
import subprocess
import json
import os
import signal
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool
    memory_exceeded: bool

def run_isolated(
    python_path: str,
    script_path: str,
    working_dir: str,
    timeout_seconds: int = 30,
    max_memory_mb: int = 512,
    env_override: dict[str, str] | None = None,
    seed: int | None = None,
) -> ExecutionResult:
    """
    Run a Python script in a subprocess with timeout and memory constraints.

    Uses resource limits via preexec_fn on Linux to cap memory usage.
    """
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = str(seed) if seed is not None else "0"

    if seed is not None:
        env["NINES_SEED"] = str(seed)

    if env_override:
        env.update(env_override)

    def set_limits() -> None:
        """Set memory limits via resource module (Linux only)."""
        try:
            import resource
            mem_bytes = max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ImportError, ValueError):
            pass  # not available on this platform

    import time
    start = time.monotonic()
    timed_out = False
    memory_exceeded = False

    try:
        proc = subprocess.run(
            [python_path, script_path],
            cwd=working_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            preexec_fn=set_limits,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
    except MemoryError:
        memory_exceeded = True
        exit_code = -2
        stdout = ""
        stderr = "MemoryError: exceeded limit"

    duration_ms = (time.monotonic() - start) * 1000

    return ExecutionResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
        memory_exceeded=memory_exceeded,
    )
```

### 4.3 `tempfile`/`tmpdir` Strategies for Filesystem Isolation

```python
import tempfile
import shutil
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def isolated_workspace(
    prefix: str = "nines_sandbox_",
    copy_files: dict[str, str] | None = None,
):
    """
    Context manager providing an isolated temporary workspace.
    Cleans up on exit. Yields a Path to the workspace root.

    copy_files: {destination_relative_path: source_path}
    """
    tmpdir = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        if copy_files:
            for dest_rel, src_path in copy_files.items():
                dest = tmpdir / dest_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                src = Path(src_path)
                if src.is_dir():
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)

        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# Usage:
# with isolated_workspace(copy_files={"task.py": "/path/to/task.py"}) as ws:
#     result = run_isolated(python, str(ws / "task.py"), str(ws))
```

#### Full Sandbox Manager

```python
from dataclasses import dataclass, field
from pathlib import Path
import uuid

@dataclass
class SandboxConfig:
    timeout_seconds: int = 30
    max_memory_mb: int = 512
    requirements: list[str] = field(default_factory=list)
    seed: int | None = None
    keep_on_failure: bool = False

@dataclass
class Sandbox:
    id: str
    workspace: Path
    venv_path: Path
    config: SandboxConfig

class SandboxManager:
    """Lifecycle management for isolated execution sandboxes."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(tempfile.gettempdir()) / "nines_sandboxes"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.venv_factory = VenvFactory(self.base_dir / "venvs")
        self._active: dict[str, Sandbox] = {}

    def create(self, config: SandboxConfig | None = None) -> Sandbox:
        """Create a new sandbox with isolated workspace and venv."""
        config = config or SandboxConfig()
        sandbox_id = uuid.uuid4().hex[:12]

        workspace = self.base_dir / "workspaces" / sandbox_id
        workspace.mkdir(parents=True, exist_ok=True)

        venv_path = self.venv_factory.create(
            name=sandbox_id,
            requirements=config.requirements,
        )

        sandbox = Sandbox(
            id=sandbox_id,
            workspace=workspace,
            venv_path=venv_path,
            config=config,
        )
        self._active[sandbox_id] = sandbox
        return sandbox

    def execute(self, sandbox: Sandbox, script_content: str) -> ExecutionResult:
        """Write and execute a script inside the sandbox."""
        script_path = sandbox.workspace / "run.py"
        script_path.write_text(script_content, encoding="utf-8")

        python = str(self.venv_factory.python_path(sandbox.venv_path))
        return run_isolated(
            python_path=python,
            script_path=str(script_path),
            working_dir=str(sandbox.workspace),
            timeout_seconds=sandbox.config.timeout_seconds,
            max_memory_mb=sandbox.config.max_memory_mb,
            seed=sandbox.config.seed,
        )

    def destroy(self, sandbox_id: str) -> None:
        """Clean up all sandbox resources."""
        sandbox = self._active.pop(sandbox_id, None)
        if sandbox is None:
            return
        shutil.rmtree(sandbox.workspace, ignore_errors=True)
        self.venv_factory.destroy(sandbox_id)

    def destroy_all(self) -> None:
        for sid in list(self._active):
            self.destroy(sid)
```

### 4.4 Seed Control for Deterministic Execution

```python
import hashlib
import json

def deterministic_env(seed: int) -> dict[str, str]:
    """Environment variables to maximize deterministic behavior."""
    return {
        "PYTHONHASHSEED": str(seed),
        "NINES_SEED": str(seed),
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",  # deterministic CUDA
        "TF_DETERMINISTIC_OPS": "1",
    }

def seed_init_snippet(seed: int) -> str:
    """Python code to prepend to evaluation scripts for seed control."""
    return f"""\
import random
import os

_SEED = int(os.environ.get("NINES_SEED", {seed}))
random.seed(_SEED)

try:
    import numpy as np
    np.random.seed(_SEED)
except ImportError:
    pass

try:
    import torch
    torch.manual_seed(_SEED)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
except ImportError:
    pass
"""

def result_fingerprint(result: ExecutionResult) -> str:
    """Compute a deterministic hash of execution output for comparison."""
    content = json.dumps({
        "exit_code": result.exit_code,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()
```

### 4.5 Pollution Detection

Verify that sandbox execution didn't modify the host environment:

```python
import os
import hashlib
from pathlib import Path
from dataclasses import dataclass

@dataclass
class EnvironmentSnapshot:
    """Snapshot of observable host state before/after sandbox execution."""
    env_vars: dict[str, str]
    watched_file_hashes: dict[str, str]
    watched_dir_listings: dict[str, list[str]]
    python_path: list[str]

def take_snapshot(
    watched_dirs: list[Path] | None = None,
    watched_files: list[Path] | None = None,
) -> EnvironmentSnapshot:
    """Capture current host environment state."""
    file_hashes: dict[str, str] = {}
    for f in (watched_files or []):
        if f.exists():
            file_hashes[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()

    dir_listings: dict[str, list[str]] = {}
    for d in (watched_dirs or []):
        if d.exists():
            dir_listings[str(d)] = sorted(str(p) for p in d.rglob("*"))

    return EnvironmentSnapshot(
        env_vars=dict(os.environ),
        watched_file_hashes=file_hashes,
        watched_dir_listings=dir_listings,
        python_path=list(sys.path),
    )

@dataclass
class PollutionReport:
    clean: bool
    env_var_changes: list[str]
    file_changes: list[str]
    dir_changes: list[str]
    path_changes: list[str]

def detect_pollution(
    before: EnvironmentSnapshot,
    after: EnvironmentSnapshot,
) -> PollutionReport:
    """Compare two snapshots to detect host environment changes."""
    env_changes: list[str] = []
    for key in set(before.env_vars) | set(after.env_vars):
        old = before.env_vars.get(key)
        new = after.env_vars.get(key)
        if old != new:
            env_changes.append(f"{key}: {old!r} → {new!r}")

    file_changes: list[str] = []
    for path in set(before.watched_file_hashes) | set(after.watched_file_hashes):
        old_hash = before.watched_file_hashes.get(path)
        new_hash = after.watched_file_hashes.get(path)
        if old_hash != new_hash:
            if old_hash is None:
                file_changes.append(f"CREATED: {path}")
            elif new_hash is None:
                file_changes.append(f"DELETED: {path}")
            else:
                file_changes.append(f"MODIFIED: {path}")

    dir_changes: list[str] = []
    for d in set(before.watched_dir_listings) | set(after.watched_dir_listings):
        old_listing = set(before.watched_dir_listings.get(d, []))
        new_listing = set(after.watched_dir_listings.get(d, []))
        added = new_listing - old_listing
        removed = old_listing - new_listing
        if added:
            dir_changes.append(f"ADDED in {d}: {added}")
        if removed:
            dir_changes.append(f"REMOVED in {d}: {removed}")

    path_changes = []
    if before.python_path != after.python_path:
        added = set(after.python_path) - set(before.python_path)
        removed = set(before.python_path) - set(after.python_path)
        if added:
            path_changes.append(f"sys.path ADDED: {added}")
        if removed:
            path_changes.append(f"sys.path REMOVED: {removed}")

    return PollutionReport(
        clean=not (env_changes or file_changes or dir_changes or path_changes),
        env_var_changes=env_changes,
        file_changes=file_changes,
        dir_changes=dir_changes,
        path_changes=path_changes,
    )
```

#### Integrated Pollution-Checked Execution

```python
def execute_with_pollution_check(
    sandbox_manager: SandboxManager,
    sandbox: Sandbox,
    script: str,
    watched_dirs: list[Path] | None = None,
    watched_files: list[Path] | None = None,
) -> tuple[ExecutionResult, PollutionReport]:
    """Execute in sandbox and verify no host pollution occurred."""
    before = take_snapshot(watched_dirs=watched_dirs, watched_files=watched_files)
    result = sandbox_manager.execute(sandbox, script)
    after = take_snapshot(watched_dirs=watched_dirs, watched_files=watched_files)

    report = detect_pollution(before, after)
    if not report.clean:
        import logging
        logging.error(
            "Sandbox %s caused host pollution: env=%d, files=%d, dirs=%d, path=%d",
            sandbox.id,
            len(report.env_var_changes),
            len(report.file_changes),
            len(report.dir_changes),
            len(report.path_changes),
        )
    return result, report
```

### 4.6 Multi-Round Re-Test Convergence

Verify result stability by running the same evaluation multiple times:

```python
from dataclasses import dataclass
from collections import Counter
import math

@dataclass
class StabilityReport:
    total_runs: int
    unique_results: int
    dominant_result_count: int
    dominant_fingerprint: str
    is_stable: bool
    stability_ratio: float
    fingerprint_distribution: dict[str, int]

def multi_round_stability_test(
    sandbox_manager: SandboxManager,
    config: SandboxConfig,
    script: str,
    rounds: int = 5,
    stability_threshold: float = 1.0,
) -> StabilityReport:
    """
    Run the same script multiple times and verify output convergence.

    Args:
        stability_threshold: Fraction of runs that must produce identical output.
            1.0 = all runs must match (strict determinism).
            0.8 = 80% of runs must agree (allows minor non-determinism).
    """
    fingerprints: list[str] = []

    for _ in range(rounds):
        sandbox = sandbox_manager.create(config)
        try:
            result = sandbox_manager.execute(sandbox, script)
            fp = result_fingerprint(result)
            fingerprints.append(fp)
        finally:
            sandbox_manager.destroy(sandbox.id)

    counts = Counter(fingerprints)
    dominant_fp, dominant_count = counts.most_common(1)[0]

    return StabilityReport(
        total_runs=rounds,
        unique_results=len(counts),
        dominant_result_count=dominant_count,
        dominant_fingerprint=dominant_fp,
        is_stable=(dominant_count / rounds) >= stability_threshold,
        stability_ratio=dominant_count / rounds,
        fingerprint_distribution=dict(counts),
    )

def adaptive_stability_test(
    sandbox_manager: SandboxManager,
    config: SandboxConfig,
    script: str,
    min_rounds: int = 3,
    max_rounds: int = 10,
    confidence: float = 0.95,
) -> StabilityReport:
    """
    Adaptive testing: stop early if results are clearly stable or clearly unstable.
    Uses a sequential probability ratio test (SPRT) approach.
    """
    fingerprints: list[str] = []

    for i in range(max_rounds):
        sandbox = sandbox_manager.create(config)
        try:
            result = sandbox_manager.execute(sandbox, script)
            fingerprints.append(result_fingerprint(result))
        finally:
            sandbox_manager.destroy(sandbox.id)

        if i + 1 >= min_rounds:
            counts = Counter(fingerprints)
            dominant_count = counts.most_common(1)[0][1]
            total = len(fingerprints)

            if dominant_count == total:
                break  # perfectly stable

            # Wilson score lower bound for proportion
            p_hat = dominant_count / total
            z = 1.96  # 95% CI
            denom = 1 + z**2 / total
            center = p_hat + z**2 / (2 * total)
            margin = z * math.sqrt(p_hat * (1 - p_hat) / total + z**2 / (4 * total**2))
            lower_bound = (center - margin) / denom

            if lower_bound >= confidence:
                break  # statistically confident enough

    counts = Counter(fingerprints)
    dominant_fp, dominant_count = counts.most_common(1)[0]

    return StabilityReport(
        total_runs=len(fingerprints),
        unique_results=len(counts),
        dominant_result_count=dominant_count,
        dominant_fingerprint=dominant_fp,
        is_stable=(dominant_count / len(fingerprints)) >= confidence,
        stability_ratio=dominant_count / len(fingerprints),
        fingerprint_distribution=dict(counts),
    )
```

---

## Summary: Key Technical Decisions for NineS

| Area | Recommended Approach | Rationale |
|------|---------------------|-----------|
| GitHub API | GraphQL as primary, REST for simple lookups | Fewer round-trips, single request for complex data |
| arXiv API | `arxiv` Python library + direct API for bulk | Library handles pagination and retries |
| Rate limiting | Token-bucket + response-header adaptation | Respects documented limits while maximizing throughput |
| AST analysis | Built-in `ast` module | Zero dependencies, full Python support |
| Architecture detection | Heuristic multi-signal with confidence scoring | Pragmatic; avoids false positives |
| Decomposition | Three strategies (functional/concern/layer) | Different analyses need different decomposition views |
| Feedback loop | MAPIM with typed intermediate artifacts | Clear phase separation, auditable history |
| Convergence | Composite of 4 statistical methods (majority vote) | Robust against any single method's blind spots |
| Sandbox | `venv` + `subprocess` + `tempfile` (3-layer) | Lightweight, no Docker dependency, sufficient isolation for MVP |
| Determinism | Seed control + output fingerprinting | Verifiable reproducibility without heavyweight tooling |
| Pollution detection | Before/after snapshot diffing | Simple, extensible, covers fs + env + sys.path |
| Stability testing | Adaptive SPRT with Wilson confidence bounds | Minimizes unnecessary re-runs while maintaining statistical rigor |

---

*Last modified: 2026-04-11T00:00:00Z*
