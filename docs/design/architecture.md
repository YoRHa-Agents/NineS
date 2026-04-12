# NineS System Architecture

> **Task**: T11 — Core Architecture Design | **Team**: Design L3
> **Input**: `docs/design/requirements.md` (67 FR + 27 NFR), `docs/design/capability_model.md`
> **Consumers**: T12 (Eval Framework), T13 (Info Pipeline), T14 (Analysis Engine), T15 (Self-Iteration), T16 (Sandbox), T17 (Skill Adapter)
> **Last Modified**: 2026-04-11

---

## Table of Contents

1. [Module Layout](#1-module-layout)
2. [Data Flow Diagrams](#2-data-flow-diagrams)
3. [Dependency Graph](#3-dependency-graph)
4. [Configuration Schema](#4-configuration-schema)
5. [Error Handling Strategy](#5-error-handling-strategy)
6. [Logging Architecture](#6-logging-architecture)
7. [Event System](#7-event-system)
8. [Requirement Traceability](#8-requirement-traceability)

---

## 1. Module Layout

### 1.1 Top-Level Package Structure

```
src/nines/
├── __init__.py              # Public API: eval(), collect(), analyze(), self_eval(), iterate(), install()
├── _version.py              # Single-source version string (PEP 440)
│
├── core/                    # Zero-dependency foundation layer
│   ├── __init__.py          # Re-exports: protocols, models, errors, events, config
│   ├── protocols.py         # Protocol classes: Scorer, Executor, Collector, Analyzer, Reporter, Loader
│   ├── models.py            # Shared data models: TaskDefinition, EvalResult, ScoreCard, SourceItem, KnowledgeUnit
│   ├── errors.py            # Error type hierarchy rooted at NinesError
│   ├── events.py            # EventBus, Event, typed event payloads
│   ├── config.py            # NinesConfig: TOML loading, 3-level merge, env var override
│   ├── defaults.toml        # Built-in default configuration values
│   ├── constants.py         # Exit codes, version constraints, magic numbers
│   └── logging.py           # Structured logging setup (structlog configuration)
│
├── eval/                    # V1: Evaluation & Benchmarking
│   ├── __init__.py          # Public: EvalRunner, TaskLoader, ScoreCard
│   ├── runner.py            # EvalRunner: load → sandbox → execute → score → report pipeline
│   ├── loader.py            # TaskLoader: TOML file, directory, glob, parameterized templates
│   ├── scorers.py           # ExactScorer, FuzzyScorer, RubricScorer, CompositeScorer, waterfall judge
│   ├── metrics.py           # pass@k, pass^k, Pass³ estimators, statistical aggregation
│   ├── matrix.py            # MatrixEvaluator: N-axis combinatorial, sampling strategies, budget guards
│   ├── reporters.py         # JSONReporter, MarkdownReporter, BaselineComparator
│   ├── analysis.py          # AxisAnalyzer: per-dimension breakdowns, trend tables
│   └── models.py            # EvalResult, ScoreCard, MatrixCell, ReliabilityMetrics, BudgetState
│
├── collector/               # V2: Information Search & Tracking
│   ├── __init__.py          # Public: collect(), CollectorRegistry
│   ├── github.py            # GitHubCollector: REST search + GraphQL deep fetch
│   ├── arxiv.py             # ArxivCollector: keyword search, pagination, metadata extraction
│   ├── store.py             # DataStore: SQLite CRUD, full-text search, faceted filtering
│   ├── tracker.py           # IncrementalTracker: bookmark/cursor state, refresh scheduling
│   ├── diff.py              # ChangeDetector: snapshot comparison, structured diff, categorization
│   ├── rate_limiter.py      # TokenBucketRateLimiter: per-source calibration, adaptive backoff
│   ├── cache.py             # ResponseCache: local TTL-based caching layer
│   └── models.py            # SourceItem, Repository, Paper, ChangeEvent, TrackingHandle, CollectionResult
│
├── analyzer/                # V3: Knowledge Analysis & Decomposition
│   ├── __init__.py          # Public: analyze(), AnalysisPipeline
│   ├── pipeline.py          # AnalysisPipeline: ingest → parse → analyze → decompose → index
│   ├── reviewer.py          # CodeReviewer: AST extraction, cyclomatic complexity, import resolution
│   ├── structure.py         # StructureAnalyzer: directory layout, module boundaries, layer detection
│   ├── patterns.py          # PatternDetector: architecture pattern recognition with confidence scoring
│   ├── decomposer.py        # Decomposer: functional, concern-based, layer-based strategies
│   ├── indexer.py           # KnowledgeIndex: SQLite-backed storage, keyword + faceted search
│   ├── abstraction.py       # PatternAbstractor: reusable pattern extraction from analyzed code
│   └── models.py            # KnowledgeUnit, FileAnalysis, StructureMap, ArchitecturePattern, CouplingMetrics
│
├── iteration/               # Self-Evaluation & Self-Iteration (MAPIM loop)
│   ├── __init__.py          # Public: self_eval(), iterate(), SelfEvalRunner
│   ├── self_eval.py         # SelfEvalRunner: 19-dimension evaluation suite execution
│   ├── dimensions.py        # DimensionEvaluator: per-dimension measurement logic
│   ├── baseline.py          # BaselineManager: create, store, list, compare, label baselines
│   ├── history.py           # ScoreHistory: time-series storage, trend detection, version comparison
│   ├── gap_detector.py      # GapDetector: current vs target comparison, ranked gap list
│   ├── planner.py           # ImprovementPlanner: ≤3 actions per iteration, action generation
│   ├── convergence.py       # ConvergenceChecker: sliding variance, relative improvement, Mann-Kendall, CUSUM
│   ├── tracker.py           # IterationTracker: MAPIM loop state machine, action lifecycle
│   ├── scoring.py           # AggregateScorer: per-vertex and composite weighted scoring
│   └── models.py            # SelfEvalResult, MeasurementSnapshot, GapAnalysis, ImprovementPlan, IterationResult
│
├── orchestrator/            # Workflow Engine & Cross-Module Coordination
│   ├── __init__.py          # Public: WorkflowEngine, Pipeline
│   ├── engine.py            # WorkflowEngine: multi-step workflow definition and execution
│   ├── pipeline.py          # Pipeline: serial, parallel, conditional stage composition
│   ├── scheduler.py         # StageScheduler: dependency resolution, parallel dispatch
│   ├── artifacts.py         # ArtifactStore: SQLite-backed typed artifact passing between vertices
│   └── models.py            # Workflow, Stage, StageResult, ArtifactRef
│
├── sandbox/                 # Isolation Layer
│   ├── __init__.py          # Public: SandboxManager, IsolatedRunner
│   ├── manager.py           # SandboxManager: lifecycle (create/reuse/destroy), pool management
│   ├── runner.py            # IsolatedRunner: execute task in sandbox, capture output
│   ├── isolation.py         # VenvFactory, TmpdirManager, seed control, resource limits
│   ├── pollution.py         # PollutionDetector: EnvironmentSnapshot, before/after diff
│   └── models.py            # SandboxConfig, ExecutionResult, PollutionReport, ResourceUsage
│
├── skill/                   # Agent Skill Adapters
│   ├── __init__.py          # Public: install(), SkillInstaller
│   ├── manifest.py          # ManifestGenerator: JSON manifest from NinesConfig + version
│   ├── installer.py         # SkillInstaller: install/uninstall orchestration, version management
│   ├── cursor_adapter.py    # CursorSkillEmitter: .cursor/skills/nines/ generation
│   ├── claude_adapter.py    # ClaudeCodeEmitter: .claude/commands/nines/ + CLAUDE.md section
│   ├── templates/           # Jinja2 or string templates for generated skill files
│   │   ├── cursor_skill.md.j2
│   │   ├── cursor_command.md.j2
│   │   ├── claude_command.md.j2
│   │   └── claude_section.md.j2
│   └── models.py            # SkillManifest, InstallResult, AdapterConfig
│
└── cli/                     # CLI Commands (Click/Typer)
    ├── __init__.py
    ├── main.py              # Root group: nines, global options (--config, -v, -q, --format, --no-color)
    ├── formatters.py        # Output formatters: text, JSON, Markdown; structured error rendering
    └── commands/
        ├── __init__.py
        ├── eval.py          # nines eval <TASK_OR_SUITE> [OPTIONS]
        ├── collect.py       # nines collect <SOURCE> <QUERY> [OPTIONS] + subcommands
        ├── analyze.py       # nines analyze <TARGET> [OPTIONS] + subcommands
        ├── self_eval.py     # nines self-eval [OPTIONS] + subcommands
        ├── iterate.py       # nines iterate [OPTIONS] + subcommands
        └── install.py       # nines install [OPTIONS]
```

### 1.2 Module Responsibility Summary

| Module | Vertex | Primary Responsibility | Key Protocols Implemented | FR Coverage |
|--------|--------|----------------------|--------------------------|-------------|
| `core/` | — | Foundation types shared by all modules | Defines all Protocols | FR-511, FR-512, NFR-20 |
| `eval/` | V1 | Task evaluation, scoring, reliability metrics, reporting | `Scorer`, `Loader`, `Reporter` | FR-101–FR-116 |
| `collector/` | V2 | External data discovery, collection, tracking, change detection | `Collector` (via `SourceProtocol`) | FR-201–FR-212 |
| `analyzer/` | V3 | Code analysis, structural decomposition, knowledge indexing | `Analyzer` | FR-301–FR-311 |
| `iteration/` | Cross | Self-evaluation, gap detection, improvement planning, convergence | — | FR-403–FR-412 |
| `orchestrator/` | Cross | Workflow execution, cross-vertex data flow, artifact passing | — | FR-401, FR-402 |
| `sandbox/` | V1 | Process/venv/filesystem isolation for evaluation execution | `Executor` | NFR-09–NFR-12 |
| `skill/` | Delivery | Agent runtime adapter generation and installation | — | FR-506, FR-513–FR-516 |
| `cli/` | Delivery | User-facing command interface | — | FR-501–FR-509 |

### 1.3 Supporting File Structure

```
NineS/
├── pyproject.toml           # uv-managed, PEP 621 metadata, ruff + mypy config
├── nines.toml               # Example project-level configuration
├── Makefile                  # dev shortcuts: make test, make lint, make fmt
├── .python-version           # 3.12
├── .pre-commit-config.yaml   # ruff lint + format hooks
├── src/nines/                # (as above)
├── tests/
│   ├── conftest.py           # Shared fixtures, temp directories, mock factories
│   ├── test_core_*.py
│   ├── test_eval_*.py
│   ├── test_collector_*.py
│   ├── test_analyzer_*.py
│   ├── test_iteration_*.py
│   ├── test_sandbox_*.py
│   ├── test_skill_*.py
│   ├── test_cli_*.py
│   └── integration/
│       ├── test_eval_e2e.py
│       ├── test_collect_analyze.py
│       ├── test_iteration_cycle.py
│       └── test_sandbox_isolation.py
├── data/
│   ├── golden_test_set/      # Curated evaluation tasks with known-correct scores
│   └── baselines/            # Stored self-evaluation baselines
├── docs/
│   ├── design/               # Architecture and design documents
│   └── research/             # Research and analysis documents
└── reports/                  # Generated reports (gitignored)
```

---

## 2. Data Flow Diagrams

### 2.1 Evaluation Flow

The evaluation pipeline transforms task definitions into scored, reported results through a sandboxed execution environment.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVALUATION FLOW (V1)                                │
│                                                                             │
│  Covers: FR-101, FR-102, FR-103–106, FR-107, FR-108–110, FR-112–114       │
└─────────────────────────────────────────────────────────────────────────────┘

  User / Orchestrator
        │
        │  nines eval tasks/coding.toml --scorer composite --sandbox --seed 42
        │
        ▼
  ┌─────────────┐     *.toml files      ┌──────────────┐
  │  CLI Layer   │────────────────────►  │  TaskLoader   │
  │  (cli/eval)  │                       │  (eval/loader) │
  └──────┬───────┘                       └──────┬────────┘
         │                                      │
         │  NinesConfig                         │  list[TaskDefinition]
         │  (scorer, seed, sandbox, format)      │
         ▼                                      ▼
  ┌──────────────────────────────────────────────────┐
  │                    EvalRunner                      │
  │                  (eval/runner.py)                   │
  │                                                    │
  │  for each task in tasks:                           │
  │    ┌──────────────────────────────────────────┐    │
  │    │ 1. SandboxManager.create(seed, timeout)  │    │
  │    │         │                                │    │
  │    │         ▼                                │    │
  │    │    ┌─────────────┐                       │    │
  │    │    │ IsolatedRunner │                     │    │
  │    │    │  • venv setup  │                     │    │
  │    │    │  • tmpdir       │                     │    │
  │    │    │  • seed control │                     │    │
  │    │    │  • execute task │                     │    │
  │    │    └───────┬─────┘                       │    │
  │    │            │ ExecutionResult              │    │
  │    │            ▼                              │    │
  │    │    ┌─────────────────────┐                │    │
  │    │    │ PollutionDetector    │  (FR-116)     │    │
  │    │    │  before/after diff   │                │    │
  │    │    └───────┬─────────────┘                │    │
  │    │            │                              │    │
  │    │ 2. Scorer.score(result, expected)         │    │
  │    │            │                              │    │
  │    │            ▼                              │    │
  │    │    ┌────────────────────────────────┐     │    │
  │    │    │ CompositeScorer (waterfall)     │     │    │
  │    │    │  ExactScorer ──► FuzzyScorer   │     │    │
  │    │    │       ──► RubricScorer          │     │    │
  │    │    └───────┬────────────────────────┘     │    │
  │    │            │ ScoreCard                    │    │
  │    │            ▼                              │    │
  │    │ 3. MetricCollector.record(score, timing)  │    │
  │    │            │                              │    │
  │    │ 4. SandboxManager.destroy()              │    │
  │    │            │                              │    │
  │    │ 5. EventBus.emit(EVAL_TASK_COMPLETE)     │    │
  │    └──────────────────────────────────────────┘    │
  │                                                    │
  │  ── After all tasks ──                             │
  │                                                    │
  │  6. ReliabilityMetrics.compute(pass_k, pass_hat_k) │
  │  7. BudgetGuard.check()  (FR-111)                 │
  │  8. Aggregate into EvalResult                      │
  └──────────────────┬─────────────────────────────────┘
                     │ EvalResult
                     ▼
         ┌───────────────────────┐
         │   Reporter Pipeline    │
         │  ┌─────────────────┐  │
         │  │ JSONReporter    │──┼──► results.json      (FR-112)
         │  │ MarkdownReporter│──┼──► report.md          (FR-113)
         │  │ BaselineCompar. │──┼──► comparison.md      (FR-115)
         │  └─────────────────┘  │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   SQLite Storage       │
         │   (score history)      │
         └───────────────────────┘
```

**Sequence Diagram — Single Task Evaluation**:

```
CLI           EvalRunner     TaskLoader    SandboxMgr   IsolatedRunner   Scorer       Reporter     EventBus
 │                │              │              │              │             │             │            │
 │─eval(cfg)─────►│              │              │              │             │             │            │
 │                │─load(glob)──►│              │              │             │             │            │
 │                │◄─tasks[]─────│              │              │             │             │            │
 │                │                             │              │             │             │            │
 │                │──────create(seed,timeout)───►│              │             │             │            │
 │                │◄─────sandbox────────────────│              │             │             │            │
 │                │                             │              │             │             │            │
 │                │─────────execute(task, sandbox)────────────►│             │             │            │
 │                │                             │              │─run in venv─│             │            │
 │                │                             │              │─capture out─│             │            │
 │                │◄────────ExecutionResult─────────────────────│             │             │            │
 │                │                             │              │             │             │            │
 │                │──────score(exec_result, expected)──────────────────────►│             │            │
 │                │◄─────ScoreCard──────────────────────────────────────────│             │            │
 │                │                             │              │             │             │            │
 │                │──────destroy()──────────────►│              │             │             │            │
 │                │                             │              │             │             │            │
 │                │────────────────emit(EVAL_TASK_COMPLETE, {task_id, score})────────────────────────►│
 │                │                             │              │             │             │            │
 │                │ (repeat for each task)       │              │             │             │            │
 │                │                             │              │             │             │            │
 │                │──────report(eval_result)────────────────────────────────────────────►│            │
 │                │◄─────files[json,md]─────────────────────────────────────────────────│            │
 │◄─EvalResult────│              │              │              │             │             │            │
 │                │              │              │              │             │             │            │
```

### 2.2 Collection Flow

The collection pipeline discovers, fetches, stores, and tracks external information sources.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COLLECTION FLOW (V2)                                 │
│                                                                             │
│  Covers: FR-201–FR-212                                                     │
└─────────────────────────────────────────────────────────────────────────────┘

  User / Orchestrator
        │
        │  nines collect github "AI agent evaluation" --limit 20 --incremental
        │
        ▼
  ┌─────────────┐                        ┌──────────────────┐
  │  CLI Layer   │──────source name──────►│ CollectorRegistry │
  │ (cli/collect)│                        │  (dispatches to   │
  └──────┬───────┘                        │   correct impl)   │
         │                                └────────┬──────────┘
         │  NinesConfig                            │ SourceProtocol impl
         │  (api_keys, rate_limits, cache_ttl)     │
         ▼                                         ▼
  ┌────────────────────────────────────────────────────────────────┐
  │                     Collection Pipeline                         │
  │                                                                 │
  │  ┌─────────────────────────────────────────────────────────┐   │
  │  │ 1. IncrementalTracker.get_bookmark(source)              │   │
  │  │    │                                                    │   │
  │  │    │  bookmark (last_cursor, last_timestamp)            │   │
  │  │    ▼                                                    │   │
  │  │ 2. ResponseCache.check(query_hash)                      │   │
  │  │    │                                                    │   │
  │  │    │  MISS ──────────────────────────┐                  │   │
  │  │    │  HIT ──► return cached ──►(skip 3)                 │   │
  │  │    │                                 │                  │   │
  │  │    ▼                                 ▼                  │   │
  │  │ 3. RateLimiter.acquire(source_tier)                     │   │
  │  │    │                                                    │   │
  │  │    │  ┌─────────────────────────────────────────┐       │   │
  │  │    │  │  Token Bucket (per-source calibration)  │       │   │
  │  │    │  │  GitHub search: 30 req/min              │       │   │
  │  │    │  │  GitHub core:   5000 req/hr             │       │   │
  │  │    │  │  arXiv:         1 req/3s                │       │   │
  │  │    │  │                                         │       │   │
  │  │    │  │  Reads x-ratelimit-remaining header     │       │   │
  │  │    │  │  Adaptive backoff on < 10% remaining    │       │   │
  │  │    │  └─────────────────────────────────────────┘       │   │
  │  │    │                                                    │   │
  │  │    ▼                                                    │   │
  │  │ 4. Collector.search(query, since=bookmark)              │   │
  │  │    │                                                    │   │
  │  │    │  ┌──────────────────┬──────────────────┐           │   │
  │  │    │  │ GitHubCollector  │  ArxivCollector   │           │   │
  │  │    │  │ REST: search     │  arxiv lib: query │           │   │
  │  │    │  │ GraphQL: deep    │  pagination       │           │   │
  │  │    │  └────────┬─────────┴────────┬─────────┘           │   │
  │  │    │           │                  │                     │   │
  │  │    │           ▼                  ▼                     │   │
  │  │    │    list[SourceItem]   list[SourceItem]             │   │
  │  │    ▼                                                    │   │
  │  │ 5. ResponseCache.store(query_hash, items, ttl)          │   │
  │  │    │                                                    │   │
  │  │    ▼                                                    │   │
  │  │ 6. DataStore.upsert(items)                              │   │
  │  │    │                                                    │   │
  │  │    │  SQLite: repositories, papers tables               │   │
  │  │    │  FTS5 index for keyword search                     │   │
  │  │    ▼                                                    │   │
  │  │ 7. IncrementalTracker.update_bookmark(new_cursor)       │   │
  │  │    │                                                    │   │
  │  │    ▼                                                    │   │
  │  │ 8. ChangeDetector.diff(previous_snapshot, current)      │   │
  │  │    │                                                    │   │
  │  │    │  list[ChangeEvent]: new, modified, removed         │   │
  │  │    ▼                                                    │   │
  │  │ 9. EventBus.emit(COLLECTION_COMPLETE, {source, count})  │   │
  │  └─────────────────────────────────────────────────────────┘   │
  │                                                                 │
  └──────────────────────────┬──────────────────────────────────────┘
                             │ CollectionResult
                             ▼
                  ┌─────────────────────┐
                  │  Output / Storage    │
                  │  • SQLite store      │
                  │  • JSON export       │
                  │  • Status table      │
                  └─────────────────────┘
```

**Sequence Diagram — Incremental GitHub Collection**:

```
CLI         Registry    Tracker       Cache     RateLimiter  GitHubColl   DataStore   ChangeDetect  EventBus
 │              │          │            │            │            │            │            │            │
 │─collect(cfg)►│          │            │            │            │            │            │            │
 │              │─resolve──►            │            │            │            │            │            │
 │              │◄─impl────│            │            │            │            │            │            │
 │              │          │            │            │            │            │            │            │
 │              │─get_bookmark(github)──►            │            │            │            │            │
 │              │◄─cursor{since: ts}────│            │            │            │            │            │
 │              │          │            │            │            │            │            │            │
 │              │─check(query_hash)─────────────────►│            │            │            │            │
 │              │◄─MISS────────────────────────────│            │            │            │            │
 │              │          │            │            │            │            │            │            │
 │              │─acquire(github_search)────────────────────────►│            │            │            │
 │              │◄─token_granted─────────────────────────────────│            │            │            │
 │              │          │            │            │            │            │            │            │
 │              │─search(query, since=ts)───────────────────────────────────►│            │            │
 │              │          │            │            │            │            │            │            │
 │              │          │            │            │    (reads x-ratelimit  │            │            │
 │              │          │            │            │     headers, adapts)   │            │            │
 │              │◄─items[]──────────────────────────────────────────────────│            │            │
 │              │          │            │            │            │            │            │            │
 │              │─store(hash, items, ttl)───────────►│            │            │            │            │
 │              │          │            │            │            │            │            │            │
 │              │─upsert(items)────────────────────────────────────────────────────────►│            │
 │              │          │            │            │            │            │            │            │
 │              │─update_bookmark(new_cursor)───────►            │            │            │            │
 │              │          │            │            │            │            │            │            │
 │              │─diff(prev, current)───────────────────────────────────────────────────────────────►│
 │              │◄─changes[]────────────────────────────────────────────────────────────────────────│
 │              │          │            │            │            │            │            │            │
 │              │─emit(COLLECTION_COMPLETE)──────────────────────────────────────────────────────────►│
 │              │          │            │            │            │            │            │            │
 │◄─result──────│          │            │            │            │            │            │            │
```

### 2.3 Analysis Flow

The analysis pipeline ingests source code, parses it into ASTs, decomposes into knowledge units, and indexes them for retrieval.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ANALYSIS FLOW (V3)                                 │
│                                                                             │
│  Covers: FR-301–FR-311                                                     │
└─────────────────────────────────────────────────────────────────────────────┘

  User / Orchestrator
        │
        │  nines analyze ./target-repo --depth deep --decompose --index
        │
        ▼
  ┌─────────────┐                    ┌──────────────────────────┐
  │  CLI Layer   │───target path────►│    AnalysisPipeline       │
  │ (cli/analyze)│                   │    (analyzer/pipeline.py)  │
  └──────────────┘                   └──────────┬───────────────┘
                                                │
         ┌──────────────────────────────────────┘
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                    AnalysisPipeline Stages                        │
  │                                                                   │
  │  ┌──────────────────────────────────────────────────────────┐    │
  │  │ STAGE 1: INGEST                                          │    │
  │  │                                                          │    │
  │  │  • Walk directory tree, discover .py files               │    │
  │  │  • Check file-level cache (mtime comparison)             │    │
  │  │  • Skip unchanged files on re-analysis (FR-310)          │    │
  │  │  • Read source content for changed/new files             │    │
  │  │                                                          │    │
  │  │  Output: list[SourceFile(path, content, mtime)]          │    │
  │  │  Event:  ANALYSIS_FILE_DISCOVERED per file               │    │
  │  └────────────────────────┬─────────────────────────────────┘    │
  │                           │                                      │
  │                           ▼                                      │
  │  ┌──────────────────────────────────────────────────────────┐    │
  │  │ STAGE 2: PARSE (CodeReviewer)                            │    │
  │  │                                                          │    │
  │  │  For each SourceFile (error-isolated — FR-310):          │    │
  │  │  • ast.parse(source) → AST tree                          │    │
  │  │  • Extract: functions, classes, imports (FR-301)          │    │
  │  │  • Compute cyclomatic complexity per function (FR-301)    │    │
  │  │  • On SyntaxError → structured ParseError, continue      │    │
  │  │                                                          │    │
  │  │  Output: list[FileAnalysis(path, functions, classes,     │    │
  │  │               imports, complexity_map)]                   │    │
  │  │  Event:  ANALYSIS_FILE_PARSED per file (FR-311)          │    │
  │  └────────────────────────┬─────────────────────────────────┘    │
  │                           │                                      │
  │                           ▼                                      │
  │  ┌──────────────────────────────────────────────────────────┐    │
  │  │ STAGE 3: ANALYZE (StructureAnalyzer + PatternDetector)   │    │
  │  │                                                          │    │
  │  │  3a. StructureAnalyzer:                                  │    │
  │  │    • Identify module boundaries (__init__.py) (FR-303)   │    │
  │  │    • Detect layers (presentation, business, data)        │    │
  │  │    • Construct module dependency graph                    │    │
  │  │                                                          │    │
  │  │  3b. Multi-file Import Resolution:                       │    │
  │  │    • Resolve cross-file imports → adjacency list (FR-302)│    │
  │  │    • Compute Ca, Ce, instability I = Ce/(Ca+Ce)          │    │
  │  │                                                          │    │
  │  │  3c. PatternDetector:                                    │    │
  │  │    • Architecture pattern recognition (FR-304)           │    │
  │  │    • Confidence scoring per detected pattern             │    │
  │  │                                                          │    │
  │  │  Output: StructureMap, CouplingMetrics,                  │    │
  │  │          list[ArchitecturePattern]                        │    │
  │  └────────────────────────┬─────────────────────────────────┘    │
  │                           │                                      │
  │                           ▼                                      │
  │  ┌──────────────────────────────────────────────────────────┐    │
  │  │ STAGE 4: DECOMPOSE (Decomposer)                          │    │
  │  │                                                          │    │
  │  │  Three strategies applied in sequence:                   │    │
  │  │                                                          │    │
  │  │  4a. Functional decomposition (FR-305):                  │    │
  │  │    • Each function/method → KnowledgeUnit               │    │
  │  │    • Includes: signature, body, docstring, complexity    │    │
  │  │                                                          │    │
  │  │  4b. Concern-based decomposition (FR-306):               │    │
  │  │    • Group by cross-cutting concern                      │    │
  │  │    • Error handling, logging, validation, config          │    │
  │  │                                                          │    │
  │  │  4c. Layer-based decomposition (FR-307):                 │    │
  │  │    • Assign units to architectural layers from Stage 3   │    │
  │  │    • Unassigned → "unclassified"                         │    │
  │  │                                                          │    │
  │  │  Output: list[KnowledgeUnit] (all three strategies)      │    │
  │  │  Event:  ANALYSIS_UNITS_EXTRACTED with count             │    │
  │  └────────────────────────┬─────────────────────────────────┘    │
  │                           │                                      │
  │                           ▼                                      │
  │  ┌──────────────────────────────────────────────────────────┐    │
  │  │ STAGE 5: INDEX (KnowledgeIndex)                          │    │
  │  │                                                          │    │
  │  │  • Store KnowledgeUnits in SQLite with metadata (FR-308) │    │
  │  │  • Build FTS5 index for keyword search                   │    │
  │  │  • Tag with: source, type, complexity, timestamp         │    │
  │  │  • Support faceted filtering (language, type, complexity) │    │
  │  │                                                          │    │
  │  │  Output: index stats (units_stored, patterns_found)      │    │
  │  │  Event:  ANALYSIS_COMPLETE                               │    │
  │  └──────────────────────────────────────────────────────────┘    │
  │                                                                   │
  └───────────────────────────┬───────────────────────────────────────┘
                              │ AnalysisResult
                              ▼
               ┌────────────────────────┐
               │  AnalysisResult         │
               │  • file_analyses[]      │
               │  • structure_map        │
               │  • knowledge_units[]    │
               │  • patterns[]           │
               │  • coupling_metrics     │
               │  • errors[] (isolated)  │
               └────────────────────────┘
```

**Sequence Diagram — Multi-File Analysis with Error Isolation**:

```
CLI         Pipeline    FileCache   CodeReviewer  StructAnalyzer  Decomposer  KnowledgeIdx  EventBus
 │              │           │            │              │              │            │            │
 │─analyze(cfg)►│           │            │              │              │            │            │
 │              │─walk(dir)─►            │              │              │            │            │
 │              │           │            │              │              │            │            │
 │              │─check(f1)►│            │              │              │            │            │
 │              │◄─CHANGED──│            │              │              │            │            │
 │              │─check(f2)►│            │              │              │            │            │
 │              │◄─UNCHANGED│  (skip f2) │              │              │            │            │
 │              │           │            │              │              │            │            │
 │              │─parse(f1)─────────────►│              │              │            │            │
 │              │◄─FileAnalysis──────────│              │              │            │            │
 │              │─emit(FILE_PARSED,f1)───────────────────────────────────────────────────────►│
 │              │           │            │              │              │            │            │
 │              │─parse(f3)─────────────►│              │              │            │            │
 │              │◄─ParseError(f3)────────│  (isolated,  │              │            │            │
 │              │           │            │   continue)  │              │            │            │
 │              │           │            │              │              │            │            │
 │              │─analyze_structure(analyses)──────────►│              │            │            │
 │              │◄─StructureMap, CouplingMetrics────────│              │            │            │
 │              │           │            │              │              │            │            │
 │              │─decompose(analyses, structure)────────────────────►│            │            │
 │              │◄─knowledge_units[]────────────────────────────────│            │            │
 │              │           │            │              │              │            │            │
 │              │─index(units)──────────────────────────────────────────────────►│            │
 │              │◄─stats─────────────────────────────────────────────────────────│            │
 │              │           │            │              │              │            │            │
 │              │─emit(ANALYSIS_COMPLETE)─────────────────────────────────────────────────────►│
 │              │           │            │              │              │            │            │
 │◄─result──────│           │            │              │              │            │            │
```

### 2.4 Cross-Vertex Integration Flow

The orchestrator coordinates data flow between all three vertices through the MAPIM loop.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CROSS-VERTEX INTEGRATION (MAPIM Loop)                     │
│                                                                             │
│  Covers: FR-401, FR-402, FR-403–FR-412                                     │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────── MAPIM Iteration ─────────────────────────────────┐
  │                                                                                       │
  │  ┌─────────┐                                                                          │
  │  │ MEASURE │  SelfEvalRunner executes 19-dimension suite                              │
  │  │ (V1,V2, │  → MeasurementSnapshot stored in SQLite                                 │
  │  │  V3,sys) │  → ScoreHistory.append(snapshot)                                        │
  │  └────┬────┘                                                                          │
  │       │ MeasurementSnapshot                                                           │
  │       ▼                                                                               │
  │  ┌─────────┐                                                                          │
  │  │ ANALYZE │  GapDetector.detect(current=snapshot, target=baseline_or_target)          │
  │  │         │  → ranked list of GapAnalysis {dimension, current, target, gap, priority} │
  │  └────┬────┘                                                                          │
  │       │ list[GapAnalysis]                                                             │
  │       ▼                                                                               │
  │  ┌─────────┐                                                                          │
  │  │  PLAN   │  ImprovementPlanner.plan(gaps, max_actions=3)                            │
  │  │         │  → ImprovementPlan with ≤3 ImprovementActions                            │
  │  │         │  → Each action: type, dimension, expected_delta, description              │
  │  └────┬────┘                                                                          │
  │       │ ImprovementPlan                                                               │
  │       ▼                                                                               │
  │  ┌─────────┐                                                                          │
  │  │ IMPROVE │  Execute actions via cross-vertex data flows:                             │
  │  │         │                                                                          │
  │  │         │  Action targets V1: adjust scorer weights, add eval tasks                │
  │  │         │  Action targets V2: trigger targeted collection (F1 flow)                │
  │  │         │  Action targets V3: queue deeper analysis (F2 flow)                      │
  │  │         │                                                                          │
  │  │         │  Action lifecycle: Proposed → Approved → Applied → Validated/Rejected    │
  │  └────┬────┘                                                                          │
  │       │                                                                               │
  │       ▼                                                                               │
  │  ┌─────────┐                                                                          │
  │  │ MEASURE │  Re-measure affected dimensions                                          │
  │  │ (again) │  → ConvergenceChecker.check(history)                                     │
  │  │         │  → 4-method majority vote: sliding variance, relative improvement,       │
  │  │         │    Mann-Kendall trend, CUSUM change detection                            │
  │  └────┬────┘                                                                          │
  │       │                                                                               │
  │       ▼                                                                               │
  │  ┌───────────────────┐                                                                │
  │  │ CONVERGED?         │                                                                │
  │  │  ≥3/4 methods agree│──YES──► Stop iteration, report final scores                   │
  │  │  improvement halted│                                                                │
  │  └────────┬───────────┘                                                                │
  │           │ NO (and iteration < max_iterations)                                        │
  │           └──────────────────────────── loop back to MEASURE ──────────────────────────┘
  │
  └───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Dependency Graph

### 3.1 Module Dependency Matrix

Arrows indicate "depends on" (import direction). Read as: row module imports from column module.

```
                    core  eval  collector  analyzer  iteration  orchestrator  sandbox  skill  cli
core                 —     ✗       ✗         ✗         ✗          ✗           ✗       ✗     ✗
eval                 ✓     —       ✗         ✗         ✗          ✗           ✗       ✗     ✗
collector            ✓     ✗       —         ✗         ✗          ✗           ✗       ✗     ✗
analyzer             ✓     ✗       ✗         —         ✗          ✗           ✗       ✗     ✗
iteration            ✓     ✓       ✗         ✗         —          ✗           ✗       ✗     ✗
orchestrator         ✓     ✓       ✓         ✓         ✓          —           ✗       ✗     ✗
sandbox              ✓     ✗       ✗         ✗         ✗          ✗           —       ✗     ✗
skill                ✓     ✗       ✗         ✗         ✗          ✗           ✗       —     ✗
cli                  ✓     ✓       ✓         ✓         ✓          ✓           ✓       ✓     —
```

### 3.2 Dependency DAG (Visual)

```
                              ┌──────────┐
                              │   cli/   │  (top-level entry point)
                              └────┬─────┘
                                   │
                   ┌───────────────┼───────────────────────────┐
                   │               │                           │
                   ▼               ▼                           ▼
            ┌────────────┐  ┌──────────────┐           ┌───────────┐
            │   skill/   │  │ orchestrator/ │           │  sandbox/  │
            └─────┬──────┘  └──────┬───────┘           └─────┬─────┘
                  │                │                          │
                  │     ┌──────┬──┴──┬──────────┐            │
                  │     │      │     │          │            │
                  │     ▼      ▼     ▼          ▼            │
                  │  ┌──────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
                  │  │eval/ │ │collect/│ │analyzer/ │ │iteration/│
                  │  └──┬───┘ └───┬────┘ └────┬─────┘ └────┬─────┘
                  │     │         │           │            │
                  │     │         │           │         ┌──┘
                  │     │         │           │         │ (iteration → eval for self-eval)
                  │     │         │           │         │
                  ▼     ▼         ▼           ▼         ▼
               ┌──────────────────────────────────────────────┐
               │                   core/                       │
               │  (zero internal dependencies)                 │
               │  protocols, models, errors, events, config    │
               └──────────────────────────────────────────────┘
```

### 3.3 Dependency Rules

| Rule | Description | Enforcement |
|------|-------------|-------------|
| **R1** | `core/` has zero imports from any other `nines` module | Static check: `ruff` custom rule or CI grep for `from nines.` in `core/` files |
| **R2** | No circular dependencies between any two modules | Topological sort of import graph must succeed; CI validation |
| **R3** | Vertex modules (`eval/`, `collector/`, `analyzer/`) do not import each other | Each vertex is independently testable; cross-vertex communication goes through `orchestrator/` |
| **R4** | `orchestrator/` is the only module permitted to import from all vertex modules | Enforces single integration point; prevents spaghetti coupling |
| **R5** | `cli/` may import from any module (it is the composition root) | CLI assembles the full dependency graph at entry |
| **R6** | `sandbox/` depends only on `core/` | Sandbox must be lightweight and independently testable |
| **R7** | `iteration/` depends on `core/` and `eval/` (for self-eval scorer reuse) | Minimal cross-vertex coupling; uses eval's scoring infrastructure |
| **R8** | `skill/` depends only on `core/` | Skill generation reads config and templates, no runtime coupling |

### 3.4 Acyclicity Proof

The topological ordering of the dependency graph is:

```
core → sandbox → eval → collector → analyzer → skill → iteration → orchestrator → cli
```

At each level, modules only depend on modules earlier in the ordering. This guarantees:
- No cycles exist
- Each module can be tested independently by mocking its dependencies
- Build order is deterministic

---

## 4. Configuration Schema

### 4.1 Merge Strategy

Configuration values are resolved through a 3-level merge with last-writer-wins semantics:

```
Priority (highest to lowest):
  1. CLI arguments / environment variables     (runtime override)
  2. Project-level  ./nines.toml               (project-specific)
  3. User-level     ~/.config/nines/config.toml (user preferences)
  4. Built-in       src/nines/core/defaults.toml (hardcoded defaults)
```

Environment variable mapping convention: `NINES_<SECTION>_<KEY>` (uppercase, dots become underscores).
Example: `eval.default_scorer` → `NINES_EVAL_DEFAULT_SCORER`.

### 4.2 Complete TOML Schema

```toml
# ============================================================================
# NineS Configuration Schema
# ============================================================================
# File: nines.toml (project-level) or ~/.config/nines/config.toml (user-level)
# All values shown are built-in defaults.
# ============================================================================

# ── General ──────────────────────────────────────────────────────────────────

[general]
log_level = "INFO"                   # DEBUG | INFO | WARNING | ERROR | CRITICAL
log_format = "structured"            # "structured" (JSON lines) | "human" (colored text)
output_dir = "./reports"             # Default output directory for reports
data_dir = "./data"                  # Default data directory for baselines, golden sets
db_path = "./data/nines.db"          # SQLite database file path
no_color = false                     # Disable ANSI color output
verbose = false                      # Enable verbose/debug output globally

# ── Evaluation (V1) ─────────────────────────────────────────────────────────

[eval]
default_scorer = "composite"         # "exact" | "fuzzy" | "rubric" | "composite"
default_timeout = 120                # Per-task execution timeout in seconds
parallel_workers = 1                 # Number of parallel evaluation workers
default_seed = null                  # Master seed for determinism (null = random)
sandbox_enabled = true               # Enable sandbox isolation by default
report_formats = ["json", "markdown"] # Output formats for evaluation reports
store_results = true                 # Persist results in SQLite score history

[eval.scorers.exact]
# ExactScorer has no configurable parameters

[eval.scorers.fuzzy]
similarity_threshold = 0.8           # Minimum similarity score to count as pass
algorithm = "token_overlap"          # "token_overlap" | "edit_distance" | "combined"

[eval.scorers.rubric]
# Rubric dimensions are defined per-task in task TOML files.
# Global default: equal weights if not specified.

[eval.scorers.composite]
chain = ["exact", "fuzzy"]           # Scorer chain order for waterfall evaluation
waterfall = true                     # Stop at first decisive scorer
namespace_prefix = true              # Prefix metric keys with scorer name

[eval.matrix]
max_cells = 1000                     # Maximum matrix cells before sampling kicks in
sampling_strategy = "pairwise"       # "latin_square" | "pairwise" | "random" | "full"
default_trials = 3                   # Number of independent trials per cell

[eval.budget]
max_time_seconds = null              # Total evaluation time budget (null = unlimited)
max_api_calls = null                 # Total API call budget
max_cost_usd = null                  # Total cost budget in USD
on_exceed = "terminate_graceful"     # "terminate_graceful" | "warn_continue"

[eval.reliability]
min_trials = 3                       # Minimum trials for pass@k / pass^k computation
report_pass_at_k = [1, 3]           # k values to compute pass@k for
report_pass_hat_k = [3]             # k values to compute pass^k for
report_pass3 = true                  # Include Pass³ (Claw-Eval all-3-must-pass)

# ── Collection (V2) ─────────────────────────────────────────────────────────

[collect]
default_limit = 50                   # Default result limit per query
incremental = true                   # Use incremental collection by default
store_path = null                    # Override DataStore SQLite path (null = use general.db_path)

[collect.github]
api_version = "2022-11-28"          # X-GitHub-Api-Version header value
token = null                         # GitHub personal access token (prefer NINES_COLLECT_GITHUB_TOKEN env var)
use_graphql = true                   # Prefer GraphQL over REST for deep fetches
search_rate_limit = 30               # Requests per minute for search API
core_rate_limit = 5000               # Requests per hour for core API
backoff_threshold_pct = 10           # Start adaptive backoff when remaining% < this

[collect.arxiv]
rate_limit_interval = 3.0            # Minimum seconds between arXiv API requests
max_results_per_query = 100          # Maximum results per single arXiv query
sort_by = "relevance"                # "relevance" | "lastUpdatedDate" | "submittedDate"

[collect.cache]
enabled = true                       # Enable response caching
ttl_seconds = 3600                   # Default cache TTL (1 hour)
max_entries = 10000                  # Maximum cache entries before LRU eviction

[collect.tracking]
default_refresh_interval = "24h"     # Default tracking refresh interval
bookmark_table = "tracking_bookmarks" # SQLite table name for bookmark state

# ── Analysis (V3) ────────────────────────────────────────────────────────────

[analyze]
default_depth = "standard"           # "shallow" | "standard" | "deep"
target_languages = ["python"]        # Languages to analyze (MVP: Python only)
decompose = true                     # Enable decomposition by default
index = true                         # Enable knowledge indexing by default
max_file_size_kb = 500               # Skip files larger than this (likely generated)

[analyze.reviewer]
complexity_threshold = 10            # Flag functions with cyclomatic complexity above this
extract_docstrings = true            # Include docstrings in extracted units
resolve_imports = true               # Resolve cross-file imports for dependency analysis

[analyze.structure]
detect_layers = true                 # Enable architectural layer detection
detect_patterns = true               # Enable architecture pattern recognition
pattern_confidence_threshold = 0.5   # Minimum confidence to report a detected pattern

[analyze.decomposer]
strategies = ["functional", "concern", "layer"]  # Active decomposition strategies
functional_granularity = "function"  # "function" | "class" | "module"
concern_categories = [               # Cross-cutting concerns to detect
    "error_handling",
    "logging",
    "validation",
    "configuration",
    "serialization",
]

[analyze.index]
fts_enabled = true                   # Enable FTS5 full-text search index
index_table = "knowledge_units"      # SQLite table name
facets = ["language", "type", "complexity_tier", "source"]

# ── Self-Evaluation & Iteration ──────────────────────────────────────────────

[self_eval]
dimensions = "all"                   # "all" or list of dimension IDs: ["D01", "D02", ...]
stability_runs = 3                   # Number of runs for multi-round stability verification
stability_cv_threshold = 0.05        # Maximum coefficient of variation for stability
baseline_table = "baselines"         # SQLite table for baseline storage
history_table = "score_history"      # SQLite table for score history

[self_eval.weights]
v1 = 0.30                           # Evaluation vertex weight in composite score
v2 = 0.25                           # Collection vertex weight
v3 = 0.25                           # Analysis vertex weight
system = 0.20                        # System-wide dimension weight

[iteration]
max_rounds = 10                      # Maximum MAPIM iterations
max_actions_per_round = 3            # Maximum improvement actions per iteration
convergence_method = "majority_vote" # Convergence detection method
dry_run = false                      # Show planned improvements without executing

[iteration.convergence]
sliding_window_size = 5              # Window size for sliding variance check
variance_threshold = 0.001           # Variance threshold for convergence
min_improvement_rate = 0.005         # Minimum relative improvement to continue
mann_kendall_confidence = 0.95       # Confidence level for Mann-Kendall trend test
cusum_drift = 0.5                    # CUSUM drift parameter
vote_threshold = 3                   # Number of methods that must agree (out of 4)

# ── Sandbox ──────────────────────────────────────────────────────────────────

[sandbox]
backend = "venv"                     # "venv" (MVP) | "docker" (future Tier 2)
pool_size = 2                        # Pre-created sandbox pool size for warm starts
default_timeout = 300                # Maximum execution time per sandbox session (seconds)
max_memory_mb = 512                  # Memory limit per sandbox (soft limit via resource module)
cleanup_on_exit = true               # Auto-cleanup sandbox artifacts on process exit
seed_control = true                  # Set PYTHONHASHSEED + random/numpy seeds from master seed

[sandbox.venv]
python_version = "3.12"              # Python version for sandbox venvs
use_uv = true                        # Use uv for venv creation (fast path)
base_packages = []                   # Packages pre-installed in every sandbox venv

[sandbox.pollution]
check_enabled = true                 # Enable pollution detection after each execution
watch_env_vars = true                # Monitor environment variable changes
watch_files = [                      # File paths to monitor for modifications
    "~/.bashrc",
    "~/.profile",
    "~/.gitconfig",
]
watch_sys_path = true                # Monitor sys.path changes

# ── Orchestrator ─────────────────────────────────────────────────────────────

[orchestrator]
artifact_store_table = "artifacts"   # SQLite table for cross-vertex artifact passing
max_parallel_stages = 2              # Maximum stages running in parallel
stage_timeout = 600                  # Maximum seconds per workflow stage

# ── Skill / Agent Integration ────────────────────────────────────────────────

[skill]
default_target = "cursor"            # "cursor" | "claude" | "all"
manifest_version = "1.0.0"          # Manifest schema version

[skill.cursor]
skill_dir = ".cursor/skills/nines"   # Cursor skill installation directory
generate_commands = true             # Generate command workflow files

[skill.claude]
commands_dir = ".claude/commands/nines"  # Claude Code commands directory
update_claude_md = true              # Append NineS section to CLAUDE.md

# ── Events ───────────────────────────────────────────────────────────────────

[events]
enabled = true                       # Enable the event system
async_dispatch = false               # Use synchronous dispatch (MVP); async in v2
max_handlers_per_event = 50          # Safety limit on handler registration
log_events = false                   # Log all emitted events at DEBUG level
```

### 4.3 Config Validation Rules

| Rule | Check | Error |
|------|-------|-------|
| Type safety | Each field must match its declared type (str, int, float, bool, list) | `ConfigError(field="eval.default_timeout", expected="int", got="str")` |
| Range validation | Numeric fields with bounds are validated (e.g., `stability_cv_threshold` ∈ [0, 1]) | `ConfigError(field="...", message="value 1.5 out of range [0.0, 1.0]")` |
| Enum validation | Fields with fixed choices are validated (e.g., `default_scorer` ∈ {exact, fuzzy, rubric, composite}) | `ConfigError(field="...", message="invalid value 'foo', expected one of: ...")` |
| Weight normalization | `self_eval.weights` must sum to 1.0 (±0.001 tolerance) | `ConfigError(message="self_eval.weights sum to 1.05, expected 1.0")` |
| Path existence | Paths referenced by config (db_path, output_dir) are validated when accessed, not at load time | Lazy validation avoids startup failures for optional paths |
| Secret masking | Fields containing tokens/keys are never logged or included in error messages | Token fields return `"***"` in `__repr__` |

---

## 5. Error Handling Strategy

### 5.1 Error Type Hierarchy

All NineS errors derive from a single root, enabling uniform handling while preserving specific catch granularity.

```
NinesError (base)
├── ConfigError                          # Configuration loading/validation failures
│   ├── ConfigFileNotFoundError          # TOML file not found at expected path
│   ├── ConfigParseError                 # TOML syntax error
│   └── ConfigValidationError            # Value constraint violation
│
├── EvalError                            # Evaluation pipeline failures
│   ├── TaskLoadError                    # Task file missing, malformed, or invalid
│   ├── TaskExecutionError               # Task execution failed (non-timeout)
│   ├── ScoringError                     # Scorer raised during scoring
│   ├── BudgetExceededError              # Time/cost/API budget exhausted
│   └── ReportError                      # Report generation failure
│
├── CollectionError                      # Information collection failures
│   ├── SourceNotFoundError              # Unknown source type requested
│   ├── APIError                         # HTTP error from external API
│   │   ├── RateLimitError               # 429 or quota exceeded
│   │   └── AuthenticationError          # 401/403 from API
│   ├── StoreError                       # SQLite storage failure
│   └── TrackingError                    # Bookmark/cursor state corruption
│
├── AnalysisError                        # Knowledge analysis failures
│   ├── ParseError                       # AST/syntax parse failure (per-file, non-fatal)
│   ├── ImportResolutionError            # Cross-file import could not be resolved
│   ├── IndexError                       # Knowledge index read/write failure
│   └── DecompositionError               # Decomposition strategy failure
│
├── IterationError                       # Self-iteration failures
│   ├── BaselineError                    # Baseline create/load/compare failure
│   ├── ConvergenceError                 # Convergence check computation failure
│   ├── PlanningError                    # Improvement plan generation failure
│   └── ActionError                      # Improvement action execution failure
│
└── SandboxError                         # Sandbox isolation failures
    ├── SandboxCreationError             # Venv/tmpdir creation failure
    ├── SandboxTimeoutError              # Execution exceeded time limit
    ├── SandboxPollutionError            # Host/cross-sandbox pollution detected
    └── SandboxResourceError             # Memory or disk limit exceeded
```

### 5.2 Error Structure

Every `NinesError` carries structured fields for programmatic consumption and human-readable reporting:

```python
@dataclass
class NinesError(Exception):
    code: str           # Machine-readable code: "E001", "E002", etc.
    message: str        # Human-readable summary
    category: str       # "config" | "eval" | "collection" | "analysis" | "iteration" | "sandbox"
    detail: str | None  # Extended explanation (optional)
    hint: str | None    # Actionable suggestion for the user (optional)
    location: str | None  # File path, module, or function where error originated
    cause: Exception | None  # Chained exception (from __cause__)
```

### 5.3 Error Code Registry

| Range | Category | Examples |
|-------|----------|---------|
| E001–E009 | Config | E001=file_not_found, E002=parse_error, E003=validation_error |
| E010–E029 | Eval | E010=task_load, E011=task_exec, E012=scoring, E013=budget_exceeded, E014=report |
| E030–E049 | Collection | E030=source_not_found, E031=api_error, E032=rate_limit, E033=auth, E034=store, E035=tracking |
| E050–E069 | Analysis | E050=parse, E051=import_resolution, E052=index, E053=decomposition |
| E070–E089 | Iteration | E070=baseline, E071=convergence, E072=planning, E073=action |
| E090–E099 | Sandbox | E090=creation, E091=timeout, E092=pollution, E093=resource |

### 5.4 Error Handling Policy

| Situation | Strategy | Rationale |
|-----------|----------|-----------|
| Configuration invalid at startup | Raise `ConfigError`, halt | Misconfiguration must be fixed before any work begins |
| Single task fails in batch evaluation | Log error, record `TaskExecutionError` in results, continue batch | Partial results are valuable (NFR-22 error isolation) |
| Single file fails AST parse in analysis | Log `ParseError`, skip file, continue pipeline | Single-file failure must not abort multi-file analysis (FR-310) |
| API returns transient HTTP error (429, 500, 502, 503) | Retry up to 3× with exponential backoff, then raise `APIError` | NFR-19 mandates automatic retry on transient failures |
| API returns permanent HTTP error (400, 404) | Raise `APIError` immediately, no retry | Retrying permanent errors wastes quota |
| Sandbox detects host pollution | Raise `SandboxPollutionError` (critical) | NFR-09 treats any pollution as a critical bug |
| Budget exceeded during evaluation | Raise `BudgetExceededError`, return partial results with `budget_exceeded=True` | FR-111 requires graceful termination with partial results |
| Convergence check fails (numerical) | Log `ConvergenceError`, report as "unable to determine convergence" | Better to report uncertainty than crash the iteration loop |
| Unknown/unexpected exception | Log full traceback at ERROR level, re-raise as `NinesError` | NFR-21 prohibits silent failures |

### 5.5 No Silent Failures Enforcement

Per NFR-21, NineS enforces a strict "no silent failures" policy:

1. **No bare `except: pass`**: Static analysis (ruff rule `E722`) blocks bare except clauses. Every caught exception must be logged, re-raised, or produce an explicit error state.
2. **Structured error propagation**: Functions that can fail return `Result[T, NinesError]` patterns or raise typed exceptions — never `None` as a silent sentinel for failure.
3. **CI check**: A pre-commit hook greps for `except.*pass` and `except Exception` without logging, failing the build if found.

---

## 6. Logging Architecture

### 6.1 Library Choice: `structlog`

NineS uses `structlog` for structured logging. Rationale:
- Produces both human-readable colored output (development) and JSON lines (production/CI)
- Zero-cost context binding (logger carries module/operation context without repeated string formatting)
- Compatible with stdlib `logging` for library interop
- Adds negligible overhead on performance-sensitive paths

### 6.2 Logger Configuration

```python
# src/nines/core/logging.py — called once at startup

import structlog
import logging

def configure_logging(level: str = "INFO", fmt: str = "structured") -> None:
    """Configure structured logging for the entire NineS process."""
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if fmt == "human":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()
    
    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### 6.3 Per-Module Logger Convention

Each module creates a bound logger with the module name as context:

```python
# Example: src/nines/eval/runner.py
import structlog
log = structlog.get_logger(module="nines.eval.runner")

# Usage within functions:
log.info("eval_started", task_count=len(tasks), scorer=config.default_scorer)
log.debug("task_executing", task_id=task.id, sandbox=sandbox.id)
log.warning("budget_approaching", spent=budget.spent, limit=budget.limit)
log.error("task_failed", task_id=task.id, error=str(e), error_code=e.code)
```

### 6.4 Log Level Policy

| Level | Usage | Performance Impact |
|-------|-------|-------------------|
| **DEBUG** | Per-item details: individual task scores, API request/response headers, cache hit/miss, event dispatch | High volume; disabled in production. Guarded by `if log.isEnabledFor(DEBUG)` on hot paths. |
| **INFO** | Pipeline lifecycle: "eval started with N tasks", "collection complete: M items", "analysis finished" | Low volume; always enabled. |
| **WARNING** | Recoverable issues: budget approaching limit, cache miss on expected hit, retry triggered | Low volume; always enabled. |
| **ERROR** | Failures that impact results: task execution failure, API error after retries exhausted, parse errors | Rare; always enabled. Includes structured error context. |
| **CRITICAL** | System integrity violations: sandbox pollution detected, database corruption, unrecoverable state | Extremely rare; triggers immediate halt or escalation. |

### 6.5 Performance-Sensitive Paths

The following paths are identified as performance-sensitive. Logging on these paths is restricted to DEBUG level and guarded by level checks:

| Path | Constraint | Rationale |
|------|-----------|-----------|
| AST node visitor (per-node) | No logging inside visitor callbacks | FR-301: ≥100 files/min throughput (NFR-05) |
| Scorer inner loop (per-token comparison) | No logging inside comparison loops | FR-103/104: scorer must be fast for matrix evaluation |
| SQLite batch insert (per-row) | Log batch start/end only, not per-row | FR-308: index 100+ units without logging overhead |
| Rate limiter token check | Log only on acquire/wait, not on check | FR-206: called on every API request |
| Event dispatch (per-handler) | Log dispatch start/end only, not per-handler | FR-512: event dispatch must not be a bottleneck |

---

## 7. Event System

### 7.1 Design Overview

The event system provides lightweight, synchronous pub/sub communication between modules without introducing direct dependencies. It enables:
- `collector/` to notify `analyzer/` that new sources are available (F3 flow)
- `eval/` to notify `iteration/` that new scores are available
- `analyzer/` to notify `eval/` that new knowledge units are indexed (F5 flow)
- Progress reporting for CLI display (FR-311, FR-114)

### 7.2 Event Types

```python
# src/nines/core/events.py

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime


class EventType(Enum):
    """All event types in the NineS system."""
    
    # Evaluation events (V1)
    EVAL_STARTED = auto()
    EVAL_TASK_COMPLETE = auto()
    EVAL_BUDGET_WARNING = auto()
    EVAL_COMPLETE = auto()
    
    # Collection events (V2)
    COLLECTION_STARTED = auto()
    COLLECTION_ITEM_FOUND = auto()
    COLLECTION_COMPLETE = auto()
    COLLECTION_ERROR = auto()
    SOURCE_CHANGE_DETECTED = auto()
    
    # Analysis events (V3)
    ANALYSIS_STARTED = auto()
    ANALYSIS_FILE_DISCOVERED = auto()
    ANALYSIS_FILE_PARSED = auto()
    ANALYSIS_UNITS_EXTRACTED = auto()
    ANALYSIS_COMPLETE = auto()
    ANALYSIS_ERROR = auto()
    
    # Iteration events
    SELF_EVAL_STARTED = auto()
    SELF_EVAL_DIMENSION_COMPLETE = auto()
    SELF_EVAL_COMPLETE = auto()
    ITERATION_ROUND_STARTED = auto()
    ITERATION_ROUND_COMPLETE = auto()
    GAP_DETECTED = auto()
    IMPROVEMENT_APPLIED = auto()
    CONVERGENCE_REACHED = auto()
    
    # System events
    CONFIG_LOADED = auto()
    SANDBOX_CREATED = auto()
    SANDBOX_DESTROYED = auto()
    SANDBOX_POLLUTION_DETECTED = auto()


@dataclass(frozen=True)
class Event:
    """Immutable event with typed payload."""
    
    type: EventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_module: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
```

### 7.3 EventBus Implementation

```python
# src/nines/core/events.py (continued)

from collections import defaultdict
from typing import Callable
import structlog

log = structlog.get_logger(module="nines.core.events")

EventHandler = Callable[[Event], None]


class EventBus:
    """Synchronous publish/subscribe event bus.
    
    Thread-safety: not required for MVP (single-user, single-process).
    Handler exceptions are caught and logged but do not propagate to
    the emitter — preventing one faulty handler from breaking the pipeline.
    """
    
    _instance: "EventBus | None" = None
    
    def __init__(self, max_handlers_per_event: int = 50) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._max_handlers = max_handlers_per_event
    
    @classmethod
    def get(cls) -> "EventBus":
        """Return the singleton EventBus instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton for testing."""
        cls._instance = None
    
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        handlers = self._handlers[event_type]
        if len(handlers) >= self._max_handlers:
            raise NinesError(
                code="E100",
                message=f"Max handlers ({self._max_handlers}) exceeded for {event_type.name}",
                category="system",
            )
        handlers.append(handler)
    
    def on(self, event_type: EventType) -> Callable:
        """Decorator form of subscribe."""
        def decorator(fn: EventHandler) -> EventHandler:
            self.subscribe(event_type, fn)
            return fn
        return decorator
    
    def emit(self, event_type: EventType, source_module: str = "", **payload: Any) -> None:
        """Emit an event to all subscribed handlers.
        
        Handler exceptions are caught, logged, and swallowed to prevent
        cross-module failure propagation. This is intentional: the emitter
        must not be affected by handler bugs (NFR-21 is satisfied because
        the exception IS logged, not silenced).
        """
        event = Event(type=event_type, source_module=source_module, payload=payload)
        
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as exc:
                log.error(
                    "event_handler_failed",
                    event_type=event_type.name,
                    handler=handler.__qualname__,
                    error=str(exc),
                )
    
    def clear(self, event_type: EventType | None = None) -> None:
        """Remove handlers. If event_type is None, remove all."""
        if event_type is None:
            self._handlers.clear()
        else:
            self._handlers.pop(event_type, None)
```

### 7.4 Event Payload Contracts

Each event type has a defined payload schema. Handlers can rely on these keys being present:

| Event Type | Payload Keys | Types |
|-----------|-------------|-------|
| `EVAL_TASK_COMPLETE` | `task_id`, `score`, `duration_ms`, `scorer_name` | str, float, int, str |
| `EVAL_COMPLETE` | `total_tasks`, `mean_score`, `result_id` | int, float, str |
| `EVAL_BUDGET_WARNING` | `resource`, `spent`, `limit`, `pct_remaining` | str, float, float, float |
| `COLLECTION_ITEM_FOUND` | `source`, `item_id`, `item_type` | str, str, str |
| `COLLECTION_COMPLETE` | `source`, `items_collected`, `items_new`, `items_changed` | str, int, int, int |
| `SOURCE_CHANGE_DETECTED` | `source`, `item_id`, `change_type`, `fields_changed` | str, str, str, list[str] |
| `ANALYSIS_FILE_PARSED` | `file_path`, `functions_found`, `classes_found`, `status` | str, int, int, str |
| `ANALYSIS_UNITS_EXTRACTED` | `unit_count`, `strategies_used` | int, list[str] |
| `ANALYSIS_COMPLETE` | `files_analyzed`, `files_skipped`, `files_errored`, `units_total` | int, int, int, int |
| `SELF_EVAL_DIMENSION_COMPLETE` | `dimension_id`, `score`, `direction`, `stable` | str, float, str, bool |
| `SELF_EVAL_COMPLETE` | `composite_score`, `v1_score`, `v2_score`, `v3_score`, `system_score` | float, float, float, float, float |
| `GAP_DETECTED` | `dimension`, `current`, `target`, `gap`, `priority` | str, float, float, float, str |
| `CONVERGENCE_REACHED` | `iteration`, `methods_agreeing`, `final_composite` | int, int, float |
| `SANDBOX_POLLUTION_DETECTED` | `sandbox_id`, `pollution_type`, `details` | str, str, dict |

### 7.5 Cross-Module Event Wiring

The following event subscriptions are established by the orchestrator at startup:

```
COLLECTION_COMPLETE     → orchestrator → queue V3 analysis for new items  (F3 flow)
ANALYSIS_COMPLETE       → orchestrator → register new KnowledgeUnits as V1 task candidates (F5 flow)
EVAL_COMPLETE           → orchestrator → trigger GapDetector if self-eval mode (F1 flow)
GAP_DETECTED            → orchestrator → generate V2 search queries (F1 flow)
SOURCE_CHANGE_DETECTED  → orchestrator → queue V3 re-analysis for changed items
SANDBOX_POLLUTION_DETECTED → orchestrator → halt evaluation, report critical error
```

CLI progress display subscribes to granular events for real-time feedback:

```
EVAL_TASK_COMPLETE           → CLI progress bar update
ANALYSIS_FILE_PARSED         → CLI progress bar update
COLLECTION_ITEM_FOUND        → CLI counter update
SELF_EVAL_DIMENSION_COMPLETE → CLI dimension table update
```

---

## 8. Requirement Traceability

### 8.1 Architecture Component → Requirement Mapping

| Architecture Component | Primary Requirements Covered |
|----------------------|----------------------------|
| `core/protocols.py` | FR-204 (SourceProtocol), CON-09, NFR-13–16 (plugin cost) |
| `core/models.py` | FR-101 (TaskDefinition), FR-305 (KnowledgeUnit), FR-510 (typed returns) |
| `core/errors.py` | NFR-20 (error hierarchy), NFR-21 (no silent failures), FR-509 (structured errors) |
| `core/events.py` | FR-512 (EventBus), FR-311 (progress events), FR-114 (progress tracking) |
| `core/config.py` | FR-511 (NinesConfig), NFR-17 (extensibility), CON-08 (TOML) |
| `core/logging.py` | Section 6 logging architecture, NFR-21 (logged exceptions) |
| `eval/runner.py` | FR-114 (orchestration), FR-107 (matrix), FR-111 (budget) |
| `eval/scorers.py` | FR-103 (Exact), FR-104 (Fuzzy), FR-105 (Rubric), FR-106 (Composite) |
| `eval/metrics.py` | FR-108 (pass@k), FR-109 (pass^k), FR-110 (Pass³) |
| `eval/reporters.py` | FR-112 (JSON), FR-113 (Markdown), FR-115 (baseline comparison) |
| `eval/matrix.py` | FR-107 (matrix evaluation), FR-111 (budget guards) |
| `collector/github.py` | FR-201 (REST), FR-202 (GraphQL) |
| `collector/arxiv.py` | FR-203 (arXiv collector) |
| `collector/store.py` | FR-205 (SQLite store), CON-04 |
| `collector/rate_limiter.py` | FR-206 (token-bucket rate limiting) |
| `collector/tracker.py` | FR-207 (incremental tracking), FR-209 (collection status) |
| `collector/diff.py` | FR-208 (change detection) |
| `collector/cache.py` | FR-212 (local caching with TTL) |
| `analyzer/reviewer.py` | FR-301 (AST analysis), FR-302 (multi-file) |
| `analyzer/structure.py` | FR-303 (structure analysis) |
| `analyzer/patterns.py` | FR-304 (architecture pattern detection) |
| `analyzer/decomposer.py` | FR-305 (functional), FR-306 (concern), FR-307 (layer) |
| `analyzer/indexer.py` | FR-308 (knowledge indexing) |
| `analyzer/abstraction.py` | FR-309 (pattern abstraction) |
| `analyzer/pipeline.py` | FR-310 (pipeline orchestration), FR-311 (progress) |
| `iteration/self_eval.py` | FR-403 (self-eval runner), FR-412 (aggregate scoring) |
| `iteration/baseline.py` | FR-404 (baseline management) |
| `iteration/history.py` | FR-405 (score history) |
| `iteration/gap_detector.py` | FR-406 (gap detection) |
| `iteration/planner.py` | FR-407 (improvement planner) |
| `iteration/convergence.py` | FR-408 (convergence detection) |
| `iteration/tracker.py` | FR-409 (MAPIM loop), FR-410 (optimization lifecycle) |
| `iteration/dimensions.py` | FR-411 (stability verification) |
| `orchestrator/engine.py` | FR-401 (workflow engine) |
| `orchestrator/artifacts.py` | FR-402 (cross-vertex data flow) |
| `sandbox/manager.py` | NFR-02 (sandbox overhead), NFR-09 (no pollution) |
| `sandbox/runner.py` | NFR-10 (no cross-pollution), NFR-11 (determinism) |
| `sandbox/isolation.py` | NFR-12 (seed control), CON-05 (no Docker) |
| `sandbox/pollution.py` | FR-116 (collateral damage) |
| `skill/installer.py` | FR-506 (install CLI), FR-516 (version management) |
| `skill/manifest.py` | FR-515 (skill manifest) |
| `skill/cursor_adapter.py` | FR-513 (Cursor skill adapter) |
| `skill/claude_adapter.py` | FR-514 (Claude Code adapter) |
| `cli/commands/*.py` | FR-501–FR-508 (CLI commands, exit codes) |
| `cli/main.py` | FR-507 (global options) |
| `cli/formatters.py` | FR-509 (structured error reporting) |

### 8.2 Non-Functional Requirement Coverage

| NFR | Architecture Mechanism |
|-----|----------------------|
| NFR-01 (pipeline latency) | Parallel workers in `eval/runner.py`, sandbox pool in `sandbox/manager.py` |
| NFR-02 (sandbox overhead) | `uv` for venv creation (CON-02), warm pool reuse |
| NFR-03–04 (collection throughput) | Token-bucket rate limiter, response caching, incremental tracking |
| NFR-05 (analysis throughput) | File-level caching, error isolation, no per-node logging |
| NFR-06 (CLI cold start) | Lazy imports in CLI commands, deferred heavy module loading |
| NFR-07 (SQLite latency) | Indexed tables, WAL mode, prepared statements |
| NFR-08 (memory footprint) | Streaming file processing, bounded batch sizes |
| NFR-09–10 (sandbox isolation) | 3-layer isolation (process + venv + tmpdir), pollution detection |
| NFR-11–12 (determinism) | Master seed propagation (PYTHONHASHSEED, random, numpy) |
| NFR-13–16 (extensibility) | Protocol-based interfaces, registry patterns |
| NFR-17 (config extensibility) | TOML sections are independently parseable; unknown sections are preserved |
| NFR-18 (graceful degradation) | Per-source error isolation in collector, `partial_failure` flags |
| NFR-19 (retry transient) | Exponential backoff in rate limiter, 3-retry policy |
| NFR-20 (error hierarchy) | Section 5 error type tree |
| NFR-21 (no silent failures) | structlog on every catch, ruff E722 enforcement |
| NFR-22 (error isolation) | Per-file try/except in analysis pipeline |
| NFR-23–27 (maintainability) | ruff (CON-03), mypy strict, docstring enforcement, dependency count control |

### 8.3 Constraint Satisfaction

| Constraint | Satisfied By |
|-----------|-------------|
| CON-01 (Python 3.12+) | `.python-version`, `pyproject.toml` requires-python |
| CON-02 (uv) | `pyproject.toml` build system, `sandbox/isolation.py` uses `uv venv` |
| CON-03 (ruff) | `pyproject.toml` `[tool.ruff]`, `.pre-commit-config.yaml` |
| CON-04 (SQLite) | `collector/store.py`, `analyzer/indexer.py`, `iteration/history.py`, `orchestrator/artifacts.py` — all use stdlib `sqlite3` |
| CON-05 (no Docker MVP) | `sandbox/` defaults to `venv` backend |
| CON-06 (offline operation) | All modules work offline except `collector/github.py`, `collector/arxiv.py` |
| CON-07 (single-user) | No authentication, no server mode, SQLite WAL mode |
| CON-08 (JSON/TOML) | JSON for reports/manifests, TOML for `nines.toml` config |
| CON-09 (Protocol interfaces) | `core/protocols.py` defines all inter-module boundaries |
| CON-10 (Cursor + Claude MVP) | `skill/cursor_adapter.py`, `skill/claude_adapter.py` |

---

*Defines the master system architecture for NineS. All module-specific design documents (T12–T17) reference this document for module boundaries, dependency rules, data flow contracts, and cross-cutting concerns.*
*Last modified: 2026-04-11*
