---
id: "nines/references/iteration-protocol"
version: "1.1.0"
purpose: >
  Documents the self-improvement iteration cycle: baseline management,
  self-evaluation, gap detection, improvement planning, convergence
  checking, and iteration tracking. v1.1.0 adds the v2.2.0 paradigm
  extension patterns (audits, budgets, identity, derived metrics).
  Load this reference when working on the iterate command, gap
  detection, or convergence logic, or when applying any v2.2.0
  paradigm to the iteration loop.
triggers:
  - "iterate"
  - "self-improve"
  - "gap"
  - "cycle"
  - "paradigm"
tier: 2
token_estimate: 2000
dependencies:
  - "nines/SKILL.md"
  - "nines/references/evaluation-framework"
  - "nines/references/resilience-budgets"
last_updated: "2026-04-18"
---

# Iteration Protocol Reference

## 1. Overview

The iteration system implements NineS's self-improvement cycle. It combines
self-evaluation, gap detection, improvement planning, and convergence
checking into a repeatable loop that drives the toolflow toward better
performance over successive versions.

### Iteration Cycle

```
  +---------------------------------------------+
  |                                             |
  |  +----------+    +--------------+           |
  |  | Baseline |<---| Save if      |           |
  |  | Manager  |    | improved     |           |
  |  +----+-----+    +--------------+           |
  |       |                   ^                 |
  |       v                   |                 |
  |  +----------+    +-------+------+           |
  |  | Self-Eval|---->| Gap Detector |           |
  |  | Runner   |    +-------+------+           |
  |  +----------+            |                  |
  |                          v                  |
  |              +-------------------+          |
  |              | Improvement       |          |
  |              | Planner           |          |
  |              +---------+---------+          |
  |                        |                    |
  |                        v                    |
  |              +-------------------+          |
  |              | Apply             |----------+
  |              | Improvements      |
  |              +---------+---------+
  |                        |
  |                        v
  |              +-------------------+
  |              | Convergence       |
  |              | Checker           |
  |              +-------------------+
  |                   |         |
  |              converged   not converged
  |                   |         |
  |                   v         +---- loop back ----> Self-Eval
  |              DONE
  +---------------------------------------------+
```

## 2. Baseline Management (`baseline.py`, FR-603, FR-604)

### BaselineManager

Persists `SelfEvalReport` snapshots as JSON files in a configurable
directory (default: `data/baselines/`).

| Method              | Purpose                                        |
|---------------------|------------------------------------------------|
| `save_baseline()`   | Write report as `{version}.json`               |
| `load_baseline()`   | Read a previously saved baseline               |
| `list_baselines()`  | Return version labels of all saved baselines   |
| `compare()`         | Compare current report against baseline        |

### ComparisonResult

```python
@dataclass
class ComparisonResult:
    improved: list[str]      # dimension names that improved
    regressed: list[str]     # dimension names that regressed
    unchanged: list[str]     # dimension names with no change
    overall_delta: float     # current.overall - baseline.overall
    details: dict[str, dict[str, float]]  # per-dimension breakdown
```

Comparison uses a configurable `tolerance` (default `1e-6`) to determine
whether a delta is significant.

## 3. Gap Detection (`gap_detector.py`, FR-606, FR-607)

### GapDetector

Compares a current `SelfEvalReport` against a baseline to identify
improved, regressed, and stagnated dimensions.

```python
detector = GapDetector(tolerance=0.01)
analysis = detector.detect(current_report, baseline_report)
```

### Gap Dataclass

```python
@dataclass
class Gap:
    dimension: str    # affected dimension name
    current: float    # current normalized score
    baseline: float   # baseline normalized score
    delta: float      # current - baseline
    severity: float   # |delta| for regressions, 0.0 otherwise
```

### GapAnalysis

```python
@dataclass
class GapAnalysis:
    improved: list[Gap]       # delta > tolerance
    regressed: list[Gap]      # delta < -tolerance
    stagnated: list[Gap]      # |delta| <= tolerance
    priority_gaps: list[Gap]  # regressed sorted by severity (worst first)
```

### Detection Logic

For each dimension in the current report:
1. Look up the baseline score (default 0.0 if dimension is new)
2. Compute `delta = current_normalized - baseline_normalized`
3. Compute `severity = |delta|` if regressed, else `0.0`
4. Classify into improved / regressed / stagnated based on tolerance
5. Sort regressions by severity descending into `priority_gaps`

## 4. Improvement Planning (`planner.py`, FR-608)

### ImprovementPlanner

Maps gap analysis results to prioritized improvement suggestions.

```python
planner = ImprovementPlanner()
plan = planner.plan(gap_analysis)
```

