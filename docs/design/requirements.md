# NineS Unified Requirements Specification

> **Task**: T10 — Unified Requirements Document | **Team**: Research L3
> **Consolidates**: `synthesis_report.md`, `capability_model.md`, `self_eval_spec.md`, `skill_interface_spec.md`
> **Primary consumer**: S03 (Architecture Design)
> **Last Modified**: 2026-04-11

---

## 1. Functional Requirements

### 1.1 V1 — Evaluation & Benchmarking

| ID | Description | Priority | Acceptance Condition |
|----|-------------|----------|----------------------|
| **FR-101** | **Task Definition**: Define evaluation tasks as Python dataclasses with typed inputs, expected outputs, difficulty tiers (5 levels), category tags, and TOML serialization support. | P0 | A `TaskDefinition` dataclass can be instantiated, serialized to TOML, deserialized back, and all fields round-trip without loss. Difficulty tiers L1–L5 are enforced by validation. |
| **FR-102** | **Task Loading**: Load evaluation tasks from individual TOML files, suite directories, and glob patterns. Support parameterized task templates for variant generation. | P0 | `TaskLoader.load("tasks/*.toml")` returns a list of valid `TaskDefinition` instances. Invalid files produce structured errors, not crashes. |
| **FR-103** | **Scoring Pipeline — ExactScorer**: Score task outputs via binary exact-match comparison against expected output. | P0 | Given identical input/expected pairs, ExactScorer returns 1.0; any difference returns 0.0. Deterministic across runs. |
| **FR-104** | **Scoring Pipeline — FuzzyScorer**: Score task outputs via token-overlap and edit-distance comparison, producing a continuous score in [0.0, 1.0]. | P0 | FuzzyScorer returns 1.0 for identical strings, 0.0 for completely disjoint strings, and monotonically decreasing scores as edit distance increases. |
| **FR-105** | **Scoring Pipeline — RubricScorer**: Score task outputs against a dimension-weighted checklist, where each dimension has a weight (summing to 1.0) and directionality metadata. | P1 | RubricScorer with 3 dimensions (weights 0.5, 0.3, 0.2) produces a composite score equal to the weighted sum. Per-dimension scores are available individually. |
| **FR-106** | **Scoring Pipeline — CompositeScorer**: Chain multiple scorers with namespace-prefixed metric aggregation. Support waterfall judge pattern (programmatic → exact-match → fuzzy-match → LLM-judge fallback). | P1 | CompositeScorer combining ExactScorer + FuzzyScorer produces metrics keyed as `exact.score` and `fuzzy.score`. Waterfall stops at first decisive scorer; fallback engages only when prior stages are inconclusive. |
| **FR-107** | **Matrix Evaluation**: Evaluate across N axes (models × tools × task types × trials) with constraint-based explosion control: `max_cells` cap, exclusion rules, and sampling strategies (LatinSquare, Pairwise, Random). | P1 | A 3-axis matrix (2 models × 3 task types × 3 trials = 18 cells) executes all 18 cells. A matrix exceeding `max_cells=100` applies the configured sampling strategy and produces ≤100 cells. |
| **FR-108** | **Reliability Metrics — pass@k**: Compute unbiased pass@k estimator over k independent trials per task. | P0 | For k=3 with results [pass, fail, pass], pass@1 uses the unbiased estimator formula. Minimum trial count is enforced (k ≥ 3). |
| **FR-109** | **Reliability Metrics — pass^k**: Compute pessimistic pass^k (probability of passing all k trials). | P0 | For k=3 with results [pass, pass, fail], pass^3 = 0.0 (not all passed). For [pass, pass, pass], pass^3 = 1.0. |
| **FR-110** | **Reliability Metrics — Pass³**: Implement Claw-Eval's all-3-must-pass consistency metric as a special case of pass^k with k=3. | P1 | Pass³ is computed identically to pass^3 with k fixed at 3. Report both individual trial results and composite Pass³. |
| **FR-111** | **Budget Guards**: Track real-time evaluation cost (time, API calls, tokens) with configurable limits. Raise `BudgetExceeded` and terminate gracefully when any limit is reached. | P1 | An evaluation run with `max_cost=10.0` terminates after spending $10.00 in API calls and returns partial results with a `budget_exceeded` flag set to true. |
| **FR-112** | **Report Generation — JSON**: Output structured evaluation results as JSON conforming to a defined schema, including per-task scores, per-dimension aggregates, statistical summary, and metadata. | P0 | JSON output passes schema validation. All fields defined in the schema are present and non-null (except explicitly nullable fields). |
| **FR-113** | **Report Generation — Markdown**: Output human-readable Markdown reports with per-dimension tables, pass/fail summary, version-over-version comparison (when baseline provided), and statistical summary. | P0 | Markdown report contains all required sections: summary, task_results, per_dimension_scores, statistical_summary, recommendations, metadata. Each section is non-empty. |
| **FR-114** | **Evaluation Orchestration**: Coordinate end-to-end evaluation pipeline: load tasks → set up sandbox → execute → score → aggregate → report → store results. Support batch evaluation with progress tracking. | P0 | A 10-task evaluation suite runs end-to-end via `EvalRunner`, produces a complete `EvalResult` with all 10 task scores, and stores results in SQLite. Progress callback fires for each completed task. |
| **FR-115** | **Baseline Comparison**: Compare current evaluation results against a named baseline, computing per-dimension deltas and highlighting regressions/improvements. | P1 | Comparison report identifies dimensions that improved (>+5%), regressed (>-5%), or remained stable, with exact delta values. |
| **FR-116** | **Collateral Damage Detection**: Detect side effects of task execution beyond the expected output (modified files, environment changes, unexpected stdout). | P2 | After a task that modifies an unrelated file during execution, the collateral damage detector flags the modification with file path and diff. |

### 1.2 V2 — Information Collection & Tracking

