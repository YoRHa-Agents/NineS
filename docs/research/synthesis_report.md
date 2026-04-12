# NineS Research Synthesis Report

> **Task**: T06 — Research Synthesis | **Team**: Research L3
> **Synthesizes**: T01 (EvoBench), T02 (GSD), T03 (External Frameworks), T04 (Domain Knowledge)
> **Last Modified**: 2026-04-11

---

## 1. Executive Summary

NineS is a self-iterating AI agent evaluation and skill-delivery platform. Research across four areas — EvoBench's Rust-based evaluation engine (T01), GSD's multi-runtime skill transpilation framework (T02), ten external AI agent evaluation benchmarks (T03), and domain knowledge on APIs, code analysis, self-improvement, and sandboxing (T04) — converges on a clear architectural direction. The evaluation landscape is shifting from single-shot accuracy (Pass@1) toward reliability-first metrics (Pass^k, Pass³), multi-dimensional scoring, and containerized isolation, while the skill-delivery landscape demonstrates that single-source multi-target transpilation across 14+ agent runtimes is both practical and scalable.

NineS can absorb proven patterns from both EvoBench (trait-based pipeline composition, weighted multi-metric scoring, combinatorial matrix evaluation, plugin systems) and GSD (canonical skill format, per-runtime converter functions, file-backed state DAG, advisory hooks, config-driven defaults) while filling gaps that no existing tool addresses: self-improvement evaluation, knowledge decomposition assessment, cross-capability synergy measurement, and convergence analysis. The recommended technology stack — Python + uv + ruff + SQLite — optimizes for rapid iteration, broad ecosystem compatibility, and zero-infrastructure operation. The architecture should follow a core-first pattern with Protocol-based interfaces for each pipeline stage, a tiered sandbox model (venv + subprocess for MVP, Docker as extension), and a composite scoring system that subsumes all surveyed methodologies.

---

## 2. Technology Stack Decision Matrix

### 2.1 Final Selection: Python + uv + ruff + SQLite

| Component | Choice | Role |
|-----------|--------|------|
| **Language** | Python 3.12+ | Core implementation |
| **Package Manager** | uv | Dependency resolution, venv management, task runner |
| **Linter/Formatter** | ruff | Static analysis, code formatting |
| **Storage** | SQLite | Evaluation results, metrics history, configuration |

### 2.2 Language Decision

| Criterion | Python | Rust | TypeScript | Go |
|-----------|--------|------|------------|-----|
| **AST analysis of target code** | Built-in `ast` module (T04 §2.1) | Requires `syn` + cross-language parsers | `ts-morph` for TS only | No native AST for Python |
| **API client ecosystem** | `httpx`, `arxiv`, `feedparser` all mature (T04 §1) | `reqwest` works but less ecosystem breadth | `axios`/`node-fetch` comparable | `net/http` adequate |
| **Evaluation script compatibility** | Native — EvoBench eval scripts are Python (T01 §7) | Would require FFI bridge | Would require child process | Would require child process |
| **Sandbox via venv** | Native `venv` module (T04 §4.1) | Not applicable | Not applicable | Not applicable |
| **LLM library ecosystem** | `anthropic`, `openai`, `tiktoken` all Python-first | Limited | Growing but secondary | Limited |
| **Rapid prototyping** | Excellent | Slow compile cycles | Good | Good |
| **GSD skill authoring target** | Supported (T02 §2.1) | Not a GSD target | GSD is natively TS | Not a GSD target |
| **External benchmark integration** | SWE-Bench, HumanEval, AppWorld all Python (T03) | Would need wrappers | Some support | Minimal |

