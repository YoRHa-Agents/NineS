---
id: "nines/references/index"
version: "1.0.0"
purpose: >
  Catalog of all NineS reference files with descriptions and trigger
  conditions. Use this index to determine which reference to load for a
  given task.
triggers:
  - "reference index"
  - "which reference"
  - "list references"
tier: 1
token_estimate: 400
dependencies:
  - "nines/SKILL.md"
last_updated: "2026-04-14"
---

# NineS Reference Index

## Reference Catalog

| Reference | File | Triggers | Token Est. |
|-----------|------|----------|------------|
| Analysis Pipeline | `references/analysis-pipeline.md` | analysis, pipeline, decompose, review | ~2400 |
| Agent Impact Analysis | `references/agent-impact-analysis.md` | agent impact, mechanisms, economics, artifacts | ~2500 |
| Key-Point Extraction | `references/key-point-extraction.md` | key points, extraction, priority, dedup | ~2500 |
| Evaluation Framework | `references/evaluation-framework.md` | eval, benchmark, self-eval, scoring | ~1800 |
| Iteration Protocol | `references/iteration-protocol.md` | iterate, self-improve, gap, cycle | ~1800 |

## When to Load

- **Modifying the analysis pipeline or decomposition** → `analysis-pipeline.md`
- **Working on mechanism detection or artifact discovery** → `agent-impact-analysis.md`
- **Tuning key-point priority, dedup, or categories** → `key-point-extraction.md`
- **Adding scorers, tasks, or benchmark generators** → `evaluation-framework.md`
- **Changing the iteration cycle, gap detection, or convergence** → `iteration-protocol.md`

## Dependency Graph

```
  index.md
    |
    +-- analysis-pipeline.md
    |     +-- agent-impact-analysis.md
    |     |     +-- key-point-extraction.md
    |     |           +-- evaluation-framework.md
    |     |                 +-- iteration-protocol.md
    |     +-- (reviewer.py, decomposer.py, structure.py)
    |
    +-- SKILL.md (root dependency for all references)
```

## Loading Strategy

1. Start with the **index** to identify relevant references
2. Load the **most specific** reference for the current task
3. Follow `dependencies` in the frontmatter if upstream context is needed
4. Minimize token usage by loading only what the task requires