| ID | Description | Priority | Acceptance Condition |
|----|-------------|----------|----------------------|
| **FR-201** | **GitHub Collector — REST**: Collect repository metadata (name, description, stars, forks, language, topics, license) via GitHub REST API with `X-GitHub-Api-Version` header pinning. | P0 | Searching for "AI agent evaluation" returns ≥1 result with all listed metadata fields populated. Rate limit headers are read and respected. |
| **FR-202** | **GitHub Collector — GraphQL**: Collect deep repository data (stars, forks, commits, releases, topics, README) in a single GraphQL request to minimize rate limit consumption. | P0 | A single GraphQL query for a known repository returns all listed fields. Total API points consumed per query is ≤2 (verified via `x-ratelimit-remaining`). |
| **FR-203** | **arXiv Collector**: Search arXiv via the `arxiv` Python library, collecting paper metadata (title, authors, abstract, categories, published date, PDF URL) with built-in pagination and retry. | P0 | Searching for "large language model benchmark" returns ≥1 result with all listed fields populated. Pagination with `limit=10` returns exactly 10 results when available. |
| **FR-204** | **Source Protocol**: Define a `SourceProtocol` (Python Protocol class) with methods: `search(query, **kwargs) → list[SourceItem]`, `fetch(item_id) → SourceItem`, `track(item_id) → TrackingHandle`, `check_updates(since) → list[ChangeEvent]`. | P0 | A mock implementation of `SourceProtocol` passes type checking. Both `GitHubCollector` and `ArxivCollector` satisfy the protocol at runtime (verified by `isinstance` check or Protocol structural subtyping). |
| **FR-205** | **Data Store — SQLite**: Store collected entities in SQLite with typed schemas for repositories, papers, and articles. Support CRUD operations, keyword search, and faceted filtering (by source, date range, language). | P0 | After storing 10 repositories, querying `store.search(language="python")` returns only Python repositories. Full-text keyword search over names and descriptions returns relevant results. |
| **FR-206** | **Token-Bucket Rate Limiter**: Implement thread-safe token-bucket rate limiting with per-source calibration: 30 req/min for GitHub search, 5,000 req/hr for GitHub core, 1 req/3s for arXiv. Adaptive back-off reads `x-ratelimit-remaining` and `x-ratelimit-reset` headers. | P0 | Under burst load (50 rapid requests to GitHub search), the rate limiter queues excess requests and delivers them at ≤30/min. When `x-ratelimit-remaining` drops below 10%, back-off doubles the inter-request interval. |
| **FR-207** | **Incremental Tracking**: Track previously collected sources using cursor/bookmark-based state in SQLite. On incremental collection, only new/changed items since the last bookmark are fetched. | P0 | After initial collection of 50 repos and a subsequent incremental run (where 3 repos changed), only 3 repos are re-fetched. Bookmark state persists across process restarts. |
| **FR-208** | **Change Detection**: Compare two collection snapshots to produce a structured diff: new items, removed items, and changed fields per item. Categorize changes by type (breaking, feature, fix, docs). | P1 | Given snapshot A (10 repos) and snapshot B (11 repos with 1 new, 1 modified star count), the diff identifies 1 addition and 1 modification with the specific changed field. |
| **FR-209** | **Collection Status**: Provide a `collect status` command showing tracking state for all monitored sources: last collection time, item count, next scheduled refresh. | P1 | `nines collect status` outputs a table listing each tracked source with `last_collected`, `item_count`, and `next_refresh` columns. |
| **FR-210** | **Data Export**: Export collected data in JSON, CSV, or Markdown format via `collect export <format>`. | P1 | `nines collect export json` produces a valid JSON file containing all collected entities with their full metadata. |
| **FR-211** | **Source Health Check**: For each configured source, execute a lightweight health-check query to verify reachability and data availability. Report active/inactive status. | P1 | `SourceProtocol.health_check()` returns `True` for a reachable GitHub API and `False` when the API is unreachable (simulated via mock). |
| **FR-212** | **Local Caching with TTL**: Cache API responses locally with configurable TTL to avoid redundant API calls. Cache invalidation on explicit refresh or TTL expiry. | P1 | A second identical query within TTL returns the cached result without making an API call. After TTL expires, the next query makes a fresh API call. |

### 1.3 V3 — Knowledge Analysis & Decomposition