**Decision**: Python. The research unanimously points to Python as the optimal choice. EvoBench's evaluation scripts are Python (T01 §7.1), all major external benchmarks are Python-native (T03), the `ast` module provides zero-dependency code analysis (T04 §2.1), and the sandbox system relies on Python's `venv` module (T04 §4.1). Rust was considered for performance-critical evaluation paths (inspired by EvoBench's Rust core), but the cost of maintaining cross-language FFI bridges outweighs the benefit given NineS's I/O-bound workload profile.

### 2.3 Package Manager Decision

| Criterion | uv | pip + venv | poetry | pdm |
|-----------|-----|-----------|--------|-----|
| **Dependency resolution speed** | 10-100x faster than pip | Baseline | 2-5x slower than pip | Comparable to pip |
| **Lock file support** | Yes (`uv.lock`) | No (requires pip-tools) | Yes | Yes |
| **venv management** | Built-in (`uv venv`) | Manual | Built-in | Built-in |
| **Script/task runner** | `uv run` | No | `poetry run` | `pdm run` |
| **Sandbox venv creation** | Fast — critical for per-evaluation venvs (T04 §4.1) | Slow for repeated creation | Slow | Moderate |
| **Rust-speed installs** | Yes | No | No | No |
| **Maturity** | Production-ready (2026) | Mature | Mature | Mature |

**Decision**: uv. NineS creates sandbox venvs per evaluation run (T04 §4.1), making venv creation speed a critical path. uv's Rust-based resolver creates venvs 10-100x faster than `venv` + `pip`, directly benefiting the evaluation pipeline's throughput. Its built-in task runner (`uv run`) eliminates the need for Makefile/tox.

### 2.4 Linter/Formatter Decision

| Criterion | ruff | flake8 + black + isort | pylint | mypy (type only) |
|-----------|------|----------------------|--------|-------------------|
| **Speed** | 10-100x faster | Baseline | 5-10x slower | N/A |
| **Unified tool** | Lint + format + import sort | Three separate tools | Lint only | Type check only |
| **Configuration** | Single `pyproject.toml` section | Three config files | `.pylintrc` | `mypy.ini` |
| **Rule coverage** | 800+ rules (flake8 + pylint + isort + pyflakes + more) | Combined ~400 | ~300 | N/A |

**Decision**: ruff. Single tool replacing three, 10-100x faster, configured in `pyproject.toml` alongside uv. Reduces CI time and developer friction. mypy can be added alongside ruff for type checking.

### 2.5 Storage Decision

| Criterion | SQLite | PostgreSQL | JSON files | DuckDB |
|-----------|--------|-----------|------------|--------|
| **Zero infrastructure** | Yes — single file | Requires server | Yes | Yes — single file |
| **Concurrent writes** | WAL mode supports readers + 1 writer | Full MVCC | Manual locking | Limited concurrent writes |
| **Query capability** | Full SQL | Full SQL | None (manual traversal) | Full SQL + analytics |
| **Version comparison** | SQL window functions (T04 §3.5) | Same | Manual implementation | Superior analytics |
| **EvoBench pattern match** | Maps to EvalResult/EvalScore storage (T01 §2.1) | Over-engineered for single-user | Would repeat EvoBench's JSON approach | Good but less mature |
| **GSD pattern match** | Upgrades GSD's file-based state (T02 §7) | N/A | Direct match | N/A |
| **Portability** | Single `.db` file, stdlib `sqlite3` | Requires connection string | Files on disk | Requires `duckdb` package |
| **Backup/migration** | Copy file | `pg_dump` | Copy directory | Copy file |

**Decision**: SQLite. NineS is a single-user local tool where zero-infrastructure operation is paramount. SQLite provides full SQL query capability (needed for version-over-version comparison per T04 §3.5), handles the evaluation history workload, and requires no external process. The GSD analysis (T02 §7) shows that file-backed state works but lacks query capability — SQLite is the natural upgrade. JSON files (used by EvoBench for reports, T01 §2.6) remain the format for human-readable report output, while SQLite handles structured metric storage.

---

## 3. Key Design Decisions

### 3.1 Evaluation Engine Approach

**Decision**: Absorb EvoBench's trait-based 8-stage pipeline architecture, re-implemented as Python Protocol classes with a composite scoring system that subsumes external benchmark methodologies.

**Rationale**:

EvoBench defines a clean 8-stage pipeline via traits: TaskLoader → MatrixExpander → TaskAdapter → Executor → DataCollector → Scorer → Aggregator → Reporter (T01 §5). Each stage is independently composable via `Arc<dyn Trait>`. This separation of concerns is the strongest architectural pattern identified across all research.

The external frameworks survey (T03) reveals that scoring is the most differentiated aspect across benchmarks: SWE-Bench uses binary Pass@1, TAU-Bench introduces Pass^k for reliability, Claw-Eval adds Pass³ with multi-dimensional weighting, and VAKRA implements a waterfall judge with four sequential stages. NineS's scorer must subsume all of these.

From EvoBench, NineS absorbs:
- **Tagged-enum domain modeling** (T01 Pattern 1): Python discriminated unions for TaskInput/TaskExpected/TaskOutput
- **Weighted multi-metric scoring** (T01 Pattern 3): Per-dimension metrics with weights summing to 1.0, directionality metadata
- **Composite scorer chaining** (T01 Pattern 5): Namespace-prefixed metric aggregation
- **pass@k + pass^k dual reliability** (T01 Pattern 6): Both optimistic and pessimistic reliability
- **Budget guards** (T01 Pattern 7): Real-time cost tracking with early termination
- **Deterministic simulation** (T01 Pattern 11): Hash-seeded mock executors for pipeline testing

From external frameworks (T03), NineS absorbs:
- **Pass³** (Claw-Eval): All-3-must-pass consistency metric
- **Waterfall judge** (VAKRA): Programmatic → exact-match → fuzzy-match → LLM-judge → groundedness scoring pipeline
- **Collateral damage detection** (AppWorld): Side-effect checking in state-based evaluation
- **Progressive capability levels** (VAKRA L1-L4): Tiered difficulty assessment

**Alternatives considered**:
- *Fork EvoBench directly*: Rejected — EvoBench is Rust, and cross-language FFI complexity outweighs reuse benefit. Absorb patterns, not code.
- *Wrap external benchmarks only (Exgentic approach)*: Rejected as primary strategy — NineS needs native evaluation capability, not just benchmark aggregation. However, NineS's TaskLoader should support wrapping external formats as a secondary capability.
- *LLM-as-judge primary*: Rejected as default — T03 §Cross-Cutting Analysis Trend 4 shows the field is split between programmatic and LLM-based evaluation. NineS defaults to programmatic evaluation with LLM-as-judge as configurable fallback.

### 3.2 Agent Skill Delivery Mechanism

**Decision**: Absorb GSD's single-source multi-target transpilation model. Define skills in a canonical Python-based format, emit per-runtime formats via SkillEmitter Protocol classes.

**Rationale**:

GSD demonstrates that a single command definition can be transpiled into 14+ runtime formats at install time (T02 §2.2). The key innovations are: (a) a canonical format with YAML frontmatter + XML body, (b) per-runtime converter functions handling tool names, paths, frontmatter format, and adapter headers, (c) a two-layer design where compact commands reference expanded workflow files.

NineS absorbs:
- **Single-source multi-target transpilation** (T02 Pattern 1): SkillEmitter Protocol with per-runtime implementations
- **Adapter header injection** (T02 Pattern 2): Preambles normalizing skill invocation on runtimes without native slash-command support
- **Tool name mapping tables** (T02 Pattern 3): Canonical → runtime tool dictionaries with `None` for unsupported tools
- **Config-driven defaults** (T02 Pattern 4): "Absent = enabled" with dataclass defaults and deep merge
- **Phase-gated tool scoping** (T02 Pattern 5): Restrict tool access per pipeline stage
- **File-backed artifact DAG** (T02 Pattern 6): Phase artifacts with declared reads/writes
- **Advisory hooks** (T02 Pattern 7): Warn-but-never-block hook model

**Alternatives considered**:
- *Runtime-specific skill authoring*: Rejected — T02 §2 shows GSD maintains 14+ runtime formats from a single source; per-runtime authoring would be unmaintainable.
- *Server-based skill delivery (API)*: Rejected — GSD's file-based approach works offline and across all runtimes without a shared server (T02 §10 Pattern 6).
- *JavaScript/TypeScript implementation*: Rejected — NineS's core is Python; maintaining a separate TS module for skill emission adds build complexity. Python can generate markdown/YAML/TOML as effectively.

### 3.3 Information Collection Pipeline

**Decision**: Use GitHub GraphQL API as primary data source with REST fallback, arXiv API via the `arxiv` Python library, and RSS feed aggregation. Implement token-bucket rate limiting with response-header adaptation.

**Rationale**:

T04 §1 provides concrete API patterns with code examples. GitHub's GraphQL API (T04 §1.2) is preferred for multi-field queries (single request retrieves stars, forks, commits, releases, topics), reducing round trips and staying within the 5,000 points/hour rate limit. REST API (T04 §1.1) serves as fallback for simple lookups. arXiv's Atom API (T04 §1.3) with the `arxiv` Python library handles paper search with built-in pagination and retry. RSS feeds (T04 §1.4) track blog posts, project announcements, and release changelogs.

Rate limiting (T04 §1.5) uses a thread-safe token-bucket algorithm with per-source limiters calibrated to documented limits: 30 req/min for GitHub search, 5,000 req/hr for GitHub core, 1 req/3s for arXiv. Adaptive back-off reads `x-ratelimit-remaining` and `x-ratelimit-reset` headers for dynamic adjustment.

**Alternatives considered**:
- *GitHub REST only*: Rejected — GraphQL reduces round trips from ~5 calls to 1 for repository deep fetch (T04 §1.2).
- *Web scraping*: Rejected — fragile, violates ToS, and unnecessary given available APIs.
- *Third-party aggregators (e.g., Libraries.io)*: Rejected for MVP — adds external dependency for data available directly from source APIs.

### 3.4 Knowledge Analysis Engine

**Decision**: Use Python's built-in `ast` module for code analysis, heuristic-based architecture pattern detection, and three decomposition strategies (functional, concern-based, layer-based).

**Rationale**:

T04 §2 demonstrates that Python's `ast` module provides complete code analysis with zero external dependencies. The `CodeExtractor` visitor pattern (T04 §2.1) extracts functions, classes, imports, and computes cyclomatic complexity. The dependency graph builder (T04 §2.1) maps intra-project imports into an adjacency list from which coupling metrics (afferent/efferent coupling, instability) are computed.

Architecture pattern recognition (T04 §2.3) uses multi-signal heuristics with confidence scoring — detecting MVC, hexagonal, layered, microservices, and plugin/extension patterns from directory structure and Protocol usage. This approach avoids false positives from single-indicator detection.

Three decomposition strategies (T04 §2.4) serve different analysis needs: functional decomposition for per-function/class knowledge units, concern-based decomposition for cross-cutting grouping (error handling, logging, validation), and layer-based decomposition for architectural layer assignment.

**Alternatives considered**:
- *tree-sitter for multi-language AST*: Deferred to post-MVP — NineS initially targets Python codebases. tree-sitter would be the extension path for multi-language support.
- *LLM-based code understanding*: Rejected as primary — LLM analysis is non-deterministic and expensive. AST analysis provides deterministic, fast, cost-free structural understanding. LLM analysis can augment AST results for semantic understanding in future iterations.
- *Static analysis frameworks (Semgrep, CodeQL)*: Rejected for MVP — heavyweight dependencies for a subset of the needed functionality. AST provides the 80% case; specialized tools can be integrated later.

### 3.5 Self-Iteration Mechanism

**Decision**: Implement a MAPIM (Measure → Analyze → Plan → Improve → Measure) feedback loop with composite convergence detection using four statistical methods under majority vote.

**Rationale**:

T04 §3 provides the full self-improvement architecture. The MAPIM loop (T04 §3.1) uses typed intermediate artifacts: `MeasurementSnapshot` → `GapAnalysis` → `ImprovementPlan` → `ImprovementAction`. Each artifact is stored in SQLite for historical tracking and version-over-version comparison (T04 §3.5).

The external frameworks survey (T03 §Gaps) identifies self-improvement evaluation as a gap that no existing benchmark fills. NineS is uniquely positioned to address this with its self-iteration vertex.

Convergence detection (T04 §3.4) combines four methods via majority vote: sliding window variance, relative improvement rate, Mann-Kendall trend test, and CUSUM change detection. This composite approach is robust against any single method's blind spots — Mann-Kendall detects trend absence, CUSUM detects level shifts, variance measures stability, and relative improvement measures diminishing returns.

Auto-curriculum generation (T04 §3.3) enables NineS to generate progressively harder evaluation tasks as mastery is demonstrated at each difficulty level, using the 5-tier difficulty scale.

EvoBench's optimization lifecycle state machine (T01 Pattern 10) — Proposed → Approved → Applied → Validated/Rejected/RolledBack — maps directly to tracking improvement action status.

**Alternatives considered**:
- *Single convergence method*: Rejected — T04 §3.4 shows each method has blind spots (e.g., Mann-Kendall misses cyclic oscillation, variance misses slow drift). Composite with majority vote is more robust.
- *No convergence detection (fixed iterations)*: Rejected — wastes compute on converged metrics and misses divergence. Adaptive termination is essential for efficiency.
- *LLM-driven improvement planning*: Deferred — the MAPIM loop works with rule-based gap analysis initially. LLM-driven planning can be added as a strategy option.

### 3.6 Sandbox Isolation

**Decision**: Implement a 3-layer sandbox (venv + subprocess + tempfile) for MVP with Docker as a Tier 2 extension. Include pollution detection and seed control for deterministic execution.

**Rationale**:

T04 §4 provides complete implementation patterns. The 3-layer approach combines: (1) `venv` for Python environment isolation (T04 §4.1), (2) `subprocess` for process isolation with resource limits via `resource.setrlimit` (T04 §4.2), and (3) `tempfile` for filesystem isolation with automatic cleanup (T04 §4.3).

The external frameworks survey (T03 §Cross-Cutting Analysis Trend 3) identifies five sandbox tiers: L0 (subprocess), L1 (venv + tmpdir), L2 (Docker), L3 (Docker + services), L4 (VMs). NineS's 3-layer approach corresponds to L1, which is appropriate for MVP. HumanEval (T03 §6) validates that subprocess execution is sufficient for function-level evaluation, while SWE-Bench and Claw-Eval (T03 §1-2) demonstrate Docker as the extension path.

Seed control (T04 §4.4) — `PYTHONHASHSEED`, `NINES_SEED`, and per-framework seed initialization — enables deterministic execution critical for reproducible evaluation. EvoBench's deterministic simulation pattern (T01 Pattern 11) reinforces this requirement.

Pollution detection (T04 §4.5) uses before/after snapshot diffing of environment variables, watched files, directory listings, and `sys.path` to verify sandbox containment. Multi-round stability testing (T04 §4.6) with adaptive SPRT validates result determinism.

**Alternatives considered**:
- *Docker-first sandbox*: Rejected for MVP — Docker adds infrastructure dependency (daemon must be running), increases setup friction, and is unnecessary for Python-focused evaluation. Docker is the planned Tier 2 extension for repository-level evaluation.
- *nsjail/bubblewrap*: Rejected — Linux-only, complex configuration, and overkill for NineS's threat model (self-evaluation, not untrusted code execution).
- *No sandbox (direct execution)*: Rejected — T04 §4.5 demonstrates real pollution risks from uncontained execution. Even self-generated evaluation code can modify the host environment.

---

## 4. Risk Register

| ID | Risk | Severity | Likelihood | Impact | Mitigation |
|----|------|----------|-----------|--------|------------|
| **R01** | **API Rate Limiting Disrupts Collection** — GitHub's 30 req/min search limit or arXiv's 1 req/3s limit blocks NineS's information collection pipeline during intensive scan operations | Medium | High | Delayed data collection, stale information | Token-bucket rate limiter with per-source calibration (T04 §1.5). Adaptive back-off reading `x-ratelimit-remaining` headers. Implement local caching with TTL to avoid redundant API calls. Use GraphQL to reduce request count per operation (T04 §1.2). Schedule bulk scans during off-peak hours. |
| **R02** | **Sandbox Escape / Host Pollution** — Evaluation code modifies host environment (sys.path, installed packages, environment variables) despite sandbox isolation | High | Medium | Corrupted host environment, non-reproducible results, potential security exposure | 3-layer sandbox: venv + subprocess + tempfile (T04 §4). Before/after pollution detection with snapshot diffing (T04 §4.5). Process-level resource limits via `resource.setrlimit` (T04 §4.2). `PYTHONDONTWRITEBYTECODE=1` prevents `.pyc` leakage. Strict `tempfile` cleanup in `finally` blocks. Tier 2 Docker isolation for high-risk evaluations. |
| **R03** | **Evaluation Non-Determinism** — Same evaluation task produces different scores across runs due to floating-point variance, hash randomization, or LLM non-determinism, undermining reliability metrics | High | High | Unreliable Pass^k/Pass³ scores, false convergence/regression signals | Seed control across all sources of randomness: `PYTHONHASHSEED`, numpy, torch (T04 §4.4). Output fingerprinting for stability verification (T04 §4.6). Adaptive SPRT-based stability testing before reporting results. Statistical tolerance bands for metric comparison. Default to programmatic scoring over LLM-as-judge. |
| **R04** | **Scope Creep in Self-Iteration** — The MAPIM feedback loop generates unbounded improvement plans, causing NineS to attempt too many changes per iteration or to iterate indefinitely | Medium | High | Wasted compute, unstable releases, feature sprawl | Composite convergence detection with 4 statistical methods (T04 §3.4) terminates iterations when improvement plateaus. Maximum iteration cap (configurable, default 10). Per-iteration action budget (max 3 improvement actions). Quality gates between phases: each action must pass validation before proceeding (T02 Pattern 9). EvoBench's optimization lifecycle state machine (T01 Pattern 10) tracks action status. |
| **R05** | **External Benchmark API Drift** — SWE-Bench, arXiv, or GitHub change their API schemas, breaking NineS's information collection or benchmark integration | Medium | Medium | Broken data pipeline, stale evaluations | Abstract external APIs behind adapter interfaces (Protocol classes). Pin API versions where possible (`X-GitHub-Api-Version` header, T04 §1.1). Automated integration tests that validate API response schemas. RSS feed monitoring for API changelog entries. Graceful degradation: skip failed sources and report partial results. |
| **R06** | **Combinatorial Explosion in Matrix Evaluation** — Large axis specifications generate millions of cells (models × tools × workflows × tasks × trials), exceeding compute/cost budgets | High | Medium | Runaway cost, evaluation timeout, OOM | EvoBench's matrix constraint system (T01 §2.4): `max_cells` cap, exclusion rules, sampling strategies (LatinSquare, Pairwise, Random). Cost budget guard with real-time tracking (T01 Pattern 7). `BudgetExceeded` error with graceful early termination. Adaptive IRT-based sampling to focus on informative cells. |
| **R07** | **Skill Transpilation Fidelity** — Per-runtime skill emission produces subtly broken skills (wrong tool names, missing adapter headers, incorrect path transformations) that fail silently on target runtimes | Medium | Medium | Skills appear installed but malfunction, damaging user trust | GSD's approach: comprehensive tool name mapping tables with explicit `None` for unsupported tools (T02 §3.3). Per-runtime integration test suite that validates emitted skills against expected output. Adapter header injection tests (T02 Pattern 2). Roundtrip validation: emit → parse → compare. Start with 2-3 runtimes (Cursor, Claude Code) and expand incrementally. |
| **R08** | **SQLite Concurrency Under Parallel Evaluation** — Multiple parallel evaluation workers writing results to SQLite simultaneously cause lock contention or WAL corruption | Medium | Low | Dropped results, corrupted metrics database | SQLite WAL mode allows concurrent readers with single writer. Evaluation workers collect results in-memory, flush to SQLite in a single batch per evaluation run. For high-parallelism scenarios, use result queue (Python `queue.Queue`) with dedicated writer thread. Connection pooling with `check_same_thread=False`. |

---

## 5. NineS Differentiation

### 5.1 Positioning Statement

NineS occupies a unique position at the intersection of three capabilities that no existing tool combines: **evaluation** (like EvoBench/SWE-Bench), **skill delivery** (like GSD), and **self-improvement** (novel). While each existing tool addresses one dimension, NineS is the first system designed to close the feedback loop between evaluating agent capabilities, delivering improved skills, and measuring the impact of those improvements iteratively.

### 5.2 Differentiation Matrix

| Capability | NineS | EvoBench | GSD | SWE-Bench | Claw-Eval | Exgentic |
|------------|-------|----------|-----|-----------|-----------|----------|
| **Multi-dimensional evaluation** | Yes — absorbs EvoBench 4-dimension model + external metrics | Yes — 4 dimensions, 32 metrics | No | Single dimension (code correctness) | 3 dimensions (completion, robustness, safety) | Aggregates others |
| **Multi-runtime skill delivery** | Yes — absorbs GSD single-source transpilation | No | Yes — 14+ runtimes | No | No | No |
| **Self-improvement loop** | Yes — MAPIM with convergence detection | Planned (optimizer crate empty) | No | No | No | No |
| **Knowledge decomposition** | Yes — AST + architecture detection + 3 strategies | No | No | No | No | No |
| **Information tracking** | Yes — GitHub + arXiv + RSS monitoring | No | No | No | No | No |
| **Reliability metrics (Pass^k)** | Yes — pass@k + pass^k + Pass³ + consistency | Yes — pass@k + pass^k + consistency | No | Pass@1 only | Pass³ | Inherited |
| **Lightweight operation** | Yes — venv + subprocess, no Docker required | Requires Rust toolchain | Node.js installer | Docker required | Docker required | Varies |
| **Auto-curriculum generation** | Yes — progressive difficulty from mastery data | No | No | Fixed task set | Fixed task set | No |

### 5.3 Gaps NineS Fills

The external frameworks survey (T03 §Gaps) identifies five gaps in the current landscape:

1. **Self-improvement evaluation**: No benchmark tests an agent's ability to iteratively improve itself. NineS's MAPIM loop (T04 §3.1) with convergence detection (T04 §3.4) directly addresses this, enabling measurement of how well agents improve through feedback.

2. **Knowledge decomposition evaluation**: No benchmark evaluates structured knowledge extraction and abstraction. NineS's analysis engine (T04 §2) measures decomposition granularity, completeness, and abstraction accuracy.

3. **Information tracking evaluation**: No benchmark tests the ability to track and synthesize evolving information sources. NineS's collection pipeline (T04 §1) evaluates change detection accuracy, tracking timeliness, and synthesis quality.

4. **Cross-capability synergy measurement**: Current benchmarks test capabilities in isolation. NineS's three vertices (evaluation, skill delivery, knowledge analysis) interact — improved evaluation capability should lead to better skill design, which should produce higher evaluation scores, and NineS can quantify this synergy.

5. **Convergence and stability analysis**: While TAU-Bench's Pass^k implies stability, no benchmark explicitly measures convergence behavior. NineS tracks scores across N iterations, detects oscillation vs. monotonic improvement, and defines mathematical convergence criteria (T04 §3.4).

### 5.4 What NineS Does NOT Compete With

NineS does not aim to replace:
- **SWE-Bench/Claw-Eval** as gold-standard external benchmarks — NineS can wrap and run these benchmarks via its TaskLoader protocol
- **GSD** as a workflow orchestration tool — NineS absorbs GSD's skill delivery patterns but does not replicate the discuss → plan → execute → verify workflow
- **Docker-based heavy evaluation platforms** — NineS targets lightweight local operation; Docker is an extension, not the default

---

## 6. Open Questions

### 6.1 For Architecture Design (S02)

| # | Question | Context | Urgency |
|---|----------|---------|---------|
| **Q1** | How should NineS's Protocol interfaces handle backward compatibility as the pipeline evolves? | EvoBench uses Rust traits with `Custom(serde_json::Value)` escape hatches (T01 Pattern 1). Python Protocols don't enforce implementation. Should NineS use ABCs with version-tagged interfaces or Protocols with runtime validation? | High — affects all module boundaries |
| **Q2** | What is the concrete SQLite schema for evaluation history? | T04 §3.5 defines `MeasurementSnapshot` and `VersionComparison` data models but not the storage schema. Need to map EvalResult, EvalScore, MetricScore, and ReliabilityMetrics to tables. | High — blocks implementation |
| **Q3** | Should the SkillEmitter produce files on disk or return in-memory strings? | GSD writes files at install time (T02 §3.1). NineS may need both: files for installation, strings for preview/testing. Define the output interface. | Medium |
| **Q4** | How should multi-language code analysis be handled beyond Python? | T04 §2.1 covers Python `ast` only. EvoBench evaluates Rust codebases. tree-sitter supports 100+ languages. Define the abstraction layer and when to introduce it. | Low for MVP, high for post-MVP |
| **Q5** | What is the maximum matrix size NineS should support before requiring sampling? | EvoBench's Phase 1 matrix is 30 cells × 22 tasks × 3 trials = 1,980 evaluations (T01 §9.2). What is NineS's equivalent? Need to define default `max_cells` and sampling trigger. | Medium |

### 6.2 For Implementation (S03)

| # | Question | Context | Urgency |
|---|----------|---------|---------|
| **Q6** | What is the minimum viable set of evaluation metrics for MVP? | EvoBench defines 32 metrics across 4 dimensions (T01 §2.3). External benchmarks add more. Which subset does NineS need for launch? | High — scopes MVP work |
| **Q7** | How should NineS handle GitHub API authentication in CI/testing? | T04 §1.6 recommends fine-grained PAT. But CI environments need secrets management, and tests should work without real API access. Define mock strategy. | Medium |
| **Q8** | Should NineS bundle a web dashboard for evaluation results? | EvoBench has an ECharts dashboard (T01 §8). The external frameworks survey shows leaderboards (SWE-Bench, VAKRA) are important for adoption. But a dashboard is significant scope. | Low for MVP |
| **Q9** | How should the convergence threshold be tuned per-project? | T04 §3.4's composite convergence uses hardcoded thresholds (variance < 0.001, improvement < 0.5%). These may need per-project calibration. Define auto-tuning or config approach. | Medium |
| **Q10** | What is the Docker extension path when L1 sandbox is insufficient? | T03 §Cross-Cutting Analysis Trend 3 shows L2 (Docker container) as the next step. Define the interface contract so Tier 2 sandbox is a drop-in replacement for Tier 1. | Low for MVP |

---

*Synthesized from T01 (EvoBench Analysis), T02 (GSD Analysis), T03 (External Frameworks Survey), T04 (Domain Knowledge Collection)*
*Last modified: 2026-04-11*
