# Module Details

<!-- auto-updated: version from src/nines/__init__.py -->

Detailed description of each NineS module, its key classes, protocols, and extension points.

---

## Module Map

```
src/nines/
├── core/           # Zero-dependency foundation
├── eval/           # V1: Evaluation & Benchmarking
├── collector/      # V2: Information Search & Tracking
├── analyzer/       # V3: Knowledge Analysis & Decomposition
├── iteration/      # Self-Evaluation & Self-Iteration
├── orchestrator/   # Workflow Engine & Cross-Module Coordination
├── sandbox/        # Isolation Layer
├── skill/          # Agent Skill Adapters
└── cli/            # CLI Entry Point
```

---

## `core/` — Foundation Layer

The zero-dependency foundation shared by all modules. No `core/` file imports from any other NineS module.

| File | Responsibility |
|------|---------------|
| `protocols.py` | Protocol classes: `Scorer`, `Executor`, `Collector`, `Analyzer`, `Reporter`, `Loader` |
| `models.py` | Shared data models: `TaskDefinition`, `EvalResult`, `ScoreCard`, `SourceItem`, `KnowledgeUnit` |
| `errors.py` | Error hierarchy rooted at `NinesError` with structured fields (code, message, hint, location) |
| `events.py` | `EventBus` singleton with synchronous pub/sub, typed `Event` payloads |
| `config.py` | `NinesConfig` with TOML loading, 3-level merge, environment variable overrides |

**Key Protocols:**

- `Scorer` — Score an execution result against expected output
- `Executor` — Execute a task in isolation and return results
- `Reporter` — Generate output reports from aggregated results
- `TaskLoader` — Load evaluation tasks from files, directories, or globs

**Extension Point:** Register custom protocol implementations via the scorer registry or entry points.

---

## `eval/` — Evaluation & Benchmarking (V1)

Task evaluation, scoring, reliability metrics, and reporting.

| File | Responsibility |
|------|---------------|
| `runner.py` | `EvalRunner`: load → sandbox → execute → score → report pipeline |
| `scorers.py` | `ExactScorer`, `FuzzyScorer`, `RubricScorer`, `CompositeScorer` with waterfall judge |
| `metrics.py` | `pass@k`, `pass^k`, `Pass³` estimators, bootstrap confidence intervals |
| `matrix.py` | `MatrixEvaluator`: N-axis combinatorial evaluation with sampling strategies and budget guards |
| `reporters.py` | `JSONReporter`, `MarkdownReporter`, `BaselineComparator` |
| `analysis.py` | `AxisAnalyzer`: per-dimension breakdowns, trend tables |
| `models.py` | `EvalResult`, `ScoreCard`, `MatrixCell`, `ReliabilityMetrics`, `BudgetState` |

**Key Classes:**

- `EvalRunner` — Orchestrates the full evaluation pipeline
- `CompositeScorer` — Chains multiple scorers in weighted or waterfall mode
- `MatrixEvaluator` — Generates and evaluates combinatorial test matrices

**Extension Point:** Register custom scorers via `ScorerRegistry.register()` or `pyproject.toml` entry points under `nines.scorers`.

---

## `collector/` — Information Search & Tracking (V2)

External data discovery, collection, tracking, and change detection.

| File | Responsibility |
|------|---------------|
| `github.py` | `GitHubCollector`: REST search + GraphQL deep fetch |
| `arxiv.py` | `ArxivCollector`: keyword search, pagination, Atom XML parsing |
| `store.py` | `DataStore`: SQLite CRUD, FTS5 full-text search, faceted filtering |
| `tracker.py` | `IncrementalTracker`: bookmark/cursor state, refresh scheduling |
| `diff.py` | `ChangeDetector`: snapshot comparison, structured diff, categorization |
| `scheduler.py` | `CollectionScheduler`: manual triggers and interval-based periodic collection |
| `models.py` | `SourceItem`, `Repository`, `Paper`, `ChangeEvent`, `TrackingHandle` |

**Key Classes:**

- `GitHubCollector` — Full GitHub integration with REST + GraphQL and adaptive rate limiting
- `ArxivCollector` — arXiv paper collection with pagination and category filtering
- `DataStore` — SQLite storage with CRUD, search, export, and cache operations
- `ChangeDetector` — Snapshot-based change detection with field-level diffs

**Extension Point:** Implement `SourceProtocol` and register with `SourceRegistry` to add new data sources (≤1 file + ≤20 lines of registration code).

---

## `analyzer/` — Knowledge Analysis & Decomposition (V3)

Code analysis, structural decomposition, and knowledge indexing.

| File | Responsibility |
|------|---------------|
| `pipeline.py` | `AnalysisPipeline`: ingest → parse → analyze → decompose → index |
| `reviewer.py` | `CodeReviewer`: AST extraction, cyclomatic complexity, import resolution |
| `structure.py` | `StructureAnalyzer`: directory layout, module boundaries, layer detection, circular dependencies |
| `decomposer.py` | `Decomposer`: functional, concern-based, and layer-based decomposition strategies |
| `indexer.py` | `KnowledgeIndex`: SQLite FTS5-backed storage, keyword + faceted search |
| `abstraction.py` | `PatternAbstractor`: design pattern recognition (Factory, Observer, Strategy, Adapter, Decorator) |
| `search.py` | `SearchEngine`: query execution combining FTS5 with faceted filters |