| ID | Description | Priority | Acceptance Condition |
|----|-------------|----------|----------------------|
| **FR-301** | **Code Review — AST Analysis**: Parse Python source files using the built-in `ast` module. Extract functions, classes, imports, and compute per-function cyclomatic complexity. | P0 | Given a Python file with 5 functions, the extractor returns all 5 with correct names, signatures, line numbers, and complexity scores. Syntax errors in target files produce structured errors. |
| **FR-302** | **Code Review — Multi-file Analysis**: Resolve cross-file imports within a project and construct a dependency adjacency list. Compute coupling metrics: afferent coupling (Ca), efferent coupling (Ce), instability index I = Ce/(Ca+Ce). | P0 | For a 3-module project where module A imports B and C, B imports C: module C has Ca=2, Ce=0, I=0.0. Module A has Ca=0, Ce=2, I=1.0. |
| **FR-303** | **Structure Analysis**: Analyze repository directory layout, identify module boundaries (`__init__.py` presence), detect layers (presentation, business, data) via directory naming heuristics, and construct a module dependency graph. | P0 | For a Flask project with `app/routes/`, `app/models/`, `app/services/` directories, the analyzer identifies 3 layers and constructs the correct dependency graph. |
| **FR-304** | **Architecture Pattern Detection**: Recognize architectural patterns (MVC, hexagonal, layered, microservices, plugin/extension) using multi-signal heuristics with confidence scoring. Each detected pattern includes a confidence value ≥ 0.0 and ≤ 1.0. | P1 | For a Flask MVC project, the detector returns `{pattern: "MVC", confidence: 0.75}` or higher. For a flat script project, no pattern is detected with confidence above 0.5. |
| **FR-305** | **Functional Decomposition**: Decompose codebases into atomic knowledge units at function/method granularity. Each unit includes signature, body, docstring, complexity score, and dependency list. | P0 | A module with 8 functions and 2 classes produces ≥10 `KnowledgeUnit` instances (8 functions + 2 class-level units). Each unit has a non-empty `source` reference. |
| **FR-306** | **Concern-Based Decomposition**: Group code elements by cross-cutting concern (error handling, logging, validation, configuration) across files. | P1 | In a project where 3 files contain try/except blocks, the concern-based decomposer groups all exception-handling code into a single "error_handling" concern unit with references to all 3 source files. |
| **FR-307** | **Layer-Based Decomposition**: Assign code elements to architectural layers identified by structure analysis. | P1 | After structure analysis identifies 3 layers, every `KnowledgeUnit` from functional decomposition is assigned to exactly one layer. Unassigned units are grouped under "unclassified". |
| **FR-308** | **Knowledge Indexing**: Store decomposed knowledge units in SQLite with metadata (source, type, complexity, timestamp). Support keyword search over unit names and content, and faceted filtering by language, type, and complexity range. | P0 | After indexing 100 knowledge units, `index.search("rate limiter")` returns units whose name or content contains "rate limiter", ranked by relevance. Faceted query `index.filter(complexity_gt=10)` returns only high-complexity units. |
| **FR-309** | **Pattern Abstraction**: Extract reusable patterns from analyzed code — common function signatures, repeated import patterns, design patterns (factory, observer, strategy, adapter, decorator) — identified from structural signatures. | P2 | After analyzing 5 modules that all implement the same `Protocol`-based interface pattern, the abstractor identifies it as a repeated pattern with frequency=5 and structural description. |
| **FR-310** | **Analysis Pipeline Orchestration**: Coordinate the end-to-end analysis flow: ingest → parse → analyze → decompose → index. Support batch analysis with file-level caching (skip unchanged files on re-analysis) and error isolation (single-file failure does not abort the pipeline). | P0 | Analyzing a 20-file project completes even when 2 files have syntax errors. Re-analyzing after modifying 3 files only re-processes those 3 files (verified by timestamp comparison). |
| **FR-311** | **Analysis Pipeline — Progress Reporting**: Emit progress events during analysis (files parsed, units extracted, patterns found) for CLI progress display and programmatic consumption. | P1 | During a 20-file analysis, the pipeline fires at least 20 progress events (one per file) with `{file, stage, status}` payloads. |

### 1.4 Integration — Orchestration, Self-Evaluation & Self-Iteration

| ID | Description | Priority | Acceptance Condition |
|----|-------------|----------|----------------------|
| **FR-401** | **Workflow Engine**: Define and execute multi-step workflows combining evaluation, collection, and analysis stages. Support serial, parallel, and conditional branching. | P1 | A workflow defined as `[collect, analyze, eval]` executes all three stages in sequence. Each stage receives the prior stage's output as input. |
| **FR-402** | **Cross-Vertex Data Flow**: Implement typed artifact passing between vertices via SQLite-backed storage: V1 `GapAnalysis` → V2 search queries (F1); V2 `CollectedSource` → V3 analysis targets (F3); V3 `KnowledgeUnit` → V1 task candidates (F5). | P1 | After V1 identifies a gap `{dimension: "reliability", gap: 0.18}`, a corresponding V2 search query is generated and stored. The query is retrievable via `SearchQueryGenerator.pending()`. |
| **FR-403** | **Self-Evaluation Runner**: Execute the 19-dimension self-evaluation suite defined in `self_eval_spec.md`. Each dimension produces a score, measurement method, evidence list, and stability flag. | P0 | Running `SelfEvalRunner.run(dimensions="all")` produces a `SelfEvalResult` with 19 non-null dimension scores. Each score includes `value`, `unit`, `direction`, and `measurements` list. |
| **FR-404** | **Baseline Management**: Create, store, list, compare, and label self-evaluation baseline snapshots. Baselines persist in SQLite with full dimension scores, metadata, and timestamps. | P0 | Creating baseline "v0.1", then running self-eval and comparing against it, produces a `ComparisonReport` with per-dimension deltas. `BaselineManager.list()` returns all saved baselines with labels and timestamps. |
| **FR-405** | **Score History**: Store self-evaluation scores across iterations in SQLite. Support time-series queries (score[t] for any dimension) and version-over-version comparison with trend detection. | P0 | After 5 iterations, `ScoreHistory.get_series("D01")` returns a list of 5 scores with timestamps. Trend detection identifies whether D01 is improving, stable, or regressing. |
| **FR-406** | **Gap Detection**: Compare current self-evaluation scores against baselines or targets. Produce a ranked list of capability gaps sorted by magnitude, with actionable labels (dimension, current, target, gap, priority). | P0 | Given current D01=0.82 and target=0.90, the gap detector produces `{dimension: "D01", current: 0.82, target: 0.90, gap: 0.08, priority: "high"}`. Gaps are sorted largest-first. |
| **FR-407** | **Improvement Planner**: Generate improvement plans from gap analysis. Each plan contains ≤3 improvement actions per iteration (bounded to prevent scope creep), with action type, target dimension, expected impact, and implementation hint. | P1 | Given 5 gaps, the planner selects the top 3 by priority and generates an `ImprovementPlan` with exactly 3 actions. Each action has `type`, `dimension`, `expected_delta`, and `description`. |
| **FR-408** | **Convergence Detection**: Implement composite convergence check using four statistical methods under majority vote: (1) sliding window variance (threshold=0.001), (2) relative improvement rate (min_improvement=0.005), (3) Mann-Kendall trend test (95% confidence), (4) CUSUM change detection. Convergence is declared when ≥3 of 4 applicable methods agree. | P0 | A time series `[0.70, 0.75, 0.78, 0.79, 0.795, 0.798, 0.799]` triggers convergence at index 5–6 (all methods agree improvement has plateaued). A series `[0.70, 0.75, 0.80, 0.75, 0.80, 0.75]` is detected as oscillating (Mann-Kendall shows no trend, CUSUM detects changes). |
| **FR-409** | **MAPIM Loop**: Implement the Measure → Analyze → Plan → Improve → Measure feedback loop with configurable `max_iterations` (default 10) and per-iteration action budget (max 3). Typed intermediate artifacts (`MeasurementSnapshot`, `GapAnalysis`, `ImprovementPlan`, `ImprovementAction`) are stored in SQLite. | P1 | Executing `SelfImprovementLoop.run(max_iterations=5)` produces an `IterationResult` with ≤5 rounds. Each round contains gap analysis, plan, execution status, and before/after scores. The loop terminates early if convergence is detected. |
| **FR-410** | **Optimization Lifecycle**: Track improvement action status through a state machine: Proposed → Approved → Applied → Validated / Rejected / RolledBack. | P1 | An action transitions from Proposed → Applied → Validated when its target dimension improves. An action transitions to RolledBack when the dimension regresses by >5% after application. |
| **FR-411** | **Multi-Round Stability Verification**: Verify baseline and score stability by repeating measurements 3× and checking coefficient of variation (CV ≤ 0.05). For binary metrics, all 3 runs must agree. | P0 | Running D01 scoring 3 times produces `[0.91, 0.92, 0.91]` with CV=0.006 → stable. Producing `[0.70, 0.85, 0.90]` with CV=0.12 → flagged as unstable. |
| **FR-412** | **Aggregate Scoring**: Compute per-vertex and composite scores using the formula: `composite = 0.30×V1 + 0.25×V2 + 0.25×V3 + 0.20×system`. Weights are configurable via `NinesConfig.self_eval.weights`. | P0 | Given V1=0.89, V2=0.87, V3=0.72, system=0.95, the composite score equals 0.30×0.89 + 0.25×0.87 + 0.25×0.72 + 0.20×0.95 = 0.854. Changing weights via config produces different composites. |

