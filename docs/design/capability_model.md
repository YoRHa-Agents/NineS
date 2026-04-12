# NineS Three-Vertex Capability Model

> **Task**: T07 — Three-Vertex Capability Model Definition | **Team**: Research L3
> **Input**: `docs/research/synthesis_report.md` (S01 consolidated findings)
> **Last Modified**: 2026-04-11

---

## 1. Model Overview

NineS is structured around three core capability vertices that form a self-reinforcing triangle. Each vertex is both a producer and consumer of data flowing through the system; improvement in any single vertex creates measurable uplift in the other two. The triangle closes a feedback loop that no existing tool provides: evaluation generates quality signals, information search discovers new targets and techniques, and knowledge analysis decomposes those targets into actionable units that feed back into evaluation tasks.

```
                    ┌─────────────────────────┐
                    │   V1: Evaluation &       │
                    │   Benchmarking            │
                    └────────┬───────┬─────────┘
                             │       │
              score gaps &   │       │  eval task
              improvement    │       │  definitions &
              priorities     │       │  scoring rubrics
                             │       │
                             ▼       │
        ┌────────────────────┐       │       ┌────────────────────┐
        │  V3: Knowledge     │       │       │  V2: Information   │
        │  Analysis &        │◄──────┘       │  Search &          │
        │  Decomposition     │               │  Tracking          │
        └────────┬───────────┘               └──────┬─────────────┘
                 │                                   │
                 │  analysis targets                  │
                 │  (new repos, papers,              │
                 │   techniques)                     │
                 │                                   │
                 └──────────────►─────────────────────┘
                   knowledge units &          discovered sources,
                   structural patterns  ◄──── changelogs, new
                   for eval rubrics           repos & papers
```

### Data Flow Summary

| Flow | From → To | Payload |
|------|-----------|---------|
| **F1** | V1 → V2 | Score gaps identify *what* to search for (e.g., "reliability scoring is weak → find new reliability benchmarks") |
| **F2** | V1 → V3 | Evaluation task definitions and scoring rubrics specify *what* to analyze in target code |
| **F3** | V2 → V3 | Newly discovered repositories, papers, and techniques become analysis targets |
| **F4** | V2 → V1 | Tracked benchmark releases, new evaluation methodologies, and leaderboard updates feed evaluation design |
| **F5** | V3 → V1 | Decomposed knowledge units generate new evaluation tasks; structural patterns inform scoring rubrics |
| **F6** | V3 → V2 | Knowledge gaps and abstraction holes identify new search queries and tracking targets |

---

## 2. Vertex 1: Evaluation & Benchmarking

Measures agent capability across multiple dimensions with statistical rigor. Absorbs EvoBench's trait-based pipeline architecture (Synthesis §3.1) and subsumes scoring methodologies from SWE-Bench, TAU-Bench, Claw-Eval, and VAKRA (Synthesis §3.1 external patterns).

### 2.1 Sub-Capabilities

#### SC1.1 — Task Definition & Management

Authoring, versioning, and organizing evaluation tasks with typed inputs, expected outputs, difficulty tiers, and metadata.

| Maturity | Description |
|----------|-------------|
| **L1** | Manual task creation as Python dataclasses with TOML serialization. Single difficulty level. Tasks stored as flat files. |
| **L2** | Task templates with parameterized variants. 5-tier difficulty scale (Synthesis §3.1 — VAKRA L1-L4 + extension). Tagging by capability dimension. |
| **L3** | Auto-curriculum generation from mastery data (Synthesis §3.5 — auto-curriculum). Task dependency graphs. Import adapters for SWE-Bench / HumanEval task formats. |
| **L4** | LLM-assisted task generation from knowledge units (V3 → V1 flow). Adversarial variant synthesis targeting detected weaknesses. Cross-vertex task linking. |
| **L5** | Fully autonomous task portfolio management: gap-driven generation, retirement of mastered tasks, difficulty re-calibration from population statistics. |

#### SC1.2 — Scoring Pipeline

Multi-stage scoring with programmatic-first evaluation and configurable judge fallbacks. Implements the waterfall judge pattern (programmatic → exact-match → fuzzy-match → LLM-judge → groundedness) from VAKRA.

| Maturity | Description |
|----------|-------------|
| **L1** | ExactScorer (binary match) and FuzzyScorer (token overlap / edit distance). Single score per task. |
| **L2** | RubricScorer (dimension-weighted checklist). CompositeScorer chaining with namespace-prefixed metrics (Synthesis §3.1 — EvoBench Pattern 5). Waterfall judge with 2 stages (programmatic + exact). |
| **L3** | Full waterfall judge (4 stages). LLM-as-judge with calibration. Collateral damage detection for side-effect evaluation (Synthesis §3.1 — AppWorld pattern). |
| **L4** | Adaptive scorer selection based on task type. Scorer performance meta-evaluation (measuring scorer accuracy against human labels). Custom scorer plugin registration. |
| **L5** | Self-tuning scorer weights. Scorer ensemble with disagreement detection. Automated scorer regression testing across versions. |

