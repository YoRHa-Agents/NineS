# NineS — Self-Iterating Agent Toolflow

Use when you need to evaluate agent capabilities, collect external information (GitHub repos, arXiv papers), analyze codebases into structured knowledge, run self-evaluation across 19 quality dimensions, or execute self-improvement iteration cycles.

## Prerequisites

- Python 3.12+
- NineS installed: `uv pip install .` or `pip install -e .` from the NineS repository root
- The `nines` CLI binary must be on `$PATH`

## Available Commands

| Command | When to Use | Example |
|---------|------------|---------|
| `nines eval` | Benchmark agent capabilities against task suites | `nines eval tasks/coding.toml --scorer composite` |
| `nines collect` | Search and collect data from GitHub, arXiv, RSS | `nines collect github "LLM evaluation" --limit 20` |
| `nines analyze` | Analyze a codebase into knowledge units | `nines analyze ./repo --depth deep --index` |
| `nines self-eval` | Run self-evaluation across all dimensions | `nines self-eval --compare --baseline v1` |
| `nines iterate` | Execute a MAPIM self-improvement cycle | `nines iterate --max-rounds 5` |
| `nines install` | Install NineS as an Agent Skill | `nines install --target cursor` |

## Workflow: Evaluation

Run evaluation benchmarks on agent capabilities. Supports multiple scorer types (exact, fuzzy, rubric, composite), sandboxed execution for isolation, and seed control for reproducibility.

```bash
nines eval <task-or-suite> [--scorer TYPE] [--format FORMAT] [--sandbox] [--seed N]
```

**Examples:**
- Evaluate a task file: `nines eval tasks/coding.toml`
- Evaluate with sandbox isolation: `nines eval tasks/coding.toml --sandbox --seed 42`
- Output JSON results: `nines eval tasks/coding.toml --format json -o results.json`

## Workflow: Information Collection

Search and collect information from configured sources. Supports incremental tracking, persistent storage, and multiple data sources.

```bash
nines collect <source> <query> [--incremental] [--store PATH] [--limit N]
```

**Examples:**
- Search GitHub: `nines collect github "AI agent evaluation" --limit 20`
- Search arXiv: `nines collect arxiv "self-improvement LLM" --limit 10`
- Incremental update: `nines collect github "AI agent" --incremental`

## Workflow: Knowledge Analysis

Analyze and decompose codebases into structured knowledge units. Supports AST analysis, complexity metrics, architecture pattern detection, and searchable knowledge indexing.

```bash
nines analyze <target> [--depth LEVEL] [--decompose] [--index] [--output FORMAT]
```

**Examples:**
- Deep analysis: `nines analyze ./target-repo --depth deep`
- Decompose and index: `nines analyze ./target-repo --decompose --index`
- Markdown report: `nines analyze ./target-repo --output markdown`

## Workflow: Self-Evaluation

Run self-evaluation across 19 dimensions spanning evaluation quality (V1), search effectiveness (V2), analysis accuracy (V3), and system-wide health. Compares against stored baselines.

```bash
nines self-eval [--dimensions DIM,...] [--baseline VERSION] [--compare] [--report]
```

**Examples:**
- Full evaluation: `nines self-eval`
- Specific dimensions: `nines self-eval --dimensions D01,D02,D03`
- Compare with baseline: `nines self-eval --baseline v1 --compare`

## Workflow: Self-Improvement Iteration

Execute the MAPIM (Measure-Analyze-Plan-Improve-Measure) cycle. Detects capability gaps, generates improvement plans, and tracks convergence across iterations.

```bash
nines iterate [--max-rounds N] [--convergence-threshold F] [--dry-run]
```

**Examples:**
- Run 5 rounds: `nines iterate --max-rounds 5`
- Dry run (plan only): `nines iterate --dry-run`

## Integration Notes

- All commands delegate to the `nines` CLI via the Shell tool
- Configuration: `nines.toml` (project root) or `~/.config/nines/config.toml` (global)
- Output formats: `text` (default), `json`, `markdown` via `--format`
- Use `--verbose` for detailed logging, `--quiet` for errors only
- Results are written to stdout by default; use `-o <path>` to write to a file