### 1.5 Delivery — CLI, Agent Skill & Programmatic API

| ID | Description | Priority | Acceptance Condition |
|----|-------------|----------|----------------------|
| **FR-501** | **CLI — `nines eval`**: Run evaluation benchmarks via `nines eval <TASK_OR_SUITE> [OPTIONS]`. Supports options: `--scorer`, `--sandbox`, `--seed`, `--timeout`, `--parallel`, `--baseline`, `--matrix`, `--report`. | P0 | `nines eval tasks/coding.toml --scorer composite --sandbox --seed 42` executes the task in sandbox with seed 42, uses composite scorer, and returns exit code 0 on success. `--help` shows all options. |
| **FR-502** | **CLI — `nines collect`**: Search and collect information via `nines collect <SOURCE> <QUERY> [OPTIONS]`. Supports options: `--limit`, `--incremental`, `--store`, `--track`, `--since`, `--sort`, `--fields`. Subcommands: `status`, `update`, `list`, `export`. | P0 | `nines collect github "AI agent evaluation" --limit 20` returns ≤20 results. `nines collect status` shows tracking state. Exit code 0 on success. |
| **FR-503** | **CLI — `nines analyze`**: Analyze knowledge via `nines analyze <TARGET> [OPTIONS]`. Supports options: `--depth`, `--decompose`, `--index`, `--reviewers`, `--target-lang`. Subcommands: `review`, `structure`, `search`, `graph`. | P0 | `nines analyze ./target-repo --depth deep --decompose --index` produces analysis results, decomposes into knowledge units, and updates the index. Exit code 0 on success. |
| **FR-504** | **CLI — `nines self-eval`**: Run self-evaluation via `nines self-eval [OPTIONS]`. Supports options: `--dimensions`, `--baseline`, `--compare`, `--report`, `--save`, `--label`. Subcommands: `baseline list`, `baseline show`, `history`, `dimensions`. | P0 | `nines self-eval --report --compare --format markdown` produces a Markdown self-evaluation report with baseline comparison. |
| **FR-505** | **CLI — `nines iterate`**: Execute self-improvement iteration via `nines iterate [OPTIONS]`. Supports options: `--max-rounds`, `--convergence-threshold`, `--focus`, `--dry-run`, `--plan-only`. Subcommands: `status`, `plan`, `gaps`, `history`. | P1 | `nines iterate --max-rounds 3 --dry-run` shows planned improvements for 3 rounds without executing them. |
| **FR-506** | **CLI — `nines install`**: Install/uninstall NineS as agent skill via `nines install [OPTIONS]`. Supports options: `--target` (required: cursor/claude/all), `--uninstall`, `--global`, `--project-dir`, `--dry-run`, `--force`. | P0 | `nines install --target cursor` creates `.cursor/skills/nines/` with SKILL.md, 6 command files, and 2 reference files. `nines install --target cursor --uninstall` removes the directory. |
| **FR-507** | **CLI — Global Options**: All commands support: `--config`, `--verbose`/`-v`, `--quiet`/`-q`, `--output`/`-o`, `--format`/`-f` (text/json/markdown), `--no-color`, `--version`, `--help`. | P0 | `nines --version` prints the version string. `nines eval --format json` outputs JSON. `--verbose` increases log detail; `--quiet` suppresses non-essential output. |
| **FR-508** | **CLI — Exit Codes**: Use consistent exit codes: 0=SUCCESS, 1=INVALID_ARGS, 2=NOT_FOUND, 3=EXECUTION_ERROR, 4=TIMEOUT, 5=SANDBOX_ERROR, 10=CONFIG_ERROR, 11=DEPENDENCY_ERROR, 20=CONVERGENCE_FAIL, 130=INTERRUPTED. | P0 | A non-existent task file produces exit code 2. A timeout produces exit code 4. Ctrl+C produces exit code 130. |
| **FR-509** | **CLI — Structured Error Reporting**: Errors are reported to stderr in a structured format with error code, category, message, location, detail, and hint. When `--format json` is active, errors are also emitted as JSON. | P1 | A task timeout error produces stderr output containing the error code (E003), human-readable message, and actionable hint. With `--format json`, the same error is output as a JSON object. |
| **FR-510** | **Programmatic API**: Expose top-level Python functions `nines.eval()`, `nines.collect()`, `nines.analyze()`, `nines.self_eval()`, `nines.iterate()`, `nines.install()` that mirror CLI commands. Return typed dataclass results (`EvalResult`, `CollectionResult`, `AnalysisResult`, `SelfEvalResult`, `IterationResult`, `InstallResult`). | P0 | `result = nines.eval("suite", scorer="composite", sandbox=True)` returns an `EvalResult` with `.score_card.overall`, `.task_results`, and `.to_json()` method. All return types have type hints. |
| **FR-511** | **Configuration Object**: `NinesConfig` supports 3-level merge (project `nines.toml` → user `~/.config/nines/config.toml` → defaults). Runtime overrides via CLI args and environment variables. Invalid config produces structured errors. | P0 | Config with project-level `eval.default_scorer = "exact"` overrides the default "composite". Missing required fields produce a `ConfigError` with the field path and expected type. |
| **FR-512** | **Event System**: `EventBus` supports subscribing to typed events (`EVAL_TASK_COMPLETE`, `COLLECTION_ITEM_FOUND`, `ANALYSIS_FILE_PARSED`, etc.) via decorator or method. Events carry typed payloads. | P1 | Registering a handler for `EVAL_TASK_COMPLETE` and running an evaluation results in the handler being called once per completed task with `{task_id, score}` payload. |
| **FR-513** | **Cursor Skill Adapter**: Generate a complete Cursor skill directory (`.cursor/skills/nines/`) containing `SKILL.md`, 6 command workflow files (`commands/*.md`), and reference files. SKILL.md follows Cursor's skill protocol with command table, invocation rules, and examples. | P0 | After `nines install --target cursor`, the file `.cursor/skills/nines/SKILL.md` exists and contains all 6 command entries. Each command file in `commands/` contains the `<nines_cursor_adapter>` header and workflow steps. |
| **FR-514** | **Claude Code Adapter**: Generate Claude Code integration files (`.claude/commands/nines/*.md`) with YAML frontmatter and semantic XML body. Append a NineS section to `CLAUDE.md` using `<!-- nines:start -->` / `<!-- nines:end -->` markers. | P0 | After `nines install --target claude`, each command file has valid YAML frontmatter with `name`, `description`, `argument-hint`, and `allowed-tools`. `CLAUDE.md` contains the NineS section between markers. |
| **FR-515** | **Skill Manifest**: Maintain a JSON manifest (`manifest.json`) as the single source of truth for skill identity, capabilities, commands, dependencies, and runtime compatibility. Validate against schema rules (SemVer version, PEP 440 Python specifier, capability-command consistency). | P0 | `manifest.json` passes all 5 validation rules defined in the spec. Modifying `commands[].capability` to reference a non-existent capability causes validation failure with a descriptive error. |
| **FR-516** | **Version Management**: On `nines install`, detect existing installations and handle version comparison: skip if same version (unless `--force`), upgrade if older, warn if newer (downgrade requires `--force`). | P1 | Installing v0.2.0 over v0.1.0 performs an in-place upgrade. Installing v0.1.0 over v0.2.0 without `--force` prints a warning and exits without changes. |

