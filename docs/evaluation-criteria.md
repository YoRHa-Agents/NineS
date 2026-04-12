# Evaluation Criteria

NineS uses 19 measurable dimensions organized into 4 categories to assess and improve AI agent capabilities. This page details each dimension, the scoring methodology, convergence detection, and how to use these criteria in practice.

---

## Overview

Self-evaluation is the foundation of NineS's self-improvement capability. Rather than relying on external reviewers, NineS measures its own performance across a comprehensive set of dimensions — from scoring accuracy and data completeness to pipeline latency and cross-vertex synergy.

Each dimension has:

- A **concrete measurement method** with a defined data source
- A **formula** that produces a normalized score (0–100)
- An **improvement direction** (higher is better or lower is better)
- An **MVP target** that defines the minimum acceptable performance

The 19 dimensions span all three capability vertices plus system-wide health, ensuring that self-evaluation captures the full picture of NineS's operational state.

---

## Evaluation Methodology

### Composite Scoring

NineS aggregates individual dimension scores into a single composite score using configurable weights:

```
V1_score = weighted_mean(normalized(D01..D05))
V2_score = weighted_mean(normalized(D06..D10))
V3_score = weighted_mean(normalized(D11..D15))
system_score = weighted_mean(normalized(D16..D19))

composite = 0.30 × V1 + 0.25 × V2 + 0.25 × V3 + 0.20 × system
```

Lower-is-better dimensions (D07, D16) are inverted via `1 − min(value, cap) / cap` before aggregation. D19 (synergy) is clamped to [0, 1]. Weights are configurable via `[self_eval.weights]` in `nines.toml`.

### Statistical Reliability

NineS employs multiple statistical measures to ensure evaluation results are trustworthy:

- **pass@k** — Probability that at least one of k attempts passes. Estimates capability breadth.
- **Pass^k** — Probability that all k attempts produce the same result. Measures determinism.
- **Pass³** — Three-run consistency check used for baseline stability verification.
- **Bootstrap confidence intervals** — Non-parametric confidence bounds for score estimates.

### Matrix Evaluation

The `MatrixEvaluator` supports evaluation across N configurable axes (task difficulty, scorer type, timeout, etc.). This enables:

- Combinatorial coverage of evaluation configurations
- Budget guards to cap total evaluation cost
- Sampling strategies for large parameter spaces
- Per-cell and cross-axis analysis

### Baseline Comparison and Gap Detection

Baselines freeze dimension scores at a point in time. The `GapDetector` compares current scores against baselines to:

- Identify **regressions** — dimensions that have worsened
- Identify **improvements** — dimensions that have improved
- Classify gaps as **critical**, **major**, **minor**, or **acceptable**
- Provide **root cause hints** pointing to specific modules

---

## Dimension Categories

### V1 Evaluation (D01–D05)

These dimensions assess the health and accuracy of the evaluation pipeline itself.

#### D01: Scoring Accuracy

| Field | Value |
|-------|-------|
| **What it measures** | How closely NineS's automated scores match human-verified ground truth |
| **Measurement** | Run `EvalRunner` on ≥30 golden test tasks. Compare output scores against ground-truth labels. |
| **Formula** | `accuracy = count(|nines_score − golden_score| ≤ 0.05) / total_tasks` |
| **Data Source** | `data/golden_test_set/` with `expected_score` fields |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.90 |
| **Why it matters** | If the scorer is inaccurate, every downstream decision (gap detection, improvement planning) is built on false data. Scoring accuracy is the bedrock of the evaluation pipeline. |
| **Improvement** | Expand golden test set, recalibrate scorer thresholds |

#### D02: Evaluation Coverage

| Field | Value |
|-------|-------|
| **What it measures** | The fraction of defined task types that NineS can successfully load, execute, and score |
| **Measurement** | Enumerate all task types in schema. For each, attempt load → execute → score. |
| **Formula** | `coverage = successful_types / total_defined_types` |
| **Direction** | Higher is better |
| **MVP Target** | 1.00 |
| **Why it matters** | Gaps in task type support mean blind spots in evaluation. Full coverage ensures that no capability goes unmeasured. |
| **Improvement** | Implement missing task-type loaders |

#### D03: Reliability (Pass^k Consistency)

