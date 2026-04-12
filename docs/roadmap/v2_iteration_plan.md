# NineS v2 Iteration Roadmap

> **Date**: 2026-04-12 | **Baseline**: v1 (overall 0.8787) | **Status**: Planning

---

## 1. Capability Gap Analysis

Based on the MVP self-evaluation baseline (official v1, composite score **0.8787**), the following gaps are identified:

### 1.1 Dimension-Level Gaps

| Dimension | Current Score | Target (v1.1) | Target (v2.0) | Gap Severity |
|-----------|--------------|----------------|----------------|--------------|
| D06: Docstring Coverage | 0.588 (58.8%) | 0.80 | 0.90 | **High** — Lowest-scoring dimension; directly impacts maintainability |
| D01–D05: V1 Eval Dimensions | Placeholder (0.0) | Wired to live data | Calibrated | **Critical** — Self-eval evaluators produce zeros; not yet wired to live data |
| D06–D10: V2 Search Dimensions | Placeholder (0.0) | Wired to live data | Calibrated | **Critical** — Same as above |
| D11–D15: V3 Analysis Dimensions | Placeholder (0.0) | Wired to live data | Calibrated | **Critical** — Same as above |
| D16–D19: System-Wide Dimensions | Placeholder (0.0) | Wired to live data | Calibrated | **Critical** — Same as above |
| CLI Coverage | 46% | 70% | 85% | **Medium** — Lowest module-level coverage |

### 1.2 Structural Gaps

| Gap | Impact | Priority |
|-----|--------|----------|
| Self-eval evaluators produce placeholder zeros | Entire self-eval feedback loop is inert | P0 |
| No golden test set for D01 (Scoring Accuracy) | Cannot measure scoring accuracy | P0 |
| No reference codebases for D12/D13/D15 | Cannot measure analysis quality | P1 |
| No search benchmark queries for D14 | Cannot measure index recall | P1 |
| No canary entities for D07/D08 | Cannot measure tracking freshness | P2 |

### 1.3 Overall Assessment

The MVP achieves strong marks on infrastructure metrics (test count, coverage, module completeness, documentation) but the self-evaluation dimensions (D01–D19) are not yet connected to live data collection. The system can measure itself structurally but not functionally.

---

## 2. v1.1 Priorities (Near-Term: 2–4 weeks)

Focus: **Wire self-eval to live data; improve baseline documentation quality.**

### P0 — Must Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v1.1-01 | Wire V1 evaluators to live data | Implement `ScoringAccuracyEvaluator`, `EvalCoverageEvaluator`, `ReliabilityEvaluator`, `ReportQualityEvaluator`, `ScorerAgreementEvaluator` using golden test set and real `EvalRunner` execution | P0 | 3 days | Golden test set (v1.1-04) |
| v1.1-02 | Wire V2 evaluators to live data | Implement `SourceCoverageEvaluator`, `TrackingFreshnessEvaluator`, `ChangeDetectionRecallEvaluator`, `DataCompletenessEvaluator`, `CollectionThroughputEvaluator` using actual collector pipeline | P0 | 3 days | Canary entities (v1.1-05) |
| v1.1-03 | Wire V3 evaluators to live data | Implement `DecompositionCoverageEvaluator`, `AbstractionQualityEvaluator`, `CodeReviewAccuracyEvaluator`, `IndexRecallEvaluator`, `StructureRecognitionEvaluator` using reference codebases | P0 | 3 days | Reference codebases (v1.1-06) |
| v1.1-04 | Create golden test set | Curate 30+ evaluation tasks with known-correct scores across difficulty tiers (10 trivial, 10 moderate, 10 complex) in `data/golden_test_set/` | P0 | 2 days | None |

### P1 — Should Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v1.1-05 | Set up canary tracking entities | Configure 3–5 GitHub repos + 2–3 arXiv queries as change detection canaries | P1 | 1 day | None |
| v1.1-06 | Annotate reference codebases | Prepare 2–3 open-source Python projects with architectural annotations in `data/reference_codebases/` | P1 | 2 days | None |
| v1.1-07 | Improve docstring coverage to 80%+ | Add docstrings to the 207 undocumented functions (current: 166/373 documented) | P1 | 2 days | None |
| v1.1-08 | Create search benchmark queries | Curate 15+ benchmark queries with ground-truth `KnowledgeUnit` IDs for D14 | P1 | 1 day | v1.1-06 |
| v1.1-09 | Improve CLI test coverage | Add tests for CLI command paths (currently 46% coverage) to reach 70%+ | P1 | 2 days | None |
| v1.1-10 | Wire system-wide evaluators | Implement `PipelineLatencyEvaluator`, `SandboxIsolationEvaluator`, `ConvergenceRateEvaluator`, `CrossVertexSynergyEvaluator` | P1 | 2 days | v1.1-01 through v1.1-03 |