---

## 2. Non-Functional Requirements

### 2.1 Performance

| ID | Requirement | Target | Measurement Method |
|----|-------------|--------|--------------------|
| **NFR-01** | Evaluation pipeline end-to-end latency (single task, no network) | p50 ≤ 30s, p95 ≤ 120s (MVP); p50 ≤ 15s, p95 ≤ 60s (v2) | Time `EvalRunner.run()` across golden test set (≥30 tasks); report p50 and p95 per-stage and total. |
| **NFR-02** | Sandbox creation + teardown overhead | ≤ 5s per venv (cold), ≤ 1s (warm pool) | Time `SandboxManager.create()` and `.destroy()` over 10 cycles; report mean and p95. |
| **NFR-03** | GitHub collection throughput | ≥ 50 entities/min (REST core), ≥ 30 entities/min (search), respecting rate limits | Run timed collection; compute entities/minute per API tier. Must not exceed documented rate limits. |
| **NFR-04** | arXiv collection throughput | ≥ 20 entities/min (respecting 1 req/3s limit) | Run timed collection for 5 minutes; compute entities/minute. |
| **NFR-05** | Code analysis throughput | ≥ 100 files/min for AST extraction (standard Python files) | Time `CodeExtractor` across a 500-file project; compute files/minute. |
| **NFR-06** | CLI cold start time | ≤ 2s from invocation to first output | Time `nines --help` from shell invocation to stdout; 10 measurements, report p50. |
| **NFR-07** | SQLite query latency for score history | ≤ 100ms for time-series retrieval (1000 data points) | Insert 1000 score records; time `ScoreHistory.get_series()` call; report p50. |
| **NFR-08** | Memory footprint during evaluation | ≤ 500MB RSS for a 100-task evaluation suite | Monitor RSS via `resource.getrusage()` during a 100-task run; report peak. |

### 2.2 Isolation & Determinism

| ID | Requirement | Target | Measurement Method |
|----|-------------|--------|--------------------|
| **NFR-09** | Sandbox isolation — no host pollution | 100% clean `PollutionReport` across all evaluation runs | Wrap every execution with `execute_with_pollution_check()`. Before/after `EnvironmentSnapshot` diff: env vars, watched files, directory listings, `sys.path`. Any diff = critical bug. |
| **NFR-10** | Sandbox isolation — no cross-sandbox pollution | Two concurrent sandboxes produce independent results | Run two sandboxes simultaneously with conflicting operations (e.g., install different package versions). Verify each sandbox's results are independent. |
| **NFR-11** | Deterministic evaluation (same seed) | Multi-round variance (CV) ≤ 5% for deterministic tasks | Run each golden test task 3× with identical seed. Compute CV across runs. For tasks without inherent randomness, require CV = 0. |
| **NFR-12** | Seed control coverage | `PYTHONHASHSEED`, `NINES_SEED`, and per-framework seeds (numpy, random) all set from a single master seed | Verify via env var inspection and output fingerprinting (sha256 of stdout+stderr+exit_code) across 3 runs with same seed. |

### 2.3 Extensibility