| Field | Value |
|-------|-------|
| **What it measures** | Whether the same task produces the same pass/fail result across independent runs |
| **Measurement** | Run ≥20 tasks × k=3 independent runs in fresh sandboxes with identical seeds. |
| **Formula** | `consistency = count(all_k_agree) / total_tasks` |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.95 |
| **Why it matters** | Non-deterministic evaluation results undermine trust. If the same input produces different outputs, scores are unreliable for trend analysis and convergence detection. |
| **Improvement** | Fix non-determinism in sandbox, tighten seed control |

#### D04: Report Quality

| Field | Value |
|-------|-------|
| **What it measures** | Whether generated reports contain all required sections with valid content |
| **Measurement** | Parse `MarkdownReporter` and `JSONReporter` output. Check required sections. |
| **Formula** | `quality = present_valid_sections / total_required_sections` |
| **Required sections** | summary, task_results, per_dimension_scores, statistical_summary, recommendations, metadata |
| **Direction** | Higher is better |
| **MVP Target** | 1.00 |
| **Why it matters** | Reports are the primary interface between NineS and its users. Missing sections make results harder to interpret and act upon. |

#### D05: Scorer Agreement

| Field | Value |
|-------|-------|
| **What it measures** | The degree of agreement between different scorer implementations on the same outputs |
| **Measurement** | Score ≥20 outputs with all applicable scorers. Compute pairwise Cohen's κ. |
| **Formula** | Mean pairwise κ across all scorer pairs |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.70 |
| **Why it matters** | If scorers disagree significantly, the choice of scorer becomes the dominant variable — not the quality of the agent's output. Agreement validates scorer consistency. |
| **Improvement** | Recalibrate scorer parameters, add calibration datasets |

### V2 Search (D06–D10)

These dimensions assess the quality and efficiency of information collection.

#### D06: Source Coverage

| Field | Value |
|-------|-------|
| **What it measures** | The fraction of configured data sources that are active and reachable |
| **Measurement** | Execute lightweight health-check query per configured source. |
| **Formula** | `coverage = active_sources / configured_sources` |
| **Direction** | Higher is better |
| **MVP Target** | 1.00 |
| **Why it matters** | Inactive sources create blind spots in data collection. Full source coverage ensures comprehensive information gathering. |
| **Improvement** | Fix API credentials, check network connectivity |

#### D07: Tracking Freshness

| Field | Value |
|-------|-------|
| **What it measures** | How quickly NineS detects changes in tracked entities |
| **Measurement** | Track canary entities with known change schedules. Measure detection lag. |
| **Formula** | `median(detection_time − change_time)` across canaries |
| **Normalization** | Inverted: `1 − min(lag, 120) / 120` |
| **Direction** | Lower lag is better (higher normalized score is better) |
| **MVP Target** | ≤60 min |
| **Why it matters** | Stale data leads to outdated analysis. Fresh tracking ensures that NineS operates on current information. |

#### D08: Change Detection Recall

| Field | Value |
|-------|-------|
| **What it measures** | The fraction of actual changes that NineS successfully detects |
| **Measurement** | Compare detected changes against ground-truth change log over 7-day window. |
| **Formula** | `recall = true_positives / (true_positives + false_negatives)` |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.85 |
| **Why it matters** | Missed changes mean missed information. High recall ensures that important updates are not overlooked. |
| **Improvement** | Fix pagination, widen query scope |

#### D09: Data Completeness

| Field | Value |
|-------|-------|
| **What it measures** | How fully populated the fields are in collected entities |
| **Measurement** | Query all entities. Check populated fields per entity model schema. |
| **Formula** | `mean(populated_fields / total_fields)` across all entities |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.90 |
| **Why it matters** | Partially populated records reduce the value of downstream analysis. Complete data enables richer insights. |

#### D10: Collection Throughput

| Field | Value |
|-------|-------|
| **What it measures** | The rate at which NineS can collect entities from external sources |
| **Measurement** | Record entities collected and wall-clock time per source. |
| **Formula** | `entities / duration_minutes` |
| **Direction** | Higher is better |
| **MVP Target** | ≥50 |
| **Why it matters** | Slow collection bottlenecks the entire pipeline. Adequate throughput ensures timely data availability. |

