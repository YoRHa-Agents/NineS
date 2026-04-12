# Changelog

All notable changes to NineS are documented here. This project follows [Semantic Versioning](https://semver.org/).

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