### P2 — Nice to Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v1.1-11 | Add more test patterns | Increase test count to 700+ with edge case tests and property-based tests | P2 | 3 days | None |
| v1.1-12 | Improve error messages | Audit and improve all `NinesError` subclass messages for clarity | P2 | 1 day | None |
| v1.1-13 | Add `nines dashboard` command | Simple terminal-based dashboard showing self-eval trends | P2 | 2 days | v1.1-10 |

**v1.1 Milestone Target**: Composite self-eval score fully data-driven; docstring coverage >= 80%; CLI coverage >= 70%.

---

## 3. v2.0 Priorities (Medium-Term: 1–3 months)

Focus: **LLM integration, expanded data sources, semantic capabilities, async pipeline.**

### P0 — Must Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v2.0-01 | LLM-as-judge scorer | Integrate LLM-based scoring (VAKRA waterfall pattern) as an optional scorer type. Support configurable model backends (OpenAI, Anthropic, local). Falls back to heuristic scorers on failure | P0 | 5 days | v1.1 complete |
| v2.0-02 | Async evaluation pipeline | Convert `EvalRunner` to async execution with `asyncio`. Support concurrent task evaluation with configurable parallelism. Maintain backward compatibility with sync callers | P0 | 5 days | v1.1 complete |
| v2.0-03 | Semantic search in knowledge index | Replace keyword-based search with embedding-based semantic search. Use sentence-transformers for local embeddings. Support hybrid (keyword + semantic) search | P0 | 5 days | v1.1-08 |

### P1 — Should Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v2.0-04 | HuggingFace data source | Add HuggingFace Hub collector for models, datasets, and spaces. Track trending items and new model releases | P1 | 3 days | v1.1 complete |
| v2.0-05 | Twitter/X data source | Add Twitter/X collector for AI research discussions. Requires API credentials management | P1 | 3 days | v1.1 complete |
| v2.0-06 | PyPI data source | Add PyPI collector for package release tracking, dependency analysis | P1 | 2 days | v1.1 complete |
| v2.0-07 | LLM-augmented code review | Use LLM for semantic-level code review findings (logic errors, design issues) beyond static analysis | P1 | 4 days | v2.0-01 |
| v2.0-08 | Docker-based sandbox (Tier 2) | Add optional Docker container isolation for higher security. Falls back to venv+subprocess when Docker unavailable | P1 | 4 days | None |
| v2.0-09 | Multi-scorer calibration | Automated scorer calibration using golden test set expansion and inter-scorer agreement optimization | P1 | 3 days | v2.0-01 |

### P2 — Nice to Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v2.0-10 | Web dashboard | HTML dashboard (inspired by EvoBench) for visualizing self-eval trends, dimension heatmaps, and convergence graphs | P2 | 5 days | v2.0-02 |
| v2.0-11 | Plugin system | Allow third-party scorers, collectors, and analyzers as pip-installable plugins | P2 | 4 days | None |
| v2.0-12 | GraphQL GitHub collector | Replace REST-based GitHub collection with GraphQL for better efficiency and richer data | P2 | 3 days | None |

**v2.0 Milestone Target**: LLM-integrated scoring; async pipeline; 3+ new data sources; semantic search operational; composite self-eval >= 0.92.

---

## 4. v3.0 Vision (Long-Term: 3–6 months)

Focus: **Full auto-curriculum, cross-project knowledge transfer, multi-language, CI/CD integration.**

### P0 — Must Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v3.0-01 | Full auto-curriculum | Automatically generate evaluation tasks based on detected capability gaps. Use LLM to create targeted exercises. Adaptive difficulty scaling based on performance history | P0 | 10 days | v2.0-01, v2.0-02 |
| v3.0-02 | CI/CD integration | GitHub Actions workflow for automated self-evaluation on PR and release. Regression detection as a merge gate. Badge generation for README | P0 | 5 days | v2.0-02 |

