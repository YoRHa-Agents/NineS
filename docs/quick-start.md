# Quick Start

<!-- auto-updated: version from src/nines/__init__.py -->

Get NineS up and running in 5 minutes. This guide walks through installation, your first evaluation, a collection run, and a code analysis.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.12+ | Check with `python --version` |
| [uv](https://docs.astral.sh/uv/) | Latest | Recommended package manager |
| Git | Any | For cloning the repository |

---

## Installation

The fastest way to get started is the one-click install script:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/NineS/main/scripts/install.sh | bash
```

Or install manually:

```bash
git clone https://github.com/YoRHa-Agents/NineS.git && cd NineS
uv sync
```

Verify the installation:

```bash
uv run nines --version
# nines, version {{ nines_version }}
```

For detailed installation options (pip, editable mode, from source), see the [Installation Guide](installation.md).

---

## Your First Evaluation

Create a task file `my_task.toml`:

```toml
[task]
id = "00000000-0000-0000-0000-000000000001"
name = "hello-world-check"
description = "Verify a simple greeting function"
dimension = "code_quality"
difficulty = 1

[task.input]
type = "code"
language = "python"
source = "def greet(name): return f'Hello, {name}!'"

[task.expected]
type = "text"
value = "Hello, World!"
```

Run the evaluation:

```bash
nines eval my_task.toml
```

Run with a specific scorer and output format:

```bash
nines eval my_task.toml --scorer composite --format markdown -o report.md
```

!!! tip "Sandboxed Execution"
    Add `--sandbox` to run evaluations in an isolated environment with its own virtual environment and temp directory, preventing any host pollution.

---

## Your First Collection

Search GitHub for repositories related to AI agent evaluation:

```bash
nines collect github "AI agent evaluation" --limit 10
```

Search arXiv for recent papers:

```bash
nines collect arxiv "LLM self-improvement" --limit 5
```

Use incremental mode to only fetch new items since the last run:

```bash
nines collect github "AI agent evaluation" --incremental --store ./data/collections
```

---

## Your First Analysis

Analyze a codebase (or NineS itself):

```bash
nines analyze ./src/nines --depth standard
```

Run a deep analysis with decomposition and knowledge indexing:

```bash
nines analyze ./src/nines --depth deep --decompose --index
```

Output a structured Markdown report:

```bash
nines analyze ./src/nines --output markdown -o analysis_report.md
```

---

## Set Up Agent Skills

Install NineS as an Agent Skill to enable AI assistants to use NineS directly from your IDE. NineS supports 4 runtimes: Cursor, Claude Code, Codex, and GitHub Copilot.

```bash
# Install for all supported runtimes at once
nines install --target all

# Or install for a specific runtime
nines install --target cursor
nines install --target claude
nines install --target codex
nines install --target copilot
```

!!! tip "One-Click Install"
    The `scripts/install.sh` script handles both package installation and skill setup in one step. Pass `--target <runtime>` to install for a specific runtime.

For full details on agent skill setup and verification, see the [Agent Skill Setup](agent-skill-setup.md) guide.

---

## Next Steps

| Goal | Resource |
|------|----------|
| Learn about all installation methods | [Installation Guide](installation.md) |
| Install NineS as an Agent Skill | [Agent Skill Setup](agent-skill-setup.md) |
| Deep-dive into evaluation workflows | [Evaluation Guide](user-guide/evaluation.md) |
| Understand the self-improvement loop | [Self-Iteration Guide](user-guide/self-iteration.md) |
| Explore the full CLI | [CLI Reference](user-guide/cli-reference.md) |
| Understand system architecture | [Architecture Overview](architecture/overview.md) |