### V3 Analysis (D11–D15)

These dimensions assess the quality of code analysis and knowledge extraction.

#### D11: Decomposition Coverage

| Field | Value |
|-------|-------|
| **What it measures** | The fraction of analyzable code elements captured by the decomposer |
| **Measurement** | Run AST extractor to count all elements. Run Decomposer. Compare. |
| **Formula** | `captured_elements / total_analyzable_elements` |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.85 |
| **Why it matters** | Missed elements are missed knowledge. High coverage ensures comprehensive codebase understanding. |

#### D12: Abstraction Quality

| Field | Value |
|-------|-------|
| **What it measures** | How accurately NineS identifies design patterns in code |
| **Measurement** | Run pattern detection on human-annotated reference codebases. |
| **Formula** | Macro-averaged F1 across architectural labels |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.60 |
| **Why it matters** | Correct pattern identification enables meaningful architectural analysis. Misclassification leads to incorrect structural understanding. |

#### D13: Code Review Accuracy

| Field | Value |
|-------|-------|
| **What it measures** | The accuracy of automated code review findings |
| **Measurement** | Run `CodeReviewer` on annotated code files with known issues. |
| **Formula** | F1 = 2 × (precision × recall) / (precision + recall) |
| **Match criteria** | Correct file, line range (±3 lines), and issue category |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.70 |
| **Why it matters** | Inaccurate code review wastes developer attention on false positives or misses real issues. Precision and recall must both be high. |

#### D14: Index Recall

| Field | Value |
|-------|-------|
| **What it measures** | How well the knowledge index retrieves relevant results for queries |
| **Measurement** | Execute ≥15 benchmark queries against indexed knowledge units. |
| **Formula** | `mean(relevant_in_top_10 / total_relevant)` |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.70 |
| **Why it matters** | A knowledge index that misses relevant results defeats its purpose. High recall ensures that searches return what users need. |

#### D15: Structure Recognition

| Field | Value |
|-------|-------|
| **What it measures** | The accuracy of architectural pattern recognition across codebases |
| **Measurement** | Run `StructureAnalyzer` on 5 reference codebases with known architectures. |
| **Formula** | `correctly_identified / total_annotated_patterns` |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.60 |
| **Why it matters** | Structural understanding is the foundation for decomposition and analysis recommendations. Misrecognition cascades through all downstream outputs. |

### System-Wide (D16–D19)

These dimensions assess overall system health and cross-cutting concerns.

#### D16: Pipeline Latency

| Field | Value |
|-------|-------|
| **What it measures** | End-to-end execution time for the evaluation pipeline |
| **Measurement** | Instrument `EvalRunner` with timing. Run golden test set. |
| **Formula** | p50 wall-clock time across all tasks |
| **Normalization** | `1 − min(p50, 300) / 300` |
| **Direction** | Lower latency is better (higher normalized score is better) |
| **MVP Target** | ≤30s |
| **Why it matters** | Slow pipelines reduce iteration speed. The MAPIM cycle's effectiveness depends on fast feedback. |

#### D17: Sandbox Isolation

| Field | Value |
|-------|-------|
| **What it measures** | Whether sandboxed execution leaves the host environment clean |
| **Measurement** | Wrap every execution with `execute_with_pollution_check()`. |
| **Formula** | `clean_runs / total_runs` |
| **Direction** | Higher is better |
| **MVP Target** | 1.00 |
| **Why it matters** | Any sandbox pollution is a critical bug. Host contamination can corrupt results, break subsequent runs, and undermine trust in the isolation layer. |
| **Critical** | Any value below 1.0 triggers an immediate investigation |

#### D18: Convergence Rate

| Field | Value |
|-------|-------|
| **What it measures** | How efficiently the MAPIM loop reaches stability |
| **Measurement** | Run MAPIM loop. Record iterations until 4-method convergence. |
| **Formula** | `1 − (iterations_to_converge / max_iterations)` |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.50 |
| **Why it matters** | A system that takes too many iterations to converge wastes compute and time. Efficient convergence means the improvement actions are effective. |

#### D19: Cross-Vertex Synergy

