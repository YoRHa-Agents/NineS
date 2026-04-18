---
id: "nines/references/index"
version: "1.1.0"
purpose: >
  Catalog of all NineS reference files with descriptions and trigger
  conditions. Use this index to determine which reference to load for a
  given task.
triggers:
  - "reference index"
  - "which reference"
  - "list references"
tier: 1
token_estimate: 500
dependencies:
  - "nines/SKILL.md"
last_updated: "2026-04-18"
---

# NineS Reference Index

## Reference Catalog

| Reference | File | Triggers | Token Est. |
|-----------|------|----------|------------|
| Analysis Pipeline | `references/analysis-pipeline.md` | analysis, pipeline, decompose, review | ~2400 |
| Agent Impact Analysis | `references/agent-impact-analysis.md` | agent impact, mechanisms, economics, artifacts | ~2500 |
| Key-Point Extraction | `references/key-point-extraction.md` | key points, extraction, priority, dedup | ~2500 |
| Evaluation Framework | `references/evaluation-framework.md` | eval, benchmark, self-eval, scoring, retry, budget | ~2000 |
| Iteration Protocol | `references/iteration-protocol.md` | iterate, self-improve, gap, cycle, paradigm | ~2000 |
| Cross-Artifact Audit (v2.2.0) | `references/cross-artifact-audit.md` | audit, consistency, gate, verifier, cross-artifact | ~1200 |
| Resilience Budgets (v2.2.0) | `references/resilience-budgets.md` | budget, timeout, retry, with_retry, cost, evaluator_budget, resilience | ~1200 |
| Project Identity (v2.2.0) | `references/project-identity.md` | fingerprint, project_id, identity, namespace, context_fingerprint, EvaluationContext | ~1200 |
| Derived Metrics (v2.2.0) | `references/derived-metrics.md` | metric, weighted, registry, formula_version, score, economics, derived | ~1200 |

## When to Load

- **Modifying the analysis pipeline or decomposition** → `analysis-pipeline.md`
- **Working on mechanism detection or artifact discovery** → `agent-impact-analysis.md`
- **Tuning key-point priority, dedup, or categories** → `key-point-extraction.md`
- **Adding scorers, tasks, or benchmark generators** → `evaluation-framework.md`
- **Changing the iteration cycle, gap detection, or convergence** → `iteration-protocol.md`
- **Adding a new analyzer output / building consistency checks / designing release-blocking gates over JSON** → `cross-artifact-audit.md`
- **Adding a new evaluator / wiring subprocess timeouts / integrating LLM judges / designing CI within wall-clock envelope** → `resilience-budgets.md`
- **Adding analyzers or evaluators that produce findings / wiring per-project context into evaluators** → `project-identity.md`
- **Adding a new score-like output / designing per-group weights / bumping a metric's `formula_version`** → `derived-metrics.md`

## Dependency Graph

```
  index.md
    |
    +-- analysis-pipeline.md
    |     +-- agent-impact-analysis.md
    |     |     +-- key-point-extraction.md
    |     |     |     +-- evaluation-framework.md
    |     |     |           +-- iteration-protocol.md
    |     |     |
    |     |     +-- project-identity.md (v2.2.0)
    |     |     +-- derived-metrics.md (v2.2.0)
    |     |
    |     +-- cross-artifact-audit.md (v2.2.0)
    |           +-- project-identity.md (v2.2.0)
    |
    +-- evaluation-framework.md
    |     +-- resilience-budgets.md (v2.2.0)
    |
    +-- iteration-protocol.md
    |     +-- resilience-budgets.md (v2.2.0)
    |     +-- (paradigm patterns section → 4 v2.2.0 docs)
    |
    +-- (reviewer.py, decomposer.py, structure.py, graph_canonicalizer.py)
```

## Loading Strategy

1. Start with the **index** to identify relevant references.
2. Load the **most specific** reference for the current task.
3. Follow `dependencies` in the frontmatter if upstream context is needed.
4. Minimize token usage by loading only what the task requires.
5. **For v2.2.0 paradigm-extension topics** (audits, budgets, identity,
   derived metrics), load both the legacy reference (e.g.
   `agent-impact-analysis.md`) and the v2.2.0 paradigm reference (e.g.
   `derived-metrics.md`) — the v2.2.0 docs codify *patterns*, while the
   legacy docs document the v3.0.0 *implementations* the patterns
   extend.