#### SC1.3 — Matrix Evaluation

Combinatorial evaluation across multiple axes (models × tools × workflows × task types × trials) with constraint-based explosion control.

| Maturity | Description |
|----------|-------------|
| **L1** | Single-axis evaluation (one model, one task set, fixed trial count). Manual configuration. |
| **L2** | 2-axis matrix (model × task type). `max_cells` cap. Basic Latin-square sampling for large matrices (Synthesis §3.1 — EvoBench matrix constraints). |
| **L3** | Full N-axis matrix with exclusion rules and pairwise coverage sampling. Budget guards with real-time cost tracking and `BudgetExceeded` early termination (Synthesis §3.1 — EvoBench Pattern 7). |
| **L4** | Adaptive IRT-based sampling to focus compute on informative cells. Incremental matrix expansion (add new axes without re-running existing cells). |
| **L5** | Autonomous matrix design: V2 discovers new models/tools → matrix auto-expands. Statistical power analysis determines minimum trial count per cell. |

#### SC1.4 — Reliability Metrics

Statistical measurement of result consistency beyond single-shot accuracy. Implements pass@k (optimistic), pass^k (pessimistic), and Pass³ (all-must-pass).

| Maturity | Description |
|----------|-------------|
| **L1** | Pass@1 (single-attempt accuracy). Mean and standard deviation across trials. |
| **L2** | pass@k with unbiased estimator. pass^k pessimistic reliability (Synthesis §3.1 — EvoBench Pattern 6). Trial count ≥ 3. |
| **L3** | Pass³ consistency metric (Synthesis §3.1 — Claw-Eval). Confidence intervals via bootstrap. Stability score (variance across N runs). |
| **L4** | Convergence-aware reliability: metric values are only reported after SPRT-based stability test passes (Synthesis §3.6 — adaptive SPRT). Trend detection via Mann-Kendall. |
| **L5** | Composite reliability index combining pass@k, pass^k, Pass³, and convergence rate. Reliability regression detection across versions. Automated re-test triggering on anomalous variance. |

#### SC1.5 — Report Generation

Structured output of evaluation results as human-readable reports and machine-readable artifacts for downstream consumption.

| Maturity | Description |
|----------|-------------|
| **L1** | JSON result dump with flat metric key-value pairs. Console summary output. |
| **L2** | Markdown report with per-dimension tables, pass/fail summary, and comparison against previous run. JSON output with defined schema. |
| **L3** | Multi-format reporting (Markdown + JSON + SQLite history). Axis-decomposed analysis (per-model, per-task-type breakdowns). Version-over-version trend tables. |
| **L4** | Narrative report generation (LLM-assisted summary of findings). Regression highlighting with root-cause hints from V3 analysis. Export to external leaderboard formats. |
| **L5** | Interactive dashboard (Synthesis §6.2 Q8). Automated insight extraction. Report customization via template DSL. Push notifications on significant score changes. |

#### SC1.6 — Evaluation Orchestration

End-to-end pipeline coordination from task loading through result storage, with sandbox integration and parallel execution support.

| Maturity | Description |
|----------|-------------|
| **L1** | Sequential single-task evaluation: load → execute in sandbox → score → store. Manual invocation via CLI. |
| **L2** | Batch evaluation with progress tracking. Sandbox pool reuse. Result caching to avoid redundant re-evaluation. |
| **L3** | Parallel evaluation with worker pool. Pipeline stage retry on transient failures. Budget-aware scheduling (pause when cost threshold approaches). |
| **L4** | Event-driven evaluation triggering (new code push → auto-eval). Incremental evaluation (only re-evaluate changed tasks). Priority queue based on V3 gap analysis. |
| **L5** | Fully autonomous evaluation scheduling: self-tuning parallelism, adaptive retry, cross-vertex priority arbitration (V2 discovery triggers V3 analysis triggers V1 evaluation). |

### 2.2 V1 Feeds Into Other Vertices

| Target | Data Flow | Mechanism |
|--------|-----------|-----------|
| **V2** (F1) | Score gaps and low-performing dimensions generate search queries. If "reliability" scores below threshold → V2 searches for new reliability benchmarks, papers on consistency testing, and repos implementing robust retry logic. | `GapAnalysis` artifact → `SearchQueryGenerator` → V2 `SourceProtocol.search()` |
| **V3** (F2) | Evaluation task definitions carry target code references and scoring rubrics. V3 receives these as analysis targets: "analyze this repo's error handling" or "decompose this function for complexity evaluation." | `EvalTask.target_ref` → V3 `AnalysisPipeline.ingest()` |
| **Self-iteration** | Evaluation scores feed the MAPIM loop's Measure phase. Version-over-version deltas trigger Analyze → Plan → Improve phases. | `ScoreHistory` → `SelfEvalRunner` → `GapDetector` |

