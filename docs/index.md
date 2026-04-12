# NineS

<!-- auto-updated: version from src/nines/__init__.py -->

**Multi-Vertex AI Agent Evaluation, Collection, Analysis & Self-Iteration**

![Version](https://img.shields.io/badge/version-{{ nines_version }}-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

NineS is a Python-based toolkit for benchmarking AI agent capabilities, discovering and tracking external information sources, analyzing codebases into structured knowledge, and running self-improvement loops via the MAPIM (Measure–Analyze–Plan–Improve–Measure) cycle.

---

## Three-Vertex Capability Model

NineS organizes its capabilities around three interconnected vertices that reinforce each other through cross-vertex data flows.

!!! abstract "V1 — Evaluation & Benchmarking"

    Run structured evaluations on AI agent outputs with multiple scoring strategies, matrix evaluation across N axes, and reliability metrics like pass@k and Pass³.

    **Key features:** TOML task definitions, Exact/Fuzzy/Rubric/Composite scorers, sandboxed execution, budget guards, Markdown & JSON reports.

!!! abstract "V2 — Information Collection & Tracking"

    Discover, fetch, and track external data sources relevant to AI agent research. Supports incremental collection with change detection.

    **Key features:** GitHub REST + GraphQL, arXiv search, SQLite storage with FTS5, rate-limited collection, snapshot-based change detection.

!!! abstract "V3 — Knowledge Analysis & Decomposition"

    Analyze codebases into structured knowledge units through AST parsing, architectural pattern detection, and multi-strategy decomposition.

    **Key features:** Cyclomatic complexity, cross-file dependency graphs, functional/concern/layer decomposition, knowledge indexing & search.

---

## Key Features

- **Agent Skill Support** — Install NineS as a skill into Cursor or Claude Code with `nines install`
- **Self-Iteration (MAPIM)** — Closed-loop self-improvement across 19 measurable dimensions
- **Sandboxed Evaluation** — Three-layer isolation (process + venv + tmpdir) with pollution detection
- **19 Evaluation Dimensions** — Spanning V1 scoring accuracy through V3 structure recognition to system-wide convergence rate
- **Extensible Scorer System** — Protocol-based scorers with registry and entry-point plugin discovery
- **Deterministic Execution** — Master seed propagation for reproducible evaluation results

---

## Quick Install

```bash
# Requires Python 3.12+ and uv
git clone https://github.com/YoRHa-Agents/NineS.git && cd NineS
uv sync
uv run nines --version
```

See the [Installation Guide](installation.md) for alternative methods.

---

## Get Started

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Get running in 5 minutes with your first evaluation, collection, and analysis.

    [:octicons-arrow-right-24: Quick Start](quick-start.md)

-   :material-book-open-variant:{ .lg .middle } **User Guide**

    ---

    In-depth guides for evaluation, collection, analysis, and self-iteration workflows.

    [:octicons-arrow-right-24: User Guide](user-guide/index.md)

-   :material-sitemap:{ .lg .middle } **Architecture**

    ---

    System design, module dependencies, data flow diagrams, and the three-vertex model.

    [:octicons-arrow-right-24: Architecture](architecture/overview.md)

-   :material-api:{ .lg .middle } **API Reference**

    ---

    Python API overview with key public classes, protocols, and configuration.

    [:octicons-arrow-right-24: API Reference](api-reference.md)

</div>