### Suggestion Dataclass

```python
@dataclass
class Suggestion:
    dimension: str          # target dimension
    action: str             # recommended action
    priority: int           # 1 = highest
    estimated_effort: str   # "low" | "medium" | "high"
    rationale: str          # why this suggestion was generated
```

### Planning Logic

1. For each gap in `priority_gaps` (regressions, worst first):
   - Rank = position in priority list (1, 2, 3, ...)
   - Effort estimated from severity magnitude:
     - severity >= 0.3 → `"high"`
     - severity >= 0.15 → `"medium"`
     - severity < 0.15 → `"low"`
   - Action: `"Improve {dimension}: regressed by {delta}"`
   - Rationale: `"Score dropped from {baseline} to {current}"`

2. For each stagnated dimension:
   - Priority = after all regressions
   - Effort = `"low"`
   - Action: `"Review {dimension}: no progress detected"`

### ImprovementPlan

```python
@dataclass
class ImprovementPlan:
    suggestions: list[Suggestion]  # sorted by priority
    total_gaps: int                # regressions + stagnations
```

## 5. Convergence Detection (`convergence.py`, FR-610)

### ConvergenceChecker

Determines whether a sequence of overall scores has stabilized using
sliding-window variance analysis.

```python
checker = ConvergenceChecker(window_size=5, min_rounds=3)
result = checker.check(history=[0.8, 0.82, 0.81, 0.82], threshold=0.05)
```

### Parameters

| Parameter     | Default | Description                               |
|---------------|---------|-------------------------------------------|
| `window_size` | 5       | Number of recent values to consider       |
| `min_rounds`  | 3       | Minimum data points before checking       |
| `threshold`   | 0.05    | Maximum variance to declare convergence   |

### Algorithm

1. If `len(history) < min_rounds` → not converged (variance = inf)
2. Take the last `window_size` values from history
3. Compute mean and variance of the window
4. If `variance <= threshold` → converged

### ConvergenceResult

```python
@dataclass
class ConvergenceResult:
    converged: bool
    variance: float
    rounds_checked: int
    mean: float
```

## 6. Iteration Tracking (`tracker.py`, FR-609)

### IterationTracker

Records the lifecycle of each iteration round for trend analysis.

```python
tracker = IterationTracker()
tracker.start_iteration("v1.0.0")
# ... perform iteration ...
tracker.complete_iteration(report)
progress = tracker.get_progress()
```

### IterationRecord

```python
@dataclass
class IterationRecord:
    version: str
    started_at: str             # ISO-8601
    completed_at: str           # ISO-8601
    report: SelfEvalReport?
    duration: float             # seconds
```

### ProgressReport

```python
@dataclass
class ProgressReport:
    total_iterations: int
    current_version: str
    overall_trend: list[float]  # overall scores per iteration
    improving: bool             # latest > previous
    best_score: float
```

The `improving` flag compares the last two entries in `overall_trend`.

## 7. Full Iteration Workflow

A complete iteration cycle follows these steps:

1. **Load baseline** — `BaselineManager.load_baseline(version)`
2. **Run self-eval** — `SelfEvalRunner.run_all(version)` → `SelfEvalReport`
3. **Detect gaps** — `GapDetector.detect(current, baseline)` → `GapAnalysis`
4. **Plan improvements** — `ImprovementPlanner.plan(analysis)` → plan
5. **Apply improvements** — execute suggestions (manual or automated)
6. **Re-evaluate** — run self-eval again
7. **Check convergence** — `ConvergenceChecker.check(trend, threshold)`
8. **Save baseline** — if improved, `BaselineManager.save_baseline(report, ver)`
9. **Track progress** — `IterationTracker.complete_iteration(report)`
10. **Loop or stop** — repeat from step 2 unless converged

## 8. Source Files

| File                  | Role                          | FRs          |
|-----------------------|-------------------------------|--------------|
| `baseline.py`         | Baseline persistence          | FR-603, 604  |
| `self_eval.py`        | Self-eval runner + evaluators | FR-601, 602  |
| `gap_detector.py`     | Gap detection and analysis    | FR-606, 607  |
| `planner.py`          | Improvement planning          | FR-608       |
| `convergence.py`      | Convergence checking          | FR-610       |
| `tracker.py`          | Iteration lifecycle tracking  | FR-609       |
| `history.py`          | Iteration history management  | (internal)   |
| `capability_evaluators.py` | Capability dimension evaluators | (internal) |
| `collection_evaluators.py` | Collection dimension evaluators | (internal) |
| `eval_evaluators.py`  | Eval dimension evaluators     | (internal)   |
| `system_evaluators.py`| System dimension evaluators   | (internal)   |
| `v1_evaluators.py`    | V1 dimension evaluators       | (internal)   |