### P1 — Should Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v3.0-03 | Cross-project knowledge transfer | Share knowledge units and analysis patterns across multiple NineS-analyzed projects. Federated knowledge index | P1 | 8 days | v2.0-03 |
| v3.0-04 | Multi-language analysis | Extend AST analysis to TypeScript, Go, Rust via tree-sitter. Language-agnostic knowledge unit format | P1 | 10 days | None |
| v3.0-05 | Conference proceedings collector | Add collectors for NeurIPS, ICML, ACL proceedings. Track accepted papers and trending topics | P1 | 4 days | v2.0 data source pattern |
| v3.0-06 | Predictive convergence modeling | Use historical iteration data to predict remaining iterations to convergence. Adaptive step-size for improvement actions | P1 | 5 days | v2.0-02 |

### P2 — Nice to Have

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v3.0-07 | Multi-objective Pareto optimization | Track Pareto front across self-eval dimensions. Optimize for balanced improvement rather than single-metric maximization | P2 | 6 days | v3.0-06 |
| v3.0-08 | Community benchmark integration | Import/export SWE-Bench, HumanEval, and Claw-Eval task formats. Publish NineS results to community leaderboards | P2 | 5 days | v3.0-02 |
| v3.0-09 | Agent-to-agent evaluation | Enable NineS instances to evaluate each other. Cross-validation of scoring accuracy | P2 | 8 days | v3.0-01 |
| v3.0-10 | Adaptive dimension weighting | Meta-learning to optimize the composite score weighting formula based on observed improvement patterns | P2 | 5 days | v3.0-07 |

### P3 — Exploratory

| ID | Item | Description | Priority | Effort | Dependency |
|----|------|-------------|----------|--------|------------|
| v3.0-11 | Self-modifying evaluation | NineS proposes and applies changes to its own evaluation criteria based on meta-analysis | P3 | 10 days | v3.0-01 |
| v3.0-12 | Distributed evaluation | Distribute evaluation workloads across multiple machines for large-scale benchmarking | P3 | 8 days | v2.0-02, v2.0-08 |

**v3.0 Milestone Target**: Auto-curriculum functional; CI/CD integration live; multi-language analysis; composite self-eval >= 0.95.

---

## 5. Version Timeline

```
  2026-Q2 (Apr–Jun)          2026-Q3 (Jul–Sep)          2026-Q4 (Oct–Dec)
  ├── v1.1 ──────────┤       ├── v2.0 ──────────┤       ├── v3.0 ──────────┤
  │                   │       │                   │       │                   │
  │ Wire self-eval    │       │ LLM integration   │       │ Auto-curriculum   │
  │ Golden test set   │       │ Async pipeline     │       │ CI/CD integration │
  │ Docstring 80%+    │       │ Semantic search    │       │ Cross-project KT  │
  │ CLI coverage 70%+ │       │ New data sources   │       │ Multi-language     │
  │                   │       │ Docker sandbox     │       │ Pareto optim.     │
  └───────────────────┘       └───────────────────┘       └───────────────────┘
```

## 6. Success Metrics

| Version | Composite Target | Key Indicator |
|---------|-----------------|---------------|
| v1.0 (current) | 0.8787 | Infrastructure complete, self-eval placeholder |
| v1.1 | >= 0.85 (data-driven) | All 19 dimensions wired to live data |
| v2.0 | >= 0.92 | LLM scoring, semantic search, async pipeline |
| v3.0 | >= 0.95 | Auto-curriculum, CI/CD, multi-language |

## 7. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM API costs exceed budget | Medium | High | Local model fallbacks (Ollama); cost caps per evaluation run |
| External API rate limits block collection | Medium | Medium | Aggressive caching; GraphQL migration; rate limit backoff |
| Semantic search accuracy insufficient | Low | High | Hybrid search (keyword + semantic); tunable weights |
| Docker unavailable on target machines | Medium | Low | Graceful fallback to venv+subprocess (already implemented) |
| Auto-curriculum generates low-quality tasks | Medium | High | Human-in-the-loop validation gate; quality scoring of generated tasks |

---

*Last modified: 2026-04-12T00:00:00Z*