| ID | Requirement | Target | Measurement Method |
|----|-------------|--------|--------------------|
| **NFR-13** | New data source plugin cost | ≤ 1 file (implementing `SourceProtocol`) + ≤ 20 lines of registration code | Implement a mock `RSSCollector` satisfying `SourceProtocol`. Measure total lines of new code (excluding tests). |
| **NFR-14** | New scorer plugin cost | ≤ 1 file (implementing `Scorer` Protocol) + ≤ 10 lines of registration | Implement a mock `RegexScorer`. Measure total lines of new code (excluding tests). |
| **NFR-15** | New analyzer plugin cost | ≤ 1 file (implementing `Analyzer` Protocol) + ≤ 10 lines of registration | Implement a mock `SecurityAnalyzer`. Measure total lines of new code (excluding tests). |
| **NFR-16** | New agent runtime adapter cost | ≤ 1 `SkillEmitter` subclass + tool name mapping table + command template | Implement a mock `CopilotEmitter`. Measure total new files and lines. |
| **NFR-17** | Configuration extensibility | New config sections are addable without modifying existing config code | Add a hypothetical `nines.toml` section `[experimental]` with one new key. Verify existing config loading is unaffected. |

### 2.4 Reliability & Error Handling

| ID | Requirement | Target | Measurement Method |
|----|-------------|--------|--------------------|
| **NFR-18** | Graceful degradation on source failure | Collection pipeline skips failed sources, reports partial results, completes without crash | Simulate GitHub API returning 503 for one source while arXiv succeeds. Verify arXiv results are returned with a `partial_failure` flag and error details for GitHub. |
| **NFR-19** | Pipeline stage retry on transient failures | ≤ 3 automatic retries with exponential backoff for transient HTTP errors (429, 500, 502, 503) | Simulate 2 consecutive 503 responses followed by success. Verify the request succeeds on the 3rd attempt without manual intervention. |
| **NFR-20** | Error hierarchy | All errors derive from `NinesError`. Sub-hierarchies: `EvalError`, `CollectionError`, `AnalysisError`, `IterationError`, `ConfigError`, `SandboxError`. | Verify `isinstance(SandboxTimeoutError(), NinesError)` is `True`. Each error type has `code`, `message`, and optional `hint` fields. |
| **NFR-21** | No silent failures | Every caught exception is logged, re-raised, or returns explicit error state. No bare `except: pass`. | Static analysis (grep + AST check) finds zero instances of bare `except: pass` or `except Exception: pass` without logging. |
| **NFR-22** | Analysis pipeline error isolation | Single-file parse errors do not abort multi-file analysis | Analyze a 20-file project where 2 files have syntax errors. Verify 18 files produce results and 2 produce structured `ParseError` entries. |

### 2.5 Maintainability

| ID | Requirement | Target | Measurement Method |
|----|-------------|--------|--------------------|
| **NFR-23** | Code coverage | ≥ 85% line coverage across `src/nines/` | Run `pytest --cov=src/nines --cov-report=term-missing`. Verify total coverage ≥ 85%. |
| **NFR-24** | Lint clean | Zero ruff errors across `src/nines/` and `tests/` | Run `ruff check .`. Verify exit code 0 and zero output. |
| **NFR-25** | Type annotations | 100% of public functions and methods have type annotations | Run `mypy src/nines/ --strict` or equivalent. Verify zero errors for missing annotations on public APIs. |
| **NFR-26** | Docstring coverage | 100% of public classes and functions have docstrings | AST-based check verifying every public class/function has a non-empty `__doc__`. |
| **NFR-27** | Dependency count | ≤ 15 direct runtime dependencies (excluding dev/test) | Count entries in `[project.dependencies]` in `pyproject.toml`. |

---

## 3. Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| **CON-01** | **Python 3.12+** | Required for `ast` module features, performance improvements, and modern typing. All surveyed benchmarks and the LLM ecosystem are Python-first (Synthesis §2.2). |
| **CON-02** | **uv** for package management | 10-100× faster venv creation directly benefits per-evaluation sandbox throughput (Synthesis §2.3). |
| **CON-03** | **ruff** for linting and formatting | Single tool replacing flake8+black+isort; configured in `pyproject.toml` (Synthesis §2.4). |
| **CON-04** | **SQLite** for local storage | Zero-infrastructure, single-file database. Full SQL for score history queries. Stdlib `sqlite3` module — no external dependency (Synthesis §2.5). |
| **CON-05** | **No Docker dependency for MVP sandbox** | Docker adds infrastructure friction. MVP uses venv + subprocess + tempfile (3-layer sandbox). Docker is the planned Tier 2 extension (Synthesis §3.6). |
| **CON-06** | **Offline operation** (except external API calls) | NineS must function without internet access for all operations except GitHub/arXiv API calls and LLM API calls. No phone-home, no license server, no cloud dependencies. |
| **CON-07** | **Single-user local tool** | NineS is designed for single-user operation. No multi-user authentication, no server mode, no shared database. SQLite WAL mode is sufficient (Synthesis §2.5). |
| **CON-08** | **JSON for machine output, TOML for user config** | JSON for manifests and reports (strict schema, universal parsing). TOML for `nines.toml` (human-readable, comment support, Python ecosystem convention). |
| **CON-09** | **Protocol-based interfaces** | All inter-module boundaries use Python Protocol classes for structural subtyping. No abstract base class inheritance required (enables easier testing and plugin development). |
| **CON-10** | **MVP runtime targets: Cursor + Claude Code only** | Two runtimes for MVP. Architecture supports additional runtimes via new `SkillEmitter` subclasses (Skill Interface Spec §Appendix B). |

---

## 4. Goal Traceability Matrix

The matrix below maps every functional requirement, non-functional requirement, and constraint to the five project goals defined in the execution plan.

**Goals**:
- **G1**: Capability and responsibility division — clear three-vertex model with defined sub-capabilities
- **G2**: First-round knowledge collection and research — proven technology choices, validated patterns
- **G3**: Architecture design — module structure, interfaces, data flows
- **G4**: MVP implementation and verification — working code, tests, baselines
- **G5**: Self-iterating toolflow — feedback loop, convergence, growth evaluation