| Field | Value |
|-------|-------|
| **What it measures** | Whether improvements in one vertex lead to improvements in others |
| **Measurement** | Extract per-vertex scores at each iteration. Compute lagged correlations. |
| **Formula** | `mean(corr(ΔVa[t], ΔVb[t+1]))` across all 6 directed vertex pairs |
| **Minimum data** | Requires ≥5 iteration data points |
| **Direction** | Higher is better |
| **MVP Target** | ≥0.00 |
| **Why it matters** | Positive synergy means the three-vertex architecture is working as designed — improvements cascade. Zero or negative synergy suggests the vertices are operating in silos. |

---

## Scoring System

### Per-Dimension Scoring

Each dimension produces a raw value that is normalized to a 0–100 scale:

- **Higher-is-better** dimensions: Score is the raw value scaled to [0, 100]
- **Lower-is-better** dimensions (D07, D16): Inverted via `1 − min(value, cap) / cap`, then scaled
- **Bounded dimensions** (D19): Clamped to [0, 1] before scaling

### Category Aggregation

Dimensions are grouped into four categories with weighted means:

| Category | Dimensions | Default Weight |
|----------|------------|---------------|
| V1 Evaluation | D01–D05 | 0.30 |
| V2 Search | D06–D10 | 0.25 |
| V3 Analysis | D11–D15 | 0.25 |
| System-wide | D16–D19 | 0.20 |

### Composite Score

The composite score is the weighted mean of category scores. All weights are configurable via `[self_eval.weights]` in `nines.toml`.

### Threshold Definitions

| Level | Composite Score | Meaning |
|-------|----------------|---------|
| **Pass** | ≥0.85 | System is performing well across all categories |
| **Warning** | 0.70–0.84 | Some dimensions need attention; MAPIM should target gaps |
| **Fail** | <0.70 | Significant issues detected; immediate action required |

Per-dimension thresholds are defined by each dimension's MVP target. Dimensions below target are flagged for prioritized improvement.

---

## Convergence Detection

### 4-Method Majority Vote

Convergence is declared when **≥3 of 4** statistical methods agree that the composite score has stabilized:

| Method | Converged When | Default Parameters |
|--------|---------------|-------------------|
| Sliding Window Variance | σ²(last w scores) < τ | w=5, τ=0.001 |
| Relative Improvement | Average step improvement < threshold | threshold=0.005 |
| Mann-Kendall Trend Test | \|Z\| ≤ 1.96 (no significant trend) | 95% confidence |
| CUSUM Stability | No shift detected from reference mean | h=1.0, δ=0.5 |

### Why Multiple Methods

No single statistical test perfectly captures "the system has stopped improving":

- **Sliding variance** can be fooled by oscillating-but-stable scores
- **Relative improvement** misses cases where scores plateau then jump
- **Mann-Kendall** requires sufficient data points for power
- **CUSUM** is sensitive to parameter choices

By requiring ≥3/4 agreement, the composite decision is robust against any single method's failure mode. This avoids both premature convergence (stopping too early) and missed convergence (wasting iterations).

---

## Using Evaluation Criteria

### Running Self-Evaluation

```bash
# Full self-evaluation across all 19 dimensions
nines self-eval

# Evaluate specific dimensions
nines self-eval --dimensions D01,D02,D03

# Generate a detailed report
nines self-eval --report -o self_eval_report.md
```

### Comparing Against Baseline

```bash
# Compare current scores against a stored baseline
nines self-eval --baseline v1 --compare

# Establish a new baseline
nines self-eval --baseline v1.1 --save
```

### Interpreting Results

1. **Check the composite score** — Is the system passing, warning, or failing?
2. **Review per-category scores** — Which vertex needs the most attention?
3. **Examine individual dimensions** — Which specific dimensions are below target?
4. **Read gap analysis** — What are the root causes of underperformance?
5. **Review recommendations** — What concrete actions does NineS suggest?

### Targeting Specific Dimensions

When a dimension is below target, the `GapDetector` provides:

- **Severity classification** — critical, major, minor, or acceptable
- **Root cause hints** — Which module or component is responsible
- **Improvement actions** — Concrete steps to improve the score

The `ImprovementPlanner` maps these gaps to ≤3 module-level actions per MAPIM iteration, ensuring focused and manageable improvement cycles.