**Key Classes:**

- `AnalysisPipeline` — End-to-end pipeline with per-file error isolation
- `CodeReviewer` — AST-based code review with coupling metrics (Ca, Ce, I)
- `Decomposer` — Three-strategy decomposition into `KnowledgeUnit` trees
- `KnowledgeIndex` — Searchable index with FTS5 and faceted filtering

**Extension Point:** Implement the `PipelineStage` protocol to add custom analysis stages. Implement `Decomposer` protocol for new decomposition strategies.

---

## `iteration/` — Self-Evaluation & Self-Iteration

The MAPIM loop engine for continuous self-improvement.

| File | Responsibility |
|------|---------------|
| `self_eval.py` | `SelfEvalRunner`: 19-dimension evaluation suite execution |
| `baseline.py` | `BaselineManager`: create, store, list, compare baselines |
| `gap_detector.py` | `GapDetector`: current vs target comparison, ranked gap list |
| `planner.py` | `ImprovementPlanner`: ≤3 actions per iteration, action generation |
| `convergence.py` | `ConvergenceChecker`: 4-method majority vote (sliding variance, relative improvement, Mann-Kendall, CUSUM) |
| `tracker.py` | `IterationTracker`: MAPIM loop state machine, progress reports |
| `history.py` | `ScoreHistory`: time-series storage, trend detection |

**Key Classes:**

- `SelfEvalRunner` — Executes all 19 dimension evaluators and produces a composite score
- `GapDetector` — Classifies gaps as critical/major/minor/acceptable with root cause hints
- `ConvergenceChecker` — Statistical convergence with 4-method composite decision
- `ImprovementPlanner` — Maps gaps to concrete module-level improvement actions

**Extension Point:** Implement the `DimensionEvaluator` protocol for custom evaluation dimensions.

---

## `orchestrator/` — Workflow Engine

Cross-module coordination and workflow execution.

| File | Responsibility |
|------|---------------|
| `engine.py` | `WorkflowEngine`: multi-step workflow definition and execution |
| `pipeline.py` | `Pipeline`: serial, parallel, conditional stage composition |
| `models.py` | `Workflow`, `Stage`, `StageResult`, `ArtifactRef` |

**Key Classes:**

- `WorkflowEngine` — Coordinates multi-vertex workflows and cross-vertex data flows
- `ArtifactStore` — SQLite-backed typed artifact passing between vertices

---

## `sandbox/` — Isolation Layer

Docker-free sandboxed execution with three-layer isolation.

| File | Responsibility |
|------|---------------|
| `manager.py` | `SandboxManager`: lifecycle (create/reuse/destroy), pool management |
| `runner.py` | `IsolatedRunner`: subprocess execution with resource limits and timeout |
| `isolation.py` | `VenvFactory`: virtual environment creation via `uv` or stdlib, seed control |
| `pollution.py` | `PollutionDetector`: before/after environment snapshot diff |

**Key Classes:**

- `SandboxManager` — Composes the three isolation layers with lifecycle management
- `IsolatedRunner` — Low-level subprocess execution with `RLIMIT_AS`, process groups, and fingerprinting
- `PollutionDetector` — Verifies host was not modified across 4 dimensions (env vars, files, directories, sys.path)

---

## `skill/` — Agent Skill Adapters

Agent runtime adapter generation and installation.

| File | Responsibility |
|------|---------------|
| `installer.py` | `SkillInstaller`: install/uninstall orchestration, version management |
| `manifest.py` | `ManifestGenerator`: JSON manifest from config + version |
| `cursor_adapter.py` | `CursorSkillEmitter`: `.cursor/skills/nines/` generation with SKILL.md and command workflows |
| `claude_adapter.py` | `ClaudeCodeEmitter`: `.claude/commands/nines/` + CLAUDE.md section |

**Key Classes:**

- `SkillInstaller` — Coordinates manifest loading, version checking, template rendering, and file writing
- `CursorAdapter` — Generates Cursor-compatible SKILL.md, command workflows, and reference docs
- `ClaudeAdapter` — Generates Claude Code slash commands and CLAUDE.md integration

**Extension Point:** Implement `SkillAdapterProtocol` to add support for new agent runtimes.

---

## `cli/` — CLI Entry Point

User-facing Click command interface.

| File | Responsibility |
|------|---------------|
| `main.py` | Root group: `nines`, global options (`--config`, `-v`, `-q`, `--format`, `--no-color`) |
| `commands/eval.py` | `nines eval <TASK_OR_SUITE> [OPTIONS]` |
| `commands/collect.py` | `nines collect <SOURCE> <QUERY> [OPTIONS]` |
| `commands/analyze.py` | `nines analyze <TARGET> [OPTIONS]` |
| `commands/self_eval.py` | `nines self-eval [OPTIONS]` |
| `commands/iterate.py` | `nines iterate [OPTIONS]` |
| `commands/install.py` | `nines install [OPTIONS]` |

The CLI is the composition root — it imports from all modules and assembles the full dependency graph at entry time. Lazy imports are used for heavy modules to minimize cold-start time.