### 4.1 Functional Requirements → Goals

| Requirement | G1 | G2 | G3 | G4 | G5 |
|-------------|:--:|:--:|:--:|:--:|:--:|
| **V1 — Evaluation & Benchmarking** | | | | | |
| FR-101 Task Definition | x | | x | x | |
| FR-102 Task Loading | | | x | x | |
| FR-103 ExactScorer | | x | x | x | |
| FR-104 FuzzyScorer | | x | x | x | |
| FR-105 RubricScorer | | x | x | x | |
| FR-106 CompositeScorer | | x | x | x | |
| FR-107 Matrix Evaluation | | x | x | x | |
| FR-108 pass@k | | x | x | x | |
| FR-109 pass^k | | x | x | x | |
| FR-110 Pass³ | | x | | x | |
| FR-111 Budget Guards | | x | x | x | |
| FR-112 JSON Report | | | x | x | |
| FR-113 Markdown Report | | | x | x | |
| FR-114 Eval Orchestration | x | | x | x | |
| FR-115 Baseline Comparison | | | | x | x |
| FR-116 Collateral Damage | | x | | x | |
| **V2 — Information Collection** | | | | | |
| FR-201 GitHub REST | x | x | x | x | |
| FR-202 GitHub GraphQL | | x | x | x | |
| FR-203 arXiv Collector | x | x | x | x | |
| FR-204 Source Protocol | x | | x | x | |
| FR-205 Data Store | | | x | x | |
| FR-206 Rate Limiter | | x | x | x | |
| FR-207 Incremental Tracking | x | | x | x | |
| FR-208 Change Detection | x | | x | x | |
| FR-209 Collection Status | | | | x | |
| FR-210 Data Export | | | | x | |
| FR-211 Source Health Check | | | x | x | |
| FR-212 Local Caching | | x | x | x | |
| **V3 — Knowledge Analysis** | | | | | |
| FR-301 AST Analysis | x | x | x | x | |
| FR-302 Multi-file Analysis | x | | x | x | |
| FR-303 Structure Analysis | x | | x | x | |
| FR-304 Architecture Detection | x | x | x | x | |
| FR-305 Functional Decomposition | x | | x | x | |
| FR-306 Concern Decomposition | x | | x | x | |
| FR-307 Layer Decomposition | x | | x | x | |
| FR-308 Knowledge Indexing | x | | x | x | |
| FR-309 Pattern Abstraction | x | x | | x | |
| FR-310 Analysis Orchestration | | | x | x | |
| FR-311 Progress Reporting | | | | x | |
| **Integration** | | | | | |
| FR-401 Workflow Engine | | | x | x | x |
| FR-402 Cross-Vertex Data Flow | x | | x | x | x |
| FR-403 Self-Eval Runner | x | | x | x | x |
| FR-404 Baseline Management | | | | x | x |
| FR-405 Score History | | | | x | x |
| FR-406 Gap Detection | | | x | x | x |
| FR-407 Improvement Planner | | | x | x | x |
| FR-408 Convergence Detection | | x | x | x | x |
| FR-409 MAPIM Loop | | | x | x | x |
| FR-410 Optimization Lifecycle | | x | x | x | x |
| FR-411 Stability Verification | | x | | x | x |
| FR-412 Aggregate Scoring | | | | x | x |
| **Delivery** | | | | | |
| FR-501 CLI eval | | | x | x | |
| FR-502 CLI collect | | | x | x | |
| FR-503 CLI analyze | | | x | x | |
| FR-504 CLI self-eval | | | x | x | x |
| FR-505 CLI iterate | | | x | x | x |
| FR-506 CLI install | | | x | x | |
| FR-507 Global Options | | | x | x | |
| FR-508 Exit Codes | | | x | x | |
| FR-509 Structured Errors | | | x | x | |
| FR-510 Programmatic API | | | x | x | |
| FR-511 Configuration | | | x | x | |
| FR-512 Event System | | | x | x | |
| FR-513 Cursor Skill Adapter | | x | x | x | |
| FR-514 Claude Code Adapter | | x | x | x | |
| FR-515 Skill Manifest | | x | x | x | |
| FR-516 Version Management | | | | x | |

### 4.2 Non-Functional Requirements → Goals

| Requirement | G1 | G2 | G3 | G4 | G5 |
|-------------|:--:|:--:|:--:|:--:|:--:|
| NFR-01 Pipeline Latency | | | x | x | x |
| NFR-02 Sandbox Overhead | | | x | x | |
| NFR-03 GitHub Throughput | | | | x | |
| NFR-04 arXiv Throughput | | | | x | |
| NFR-05 Analysis Throughput | | | | x | |
| NFR-06 CLI Start Time | | | | x | |
| NFR-07 SQLite Query Latency | | | | x | x |
| NFR-08 Memory Footprint | | | | x | |
| NFR-09 No Host Pollution | | x | x | x | |
| NFR-10 No Cross Pollution | | x | x | x | |
| NFR-11 Determinism (CV ≤ 5%) | | x | x | x | x |
| NFR-12 Seed Control | | x | x | x | |
| NFR-13 Source Plugin Cost | x | | x | | |
| NFR-14 Scorer Plugin Cost | x | | x | | |
| NFR-15 Analyzer Plugin Cost | x | | x | | |
| NFR-16 Runtime Adapter Cost | x | | x | | |
| NFR-17 Config Extensibility | | | x | | |
| NFR-18 Graceful Degradation | | | x | x | |
| NFR-19 Retry Transient Errors | | | x | x | |
| NFR-20 Error Hierarchy | | | x | x | |
| NFR-21 No Silent Failures | | | x | x | |
| NFR-22 Error Isolation | | | x | x | |
| NFR-23 Coverage ≥ 85% | | | | x | |
| NFR-24 Lint Clean | | | | x | |
| NFR-25 Type Annotations | | | | x | |
| NFR-26 Docstring Coverage | | | | x | |
| NFR-27 Dependency Count | | | x | x | |