---

## 3. Vertex 2: Information Search & Tracking

Discovers, collects, and monitors external information sources relevant to NineS's evaluation targets and knowledge base. Uses GitHub GraphQL API, arXiv API, and RSS feeds (Synthesis §3.3).

### 3.1 Sub-Capabilities

#### SC2.1 — Source Discovery

Finding relevant repositories, papers, blog posts, and benchmark releases across multiple platforms.

| Maturity | Description |
|----------|-------------|
| **L1** | Manual source registration (user provides repo URLs or search terms). GitHub REST API keyword search with basic filtering (stars, language). |
| **L2** | Multi-platform search: GitHub GraphQL (Synthesis §3.3 — single-request deep fetch), arXiv keyword search, RSS feed registration. Query templates for common patterns (e.g., "AI agent evaluation"). |
| **L3** | Gap-driven discovery: V1 score gaps and V3 knowledge holes automatically generate search queries. Deduplication across sources. Relevance ranking with configurable scoring. |
| **L4** | Citation-chain expansion: discover related repos via dependency graphs, related papers via citation networks. Community signal tracking (trending repos, highly-cited papers). |
| **L5** | Autonomous source portfolio management: continuous discovery, relevance decay detection, source retirement. Cross-platform identity linking (same project across GitHub, arXiv, blog). |

#### SC2.2 — Data Collection

Structured extraction of metadata and content from discovered sources with rate-limiting compliance.

| Maturity | Description |
|----------|-------------|
| **L1** | GitHub repo metadata (stars, forks, language, description). arXiv paper metadata (title, authors, abstract, categories). Synchronous collection with hardcoded rate limits. |
| **L2** | Deep collection: README content, directory structure, release history, commit frequency, contributor count. arXiv full-text PDF metadata. Token-bucket rate limiter with per-source calibration (Synthesis §3.3 — 30 req/min GitHub search, 1 req/3s arXiv). |
| **L3** | Adaptive rate limiting reading `x-ratelimit-remaining` headers. Content extraction (code snippets, configuration patterns, API signatures). Local caching with TTL to avoid redundant API calls. |
| **L4** | Bulk collection scheduling during off-peak hours. Parallel collection with per-source concurrency limits. Partial failure resilience (skip failed sources, report partial results). |
| **L5** | Intelligent collection prioritization: collect high-value sources first (based on V1/V3 demand signals). Streaming collection for large repositories. Incremental deep-dive triggered by relevance score. |

#### SC2.3 — Incremental Tracking

Monitoring previously collected sources for changes over time using bookmark/cursor-based state management.

| Maturity | Description |
|----------|-------------|
| **L1** | Manual re-collection with full refresh. Timestamp-based "last collected" bookmarks in SQLite. |
| **L2** | Cursor-based incremental collection: GitHub `since` parameter for commits, arXiv date-range queries. Bookmark state persisted per source in SQLite. Configurable refresh interval. |
| **L3** | Event-driven tracking: GitHub webhook registration (or polling simulation) for push/release/issue events. Differential state comparison (what changed since last collection). |
| **L4** | Priority-based tracking frequency: high-value sources polled more often. Adaptive interval based on source activity patterns (active repos tracked hourly, dormant repos weekly). |
| **L5** | Predictive tracking: anticipate likely change times from historical patterns. Zero-latency notification via streaming APIs where available. Cross-source correlation (paper published → check related repo for code release). |

#### SC2.4 — Change Detection & Diff Analysis

Identifying and categorizing changes between collection snapshots to determine significance and required downstream actions.

| Maturity | Description |
|----------|-------------|
| **L1** | Binary change detection: "source changed" vs. "no change" based on metadata comparison (star count, last commit date). |
| **L2** | Structured diff: new releases, new commits, README changes, dependency updates. Categorization by change type (breaking, feature, fix, docs). |
| **L3** | Semantic diff: detect API changes, new evaluation methodologies, scoring formula updates. Significance scoring (minor cosmetic vs. major architectural change). |
| **L4** | Impact analysis: map detected changes to affected V1 evaluation tasks and V3 knowledge units. Automated re-analysis triggering for high-impact changes. |
| **L5** | Trend detection across sources: identify emerging patterns (e.g., "3 repos adopted pass^k this month"). Anomaly detection (unexpected activity spikes, mass deprecation). |