## 9. v2.2.0 Paradigm Extension Patterns

The v2.2.0 paradigm-extension work introduced four cross-cutting
patterns that the iteration loop should adopt as new evaluators,
analyzers, or improvement-plan stages are added. Each is documented
in a dedicated reference file; the table below summarises how each
pattern slots into the iteration cycle and points to the empirical
evidence file that motivated it.

| Pattern                              | Reference                              | Iteration-cycle integration                                                                                                                       | Empirical evidence                                                |
|--------------------------------------|----------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| **Cross-artifact consistency audit** | `references/cross-artifact-audit.md`   | Run `ConsistencyAuditor` (planned C10) over each iteration's artifacts before promoting a baseline; gate on critical issues via `QualityGateMachine` (planned C07). | `.local/v2.2.0/profile/00_baseline_report.md` §4.1, §4.2, §4.5    |
| **Resilience budgets**               | `references/resilience-budgets.md`     | Wrap each `DimensionEvaluator.evaluate()` in `evaluator_budget(name, TimeBudget)` (shipped C04); use `with_retry` for transient-failure-prone evaluators (shipped C05). | `.local/v2.2.0/profile/00_baseline_report.md` §4.7 + `_timings.txt` |
| **Project identity**                 | `references/project-identity.md`       | All findings carry `project_fingerprint` (shipped C02); `EvaluationContext` (planned C01) makes per-project context explicit so foreign-repo iterations stop reading NineS's own values. | `.local/v2.2.0/profile/00_baseline_report.md` §4.5, §4.8           |
| **Derived metrics**                  | `references/derived-metrics.md`        | Score-like outputs (e.g. `economics_score`, planned `weighted_overall`) are computed from real inputs with `formula_version` migration; weighted by `MetricRegistry` (planned C08). | `.local/v2.2.0/profile/00_baseline_report.md` §4.6, §4.10          |

### How the patterns combine in a v2.2.x iteration round

1. **Bind context.** Build an `EvaluationContext(project_root, src_dir,
   …)` from CLI options; pass to `runner.run_all(ctx)` (post-C01). The
   context's `.fingerprint()` reuses `nines.core.identity.project_fingerprint`
   (shipped C02) so every analyzer and evaluator emits namespaced
   finding-IDs and dimension-metadata against the right project.
2. **Run within budgets.** Each evaluator is wrapped in
   `evaluator_budget(name, TimeBudget(soft, hard))` (shipped C04).
   Transient-failure paths use `with_retry(fn, RetryPolicy(attempts=
   cfg.eval_max_retries))` (shipped C05). Cost-bounded paths use
   `CostBudget(token_limit=…)` (shipped C05) with `CostExceeded`
   producing partial-results reports rather than crashes.
3. **Compute derived scores.** Per-evaluator scores feed into a
   `MetricRegistry` (planned C08) for per-group weighted aggregation.
   Score-like outputs (e.g. `economics_score`, shipped C09) are
   computed from real inputs with explicit `formula_version`
   migration.
4. **Audit and gate.** Before promoting a new baseline, run
   `ConsistencyAuditor.run_all(report_dir)` (planned C10) and
   `QualityGateMachine` (planned C07). If any `severity == "critical"`
   issue is detected, the gate refuses promotion (`GateState =
   REJECTED`) and the report is preserved for forensic inspection.

### Wave plan for these patterns

The patterns ship in waves keyed off the
`.local/v2.2.0/validate/03_consolidated_findings.md` §6 plan:

- **Wave 1 (v2.2.0):** identity (C02), derived economics (C09), resilience
  primitives (C04 runner-level + C05).
- **Wave 2 (v2.2.x or v2.3.0-rc1):** identity full migration (C01),
  consistency auditor (C10), gate FSM (C07), full mock harness for
  golden tests (C06 follow-up).
- **Wave 3 (v2.3.0):** weighted metric registry (C08), mechanism
  diversification rule-based (C11a).
- **Wave 4 (v2.4.0+):** breakdown reporter (C12), opt-in LLM-judge
  (C11b).

### Cross-references

- For accept-list decisions on each candidate: `.local/accept_list_v2.2.0.md`.
- For empirical proofs from the S04 POC stage:
  `.local/v2.2.0/benchmark/c0*_*.txt`.
- For per-track design rationale: `.local/v2.2.0/design/0[1-4]_track_*.md`.
- For per-candidate validation verdicts:
  `.local/v2.2.0/validate/0[1-3]_*.md`.
