# NineS

A multi-vertex evaluation, collection, analysis, and self-iteration system for AI agents.

NineS provides a unified CLI and library for benchmarking AI agent capabilities (V1), discovering and tracking external information sources (V2), analyzing codebases into structured knowledge (V3), and running self-improvement loops via the MAPIM (Measure-Analyze-Plan-Improve-Measure) cycle.

## Quick Start

### Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/YoRHa-Agents/NineS.git && cd NineS

# Option A: Install with uv (recommended)
uv sync
uv run nines --version

# Option B: Install with pip (editable mode)
pip install -e .
nines --version

# Option C: Direct pip install
uv pip install .
nines --version
```

### Agent Skill Installation

NineS can be installed as an Agent Skill into Cursor or Claude Code:

```bash
# Install as a Cursor skill (creates .cursor/skills/nines/)
nines install --target cursor

# Install as a Claude Code skill (creates .claude/commands/nines/)
nines install --target claude

# Install for all supported runtimes
nines install --target all

# Uninstall
nines install --target cursor --uninstall
```

### Usage Examples

#### Evaluate agent capabilities

```bash
# Run a single evaluation task file
nines eval tasks/coding.toml

# Run with a specific scorer and sandboxed execution
nines eval tasks/coding.toml --scorer composite --sandbox --seed 42

# Output results as JSON
nines eval tasks/coding.toml --format json -o results.json
```

#### Collect external information

```bash
# Search GitHub for repositories
nines collect github "AI agent evaluation" --limit 20

# Search arXiv for papers
nines collect arxiv "LLM self-improvement" --limit 10

# Incremental collection (only new items since last run)
nines collect github "AI agent evaluation" --incremental --store ./data/collections
```

#### Analyze a codebase

```bash
# Run deep analysis on a target repository
nines analyze ./target-repo --depth deep

# Decompose into knowledge units and build search index
nines analyze ./target-repo --decompose --index

# Output structured Markdown report
nines analyze ./target-repo --output markdown -o analysis_report.md
```

#### Self-evaluation

```bash
# Run full self-evaluation across all 19 dimensions
nines self-eval

# Evaluate specific dimensions and compare against a baseline
nines self-eval --dimensions D01,D02,D03 --baseline v1 --compare

# Generate a self-eval report
nines self-eval --report -o self_eval_report.md
```

#### Self-improvement iteration

```bash
# Run iterative self-improvement (MAPIM cycle)
nines iterate --max-rounds 5

# Set convergence threshold and dry-run mode
nines iterate --max-rounds 10 --convergence-threshold 0.001 --dry-run
```

## Module Architecture

NineS is organized around three capability vertices and supporting infrastructure:

```
┌─────────────────────────────────────────────────────┐
│                   CLI (cli/)                         │
│   eval │ collect │ analyze │ self-eval │ iterate     │
├────────┴─────────┴─────────┴──────────┴─────────────┤
│                Orchestrator (orchestrator/)          │
│        Workflow engine, pipeline composition         │
├─────────────┬──────────────┬────────────────────────┤
│  V1: Eval   │ V2: Collect  │    V3: Analyze         │
│  (eval/)    │ (collector/) │    (analyzer/)          │
│  Runner     │ GitHub       │    Pipeline             │
│  Scorers    │ arXiv        │    Code Reviewer        │
│  Reporters  │ Store        │    Structure Analyzer   │
│  Metrics    │ Tracker      │    Decomposer           │
│  Matrix     │ Scheduler    │    Indexer / Search     │
├─────────────┴──────────────┴────────────────────────┤
│            Self-Iteration (iteration/)              │
│  SelfEvalRunner │ Baseline │ GapDetector │ Planner  │
│  Convergence    │ History  │ Tracker                │
├─────────────────────────────────────────────────────┤
│  Core (core/)   │ Sandbox (sandbox/)  │ Skill       │
│  Protocols      │ Manager             │ (skill/)    │
│  Models         │ Runner              │ Manifest    │
│  Config         │ Isolation           │ Adapters    │
│  Events/Errors  │                     │ Installer   │
└─────────────────┴─────────────────────┴─────────────┘
```

| Module | Description |
|--------|-------------|
| `core/` | Foundation layer: protocols, models, errors, events, configuration |
| `eval/` | V1 — Task evaluation, scoring, reliability metrics, reporting |
| `collector/` | V2 — External data discovery, collection, tracking, change detection |
| `analyzer/` | V3 — Code analysis, structural decomposition, knowledge indexing |
| `iteration/` | Self-evaluation, gap detection, improvement planning, convergence |
| `orchestrator/` | Workflow execution, cross-vertex data flow, artifact passing |
| `sandbox/` | Process/venv/filesystem isolation for evaluation execution |
| `skill/` | Agent runtime adapter generation (Cursor, Claude Code) |
| `cli/` | User-facing Click command interface |

## Configuration

NineS uses TOML configuration with three priority levels (highest first):

1. **CLI flags** — Override everything (`--config`, `--verbose`, etc.)
2. **Project config** — `nines.toml` in the project root
3. **User config** — `~/.config/nines/config.toml`
4. **Built-in defaults** — `src/nines/core/defaults.toml`

## Self-Evaluation Dimensions

NineS tracks 19 self-evaluation dimensions across four categories:

| Category | Dimensions | Description |
|----------|------------|-------------|
| V1 Evaluation (D01–D05) | Scoring Accuracy, Coverage, Reliability, Report Quality, Scorer Agreement | Evaluation pipeline health |
| V2 Search (D06–D10) | Source Coverage, Freshness, Change Detection, Completeness, Throughput | Information collection quality |
| V3 Analysis (D11–D15) | Decomposition, Abstraction, Code Review, Index Recall, Structure Recognition | Knowledge analysis accuracy |
| System-wide (D16–D19) | Pipeline Latency, Sandbox Isolation, Convergence Rate, Cross-Vertex Synergy | Overall system health |

## Development

```bash
# Run tests
make test

# Lint and format
make lint
make format

# Type checking
make typecheck

# Test coverage report
make coverage

# Clean build artifacts
make clean
```

## Project Structure

```
NineS/
  pyproject.toml          # uv-managed, PEP 621 metadata
  Makefile                # Dev shortcuts: make test, make lint, make format
  .python-version         # 3.12
  src/nines/              # Main package (src layout)
    core/                 # Zero-dependency foundation
    eval/                 # Evaluation & benchmarking
    collector/            # Information search & tracking
    analyzer/             # Knowledge analysis & decomposition
    iteration/            # Self-evaluation & self-iteration
    orchestrator/         # Workflow engine
    sandbox/              # Isolation layer
    skill/                # Agent skill adapters
      templates/          # SKILL.md and command templates
    cli/                  # CLI entry point
      commands/           # Per-vertex CLI subcommands
  tests/                  # Unit tests
    integration/          # End-to-end integration tests
  docs/                   # Design, research, and roadmap documents
    design/               # Architecture and module design specs
    research/             # Reference analysis and domain knowledge
    roadmap/              # Iteration plans and growth evaluation
  reports/                # Baseline and performance reports
```

## License

MIT
