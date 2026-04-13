# NineS Agent Skill Interface Specification

> Task T09 — Defines the complete interface for NineS as an installable Agent Skill across Cursor, Claude Code, Codex, GitHub Copilot, and programmatic consumers.
>
> **Read-only reference:** `docs/research/gsd_analysis.md`
> **Last updated:** 2026-04-11

---

## Table of Contents

1. [Skill Manifest Format](#1-skill-manifest-format)
2. [Cursor Skill Adapter](#2-cursor-skill-adapter)
3. [Claude Code Adapter](#3-claude-code-adapter)
4. [Codex Skill Adapter](#4-codex-skill-adapter)
5. [GitHub Copilot Adapter](#5-github-copilot-adapter)
6. [CLI Interface Definition](#6-cli-interface-definition)
7. [Programmatic API](#7-programmatic-api)
8. [Install / Uninstall Mechanism](#8-install--uninstall-mechanism)

---

## 1. Skill Manifest Format

The manifest is the single source of truth describing a NineS installation. It is authored in JSON and lives at the root of the installed skill directory. Every adapter reads this manifest to generate runtime-specific files.

### 1.1 Complete Schema

```jsonc
{
  "$schema": "https://nines.dev/schemas/manifest-v1.json",

  // ── Identity ──
  "name": "nines",
  "version": "0.1.0",
  "description": "Self-iterating agent toolflow for evaluation, information collection, and knowledge analysis.",
  "author": "YoRHa-Agents",
  "license": "MIT",
  "homepage": "https://github.com/YoRHa-Agents/NineS",

  // ── Capabilities declared by this skill ──
  "capabilities": [
    "eval",          // Run evaluation benchmarks
    "collect",       // Search and track information sources
    "analyze",       // Deep knowledge analysis and decomposition
    "self-eval",     // Self-assessment across capability dimensions
    "iterate",       // Self-improvement iteration cycle
    "install"        // Install/uninstall skill into agent runtimes
  ],

  // ── Commands exposed to agent runtimes ──
  "commands": {
    "nines-eval": {
      "description": "Run evaluation benchmarks on agent capabilities.",
      "argument_hint": "<task-or-suite> [--scorer TYPE] [--format FORMAT] [--sandbox] [--seed N]",
      "capability": "eval"
    },
    "nines-collect": {
      "description": "Search and collect information from configured sources.",
      "argument_hint": "<source> <query> [--incremental] [--store PATH] [--limit N]",
      "capability": "collect"
    },
    "nines-analyze": {
      "description": "Analyze and decompose collected knowledge into structured units.",
      "argument_hint": "<target> [--depth LEVEL] [--decompose] [--index] [--output FORMAT]",
      "capability": "analyze"
    },
    "nines-self-eval": {
      "description": "Run self-evaluation across all capability dimensions.",
      "argument_hint": "[--dimensions DIM,...] [--baseline VERSION] [--compare] [--report]",
      "capability": "self-eval"
    },
    "nines-iterate": {
      "description": "Execute a self-improvement iteration cycle.",
      "argument_hint": "[--max-rounds N] [--convergence-threshold F] [--dry-run]",
      "capability": "iterate"
    },
    "nines-install": {
      "description": "Install or uninstall NineS as an agent skill.",
      "argument_hint": "--target <cursor|claude|codex|copilot|all> [--uninstall] [--global]",
      "capability": "install"
    }
  },

  // ── Dependencies ──
  "dependencies": {
    "python": ">=3.12",
    "package": "nines",
    "cli_binary": "nines"
  },

  // ── Compatibility matrix ──
  "compatibility": {
    "runtimes": {
      "cursor": {
        "min_version": "0.50.0",
        "skill_format": "SKILL.md",
        "install_dir": ".cursor/skills/nines/"
      },
      "claude_code": {
        "min_version": "1.0.0",
        "skill_format": "commands/*.md",
        "install_dir": ".claude/commands/nines/"
      },
      "codex": {
        "skill_format": "SKILL.md",
        "install_dir": ".codex/skills/nines/"
      },
      "copilot": {
        "skill_format": "copilot-instructions.md",
        "install_dir": ".github/"
      }
    },
    "platforms": ["linux", "macos", "windows"],
    "architectures": ["x86_64", "aarch64"]
  },

  // ── Metadata ──
  "manifest_version": 1,
  "generated_at": null
}
```

### 1.2 Schema Field Definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Package identifier, lowercase, no spaces. |
| `version` | `string` | yes | SemVer version string. |
| `description` | `string` | yes | One-line description for skill listings. |
| `author` | `string` | yes | Author or organization name. |
| `license` | `string` | no | SPDX license identifier. |
| `homepage` | `string` | no | URL to project homepage or repository. |
| `capabilities` | `string[]` | yes | List of capability identifiers this skill provides. |
| `commands` | `Record<string, CommandDef>` | yes | Commands exposed to agent runtimes (see below). |
| `commands[].description` | `string` | yes | Human-readable command description. |
| `commands[].argument_hint` | `string` | yes | Usage hint showing expected arguments and flags. |
| `commands[].capability` | `string` | yes | Which capability this command exercises. Must be in `capabilities`. |
| `dependencies.python` | `string` | yes | Python version specifier (PEP 440). |
| `dependencies.package` | `string` | yes | PyPI package name for `pip install`. |
| `dependencies.cli_binary` | `string` | yes | Name of the CLI binary available on `$PATH` after install. |
| `compatibility.runtimes` | `Record<string, RuntimeDef>` | yes | Per-runtime installation metadata. |
| `compatibility.runtimes[].min_version` | `string` | no | Minimum runtime version required. |
| `compatibility.runtimes[].skill_format` | `string` | yes | File format used by this runtime for skills. |
| `compatibility.runtimes[].install_dir` | `string` | yes | Relative path where skill files are installed. |
| `compatibility.platforms` | `string[]` | no | Supported OS platforms. |
| `compatibility.architectures` | `string[]` | no | Supported CPU architectures. |
| `manifest_version` | `integer` | yes | Schema version for forward compatibility. Must be `1`. |
| `generated_at` | `string \| null` | no | ISO 8601 timestamp set by the installer on generation. |

### 1.3 Validation Rules

1. `name` must match `^[a-z][a-z0-9_-]*$`.
2. `version` must be valid SemVer.
3. Every `commands[].capability` must reference an entry in `capabilities`.
4. `manifest_version` must be `1` for this schema version. Future breaking changes increment this.
5. `dependencies.python` must be a valid PEP 440 specifier.

---

## 2. Cursor Skill Adapter

### 2.1 Directory Structure

When installed into Cursor, NineS creates the following file tree:

```
.cursor/
└── skills/
    └── nines/
        ├── SKILL.md              # Main skill entry point (Cursor reads this)
        ├── commands/
        │   ├── eval.md           # nines-eval command workflow
        │   ├── collect.md        # nines-collect command workflow
        │   ├── analyze.md        # nines-analyze command workflow
        │   ├── self-eval.md      # nines-self-eval command workflow
        │   ├── iterate.md        # nines-iterate command workflow
        │   └── install.md        # nines-install command workflow
        └── references/
            ├── capabilities.md   # Capability model reference
            └── config.md         # Configuration reference
```

### 2.2 SKILL.md Content Format

The `SKILL.md` file is the primary entry point that Cursor loads when the skill is invoked. It follows Cursor's skill protocol: a description block, available commands, invocation rules, and usage examples.

```markdown
# NineS — Self-Iterating Agent Toolflow

NineS is an agent skill providing three core capabilities: **evaluation & benchmarking**,
**information collection & tracking**, and **knowledge analysis & decomposition**.
It supports self-assessment and self-improvement iteration cycles.

## Available Commands

| Command | Description |
|---------|-------------|
| `nines-eval` | Run evaluation benchmarks on agent capabilities |
| `nines-collect` | Search and collect information from GitHub, arXiv, and other sources |
| `nines-analyze` | Analyze and decompose collected knowledge into structured units |
| `nines-self-eval` | Run self-evaluation across all capability dimensions |
| `nines-iterate` | Execute a self-improvement iteration cycle |
| `nines-install` | Install or uninstall NineS into agent runtimes |

## Invocation

When the user mentions any command above or describes a task matching one of these
capabilities, invoke the corresponding command by reading its workflow file from
`.cursor/skills/nines/commands/<command>.md` and executing it end-to-end.

Treat all user text after the command mention as arguments. If no arguments are
provided, use sensible defaults as described in each command file.

## Prerequisites

NineS must be installed as a Python package. The `nines` CLI binary must be on `$PATH`.
All commands delegate to `nines <subcommand>` via the Shell tool.

## Usage Examples

### Run an evaluation suite
User: "nines-eval coding-tasks --scorer composite --format markdown"
→ Read `.cursor/skills/nines/commands/eval.md`, execute the workflow.

### Collect GitHub repositories
User: "nines-collect github 'AI agent evaluation' --limit 20"
→ Read `.cursor/skills/nines/commands/collect.md`, execute the workflow.

### Analyze a repository
User: "nines-analyze ./target-repo --depth full --decompose"
→ Read `.cursor/skills/nines/commands/analyze.md`, execute the workflow.

### Run self-evaluation
User: "nines-self-eval --compare --report"
→ Read `.cursor/skills/nines/commands/self-eval.md`, execute the workflow.
```

### 2.3 Command Workflow File Format

Each file in `commands/` uses the adapter header pattern (derived from GSD's `<cursor_skill_adapter>` approach) followed by the workflow body:

```markdown
<nines_cursor_adapter>
## A. Skill Invocation
- This command is invoked when the user mentions `nines-eval` or describes
  an evaluation/benchmarking task.
- Treat all user text after the command mention as `{{NINES_ARGS}}`.
- If no arguments are present, treat `{{NINES_ARGS}}` as empty.

## B. Tool Mapping
- Use `Shell` to execute CLI commands (not `Bash`).
- Use `Read` to read result files.
- Use `Write` to create configuration files if needed.
- Use `Task(subagent_type="generalPurpose", ...)` if parallel evaluation is needed.

## C. Execution
Run the NineS CLI via Shell and process the results.
</nines_cursor_adapter>

## Workflow: nines-eval

### Objective
Run evaluation benchmarks on agent capabilities using NineS's eval pipeline.

### Process
1. **Parse arguments**: Extract task/suite name, scorer type, format, flags from `{{NINES_ARGS}}`.
2. **Validate prerequisites**: Check `nines` is available via `which nines`.
3. **Execute evaluation**:
   ```
   nines eval {{NINES_ARGS}}
   ```
4. **Read results**: The command outputs results to stdout and optionally to a file
   (controlled by `--output`). Read the output file if `--output` was specified.
5. **Report**: Present the evaluation results to the user in the requested format.

### Error Handling
- If `nines` is not found, advise: `pip install nines` or `uv pip install nines`.
- If the evaluation fails, show the stderr output and suggest fixes.
- Exit code 0 = success, non-zero = failure (see CLI exit codes in the reference).
```

### 2.4 Capability-to-Command Mapping

| NineS Capability | Cursor Command | CLI Delegation | Cursor Tools Used |
|---|---|---|---|
| Evaluation | `nines-eval` | `nines eval ...` | Shell, Read |
| Collection | `nines-collect` | `nines collect ...` | Shell, Read, Write |
| Analysis | `nines-analyze` | `nines analyze ...` | Shell, Read |
| Self-Evaluation | `nines-self-eval` | `nines self-eval ...` | Shell, Read |
| Iteration | `nines-iterate` | `nines iterate ...` | Shell, Read, Write, Task |
| Installation | `nines-install` | `nines install ...` | Shell |

### 2.5 Installation Process

1. Verify `nines` Python package is installed (check `which nines`).
2. Create directory `.cursor/skills/nines/` in the project root.
3. Write `SKILL.md` from the manifest template.
4. Write each command workflow file to `commands/`.
5. Write reference files to `references/`.
6. No Cursor config file modification is needed — Cursor auto-discovers skills under `.cursor/skills/`.

---

## 3. Claude Code Adapter

### 3.1 Integration Approach

Claude Code supports two integration mechanisms. NineS uses **both**:

1. **Slash commands** via `commands/nines/*.md` — for structured command invocation.
2. **CLAUDE.md instructions** — for ambient context that teaches Claude Code about NineS capabilities.

### 3.2 Directory Structure

```
.claude/
├── commands/
│   └── nines/
│       ├── eval.md
│       ├── collect.md
│       ├── analyze.md
│       ├── self-eval.md
│       ├── iterate.md
│       └── install.md
└── (CLAUDE.md receives an appended NineS section)
```

### 3.3 Command Format

Each command file uses Claude Code's native YAML frontmatter + body structure:

```yaml
---
name: nines:eval
description: Run evaluation benchmarks on agent capabilities
argument-hint: "<task-or-suite> [--scorer TYPE] [--format FORMAT] [--sandbox] [--seed N]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Task
---
```

```markdown
<objective>
Execute NineS evaluation benchmarks. Parse user arguments, run the eval pipeline
via the `nines` CLI, and present structured results.
</objective>

<process>
1. Parse $ARGUMENTS to extract: task/suite identifier, scorer type, output format, flags.
2. Validate that the `nines` CLI is installed: `which nines`.
3. Run the evaluation:
   ```bash
   nines eval $ARGUMENTS
   ```
4. If `--output` flag was specified, read the output file and present results.
5. If no `--output`, parse stdout for the results summary.
6. Present results to the user in the requested format (default: markdown table).
</process>

<error_handling>
- Exit code 1: Invalid arguments → show usage hint.
- Exit code 2: Task/suite not found → list available tasks.
- Exit code 3: Execution failure → show stderr, suggest debug steps.
- If `nines` not found → advise `pip install nines`.
</error_handling>
```

### 3.4 CLAUDE.md Section

The installer appends a NineS section to the project's `CLAUDE.md` (or creates it). This provides ambient context so Claude Code understands NineS capabilities even without explicit slash-command invocation:

```markdown
## NineS Agent Toolflow

This project uses NineS for evaluation, information collection, and knowledge analysis.

### Available Commands
- `/nines:eval` — Run evaluation benchmarks
- `/nines:collect` — Collect information from sources (GitHub, arXiv)
- `/nines:analyze` — Analyze and decompose knowledge
- `/nines:self-eval` — Self-assessment across capability dimensions
- `/nines:iterate` — Self-improvement iteration cycle
- `/nines:install` — Manage NineS skill installation

### Configuration
NineS configuration: `nines.toml` (project root) or `~/.config/nines/config.toml` (global).

### Quick Reference
- Run evaluations: `/nines:eval <suite>`
- Collect repos: `/nines:collect github "<query>"`
- Full self-eval: `/nines:self-eval --report`
```

### 3.5 Capability-to-Command Mapping

| NineS Capability | Claude Code Command | Invocation | Native Tools |
|---|---|---|---|
| Evaluation | `nines:eval` | `/nines:eval <args>` | Bash, Read |
| Collection | `nines:collect` | `/nines:collect <args>` | Bash, Read, Write |
| Analysis | `nines:analyze` | `/nines:analyze <args>` | Bash, Read |
| Self-Evaluation | `nines:self-eval` | `/nines:self-eval <args>` | Bash, Read |
| Iteration | `nines:iterate` | `/nines:iterate <args>` | Bash, Read, Write, Task |
| Installation | `nines:install` | `/nines:install <args>` | Bash |

---

## 4. Codex Skill Adapter

### 4.1 Integration Approach

Codex uses the same SKILL.md-based skill protocol as Cursor. NineS installs a skill directory under `.codex/skills/nines/` containing a `SKILL.md` entry point and per-command workflow files.

### 4.2 Directory Structure

```
.codex/
└── skills/
    └── nines/
        ├── SKILL.md              # Main skill entry point (Codex reads this)
        ├── manifest.json         # Version manifest
        └── commands/
            ├── eval.md           # nines-eval command workflow
            ├── collect.md        # nines-collect command workflow
            ├── analyze.md        # nines-analyze command workflow
            ├── self-eval.md      # nines-self-eval command workflow
            ├── iterate.md        # nines-iterate command workflow
            └── install.md        # nines-install command workflow
```

### 4.3 SKILL.md Content Format

The `SKILL.md` file follows the same format as the Cursor adapter — a description block, available commands, invocation rules, and usage examples. The content is generated from the same manifest template, ensuring consistency across runtimes.

### 4.4 Capability-to-Command Mapping

| NineS Capability | Codex Command | CLI Delegation | Codex Tools Used |
|---|---|---|---|
| Evaluation | `nines-eval` | `nines eval ...` | Shell, Read |
| Collection | `nines-collect` | `nines collect ...` | Shell, Read, Write |
| Analysis | `nines-analyze` | `nines analyze ...` | Shell, Read |
| Self-Evaluation | `nines-self-eval` | `nines self-eval ...` | Shell, Read |
| Iteration | `nines-iterate` | `nines iterate ...` | Shell, Read, Write |
| Installation | `nines-install` | `nines install ...` | Shell |

### 4.5 Installation Process

1. Verify `nines` Python package is installed (check `which nines`).
2. Create directory `.codex/skills/nines/` in the project root.
3. Write `SKILL.md` from the manifest template (same content as Cursor adapter).
4. Write each command workflow file to `commands/`.
5. Write `manifest.json` for version tracking.
6. Codex auto-discovers skills under `.codex/skills/`.

---

## 5. GitHub Copilot Adapter

### 5.1 Integration Approach

GitHub Copilot uses a single instructions file (`.github/copilot-instructions.md`) for project-level customization. NineS generates this file with comprehensive documentation of all available CLI commands, usage patterns, and capability descriptions.

Unlike the multi-file approaches used by Cursor, Claude Code, and Codex, Copilot relies on a single Markdown document that provides ambient context about NineS capabilities.

### 5.2 File Structure

```
.github/
└── copilot-instructions.md     # NineS capability documentation
```

### 5.3 Instructions Content Format

The `copilot-instructions.md` file contains:

1. **Overview** — Brief description of NineS and its purpose.
2. **Available Commands** — Table of all CLI commands with descriptions and usage hints.
3. **Usage Examples** — Concrete examples for each command.
4. **Configuration** — How NineS configuration works.
5. **Error Handling** — Common errors and troubleshooting hints.

The content is delimited by markers (`<!-- nines:start -->` / `<!-- nines:end -->`) for clean install/uninstall, similar to the CLAUDE.md approach.

### 5.4 Capability-to-Command Mapping

| NineS Capability | CLI Command | Usage Pattern |
|---|---|---|
| Evaluation | `nines eval` | `nines eval <task> [--scorer TYPE] [--sandbox]` |
| Collection | `nines collect` | `nines collect <source> <query> [--limit N]` |
| Analysis | `nines analyze` | `nines analyze <target> [--depth LEVEL]` |
| Self-Evaluation | `nines self-eval` | `nines self-eval [--report] [--compare]` |
| Iteration | `nines iterate` | `nines iterate [--max-rounds N]` |
| Installation | `nines install` | `nines install --target <runtime>` |

### 5.5 Installation Process

1. Verify `nines` Python package is installed.
2. Check if `.github/copilot-instructions.md` exists.
3. If it exists, append the NineS section between markers (or update existing markers).
4. If it does not exist, create it with the NineS section.
5. Write `manifest.json` to `.github/` for version tracking.

### 5.6 Uninstallation

1. Remove the `<!-- nines:start -->` ... `<!-- nines:end -->` section from `.github/copilot-instructions.md`.
2. If the file is now empty, remove it.

---

## 6. CLI Interface Definition

### 6.1 Top-Level Structure

```
nines [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS] [ARGS...]
```

**Global options** (available on every command):

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--config` | `-c` | `PATH` | auto-discover | Path to `nines.toml` config file. |
| `--verbose` | `-v` | `flag` | off | Increase output verbosity. Repeat for more (`-vv`, `-vvv`). |
| `--quiet` | `-q` | `flag` | off | Suppress non-essential output. |
| `--output` | `-o` | `PATH` | stdout | Write primary output to file instead of stdout. |
| `--format` | `-f` | `string` | `text` | Output format: `text`, `json`, `markdown`. |
| `--no-color` | | `flag` | off | Disable colored output. |
| `--version` | `-V` | `flag` | | Print version and exit. |
| `--help` | `-h` | `flag` | | Show help and exit. |

### 6.2 Command: `nines eval`

Run evaluation benchmarks.

```
nines eval [OPTIONS] <TASK_OR_SUITE>
```

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `TASK_OR_SUITE` | yes | Task file path, suite name, or glob pattern. |

**Options:**

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--scorer` | `-s` | `string` | `composite` | Scorer to use: `exact`, `fuzzy`, `rubric`, `composite`. |
| `--sandbox` | | `flag` | off | Execute evaluation tasks in isolated sandbox. |
| `--seed` | | `int` | none | Random seed for deterministic reproduction. |
| `--timeout` | `-t` | `int` | `300` | Per-task timeout in seconds. |
| `--parallel` | `-p` | `int` | `1` | Number of parallel evaluation workers. |
| `--baseline` | `-b` | `string` | none | Compare results against named baseline. |
| `--matrix` | `-m` | `flag` | off | Run matrix combination evaluation (all scorers × all tasks). |
| `--report` | `-r` | `flag` | off | Generate a full evaluation report after run. |

**Examples:**

```bash
nines eval tasks/coding.toml --scorer composite --sandbox --seed 42
nines eval benchmark-suite --format json --output results.json
nines eval "tasks/*.toml" --parallel 4 --matrix --report
nines eval tasks/analysis.toml --baseline v1 --format markdown
```

### 6.3 Command: `nines collect`

Search and collect information from data sources.

```
nines collect [OPTIONS] <SOURCE> <QUERY>
```

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `SOURCE` | yes | Data source: `github`, `arxiv`. |
| `QUERY` | yes | Search query string (quoted if multi-word). |

**Options:**

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--limit` | `-l` | `int` | `50` | Maximum results to collect. |
| `--incremental` | `-i` | `flag` | off | Only collect new/changed items since last run. |
| `--store` | | `PATH` | `.nines/data/` | Local storage directory for collected data. |
| `--track` | | `flag` | off | Enable ongoing tracking for matched items. |
| `--since` | | `string` | none | ISO 8601 date; only collect items after this date. |
| `--sort` | | `string` | `relevance` | Sort order: `relevance`, `stars`, `updated`, `created`. |
| `--fields` | | `string` | `default` | Fields to collect: `default`, `full`, `minimal`, or comma-separated list. |

**Subcommands:**

| Subcommand | Description |
|---|---|
| `nines collect status` | Show tracking status for all tracked sources. |
| `nines collect update` | Run incremental update on all tracked sources. |
| `nines collect list` | List all collected items with summary. |
| `nines collect export <FORMAT>` | Export collected data as `json`, `csv`, or `markdown`. |

**Examples:**

```bash
nines collect github "AI agent evaluation framework" --limit 20 --sort stars
nines collect arxiv "large language model benchmark" --since 2026-01-01
nines collect github "cursor plugin" --track --incremental
nines collect status
nines collect update --format json
nines collect export json --output collected.json
```

### 6.4 Command: `nines analyze`

Analyze and decompose knowledge.

```
nines analyze [OPTIONS] <TARGET>
```

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `TARGET` | yes | Path to repository, file, or collected data item. |

**Options:**

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--depth` | `-d` | `string` | `standard` | Analysis depth: `shallow`, `standard`, `deep`. |
| `--decompose` | | `flag` | off | Decompose into knowledge units after analysis. |
| `--index` | | `flag` | off | Build/update the knowledge index with results. |
| `--reviewers` | | `string` | `all` | Reviewers to run: `ast`, `structure`, `complexity`, `all`. |
| `--target-lang` | | `string` | auto-detect | Target language for code analysis. |

**Subcommands:**

| Subcommand | Description |
|---|---|
| `nines analyze review <PATH>` | Run code review on a specific file or directory. |
| `nines analyze structure <PATH>` | Analyze project/directory structure. |
| `nines analyze search <QUERY>` | Search the knowledge index. |
| `nines analyze graph` | Display the knowledge unit relationship graph. |

**Examples:**

```bash
nines analyze ./target-repo --depth deep --decompose --index
nines analyze review src/main.py --reviewers ast,complexity
nines analyze structure ./project --format json
nines analyze search "dependency injection patterns"
```

### 6.5 Command: `nines self-eval`

Run self-evaluation.

```
nines self-eval [OPTIONS]
```

**Options:**

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--dimensions` | `-d` | `string` | `all` | Comma-separated dimension names, or `all`. |
| `--baseline` | `-b` | `string` | `latest` | Baseline version to compare against. |
| `--compare` | | `flag` | off | Show comparison with baseline. |
| `--report` | `-r` | `flag` | off | Generate full self-evaluation report. |
| `--save` | | `flag` | off | Save results as a new baseline snapshot. |
| `--label` | | `string` | auto-timestamp | Label for the saved baseline snapshot. |

**Subcommands:**

| Subcommand | Description |
|---|---|
| `nines self-eval baseline list` | List all saved baseline snapshots. |
| `nines self-eval baseline show <LABEL>` | Show details of a specific baseline. |
| `nines self-eval history` | Show self-evaluation score history and trends. |
| `nines self-eval dimensions` | List all available evaluation dimensions. |

**Examples:**

```bash
nines self-eval --report --compare --format markdown
nines self-eval --dimensions eval_accuracy,collection_coverage --save --label v0.1
nines self-eval baseline list
nines self-eval history --format json
```

### 6.6 Command: `nines iterate`

Execute self-improvement iteration.

```
nines iterate [OPTIONS]
```

**Options:**

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--max-rounds` | `-n` | `int` | `5` | Maximum iteration rounds. |
| `--convergence-threshold` | | `float` | `0.02` | Stop when improvement delta falls below this. |
| `--focus` | | `string` | `auto` | Focus area: `eval`, `collect`, `analyze`, or `auto` (lowest-scoring). |
| `--dry-run` | | `flag` | off | Show planned improvements without executing. |
| `--plan-only` | | `flag` | off | Generate iteration plan and stop. |

**Subcommands:**

| Subcommand | Description |
|---|---|
| `nines iterate status` | Show current iteration cycle status. |
| `nines iterate plan` | Show the current or last iteration plan. |
| `nines iterate gaps` | Analyze capability gaps from latest self-eval. |
| `nines iterate history` | Show iteration history across rounds. |

**Examples:**

```bash
nines iterate --max-rounds 3 --convergence-threshold 0.01
nines iterate --dry-run --focus eval
nines iterate gaps --format markdown
nines iterate plan --format json
```

### 6.7 Command: `nines install`

Install or uninstall NineS as an agent skill.

```
nines install [OPTIONS]
```

**Options:**

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--target` | `-t` | `string` | **required** | Target runtime: `cursor`, `claude`, `codex`, `copilot`, `all`. |
| `--uninstall` | | `flag` | off | Remove NineS skill from target. |
| `--global` | `-g` | `flag` | off | Install to global user directory instead of project. |
| `--project-dir` | | `PATH` | `.` | Project root for local installation. |
| `--dry-run` | | `flag` | off | Show what would be created/modified without writing. |
| `--force` | | `flag` | off | Overwrite existing installation. |

**Examples:**

```bash
nines install --target cursor
nines install --target claude --global
nines install --target all --dry-run
nines install --target cursor --uninstall
nines install --target all --force
```

### 6.8 Exit Codes

All commands follow a consistent exit code scheme:

| Code | Name | Description |
|---|---|---|
| `0` | `SUCCESS` | Command completed successfully. |
| `1` | `INVALID_ARGS` | Invalid arguments or flags. |
| `2` | `NOT_FOUND` | Requested resource (task, suite, source, baseline) not found. |
| `3` | `EXECUTION_ERROR` | Runtime error during command execution. |
| `4` | `TIMEOUT` | Operation exceeded timeout limit. |
| `5` | `SANDBOX_ERROR` | Sandbox creation or isolation failure. |
| `10` | `CONFIG_ERROR` | Configuration file invalid or missing required fields. |
| `11` | `DEPENDENCY_ERROR` | Required dependency not available. |
| `20` | `CONVERGENCE_FAIL` | Iteration did not converge within max rounds. |
| `130` | `INTERRUPTED` | Interrupted by user (SIGINT / Ctrl+C). |

### 6.9 Error Reporting

Errors are reported to stderr in a structured format:

```
nines: error[E003]: evaluation task failed
  --> tasks/coding.toml:15
  |
  | task "parse_json" timed out after 300s
  |
  = hint: increase timeout with --timeout or simplify the task
  = exit: 4
```

When `--format json` is active, errors are also written as JSON:

```json
{
  "error": {
    "code": "E003",
    "category": "EXECUTION_ERROR",
    "message": "evaluation task failed",
    "location": "tasks/coding.toml:15",
    "detail": "task \"parse_json\" timed out after 300s",
    "hint": "increase timeout with --timeout or simplify the task",
    "exit_code": 4
  }
}
```

---

## 7. Programmatic API

### 7.1 Package Structure

```python
import nines

# Top-level convenience functions (thin wrappers)
nines.eval(...)
nines.collect(...)
nines.analyze(...)
nines.self_eval(...)
nines.iterate(...)
nines.install(...)
```

### 7.2 Public API

#### `nines.eval`

```python
from nines.eval import EvalRunner, TaskDefinition, EvalResult, ScoreCard

def eval(
    task_or_suite: str | Path | list[TaskDefinition],
    *,
    scorer: str = "composite",
    sandbox: bool = False,
    seed: int | None = None,
    timeout: int = 300,
    parallel: int = 1,
    baseline: str | None = None,
    config: "NinesConfig | None" = None,
) -> EvalResult:
    """Run evaluation benchmarks and return structured results."""
```

**Key classes:**

```python
@dataclass
class TaskDefinition:
    """A single evaluation task."""
    id: str
    name: str
    description: str
    category: str
    input: dict[str, Any]
    expected: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout: int = 300
    tags: list[str] = field(default_factory=list)

@dataclass
class EvalResult:
    """Complete evaluation results."""
    task_results: list[TaskResult]
    score_card: ScoreCard
    metadata: RunMetadata
    
    def to_json(self) -> str: ...
    def to_markdown(self) -> str: ...
    def compare(self, baseline: "EvalResult") -> ComparisonReport: ...

@dataclass
class ScoreCard:
    """Aggregated scores across all tasks."""
    overall: float
    per_category: dict[str, float]
    per_scorer: dict[str, float]
    per_task: dict[str, float]
```

#### `nines.collect`

```python
from nines.collector import Collector, GitHubCollector, ArxivCollector

def collect(
    source: str,
    query: str,
    *,
    limit: int = 50,
    incremental: bool = False,
    store: str | Path = ".nines/data/",
    since: str | None = None,
    config: "NinesConfig | None" = None,
) -> CollectionResult:
    """Collect information from a data source."""
```

**Key classes:**

```python
class SourceProtocol(Protocol):
    """Interface for all data source collectors."""
    
    def search(self, query: str, **kwargs: Any) -> list[SourceItem]: ...
    def fetch(self, item_id: str) -> SourceItem: ...
    def track(self, item_id: str) -> TrackingHandle: ...
    def check_updates(self, since: datetime) -> list[ChangeEvent]: ...

@dataclass
class CollectionResult:
    """Results from a collection operation."""
    items: list[SourceItem]
    source: str
    query: str
    total_found: int
    collected: int
    new_since_last: int | None
    metadata: RunMetadata
```

#### `nines.analyze`

```python
from nines.analyzer import Analyzer, AnalysisResult, KnowledgeUnit

def analyze(
    target: str | Path,
    *,
    depth: str = "standard",
    decompose: bool = False,
    index: bool = False,
    reviewers: list[str] | None = None,
    config: "NinesConfig | None" = None,
) -> AnalysisResult:
    """Analyze a target and optionally decompose into knowledge units."""
```

**Key classes:**

```python
@dataclass
class AnalysisResult:
    """Complete analysis output."""
    findings: list[Finding]
    structure: StructureMap | None
    knowledge_units: list[KnowledgeUnit] | None
    metrics: AnalysisMetrics
    metadata: RunMetadata

@dataclass
class KnowledgeUnit:
    """An atomic unit of decomposed knowledge."""
    id: str
    title: str
    category: str
    content: str
    source: str
    relations: list[Relation]
    abstraction_level: int
    tags: list[str]
```

#### `nines.self_eval`

```python
from nines.iteration import SelfEvalRunner, SelfEvalResult, Baseline

def self_eval(
    *,
    dimensions: list[str] | None = None,
    baseline: str = "latest",
    compare: bool = False,
    save: bool = False,
    label: str | None = None,
    config: "NinesConfig | None" = None,
) -> SelfEvalResult:
    """Run self-evaluation across capability dimensions."""
```

**Key classes:**

```python
@dataclass
class SelfEvalResult:
    """Self-evaluation output."""
    dimension_scores: dict[str, DimensionScore]
    overall_score: float
    comparison: ComparisonReport | None
    recommendations: list[Recommendation]
    metadata: RunMetadata

@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""
    dimension: str
    score: float
    max_score: float
    normalized: float  # 0.0 – 1.0
    method: str
    evidence: list[str]
```

#### `nines.iterate`

```python
from nines.iteration import IterationEngine, IterationResult

def iterate(
    *,
    max_rounds: int = 5,
    convergence_threshold: float = 0.02,
    focus: str = "auto",
    dry_run: bool = False,
    config: "NinesConfig | None" = None,
) -> IterationResult:
    """Execute self-improvement iteration cycle."""
```

**Key classes:**

```python
@dataclass
class IterationResult:
    """Results from an iteration cycle."""
    rounds: list[RoundResult]
    converged: bool
    convergence_delta: float
    initial_score: float
    final_score: float
    improvements: list[Improvement]
    metadata: RunMetadata

@dataclass
class RoundResult:
    """A single iteration round."""
    round_number: int
    gaps: list[Gap]
    plan: ImprovementPlan
    executed: bool
    score_before: float
    score_after: float
    delta: float
```

#### `nines.install`

```python
from nines.skill import SkillInstaller, InstallResult

def install(
    *,
    target: str,
    uninstall: bool = False,
    global_install: bool = False,
    project_dir: str | Path = ".",
    dry_run: bool = False,
    force: bool = False,
) -> InstallResult:
    """Install or uninstall NineS as an agent skill."""
```

### 7.3 Configuration Object

```python
from nines.core.config import NinesConfig

config = NinesConfig.load()           # Auto-discover from project/user/defaults
config = NinesConfig.from_file("nines.toml")
config = NinesConfig.default()        # Pure defaults, no file

config.eval.default_scorer            # "composite"
config.eval.sandbox                   # False
config.collector.default_store        # ".nines/data/"
config.collector.github_token         # None (from env: GITHUB_TOKEN)
config.analyzer.default_depth         # "standard"
config.iteration.max_rounds           # 5
config.iteration.convergence_threshold  # 0.02
```

### 7.4 Event System

```python
from nines.core.events import EventBus, Event, EventType

bus = EventBus()

@bus.on(EventType.EVAL_TASK_COMPLETE)
def on_task_complete(event: Event):
    print(f"Task {event.data['task_id']} scored {event.data['score']}")

result = nines.eval("suite", config=NinesConfig(event_bus=bus))
```

---

## 8. Install / Uninstall Mechanism

### 8.1 Installation Flow

```
nines install --target <cursor|claude|codex|copilot|all> [--global] [--force]
```

#### Step-by-step: `nines install --target cursor`

1. **Resolve install directory:**
   - Local (default): `<project_dir>/.cursor/skills/nines/`
   - Global (`--global`): `~/.cursor/skills/nines/`
2. **Check existing installation:**
   - If exists and `--force` not set: error with message showing existing version.
   - If exists and `--force` set: remove old installation first.
3. **Load manifest:** Read the bundled `manifest.json` from the NineS package.
4. **Generate SKILL.md:** Render from template using manifest data (name, version, commands, description).
5. **Generate command files:** For each entry in `manifest.commands`, render the Cursor-format command workflow to `commands/<name>.md`. Apply Cursor adapter header.
6. **Generate reference files:** Write `references/capabilities.md` and `references/config.md`.
7. **Write manifest copy:** Write `manifest.json` into the install directory for version tracking.
8. **Report:**
   ```
   ✓ NineS v0.1.0 installed to .cursor/skills/nines/
     Created: SKILL.md, 6 commands, 2 references
     Invoke: mention "nines-eval", "nines-collect", etc. in Cursor chat
   ```

#### Files created: Cursor

| File | Purpose |
|---|---|
| `.cursor/skills/nines/SKILL.md` | Main skill entry point |
| `.cursor/skills/nines/manifest.json` | Installed version manifest |
| `.cursor/skills/nines/commands/eval.md` | Eval command workflow |
| `.cursor/skills/nines/commands/collect.md` | Collect command workflow |
| `.cursor/skills/nines/commands/analyze.md` | Analyze command workflow |
| `.cursor/skills/nines/commands/self-eval.md` | Self-eval command workflow |
| `.cursor/skills/nines/commands/iterate.md` | Iterate command workflow |
| `.cursor/skills/nines/commands/install.md` | Install command workflow |
| `.cursor/skills/nines/references/capabilities.md` | Capability model reference |
| `.cursor/skills/nines/references/config.md` | Configuration reference |

#### Step-by-step: `nines install --target claude`

1. **Resolve install directory:**
   - Local (default): `<project_dir>/.claude/commands/nines/`
   - Global (`--global`): `~/.claude/commands/nines/`
2. **Check existing installation:** Same as Cursor flow.
3. **Load manifest:** Same.
4. **Generate command files:** For each entry in `manifest.commands`, render Claude Code format with YAML frontmatter + semantic XML body to `<name>.md`.
5. **Update CLAUDE.md:**
   - If `CLAUDE.md` exists: append NineS section (delimited by markers for clean removal).
   - If `CLAUDE.md` does not exist: create it with NineS section.
   - Markers: `<!-- nines:start -->` ... `<!-- nines:end -->`
6. **Write manifest copy:** Write `manifest.json` for version tracking.
7. **Report:**
   ```
   ✓ NineS v0.1.0 installed to .claude/commands/nines/
     Created: 6 commands
     Updated: CLAUDE.md (NineS section appended)
     Invoke: /nines:eval, /nines:collect, etc.
   ```

#### Files created/modified: Claude Code

| File | Action | Purpose |
|---|---|---|
| `.claude/commands/nines/eval.md` | created | Eval slash command |
| `.claude/commands/nines/collect.md` | created | Collect slash command |
| `.claude/commands/nines/analyze.md` | created | Analyze slash command |
| `.claude/commands/nines/self-eval.md` | created | Self-eval slash command |
| `.claude/commands/nines/iterate.md` | created | Iterate slash command |
| `.claude/commands/nines/install.md` | created | Install slash command |
| `.claude/commands/nines/manifest.json` | created | Version manifest |
| `CLAUDE.md` | appended/created | Ambient NineS context |

#### Step-by-step: `nines install --target codex`

1. **Resolve install directory:**
   - Local (default): `<project_dir>/.codex/skills/nines/`
   - Global (`--global`): `~/.codex/skills/nines/`
2. **Check existing installation:** Same as Cursor flow.
3. **Load manifest:** Same.
4. **Generate SKILL.md:** Render from template using manifest data (same as Cursor format).
5. **Generate command files:** Write command workflow files to `commands/`.
6. **Write manifest copy:** Write `manifest.json` for version tracking.
7. **Report:**
   ```
   ✓ NineS v1.0.0-pre installed to .codex/skills/nines/
     Created: SKILL.md, 6 commands
     Invoke: mention "nines-eval", "nines-collect", etc. in Codex chat
   ```

#### Files created: Codex

| File | Purpose |
|---|---|
| `.codex/skills/nines/SKILL.md` | Main skill entry point |
| `.codex/skills/nines/manifest.json` | Installed version manifest |
| `.codex/skills/nines/commands/eval.md` | Eval command workflow |
| `.codex/skills/nines/commands/collect.md` | Collect command workflow |
| `.codex/skills/nines/commands/analyze.md` | Analyze command workflow |
| `.codex/skills/nines/commands/self-eval.md` | Self-eval command workflow |
| `.codex/skills/nines/commands/iterate.md` | Iterate command workflow |
| `.codex/skills/nines/commands/install.md` | Install command workflow |

#### Step-by-step: `nines install --target copilot`

1. **Resolve install directory:**
   - Local (default): `<project_dir>/.github/`
   - Global (`--global`): `~/.github/`
2. **Check existing installation:** Look for NineS markers in `.github/copilot-instructions.md`.
3. **Load manifest:** Same.
4. **Generate instructions content:** Render NineS capability documentation from template.
5. **Update copilot-instructions.md:**
   - If exists: append NineS section (delimited by markers `<!-- nines:start -->` / `<!-- nines:end -->`).
   - If does not exist: create it with NineS section.
6. **Report:**
   ```
   ✓ NineS v1.0.0-pre installed to .github/copilot-instructions.md
     Updated: copilot-instructions.md (NineS section appended)
   ```

#### Files created/modified: Copilot

| File | Action | Purpose |
|---|---|---|
| `.github/copilot-instructions.md` | appended/created | NineS capability documentation for Copilot |

### 8.2 Uninstallation Flow

```
nines install --target <cursor|claude|codex|copilot|all> --uninstall
```

#### Cursor uninstall

1. Verify `.cursor/skills/nines/` exists.
2. Remove the entire `.cursor/skills/nines/` directory.
3. If `.cursor/skills/` is now empty, remove it.
4. Report: `✓ NineS removed from .cursor/skills/nines/`

#### Claude Code uninstall

1. Verify `.claude/commands/nines/` exists.
2. Remove the entire `.claude/commands/nines/` directory.
3. If `CLAUDE.md` exists, remove the `<!-- nines:start -->` ... `<!-- nines:end -->` section.
4. If `CLAUDE.md` is now empty, remove it.
5. If `.claude/commands/` is now empty, remove it.
6. Report: `✓ NineS removed from .claude/commands/nines/ and CLAUDE.md`

#### Codex uninstall

1. Verify `.codex/skills/nines/` exists.
2. Remove the entire `.codex/skills/nines/` directory.
3. If `.codex/skills/` is now empty, remove it.
4. Report: `✓ NineS removed from .codex/skills/nines/`

#### Copilot uninstall

1. Verify `.github/copilot-instructions.md` exists and contains NineS markers.
2. Remove the `<!-- nines:start -->` ... `<!-- nines:end -->` section from `.github/copilot-instructions.md`.
3. If the file is now empty, remove it.
4. Report: `✓ NineS removed from .github/copilot-instructions.md`

### 8.3 Version Management

The installed `manifest.json` records the installed version. On subsequent `nines install`, version comparison drives behavior:

| Condition | Behavior |
|---|---|
| No existing install | Fresh install. |
| Same version installed | Skip with message: "NineS v0.1.0 already installed. Use --force to reinstall." |
| Older version installed | Upgrade in-place: remove old files, write new. Show changelog delta. |
| Newer version installed | Warn: "Installed v0.2.0 is newer than package v0.1.0. Use --force to downgrade." |

Version is read from `manifest.json` in the installed directory:

```python
def get_installed_version(install_dir: Path) -> str | None:
    manifest_path = install_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text())
    return manifest.get("version")
```

### 8.4 Dry-Run Mode

`--dry-run` prints every file operation without executing:

```
$ nines install --target cursor --dry-run
[dry-run] Would create: .cursor/skills/nines/SKILL.md (2.1 KB)
[dry-run] Would create: .cursor/skills/nines/manifest.json (1.4 KB)
[dry-run] Would create: .cursor/skills/nines/commands/eval.md (1.8 KB)
[dry-run] Would create: .cursor/skills/nines/commands/collect.md (1.6 KB)
[dry-run] Would create: .cursor/skills/nines/commands/analyze.md (1.5 KB)
[dry-run] Would create: .cursor/skills/nines/commands/self-eval.md (1.3 KB)
[dry-run] Would create: .cursor/skills/nines/commands/iterate.md (1.4 KB)
[dry-run] Would create: .cursor/skills/nines/commands/install.md (0.9 KB)
[dry-run] Would create: .cursor/skills/nines/references/capabilities.md (2.0 KB)
[dry-run] Would create: .cursor/skills/nines/references/config.md (1.1 KB)
[dry-run] Total: 10 files, 15.1 KB
```

### 8.5 Runtime Detection

The installer can auto-detect which runtimes are available when `--target all` is used:

```python
def detect_runtimes(project_dir: Path) -> list[str]:
    """Detect which agent runtimes are available."""
    detected = []
    if (project_dir / ".cursor").is_dir() or shutil.which("cursor"):
        detected.append("cursor")
    if (project_dir / ".claude").is_dir() or shutil.which("claude"):
        detected.append("claude_code")
    if (project_dir / ".codex").is_dir() or shutil.which("codex"):
        detected.append("codex")
    if (project_dir / ".github").is_dir():
        detected.append("copilot")
    return detected
```

When `--target all`, the installer iterates over detected runtimes and installs into each. If no runtimes are detected, it reports an error with instructions.

---

## Appendix A: Design Decisions

### A.1 JSON Manifest vs TOML

**Decision:** JSON for manifest, TOML for user-facing config.

**Rationale:** The manifest is machine-generated and machine-consumed — JSON's strict schema and universal parsing support make it the better choice. User configuration (`nines.toml`) uses TOML for readability and comment support, following Python ecosystem conventions (`pyproject.toml`).

### A.2 CLI-Delegation Model

**Decision:** Agent skill commands delegate to the `nines` CLI binary via shell execution rather than embedding Python evaluation logic in markdown.

**Rationale:** This follows GSD's pattern of commands as "launchers." The CLI is the single implementation; skills are thin wrappers that parse arguments and invoke it. This avoids duplicating logic across runtimes and ensures the CLI, the Python API, and the agent skills all exercise the same code paths.

### A.3 Adapter Header Pattern

**Decision:** Adopt GSD's adapter header pattern (`<nines_cursor_adapter>`) for runtimes without native slash-command support.

**Rationale:** Cursor lacks native `$ARGUMENTS` support. The adapter header teaches the agent how to detect invocation, extract arguments, and map tools. This is proven at scale across 14+ runtimes in GSD. NineS narrows the scope to Cursor and Claude Code for the MVP, with the architecture supporting additional runtimes via new emitter classes.

### A.4 CLAUDE.md Markers

**Decision:** Use HTML comment markers (`<!-- nines:start -->` / `<!-- nines:end -->`) for the NineS section in `CLAUDE.md`.

**Rationale:** Clean install/uninstall requires knowing which content NineS owns. HTML comments are invisible in rendered markdown and provide unambiguous boundaries for automated removal without affecting user content.

### A.5 Single-Source Multi-Target

**Decision:** Commands are defined once in the manifest and Python templates, then emitted per-runtime by adapter classes.

**Rationale:** Direct adoption of GSD's core architecture pattern. Prevents content drift between runtimes and makes adding new runtime targets a matter of writing a new `SkillEmitter` subclass.

---

## Appendix B: Current and Future Runtime Support

NineS currently supports 4 agent runtimes:

| Runtime | Install Dir | Skill Format | Status |
|---|---|---|---|
| Cursor | `.cursor/skills/nines/` | SKILL.md + command workflows | Shipped |
| Claude Code | `.claude/commands/nines/` | Slash commands + CLAUDE.md | Shipped |
| Codex | `.codex/skills/nines/` | SKILL.md + command workflows | Shipped (v1.0.0-pre) |
| Copilot | `.github/copilot-instructions.md` | Single instructions file | Shipped (v1.0.0-pre) |

The adapter architecture is designed for extensibility. Adding a new runtime requires:

1. Add a new entry to `compatibility.runtimes` in the manifest schema.
2. Implement a `SkillEmitter` subclass (e.g., `WindsurfEmitter`).
3. Define tool name mapping for that runtime.
4. Create a command template with the appropriate adapter header.
5. Register the emitter in the installer's runtime registry.

Candidate runtimes for future support:

| Runtime | Install Dir | Skill Format | Priority |
|---|---|---|---|
| Windsurf | `.windsurf/skills/` | Markdown + adapter header | Medium |
| Augment | `.augment/skills/` | Markdown + adapter header | Low |
