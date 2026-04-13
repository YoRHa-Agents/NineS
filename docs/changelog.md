# Changelog

All notable changes to NineS are documented here. This project follows [Semantic Versioning](https://semver.org/).

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
