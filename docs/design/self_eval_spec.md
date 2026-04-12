# NineS Self-Evaluation System Specification

> **Task**: T08 (Research Team L3) | **Generated**: 2026-04-11 | **Status**: Complete

This document defines the complete self-evaluation specification for NineS, covering all three capability vertices (V1 Evaluation, V2 Search, V3 Analysis) plus system-wide quality. It specifies 19 measurable dimensions, each with an executable measurement method, a baseline establishment plan, and extension points for future growth.

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Dimension Overview](#2-dimension-overview)
3. [V1 Evaluation Dimensions](#3-v1-evaluation-dimensions)
4. [V2 Search Dimensions](#4-v2-search-dimensions)
5. [V3 Analysis Dimensions](#5-v3-analysis-dimensions)
6. [System-Wide Dimensions](#6-system-wide-dimensions)
7. [MVP Baseline Collection Plan](#7-mvp-baseline-collection-plan)
8. [Output Formats](#8-output-formats)
9. [Convergence & Stability Framework](#9-convergence--stability-framework)
10. [Extension Roadmap](#10-extension-roadmap)

---

## 1. Design Principles

The self-evaluation system is guided by five principles drawn from the surveyed external frameworks and domain knowledge research:

| Principle | Source Inspiration | Application in NineS |
|-----------|-------------------|---------------------|
| **Reliability over single-shot** | Claw-Eval Pass³, TAU-Bench Pass^k | Every dimension is measured across multiple runs; single-run results are never authoritative |
| **Composite multi-metric** | Claw-Eval `safety × (0.8·completion + 0.2·robustness)` | Dimensions are aggregated via configurable weighted composition |
| **Progressive difficulty** | VAKRA L1–L4, SWE-Bench Lite→Pro | Baselines are tiered; dimensions have growth trajectories |
| **Automated collection** | HumanEval subprocess, SWE-Bench Docker | All measurements are fully automated with zero human intervention for MVP |
| **Statistical convergence** | Domain knowledge Area 3: composite convergence (sliding variance + relative improvement + Mann-Kendall + CUSUM) | Multi-round stability uses majority-vote convergence detection |

---

## 2. Dimension Overview

| ID | Name | Category | Improvement Direction |
|----|------|----------|----------------------|
| D01 | Scoring Accuracy | V1 Evaluation | Higher is better |
| D02 | Evaluation Coverage | V1 Evaluation | Higher is better |
| D03 | Reliability (Pass^k Consistency) | V1 Evaluation | Higher is better |
| D04 | Report Quality | V1 Evaluation | Higher is better |
| D05 | Scorer Agreement | V1 Evaluation | Higher is better |
| D06 | Source Coverage | V2 Search | Higher is better |
| D07 | Tracking Freshness | V2 Search | Lower is better |
| D08 | Change Detection Recall | V2 Search | Higher is better |
| D09 | Data Completeness | V2 Search | Higher is better |
| D10 | Collection Throughput | V2 Search | Higher is better |
| D11 | Decomposition Coverage | V3 Analysis | Higher is better |
| D12 | Abstraction Quality | V3 Analysis | Higher is better |
| D13 | Code Review Accuracy | V3 Analysis | Higher is better |
| D14 | Index Recall | V3 Analysis | Higher is better |
| D15 | Structure Recognition Rate | V3 Analysis | Higher is better |
| D16 | End-to-End Pipeline Latency | System-wide | Lower is better |
| D17 | Sandbox Isolation Effectiveness | System-wide | Higher is better |
| D18 | Self-Iteration Convergence Rate | System-wide | Higher is better |
| D19 | Cross-Vertex Synergy Score | System-wide | Higher is better |

---

## 3. V1 Evaluation Dimensions

### D01: Scoring Accuracy

| Field | Specification |
|-------|--------------|
| **Name** | Scoring Accuracy |
| **Category** | V1 Evaluation |
| **Metric** | Agreement rate between NineS-assigned scores and ground-truth labels on a curated golden test set, expressed as a fraction in [0.0, 1.0]. |
| **Measurement Method** | 1. Maintain a golden test set of ≥30 evaluation tasks with known-correct scores (manually verified). 2. Run `EvalRunner` on each task using the configured scorer pipeline. 3. Compare output `ScoreCard` against golden labels. 4. Compute: `accuracy = count(|nines_score - golden_score| ≤ tolerance) / total_tasks` where `tolerance = 0.05` for continuous scores or exact match for binary pass/fail. |
| **Data Source** | `data/golden_test_set/` — curated evaluation tasks with `expected_score` fields; `EvalRunner` output. |
| **Baseline Establishment** | Populate golden test set with 30 tasks across difficulty tiers (10 trivial, 10 moderate, 10 complex). Run each task 3 times. Record mean accuracy across runs as v1 baseline. For MVP, golden tasks are manually constructed from known code snippets with deterministic expected outputs. |
| **Improvement Direction** | Higher is better (target: ≥0.90 for MVP, ≥0.95 for v2). |
| **Guiding Significance** | Scoring accuracy is the foundation of NineS's credibility. A drop below baseline indicates scorer regression — investigate scorer logic changes, task format drift, or execution environment inconsistencies. A sustained increase signals improved scorer calibration and should trigger expansion of the golden test set to harder tasks to avoid ceiling effects. |
| **Extension Points** | (1) Add LLM-as-judge agreement as a secondary check (VAKRA waterfall pattern). (2) Stratify accuracy by task difficulty tier. (3) Introduce human-in-the-loop verification for disputed scores. (4) Track per-scorer-type accuracy (exact, fuzzy, rubric, composite). |

### D02: Evaluation Coverage

| Field | Specification |
|-------|--------------|
| **Name** | Evaluation Coverage |
| **Category** | V1 Evaluation |
| **Metric** | Fraction of defined task types that NineS can load, execute, and score, expressed as `covered_types / total_defined_types`. |
| **Measurement Method** | 1. Enumerate all task types declared in `TaskDefinition` schema (e.g., code-correctness, code-review, structure-analysis, knowledge-extraction). 2. For each type, attempt to load a representative task, execute it in the sandbox, and produce a score. 3. A type is "covered" if all three stages (load, execute, score) succeed without errors. 4. Compute: `coverage = successful_types / total_types`. |
| **Data Source** | `TaskDefinition` schema registry; `EvalRunner` execution logs per type. |
| **Baseline Establishment** | In MVP, define the initial set of task types from the capability model (minimum 4: code-correctness, code-review-quality, structure-recognition, knowledge-decomposition). Run coverage check. Expected MVP baseline: 1.0 (all defined types are supported by definition). |
| **Improvement Direction** | Higher is better (maintain 1.0 as new types are added). |
| **Guiding Significance** | Coverage dropping below 1.0 after adding new task types signals implementation gaps. This metric drives task-type prioritization — uncovered types become top-priority implementation targets. Sustained 1.0 with an increasing type count demonstrates healthy feature growth. |
| **Extension Points** | (1) Weight coverage by type usage frequency. (2) Track partial coverage (load-only, execute-only). (3) Add cross-language coverage (Python → multi-language). (4) Measure coverage of external benchmark formats (SWE-Bench JSONL, Claw-Eval scenarios). |

### D03: Reliability (Pass^k Consistency)

| Field | Specification |
|-------|--------------|
| **Name** | Reliability (Pass^k Consistency) |
| **Category** | V1 Evaluation |
| **Metric** | The fraction of tasks that produce the same pass/fail result across k independent runs, computed as Pass^k: `P(pass on all k trials)`. Default k=3 for MVP. |
| **Measurement Method** | 1. Select a representative task subset (≥20 tasks). 2. For each task, execute k=3 independent evaluation runs in fresh sandboxes with identical seed configuration. 3. Compute per-task consistency: `1` if all k runs agree (all-pass or all-fail), `0` otherwise. 4. Aggregate: `pass_k_consistency = consistent_tasks / total_tasks`. 5. Additionally compute the `StabilityReport` per task using output fingerprinting (sha256 of stdout+stderr+exit_code). |
| **Data Source** | `SandboxManager` multi-run results; `result_fingerprint` output; `StabilityReport` from the multi-round stability test framework (domain_knowledge.md §4.6). |
| **Baseline Establishment** | Run the full golden test set 3× each. Compute Pass^3. For deterministic tasks (no randomness in evaluation script), target baseline of 1.0. For tasks with inherent non-determinism, record the natural floor and set target as ≥0.90. Use the adaptive stability test (SPRT with Wilson confidence bounds) to determine minimum necessary run count. |
| **Improvement Direction** | Higher is better (target: Pass^3 ≥0.95 for MVP). |
| **Guiding Significance** | This metric, inspired by Claw-Eval's Pass³ and TAU-Bench's Pass^k, measures deployment reliability. A Pass^3 < 0.95 indicates non-determinism in the evaluation pipeline — investigate seed control, sandbox state leakage, or flaky test oracles. Tracking Pass^k for increasing k reveals the reliability decay curve, which predicts failure rates at scale. |
| **Extension Points** | (1) Increase k to 5 or 8 for stricter reliability assessment. (2) Generate reliability decay curves (Pass^1 → Pass^k). (3) Stratify by task difficulty. (4) Implement the full adaptive SPRT stopping criterion from domain_knowledge.md §4.6. |

### D04: Report Quality

| Field | Specification |
|-------|--------------|
| **Name** | Report Quality |
| **Category** | V1 Evaluation |
| **Metric** | Completeness score of generated evaluation reports, measured as the fraction of required report sections that are present and non-empty. |
| **Measurement Method** | 1. Define a report schema specifying required sections: `[summary, task_results, per_dimension_scores, statistical_summary, recommendations, metadata]`. 2. After each evaluation run, parse the `MarkdownReporter` and `JSONReporter` output. 3. Check each required section for (a) presence and (b) minimum content (non-empty, >10 chars for text sections, >0 entries for list sections). 4. Compute: `quality = present_valid_sections / total_required_sections`. |
| **Data Source** | `MarkdownReporter` output (`.md` files); `JSONReporter` output (`.json` files); report schema definition. |
| **Baseline Establishment** | Generate reports for the full golden test set. Parse and validate against the schema. MVP baseline: 1.0 (all sections present) since the report template is controlled. |
| **Improvement Direction** | Higher is better (maintain 1.0). |
| **Guiding Significance** | A drop below 1.0 signals a regression in the reporting module — a section was removed, a formatter broke, or a data source for a section was lost. This metric acts as a canary for reporter health. Consistent 1.0 with increasing section count demonstrates growing report richness. |
| **Extension Points** | (1) Add content quality scoring via LLM-based readability check. (2) Measure report utility via downstream consumption (do users/agents act on the report?). (3) Add visual report quality (chart generation accuracy). (4) Compare report quality across output formats (Markdown vs JSON vs HTML). |

### D05: Scorer Agreement

| Field | Specification |
|-------|--------------|
| **Name** | Scorer Agreement |
| **Category** | V1 Evaluation |
| **Metric** | Pairwise agreement rate among different scorer implementations on the same task outputs, measured as Cohen's kappa (κ) or Pearson correlation coefficient. |
| **Measurement Method** | 1. Select ≥20 task outputs that can be scored by multiple scorers (e.g., ExactScorer + FuzzyScorer, or CompositeScorer sub-scorer pairs). 2. Score each output with all applicable scorers. 3. For binary scorers: compute Cohen's κ for each pair. 4. For continuous scorers: compute Pearson r for each pair. 5. Aggregate: mean pairwise agreement across all scorer pairs. |
| **Data Source** | `EvalRunner` with multiple scorer configurations on the same task set; scorer output pairs. |
| **Baseline Establishment** | Run multi-scorer evaluation on the golden test set. Record pairwise κ/r for each scorer pair. Expect MVP baseline: κ ≥ 0.70 (substantial agreement) between ExactScorer and CompositeScorer; r ≥ 0.80 between FuzzyScorer and CompositeScorer. |
| **Improvement Direction** | Higher is better (target: κ ≥ 0.80 for v2). |
| **Guiding Significance** | Low scorer agreement indicates that the scorers are measuring different constructs or that one scorer is miscalibrated. Action: investigate divergent cases, recalibrate scorer parameters, or document legitimate scoring divergence. High agreement validates that the scoring system is internally consistent. |
| **Extension Points** | (1) Add Krippendorff's alpha for multi-scorer agreement. (2) Track agreement trends over time. (3) Introduce scorer calibration datasets. (4) Add LLM-judge agreement as a cross-validation method (VAKRA waterfall pattern). |

---

## 4. V2 Search Dimensions

### D06: Source Coverage

| Field | Specification |
|-------|--------------|
| **Name** | Source Coverage |
| **Category** | V2 Search |
| **Metric** | Fraction of configured data sources that are reachable and returning data, expressed as `active_sources / configured_sources`. |
| **Measurement Method** | 1. Enumerate all configured sources from `NinesConfig` (e.g., GitHub REST, GitHub GraphQL, arXiv API, RSS feeds). 2. For each source, execute a lightweight health-check query (e.g., search for a known-existing repository, fetch a known arXiv paper). 3. A source is "active" if the health check returns ≥1 result within the timeout. 4. Compute: `coverage = active_sources / configured_sources`. |
| **Data Source** | `NinesConfig` source registry; `SourceProtocol.health_check()` results; HTTP response status codes and latencies. |
| **Baseline Establishment** | Configure MVP sources (GitHub REST, GitHub GraphQL, arXiv, ≥2 RSS feeds). Run health check for each. Expected MVP baseline: 1.0 (all sources healthy). Record per-source response times as secondary baseline. |
| **Improvement Direction** | Higher is better (maintain 1.0; grow configured source count). |
| **Guiding Significance** | Source coverage < 1.0 means a data source is down, misconfigured, or rate-limited. Action: check API credentials, rate limiter state, network connectivity. Tracking this over time reveals source reliability patterns (e.g., arXiv downtime windows). |
| **Extension Points** | (1) Add source quality scoring (data freshness, completeness per source). (2) Track source-specific rate limit utilization. (3) Add new source types (PyPI, Hugging Face, conference proceedings). (4) Weight sources by information value. |

### D07: Tracking Freshness

| Field | Specification |
|-------|--------------|
| **Name** | Tracking Freshness |
| **Category** | V2 Search |
| **Metric** | Median time lag (in minutes) between a change occurring in a tracked source and NineS detecting that change. |
| **Measurement Method** | 1. Maintain a set of "canary" tracked entities (e.g., a test repository with known commit schedule, a known arXiv daily posting). 2. Record the timestamp of the actual change (e.g., GitHub push event timestamp, arXiv publication time). 3. Record the timestamp when NineS's `ChangeDetector` first reports the change. 4. Compute per-entity lag: `detection_time - change_time`. 5. Report: median lag across all canary entities over the measurement window. |
| **Data Source** | Canary entity commit/publish timestamps (from source APIs); `ChangeDetector` detection logs with timestamps; `DataStore` ingestion timestamps. |
| **Baseline Establishment** | Set up 3–5 canary entities. Trigger known changes (push a commit, wait for arXiv daily update). Run the collector cycle and record detection lag. MVP baseline: dependent on collection schedule (if hourly, expect median lag ~30–60 min). |
| **Improvement Direction** | Lower is better (target: ≤60 min for MVP, ≤15 min for v2). |
| **Guiding Significance** | High lag means the collection schedule is too infrequent or the change detection algorithm is slow. Action: increase collection frequency, optimize diff computation, or add event-driven collection (webhooks). A decreasing trend confirms that scheduling and detection optimizations are effective. |
| **Extension Points** | (1) Stratify by source type (GitHub vs arXiv vs RSS). (2) Add event-driven collection (GitHub webhooks) and measure push-based lag. (3) Track p95 and p99 lag in addition to median. (4) Implement freshness SLA monitoring with alerting. |

### D08: Change Detection Recall

| Field | Specification |
|-------|--------------|
| **Name** | Change Detection Recall |
| **Category** | V2 Search |
| **Metric** | Fraction of actual changes in tracked entities that are correctly detected by NineS, expressed as `detected_changes / total_actual_changes`. |
| **Measurement Method** | 1. Prepare a ground-truth change log for canary entities over a measurement window (e.g., 7 days). Include: new commits, new releases, README updates, new papers matching tracked queries. 2. Run NineS collection + change detection over the same window. 3. Match NineS-detected changes against the ground-truth log. 4. Compute: `recall = true_positives / (true_positives + false_negatives)`. 5. Also compute precision: `true_positives / (true_positives + false_positives)` for context. |
| **Data Source** | Ground-truth change log (manually curated or from API audit trail); `ChangeDetector` output; `DiffAnalyzer` reports. |
| **Baseline Establishment** | Track 3–5 repositories and 2–3 arXiv queries for 7 days. Manually compile the ground-truth change log (use GitHub event API and arXiv listing to enumerate actual changes). Run NineS and compare. Expected MVP baseline: recall ≥ 0.85 for commits, ≥ 0.90 for releases. |
| **Improvement Direction** | Higher is better (target: ≥0.95 recall for v2). |
| **Guiding Significance** | Recall below baseline means NineS is missing real changes. Root cause investigation: pagination issues, rate limit throttling causing skipped checks, bookmark cursor errors, or query scope too narrow. Tracking recall alongside precision prevents recall inflation via over-detection. |
| **Extension Points** | (1) Separate recall metrics per change type (commit, release, paper, README). (2) Add change-severity-weighted recall (missing a major release is worse than missing a minor commit). (3) Introduce F1 score combining recall and precision. (4) Automated ground-truth generation via shadow collector. |

### D09: Data Completeness

| Field | Specification |
|-------|--------------|
| **Name** | Data Completeness |
| **Category** | V2 Search |
| **Metric** | Fraction of expected data fields that are populated (non-null, non-empty) in collected entities, averaged across all entities. |
| **Measurement Method** | 1. Define the full field schema for each entity type (Repository: name, description, stars, forks, language, topics, README, recent_commits, releases; Paper: title, authors, abstract, categories, published_date, pdf_url). 2. Query all entities from `DataStore`. 3. Per entity: `completeness = populated_fields / total_fields`. 4. Aggregate: mean completeness across all entities. |
| **Data Source** | `DataStore` (SQLite); entity model schemas from `src/nines/collector/models.py`. |
| **Baseline Establishment** | After initial MVP collection run, compute completeness across all stored entities. Some fields (e.g., README for repos without one, pdf_url for arXiv papers with withdrawn PDFs) may be legitimately empty — exclude these from the denominator via a `nullable` field annotation. Expected MVP baseline: ≥0.90. |
| **Improvement Direction** | Higher is better (target: ≥0.95 for v2). |
| **Guiding Significance** | Low completeness indicates collector bugs (fields not extracted), API response changes, or schema drift. Action: audit collector extraction logic per field, check API version compatibility. Track completeness per field to identify systematically missing data. |
| **Extension Points** | (1) Per-field completeness tracking with heatmap visualization. (2) Data quality scoring beyond presence (format validation, value range checks). (3) Cross-source completeness comparison (GitHub REST vs GraphQL for the same entity). (4) Staleness detection (populated but outdated fields). |

### D10: Collection Throughput

| Field | Specification |
|-------|--------------|
| **Name** | Collection Throughput |
| **Category** | V2 Search |
| **Metric** | Number of data entities successfully collected per minute, measured per source and aggregated. |
| **Measurement Method** | 1. Instrument the collector pipeline with timing telemetry. 2. During a collection run, record: `start_time`, `end_time`, `entities_collected` per source. 3. Compute per-source throughput: `entities / duration_minutes`. 4. Aggregate: weighted average across sources (weighted by expected entity volume). |
| **Data Source** | Collector timing instrumentation; `MetricCollector` output; rate limiter utilization stats. |
| **Baseline Establishment** | Run a full collection cycle (all sources, all tracked queries). Record entities collected and wall-clock time. Decompose by source. Expected MVP baseline: dependent on rate limits (GitHub REST: ~50/min for core API, ~30/min for search; arXiv: ~20/min respecting 3s delay; RSS: ~100/min). |
| **Improvement Direction** | Higher is better (within rate limits). |
| **Guiding Significance** | Throughput degradation indicates rate limit saturation, network issues, or collector inefficiency. Action: optimize batch queries (use GraphQL instead of REST), increase parallelism for independent sources, review rate limiter configuration. Throughput exceeding rate limits may indicate broken rate limiting — investigate immediately. |
| **Extension Points** | (1) Track throughput efficiency: entities per API call. (2) Add cost-per-entity metric (for paid APIs). (3) GraphQL point consumption tracking. (4) Adaptive collection scheduling based on throughput trends. |

---

## 5. V3 Analysis Dimensions

### D11: Decomposition Coverage

| Field | Specification |
|-------|--------------|
| **Name** | Decomposition Coverage |
| **Category** | V3 Analysis |
| **Metric** | Fraction of analyzable code elements (functions, classes, modules) that are captured as `KnowledgeUnit` instances by the decomposer, expressed as `decomposed_elements / total_analyzable_elements`. |
| **Measurement Method** | 1. Select a reference codebase (or the NineS codebase itself). 2. Run the AST-based `CodeExtractor` to enumerate all functions, classes, and modules. 3. Run the `Decomposer` (functional, concern-based, and layer-based strategies). 4. Count total unique code elements from the extractor; count unique elements captured by at least one decomposition strategy. 5. Compute: `coverage = captured / total`. |
| **Data Source** | `CodeExtractor` output (function/class/module counts); `Decomposer` output (`KnowledgeUnit` lists); reference codebase files. |
| **Baseline Establishment** | Run decomposition on the NineS `src/nines/` codebase itself (self-referential baseline). Record counts per strategy. Expected MVP baseline: ≥0.85 (functional decomposition should capture most functions/classes; some dynamically generated code or metaprogramming may be missed). |
| **Improvement Direction** | Higher is better (target: ≥0.95 for v2). |
| **Guiding Significance** | Coverage below baseline means the decomposer is missing code elements. Root causes: unsupported syntax patterns, AST parse errors, or overly restrictive filtering. Track coverage per decomposition strategy to identify which strategy has gaps. |
| **Extension Points** | (1) Multi-language decomposition coverage (TypeScript, Go, Rust via tree-sitter). (2) Coverage weighted by element complexity (missing a complex class is worse than missing a simple function). (3) Cross-strategy coverage overlap analysis. (4) Dynamic analysis coverage (runtime-generated code). |

### D12: Abstraction Quality

| Field | Specification |
|-------|--------------|
| **Name** | Abstraction Quality |
| **Category** | V3 Analysis |
| **Metric** | Accuracy of abstracted patterns compared to human-annotated architectural labels on a reference codebase, measured as classification F1 score. |
| **Measurement Method** | 1. Prepare a reference codebase with human-annotated labels: each module/file tagged with its architectural role (e.g., "presentation", "domain", "infrastructure", "testing") and patterns (e.g., "MVC", "Hexagonal"). 2. Run `AbstractionLayer` and `detect_architecture_patterns()` on the reference codebase. 3. Compare NineS-assigned labels against human annotations. 4. Compute: per-label precision, recall, and F1. Report macro-averaged F1. |
| **Data Source** | Reference codebase with annotations in `data/reference_codebases/`; `AbstractionLayer` output; `detect_architecture_patterns()` output. |
| **Baseline Establishment** | Annotate 2–3 open-source Python projects (one MVC, one layered, one flat/simple) with ground-truth architectural labels. Run NineS analysis. Compute F1. Expected MVP baseline: macro F1 ≥ 0.60 (heuristic-based detection has inherent limitations). |
| **Improvement Direction** | Higher is better (target: F1 ≥ 0.75 for v2). |
| **Guiding Significance** | Low F1 indicates that the abstraction heuristics are misclassifying code. Investigate per-label precision/recall to identify which architectural patterns or layers are hardest to detect. Use errors to refine `LAYER_INDICATORS` and `ArchitectureSignal` detection rules. |
| **Extension Points** | (1) Add ML-based pattern classification (train on annotated codebases). (2) Include design pattern detection (Singleton, Observer, Strategy). (3) Measure abstraction stability across code versions. (4) Support architectural drift detection. |

### D13: Code Review Accuracy

| Field | Specification |
|-------|--------------|
| **Name** | Code Review Accuracy |
| **Category** | V3 Analysis |
| **Metric** | Precision and recall of code review findings against human-annotated known-issue lists on reference codebases. Report F1 score. |
| **Measurement Method** | 1. Prepare reference code files with intentionally inserted issues: high cyclomatic complexity, missing docstrings, coupling violations, naming convention issues, and genuine bugs. Annotate each issue with location and type. 2. Run `CodeReviewer` on the reference files. 3. Match NineS findings against the annotation list. A finding matches if it identifies the correct file, line range (±3 lines), and issue category. 4. Compute: precision, recall, F1. |
| **Data Source** | Annotated reference code in `data/review_test_set/`; `CodeReviewer` output (`Finding` objects); annotation schema. |
| **Baseline Establishment** | Create 5–10 reference files with 3–5 annotated issues each (total ≥30 issues across categories). Run CodeReviewer. Expected MVP baseline: F1 ≥ 0.70. Precision may be higher than recall for MVP since the reviewer uses conservative heuristics. |
| **Improvement Direction** | Higher is better (target: F1 ≥ 0.85 for v2). |
| **Guiding Significance** | Low precision means the reviewer produces too many false positives (noisy findings). Low recall means it misses real issues. Action: for low precision, tighten detection thresholds; for low recall, add new detection rules or lower thresholds. Track per-category F1 to focus improvement on the weakest categories. |
| **Extension Points** | (1) Security-focused review rules (SQL injection, path traversal patterns). (2) Style-guide compliance checking (PEP 8 beyond what ruff catches). (3) Severity-weighted F1 (missing a critical bug is worse than missing a style issue). (4) LLM-augmented review for semantic-level findings. |

### D14: Index Recall

| Field | Specification |
|-------|--------------|
| **Name** | Index Recall |
| **Category** | V3 Analysis |
| **Metric** | Fraction of relevant `KnowledgeUnit` instances returned by the search engine for a set of benchmark queries, measured as Recall@k (k=10). |
| **Measurement Method** | 1. Prepare ≥15 benchmark search queries with ground-truth relevant `KnowledgeUnit` IDs (manually curated after running decomposition on a reference codebase). 2. Execute each query via `SearchEngine`. 3. Check whether the ground-truth units appear in the top-k results. 4. Compute per-query recall@k: `relevant_in_top_k / total_relevant`. 5. Report mean Recall@10 across all queries. |
| **Data Source** | Benchmark query set in `data/search_benchmark/`; `KnowledgeIndex` contents; `SearchEngine` query results. |
| **Baseline Establishment** | After decomposing and indexing a reference codebase, manually craft 15 queries of varying specificity (5 exact-name, 5 concept-based, 5 cross-cutting). For each query, identify the 1–5 ground-truth relevant units. Run search and compute Recall@10. Expected MVP baseline: ≥0.70 for exact-name queries, ≥0.50 for concept-based queries. |
| **Improvement Direction** | Higher is better (target: mean Recall@10 ≥ 0.80 for v2). |
| **Guiding Significance** | Low recall means the index or search algorithm is failing to surface relevant units. For exact-name queries, investigate tokenization and indexing completeness. For concept-based queries, investigate the similarity/relevance algorithm. Improving index recall directly improves the utility of the knowledge analysis vertex for downstream consumers. |
| **Extension Points** | (1) Add semantic search via embedding-based similarity. (2) Track Precision@k and compute NDCG. (3) Query expansion and auto-complete. (4) Cross-codebase search. |

### D15: Structure Recognition Rate

| Field | Specification |
|-------|--------------|
| **Name** | Structure Recognition Rate |
| **Category** | V3 Analysis |
| **Metric** | Fraction of known architectural patterns and module boundaries correctly identified by `StructureAnalyzer` and `detect_architecture_patterns()` on reference codebases. |
| **Measurement Method** | 1. Select 5 reference codebases with known architectures (annotated): e.g., a Flask app (MVC), a hexagonal project, a microservices project with docker-compose, a flat script collection, a plugin-based system. 2. Run `StructureAnalyzer` and pattern detection on each. 3. Compare detected patterns against annotations. A pattern is "correctly identified" if the pattern name matches and confidence ≥ 0.5. 4. Compute: `recognition_rate = correctly_identified / total_annotated_patterns`. |
| **Data Source** | Reference codebases with architecture annotations in `data/reference_codebases/`; `StructureAnalyzer` output; `ArchitectureSignal` list. |
| **Baseline Establishment** | Annotate 5 reference codebases (can use well-known open-source projects). Run analysis. Expected MVP baseline: ≥0.60 (heuristic detection is limited; some patterns like microservices require infrastructure-level signals). |
| **Improvement Direction** | Higher is better (target: ≥0.80 for v2). |
| **Guiding Significance** | Low recognition rate means the pattern detection heuristics are insufficient. Analyze false negatives per pattern type to prioritize rule improvements. False positives (over-detection) should be tracked separately as they reduce trust in analysis results. |
| **Extension Points** | (1) Confidence calibration (are confidence scores well-calibrated?). (2) Pattern evolution tracking (detect architectural drift over time). (3) Add dependency-graph-based detection (not just directory naming). (4) Support polyglot architecture detection. |

---

## 6. System-Wide Dimensions

### D16: End-to-End Pipeline Latency

| Field | Specification |
|-------|--------------|
| **Name** | End-to-End Pipeline Latency |
| **Category** | System-wide |
| **Metric** | Wall-clock time (in seconds) to complete a full pipeline run: load task → sandbox setup → execute → score → report. Measured as p50 and p95 across the golden test set. |
| **Measurement Method** | 1. Instrument the `EvalRunner` pipeline with timing at each stage boundary. 2. Run the full golden test set (≥30 tasks). 3. Record per-task total latency and per-stage latency. 4. Compute: p50 and p95 across tasks. 5. Also record per-stage p50/p95 to identify bottlenecks. |
| **Data Source** | `EvalRunner` timing instrumentation; `MetricCollector` latency records; system clock. |
| **Baseline Establishment** | Run the golden test set 3 times on the target hardware. Record p50 and p95 for total pipeline and per-stage. Document hardware specs (CPU, RAM, disk type). Expected MVP baseline: p50 ≤ 30s, p95 ≤ 120s (depends heavily on sandbox creation time and task complexity). |
| **Improvement Direction** | Lower is better (target: p50 ≤ 15s, p95 ≤ 60s for v2). |
| **Guiding Significance** | Latency regression indicates: sandbox creation overhead increased, scorer complexity grew, or a stage introduced blocking I/O. Per-stage breakdown pinpoints the bottleneck. This metric directly affects NineS's usability as an interactive tool and as an Agent Skill (agents have timeout budgets). |
| **Extension Points** | (1) Track latency by task difficulty tier. (2) Add sandbox pool pre-warming to reduce cold-start latency. (3) Parallel task execution latency. (4) Memory footprint tracking alongside latency. (5) CI-integrated latency regression detection. |

### D17: Sandbox Isolation Effectiveness

| Field | Specification |
|-------|--------------|
| **Name** | Sandbox Isolation Effectiveness |
| **Category** | System-wide |
| **Metric** | Fraction of sandbox executions that produce a clean `PollutionReport` (no host environment changes detected), expressed as `clean_runs / total_runs`. |
| **Measurement Method** | 1. For every evaluation execution, wrap with `execute_with_pollution_check()` (domain_knowledge.md §4.5). 2. Before and after execution, take `EnvironmentSnapshot` of: environment variables, watched file hashes (project root, home directory sentinel files), watched directory listings (tmp dirs, pip cache), and `sys.path`. 3. Compare snapshots via `detect_pollution()`. 4. A run is "clean" if `PollutionReport.clean == True`. 5. Compute: `effectiveness = clean_runs / total_runs`. |
| **Data Source** | `PollutionReport` from each sandbox execution; `EnvironmentSnapshot` diffs; `SandboxManager` execution logs. |
| **Baseline Establishment** | Run the golden test set with pollution checking enabled. Include intentionally "messy" tasks that write to stdout, create temp files, and install pip packages — all should be contained within the sandbox. Expected MVP baseline: 1.0 (any pollution is a bug). |
| **Improvement Direction** | Higher is better (must be 1.0; any value below 1.0 is a critical bug). |
| **Guiding Significance** | This is a binary health metric. Any value below 1.0 is a critical defect requiring immediate investigation. Pollution categories (env var leak, file system leak, sys.path leak) guide the fix. This metric provides the trust foundation for the entire evaluation system — without isolation, results are unreliable. |
| **Extension Points** | (1) Add network isolation verification (sandbox should not make unauthorized network calls). (2) Cross-sandbox pollution detection (sandbox A affects sandbox B). (3) Resource leak detection (orphan processes, unclosed file handles). (4) Docker-level isolation verification (future Tier 2 sandbox). |

### D18: Self-Iteration Convergence Rate

| Field | Specification |
|-------|--------------|
| **Name** | Self-Iteration Convergence Rate |
| **Category** | System-wide |
| **Metric** | Number of MAPIM loop iterations required for the composite self-evaluation score to converge (variance < threshold), or equivalently, the fraction of maximum allowed iterations consumed before convergence. |
| **Measurement Method** | 1. Execute the `SelfImprovementLoop.run_iteration()` repeatedly (up to `max_iterations`). 2. After each iteration, record the composite self-evaluation score. 3. Apply the `composite_convergence_check()` from domain_knowledge.md §3.4 using all four methods: sliding window variance (`threshold=0.001`), relative improvement rate (`min_improvement=0.005`), Mann-Kendall trend test (95% confidence), and CUSUM stability check. 4. Convergence is declared when ≥3 of 4 methods agree (majority vote). 5. Record `iterations_to_converge`. Compute: `convergence_rate = 1 - (iterations_to_converge / max_iterations)`. |
| **Data Source** | `SelfImprovementLoop` history (`MeasurementSnapshot` series); `ConvergenceReport` output; `ScoreHistory` database. |
| **Baseline Establishment** | Run the self-iteration loop with `max_iterations=10` and `window=5`. Record the iteration at which convergence is first detected. For MVP (where manual improvements between iterations are not automated), simulate iteration by running self-eval after each code change. Expected MVP baseline: convergence within 5 iterations (convergence_rate ≥ 0.50). |
| **Improvement Direction** | Higher is better (faster convergence = fewer iterations needed = more efficient self-improvement). |
| **Guiding Significance** | Slow convergence (rate < 0.30) means improvement actions have low impact or the system is oscillating rather than monotonically improving. Action: review the `ImprovementPlanner` strategy selection, check for contradictory improvement actions, or increase the convergence window size. Fast convergence could also indicate premature plateau — verify against actual capability improvements. |
| **Extension Points** | (1) Per-dimension convergence tracking (some dimensions converge faster). (2) Convergence prediction (estimate iterations remaining). (3) Automatic step-size adjustment in improvement actions based on convergence rate. (4) Multi-objective convergence (Pareto front tracking across dimensions). |

### D19: Cross-Vertex Synergy Score

| Field | Specification |
|-------|--------------|
| **Name** | Cross-Vertex Synergy Score |
| **Category** | System-wide |
| **Metric** | Correlation coefficient between improvement in one vertex's aggregate score and subsequent improvement in other vertices' scores, measured over the iteration history. |
| **Measurement Method** | 1. From `ScoreHistory`, extract per-vertex aggregate scores at each iteration: `V1_score[t]`, `V2_score[t]`, `V3_score[t]`. 2. Compute lagged cross-correlations: does a V2 improvement at iteration t predict a V1 improvement at iteration t+1? 3. For each vertex pair (V1↔V2, V1↔V3, V2↔V3), compute Pearson correlation of score deltas: `corr(ΔVa[t], ΔVb[t+1])`. 4. Report mean synergy score across all pairs. A positive value indicates beneficial cross-vertex reinforcement. |
| **Data Source** | `ScoreHistory` database; per-vertex aggregate scores from `SelfEvalRunner`; iteration timestamps. |
| **Baseline Establishment** | Requires at least 5 iteration data points to compute meaningful correlations. In MVP, record per-vertex scores at each self-evaluation run. After ≥5 data points, compute initial synergy score. Expected MVP baseline: 0.0 (no measurable correlation yet — this is a tracking metric whose value emerges over time). |
| **Improvement Direction** | Higher is better (positive correlation indicates vertices reinforce each other). |
| **Guiding Significance** | A negative synergy score means improving one vertex is hurting another — a sign of resource competition or conflicting optimization. A positive score validates the three-vertex architecture design (improvements compound). Zero means the vertices are independent, which is not the design intent. Action on negative: investigate shared resource contention or improvement actions with cross-vertex side effects. |
| **Extension Points** | (1) Causal analysis (Granger causality tests for directed synergy). (2) Synergy decomposition by specific dimension pairs. (3) Optimal improvement allocation (invest in the vertex with highest synergy multiplier). (4) Visualization as a synergy graph with edge weights. |

---

## 7. MVP Baseline Collection Plan

### 7.1 Prerequisites

Before running the first baseline collection, the following must be in place:

1. **Golden test set**: ≥30 evaluation tasks in `data/golden_test_set/` with expected scores
2. **Reference codebases**: 2–3 annotated Python projects in `data/reference_codebases/`
3. **Canary tracking entities**: 3–5 GitHub repos + 2–3 arXiv queries configured
4. **Review test set**: 5–10 annotated code files in `data/review_test_set/`
5. **Search benchmark**: ≥15 queries with ground-truth in `data/search_benchmark/`
6. **Hardware documentation**: CPU, RAM, disk type, OS version recorded in baseline metadata

### 7.2 Execution Steps

The baseline collection is a sequential pipeline:

```
Step 1: Environment Validation (estimated: 2 min)
├── Verify all data prerequisites exist
├── Run source health checks (D06)
├── Verify sandbox creation/teardown works
└── Record hardware specs and NineS version

Step 2: V1 Evaluation Baseline (estimated: 15 min)
├── D01: Run golden test set × 3 runs, compute accuracy
├── D02: Run coverage check across all task types
├── D03: Run golden test set × 3 runs, compute Pass^3
├── D04: Validate report structure from latest run
└── D05: Run multi-scorer evaluation, compute pairwise agreement

Step 3: V2 Search Baseline (estimated: 20 min)
├── D06: Run source coverage health check
├── D07: Trigger canary changes, run collection, measure lag
├── D08: Compare detected changes against 7-day ground-truth
├── D09: Query DataStore, compute field completeness
└── D10: Run timed collection cycle, compute throughput per source

Step 4: V3 Analysis Baseline (estimated: 15 min)
├── D11: Run decomposition on reference codebases, compute coverage
├── D12: Run abstraction on annotated codebases, compute F1
├── D13: Run code review on review test set, compute F1
├── D14: Run search benchmark queries, compute Recall@10
└── D15: Run pattern detection on reference codebases, compute recognition rate

Step 5: System-Wide Baseline (estimated: 10 min)
├── D16: Extract per-stage latencies from Step 2 runs, compute p50/p95
├── D17: Extract PollutionReports from Step 2 runs, verify all clean
├── D18: Record initial self-eval score (this run is iteration 0)
└── D19: Record V1/V2/V3 aggregate scores (synergy requires ≥5 points)

Step 6: Report Generation (estimated: 2 min)
├── Generate baseline_v1.json (structured data)
├── Generate baseline_v1.md (human-readable report)
├── Store in data/baselines/v1/
└── Commit baseline artifacts
```

**Total estimated time**: ~65 minutes for first run.

### 7.3 Multi-Round Stability Verification

To ensure the baseline itself is stable, the full collection (Steps 2–5) is repeated 3 times. Stability is verified using the following protocol, adapted from domain_knowledge.md Area 3 (§3.4 and §4.6):

**Per-dimension stability check:**

1. Collect 3 independent measurements: `[m1, m2, m3]`
2. Compute coefficient of variation: `CV = std(measurements) / mean(measurements)`
3. Stability criterion: `CV ≤ 0.05` (5% variation acceptable)
4. For binary metrics (D17): all 3 runs must agree (3/3 clean)

**Composite stability check:**

Using the `composite_convergence_check()` with window=3:
- Sliding window variance: `variance(measurements) < 0.001`
- Relative improvement: `|m3 - m2| / m2 < 0.005`
- Mann-Kendall: not applicable with n=3 (skip)
- CUSUM: not applicable with n=3 (skip)

Fallback: for n=3, use the simplified criterion: `max(measurements) - min(measurements) < 0.10 × mean(measurements)`.

**Unstable dimension protocol:**

If a dimension fails the stability check:
1. Increase to 5 runs
2. Re-check with the full composite convergence check (all 4 methods applicable with n=5)
3. If still unstable: flag the dimension, record the variance, and investigate the root cause before accepting the baseline
4. Document any inherent non-determinism (e.g., D07 depends on external API timing) with a `stability_note` field

### 7.4 Baseline Acceptance Criteria

The baseline is accepted when:

| Criterion | Requirement |
|-----------|-------------|
| All 19 dimensions measured | No dimension has `null` or `error` value |
| Stability verified | ≥17 of 19 dimensions have CV ≤ 0.05 |
| Sandbox clean | D17 = 1.0 in all runs |
| Reports generated | Both JSON and Markdown outputs exist and pass schema validation |
| Metadata complete | Hardware specs, NineS version, timestamp, and run IDs recorded |

---

## 8. Output Formats

### 8.1 JSON Output Schema

The baseline and all subsequent self-evaluation runs produce a JSON file conforming to this structure:

```json
{
  "schema_version": "1.0",
  "nines_version": "0.1.0",
  "run_id": "uuid",
  "timestamp": "2026-04-11T12:00:00Z",
  "environment": {
    "python_version": "3.12.x",
    "os": "linux",
    "cpu": "...",
    "ram_gb": 16,
    "disk_type": "ssd"
  },
  "dimensions": {
    "D01_scoring_accuracy": {
      "value": 0.92,
      "unit": "fraction",
      "direction": "higher_is_better",
      "category": "V1_evaluation",
      "measurements": [0.93, 0.91, 0.92],
      "cv": 0.011,
      "stable": true,
      "details": {
        "per_tier": {"trivial": 0.98, "moderate": 0.92, "complex": 0.85}
      }
    }
  },
  "aggregates": {
    "V1_evaluation": 0.89,
    "V2_search": 0.87,
    "V3_analysis": 0.72,
    "system_wide": 0.95,
    "composite": 0.86
  },
  "stability": {
    "total_dimensions": 19,
    "stable_dimensions": 18,
    "unstable_dimensions": ["D07_tracking_freshness"],
    "stability_notes": {
      "D07_tracking_freshness": "Dependent on external API response time; CV=0.08"
    }
  },
  "comparison": {
    "baseline_version": null,
    "improved": [],
    "regressed": [],
    "unchanged": []
  }
}
```

### 8.2 Markdown Report Template

```markdown
# NineS Self-Evaluation Report

**Version**: {nines_version} | **Run**: {run_id} | **Date**: {timestamp}

## Summary

| Category | Score | Dimensions | Status |
|----------|-------|------------|--------|
| V1 Evaluation | {v1_score} | 5/5 measured | {status} |
| V2 Search | {v2_score} | 5/5 measured | {status} |
| V3 Analysis | {v3_score} | 5/5 measured | {status} |
| System-wide | {sys_score} | 4/4 measured | {status} |
| **Composite** | **{composite}** | **19/19** | {status} |

## Dimension Details

(Per-dimension table with value, baseline, delta, and stability flag)

## Trend Analysis

(Version-over-version comparison if previous baseline exists)

## Recommendations

(Auto-generated from GapDetector based on largest gaps)

## Stability Report

(Multi-round CV values and convergence check results)
```

### 8.3 Aggregate Scoring Formula

The composite score combines per-category aggregates:

```
V1_score = mean(D01, D02, D03, D04, D05)
V2_score = mean(D06, 1-normalize(D07), D08, D09, D10)
V3_score = mean(D11, D12, D13, D14, D15)
system_score = mean(D16_normalized, D17, D18, D19)

composite = 0.30 × V1_score + 0.25 × V2_score + 0.25 × V3_score + 0.20 × system_score
```

Notes:
- D07 (Tracking Freshness) is inverted and normalized to [0,1] via `1 - min(lag_minutes, max_lag) / max_lag` where `max_lag = 120 minutes`
- D16 (Latency) is normalized similarly: `1 - min(p50_seconds, max_latency) / max_latency` where `max_latency = 300 seconds`
- D19 (Synergy) is clamped to [0, 1] via `max(0, synergy_correlation)`
- Weights are configurable via `NinesConfig.self_eval.weights`

---

## 9. Convergence & Stability Framework

This section defines how NineS uses self-evaluation results to determine whether improvement has plateaued, referencing the four statistical methods from domain_knowledge.md §3.4.

### 9.1 Per-Dimension Convergence

For each dimension, maintain a time series `scores[t]` across iterations. Apply:

| Method | Parameters | When to Use |
|--------|-----------|-------------|
| **Sliding Window Variance** | `window=5, threshold=0.001` | Default; works for metrics stabilizing around a value |
| **Relative Improvement Rate** | `window=3, min_improvement=0.005` | Early iterations when trend direction matters |
| **Mann-Kendall Trend Test** | `window=10, confidence=0.95` | Mature series (≥10 data points) for trend detection |
| **CUSUM Change Detection** | `threshold=1.0, drift=0.5` | Detecting recent shifts after a period of stability |

**Decision rule**: A dimension is converged when ≥3 of the 4 applicable methods agree (majority vote via `composite_convergence_check()`).

### 9.2 System-Level Convergence

The system is considered converged when:
1. The composite score has converged (per §9.1)
2. No individual dimension has regressed by more than 5% in the last 3 iterations
3. No dimension flagged as "critical gap" by the `GapDetector` remains unaddressed

### 9.3 Convergence Actions

| State | Condition | Action |
|-------|-----------|--------|
| **Active Improvement** | ≤2 methods agree on convergence | Continue MAPIM loop; prioritize largest gaps |
| **Near Convergence** | 3 methods agree but composite still improving >0.5% | Run 2 more iterations to confirm stability |
| **Converged** | ≥3 methods agree, composite delta < 0.5% for 3 iterations | Terminate current improvement cycle; generate next-version plan |
| **Oscillating** | Mann-Kendall shows no trend but CUSUM detects changes | Investigate conflicting improvement actions; reduce step size |
| **Regressing** | Mann-Kendall shows significant negative trend | Halt improvements; rollback last change; investigate root cause |

---

## 10. Extension Roadmap

### Phase 1 (MVP → v1.1): Immediate Extensions

| Extension | Affected Dimensions | Effort |
|-----------|-------------------|--------|
| Increase golden test set to 100 tasks | D01, D03, D04, D05 | Low |
| Add 3 more reference codebases | D12, D13, D15 | Low |
| Implement per-stage latency dashboard | D16 | Medium |
| Add GitHub webhook support for push-based collection | D07, D08 | Medium |

### Phase 2 (v1.1 → v2.0): Capability Expansion

| Extension | Affected Dimensions | Effort |
|-----------|-------------------|--------|
| LLM-as-judge scorer integration (VAKRA waterfall) | D01, D05 | High |
| Semantic search via embeddings | D14 | Medium |
| Multi-language AST support (tree-sitter) | D11, D13, D15 | High |
| Docker-based sandbox (Tier 2) | D17 | Medium |
| Automated ground-truth generation via shadow collector | D08 | Medium |

### Phase 3 (v2.0+): Advanced Analytics

| Extension | Affected Dimensions | Effort |
|-----------|-------------------|--------|
| Causal synergy analysis (Granger causality) | D19 | Medium |
| Multi-objective Pareto convergence | D18 | High |
| Adaptive dimension weighting (meta-learning) | All | High |
| Community benchmark integration (SWE-Bench format) | D01, D02, D03 | Medium |
| Predictive convergence modeling | D18, D19 | High |

---

*Last modified: 2026-04-11T00:00:00Z*
