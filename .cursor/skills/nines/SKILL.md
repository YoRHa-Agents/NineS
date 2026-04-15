# NINES — Self-iterating agent toolflow for evaluation, information collection, and knowledge analysis.

## Available Commands

| Command | Description |
|---------|-------------|
| `nines-eval` | Run evaluation benchmarks on agent capabilities. |
| `nines-collect` | Search and collect information from configured sources. |
| `nines-analyze` | Analyze and decompose collected knowledge into structured units. Use `--strategy graph` for full knowledge graph with multi-language scanning, verification, and summary. |
| `nines-self-eval` | Run self-evaluation across all 24 capability dimensions. |
| `nines-iterate` | Execute a self-improvement iteration cycle. |
| `nines-install` | Install or uninstall NineS as an agent skill. |
| `nines-update` | Check for and install NineS updates, refresh skill files. |

## Prerequisites

The `nines` CLI binary must be on `$PATH`.
All commands delegate to `nines <subcommand>` via the Shell tool.

## v3.0.0 — Knowledge Graph Analysis

The `graph` decomposition strategy builds a complete knowledge graph:
- **Multi-language scanning** — 30+ languages, 7 file categories, framework detection
- **Cross-language import graph** — AST (Python) + regex (JS/TS/Go/Rust) dependency resolution
- **Typed knowledge graph** — 11 node types, 10 edge types, architecture layers
- **Graph verification** — Referential integrity, orphan detection, layer coverage
- **Analysis summary** — Fan-in/fan-out rankings, entry point detection, agent impact text
- **4 new self-eval dimensions** (D21-D24) — Graph coverage, verification, layer quality, summary completeness

```bash
nines analyze --target-path ./repo --strategy graph
```

## Reference Navigation Guide

NineS provides structured reference files in `references/` for domain
knowledge that agents can selectively load. Each reference has YAML
frontmatter with `triggers` — load a reference when the current task
matches its trigger phrases.

### Quick Reference Index

| When working on...                     | Load this reference                      |
|----------------------------------------|------------------------------------------|
| Analysis pipeline, decomposition       | `references/analysis-pipeline.md`        |
| Agent impact, mechanisms, artifacts    | `references/agent-impact-analysis.md`    |
| Key points, priority, deduplication    | `references/key-point-extraction.md`     |
| Eval tasks, scorers, benchmarks        | `references/evaluation-framework.md`     |
| Iteration cycle, gaps, convergence     | `references/iteration-protocol.md`       |
| Finding the right reference            | `references/index.md`                    |

### Loading Strategy

1. Read `references/index.md` first to identify which reference applies
2. Load only the most specific reference for the current task
3. Follow `dependencies` in the YAML frontmatter if upstream context is needed
4. Each reference includes source file mappings and feature requirement IDs
