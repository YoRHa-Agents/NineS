# NineS Self-Iteration Mechanism Design

> **Task**: T15 (Design Team L3) | **Generated**: 2026-04-11 | **Status**: Complete
>
> **Inputs**: `docs/design/self_eval_spec.md` (19-dimension evaluation spec), `docs/design/capability_model.md` (three-vertex mutual reinforcement), `docs/research/domain_knowledge.md` (Area 3: self-improving system patterns)

This document defines the self-iteration engine that drives NineS's continuous self-improvement. It specifies the complete MAPIM (Measure ? Analyze ? Plan ? Improve ? Measure) loop, including all component interfaces, convergence detection with mathematical rigor, and cross-vertex growth tracking.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Self-Evaluation Executor](#2-self-evaluation-executor)
3. [Baseline Manager](#3-baseline-manager)
4. [Gap Detector](#4-gap-detector)
5. [Improvement Planner](#5-improvement-planner)
6. [Iteration Tracker](#6-iteration-tracker)
7. [Convergence Checker](#7-convergence-checker)
8. [MAPIM Loop Orchestration](#8-mapim-loop-orchestration)
9. [Growth Tracking](#9-growth-tracking)
10. [Data Model Summary](#10-data-model-summary)

---

## 1. Architecture Overview

The self-iteration mechanism is a closed-loop control system: NineS measures its own capability across 19 dimensions (self_eval_spec.md ?2), detects gaps against baselines and targets, plans improvements, applies them, and re-measures. The loop terminates when convergence is detected or a maximum iteration count is reached.

### 1.1 Component Dependency Graph

```
????????????????????????????????????????????????????????????????????????????
?                        MAPIMOrchestrator                                 ?
?  (owns the loop lifecycle, enforces max iterations & escalation policy)  ?
???????????????????????????????????????????????????????????????????????????
        ?          ?          ?          ?          ?          ?
        ?          ?          ?          ?          ?          ?
 ?????????????? ???????????? ???????????? ????????????? ???????????? ?????????????
 ? SelfEval   ? ? Baseline ? ?   Gap    ? ?Improvement? ?Iteration ? ?Convergence?
 ? Runner     ? ? Manager  ? ? Detector ? ? Planner   ? ? Tracker  ? ? Checker   ?
 ?????????????? ???????????? ???????????? ????????????? ???????????? ?????????????
       ?              ?            ?              ?            ?              ?
       ?              ?            ?              ?            ?              ?
       ?              ?            ?              ?            ?              ?
 ????????????  ????????????? ???????????? ????????????? ???????????? ?????????????
 ?DimensionEva? ?data/      ? ?GapAnalysis? ?Improvement? ?Progress  ? ?Convergence?
 ?luator ?19  ? ?baselines/ ? ?(artifact) ? ?Plan       ? ?Report    ? ?Report     ?
 ?????????????? ????????????? ????????????? ????????????? ???????????? ?????????????
```

### 1.2 MAPIM Cycle Flow Diagram

```
                        ???????????????????
                        ?   START / RESUME ?
                        ???????????????????
                                 ?
                                 ?
                    ??????????????????????????
                    ?   M: MEASURE           ? ????????????????????????????????????
                    ?   SelfEvalRunner        ?                                    ?
                    ?   executes 19 dims      ?                                    ?
                    ?   ? SelfEvalReport      ?                                    ?
                    ???????????????????????????                                    ?
                                 ?                                                 ?
                                 ?                                                 ?
                    ??????????????????????????                                     ?
                    ?   A: ANALYZE           ?                                     ?
                    ?   GapDetector compares  ?                                    ?
                    ?   report vs baseline    ?                                    ?
                    ?   ? GapAnalysis         ?                                    ?
                    ???????????????????????????                                    ?
                                 ?                                                 ?
                                 ?                                                 ?
                    ??????????????????????????                                     ?
                    ?   ConvergenceChecker    ?                                    ?
                    ?   4-method composite    ?                                    ?
                    ?   check                 ?                                    ?
                    ???????????????????????????                                    ?
                             ?       ?                                             ?
                  converged  ?       ? not converged                               ?
                             ?       ?                                             ?
               ????????????????  ??????????????????????????                       ?
               ?   CONVERGED   ?  ?   P: PLAN              ?                      ?
               ?   Generate    ?  ?   ImprovementPlanner   ?                      ?
               ?   final       ?  ?   maps gaps ? actions  ?                      ?
               ?   report      ?  ?   ? ImprovementPlan    ?                      ?
               ????????????????  ???????????????????????????                      ?
                      ?                        ?                                   ?
                      ?                        ?                                   ?
               ????????????????  ??????????????????????????                       ?
               ?   TERMINATE   ?  ?   I: IMPROVE           ?                      ?
               ?   IterTracker ?  ?   Execute actions from  ?                     ?
               ?   generates   ?  ?   plan. Update modules. ?                     ?
               ?   ProgressRpt ?  ?   Record changes.       ?                     ?
               ????????????????  ???????????????????????????                      ?
                                               ?                                   ?
                                               ?  iteration_count < max?           ?
                                               ?  no stagnation detected?          ?
                                               ?                                   ?
                                               ?????????????????????????????????????
```

### 1.3 Design Principles

| Principle | Application |
|-----------|------------|
| **Typed artifacts between phases** | Every MAPIM phase produces a serializable dataclass stored in SQLite for auditability (capability_model.md C4) |
| **Bounded iteration** | Hard cap of `max_iterations` prevents unbounded loops (capability_model.md C5) |
| **Statistical convergence** | Multi-method composite check avoids premature termination (domain_knowledge.md ?3.4) |
| **Dimension-level granularity** | Each of the 19 dimensions is independently tracked, analyzed, and targeted for improvement |
| **Cross-vertex awareness** | Growth tracking measures inter-vertex synergy from the mutual reinforcement model |

---

## 2. Self-Evaluation Executor

The `SelfEvalRunner` orchestrates evaluation of all 19 dimensions defined in self_eval_spec.md. Each dimension is measured by a dedicated `DimensionEvaluator` implementing a common interface.

### 2.1 Dimension Evaluator Interface

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ImprovementDirection(Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class DimensionCategory(Enum):
    V1_EVALUATION = "V1_evaluation"
    V2_SEARCH = "V2_search"
    V3_ANALYSIS = "V3_analysis"
    SYSTEM_WIDE = "system_wide"


@dataclass(frozen=True)
class DimensionSpec:
    id: str                                  # e.g. "D01"
    name: str                                # e.g. "Scoring Accuracy"
    category: DimensionCategory
    direction: ImprovementDirection
    unit: str                                # e.g. "fraction", "seconds", "count"
    target: float                            # MVP target value
    weight: float = 1.0                      # contribution to category aggregate


@dataclass
class DimensionResult:
    dimension_id: str
    value: float
    measurements: list[float]                # raw per-run values
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def is_valid(self) -> bool:
        return self.error is None and len(self.measurements) > 0

    @property
    def cv(self) -> float:
        """Coefficient of variation across measurements."""
        if len(self.measurements) < 2:
            return 0.0
        mean = sum(self.measurements) / len(self.measurements)
        if mean == 0:
            return 0.0
        variance = sum((x - mean) ** 2 for x in self.measurements) / len(
            self.measurements
        )
        return (variance ** 0.5) / abs(mean)


@runtime_checkable
class DimensionEvaluator(Protocol):
    """Protocol interface for evaluating a single dimension (CON-09).

    Each of the 19 dimensions has a concrete class satisfying this
    protocol. No inheritance required ? any class implementing
    `evaluate()` with a matching signature satisfies this protocol
    via structural subtyping.
    """

    spec: DimensionSpec

    def evaluate(self, context: EvalContext) -> DimensionResult:
        """Execute the measurement and return the result.

        Implementations must:
        1. Run at least `context.min_runs` independent measurements.
        2. Populate `DimensionResult.measurements` with per-run values.
        3. Set `DimensionResult.value` to the aggregated score
           (typically the mean).
        4. Set `DimensionResult.error` if measurement failed.
        """
        ...


def normalize_dimension_value(value: float, spec: DimensionSpec) -> float:
    """Normalize a raw dimension value to [0, 1] for composite scoring.

    Standalone utility (formerly a method on the ABC).
    Higher-is-better dimensions are clamped to [0, 1].
    Lower-is-better dimensions are inverted via
    1 - min(value, cap) / cap.
    """
    if spec.direction == ImprovementDirection.HIGHER_IS_BETTER:
        return max(0.0, min(1.0, value))
    cap = spec.target * 2
    return max(0.0, 1.0 - min(value, cap) / cap)
```

### 2.2 Evaluation Context

```python
@dataclass
class EvalContext:
    """Shared context passed to every DimensionEvaluator."""
    nines_version: str
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    min_runs: int = 3
    golden_test_set_path: str = "data/golden_test_set/"
    reference_codebases_path: str = "data/reference_codebases/"
    review_test_set_path: str = "data/review_test_set/"
    search_benchmark_path: str = "data/search_benchmark/"
    environment: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
```

### 2.3 Self-Evaluation Report

```python
@dataclass
class SelfEvalReport:
    """Complete output of a self-evaluation run across all 19 dimensions."""
    run_id: str
    nines_version: str
    timestamp: datetime
    results: dict[str, DimensionResult]       # dimension_id ? result
    category_scores: dict[str, float]         # category name ? aggregate
    composite_score: float
    environment: dict[str, str]
    duration_total_ms: float

    @property
    def valid_count(self) -> int:
        return sum(1 for r in self.results.values() if r.is_valid)

    @property
    def stable_count(self) -> int:
        return sum(
            1 for r in self.results.values() if r.is_valid and r.cv <= 0.05
        )
```

### 2.4 SelfEvalRunner

```python
# Dimension registry: maps dimension IDs to their specs
DIMENSION_SPECS: dict[str, DimensionSpec] = {
    "D01": DimensionSpec("D01", "Scoring Accuracy",          DimensionCategory.V1_EVALUATION, ImprovementDirection.HIGHER_IS_BETTER, "fraction", 0.90),
    "D02": DimensionSpec("D02", "Evaluation Coverage",       DimensionCategory.V1_EVALUATION, ImprovementDirection.HIGHER_IS_BETTER, "fraction", 1.00),
    "D03": DimensionSpec("D03", "Reliability (Pass^k)",      DimensionCategory.V1_EVALUATION, ImprovementDirection.HIGHER_IS_BETTER, "fraction", 0.95),
    "D04": DimensionSpec("D04", "Report Quality",            DimensionCategory.V1_EVALUATION, ImprovementDirection.HIGHER_IS_BETTER, "fraction", 1.00),
    "D05": DimensionSpec("D05", "Scorer Agreement",          DimensionCategory.V1_EVALUATION, ImprovementDirection.HIGHER_IS_BETTER, "kappa",    0.70),
    "D06": DimensionSpec("D06", "Source Coverage",            DimensionCategory.V2_SEARCH,     ImprovementDirection.HIGHER_IS_BETTER, "fraction", 1.00),
    "D07": DimensionSpec("D07", "Tracking Freshness",         DimensionCategory.V2_SEARCH,     ImprovementDirection.LOWER_IS_BETTER,  "minutes",  60.0),
    "D08": DimensionSpec("D08", "Change Detection Recall",    DimensionCategory.V2_SEARCH,     ImprovementDirection.HIGHER_IS_BETTER, "fraction", 0.85),
    "D09": DimensionSpec("D09", "Data Completeness",          DimensionCategory.V2_SEARCH,     ImprovementDirection.HIGHER_IS_BETTER, "fraction", 0.90),
    "D10": DimensionSpec("D10", "Collection Throughput",      DimensionCategory.V2_SEARCH,     ImprovementDirection.HIGHER_IS_BETTER, "entities/min", 50.0),
    "D11": DimensionSpec("D11", "Decomposition Coverage",     DimensionCategory.V3_ANALYSIS,   ImprovementDirection.HIGHER_IS_BETTER, "fraction", 0.85),
    "D12": DimensionSpec("D12", "Abstraction Quality",        DimensionCategory.V3_ANALYSIS,   ImprovementDirection.HIGHER_IS_BETTER, "f1",       0.60),
    "D13": DimensionSpec("D13", "Code Review Accuracy",       DimensionCategory.V3_ANALYSIS,   ImprovementDirection.HIGHER_IS_BETTER, "f1",       0.70),
    "D14": DimensionSpec("D14", "Index Recall",               DimensionCategory.V3_ANALYSIS,   ImprovementDirection.HIGHER_IS_BETTER, "recall@10",0.70),
    "D15": DimensionSpec("D15", "Structure Recognition Rate", DimensionCategory.V3_ANALYSIS,   ImprovementDirection.HIGHER_IS_BETTER, "fraction", 0.60),
    "D16": DimensionSpec("D16", "Pipeline Latency",           DimensionCategory.SYSTEM_WIDE,   ImprovementDirection.LOWER_IS_BETTER,  "seconds",  30.0),
    "D17": DimensionSpec("D17", "Sandbox Isolation",          DimensionCategory.SYSTEM_WIDE,   ImprovementDirection.HIGHER_IS_BETTER, "fraction", 1.00),
    "D18": DimensionSpec("D18", "Convergence Rate",           DimensionCategory.SYSTEM_WIDE,   ImprovementDirection.HIGHER_IS_BETTER, "fraction", 0.50),
    "D19": DimensionSpec("D19", "Cross-Vertex Synergy",       DimensionCategory.SYSTEM_WIDE,   ImprovementDirection.HIGHER_IS_BETTER, "correlation", 0.00),
}

# Category weights from self_eval_spec.md ?8.3
CATEGORY_WEIGHTS: dict[str, float] = {
    "V1_evaluation": 0.30,
    "V2_search":     0.25,
    "V3_analysis":   0.25,
    "system_wide":   0.20,
}


class SelfEvalRunner:
    """Executes all 19 dimension evaluations and produces a SelfEvalReport.

    This is the 'Measure' phase of the MAPIM loop.
    """

    def __init__(
        self,
        evaluators: dict[str, DimensionEvaluator],
        category_weights: dict[str, float] | None = None,
    ) -> None:
        self.evaluators = evaluators
        self.category_weights = category_weights or CATEGORY_WEIGHTS

    def run(self, context: EvalContext) -> SelfEvalReport:
        """Execute all dimension evaluators and aggregate results."""
        import time

        start = time.monotonic()
        results: dict[str, DimensionResult] = {}

        for dim_id, evaluator in self.evaluators.items():
            try:
                results[dim_id] = evaluator.evaluate(context)
            except Exception as exc:
                results[dim_id] = DimensionResult(
                    dimension_id=dim_id,
                    value=0.0,
                    measurements=[],
                    error=f"{type(exc).__name__}: {exc}",
                )

        category_scores = self._compute_category_scores(results)
        composite = self._compute_composite(category_scores)
        duration = (time.monotonic() - start) * 1000

        return SelfEvalReport(
            run_id=context.run_id,
            nines_version=context.nines_version,
            timestamp=context.timestamp,
            results=results,
            category_scores=category_scores,
            composite_score=composite,
            environment=context.environment,
            duration_total_ms=duration,
        )

    def _compute_category_scores(
        self,
        results: dict[str, DimensionResult],
    ) -> dict[str, float]:
        """Compute per-category aggregate as weighted mean of normalized scores."""
        category_groups: dict[str, list[tuple[float, float]]] = {}
        for dim_id, result in results.items():
            if not result.is_valid:
                continue
            spec = DIMENSION_SPECS[dim_id]
            normalized = normalize_dimension_value(result.value, spec)
            cat = spec.category.value
            category_groups.setdefault(cat, []).append(
                (normalized, spec.weight)
            )

        scores: dict[str, float] = {}
        for cat, entries in category_groups.items():
            total_weight = sum(w for _, w in entries)
            if total_weight > 0:
                scores[cat] = sum(v * w for v, w in entries) / total_weight
            else:
                scores[cat] = 0.0
        return scores

    def _compute_composite(
        self,
        category_scores: dict[str, float],
    ) -> float:
        """Weighted composite: 0.30?V1 + 0.25?V2 + 0.25?V3 + 0.20?Sys."""
        total = 0.0
        for cat, weight in self.category_weights.items():
            total += category_scores.get(cat, 0.0) * weight
        return total
```

---

## 3. Baseline Manager

The `BaselineManager` handles creation, storage, retrieval, and comparison of version-tagged baseline snapshots. Baselines are the reference points against which all gap analysis is performed.

### 3.1 Baseline Storage Layout

```
data/baselines/
??? v1/
?   ??? baseline.json              # structured evaluation data
?   ??? baseline.md                # human-readable report
?   ??? metadata.json              # hardware, version, collection params
??? v1.1/
?   ??? baseline.json
?   ??? baseline.md
?   ??? metadata.json
??? latest -> v1.1/                # symlink to most recent
```

### 3.2 Interface Definition

```python
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class BaselineMetadata:
    version_tag: str                         # e.g. "v1", "v1.1"
    nines_version: str
    created_at: datetime
    hardware: dict[str, str]                 # cpu, ram_gb, disk_type, os
    collection_params: dict[str, Any]        # min_runs, window, etc.
    notes: str = ""


@dataclass
class Baseline:
    """A frozen snapshot of dimension scores serving as a reference point."""
    metadata: BaselineMetadata
    dimension_scores: dict[str, float]       # dimension_id ? value
    category_scores: dict[str, float]        # category ? aggregate
    composite_score: float
    dimension_details: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )
    stability: dict[str, float] = field(default_factory=dict)  # dim ? CV


@dataclass
class BaselineDiff:
    """Comparison between two baselines or between a report and a baseline."""
    base_version: str
    target_version: str
    improved: list[DimensionDelta]
    regressed: list[DimensionDelta]
    unchanged: list[DimensionDelta]
    composite_delta: float
    category_deltas: dict[str, float]


@dataclass
class DimensionDelta:
    dimension_id: str
    old_value: float
    new_value: float
    absolute_delta: float
    relative_delta: float                    # (new - old) / |old|
    direction_label: str                     # "improved", "regressed", "unchanged"


class BaselineManager:
    """Manages version-tagged baselines in data/baselines/.

    Responsibilities:
    - Establish a new baseline from a SelfEvalReport
    - Store and load baselines from disk
    - Compare any two baselines or a report against a baseline
    - Maintain a 'latest' symlink
    """

    def __init__(self, baselines_dir: str = "data/baselines") -> None:
        self.baselines_dir = Path(baselines_dir)
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

    def establish(
        self,
        report: SelfEvalReport,
        version_tag: str,
        hardware: dict[str, str],
        notes: str = "",
    ) -> Baseline:
        """Create and store a new baseline from a self-evaluation report."""
        metadata = BaselineMetadata(
            version_tag=version_tag,
            nines_version=report.nines_version,
            created_at=report.timestamp,
            hardware=hardware,
            collection_params={"min_runs": 3},
            notes=notes,
        )
        baseline = Baseline(
            metadata=metadata,
            dimension_scores={
                dim_id: r.value
                for dim_id, r in report.results.items()
                if r.is_valid
            },
            category_scores=report.category_scores,
            composite_score=report.composite_score,
            dimension_details={
                dim_id: r.details
                for dim_id, r in report.results.items()
            },
            stability={
                dim_id: r.cv
                for dim_id, r in report.results.items()
                if r.is_valid
            },
        )
        self._save(baseline)
        self._update_latest(version_tag)
        return baseline

    def load(self, version_tag: str) -> Baseline:
        """Load a stored baseline by version tag."""
        path = self.baselines_dir / version_tag / "baseline.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No baseline found for version '{version_tag}'"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._deserialize(data)

    def load_latest(self) -> Baseline | None:
        """Load the most recently established baseline."""
        latest = self.baselines_dir / "latest"
        if not latest.exists():
            return None
        resolved = latest.resolve()
        tag = resolved.name
        return self.load(tag)

    def list_versions(self) -> list[str]:
        """Return all stored baseline version tags, sorted chronologically."""
        versions = []
        for child in sorted(self.baselines_dir.iterdir()):
            if child.is_dir() and child.name != "latest":
                versions.append(child.name)
        return versions

    def compare(
        self,
        base: Baseline,
        target_report: SelfEvalReport,
        tolerance: float = 0.01,
    ) -> BaselineDiff:
        """Compare a SelfEvalReport against a baseline."""
        improved, regressed, unchanged = [], [], []

        all_dims = set(base.dimension_scores) | set(target_report.results)
        for dim_id in sorted(all_dims):
            old_val = base.dimension_scores.get(dim_id, 0.0)
            result = target_report.results.get(dim_id)
            new_val = result.value if result and result.is_valid else 0.0

            abs_delta = new_val - old_val
            rel_delta = abs_delta / max(abs(old_val), 1e-9)

            spec = DIMENSION_SPECS.get(dim_id)
            if spec and spec.direction == ImprovementDirection.LOWER_IS_BETTER:
                abs_delta = -abs_delta
                rel_delta = -rel_delta

            if abs(abs_delta) <= tolerance:
                label = "unchanged"
            elif abs_delta > 0:
                label = "improved"
            else:
                label = "regressed"

            delta = DimensionDelta(
                dimension_id=dim_id,
                old_value=old_val,
                new_value=new_val,
                absolute_delta=abs_delta,
                relative_delta=rel_delta,
                direction_label=label,
            )

            if label == "improved":
                improved.append(delta)
            elif label == "regressed":
                regressed.append(delta)
            else:
                unchanged.append(delta)

        composite_delta = (
            target_report.composite_score - base.composite_score
        )
        category_deltas = {
            cat: target_report.category_scores.get(cat, 0.0) - base.category_scores.get(cat, 0.0)
            for cat in set(base.category_scores) | set(target_report.category_scores)
        }

        return BaselineDiff(
            base_version=base.metadata.version_tag,
            target_version=target_report.nines_version,
            improved=improved,
            regressed=regressed,
            unchanged=unchanged,
            composite_delta=composite_delta,
            category_deltas=category_deltas,
        )

    def _save(self, baseline: Baseline) -> None:
        tag_dir = self.baselines_dir / baseline.metadata.version_tag
        tag_dir.mkdir(parents=True, exist_ok=True)
        data = self._serialize(baseline)
        (tag_dir / "baseline.json").write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    def _update_latest(self, version_tag: str) -> None:
        latest = self.baselines_dir / "latest"
        target = self.baselines_dir / version_tag
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(target)

    def _serialize(self, baseline: Baseline) -> dict:
        return {
            "metadata": {
                "version_tag": baseline.metadata.version_tag,
                "nines_version": baseline.metadata.nines_version,
                "created_at": baseline.metadata.created_at.isoformat(),
                "hardware": baseline.metadata.hardware,
                "collection_params": baseline.metadata.collection_params,
                "notes": baseline.metadata.notes,
            },
            "dimension_scores": baseline.dimension_scores,
            "category_scores": baseline.category_scores,
            "composite_score": baseline.composite_score,
            "dimension_details": baseline.dimension_details,
            "stability": baseline.stability,
        }

    def _deserialize(self, data: dict) -> Baseline:
        meta = data["metadata"]
        return Baseline(
            metadata=BaselineMetadata(
                version_tag=meta["version_tag"],
                nines_version=meta["nines_version"],
                created_at=datetime.fromisoformat(meta["created_at"]),
                hardware=meta["hardware"],
                collection_params=meta["collection_params"],
                notes=meta.get("notes", ""),
            ),
            dimension_scores=data["dimension_scores"],
            category_scores=data["category_scores"],
            composite_score=data["composite_score"],
            dimension_details=data.get("dimension_details", {}),
            stability=data.get("stability", {}),
        )
```

---

## 4. Gap Detector

The `GapDetector` compares current evaluation scores against baseline values and target thresholds, producing a prioritized `GapAnalysis` that identifies which dimensions improved, regressed, or stagnated.

### 4.1 Gap Severity Classification

| Severity | Condition | Priority Weight |
|----------|-----------|----------------|
| **critical** | score < 50% of target OR regression > 10% from baseline | 4.0 |
| **major** | score < 75% of target OR regression > 5% from baseline | 3.0 |
| **minor** | score < 90% of target | 2.0 |
| **acceptable** | score ? 90% of target | 1.0 |

### 4.2 Interface Definition

```python
from dataclasses import dataclass, field


class GapSeverity(Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    ACCEPTABLE = "acceptable"


@dataclass
class DimensionGap:
    dimension_id: str
    dimension_name: str
    category: DimensionCategory
    current_value: float
    baseline_value: float | None
    target_value: float
    gap_to_target: float                     # target - current (normalized sign)
    gap_to_baseline: float                   # current - baseline (normalized sign)
    severity: GapSeverity
    priority_score: float                    # weighted ranking value
    trend: str                               # "improving", "regressing", "stagnant"
    suggested_root_causes: list[str]


@dataclass
class GapAnalysisReport:
    """Output of the GapDetector: prioritized gap list with summary."""
    run_id: str
    timestamp: datetime
    gaps: list[DimensionGap]                 # sorted by priority_score desc
    top_priority_dimensions: list[str]       # top-N dimension IDs to focus on
    regression_count: int
    improvement_count: int
    stagnant_count: int
    composite_gap: float                     # target composite - current

    @property
    def critical_gaps(self) -> list[DimensionGap]:
        return [g for g in self.gaps if g.severity == GapSeverity.CRITICAL]

    @property
    def actionable_gaps(self) -> list[DimensionGap]:
        return [
            g for g in self.gaps
            if g.severity in (GapSeverity.CRITICAL, GapSeverity.MAJOR)
        ]


# Mapping from dimension IDs to likely root causes for gap analysis hints.
# These are refined over successive iterations.
ROOT_CAUSE_HINTS: dict[str, list[str]] = {
    "D01": ["scorer calibration drift", "golden test set too narrow", "task format changes"],
    "D02": ["new task type missing loader", "schema registry out of sync"],
    "D03": ["non-determinism in sandbox", "seed control gaps", "flaky test oracles"],
    "D04": ["reporter template regression", "missing data source for section"],
    "D05": ["scorer parameter divergence", "different construct measurement"],
    "D06": ["API credential expiry", "rate limit saturation", "source URL change"],
    "D07": ["collection schedule too infrequent", "slow diff computation"],
    "D08": ["pagination bug", "bookmark cursor error", "query scope too narrow"],
    "D09": ["collector extraction bug", "API response schema drift"],
    "D10": ["rate limit saturation", "network degradation", "missing batch queries"],
    "D11": ["unsupported syntax patterns", "AST parse errors", "filter too restrictive"],
    "D12": ["heuristic rules too coarse", "missing layer indicators"],
    "D13": ["detection thresholds too conservative", "missing rule category"],
    "D14": ["index tokenization gap", "relevance algorithm weakness"],
    "D15": ["insufficient pattern detection rules", "confidence threshold too high"],
    "D16": ["sandbox cold-start overhead", "scorer complexity increase", "blocking I/O"],
    "D17": ["sandbox env var leak", "file system isolation breach", "sys.path leak"],
    "D18": ["conflicting improvement actions", "oscillation in scores"],
    "D19": ["resource competition between vertices", "conflicting optimization"],
}


class GapDetector:
    """Compares SelfEvalReport against baseline/targets to identify gaps.

    This is the 'Analyze' phase of the MAPIM loop.
    """

    SEVERITY_WEIGHTS: dict[GapSeverity, float] = {
        GapSeverity.CRITICAL: 4.0,
        GapSeverity.MAJOR: 3.0,
        GapSeverity.MINOR: 2.0,
        GapSeverity.ACCEPTABLE: 1.0,
    }

    def __init__(
        self,
        dimension_specs: dict[str, DimensionSpec] | None = None,
        top_n: int = 5,
    ) -> None:
        self.specs = dimension_specs or DIMENSION_SPECS
        self.top_n = top_n

    def detect(
        self,
        report: SelfEvalReport,
        baseline: Baseline | None,
        history: list[SelfEvalReport] | None = None,
    ) -> GapAnalysisReport:
        """Analyze gaps across all 19 dimensions."""
        gaps: list[DimensionGap] = []

        for dim_id, spec in self.specs.items():
            result = report.results.get(dim_id)
            current = result.value if result and result.is_valid else 0.0
            baseline_val = (
                baseline.dimension_scores.get(dim_id)
                if baseline
                else None
            )
            target = spec.target

            gap_to_target = self._signed_gap(
                current, target, spec.direction
            )
            gap_to_baseline = (
                self._signed_gap(current, baseline_val, spec.direction)
                if baseline_val is not None
                else 0.0
            )

            severity = self._classify_severity(
                current, target, baseline_val, spec.direction
            )
            trend = self._detect_trend(dim_id, history)
            priority = self._compute_priority(
                severity, gap_to_target, spec.weight
            )

            gaps.append(DimensionGap(
                dimension_id=dim_id,
                dimension_name=spec.name,
                category=spec.category,
                current_value=current,
                baseline_value=baseline_val,
                target_value=target,
                gap_to_target=gap_to_target,
                gap_to_baseline=gap_to_baseline,
                severity=severity,
                priority_score=priority,
                trend=trend,
                suggested_root_causes=ROOT_CAUSE_HINTS.get(dim_id, []),
            ))

        gaps.sort(key=lambda g: g.priority_score, reverse=True)
        top_dims = [g.dimension_id for g in gaps[: self.top_n]]

        return GapAnalysisReport(
            run_id=report.run_id,
            timestamp=report.timestamp,
            gaps=gaps,
            top_priority_dimensions=top_dims,
            regression_count=sum(
                1 for g in gaps if g.trend == "regressing"
            ),
            improvement_count=sum(
                1 for g in gaps if g.trend == "improving"
            ),
            stagnant_count=sum(
                1 for g in gaps if g.trend == "stagnant"
            ),
            composite_gap=1.0 - report.composite_score,
        )

    def _signed_gap(
        self,
        current: float,
        target: float,
        direction: ImprovementDirection,
    ) -> float:
        """Positive = room for improvement; negative = exceeding target."""
        if direction == ImprovementDirection.HIGHER_IS_BETTER:
            return target - current
        return current - target

    def _classify_severity(
        self,
        current: float,
        target: float,
        baseline: float | None,
        direction: ImprovementDirection,
    ) -> GapSeverity:
        ratio = current / target if target != 0 else 1.0
        if direction == ImprovementDirection.LOWER_IS_BETTER:
            ratio = target / current if current != 0 else 1.0

        baseline_regression = 0.0
        if baseline is not None and baseline != 0:
            if direction == ImprovementDirection.HIGHER_IS_BETTER:
                baseline_regression = (baseline - current) / abs(baseline)
            else:
                baseline_regression = (current - baseline) / abs(baseline)

        if ratio < 0.50 or baseline_regression > 0.10:
            return GapSeverity.CRITICAL
        if ratio < 0.75 or baseline_regression > 0.05:
            return GapSeverity.MAJOR
        if ratio < 0.90:
            return GapSeverity.MINOR
        return GapSeverity.ACCEPTABLE

    def _detect_trend(
        self,
        dim_id: str,
        history: list[SelfEvalReport] | None,
    ) -> str:
        if not history or len(history) < 2:
            return "stagnant"
        recent = []
        for h in history[-3:]:
            r = h.results.get(dim_id)
            if r and r.is_valid:
                recent.append(r.value)
        if len(recent) < 2:
            return "stagnant"
        deltas = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        avg_delta = sum(deltas) / len(deltas)
        if avg_delta > 0.005:
            return "improving"
        if avg_delta < -0.005:
            return "regressing"
        return "stagnant"

    def _compute_priority(
        self,
        severity: GapSeverity,
        gap_to_target: float,
        dim_weight: float,
    ) -> float:
        """Priority = severity_weight ? |gap_to_target| ? dimension_weight."""
        return (
            self.SEVERITY_WEIGHTS[severity]
            * abs(gap_to_target)
            * dim_weight
        )
```

---

## 5. Improvement Planner

The `ImprovementPlanner` translates a `GapAnalysisReport` into an actionable `ImprovementPlan` ? a prioritized list of concrete module changes mapped to specific dimensions.

### 5.1 Gap-to-Module Mapping

Each dimension maps to one or more NineS modules that can be changed to improve it:

| Dimension | Primary Module(s) | Improvement Strategy |
|-----------|-------------------|---------------------|
| D01 | `EvalRunner`, `ScorerPipeline` | Calibrate scorer thresholds, expand golden test set |
| D02 | `TaskLoader`, `TaskDefinition` | Implement missing task-type loaders |
| D03 | `SandboxManager`, seed control | Fix non-determinism sources, tighten seed control |
| D04 | `MarkdownReporter`, `JSONReporter` | Add missing report sections, fix formatters |
| D05 | `ScorerPipeline` multi-scorer | Recalibrate scorer parameters, add calibration dataset |
| D06 | `SourceProtocol`, credential management | Fix API credentials, add health-check retries |
| D07 | Collection scheduler, `ChangeDetector` | Increase collection frequency, add webhooks |
| D08 | `ChangeDetector`, pagination logic | Fix pagination, widen query scope |
| D09 | Collector extraction per field | Audit field extractors, handle API schema changes |
| D10 | Collector pipeline, rate limiter | Switch REST?GraphQL, increase parallelism |
| D11 | `Decomposer`, `CodeExtractor` | Handle more syntax patterns, relax filters |
| D12 | `AbstractionLayer`, `LAYER_INDICATORS` | Refine heuristic rules, add indicators |
| D13 | `CodeReviewer`, detection rules | Add rule categories, adjust thresholds |
| D14 | `SearchEngine`, `KnowledgeIndex` | Improve tokenization, add relevance tuning |
| D15 | `StructureAnalyzer`, pattern rules | Add detection rules, lower confidence threshold |
| D16 | `EvalRunner` pipeline, sandbox pool | Pre-warm sandboxes, optimize slow stages |
| D17 | `SandboxManager`, isolation barriers | Fix identified leak type from `PollutionReport` |
| D18 | `ImprovementPlanner`, action selection | Reduce conflicting actions, adjust step sizes |
| D19 | Cross-vertex data flows | Strengthen F1?F6 data flows (capability_model.md ?1) |

### 5.2 Interface Definition

```python
@dataclass
class ImprovementAction:
    """A single concrete action to improve a dimension."""
    id: str
    target_dimensions: list[str]             # primary dimension(s) targeted
    target_modules: list[str]                # source modules to modify
    description: str
    rationale: str                           # why this action addresses the gap
    priority: int                            # 1 = highest
    effort: str                              # "small" (<1h), "medium" (1-4h), "large" (>4h)
    expected_impact: dict[str, float]        # dimension_id ? expected delta
    risk: str                                # "low", "medium", "high"
    cross_vertex_effects: list[str]          # predicted side-effects on other vertices


@dataclass
class ImprovementPlan:
    """Prioritized plan of improvement actions for one MAPIM iteration."""
    plan_id: str
    iteration: int
    timestamp: datetime
    source_gap_analysis: str                 # run_id of the GapAnalysisReport
    actions: list[ImprovementAction]
    total_expected_composite_delta: float
    estimated_total_effort: str
    focus_categories: list[str]              # which vertex categories are prioritized

    @property
    def action_count(self) -> int:
        return len(self.actions)

    def actions_by_priority(self) -> list[ImprovementAction]:
        return sorted(self.actions, key=lambda a: a.priority)


# Maps (dimension_id, severity) to candidate action templates.
ACTION_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "D01": [
        {"desc": "Expand golden test set with {n} new tasks at gap difficulty tier",
         "modules": ["data/golden_test_set", "EvalRunner"],
         "effort": "medium", "impact": 0.03},
        {"desc": "Recalibrate ExactScorer tolerance parameter",
         "modules": ["ScorerPipeline"],
         "effort": "small", "impact": 0.02},
    ],
    "D03": [
        {"desc": "Audit sandbox seed control for sources of non-determinism",
         "modules": ["SandboxManager", "seed_control"],
         "effort": "medium", "impact": 0.05},
    ],
    "D07": [
        {"desc": "Reduce collection interval from {current} to {proposed} minutes",
         "modules": ["CollectionScheduler"],
         "effort": "small", "impact": 0.15},
    ],
    "D11": [
        {"desc": "Add AST handling for {pattern} syntax patterns",
         "modules": ["CodeExtractor", "Decomposer"],
         "effort": "medium", "impact": 0.04},
    ],
    # ... templates for all 19 dimensions follow the same structure
}


class ImprovementPlanner:
    """Generates actionable improvement plans from gap analysis.

    This is the 'Plan' phase of the MAPIM loop.

    Prioritization Algorithm:
    1. Score each candidate action:
       action_score = gap.priority_score ? expected_impact / effort_weight
    2. Apply cross-vertex bonus: +20% for actions that improve multiple vertices
    3. Apply regression penalty: +50% priority for actions fixing regressions
    4. Sort by action_score descending
    5. Select top-K actions respecting effort budget
    """

    EFFORT_WEIGHTS: dict[str, float] = {
        "small": 1.0,
        "medium": 2.0,
        "large": 4.0,
    }

    def __init__(
        self,
        max_actions_per_plan: int = 3,
        cross_vertex_bonus: float = 0.20,
        regression_penalty: float = 0.50,
    ) -> None:
        self.max_actions = max_actions_per_plan
        self.cross_vertex_bonus = cross_vertex_bonus
        self.regression_penalty = regression_penalty

    def plan(
        self,
        gap_report: GapAnalysisReport,
        history: list[SelfEvalReport] | None = None,
    ) -> ImprovementPlan:
        """Generate a prioritized improvement plan from gap analysis."""
        candidates: list[tuple[float, ImprovementAction]] = []

        for gap in gap_report.actionable_gaps:
            actions = self._generate_actions(gap)
            for action in actions:
                score = self._score_action(action, gap)
                candidates.append((score, action))

        candidates.sort(key=lambda c: c[0], reverse=True)
        selected = [
            action for _, action in candidates[: self.max_actions]
        ]

        for i, action in enumerate(selected, start=1):
            action.priority = i

        total_delta = sum(
            sum(a.expected_impact.values()) for a in selected
        )

        return ImprovementPlan(
            plan_id=uuid.uuid4().hex[:12],
            iteration=len(history) if history else 0,
            timestamp=datetime.now(timezone.utc),
            source_gap_analysis=gap_report.run_id,
            actions=selected,
            total_expected_composite_delta=total_delta,
            estimated_total_effort=self._estimate_total_effort(selected),
            focus_categories=self._identify_focus_categories(selected),
        )

    def _generate_actions(
        self,
        gap: DimensionGap,
    ) -> list[ImprovementAction]:
        """Instantiate action templates for a specific gap."""
        templates = ACTION_TEMPLATES.get(gap.dimension_id, [])
        actions = []
        for tmpl in templates:
            action = ImprovementAction(
                id=f"act_{gap.dimension_id}_{uuid.uuid4().hex[:6]}",
                target_dimensions=[gap.dimension_id],
                target_modules=tmpl["modules"],
                description=tmpl["desc"],
                rationale=f"Gap severity={gap.severity.value}, "
                          f"gap_to_target={gap.gap_to_target:.3f}",
                priority=0,
                effort=tmpl["effort"],
                expected_impact={
                    gap.dimension_id: tmpl["impact"]
                },
                risk="low",
                cross_vertex_effects=[],
            )
            actions.append(action)
        return actions

    def _score_action(
        self,
        action: ImprovementAction,
        gap: DimensionGap,
    ) -> float:
        total_impact = sum(action.expected_impact.values())
        effort_w = self.EFFORT_WEIGHTS.get(action.effort, 2.0)
        base_score = gap.priority_score * total_impact / effort_w

        if len(action.target_dimensions) > 1:
            base_score *= 1.0 + self.cross_vertex_bonus

        if gap.trend == "regressing":
            base_score *= 1.0 + self.regression_penalty

        return base_score

    def _estimate_total_effort(
        self,
        actions: list[ImprovementAction],
    ) -> str:
        total = sum(self.EFFORT_WEIGHTS.get(a.effort, 2.0) for a in actions)
        if total <= 5:
            return "small"
        if total <= 15:
            return "medium"
        return "large"

    def _identify_focus_categories(
        self,
        actions: list[ImprovementAction],
    ) -> list[str]:
        cat_counts: dict[str, int] = {}
        for action in actions:
            for dim_id in action.target_dimensions:
                spec = DIMENSION_SPECS.get(dim_id)
                if spec:
                    cat = spec.category.value
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1
        return sorted(cat_counts, key=cat_counts.get, reverse=True)
```

---

## 6. Iteration Tracker

The `IterationTracker` maintains a complete history of self-evaluation scores across iterations. It computes trend statistics (moving average, linear regression) and generates `ProgressReport` artifacts.

### 6.1 Interface Definition

```python
import math
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScorePoint:
    """A single score observation at a point in time."""
    iteration: int
    timestamp: datetime
    value: float


@dataclass
class TrendStats:
    """Statistical trend analysis for a score time series."""
    moving_average: float                    # MA over configured window
    moving_average_window: int
    slope: float                             # linear regression slope
    intercept: float                         # linear regression intercept
    r_squared: float                         # coefficient of determination
    predicted_next: float                    # extrapolated next-iteration value
    direction: str                           # "improving", "declining", "stable"


@dataclass
class DimensionProgress:
    dimension_id: str
    history: list[ScorePoint]
    current_value: float
    baseline_value: float | None
    target_value: float
    trend: TrendStats
    iterations_to_target: int | None         # estimated, None if unreachable


@dataclass
class ProgressReport:
    """Version-over-version progress tracking output."""
    report_id: str
    timestamp: datetime
    total_iterations: int
    dimension_progress: dict[str, DimensionProgress]
    composite_history: list[ScorePoint]
    composite_trend: TrendStats
    category_trends: dict[str, TrendStats]
    best_improving_dimensions: list[str]     # top-3 most improved
    worst_stalling_dimensions: list[str]     # top-3 most stalled


class IterationTracker:
    """Tracks scores across iterations and computes trend statistics.

    Stores all historical data and produces ProgressReports with
    moving averages and linear regression for each dimension.
    """

    def __init__(
        self,
        ma_window: int = 5,
        stability_slope_threshold: float = 0.001,
    ) -> None:
        self.ma_window = ma_window
        self.stability_threshold = stability_slope_threshold
        self._dimension_history: dict[str, list[ScorePoint]] = {}
        self._composite_history: list[ScorePoint] = []
        self._category_history: dict[str, list[ScorePoint]] = {}

    def record(self, report: SelfEvalReport, iteration: int) -> None:
        """Record a complete self-evaluation report."""
        ts = report.timestamp

        self._composite_history.append(
            ScorePoint(iteration, ts, report.composite_score)
        )

        for cat, score in report.category_scores.items():
            self._category_history.setdefault(cat, []).append(
                ScorePoint(iteration, ts, score)
            )

        for dim_id, result in report.results.items():
            if result.is_valid:
                self._dimension_history.setdefault(dim_id, []).append(
                    ScorePoint(iteration, ts, result.value)
                )

    def generate_report(
        self,
        baseline: Baseline | None = None,
    ) -> ProgressReport:
        """Generate a comprehensive progress report."""
        dim_progress: dict[str, DimensionProgress] = {}
        for dim_id, history in self._dimension_history.items():
            spec = DIMENSION_SPECS.get(dim_id)
            trend = self._compute_trend(history)
            baseline_val = (
                baseline.dimension_scores.get(dim_id)
                if baseline
                else None
            )
            target_val = spec.target if spec else 1.0
            dim_progress[dim_id] = DimensionProgress(
                dimension_id=dim_id,
                history=history,
                current_value=history[-1].value if history else 0.0,
                baseline_value=baseline_val,
                target_value=target_val,
                trend=trend,
                iterations_to_target=self._estimate_iterations_to_target(
                    history, target_val, trend, spec
                ),
            )

        composite_trend = self._compute_trend(self._composite_history)
        cat_trends = {
            cat: self._compute_trend(hist)
            for cat, hist in self._category_history.items()
        }

        improving = sorted(
            dim_progress.values(),
            key=lambda d: d.trend.slope,
            reverse=True,
        )
        stalling = sorted(
            dim_progress.values(),
            key=lambda d: abs(d.trend.slope),
        )

        return ProgressReport(
            report_id=uuid.uuid4().hex[:12],
            timestamp=datetime.now(timezone.utc),
            total_iterations=len(self._composite_history),
            dimension_progress=dim_progress,
            composite_history=self._composite_history,
            composite_trend=composite_trend,
            category_trends=cat_trends,
            best_improving_dimensions=[
                d.dimension_id for d in improving[:3]
            ],
            worst_stalling_dimensions=[
                d.dimension_id for d in stalling[:3]
            ],
        )

    def _compute_trend(self, points: list[ScorePoint]) -> TrendStats:
        """Compute moving average and linear regression over score points."""
        if not points:
            return TrendStats(0.0, self.ma_window, 0.0, 0.0, 0.0, 0.0, "stable")

        values = [p.value for p in points]

        window = min(self.ma_window, len(values))
        ma = sum(values[-window:]) / window

        slope, intercept, r_sq = self._linear_regression(values)

        predicted = slope * (len(values)) + intercept

        if abs(slope) < self.stability_threshold:
            direction = "stable"
        elif slope > 0:
            direction = "improving"
        else:
            direction = "declining"

        return TrendStats(
            moving_average=ma,
            moving_average_window=window,
            slope=slope,
            intercept=intercept,
            r_squared=r_sq,
            predicted_next=predicted,
            direction=direction,
        )

    @staticmethod
    def _linear_regression(
        values: list[float],
    ) -> tuple[float, float, float]:
        """Ordinary least squares: y = slope * x + intercept.

        Returns (slope, intercept, r_squared).
        """
        n = len(values)
        if n < 2:
            return 0.0, values[0] if values else 0.0, 0.0

        x_vals = list(range(n))
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n

        ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
        ss_xx = sum((x - x_mean) ** 2 for x in x_vals)
        ss_yy = sum((y - y_mean) ** 2 for y in values)

        if ss_xx == 0:
            return 0.0, y_mean, 0.0

        slope = ss_xy / ss_xx
        intercept = y_mean - slope * x_mean
        r_sq = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy != 0 else 0.0

        return slope, intercept, r_sq

    def _estimate_iterations_to_target(
        self,
        history: list[ScorePoint],
        target: float,
        trend: TrendStats,
        spec: DimensionSpec | None,
    ) -> int | None:
        """Estimate how many more iterations to reach target at current rate."""
        if not history or trend.slope == 0:
            return None

        current = history[-1].value
        if spec and spec.direction == ImprovementDirection.HIGHER_IS_BETTER:
            remaining = target - current
            if remaining <= 0:
                return 0
            if trend.slope <= 0:
                return None
            return max(1, math.ceil(remaining / trend.slope))
        else:
            remaining = current - target
            if remaining <= 0:
                return 0
            if trend.slope >= 0:
                return None
            return max(1, math.ceil(remaining / abs(trend.slope)))
```

---

## 7. Convergence Checker

The `ConvergenceChecker` implements four statistical methods from domain_knowledge.md ?3.4 to determine when the self-improvement cycle should terminate. Convergence is declared by **majority vote**: ?3 of 4 methods must agree.

### 7.1 Mathematical Definitions

#### Method 1: Sliding Window Variance

Given score series \(S = [s_1, s_2, \ldots, s_n]\) and window size \(w\):

$$\bar{s}_w = \frac{1}{w} \sum_{i=n-w+1}^{n} s_i$$

$$\sigma^2_w = \frac{1}{w} \sum_{i=n-w+1}^{n} (s_i - \bar{s}_w)^2$$

**Converged** when \(\sigma^2_w < \tau_{var}\) where \(\tau_{var} = 0.001\) (default).

*Interpretation*: the last \(w\) scores have near-zero variance, indicating the system has settled at a stable performance level.

#### Method 2: Relative Improvement Rate

Given window \(w\), compute per-step relative improvement:

$$r_i = \frac{s_i - s_{i-1}}{|s_{i-1}|}, \quad i \in [n-w+1, n]$$

$$\bar{r}_w = \frac{1}{w} \sum r_i$$

**Converged** when \(\bar{r}_w < \tau_{imp}\) where \(\tau_{imp} = 0.005\) (0.5% default).

*Interpretation*: the average per-step improvement rate has dropped below the minimum meaningful threshold ? further iterations yield diminishing returns.

#### Method 3: Mann-Kendall Trend Test

A non-parametric test for monotonic trend. Given \(n\) observations, compute the S statistic:

$$S = \sum_{i=1}^{n-1} \sum_{j=i+1}^{n} \text{sgn}(s_j - s_i)$$

where \(\text{sgn}(x) = \begin{cases} +1 & x > 0 \\ 0 & x = 0 \\ -1 & x < 0 \end{cases}\)

Kendall's tau:

$$\tau = \frac{2S}{n(n-1)}$$

Variance of S (under the null hypothesis of no trend):

$$\text{Var}(S) = \frac{n(n-1)(2n+5)}{18}$$

Z-statistic with continuity correction:

$$Z = \begin{cases} \frac{S-1}{\sqrt{\text{Var}(S)}} & S > 0 \\ 0 & S = 0 \\ \frac{S+1}{\sqrt{\text{Var}(S)}} & S < 0 \end{cases}$$

**Converged** when \(|Z| \leq 1.96\) (no significant trend at 95% confidence).

*Interpretation*: if the Mann-Kendall test finds no statistically significant upward or downward trend in recent scores, the system has plateaued.

#### Method 4: CUSUM (Cumulative Sum) Change Detection

Using the initial \(k=5\) observations as reference mean \(\mu_0\):

$$\mu_0 = \frac{1}{k} \sum_{i=1}^{k} s_i$$

Cumulative sums for upward and downward shifts:

$$S^+_i = \max(0, S^+_{i-1} + (s_i - \mu_0) - \delta)$$
$$S^-_i = \max(0, S^-_{i-1} - (s_i - \mu_0) - \delta)$$

where \(\delta = 0.5\) (allowable drift).

**Change detected** when \(S^+_i > h\) or \(S^-_i > h\) where \(h = 1.0\) (threshold).
**Converged** when no change is detected (both cumulative sums stay below threshold).

*Interpretation*: CUSUM detects whether scores have shifted away from the reference mean. If no shift is detected, the process is stable.

### 7.2 Composite Convergence Decision

```
Method Results: [sliding_var, rel_improvement, mann_kendall, cusum_stable]
                     ?             ?                ?            ?
                  bool          bool             bool         bool
                     ?             ?                ?            ?
                     ?????????????????????????????????????????????
                                ?                          ?
                           count(True) ? 3?                ?
                                ?                          ?
                          ?????????????                    ?
                          ?           ?                    ?
                         YES         NO                    ?
                          ?           ?                    ?
                    ????????????? ???????????             ?
                    ? CONVERGED ? ?  ACTIVE  ?    confidence = count/4
                    ????????????? ???????????
```

### 7.3 Interface Definition

```python
@dataclass
class ConvergenceMethodResult:
    method_name: str
    is_converged: bool
    detail: str


@dataclass
class ConvergenceReport:
    """Output of the composite convergence check."""
    is_converged: bool
    confidence: float                        # agreeing_count / total_methods
    methods_agreeing: int
    total_methods: int
    method_results: list[ConvergenceMethodResult]
    recommendation: str                      # "continue", "confirm", "terminate", "investigate"


class ConvergenceChecker:
    """Implements 4-method composite convergence detection.

    Parameters:
        window: sliding window size for variance and improvement rate methods.
        variance_threshold: ?? threshold for Method 1.
        min_improvement: minimum relative improvement rate for Method 2.
        mk_confidence: Z-score threshold for Mann-Kendall (Method 3).
        cusum_threshold: h parameter for CUSUM (Method 4).
        cusum_drift: ? parameter for CUSUM (Method 4).
        min_data_points: minimum observations before any convergence check.
        majority: number of methods that must agree.
    """

    def __init__(
        self,
        window: int = 5,
        variance_threshold: float = 0.001,
        min_improvement: float = 0.005,
        mk_confidence: float = 1.96,
        cusum_threshold: float = 1.0,
        cusum_drift: float = 0.5,
        min_data_points: int = 5,
        majority: int = 3,
    ) -> None:
        self.window = window
        self.variance_threshold = variance_threshold
        self.min_improvement = min_improvement
        self.mk_confidence = mk_confidence
        self.cusum_threshold = cusum_threshold
        self.cusum_drift = cusum_drift
        self.min_data_points = min_data_points
        self.majority = majority

    def check(self, scores: list[float]) -> ConvergenceReport:
        """Run all four convergence methods and return composite decision."""
        if len(scores) < self.min_data_points:
            return ConvergenceReport(
                is_converged=False,
                confidence=0.0,
                methods_agreeing=0,
                total_methods=4,
                method_results=[],
                recommendation="continue",
            )

        results = [
            self._check_sliding_variance(scores),
            self._check_relative_improvement(scores),
            self._check_mann_kendall(scores),
            self._check_cusum(scores),
        ]

        agreeing = sum(1 for r in results if r.is_converged)
        confidence = agreeing / len(results)
        converged = agreeing >= self.majority

        recommendation = self._determine_recommendation(
            converged, confidence, results, scores
        )

        return ConvergenceReport(
            is_converged=converged,
            confidence=confidence,
            methods_agreeing=agreeing,
            total_methods=len(results),
            method_results=results,
            recommendation=recommendation,
        )

    def check_per_dimension(
        self,
        dimension_histories: dict[str, list[float]],
    ) -> dict[str, ConvergenceReport]:
        """Check convergence independently for each dimension."""
        return {
            dim_id: self.check(scores)
            for dim_id, scores in dimension_histories.items()
        }

    def _check_sliding_variance(
        self, scores: list[float]
    ) -> ConvergenceMethodResult:
        w = min(self.window, len(scores))
        window = scores[-w:]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        converged = variance < self.variance_threshold
        return ConvergenceMethodResult(
            method_name="sliding_window_variance",
            is_converged=converged,
            detail=f"variance={variance:.6f}, threshold={self.variance_threshold}",
        )

    def _check_relative_improvement(
        self, scores: list[float]
    ) -> ConvergenceMethodResult:
        w = min(3, len(scores) - 1)
        if w < 1:
            return ConvergenceMethodResult(
                "relative_improvement", False, "insufficient data"
            )
        improvements = []
        for i in range(-w, 0):
            prev = scores[i - 1]
            curr = scores[i]
            if prev != 0:
                improvements.append((curr - prev) / abs(prev))
            else:
                improvements.append(0.0)
        avg = sum(improvements) / len(improvements)
        converged = avg < self.min_improvement
        return ConvergenceMethodResult(
            method_name="relative_improvement_rate",
            is_converged=converged,
            detail=f"avg_improvement={avg:.6f}, threshold={self.min_improvement}",
        )

    def _check_mann_kendall(
        self, scores: list[float]
    ) -> ConvergenceMethodResult:
        w = min(max(self.window, 4), len(scores))
        recent = scores[-w:]
        n = len(recent)

        if n < 4:
            return ConvergenceMethodResult(
                "mann_kendall", False, "insufficient data (need ?4)"
            )

        s = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                diff = recent[j] - recent[i]
                if diff > 0:
                    s += 1
                elif diff < 0:
                    s -= 1

        tau = s / (n * (n - 1) / 2)
        var_s = n * (n - 1) * (2 * n + 5) / 18

        if s > 0:
            z = (s - 1) / math.sqrt(var_s)
        elif s < 0:
            z = (s + 1) / math.sqrt(var_s)
        else:
            z = 0.0

        significant_trend = abs(z) > self.mk_confidence
        converged = not significant_trend

        return ConvergenceMethodResult(
            method_name="mann_kendall_trend",
            is_converged=converged,
            detail=f"tau={tau:.4f}, z={z:.4f}, significant={significant_trend}",
        )

    def _check_cusum(
        self, scores: list[float]
    ) -> ConvergenceMethodResult:
        if len(scores) < 5:
            return ConvergenceMethodResult(
                "cusum", False, "insufficient data (need ?5)"
            )

        reference_mean = sum(scores[:5]) / 5
        s_pos = 0.0
        s_neg = 0.0

        for x in scores[5:]:
            s_pos = max(0.0, s_pos + (x - reference_mean) - self.cusum_drift)
            s_neg = max(0.0, s_neg - (x - reference_mean) - self.cusum_drift)

        change_detected = s_pos > self.cusum_threshold or s_neg > self.cusum_threshold
        converged = not change_detected

        return ConvergenceMethodResult(
            method_name="cusum_stability",
            is_converged=converged,
            detail=f"S+={s_pos:.4f}, S-={s_neg:.4f}, "
                   f"threshold={self.cusum_threshold}, stable={converged}",
        )

    def _determine_recommendation(
        self,
        converged: bool,
        confidence: float,
        results: list[ConvergenceMethodResult],
        scores: list[float],
    ) -> str:
        """Map convergence state to an actionable recommendation.

        States from self_eval_spec.md ?9.3:
        - Active Improvement: ?2 methods agree ? "continue"
        - Near Convergence: 3 agree but still improving >0.5% ? "confirm"
        - Converged: ?3 agree, delta <0.5% for 3 iters ? "terminate"
        - Oscillating: MK no trend but CUSUM detects changes ? "investigate"
        - Regressing: MK shows negative trend ? "investigate"
        """
        if not converged:
            mk = next(
                (r for r in results if r.method_name == "mann_kendall_trend"),
                None,
            )
            cusum = next(
                (r for r in results if r.method_name == "cusum_stability"),
                None,
            )
            if mk and cusum and mk.is_converged and not cusum.is_converged:
                return "investigate"
            return "continue"

        if len(scores) >= 3:
            recent_deltas = [
                abs(scores[i] - scores[i - 1]) / max(abs(scores[i - 1]), 1e-9)
                for i in range(-2, 0)
            ]
            if any(d > 0.005 for d in recent_deltas):
                return "confirm"

        return "terminate"
```

---

## 8. MAPIM Loop Orchestration

The `MAPIMOrchestrator` ties all components together into the Measure ? Analyze ? Plan ? Improve ? Measure cycle. It enforces termination conditions and handles edge cases.

### 8.1 Loop State Machine

```
                          ???????????????
                          ?    IDLE      ?
                          ???????????????
                                 ? start()
                                 ?
     ???????????          ???????????????
     ?ESCALATED????????????  MEASURING  ???????????????????????????????????????
     ???????????  error   ???????????????                                     ?
                                 ? SelfEvalRunner.run()                       ?
                                 ?                                            ?
                          ???????????????                                     ?
                          ?  ANALYZING  ?                                     ?
                          ???????????????                                     ?
                                 ? GapDetector.detect()                       ?
                                 ? ConvergenceChecker.check()                 ?
                                 ?                                            ?
                          ???????????????    terminate                        ?
                          ? CONVERGED?  ???????????????? COMPLETED             ?
                          ???????????????                                     ?
                                 ? not converged                              ?
                                 ?                                            ?
                          ???????????????    max_iters                        ?
                          ?  PLANNING   ???????????????? EXHAUSTED             ?
                          ???????????????                                     ?
                                 ? ImprovementPlanner.plan()                  ?
                                 ?                                            ?
                          ???????????????    stagnation                       ?
                          ?  IMPROVING  ???????????????? STAGNATED             ?
                          ???????????????                                     ?
                                 ? execute actions                            ?
                                 ?                                            ?
                                 ??????????????????????????????????????????????
```

### 8.2 Termination Conditions

| Condition | Trigger | Action |
|-----------|---------|--------|
| **Converged** | ConvergenceChecker returns `terminate` | Stop loop, generate final ProgressReport |
| **Max iterations** | `iteration >= max_iterations` | Stop loop, generate report with warning |
| **Stagnation** | composite_delta < 0.001 for `stagnation_window` consecutive iterations | Stop loop, escalate for manual review |
| **Regression** | composite score drops >5% from peak | Pause, rollback last action, investigate |
| **Critical failure** | DimensionResult.error on ?3 dimensions | Halt, escalate immediately |

### 8.3 Escalation Policy

```
Level 0 (Auto-handled):
  - Single dimension error ? skip dimension, log warning, continue
  - Minor regression (<2%) ? increase priority of regressed dimension

Level 1 (Logged alert):
  - Stagnation detected ? log stagnation report, suggest manual intervention
  - 2 dimensions in error ? log alert, continue with degraded coverage

Level 2 (Halt):
  - ?3 dimensions in error ? halt loop, require manual restart
  - Composite regression >5% from peak ? halt, rollback suggestion
  - Oscillation detected (ConvergenceChecker recommendation="investigate") for
    3 consecutive iterations ? halt, require parameter review
```

### 8.4 Interface Definition

```python
class LoopState(Enum):
    IDLE = "idle"
    MEASURING = "measuring"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    IMPROVING = "improving"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"
    STAGNATED = "stagnated"
    ESCALATED = "escalated"


@dataclass
class LoopConfig:
    max_iterations: int = 10
    stagnation_window: int = 3
    stagnation_threshold: float = 0.001
    regression_threshold: float = 0.05
    max_dimension_errors: int = 3
    convergence_params: dict[str, Any] = field(default_factory=lambda: {
        "window": 5,
        "variance_threshold": 0.001,
        "min_improvement": 0.005,
        "mk_confidence": 1.96,
        "cusum_threshold": 1.0,
        "cusum_drift": 0.5,
    })


@dataclass
class IterationRecord:
    """Record of a single MAPIM iteration for audit trail."""
    iteration: int
    phase: IterationPhase
    report: SelfEvalReport | None = None
    gap_analysis: GapAnalysisReport | None = None
    convergence: ConvergenceReport | None = None
    improvement_plan: ImprovementPlan | None = None
    actions_executed: list[str] = field(default_factory=list)
    composite_score: float = 0.0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class LoopResult:
    """Final output of a complete MAPIM loop run."""
    termination_reason: str                  # "converged", "exhausted", "stagnated", "escalated"
    total_iterations: int
    iteration_records: list[IterationRecord]
    final_report: SelfEvalReport | None
    progress_report: ProgressReport | None
    final_convergence: ConvergenceReport | None


class MAPIMOrchestrator:
    """Orchestrates the full Measure?Analyze?Plan?Improve?Measure loop.

    This is the top-level entry point for NineS self-iteration. It owns
    the loop lifecycle and delegates to the five core components.
    """

    def __init__(
        self,
        eval_runner: SelfEvalRunner,
        baseline_manager: BaselineManager,
        gap_detector: GapDetector,
        planner: ImprovementPlanner,
        tracker: IterationTracker,
        convergence_checker: ConvergenceChecker,
        config: LoopConfig | None = None,
        action_executor: ActionExecutor | None = None,
    ) -> None:
        self.eval_runner = eval_runner
        self.baseline_manager = baseline_manager
        self.gap_detector = gap_detector
        self.planner = planner
        self.tracker = tracker
        self.convergence_checker = convergence_checker
        self.config = config or LoopConfig()
        self.action_executor = action_executor

        self.state = LoopState.IDLE
        self._records: list[IterationRecord] = []
        self._composite_scores: list[float] = []
        self._peak_composite: float = 0.0

    def run(
        self,
        nines_version: str,
        baseline_version: str | None = None,
    ) -> LoopResult:
        """Execute the full MAPIM loop until termination."""
        baseline = None
        if baseline_version:
            baseline = self.baseline_manager.load(baseline_version)
        elif (latest := self.baseline_manager.load_latest()):
            baseline = latest

        history: list[SelfEvalReport] = []

        for iteration in range(self.config.max_iterations):
            record = IterationRecord(iteration=iteration, phase=IterationPhase.MEASURE)

            # ?? M: MEASURE ??
            self.state = LoopState.MEASURING
            context = EvalContext(nines_version=nines_version)
            report = self.eval_runner.run(context)
            record.report = report
            record.composite_score = report.composite_score
            history.append(report)
            self.tracker.record(report, iteration)
            self._composite_scores.append(report.composite_score)
            self._peak_composite = max(
                self._peak_composite, report.composite_score
            )

            error_count = sum(
                1 for r in report.results.values() if not r.is_valid
            )
            if error_count >= self.config.max_dimension_errors:
                self.state = LoopState.ESCALATED
                record.phase = IterationPhase.MEASURE
                self._records.append(record)
                return self._build_result(
                    "escalated", report, baseline
                )

            # ?? A: ANALYZE ??
            self.state = LoopState.ANALYZING
            record.phase = IterationPhase.ANALYZE
            gap_analysis = self.gap_detector.detect(
                report, baseline, history
            )
            record.gap_analysis = gap_analysis

            convergence = self.convergence_checker.check(
                self._composite_scores
            )
            record.convergence = convergence

            if convergence.recommendation == "terminate":
                self.state = LoopState.COMPLETED
                self._records.append(record)
                return self._build_result(
                    "converged", report, baseline
                )

            if self._detect_regression(report):
                self.state = LoopState.ESCALATED
                self._records.append(record)
                return self._build_result(
                    "escalated", report, baseline
                )

            if self._detect_stagnation():
                self.state = LoopState.STAGNATED
                self._records.append(record)
                return self._build_result(
                    "stagnated", report, baseline
                )

            # ?? P: PLAN ??
            self.state = LoopState.PLANNING
            record.phase = IterationPhase.PLAN
            plan = self.planner.plan(gap_analysis, history)
            record.improvement_plan = plan

            # ?? I: IMPROVE ??
            self.state = LoopState.IMPROVING
            record.phase = IterationPhase.IMPROVE
            if self.action_executor:
                executed = self.action_executor.execute(plan)
                record.actions_executed = executed

            self._records.append(record)

        self.state = LoopState.EXHAUSTED
        return self._build_result(
            "exhausted",
            history[-1] if history else None,
            baseline,
        )

    def _detect_regression(self, report: SelfEvalReport) -> bool:
        if self._peak_composite == 0:
            return False
        drop = (self._peak_composite - report.composite_score) / self._peak_composite
        return drop > self.config.regression_threshold

    def _detect_stagnation(self) -> bool:
        w = self.config.stagnation_window
        if len(self._composite_scores) < w + 1:
            return False
        recent = self._composite_scores[-w:]
        deltas = [abs(recent[i] - recent[i - 1]) for i in range(1, len(recent))]
        return all(d < self.config.stagnation_threshold for d in deltas)

    def _build_result(
        self,
        reason: str,
        final_report: SelfEvalReport | None,
        baseline: Baseline | None,
    ) -> LoopResult:
        progress = self.tracker.generate_report(baseline)
        final_convergence = (
            self.convergence_checker.check(self._composite_scores)
            if self._composite_scores
            else None
        )
        return LoopResult(
            termination_reason=reason,
            total_iterations=len(self._records),
            iteration_records=self._records,
            final_report=final_report,
            progress_report=progress,
            final_convergence=final_convergence,
        )


class ActionExecutor(ABC):
    """Interface for executing improvement actions.

    MVP implementation logs actions for manual execution.
    Future versions will apply automated code changes.
    """

    @abstractmethod
    def execute(self, plan: ImprovementPlan) -> list[str]:
        """Execute actions from the plan. Returns list of executed action IDs."""
        ...


class LoggingActionExecutor(ActionExecutor):
    """MVP executor that logs actions for manual follow-up."""

    def execute(self, plan: ImprovementPlan) -> list[str]:
        import logging
        logger = logging.getLogger("nines.self_iteration")
        executed = []
        for action in plan.actions_by_priority():
            logger.info(
                "IMPROVEMENT ACTION [%s] priority=%d: %s (modules: %s)",
                action.id,
                action.priority,
                action.description,
                action.target_modules,
            )
            executed.append(action.id)
        return executed
```

---

## 9. Growth Tracking

Growth tracking measures how improvement in one capability vertex triggers improvement in the others. This implements the cross-vertex synergy concept from capability_model.md ?5 and drives the D19 (Cross-Vertex Synergy Score) dimension.

### 9.1 Synergy Measurement Framework

The three-vertex model produces six directed data flows (F1?F6). Growth tracking quantifies the strength of each flow as measured by lagged score correlations.

```
                    V1 Score Series
                  ???????????????????
                  ? [0.72, 0.75, 0.78, 0.80, 0.82] ?
                  ???????????????????????????????????
                           ?      ?
              r(?V1[t],    ?      ?  r(?V1[t],
              ?V2[t+1])    ?      ?  ?V3[t+1])
                           ?      ?
                           ?      ?
    V2 Score Series                    V3 Score Series
  ???????????????????               ???????????????????
  ? [0.85, 0.86, 0.88, 0.89, 0.91]? ? [0.65, 0.67, 0.70, 0.72, 0.74]?
  ???????????????????               ???????????????????
            ?                                   ?
            ?     r(?V2[t], ?V3[t+1])          ?
            ?????????????????????????????????????
```

### 9.2 Concrete Metrics

| Metric | Definition | Formula | Target |
|--------|-----------|---------|--------|
| **Pairwise Lagged Correlation** | Pearson correlation between score delta in vertex A at iteration t and score delta in vertex B at iteration t+1 | \(r(\Delta V_a[t], \Delta V_b[t+1])\) | > 0.3 (positive reinforcement) |
| **Mean Synergy Score** | Average of all 6 pairwise lagged correlations | \(\bar{r} = \frac{1}{6}\sum_{(a,b)} r(\Delta V_a, \Delta V_b)\) | > 0.2 |
| **Cross-Vertex Trigger Rate** | Actions in vertex B triggered per vertex A output | \(\text{triggers}_B / \text{outputs}_A\) | Increasing over iterations |
| **Gap Closure Velocity** | Iterations from gap detection (V1) to gap closure (re-eval passes target) | \(t_{closed} - t_{detected}\) | Decreasing over iterations |
| **Knowledge Amplification Factor** | Knowledge units (V3) produced per source (V2) discovered | \(\text{KU}_{new} / \text{sources}_{new}\) | > 5.0 and increasing |
| **Synergy Acceleration** | Rate of change of mean synergy score | \(\frac{d\bar{r}}{dt}\) | > 0 (accelerating reinforcement) |

### 9.3 Interface Definition

```python
@dataclass
class VertexScores:
    """Per-vertex aggregate scores at one iteration."""
    iteration: int
    timestamp: datetime
    v1_score: float
    v2_score: float
    v3_score: float


@dataclass
class SynergyPair:
    """Correlation result for one directed vertex pair."""
    source_vertex: str                       # e.g. "V1"
    target_vertex: str                       # e.g. "V2"
    correlation: float                       # Pearson r of lagged deltas
    p_value: float | None                    # statistical significance
    sample_size: int
    interpretation: str                      # "reinforcing", "independent", "competing"


@dataclass
class GrowthReport:
    """Complete cross-vertex growth tracking output."""
    report_id: str
    timestamp: datetime
    total_iterations: int
    synergy_pairs: list[SynergyPair]         # 6 directed pairs
    mean_synergy_score: float
    synergy_acceleration: float              # ?(mean synergy) over last 3 iterations
    trigger_rates: dict[str, float]          # "V1?V2" ? rate
    gap_closure_velocity: float | None       # mean iterations to close a gap
    knowledge_amplification: float | None
    vertex_score_history: list[VertexScores]
    interpretation: str                      # summary assessment


class GrowthTracker:
    """Tracks cross-vertex synergy and growth dynamics.

    Requires at least 5 iteration data points to compute
    meaningful correlations (self_eval_spec.md D19 baseline).
    """

    MIN_HISTORY_FOR_CORRELATION = 5

    def __init__(self) -> None:
        self._vertex_history: list[VertexScores] = []
        self._trigger_counts: dict[str, list[int]] = {
            "V1?V2": [], "V1?V3": [],
            "V2?V1": [], "V2?V3": [],
            "V3?V1": [], "V3?V2": [],
        }
        self._gap_closures: list[int] = []

    def record_iteration(
        self,
        report: SelfEvalReport,
        iteration: int,
    ) -> None:
        """Record per-vertex scores from a self-eval report."""
        self._vertex_history.append(VertexScores(
            iteration=iteration,
            timestamp=report.timestamp,
            v1_score=report.category_scores.get("V1_evaluation", 0.0),
            v2_score=report.category_scores.get("V2_search", 0.0),
            v3_score=report.category_scores.get("V3_analysis", 0.0),
        ))

    def record_trigger(self, flow: str, count: int) -> None:
        """Record cross-vertex trigger count for a flow (e.g. 'V1?V2')."""
        if flow in self._trigger_counts:
            self._trigger_counts[flow].append(count)

    def record_gap_closure(self, iterations_to_close: int) -> None:
        """Record how many iterations it took to close a gap."""
        self._gap_closures.append(iterations_to_close)

    def generate_report(self) -> GrowthReport:
        """Generate a comprehensive growth tracking report."""
        synergy_pairs = self._compute_all_synergy_pairs()
        mean_synergy = (
            sum(p.correlation for p in synergy_pairs) / len(synergy_pairs)
            if synergy_pairs
            else 0.0
        )

        trigger_rates = {}
        for flow, counts in self._trigger_counts.items():
            trigger_rates[flow] = (
                sum(counts) / len(counts) if counts else 0.0
            )

        gap_velocity = (
            sum(self._gap_closures) / len(self._gap_closures)
            if self._gap_closures
            else None
        )

        acceleration = self._compute_synergy_acceleration()

        interpretation = self._interpret(mean_synergy, synergy_pairs)

        return GrowthReport(
            report_id=uuid.uuid4().hex[:12],
            timestamp=datetime.now(timezone.utc),
            total_iterations=len(self._vertex_history),
            synergy_pairs=synergy_pairs,
            mean_synergy_score=mean_synergy,
            synergy_acceleration=acceleration,
            trigger_rates=trigger_rates,
            gap_closure_velocity=gap_velocity,
            knowledge_amplification=None,
            vertex_score_history=list(self._vertex_history),
            interpretation=interpretation,
        )

    def _compute_all_synergy_pairs(self) -> list[SynergyPair]:
        """Compute lagged Pearson correlation for all 6 directed vertex pairs."""
        if len(self._vertex_history) < self.MIN_HISTORY_FOR_CORRELATION:
            return []

        scores = {
            "V1": [v.v1_score for v in self._vertex_history],
            "V2": [v.v2_score for v in self._vertex_history],
            "V3": [v.v3_score for v in self._vertex_history],
        }

        deltas: dict[str, list[float]] = {}
        for vertex, vals in scores.items():
            deltas[vertex] = [
                vals[i] - vals[i - 1] for i in range(1, len(vals))
            ]

        pairs = []
        for src in ["V1", "V2", "V3"]:
            for tgt in ["V1", "V2", "V3"]:
                if src == tgt:
                    continue
                src_deltas = deltas[src][:-1]
                tgt_deltas = deltas[tgt][1:]
                n = min(len(src_deltas), len(tgt_deltas))
                if n < 3:
                    continue
                r = self._pearson_correlation(
                    src_deltas[:n], tgt_deltas[:n]
                )
                pairs.append(SynergyPair(
                    source_vertex=src,
                    target_vertex=tgt,
                    correlation=r,
                    p_value=None,
                    sample_size=n,
                    interpretation=self._interpret_pair(r),
                ))
        return pairs

    @staticmethod
    def _pearson_correlation(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient between two series."""
        n = len(x)
        if n < 2:
            return 0.0
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        cov = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        std_x = math.sqrt(sum((xi - x_mean) ** 2 for xi in x))
        std_y = math.sqrt(sum((yi - y_mean) ** 2 for yi in y))
        if std_x == 0 or std_y == 0:
            return 0.0
        return cov / (std_x * std_y)

    def _compute_synergy_acceleration(self) -> float:
        """Compute rate of change of mean synergy over the last 3 checkpoints.

        Requires at least MIN_HISTORY_FOR_CORRELATION + 2 data points.
        """
        min_for_accel = self.MIN_HISTORY_FOR_CORRELATION + 2
        if len(self._vertex_history) < min_for_accel:
            return 0.0

        window_synergies = []
        for end_idx in range(
            self.MIN_HISTORY_FOR_CORRELATION,
            len(self._vertex_history) + 1,
        ):
            subset = self._vertex_history[:end_idx]
            scores = {
                "V1": [v.v1_score for v in subset],
                "V2": [v.v2_score for v in subset],
                "V3": [v.v3_score for v in subset],
            }
            deltas = {}
            for vertex, vals in scores.items():
                deltas[vertex] = [
                    vals[i] - vals[i - 1] for i in range(1, len(vals))
                ]
            corrs = []
            for src in ["V1", "V2", "V3"]:
                for tgt in ["V1", "V2", "V3"]:
                    if src == tgt:
                        continue
                    sd = deltas[src][:-1]
                    td = deltas[tgt][1:]
                    n = min(len(sd), len(td))
                    if n >= 3:
                        corrs.append(
                            self._pearson_correlation(sd[:n], td[:n])
                        )
            if corrs:
                window_synergies.append(sum(corrs) / len(corrs))

        if len(window_synergies) < 2:
            return 0.0

        recent = window_synergies[-3:] if len(window_synergies) >= 3 else window_synergies
        acceleration = (recent[-1] - recent[0]) / len(recent)
        return acceleration

    @staticmethod
    def _interpret_pair(r: float) -> str:
        if r > 0.3:
            return "reinforcing"
        if r < -0.3:
            return "competing"
        return "independent"

    @staticmethod
    def _interpret(mean_synergy: float, pairs: list[SynergyPair]) -> str:
        if not pairs:
            return "Insufficient data for synergy analysis (need ?5 iterations)."

        competing = sum(1 for p in pairs if p.interpretation == "competing")
        reinforcing = sum(
            1 for p in pairs if p.interpretation == "reinforcing"
        )

        if mean_synergy > 0.3:
            return (
                f"Strong mutual reinforcement (mean r={mean_synergy:.3f}). "
                f"{reinforcing}/6 pairs reinforcing. "
                "The three-vertex architecture is delivering compounding gains."
            )
        if mean_synergy > 0.1:
            return (
                f"Moderate reinforcement (mean r={mean_synergy:.3f}). "
                f"{reinforcing}/6 reinforcing, {competing}/6 competing. "
                "Cross-vertex data flows are partially effective."
            )
        if mean_synergy > -0.1:
            return (
                f"Vertices appear independent (mean r={mean_synergy:.3f}). "
                "Cross-vertex data flows may not be active. "
                "Check that F1?F6 flows are connected and producing artifacts."
            )
        return (
            f"Negative synergy detected (mean r={mean_synergy:.3f}). "
            f"{competing}/6 pairs competing. "
            "Improvement in one vertex is harming others. "
            "Investigate resource competition and conflicting optimization targets."
        )
```

---

## 10. Data Model Summary

### 10.1 Artifact Flow

| MAPIM Phase | Input Artifact | Output Artifact | Storage |
|-------------|---------------|-----------------|---------|
| **Measure** | `EvalContext` | `SelfEvalReport` | SQLite `eval_reports` table |
| **Analyze** | `SelfEvalReport` + `Baseline` | `GapAnalysisReport` | SQLite `gap_analyses` table |
| **Converge?** | `list[float]` (composite scores) | `ConvergenceReport` | SQLite `convergence_checks` table |
| **Plan** | `GapAnalysisReport` + history | `ImprovementPlan` | SQLite `improvement_plans` table |
| **Improve** | `ImprovementPlan` | action execution log | SQLite `action_log` table |
| **Track** | all reports | `ProgressReport`, `GrowthReport` | SQLite `progress_reports` table |
| **Baseline** | `SelfEvalReport` | `Baseline` | `data/baselines/{version}/` (JSON) |

### 10.2 Class Hierarchy

```
DimensionEvaluator (Protocol)
??? D01_ScoringAccuracyEvaluator
??? D02_EvaluationCoverageEvaluator
??? D03_ReliabilityEvaluator
??? ...
??? D19_CrossVertexSynergyEvaluator

normalize_dimension_value()   # standalone utility for [0,1] normalization

BaselineManager
??? establish(report) ? Baseline
??? load(version) ? Baseline
??? compare(base, report) ? BaselineDiff
??? list_versions() ? list[str]

GapDetector
??? detect(report, baseline, history) ? GapAnalysisReport

ImprovementPlanner
??? plan(gap_report, history) ? ImprovementPlan

IterationTracker
??? record(report, iteration)
??? generate_report(baseline) ? ProgressReport

ConvergenceChecker
??? check(scores) ? ConvergenceReport
??? check_per_dimension(histories) ? dict[str, ConvergenceReport]

GrowthTracker
??? record_iteration(report, iteration)
??? record_trigger(flow, count)
??? generate_report() ? GrowthReport

MAPIMOrchestrator
??? run(version, baseline_version) ? LoopResult

ActionExecutor (ABC)
??? LoggingActionExecutor (MVP)
```

### 10.3 Configuration Defaults

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `max_iterations` | 10 | Bounded loops per capability_model.md C5 |
| `convergence.window` | 5 | Balances responsiveness and stability |
| `convergence.variance_threshold` | 0.001 | <0.1% variance = effectively flat |
| `convergence.min_improvement` | 0.005 | <0.5% step improvement = diminishing returns |
| `convergence.mk_confidence` | 1.96 | 95% confidence interval (standard) |
| `convergence.cusum_threshold` | 1.0 | Tuned for typical [0,1] score ranges |
| `convergence.cusum_drift` | 0.5 | Allows natural noise without triggering |
| `convergence.majority` | 3 | ?3/4 methods must agree |
| `stagnation_window` | 3 | 3 flat iterations before declaring stagnation |
| `regression_threshold` | 0.05 | 5% drop from peak triggers halt |
| `min_eval_runs` | 3 | Per self_eval_spec.md reliability requirement |
| `planner.max_actions` | 3 | Bounded action set per iteration (FR-407: ?3 actions) |
| `planner.cross_vertex_bonus` | 0.20 | 20% priority boost for cross-vertex actions |
| `tracker.ma_window` | 5 | 5-iteration moving average |
| `growth.min_history` | 5 | Pearson r requires ?5 data points |

---

*Last modified: 2026-04-11T00:00:00Z*
