# Changelog

All notable changes to NineS are documented here. This project follows [Semantic Versioning](https://semver.org/).

---

## v3.0.0 — 2026-04-14

**Theme:** Knowledge Graph Analysis Engine — Integrates [Understand-Anything](https://github.com/Lum1104/Understand-Anything) repo decomposition and analysis capabilities into a complete analyze → decompose → verify → summarize pipeline.

> Breaking changes: New `graph` decomposition strategy, self-eval expanded to 24 dimensions, analysis pipeline supports multi-language scanning and knowledge graph construction.

### Added
- **Multi-language project scanner** (`scanner.py`) — Discovers 30+ programming languages, detects file categories (code/config/docs/infra/data/script/markup), identifies frameworks from manifests
- **Cross-language import graph builder** (`import_graph.py`) — AST-based (Python) and regex-based (JS/TS/Go/Rust) project-internal dependency graph construction
- **Knowledge graph data models** (`graph_models.py`) — `GraphNode`, `GraphEdge`, `ArchitectureLayer`, `KnowledgeGraph`, `VerificationResult`, `AnalysisSummary` with typed constants and full serialization
- **Graph decomposition strategy** (`graph_decomposer.py`) — New `--strategy graph` builds a complete knowledge graph with typed nodes, edges, and architecture layers
- **Graph verifier** (`graph_verifier.py`) — 7 verification checks: referential integrity, duplicate edges, orphan nodes, layer coverage, node/edge type validity, self-loops
- **Analysis summarizer** (`summarizer.py`) — Produces structured summaries with fan-in/fan-out rankings, entry point detection, and agent impact text
- **4 new self-eval dimensions** (D21-D24): graph decomposition coverage, verification pass rate, layer assignment quality, summary completeness
- **Pipeline graph strategy integration** — `nines analyze --strategy graph` auto-executes: scan → import graph → knowledge graph → verify → summarize
- **CLI graph output** — Text report includes knowledge graph statistics (scanned files, languages, frameworks, import edges, graph nodes/edges/layers, verification results)
- 67 new tests (total: 1189)

### Design Decisions
- **Deterministic-first, LLM-assist-second** — Following Understand-Anything's two-phase design (scripts first → LLM enrichment), all core logic is AST/regex/path-heuristic based with no LLM dependency
- **Typed graph contract** — 11 node types, 10 edge types, 7 file categories constrained by `frozenset` constants; verifier enforces schema compliance
- **Path + fan-in hybrid layer assignment** — Combines path-pattern matching with fan-in ranking promotion; high-dependency nodes auto-promoted to core layer
- **Everything serves Agent capability verification** — D21-D24 directly measure graph decomposition and verification quality, driving iterative improvement

### Improved
- **Self-eval expanded from 20 to 24 dimensions** — D21-D24 cover graph decomposition, verification, layer assignment, summary
- **Pipeline constructor expanded** — `AnalysisPipeline.__init__` accepts `scanner`, `graph_decomposer`, `graph_verifier`, `summarizer` injection
- **`analyzer/__init__.py` public API expanded** — Exports all new module public classes
- **Full test suite**: 1189 tests passing, 0 lint errors

---

## v2.1.0 — 2026-04-14

**Theme:** Self-update iteration — analysis quality improvements, strategy routing, reference system, driven by DevolaFlow self-update workflow analyzing [Understand-Anything](https://github.com/Lum1104/Understand-Anything).

### Added
- **Decomposition strategy routing** — `--strategy concern|layer|functional` now correctly dispatches to the corresponding `Decomposer` method (was hardcoded to `functional`)
- **Strategy and depth in metrics** — `strategy` and `depth` recorded in analysis result metrics for traceability
- **Reference system** — 6 DevolaFlow-style reference documents in `references/` with YAML frontmatter (analysis-pipeline, agent-impact-analysis, key-point-extraction, evaluation-framework, iteration-protocol, index)
- **SKILL.md Reference Navigation Guide** — quick-reference table for selective context loading
- **Semantic key-point deduplication** — second-pass dedup merging points with >60% word overlap within same category
- 27 new tests (1093 total)

### Fixed
- **Finding ID collision** — IDs now include a deterministic file-path hash prefix (`CC-{hash}-{idx}`), eliminating duplicates across multi-file analysis (was: 10 duplicates on Understand-Anything repo)
- **Beneficial mechanism impact** — `behavioral_instruction`, `safety`, and `persistence` mechanisms correctly classified as `"positive"` impact (was: `"negative"` due to token-count-only heuristic)
- **Impact magnitude saturation** — switched from linear to logarithmic scale (`log1p`), producing differentiated magnitudes (was: all 1.0 for >5K tokens; now: 0.817–0.862 range)
- **arxiv collector** — `_DEFAULT_BASE_URL` upgraded from `http://` to `https://`

### Improved
- **Analysis of Understand-Anything**: 0 duplicate finding IDs, 5 differentiated mechanism magnitudes, 3 correctly-positive beneficial mechanisms
- **Full test suite**: 1093 tests passing, 0 lint errors

---

## v2.0.0 — 2026-04-13

**Theme:** Agent-facing repository analysis realignment — NineS is now a purpose-built tool for analyzing how repositories improve AI Agent effectiveness.

> Breaking: analysis pipeline defaults changed, self-eval expanded to 20 dimensions, benchmark executor replaced.

### Added
- **AgentAnalysisQualityEvaluator (D20)** — measures NineS's ability to detect artifacts, mechanisms, economics, findings, and key points on real repos
- **SourceFreshnessEvaluator (D07)** — measures data staleness within configurable window (default 30 days)
- **ChangeDetectionEvaluator (D08)** — verifies DataStore update detection capability
- **Real benchmark executor** — dimension-aware comparison scoring replaces passthrough executor (compression, context, behavioral, semantic, cross-platform, engineering)
- **`ingest_all()` method** in AnalysisPipeline — discovers non-Python agent artifacts (.yaml, .md, .json, .toml, .cfg, .ini, .rules)
- **`--tasks-path` option** for `nines benchmark` — load custom TOML task definitions
- **`--project-root`/`--src-dir`/`--test-dir`** options for `nines iterate` with live evaluators
- **Configurable `cov_package`** and **coverage file parsing** (coverage.xml/json) in LiveCodeCoverageEvaluator
- **pytest --collect-only** for accurate test counting with AST-walk fallback
- 13 new tests (1069 total)

### Changed
- **[BREAKING] `nines analyze` defaults to agent-impact analysis** — `--agent-impact/--no-agent-impact` flag pair, default enabled. Use `--no-agent-impact` to disable.
- **[BREAKING] `nines analyze` defaults to key-point extraction** — `--keypoints/--no-keypoints` flag pair, default enabled
- **[BREAKING] Benchmark executor** produces differentiated scores (mean 0.4) instead of passthrough 1.0
- **Self-eval expanded from 17 to 20 dimensions** (D07, D08, D20)
- **Context Economics enriched** with mechanism-derived tokens, expanded artifact patterns (pyproject.toml, copilot, aider), minimum fallback estimate
- **KeyPointExtractor** filters generic metric noise — 23→10 key points, engineering observations capped at 5 (critical/error only)
- **`nines iterate`** registers all 20 capability dimensions (was 0) plus 5 hygiene dimensions
- **README** rewritten: Agent-facing repo analysis mission, all CLI examples fixed
- **SKILL.md** rewritten: core workflow description (analyze→benchmark→self-eval→iterate)
- D07/D08 numbering gap filled in dimension labels

### Improved
- **Self-eval overall: 0.9727** — 20 dimensions, D07=50% (real freshness signal), D20=100%
- **Benchmark mean: 0.4** — real differentiation across compression/context/behavioral dimensions
- **Context Economics**: overhead=3575 tokens, savings=15%, breakeven=7 interactions (was empty `{}`)
- **Agent-impact key points**: 9/10 are agent-relevant (was 9/23)

---

## v1.1.0 — 2026-04-13

**Theme:** External project support and DevolaFlow integration feedback fixes.

> Based on integration testing feedback from DevolaFlow v4.3.1, this release fixes 4 core issues when NineS evaluates external projects, transforming NineS from "can only evaluate itself" to a general-purpose project quality scanner.

### Added
- **Configurable coverage package** in `LiveCodeCoverageEvaluator` — new `cov_package` parameter replaces hardcoded `--cov=nines`, enabling correct coverage measurement for external projects (e.g. DevolaFlow)
- **Coverage file parsing** — new `coverage_file` parameter supports reading pre-existing `coverage.xml` (Cobertura format) and `coverage.json` files without re-running pytest
- **`LiveTestCountEvaluator` prefers pytest collection** — uses `pytest --collect-only -q` for accurate counting (handles parameterized tests, class methods, etc.), with AST-walk fallback
- **`nines iterate` project context flags** — new `--project-root`, `--src-dir`, `--test-dir` options with auto-detection of source and test directories
- **`nines iterate` live evaluators** — uses 5 live evaluators (coverage, test count, modules, docstring coverage, lint) when `--project-root` is specified, replacing fixed-zero stub evaluators
- **`nines benchmark --tasks-path`** — new custom TOML task directory option, skips auto-generated generic tasks and loads user-defined project-specific benchmark tasks directly
- 24 new tests (self_eval: 6, iterate_cmd: 14, benchmark_cmd: 4), bringing total to 1052

### Changed
- `LiveCodeCoverageEvaluator` metadata includes `source` field (`"file"` or `"pytest"`) indicating data origin
- `LiveTestCountEvaluator` metadata includes `method` field (`"pytest-collect"` or `"ast-walk"`) indicating counting method
- `nines iterate` warns when no `--project-root` is given and uses non-zero stub values (avoids immediate convergence at 0.0)
- Fixed potential `UnboundLocalError` on `conv_result` in iterate command

### Improved
- **Self-eval score: 0.9928** — capability dimensions 17/17 at 100%, hygiene 97.6% (coverage 90%, tests 1052, modules 65, docstrings 100%, lint 98%)
- NineS now usable as a general-purpose project quality scanner, no longer limited to evaluating itself
- In DevolaFlow integration scenario, `nines iterate --project-root .` correctly produces a 0.976 composite score

---

## v1.0.0 — 2026-04-13

**Theme:** Multi-runtime skill integration, 19-dimension capability evaluation, and production readiness.

### Added
- **Codex adapter** — install NineS as a Codex skill at `.codex/skills/nines/` with SKILL.md + per-command workflows
- **GitHub Copilot adapter** — install NineS as Copilot instructions at `.github/copilot-instructions.md`
- **One-click install script** (`scripts/install.sh`) — `curl | bash` style installer with Python detection, uv/pip fallback, and automatic skill file generation
- **`--uninstall` CLI flag** for `nines install` — clean removal of skill files from any target runtime
- **DevolaFlow integration feedback** — proposed NineS as quality gate scorer, research tool, and advisor plugin for DevolaFlow v4.2.0
- 12 new tests for Codex adapter, Copilot adapter, installer integration, and uninstall flow
- **19-dimension capability evaluation framework** — all design dimensions (D01–D19) now have live evaluators
- **V1 Evaluation evaluators** (D01 ScoringAccuracy, D03 Reliability, D05 ScorerAgreement) with 20-task golden test set
- **V2 Collection evaluators** (D06 SourceCoverage, D09 DataCompleteness, D10 CollectionThroughput)
- **V3 Analysis evaluators** (D11–D15) measuring decomposition, abstraction, code review, index recall, structure recognition
- **System evaluators** (D16 PipelineLatency, D17 SandboxIsolation, D18 ConvergenceRate, D19 CrossVertexSynergy)
- Golden test set at `data/golden_test_set/` with 20 calibrated TOML tasks
- Self-eval CLI restructured: 70% capability / 30% hygiene weighting, grouped output by V1/V2/V3/System
- `--capability-only` and `--golden-dir` CLI options for focused evaluation (total: 1005 tests)

### Changed
- `nines install --target` now accepts 5 targets: `cursor`, `claude`, `codex`, `copilot`, `all`
- Installer `ADAPTERS` registry expanded from 2 to 4 runtimes
- Skill `__init__.py` public API includes `CopilotAdapter` alongside existing adapters

### Improved
- **Self-eval score: 0.9940** — capability dimensions 17/17 at 100%, hygiene 98%
  - V1 Evaluation: D01–D05 all 100% (scoring accuracy, coverage, reliability, report quality, scorer agreement)
  - V2 Collection: D06/D09/D10 all 100% (source coverage, data completeness, throughput)
  - V3 Analysis: D11–D15 all 100% (decomposition, abstraction, code review, index recall, structure recognition)
  - System: D16–D19 all 100% (pipeline latency, sandbox isolation, convergence, cross-vertex synergy)
- Documentation updated for all 4 runtime targets (EN + ZH)
- Agent skill setup guide, quick start, CLI reference, installation guide, and design spec all reflect v1.0.0-pre capabilities
- README updated with one-click install and 4-runtime support

---

## v0.6.0 — 2026-04-13

**Theme:** DevolaFlow analysis showcase and EvoBench evaluation integration.

### Added
- DevolaFlow repository deep analysis showcase — 15 key points, 30 benchmark tasks, multi-round evaluation with EvoBench dimension mapping
- EvoBench integration insights section documenting 32 evaluation dimensions (T1–T8, M1–M8, W1–W8, TT1–TT8) alignment with agent-facing analysis
- NineS capabilities assessment and v0.6.0 improvement roadmap in showcase reports
- Chinese translation for DevolaFlow analysis showcase

### Changed
- Showcase index updated to feature DevolaFlow as second case study alongside Caveman
- Analysis methodology extended to meta-framework evaluation (orchestration rules, not just tools)

### Improved
- Documentation of NineS evaluation pipeline capabilities and identified gaps
- Cross-repository analysis patterns established (simple tool → meta-framework)

---

## v0.5.0 — 2026-04-12

**Theme:** Executable evaluation framework and self-driven improvement.

### Added
- Key point extraction module (`KeyPointExtractor`) — decomposes Agent impact reports into categorized, prioritized key points with validation approaches
- Benchmark generation module (`BenchmarkGenerator`) — generates `TaskDefinition` benchmark suites from key points with per-category task templates
- Multi-round evaluation runner (`MultiRoundRunner`) — sandboxed multi-round evaluation with convergence detection and reliability metrics (pass@k, consistency)
- Key point → conclusion mapping module (`MappingTableGenerator`) — maps key points to effectiveness conclusions with confidence scores and recommendations
- Five live self-evaluation evaluators: `LiveCodeCoverageEvaluator`, `LiveTestCountEvaluator`, `LiveModuleCountEvaluator`, `DocstringCoverageEvaluator`, `LintCleanlinessEvaluator`
- New CLI command `nines benchmark` — full analysis→benchmark→evaluate→mapping workflow
- CLI options `--agent-impact` and `--keypoints` for `nines analyze`
- CLI options `--project-root`, `--src-dir`, `--test-dir` for `nines self-eval`
- 18 new integration tests for benchmark workflow and enhanced analysis pipeline
- `BenchmarkSuite` with TOML directory export (`to_toml_dir()`)
- `MappingTable` with markdown and JSON export
- `MultiRoundReport` with per-task summary statistics

### Changed
- Caveman showcase completely rewritten to demonstrate v0.5.0 executable evaluation methodology — key points, benchmarks, multi-round results, mapping table, lessons learnt
- `AnalysisPipeline.run()` now accepts `agent_impact` and `keypoints` keyword arguments
- Self-evaluation CLI wires live evaluators instead of placeholder zeros
- Orchestrator `Pipeline` methods now wire real component calls (eval, analyze, benchmark)
- `nines analyze` CLI now supports `--depth` option

### Improved
- Self-evaluation produces real measurements from project introspection (coverage, test counts, docstrings, lint)
- Analysis pipeline integrates `AgentImpactAnalyzer` and `KeyPointExtractor` into the main flow
- 914+ tests with comprehensive coverage across all new modules

---

## v0.4.0 — 2026-04-12

**Theme:** Agent-oriented analysis and AI repository evaluation.

### Added
- Agent impact analysis module (`AgentImpactAnalyzer`) for evaluating how repositories influence AI Agent effectiveness
- New data models: `AgentMechanism`, `ContextEconomics`, `AgentImpactReport` with full serialization
- Research synthesis document on analyzing AI-oriented repositories
- Agent artifact detection covering 14+ patterns across 7 AI agent platforms
- Mechanism decomposition with 5 detection categories: behavioral instruction, context compression, safety, distribution, persistence
- Context economics estimation with token overhead, savings ratio, and break-even analysis
- 45 new tests for the Agent impact analyzer with 100% pass rate

### Changed
- Caveman showcase completely rewritten with Agent-oriented focus — mechanism decomposition, context economics, semantic preservation, behavioral impact analysis
- Showcase index updated to reflect Agent-oriented analysis capabilities
- Analysis module exports expanded with Agent impact types

### Improved
- V3 Analysis now supports dual-track mode: traditional code analysis + Agent impact analysis
- Documentation coverage for AI repository evaluation methodology

---

## v0.3.0 — 2026-04-12

**Theme:** Documentation completeness and international polish.

### Added
- Development plan documentation with MAPIM-aligned engineering methodology
- Caveman repository analysis showcase demonstrating V3 capabilities
- Sample task files for quick evaluation demos

### Fixed
- Chinese site i18n issues: language switcher, nav translations, and UI locale
- Deploy workflow updated with i18n plugin dependency

### Improved
- Navigation restructured to surface design documents, research reports, and internal references
- Emoji icon rendering for Material card grids on homepage

---

## v0.2.0 — 2026-04

**Theme:** Visual identity and internationalization.

### Added
- NieR: Automata custom theme (`nier.css`) — warm cream/parchment light mode, deep charcoal dark mode
- Full i18n support with `mkdocs-static-i18n` — English (default) and Chinese
- Chinese translations for all user-facing documentation pages
- Light/dark mode toggle with NieR-inspired color palettes
- HUD-style geometric accents, custom typography (JetBrains Mono, Noto Sans/SC)
- MkDocs Material theme with navigation tabs, search, code copy

### Changed
- Documentation site deployed to GitHub Pages via `deploy-pages.yml`
- Version macro system (`{{ nines_version }}`) for automatic version tracking

---

## v0.1.0 — 2026-03

**Theme:** MVP — Full implementation of three-vertex architecture.

### Added
- **V1 Evaluation & Benchmarking**
    - TOML-based task definitions with structured input/expected schemas
    - Multiple scorer types: Exact, Fuzzy, Rubric, Composite
    - `EvalRunner` with configurable execution pipeline
    - Matrix evaluation across N configurable axes
    - Statistical reliability metrics: pass@k, Pass^k, Pass³
    - Sandboxed execution with three-layer isolation (process + venv + tmpdir)
    - Pollution detection across 4 dimensions (env vars, files, dirs, sys.path)
    - Markdown and JSON report generation
- **V2 Information Collection**
    - GitHub REST and GraphQL source collectors
    - arXiv search and metadata collector
    - SQLite storage with FTS5 full-text search
    - Token-bucket rate limiting per source
    - Incremental collection with snapshot-based change detection
- **V3 Code Analysis**
    - AST-based code parsing and element extraction
    - Cyclomatic complexity calculation
    - Cross-file dependency graph construction
    - Multi-strategy decomposition (functional, concern, layer)
    - Knowledge unit indexing and search
    - Architectural pattern detection
- **Self-Iteration (MAPIM)**
    - 19 self-evaluation dimensions across 4 categories
    - Gap detection with severity classification
    - Improvement planning with ≤3 actions per iteration
    - 4-method convergence detection (sliding variance, relative improvement, Mann-Kendall, CUSUM)
    - Composite scoring with configurable weights
- **Agent Skill Support**
    - `nines install` command for Cursor and Claude Code integration
    - Skill templates for both platforms
- **CLI**
    - `nines eval` — Run evaluations on TOML task files
    - `nines collect` — Collect from GitHub and arXiv
    - `nines analyze` — Analyze codebases
    - `nines self-eval` — Run self-evaluation
    - `nines iterate` — Run MAPIM self-improvement loop
- **Documentation**
    - MkDocs site with user guide, architecture docs, API reference
    - Quick start guide with step-by-step examples
    - Comprehensive design philosophy page
    - 19-dimension evaluation criteria reference
    - Development plan and roadmap
    - Contributing guide with module ownership matrix
- **Infrastructure**
    - Python 3.12+ with `uv` package management
    - GitHub Actions: version sync check, documentation deployment
    - Deterministic execution with master seed propagation
    - Protocol-based extensibility (PEP 544)
    - Structured logging with `structlog`
    - Progressive configuration depth (CLI → project → user → defaults)