#### SC2.5 — Summary Generation

Producing human-readable and machine-consumable summaries of collected information and detected changes.

| Maturity | Description |
|----------|-------------|
| **L1** | Tabular summary of collected sources: name, URL, last updated, key metrics. Plain-text change log. |
| **L2** | Categorized collection reports: new discoveries, significant changes, unchanged sources. Per-source detail pages with metadata history. |
| **L3** | Digest generation: periodic summaries (daily/weekly) of information landscape changes. Structured JSON output for V1 and V3 consumption. |
| **L4** | LLM-assisted narrative summaries: "This week, 3 new agent evaluation frameworks were released, with a trend toward reliability-first metrics." Actionable recommendations for V1/V3. |
| **L5** | Personalized briefings based on current V1 evaluation gaps and V3 knowledge needs. Interactive exploration of collected information graph. |

#### SC2.6 — Source Quality Assessment

Evaluating the reliability, relevance, and freshness of information sources to prioritize collection and tracking effort.

| Maturity | Description |
|----------|-------------|
| **L1** | Basic quality heuristics: star count, citation count, recency. Manual source quality tagging. |
| **L2** | Multi-signal quality scoring: activity frequency, community size, documentation quality, maintenance status (archived, abandoned, active). |
| **L3** | Relevance scoring against NineS's current capability gaps: "how useful is this source for improving V1 reliability metrics?" Cross-reference with V1 evaluation dimensions. |
| **L4** | Historical quality tracking: source quality trends over time. Early warning for quality degradation (maintainer departure, fork proliferation). |
| **L5** | Predictive quality model: forecast source value trajectory. Portfolio optimization (maximize information value per API call budget). |

### 3.2 V2 Feeds Into Other Vertices

| Target | Data Flow | Mechanism |
|--------|-----------|-----------|
| **V1** (F4) | Newly discovered benchmarks, evaluation methodologies, and leaderboard updates inform evaluation design. New tool/model releases trigger matrix expansion. | `CollectedSource[type=benchmark]` → V1 `TaskLoader.import_external()` |
| **V3** (F3) | Discovered repositories and papers become analysis targets. V3 receives repository URLs, paper content, and code snapshots for structural decomposition. | `CollectedSource[type=repo\|paper]` → V3 `AnalysisPipeline.ingest()` |
| **Self-iteration** | Collection coverage and freshness metrics feed the self-evaluation dimensions. Discovery rate tracks V2's own improvement. | `CollectionMetrics` → `SelfEvalRunner` |

---

## 4. Vertex 3: Knowledge Analysis & Decomposition

Analyzes codebases, papers, and technical artifacts to extract structured knowledge. Uses Python `ast` module for code analysis with heuristic-based architecture pattern detection (Synthesis §3.4).

### 4.1 Sub-Capabilities

#### SC3.1 — Code Review & Static Analysis

AST-based extraction of structural information from source code: functions, classes, imports, complexity metrics, and dependency relationships.

| Maturity | Description |
|----------|-------------|
| **L1** | Python `ast` module extraction: function/class/import enumeration. Basic cyclomatic complexity per function. Single-file analysis. |
| **L2** | Multi-file analysis with cross-file import resolution. Dependency adjacency list construction. Coupling metrics: afferent coupling (Ca), efferent coupling (Ce), instability index I = Ce/(Ca+Ce) (Synthesis §3.4). |
| **L3** | Pattern detection: decorator usage, Protocol/ABC implementations, common anti-patterns (god class, circular imports). Configurable rule engine for custom checks. |
| **L4** | Multi-language support via tree-sitter (Synthesis §6.1 Q4). Semantic analysis: variable flow tracking, type inference from usage patterns. Security-relevant pattern detection. |
| **L5** | LLM-augmented semantic understanding: "what does this function do?" Code quality scoring combining structural metrics and semantic analysis. Automated refactoring suggestions. |

#### SC3.2 — Structure Analysis

Repository-level structural understanding: directory layout, module boundaries, layer identification, and architectural pattern recognition.

| Maturity | Description |
|----------|-------------|
| **L1** | Directory tree enumeration. File type distribution. Basic module identification from `__init__.py` presence. |
| **L2** | Module dependency graph construction. Layer detection (presentation, business logic, data access) from directory naming heuristics. Package boundary identification. |
| **L3** | Multi-signal architecture pattern recognition with confidence scoring: MVC, hexagonal, layered, microservices, plugin/extension (Synthesis §3.4 — heuristic-based detection). Boundary violation detection. |
| **L4** | Cross-repository structural comparison: "repo A uses layered architecture, repo B uses hexagonal." Pattern frequency statistics across analyzed repositories. Evolution tracking (structural changes across versions). |
| **L5** | Architectural fitness function evaluation: does the actual structure match the intended architecture? Drift detection with automated alerts. Architecture-aware refactoring path generation. |

