# NineS — Claude Code Commands Template

This document defines the slash command templates for integrating NineS as a set of Claude Code commands installed at `.claude/commands/nines/`.

## Command Definitions

### /nines:eval

```yaml
---
name: nines:eval
description: Run evaluation benchmarks on agent capabilities.
argument-hint: "<task-or-suite> [--scorer TYPE] [--format FORMAT] [--sandbox] [--seed N]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - Task
---

Execute `nines eval $ARGUMENTS`.

Use this command to:
- Benchmark agent capabilities against defined task suites
- Compare scoring accuracy across different scorer types
- Run evaluations in sandboxed isolation with seed control

Output: evaluation results with per-task scores, statistical summary, and recommendations.
```

### /nines:collect

```yaml
---
name: nines:collect
description: Search and collect information from configured sources.
argument-hint: "<source> <query> [--incremental] [--store PATH] [--limit N]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - Task
---

Execute `nines collect $ARGUMENTS`.

Use this command to:
- Search GitHub for repositories matching a query
- Search arXiv for relevant papers
- Perform incremental collection (only new items since last run)
- Store collected data persistently for analysis

Output: list of collected entities (repositories, papers) with metadata.
```

### /nines:analyze

```yaml
---
name: nines:analyze
description: Analyze and decompose collected knowledge into structured units.
argument-hint: "<target> [--depth LEVEL] [--decompose] [--index] [--output FORMAT]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - Task
---

Execute `nines analyze $ARGUMENTS`.

Use this command to:
- Analyze a codebase's structure and architecture patterns
- Decompose code into knowledge units (functions, classes, modules)
- Build a searchable knowledge index
- Compute complexity metrics and detect code review findings

Output: analysis report with structural breakdown, knowledge units, and findings.
```

### /nines:self-eval

```yaml
---
name: nines:self-eval
description: Run self-evaluation across all capability dimensions.
argument-hint: "[--dimensions DIM,...] [--baseline VERSION] [--compare] [--report]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - Task
---

Execute `nines self-eval $ARGUMENTS`.

Use this command to:
- Measure NineS performance across 19 self-evaluation dimensions
- Compare current scores against a stored baseline version
- Generate a trend analysis report showing version-over-version progress
- Identify capability gaps and regression areas

Output: self-evaluation report with per-dimension scores, comparisons, and recommendations.
```

### /nines:iterate

```yaml
---
name: nines:iterate
description: Execute a self-improvement iteration cycle.
argument-hint: "[--max-rounds N] [--convergence-threshold F] [--dry-run]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - Task
---

Execute `nines iterate $ARGUMENTS`.

Use this command to:
- Run the MAPIM (Measure-Analyze-Plan-Improve-Measure) self-improvement loop
- Detect capability gaps and generate prioritized improvement plans
- Track convergence across multiple iteration rounds
- Dry-run to preview planned improvements without executing them

Output: iteration summary with gap analysis, improvement plan, and convergence status.
```

### /nines:install

```yaml
---
name: nines:install
description: Install or uninstall NineS as an agent skill.
argument-hint: "--target <cursor|claude|all> [--uninstall] [--global]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - Task
---

Execute `nines install $ARGUMENTS`.

Use this command to:
- Install NineS skill files into the current project
- Target Cursor (.cursor/skills/nines/) or Claude Code (.claude/commands/nines/)
- Uninstall previously installed skill files
- Install globally for all projects

Output: list of installed/removed files and installation status.
```

## CLAUDE.md Section

When NineS is installed for Claude Code, the following section is appended to the project's `CLAUDE.md`:

```markdown
<!-- nines:start -->
## NineS Agent Toolflow

### Available Commands
- `/nines:eval` — Run evaluation benchmarks on agent capabilities.
- `/nines:collect` — Search and collect information from configured sources.
- `/nines:analyze` — Analyze and decompose collected knowledge into structured units.
- `/nines:self-eval` — Run self-evaluation across all capability dimensions.
- `/nines:iterate` — Execute a self-improvement iteration cycle.
- `/nines:install` — Install or uninstall NineS as an agent skill.

### Configuration
NineS configuration: `nines.toml` (project root) or `~/.config/nines/config.toml` (global).
<!-- nines:end -->
```

## Integration Notes

- Commands are installed at `.claude/commands/nines/` as individual `.md` files
- Each command file uses YAML frontmatter for metadata
- The `allowed-tools` list grants the command access to filesystem and execution tools
- `$ARGUMENTS` is substituted with user-provided arguments at invocation time
- The CLAUDE.md section uses sentinel comments (`nines:start`/`nines:end`) for idempotent updates