### 4.3 Constraints → Goals

| Constraint | G1 | G2 | G3 | G4 | G5 |
|-----------|:--:|:--:|:--:|:--:|:--:|
| CON-01 Python 3.12+ | | x | x | x | |
| CON-02 uv | | x | x | x | |
| CON-03 ruff | | | x | x | |
| CON-04 SQLite | | x | x | x | x |
| CON-05 No Docker | | x | x | x | |
| CON-06 Offline operation | | | x | x | |
| CON-07 Single-user | | | x | x | |
| CON-08 JSON/TOML split | | | x | x | |
| CON-09 Protocol interfaces | x | | x | x | |
| CON-10 Cursor + Claude MVP | | x | x | x | |

### 4.4 Goal Coverage Summary

| Goal | FR Count | NFR Count | CON Count | Total | Coverage |
|------|----------|-----------|-----------|-------|----------|
| **G1** — Capability division | 22 | 4 | 2 | 28 | Full — three-vertex model with 18 sub-capabilities mapped to concrete requirements |
| **G2** — Knowledge & research | 18 | 6 | 5 | 29 | Full — technology decisions, external patterns, and domain knowledge all reflected |
| **G3** — Architecture design | 42 | 18 | 9 | 69 | Full — module boundaries, interfaces, data flows, and extensibility points defined |
| **G4** — MVP implementation | 55 | 22 | 8 | 85 | Full — every module has testable requirements with acceptance conditions |
| **G5** — Self-iteration | 15 | 3 | 1 | 19 | Full — MAPIM loop, convergence detection, baseline management, growth evaluation |

---

## 5. Requirement Priority Summary

| Priority | Count | Scope |
|----------|-------|-------|
| **P0** — Must have for MVP | 38 | Core evaluation pipeline, basic collection, AST analysis, self-eval runner, CLI commands, API, skill adapters, configuration |
| **P1** — Should have for MVP | 21 | Matrix evaluation, advanced scorers, change detection, improvement planner, workflow engine, event system, version management |
| **P2** — Nice to have | 2 | Collateral damage detection, pattern abstraction |

---

## 6. Cross-Reference Index

### 6.1 Source Document Mapping

| Requirement Range | Primary Source Document |
|-------------------|----------------------|
| FR-101 – FR-116 | `capability_model.md` §2 (V1), `synthesis_report.md` §3.1 |
| FR-201 – FR-212 | `capability_model.md` §3 (V2), `synthesis_report.md` §3.3 |
| FR-301 – FR-311 | `capability_model.md` §4 (V3), `synthesis_report.md` §3.4 |
| FR-401 – FR-412 | `self_eval_spec.md`, `capability_model.md` §5, `synthesis_report.md` §3.5 |
| FR-501 – FR-516 | `skill_interface_spec.md` |
| NFR-01 – NFR-08 | `self_eval_spec.md` §D16, `synthesis_report.md` §2 |
| NFR-09 – NFR-12 | `self_eval_spec.md` §D17, `synthesis_report.md` §3.6 |
| NFR-13 – NFR-17 | `capability_model.md` §7, `synthesis_report.md` §3 |
| NFR-18 – NFR-22 | `synthesis_report.md` §4, `self_eval_spec.md` |
| NFR-23 – NFR-27 | Execution plan gate profile (≥85 composite, ≥80% coverage) |
| CON-01 – CON-10 | `synthesis_report.md` §2, `skill_interface_spec.md` §A |

### 6.2 Risk Mitigation Mapping

| Risk (from Synthesis §4) | Mitigating Requirements |
|--------------------------|------------------------|
| R01 API Rate Limiting | FR-206, FR-212, NFR-03, NFR-04 |
| R02 Sandbox Escape | NFR-09, NFR-10, FR-116 |
| R03 Evaluation Non-Determinism | NFR-11, NFR-12, FR-411 |
| R04 Scope Creep in Self-Iteration | FR-407 (≤3 actions), FR-408, FR-409 (max_iterations) |
| R05 External API Drift | FR-204 (Protocol abstraction), NFR-19, CON-09 |
| R06 Combinatorial Explosion | FR-107 (max_cells, sampling), FR-111 (budget guards) |
| R07 Skill Transpilation Fidelity | FR-513, FR-514, FR-515 (validation rules) |
| R08 SQLite Concurrency | CON-07 (single-user), FR-205 (WAL mode) |

### 6.3 Self-Evaluation Dimension Mapping

| Dimension (from self_eval_spec.md) | Primary Requirements |
|------------------------------------|---------------------|
| D01 Scoring Accuracy | FR-103, FR-104, FR-105, FR-106 |
| D02 Evaluation Coverage | FR-102, FR-107, FR-114 |
| D03 Reliability (Pass^k) | FR-108, FR-109, FR-110, NFR-11 |
| D04 Report Quality | FR-112, FR-113 |
| D05 Scorer Agreement | FR-105, FR-106 |
| D06 Source Coverage | FR-201, FR-202, FR-203, FR-211 |
| D07 Tracking Freshness | FR-207, FR-208 |
| D08 Change Detection Recall | FR-208 |
| D09 Data Completeness | FR-205, FR-201, FR-202, FR-203 |
| D10 Collection Throughput | NFR-03, NFR-04, FR-206 |
| D11 Decomposition Coverage | FR-305, FR-306, FR-307 |
| D12 Abstraction Quality | FR-304, FR-309 |
| D13 Code Review Accuracy | FR-301, FR-302 |
| D14 Index Recall | FR-308 |
| D15 Structure Recognition | FR-303, FR-304 |
| D16 Pipeline Latency | NFR-01, NFR-02 |
| D17 Sandbox Isolation | NFR-09, NFR-10 |
| D18 Convergence Rate | FR-408, FR-409 |
| D19 Cross-Vertex Synergy | FR-402, FR-401 |

---

*Consolidates all S01 research and S02 capability definitions into the authoritative requirements document for S03 architecture design.*
*Last modified: 2026-04-11*