#### SC3.3 — Unit Decomposition

Breaking codebases into atomic knowledge units suitable for evaluation, indexing, and pattern abstraction.

| Maturity | Description |
|----------|-------------|
| **L1** | Function-level decomposition: each function/method → one knowledge unit with signature, body, docstring, and complexity score. |
| **L2** | Three decomposition strategies: functional (per-function/class), concern-based (error handling, logging, validation grouped across files), layer-based (per-architectural-layer) (Synthesis §3.4). Unit metadata includes dependencies and coupling. |
| **L3** | Semantic grouping: cluster related units by functionality even when spread across modules. Interface-implementation pairing. Test-to-source mapping. |
| **L4** | Hierarchical decomposition: units nest (function → class → module → package → system). Cross-cutting concern extraction (aspects that span multiple units). Configurable granularity control. |
| **L5** | Adaptive decomposition: granularity auto-adjusts based on downstream consumer needs (V1 evaluation tasks need fine-grained units, V2 summaries need coarse-grained units). |

#### SC3.4 — Pattern Abstraction

Extracting reusable patterns, idioms, and design decisions from concrete code into generalized knowledge.

| Maturity | Description |
|----------|-------------|
| **L1** | Frequency-based pattern detection: common function signatures, repeated import patterns, configuration structures. |
| **L2** | Design pattern recognition: factory, observer, strategy, adapter, decorator identified from structural signatures. Idiom detection: context managers, generator patterns, Protocol implementations. |
| **L3** | Cross-repository pattern mining: identify patterns that appear across multiple analyzed codebases. Pattern confidence scoring based on frequency and structural consistency. |
| **L4** | Pattern evolution tracking: how do patterns change across versions? Anti-pattern detection with severity scoring. Pattern recommendation: "based on your architecture, consider applying pattern X." |
| **L5** | Generative pattern synthesis: abstract new patterns from observed code that don't match known catalogs. Pattern effectiveness correlation with V1 evaluation scores. |

#### SC3.5 — Knowledge Indexing & Retrieval

Storing and querying decomposed knowledge units and abstracted patterns for efficient retrieval by V1 and V2.

| Maturity | Description |
|----------|-------------|
| **L1** | SQLite-backed flat index: knowledge units stored with metadata (source, type, complexity, timestamp). Keyword search over unit names and content. |
| **L2** | Structured index with faceted search: filter by language, pattern type, complexity range, architectural layer. Relationship edges (calls, imports, implements). |
| **L3** | Knowledge graph: units as nodes, relationships as typed edges. Graph queries ("find all implementations of Protocol X"). Similarity search across units. |
| **L4** | Semantic search: embedding-based retrieval for "find code similar to this pattern." Cross-modality search: find code from natural language description. Ranking by relevance to V1 evaluation context. |
| **L5** | Proactive knowledge surfacing: automatically suggest relevant knowledge units when V1 creates new evaluation tasks or V2 discovers new sources. Knowledge freshness tracking with staleness alerts. |

#### SC3.6 — Analysis Pipeline Orchestration

Coordinating the end-to-end analysis flow from raw source ingestion through indexed knowledge output, with incremental processing support.

