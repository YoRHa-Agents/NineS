# CLI Reference

<!-- auto-updated: version from src/nines/__init__.py -->

Complete command reference for the `nines` CLI (version {{ nines_version }}).

---

## Global Options

All commands inherit these global options:

```
nines [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config PATH` | `-c` | Path to `nines.toml` config file | Auto-discover |
| `--verbose` | `-v` | Enable verbose/debug output | Off |
| `--quiet` | `-q` | Suppress non-error output | Off |
| `--output PATH` | `-o` | Write primary output to file | stdout |
| `--format FORMAT` | `-f` | Output format: `text`, `json`, `markdown` | `text` |
| `--no-color` | | Disable colored output | Off |
| `--version` | | Show version and exit | |
| `--help` | | Show help and exit | |

---

## `nines eval`

Run evaluation benchmarks on agent capabilities.

```
nines eval <TASK_OR_SUITE> [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_OR_SUITE` | Path to a `.toml` task file, directory of tasks, or glob pattern |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--scorer TYPE` | Scorer to use: `exact`, `fuzzy`, `rubric`, `composite` | `composite` |
| `--sandbox` | Enable sandboxed execution | From config |
| `--seed N` | Master seed for determinism | Random |
| `--format FORMAT` | Output format: `text`, `json`, `markdown` | `text` |
| `--trials N` | Number of independent trials per task | 1 |
| `--timeout N` | Per-task execution timeout (seconds) | 120 |
| `--parallel N` | Number of parallel evaluation workers | 1 |
| `--baseline VERSION` | Compare results against a stored baseline | None |
| `--compare` | Show baseline comparison in report | Off |
| `--matrix` | Enable matrix evaluation | Off |

### Examples

```bash
nines eval tasks/coding.toml
nines eval tasks/ --scorer composite --sandbox --seed 42
nines eval tasks/ --format json -o results.json
nines eval tasks/ --trials 3 --baseline v1 --compare
```

---

## `nines collect`

Search and collect information from configured sources.

```
nines collect <SOURCE> <QUERY> [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `SOURCE` | Data source: `github`, `arxiv` |
| `QUERY` | Search query string |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--limit N` | Maximum number of results | 50 |
| `--incremental` | Only fetch new items since last run | From config |
| `--store PATH` | Override data store path | From config |
| `--no-incremental` | Force full collection | Off |

### Examples

```bash
nines collect github "AI agent evaluation" --limit 20
nines collect arxiv "LLM self-improvement" --limit 10
nines collect github "AI agent evaluation" --incremental --store ./data
```

---

## `nines analyze`

Analyze and decompose collected knowledge into structured units.

```
nines analyze <TARGET> [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `TARGET` | Path to the directory or repository to analyze |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--depth LEVEL` | Analysis depth: `shallow`, `standard`, `deep` | `standard` |
| `--decompose` | Enable knowledge decomposition | From config |
| `--index` | Enable knowledge indexing | From config |
| `--strategies LIST` | Decomposition strategies (comma-separated) | `functional,concern,layer` |
| `--output FORMAT` | Report format: `text`, `json`, `markdown` | `text` |
| `--incremental` | Only re-analyze changed files | Off |

### Examples

```bash
nines analyze ./target-repo
nines analyze ./target-repo --depth deep --decompose --index
nines analyze ./target-repo --output markdown -o analysis.md
```

---

## `nines self-eval`

Run self-evaluation across capability dimensions.

```
nines self-eval [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dimensions DIM,...` | Comma-separated dimension IDs (e.g., `D01,D02`) | All |
| `--baseline VERSION` | Compare against a stored baseline | Latest |
| `--compare` | Show delta comparison | Off |
| `--report` | Generate detailed report | Off |
| `--save-baseline TAG` | Save results as a new baseline | None |
| `--list-baselines` | List all stored baselines | Off |
| `--stability-runs N` | Number of stability verification runs | 3 |

### Examples

```bash
nines self-eval
nines self-eval --dimensions D01,D02,D03 --baseline v1 --compare
nines self-eval --report -o self_eval_report.md
nines self-eval --save-baseline v1.1
```

---

## `nines iterate`

Execute a self-improvement iteration cycle (MAPIM loop).

```
nines iterate [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--max-rounds N` | Maximum MAPIM iterations | 10 |
| `--convergence-threshold F` | Variance threshold for convergence | 0.001 |
| `--dry-run` | Show planned improvements without executing | Off |
| `--baseline VERSION` | Baseline to compare against | Latest |

### Examples

```bash
nines iterate --max-rounds 5
nines iterate --max-rounds 10 --convergence-threshold 0.001 --dry-run
```

---

## `nines install`

Install or uninstall NineS as an agent skill.

```
nines install [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--target TARGET` | Target runtime: `cursor`, `claude`, `codex`, `copilot`, `all` | Required |
| `--uninstall` | Remove NineS skill files from the target runtime | Off |
| `--global` | Install to global user directory | Off |
| `--project-dir PATH` | Project root directory | Current directory |
| `--dry-run` | Show what would be done | Off |
| `--force` | Overwrite existing installation | Off |

### Targets

| Target | Description | Install Directory |
|--------|-------------|-------------------|
| `cursor` | Cursor IDE agent skill | `.cursor/skills/nines/` |
| `claude` | Claude Code slash commands | `.claude/commands/nines/` |
| `codex` | Codex agent skill | `.codex/skills/nines/` |
| `copilot` | GitHub Copilot instructions | `.github/copilot-instructions.md` |
| `all` | All detected runtimes | All of the above |

### Examples

```bash
nines install --target cursor
nines install --target claude --global
nines install --target codex
nines install --target copilot
nines install --target all --dry-run
nines install --target cursor --uninstall
nines install --target all --uninstall
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid arguments or general error |
| 2 | Task or resource not found |
| 3 | Execution failure |
| 4 | Scoring error |
| 5 | Sandbox error |
| 6 | Budget exceeded |
| 7 | Configuration error |
| 10 | Collection API error |
| 11 | Rate limit exceeded |
| 12 | Authentication error |

---

## Output Formats

### Text (default)

Human-readable colored output with tables and summaries.

### JSON

Machine-readable structured output. Use with `-o` to write to file:

```bash
nines eval tasks/ --format json -o results.json
```

### Markdown

Report-style output with tables, headings, and formatted sections:

```bash
nines eval tasks/ --format markdown -o report.md
```