| Maturity | Description |
|----------|-------------|
| **L1** | Sequential pipeline: ingest → parse → analyze → decompose → store. Manual invocation per target. Whole-repository re-analysis on each run. |
| **L2** | Batch analysis with progress reporting. File-level caching (skip unchanged files on re-analysis). Error isolation (single file failure doesn't abort pipeline). |
| **L3** | Incremental analysis: detect changed files via git diff, re-analyze only deltas. Pipeline stage retry on transient failures. Parallel file processing within stages. |
| **L4** | Event-driven triggering: V2 discovers new repo → automatic analysis queued. Priority scheduling based on V1 evaluation demand. Analysis result versioning for historical comparison. |
| **L5** | Autonomous pipeline management: self-tuning parallelism, adaptive depth (shallow scan for low-priority targets, deep analysis for high-value targets), cross-target deduplication. |

### 4.2 V3 Feeds Into Other Vertices

| Target | Data Flow | Mechanism |
|--------|-----------|-----------|
| **V1** (F5) | Decomposed knowledge units become evaluation task targets (e.g., "evaluate agent's ability to refactor this function"). Structural patterns inform scoring rubric design (e.g., complexity thresholds for "clean code" evaluation). | `KnowledgeUnit` → V1 `TaskDefinition.from_knowledge_unit()`. `AbstractedPattern` → V1 `RubricScorer.pattern_rules` |
| **V2** (F6) | Knowledge gaps (e.g., "no examples of hexagonal architecture in our knowledge base") generate targeted search queries. Abstraction holes (e.g., "insufficient data on error handling patterns") drive V2 source discovery. | `GapAnalysis.knowledge_gaps[]` → V2 `SourceDiscovery.search()` |
| **Self-iteration** | Analysis coverage, decomposition granularity, and pattern extraction rate feed self-evaluation dimensions. | `AnalysisMetrics` → `SelfEvalRunner` |

---

## 5. Mutual Reinforcement Model

### 5.1 Concrete Data Flow Cycles

The three vertices form three bilateral reinforcement loops and one trilateral cycle:

#### Loop A: V1 ↔ V2 (Evaluation–Search Loop)

```
V1 evaluation scores → GapAnalysis identifies weak dimensions
→ V2 searches for benchmarks/papers/repos addressing those weaknesses
→ V2 discovers new evaluation methodologies and benchmark tasks
→ V1 imports new tasks and updates scoring rubrics
→ V1 re-evaluates with richer task set → new gap analysis
```

**Concrete example**: V1 measures NineS's "reliability" dimension at 0.62 (below 0.80 target). GapAnalysis generates: `{dimension: "reliability", gap: 0.18, action: "search for reliability benchmarking techniques"}`. V2 discovers TAU-Bench's pass^k methodology and three repos implementing retry-aware evaluation. V1 integrates pass^k into its scoring pipeline and adds retry-based tasks. Next evaluation cycle measures reliability at 0.71.

#### Loop B: V2 ↔ V3 (Search–Analysis Loop)

```
V2 discovers new repositories and papers
→ V3 analyzes their code structure, extracts patterns, decomposes into knowledge units
→ V3 identifies knowledge gaps (areas with insufficient analyzed examples)
→ V2 targets those gaps with new search queries
→ V2 discovers additional sources filling knowledge gaps
→ V3 re-analyzes with broader corpus → richer pattern library
```

**Concrete example**: V2 discovers 5 new Python evaluation frameworks on GitHub. V3 analyzes them and extracts `ScorerProtocol` implementations, finding 3 use composite scoring and 2 use waterfall judging. V3's pattern library now has 8 scoring patterns but only 2 sandbox patterns — it signals this gap. V2 searches for "Python sandbox isolation evaluation" and discovers 4 repos with Docker-based and venv-based sandboxing. V3 analyzes these, expanding sandbox patterns to 6.

#### Loop C: V3 ↔ V1 (Analysis–Evaluation Loop)

```
V3 decomposes codebases into knowledge units with complexity/quality metrics
→ V1 generates evaluation tasks targeting those units (test agent ability to understand/modify them)
→ V1 scores reveal which code patterns agents handle well vs. poorly
→ V3 prioritizes deeper analysis of poorly-handled pattern categories
→ V3 produces finer-grained decomposition and richer pattern descriptions
→ V1 creates more targeted evaluation tasks → sharper capability measurement
```

**Concrete example**: V3 decomposes a codebase and identifies 15 functions with cyclomatic complexity > 10. V1 creates evaluation tasks: "refactor function X to reduce complexity." Agent scores 0.80 on simple refactoring but 0.35 on functions involving decorator chains. V3 responds by performing deeper analysis of decorator-heavy code, extracting 8 decorator patterns with difficulty annotations. V1 creates graduated decorator tasks (L1: simple, L2: chained, L3: parameterized, L4: class decorators, L5: metaclass interaction).

#### Trilateral Cycle: V2 → V3 → V1 → V2 (Full Triangle)

```
V2 discovers a new trending repo (e.g., a novel agent evaluation framework)
→ V3 analyzes the repo: extracts architecture, decomposes modules, identifies novel patterns
→ V1 uses analysis results to create evaluation tasks testing the novel patterns
→ V1 evaluation reveals gaps in NineS's own capabilities
→ V2 searches for resources to address those gaps
→ cycle repeats
```

### 5.2 Iteration Growth Path

Each improvement in one vertex triggers measurable improvement in the others. The growth path defines how this amplification works over successive iterations.

#### Phase 1: Foundation (L1–L2 across all vertices)

Each vertex operates independently with manual integration.

| Vertex | State | Feeds |
|--------|-------|-------|
| V1 | Basic eval tasks, ExactScorer + FuzzyScorer, single-axis evaluation | Score reports (JSON) available for manual review |
| V2 | GitHub + arXiv collection, manual source registration, basic bookmarks | Collected source list available as SQLite queries |
| V3 | Python AST analysis, function-level decomposition, keyword index | Knowledge units stored in SQLite with metadata |

**Growth trigger**: V1 scores establish first baseline → gaps are visible → humans manually query V2 for relevant sources → V3 analyzes them → V1 tasks expand.

#### Phase 2: Linked (L2–L3 across vertices)

Automated data flows connect vertices. Improvement in one vertex automatically creates work for others.

| Vertex | State | Automated Feeds |
|--------|-------|----------------|
| V1 | Matrix evaluation, composite scoring, reliability metrics (pass@k, pass^k) | `GapAnalysis` auto-generates V2 search queries |
| V2 | Multi-platform search, incremental tracking, structured change detection | `CollectedSource` events auto-queue V3 analysis |
| V3 | Multi-file analysis, 3 decomposition strategies, pattern detection | `KnowledgeUnit` creation auto-generates V1 task candidates |

**Growth trigger**: V2 discovers 10 new repos → V3 auto-analyzes them, producing 200 knowledge units → V1 auto-generates 50 evaluation tasks → V1 scores identify 3 weak dimensions → V2 auto-searches for those dimensions → cycle accelerates.

#### Phase 3: Adaptive (L3–L4 across vertices)

Vertices dynamically adjust their behavior based on signals from other vertices. The system self-optimizes resource allocation across the triangle.

| Vertex | State | Adaptive Behavior |
|--------|-------|-------------------|
| V1 | Adaptive scorer selection, IRT-based matrix sampling, auto-curriculum | Evaluation priorities driven by V3 gap analysis. Task difficulty calibrated from population data. |
| V2 | Gap-driven discovery, adaptive tracking frequency, quality assessment | Search queries and tracking priorities driven by V1 score gaps and V3 knowledge holes simultaneously. |
| V3 | Incremental analysis, cross-repo pattern mining, semantic search | Analysis depth driven by V1 demand signals. Pattern extraction targets driven by V2 discovery rate. |

**Growth trigger**: The system reaches a state where each vertex improvement is measurably correlated with improvements in the other two. Convergence detection (Synthesis §3.5) monitors inter-vertex correlation coefficients.

#### Phase 4: Autonomous (L4–L5 across vertices)

The triangle operates as a self-improving system with minimal human intervention. The MAPIM loop (Synthesis §3.5) governs the full cycle.

| Vertex | State | Autonomous Behavior |
|--------|-------|---------------------|
| V1 | Autonomous task portfolio management, self-tuning scorer weights | Generates, retires, and calibrates evaluation tasks based on mastery curves. |
| V2 | Predictive tracking, portfolio optimization, cross-source correlation | Anticipates information needs before V1/V3 signal them. Optimizes API budget allocation. |
| V3 | Adaptive decomposition, generative pattern synthesis, proactive knowledge surfacing | Auto-adjusts analysis granularity per consumer. Synthesizes new patterns from cross-repo observations. |

**Growth trigger**: Convergence detection identifies diminishing returns → system shifts focus to the vertex with the highest marginal improvement potential (max-gradient strategy). When all vertices converge, the system signals readiness for the next capability tier or external expansion (new data sources, new languages, new evaluation domains).

### 5.3 Reinforcement Metrics

To measure inter-vertex reinforcement, the system tracks:

| Metric | Definition | Target |
|--------|------------|--------|
| **Cross-vertex trigger rate** | Number of downstream actions triggered per vertex output (e.g., V2 discoveries → V3 analyses queued) | Increasing over iterations |
| **Gap closure velocity** | Time from gap identification (V1) to gap closure (V2 discovery + V3 analysis + V1 re-evaluation) | Decreasing over iterations |
| **Knowledge amplification factor** | Ratio of knowledge units produced (V3) to sources discovered (V2) | Increasing (richer extraction per source) |
| **Evaluation coverage growth** | Rate of new evaluation task generation from V3 knowledge units | Positive and accelerating until portfolio saturation |
| **Inter-vertex correlation** | Pearson correlation between vertex-level improvement scores across iterations | ≥ 0.5 (indicating mutual reinforcement, not independent drift) |

---

## 6. Capability Maturity Summary

The table below provides a consolidated view of all sub-capabilities across the three vertices with their maturity level definitions.

### 6.1 V1: Evaluation & Benchmarking — Maturity Overview

| Sub-Capability | L1 (Initial) | L2 (Repeatable) | L3 (Defined) | L4 (Managed) | L5 (Optimizing) |
|----------------|--------------|------------------|---------------|---------------|-------------------|
| SC1.1 Task Definition | Manual dataclass | Templates + tiers | Auto-curriculum | LLM-assisted gen | Autonomous portfolio |
| SC1.2 Scoring Pipeline | Exact + Fuzzy | Rubric + Composite | Waterfall judge | Adaptive selection | Self-tuning weights |
| SC1.3 Matrix Evaluation | Single-axis | 2-axis + cap | N-axis + budget | IRT sampling | Autonomous expansion |
| SC1.4 Reliability Metrics | Pass@1 + std | pass@k + pass^k | Pass³ + CI | SPRT stability | Composite index |
| SC1.5 Report Generation | JSON dump | Markdown + diff | Multi-format + trends | Narrative + regression | Dashboard + insights |
| SC1.6 Eval Orchestration | Sequential | Batch + cache | Parallel + budget | Event-driven | Autonomous scheduling |

### 6.2 V2: Information Search & Tracking — Maturity Overview

| Sub-Capability | L1 (Initial) | L2 (Repeatable) | L3 (Defined) | L4 (Managed) | L5 (Optimizing) |
|----------------|--------------|------------------|---------------|---------------|-------------------|
| SC2.1 Source Discovery | Manual + REST | Multi-platform | Gap-driven | Citation-chain | Autonomous portfolio |
| SC2.2 Data Collection | Basic metadata | Deep + rate limit | Adaptive + cache | Bulk + parallel | Prioritized + streaming |
| SC2.3 Incremental Tracking | Manual refresh | Cursor-based | Event-driven | Priority-based | Predictive |
| SC2.4 Change Detection | Binary changed | Structured diff | Semantic diff | Impact analysis | Trend + anomaly |
| SC2.5 Summary Generation | Tabular list | Categorized report | Periodic digest | LLM narrative | Personalized briefing |
| SC2.6 Source Quality | Star/citation | Multi-signal score | Relevance scoring | Quality trends | Predictive + portfolio opt |

### 6.3 V3: Knowledge Analysis & Decomposition — Maturity Overview

| Sub-Capability | L1 (Initial) | L2 (Repeatable) | L3 (Defined) | L4 (Managed) | L5 (Optimizing) |
|----------------|--------------|------------------|---------------|---------------|-------------------|
| SC3.1 Code Review | Single-file AST | Multi-file + coupling | Pattern detection | Multi-language | LLM-augmented |
| SC3.2 Structure Analysis | Directory tree | Module deps + layers | Architecture patterns | Cross-repo comparison | Fitness functions |
| SC3.3 Unit Decomposition | Function-level | 3 strategies | Semantic grouping | Hierarchical + cross-cut | Adaptive granularity |
| SC3.4 Pattern Abstraction | Frequency-based | Design pattern recog | Cross-repo mining | Evolution tracking | Generative synthesis |
| SC3.5 Knowledge Indexing | SQLite keyword | Faceted search | Knowledge graph | Semantic search | Proactive surfacing |
| SC3.6 Analysis Orchestration | Sequential | Batch + cache | Incremental + parallel | Event-driven | Autonomous management |

### 6.4 MVP Target Maturity

For MVP delivery, the target maturity per vertex is:

| Vertex | Target Range | Rationale |
|--------|-------------|-----------|
| V1: Evaluation | **L2** across all SCs, **L3** for SC1.2 (Scoring) and SC1.4 (Reliability) | Scoring and reliability are NineS's core differentiators (Synthesis §5.1); they need to exceed external benchmarks at launch. |
| V2: Information | **L2** across all SCs | MVP requires functional collection and tracking; advanced discovery and quality assessment are post-MVP. |
| V3: Analysis | **L2** across all SCs, **L3** for SC3.1 (Code Review) | AST-based analysis is the foundation for knowledge extraction; it must be robust at launch. |

---

## 7. Triangle Integrity Constraints

For the mutual reinforcement model to function, the following invariants must hold:

| ID | Constraint | Violation Consequence |
|----|-----------|----------------------|
| **C1** | Every V1 `GapAnalysis` must produce at least one actionable V2 search query OR one V3 analysis target. | Gap detected but never acted on → no improvement. |
| **C2** | Every V2 `CollectedSource` of type `repo` or `paper` must be queued for V3 analysis within the configured SLA (default: next analysis batch). | Discovery without analysis → information hoarding without knowledge creation. |
| **C3** | Every V3 `KnowledgeUnit` above a configurable quality threshold must be registered as a potential V1 evaluation task target. | Knowledge extracted but never evaluated → analysis without quality signal. |
| **C4** | Inter-vertex data flows must use typed artifacts stored in SQLite (not in-memory-only), ensuring auditability and replay. | In-memory-only flows break after restart; no historical tracking of reinforcement cycles. |
| **C5** | Each full triangle cycle (V1 → V2 → V3 → V1) must complete within a bounded iteration count (default: 10 iterations per MAPIM cycle) to prevent unbounded loops (Synthesis §3.5 — scope creep risk R04). | Unbounded iteration → resource exhaustion, oscillation without convergence. |

---

*Defines the capability foundation for NineS. Consumed by T08 (Self-Evaluation Spec), T10 (Requirements), and S03 (Architecture Design).*
*Last modified: 2026-04-11*
