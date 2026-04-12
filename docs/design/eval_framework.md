# NineS Evaluation Framework Design

> **Task**: T12 — Evaluation Framework Design | **Team**: Design L3
> **Absorbs**: EvoBench patterns from `docs/research/evobench_migration_patterns.md`
> **Implements**: FR-101 through FR-116 from `docs/design/requirements.md`
> **Last Modified**: 2026-04-11

---

## Table of Contents

1. [Evaluation Dimensions](#1-evaluation-dimensions)
2. [Task Definition Format](#2-task-definition-format)
3. [Evaluation Pipeline](#3-evaluation-pipeline)
4. [Scorer Plugin System](#4-scorer-plugin-system)
5. [Matrix Evaluation](#5-matrix-evaluation)
6. [Reliability Metrics](#6-reliability-metrics)
7. [Budget Guards](#7-budget-guards)
8. [ADR — Key Differences from EvoBench](#8-adr--key-differences-from-evobench)

---

## 1. Evaluation Dimensions

EvoBench defines four dimensions (Tool, Model, Workflow, TaskType) designed to benchmark *external* AI agents. NineS has a fundamentally different scope — it evaluates capabilities across its own three-vertex model plus system health. The dimension system is purpose-built for NineS's self-referential evaluation loop.

### 1.1 Dimension Protocol

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable, Any

class DimensionCategory(Enum):
    """Top-level grouping aligned with NineS's three vertices + system health."""
    EVAL_QUALITY = "eval_quality"           # V1 — Evaluation & Benchmarking
    COLLECTION_QUALITY = "collection_quality"  # V2 — Information Search & Tracking
    ANALYSIS_DEPTH = "analysis_depth"        # V3 — Knowledge Analysis & Decomposition
    SYSTEM_HEALTH = "system_health"          # Cross-cutting operational concerns

class MetricDirection(Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"

class MetricValueType(Enum):
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    DURATION_SECONDS = "duration_seconds"

@dataclass(frozen=True)
class MetricDefinition:
    """A single measurable metric within a dimension."""
    name: str
    description: str
    value_type: MetricValueType
    direction: MetricDirection
    default_weight: float
    unit: str = ""
    min_value: float | None = None
    max_value: float | None = None

    def normalize(self, raw_value: float) -> float:
        """Normalize to [0, 1] scale, inverting LowerIsBetter metrics."""
        lo = self.min_value if self.min_value is not None else 0.0
        hi = self.max_value if self.max_value is not None else 1.0
        if hi == lo:
            return 1.0
        clamped = max(lo, min(raw_value, hi))
        normalized = (clamped - lo) / (hi - lo)
        if self.direction == MetricDirection.LOWER_IS_BETTER:
            return 1.0 - normalized
        return normalized

@runtime_checkable
class Dimension(Protocol):
    """Protocol that every evaluation dimension must satisfy."""
    def kind(self) -> str: ...
    def name(self) -> str: ...
    def description(self) -> str: ...
    def category(self) -> DimensionCategory: ...
    def metrics(self) -> list[MetricDefinition]: ...
    def default_scorer(self) -> Scorer: ...
    async def evaluate(self, context: EvalContext) -> DimensionScore: ...
```

### 1.2 NineS Dimension Definitions

NineS defines **six** evaluation dimensions organized by the three-vertex model:

| ID | Dimension | Category | Metrics (summarized) | Direction |
|----|-----------|----------|---------------------|-----------|
| **D-CQ** | Code Quality | V1 Eval Quality | Scoring accuracy, scorer agreement, output correctness | Higher is better |
| **D-AI** | Architecture Insight | V3 Analysis Depth | Pattern detection F1, layer recognition rate, coupling accuracy | Higher is better |
| **D-DD** | Decomposition Depth | V3 Analysis Depth | Coverage ratio, unit granularity, cross-cutting concern detection | Higher is better |
| **D-PR** | Pipeline Reliability | V1 Eval Quality / System | Pass^k consistency, determinism CV, sandbox isolation rate | Higher is better |
| **D-IF** | Information Freshness | V2 Collection Quality | Tracking lag, change detection recall, data completeness | Higher is better (after inversion of lag) |
| **D-SE** | System Efficiency | System Health | Pipeline latency p50/p95, throughput, memory footprint | Lower is better (latency) |

#### D-CQ: Code Quality

Measures how accurately NineS evaluates code. Drawn from self-eval dimensions D01 and D05.

```python
class CodeQualityDimension:
    def kind(self) -> str:
        return "code_quality"

    def name(self) -> str:
        return "Code Quality"

    def description(self) -> str:
        return (
            "Measures the accuracy and consistency of NineS's evaluation "
            "scoring against ground-truth golden test sets."
        )

    def category(self) -> DimensionCategory:
        return DimensionCategory.EVAL_QUALITY

    def metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition(
                name="scoring_accuracy",
                description="Agreement rate with golden test set labels",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.35,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="scorer_agreement",
                description="Pairwise Cohen's kappa across scorer implementations",
                value_type=MetricValueType.FLOAT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.25,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="output_correctness",
                description="Fraction of task outputs matching expected format",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.20,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="report_completeness",
                description="Fraction of required report sections present and valid",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.20,
                min_value=0.0, max_value=1.0,
            ),
        ]
```

#### D-AI: Architecture Insight

Measures NineS's ability to recognize software architecture patterns. Drawn from self-eval dimensions D12 and D15.

```python
class ArchitectureInsightDimension:
    def kind(self) -> str:
        return "architecture_insight"

    def name(self) -> str:
        return "Architecture Insight"

    def description(self) -> str:
        return (
            "Measures accuracy of architectural pattern detection, "
            "layer identification, and structural understanding."
        )

    def category(self) -> DimensionCategory:
        return DimensionCategory.ANALYSIS_DEPTH

    def metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition(
                name="pattern_detection_f1",
                description="F1 score for architecture pattern classification",
                value_type=MetricValueType.FLOAT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.30,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="layer_recognition_rate",
                description="Fraction of known layers correctly identified",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.25,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="coupling_accuracy",
                description="Agreement of computed coupling metrics with ground truth",
                value_type=MetricValueType.FLOAT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.25,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="boundary_violation_recall",
                description="Fraction of known violations detected",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.20,
                min_value=0.0, max_value=1.0,
            ),
        ]
```

#### D-DD: Decomposition Depth

Measures coverage and granularity of knowledge decomposition. Drawn from self-eval dimension D11.

```python
class DecompositionDepthDimension:
    def kind(self) -> str:
        return "decomposition_depth"

    def name(self) -> str:
        return "Decomposition Depth"

    def description(self) -> str:
        return (
            "Measures how thoroughly NineS decomposes codebases into "
            "atomic knowledge units across multiple strategies."
        )

    def category(self) -> DimensionCategory:
        return DimensionCategory.ANALYSIS_DEPTH

    def metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition(
                name="element_coverage",
                description="Fraction of analyzable elements captured as KnowledgeUnits",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.35,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="strategy_breadth",
                description="Number of active decomposition strategies / total available",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.20,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="cross_cutting_detection",
                description="Recall of known cross-cutting concerns identified",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.25,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="index_recall_at_10",
                description="Recall@10 on benchmark search queries",
                value_type=MetricValueType.FLOAT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.20,
                min_value=0.0, max_value=1.0,
            ),
        ]
```

#### D-PR: Pipeline Reliability

Measures determinism and consistency of the evaluation pipeline. Drawn from self-eval dimensions D03 and D17.

```python
class PipelineReliabilityDimension:
    def kind(self) -> str:
        return "pipeline_reliability"

    def name(self) -> str:
        return "Pipeline Reliability"

    def description(self) -> str:
        return (
            "Measures evaluation pipeline determinism, multi-run consistency, "
            "and sandbox isolation effectiveness."
        )

    def category(self) -> DimensionCategory:
        return DimensionCategory.EVAL_QUALITY

    def metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition(
                name="pass_k_consistency",
                description="Fraction of tasks with identical results across k runs",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.30,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="determinism_cv",
                description="Coefficient of variation across repeated runs (lower=more deterministic)",
                value_type=MetricValueType.FLOAT,
                direction=MetricDirection.LOWER_IS_BETTER,
                default_weight=0.25,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="sandbox_isolation_rate",
                description="Fraction of runs producing clean PollutionReport",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.30,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="seed_reproducibility",
                description="Output fingerprint match rate across same-seed runs",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.15,
                min_value=0.0, max_value=1.0,
            ),
        ]
```

#### D-IF: Information Freshness

Measures timeliness and completeness of information collection. Drawn from self-eval dimensions D07, D08, D09.

```python
class InformationFreshnessDimension:
    def kind(self) -> str:
        return "information_freshness"

    def name(self) -> str:
        return "Information Freshness"

    def description(self) -> str:
        return (
            "Measures how quickly and completely NineS detects changes "
            "in tracked information sources."
        )

    def category(self) -> DimensionCategory:
        return DimensionCategory.COLLECTION_QUALITY

    def metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition(
                name="tracking_lag_minutes",
                description="Median detection lag in minutes",
                value_type=MetricValueType.DURATION_SECONDS,
                direction=MetricDirection.LOWER_IS_BETTER,
                default_weight=0.25,
                unit="minutes",
                min_value=0.0, max_value=120.0,
            ),
            MetricDefinition(
                name="change_detection_recall",
                description="Fraction of actual changes correctly detected",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.30,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="data_completeness",
                description="Fraction of expected fields populated in collected entities",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.25,
                min_value=0.0, max_value=1.0,
            ),
            MetricDefinition(
                name="source_coverage",
                description="Fraction of configured sources that are reachable",
                value_type=MetricValueType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.20,
                min_value=0.0, max_value=1.0,
            ),
        ]
```

#### D-SE: System Efficiency

Measures operational performance of the NineS pipeline. Drawn from self-eval dimension D16.

```python
class SystemEfficiencyDimension:
    def kind(self) -> str:
        return "system_efficiency"

    def name(self) -> str:
        return "System Efficiency"

    def description(self) -> str:
        return (
            "Measures end-to-end pipeline latency, throughput, "
            "and resource consumption."
        )

    def category(self) -> DimensionCategory:
        return DimensionCategory.SYSTEM_HEALTH

    def metrics(self) -> list[MetricDefinition]:
        return [
            MetricDefinition(
                name="pipeline_latency_p50",
                description="Median end-to-end pipeline latency in seconds",
                value_type=MetricValueType.DURATION_SECONDS,
                direction=MetricDirection.LOWER_IS_BETTER,
                default_weight=0.30,
                unit="seconds",
                min_value=0.0, max_value=300.0,
            ),
            MetricDefinition(
                name="pipeline_latency_p95",
                description="95th percentile pipeline latency in seconds",
                value_type=MetricValueType.DURATION_SECONDS,
                direction=MetricDirection.LOWER_IS_BETTER,
                default_weight=0.20,
                unit="seconds",
                min_value=0.0, max_value=300.0,
            ),
            MetricDefinition(
                name="analysis_throughput",
                description="Files analyzed per minute",
                value_type=MetricValueType.FLOAT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                default_weight=0.25,
                unit="files/min",
                min_value=0.0, max_value=1000.0,
            ),
            MetricDefinition(
                name="peak_memory_mb",
                description="Peak RSS during a 100-task evaluation",
                value_type=MetricValueType.FLOAT,
                direction=MetricDirection.LOWER_IS_BETTER,
                default_weight=0.25,
                unit="MB",
                min_value=0.0, max_value=2048.0,
            ),
        ]
```

### 1.3 Dimension Registry

```python
class DimensionRegistry:
    """Central registry for all evaluation dimensions with weight validation."""

    def __init__(self) -> None:
        self._dimensions: dict[str, Dimension] = {}

    def register(self, dimension: Dimension) -> None:
        kind = dimension.kind()
        if kind in self._dimensions:
            raise ConfigError(f"Dimension '{kind}' already registered")
        self._validate_weights(dimension)
        self._dimensions[kind] = dimension

    def get(self, kind: str) -> Dimension:
        if kind not in self._dimensions:
            raise ConfigError(f"Unknown dimension: {kind}")
        return self._dimensions[kind]

    def list_by_category(self, category: DimensionCategory) -> list[Dimension]:
        return [d for d in self._dimensions.values() if d.category() == category]

    def all(self) -> list[Dimension]:
        return list(self._dimensions.values())

    @staticmethod
    def _validate_weights(dimension: Dimension) -> None:
        weights = [m.default_weight for m in dimension.metrics()]
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ConfigError(
                f"Dimension '{dimension.kind()}' metric weights sum to "
                f"{sum(weights):.6f}, expected 1.0"
            )
```

### 1.4 Mapping to Self-Eval Spec Dimensions

| NineS Eval Dimension | Self-Eval Spec Dimensions Covered |
|----------------------|-----------------------------------|
| D-CQ Code Quality | D01 Scoring Accuracy, D04 Report Quality, D05 Scorer Agreement |
| D-AI Architecture Insight | D12 Abstraction Quality, D15 Structure Recognition |
| D-DD Decomposition Depth | D11 Decomposition Coverage, D14 Index Recall |
| D-PR Pipeline Reliability | D03 Pass^k Consistency, D17 Sandbox Isolation |
| D-IF Information Freshness | D07 Tracking Freshness, D08 Change Detection, D09 Data Completeness, D06 Source Coverage |
| D-SE System Efficiency | D16 Pipeline Latency, D10 Collection Throughput |

Self-eval dimensions D02, D13, D18, D19 are covered as cross-cutting metrics within the composite aggregation formula (§1.5).

**Relationship to self-eval dimensions (M-04 clarification):** The 19 self-eval dimensions (D01–D19 from `self_eval_spec.md`) are the **canonical measurement system** — each has a concrete `DimensionEvaluator` that produces raw scores. The 6 eval framework dimensions (D-CQ, D-AI, etc.) defined here are **aggregation views** used for evaluation reporting and dashboard display. The eval framework consumes self-eval results rather than duplicating measurement logic. Consumers needing raw per-dimension data should use the self-eval API; consumers needing category-level summaries should use the eval framework dimensions.

### 1.5 Aggregate Scoring

The composite evaluation score uses the same formula defined in `self_eval_spec.md` §8.3:

```python
@dataclass
class AggregateWeights:
    """Configurable weights for composite scoring. Must sum to 1.0."""
    v1_eval_quality: float = 0.30
    v2_collection_quality: float = 0.25
    v3_analysis_depth: float = 0.25
    system_health: float = 0.20

def compute_composite(
    dimension_scores: dict[str, float],
    weights: AggregateWeights,
) -> float:
    """
    Compute weighted composite score from per-dimension normalized scores.

    Formula:
      composite = w1*mean(V1_dims) + w2*mean(V2_dims) + w3*mean(V3_dims) + w4*mean(sys_dims)
    """
    by_category: dict[DimensionCategory, list[float]] = {c: [] for c in DimensionCategory}
    registry = get_dimension_registry()
    for kind, score in dimension_scores.items():
        dim = registry.get(kind)
        by_category[dim.category()].append(score)

    def safe_mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    return (
        weights.v1_eval_quality * safe_mean(by_category[DimensionCategory.EVAL_QUALITY])
        + weights.v2_collection_quality * safe_mean(by_category[DimensionCategory.COLLECTION_QUALITY])
        + weights.v3_analysis_depth * safe_mean(by_category[DimensionCategory.ANALYSIS_DEPTH])
        + weights.system_health * safe_mean(by_category[DimensionCategory.SYSTEM_HEALTH])
    )
```

---

## 2. Task Definition Format

Evaluation tasks are the atomic unit of evaluation. Each task defines an input, an expected output (optional), scoring criteria, and metadata. Tasks are authored as Python dataclasses and persisted as TOML files.

### 2.1 Core Dataclasses

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import tomli
import tomli_w


class DifficultyLevel(Enum):
    """Five-tier difficulty scale (VAKRA L1–L4 + extension)."""
    L1_TRIVIAL = 1
    L2_SIMPLE = 2
    L3_MODERATE = 3
    L4_COMPLEX = 4
    L5_EXPERT = 5


# --- Discriminated union inputs (absorbs EvoBench Pattern 1.1) ---

@dataclass
class TextInput:
    type: Literal["text"] = "text"
    prompt: str = ""

@dataclass
class CodeInput:
    type: Literal["code"] = "code"
    language: str = "python"
    source: str = ""
    file_path: str | None = None

@dataclass
class ConversationInput:
    type: Literal["conversation"] = "conversation"
    messages: list[dict[str, str]] = field(default_factory=list)

@dataclass
class CustomInput:
    type: Literal["custom"] = "custom"
    data: dict[str, Any] = field(default_factory=dict)

TaskInput = TextInput | CodeInput | ConversationInput | CustomInput


# --- Discriminated union expected outputs ---

@dataclass
class TextExpected:
    type: Literal["text"] = "text"
    value: str = ""
    tolerance: float = 0.0

@dataclass
class CodeExpected:
    type: Literal["code"] = "code"
    value: str = ""
    language: str = "python"

@dataclass
class StructuredExpected:
    type: Literal["structured"] = "structured"
    schema: dict[str, Any] = field(default_factory=dict)
    value: dict[str, Any] = field(default_factory=dict)

@dataclass
class PatternExpected:
    type: Literal["pattern"] = "pattern"
    regex: str = ""

TaskExpected = TextExpected | CodeExpected | StructuredExpected | PatternExpected | None


# --- Scoring criterion ---

@dataclass
class ScoringCriterion:
    """A single criterion within a task's scoring rubric."""
    name: str
    weight: float
    description: str = ""
    scorer_type: str = "exact"
    scorer_params: dict[str, Any] = field(default_factory=dict)


# --- Resource attachment ---

@dataclass
class TaskResource:
    """External resource required by a task (file, URL, etc.)."""
    name: str
    resource_type: str  # "file", "url", "inline"
    value: str
    checksum: str | None = None


# --- The task definition itself ---

@dataclass
class EvalTask:
    """
    Canonical in-memory representation of an evaluation task.

    Implements FR-101: typed inputs, expected outputs, difficulty tiers,
    category tags, and TOML round-trip serialization.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    dimension: str = ""
    difficulty: DifficultyLevel = DifficultyLevel.L3_MODERATE
    input: TaskInput = field(default_factory=TextInput)
    expected: TaskExpected = None
    scoring: list[ScoringCriterion] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None
    resources: list[TaskResource] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    version: str = "1.0"

    def __post_init__(self) -> None:
        from uuid import UUID
        try:
            UUID(self.id)
        except ValueError as exc:
            raise TaskValidationError(f"Invalid task ID (not a UUID): {self.id}") from exc

    @classmethod
    def from_toml(cls, path: Path) -> EvalTask:
        """Load from a TOML file, deserializing tagged unions via 'type' field."""
        raw = tomli.loads(path.read_text(encoding="utf-8"))
        task_data = raw.get("task", raw)
        task_input = _deserialize_input(task_data.pop("input", {}))
        expected = _deserialize_expected(task_data.pop("expected", None))
        scoring = [
            ScoringCriterion(**c) for c in task_data.pop("scoring", [])
        ]
        resources = [
            TaskResource(**r) for r in task_data.pop("resources", [])
        ]
        difficulty_raw = task_data.pop("difficulty", 3)
        difficulty = DifficultyLevel(difficulty_raw)
        return cls(
            input=task_input,
            expected=expected,
            scoring=scoring,
            resources=resources,
            difficulty=difficulty,
            **task_data,
        )

    def to_toml(self) -> str:
        """Serialize back to TOML string."""
        data: dict[str, Any] = {
            "task": {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "dimension": self.dimension,
                "difficulty": self.difficulty.value,
                "tags": self.tags,
                "metadata": self.metadata,
                "version": self.version,
                "created_at": self.created_at,
            }
        }
        if self.timeout_seconds is not None:
            data["task"]["timeout_seconds"] = self.timeout_seconds
        data["task"]["input"] = _serialize_input(self.input)
        if self.expected is not None:
            data["task"]["expected"] = _serialize_expected(self.expected)
        if self.scoring:
            data["task"]["scoring"] = [
                {"name": c.name, "weight": c.weight, "description": c.description,
                 "scorer_type": c.scorer_type, "scorer_params": c.scorer_params}
                for c in self.scoring
            ]
        if self.resources:
            data["task"]["resources"] = [
                {"name": r.name, "resource_type": r.resource_type,
                 "value": r.value, **({"checksum": r.checksum} if r.checksum else {})}
                for r in self.resources
            ]
        return tomli_w.dumps(data)


def _deserialize_input(raw: dict[str, Any]) -> TaskInput:
    input_type = raw.get("type", "text")
    match input_type:
        case "text":
            return TextInput(prompt=raw.get("prompt", ""))
        case "code":
            return CodeInput(
                language=raw.get("language", "python"),
                source=raw.get("source", ""),
                file_path=raw.get("file_path"),
            )
        case "conversation":
            return ConversationInput(messages=raw.get("messages", []))
        case "custom":
            return CustomInput(data=raw.get("data", {}))
        case _:
            raise TaskLoadError(f"Unknown input type: {input_type}")


def _deserialize_expected(raw: dict[str, Any] | None) -> TaskExpected:
    if raw is None:
        return None
    exp_type = raw.get("type", "text")
    match exp_type:
        case "text":
            return TextExpected(value=raw.get("value", ""), tolerance=raw.get("tolerance", 0.0))
        case "code":
            return CodeExpected(value=raw.get("value", ""), language=raw.get("language", "python"))
        case "structured":
            return StructuredExpected(schema=raw.get("schema", {}), value=raw.get("value", {}))
        case "pattern":
            return PatternExpected(regex=raw.get("regex", ""))
        case _:
            raise TaskLoadError(f"Unknown expected type: {exp_type}")


def _serialize_input(inp: TaskInput) -> dict[str, Any]:
    match inp:
        case TextInput():
            return {"type": "text", "prompt": inp.prompt}
        case CodeInput():
            d: dict[str, Any] = {"type": "code", "language": inp.language, "source": inp.source}
            if inp.file_path:
                d["file_path"] = inp.file_path
            return d
        case ConversationInput():
            return {"type": "conversation", "messages": inp.messages}
        case CustomInput():
            return {"type": "custom", "data": inp.data}


def _serialize_expected(exp: TextExpected | CodeExpected | StructuredExpected | PatternExpected) -> dict[str, Any]:
    match exp:
        case TextExpected():
            return {"type": "text", "value": exp.value, "tolerance": exp.tolerance}
        case CodeExpected():
            return {"type": "code", "value": exp.value, "language": exp.language}
        case StructuredExpected():
            return {"type": "structured", "schema": exp.schema, "value": exp.value}
        case PatternExpected():
            return {"type": "pattern", "regex": exp.regex}
```

### 2.2 Example Task TOML

```toml
[task]
id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
name = "cyclomatic-complexity-detection"
description = "Verify that the analyzer correctly computes cyclomatic complexity for a function with nested branches."
dimension = "code_quality"
difficulty = 3
tags = ["ast", "complexity", "v3-analysis"]
timeout_seconds = 30.0
version = "1.0"
created_at = "2026-04-11T00:00:00+00:00"

[task.input]
type = "code"
language = "python"
source = """
def process(data, mode):
    if mode == 'fast':
        for item in data:
            if item.valid:
                yield item.transform()
            else:
                if item.recoverable:
                    yield item.recover()
    elif mode == 'safe':
        results = []
        for item in data:
            try:
                results.append(item.transform())
            except TransformError:
                continue
        return results
"""

[task.expected]
type = "structured"
value = { cyclomatic_complexity = 7, num_branches = 6, num_functions = 1 }
schema = { cyclomatic_complexity = "integer", num_branches = "integer", num_functions = "integer" }

[[task.scoring]]
name = "complexity_exact"
weight = 0.6
description = "Exact match on cyclomatic complexity value"
scorer_type = "exact"
scorer_params = { field = "cyclomatic_complexity" }

[[task.scoring]]
name = "branch_count"
weight = 0.4
description = "Fuzzy match on branch count (±1 tolerance)"
scorer_type = "fuzzy"
scorer_params = { field = "num_branches", tolerance = 1 }
```

### 2.3 Task Suite

A task suite is a directory or glob pattern grouping multiple tasks:

```python
@dataclass
class TaskSuite:
    """A collection of evaluation tasks loaded from a directory or glob."""
    name: str
    description: str = ""
    tasks: list[EvalTask] = field(default_factory=list)
    source_pattern: str = ""

    @classmethod
    def from_directory(cls, path: Path, pattern: str = "*.toml") -> TaskSuite:
        tasks = []
        for toml_path in sorted(path.glob(pattern)):
            tasks.append(EvalTask.from_toml(toml_path))
        return cls(
            name=path.name,
            tasks=tasks,
            source_pattern=str(path / pattern),
        )
```

---

## 3. Evaluation Pipeline

The pipeline follows a six-stage architecture: `load → validate → execute → score → aggregate → report`. This merges EvoBench's 8-stage pipeline (Pattern 2.1) into 6 stages by folding DataCollector into Executor and MatrixExpander into load-time validation.

### 3.1 Pipeline Stage Protocols

Each stage is defined as a `Protocol` for structural subtyping. Classes satisfy these protocols by implementing the required methods — no inheritance needed.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable, Any


# --- Result types used across stages ---

@dataclass
class EvalResult:
    """Output from executing a single evaluation task."""
    task_id: str
    output: Any
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    cost: CostRecord = field(default_factory=lambda: CostRecord())
    timing: TimingRecord = field(default_factory=lambda: TimingRecord())
    environment: EnvironmentRecord | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)

@dataclass
class CostRecord:
    total_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0

@dataclass
class TimingRecord:
    total_duration_seconds: float = 0.0
    per_stage: dict[str, float] = field(default_factory=dict)

@dataclass
class MetricScore:
    metric_name: str
    raw_value: float
    normalized_value: float
    weight: float

@dataclass
class EvalScore:
    """Scoring result for a single task."""
    task_id: str
    overall_score: float
    scores: list[MetricScore] = field(default_factory=list)
    reasoning: str = ""
    scorer_name: str = ""

@dataclass
class AggregatedResult:
    """Aggregated scores across multiple tasks and dimensions."""
    dimension_scores: dict[str, float] = field(default_factory=dict)
    per_task_scores: dict[str, EvalScore] = field(default_factory=dict)
    composite_score: float = 0.0
    statistics: dict[str, Any] = field(default_factory=dict)

@dataclass
class ReportOutput:
    """Generated report artifact."""
    path: Path | None = None
    content: str = ""
    format: str = "markdown"
    size_bytes: int = 0


# --- Stage 1: Loader ---

@runtime_checkable
class TaskLoader(Protocol):
    """
    Loads evaluation tasks from various sources.
    Implements FR-102.
    """
    async def load(self, source: str | Path) -> list[EvalTask]:
        """Load tasks from a file path, directory, or glob pattern."""
        ...

    def supported_formats(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.toml'])."""
        ...


# --- Stage 2: Validator ---

@runtime_checkable
class TaskValidator(Protocol):
    """
    Validates loaded tasks for structural correctness and completeness.
    Catches malformed tasks before they enter execution.
    """
    async def validate(self, tasks: list[EvalTask]) -> ValidationResult:
        """
        Validate a batch of tasks.
        Returns valid tasks and structured errors for invalid ones.
        """
        ...

@dataclass
class ValidationResult:
    valid_tasks: list[EvalTask] = field(default_factory=list)
    errors: list[ValidationError] = field(default_factory=list)

@dataclass
class ValidationError:
    task_id: str
    field: str
    message: str
    severity: str = "error"  # "error" | "warning"


# --- Stage 3: Executor ---

@runtime_checkable
class Executor(Protocol):
    """
    Executes a single evaluation task and returns the result.
    Subsumes EvoBench's Executor + DataCollector (Pattern 2.1).
    Implements FR-114.
    """
    async def execute(self, task: EvalTask) -> EvalResult:
        """Execute task in isolation, returning collected output and metrics."""
        ...

    def capabilities(self) -> ExecutorCapabilities:
        """Report what this executor supports."""
        ...

@dataclass
class ExecutorCapabilities:
    supports_sandbox: bool = False
    supports_timeout: bool = True
    supports_parallel: bool = False
    max_concurrent: int = 1


# --- Stage 4: Scorer ---

@runtime_checkable
class Scorer(Protocol):
    """
    Scores an execution result against expected output.
    Base protocol for the entire scorer plugin system (§4).
    Implements FR-103 through FR-106.
    """
    async def score(
        self,
        result: EvalResult,
        expected: TaskExpected,
    ) -> EvalScore:
        """Produce a score for a single task execution."""
        ...

    def name(self) -> str:
        """Unique identifier for this scorer."""
        ...


# --- Stage 5: Aggregator ---

@runtime_checkable
class Aggregator(Protocol):
    """
    Aggregates per-task scores into per-dimension and composite results.
    Implements FR-412 composite scoring.
    """
    async def aggregate(
        self,
        scores: list[EvalScore],
        tasks: list[EvalTask],
    ) -> AggregatedResult:
        """Aggregate individual task scores into dimension-level and composite scores."""
        ...


# --- Stage 6: Reporter ---

@runtime_checkable
class Reporter(Protocol):
    """
    Generates output reports from aggregated evaluation results.
    Implements FR-112 (JSON) and FR-113 (Markdown).
    """
    async def generate(
        self,
        result: AggregatedResult,
        config: ReportConfig,
    ) -> ReportOutput:
        """Produce a formatted report."""
        ...

    def supported_formats(self) -> list[str]:
        """Return list of output formats this reporter can produce."""
        ...

@dataclass
class ReportConfig:
    output_dir: Path = field(default_factory=lambda: Path("reports"))
    formats: list[str] = field(default_factory=lambda: ["markdown", "json"])
    include_per_task: bool = True
    include_statistics: bool = True
    include_recommendations: bool = True
    baseline_path: Path | None = None
```

### 3.2 Pipeline Orchestrator

The `EvalPipeline` class wires all six stages together with error handling, timing, and progress callbacks.

```python
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable

logger = logging.getLogger("nines.eval.pipeline")


@dataclass
class PipelineConfig:
    """Pipeline execution configuration. Loaded from NinesConfig."""
    num_trials: int = 1
    max_concurrent: int = 4
    timeout_seconds: float | None = 300.0
    cost_budget: float | None = None
    retry_max: int = 3
    retry_base_delay_seconds: float = 1.0
    seed: int | None = None

ProgressCallback = Callable[[str, int, int], Awaitable[None]]


class EvalPipeline:
    """
    Orchestrates the 6-stage evaluation pipeline.
    Implements FR-114 (Evaluation Orchestration).
    """

    def __init__(
        self,
        loader: TaskLoader,
        validator: TaskValidator,
        executor: Executor,
        scorer: Scorer,
        aggregator: Aggregator,
        reporters: list[Reporter],
        config: PipelineConfig,
        budget_guard: BudgetGuard | None = None,
    ) -> None:
        self._loader = loader
        self._validator = validator
        self._executor = executor
        self._scorer = scorer
        self._aggregator = aggregator
        self._reporters = reporters
        self._config = config
        self._budget_guard = budget_guard

    async def run(
        self,
        source: str,
        on_progress: ProgressCallback | None = None,
    ) -> PipelineResult:
        """
        Execute the full pipeline: load → validate → execute → score → aggregate → report.
        """
        timings: dict[str, float] = {}

        # Stage 1: Load
        t0 = time.monotonic()
        tasks = await self._loader.load(source)
        timings["load"] = time.monotonic() - t0
        if not tasks:
            raise TaskLoadError(f"No tasks loaded from: {source}")
        logger.info("Loaded %d tasks from %s", len(tasks), source)

        # Stage 2: Validate
        t0 = time.monotonic()
        validation = await self._validator.validate(tasks)
        timings["validate"] = time.monotonic() - t0
        if validation.errors:
            for err in validation.errors:
                logger.warning(
                    "Validation %s on task %s.%s: %s",
                    err.severity, err.task_id, err.field, err.message,
                )
        tasks = validation.valid_tasks
        if not tasks:
            raise TaskValidationError("All tasks failed validation")
        logger.info("Validated %d tasks (%d errors)", len(tasks), len(validation.errors))

        # Stage 3: Execute
        t0 = time.monotonic()
        results = await self._execute_all(tasks, on_progress)
        timings["execute"] = time.monotonic() - t0

        # Stage 4: Score
        t0 = time.monotonic()
        scores = await self._score_all(results, tasks)
        timings["score"] = time.monotonic() - t0

        # Stage 5: Aggregate
        t0 = time.monotonic()
        aggregated = await self._aggregator.aggregate(scores, tasks)
        timings["aggregate"] = time.monotonic() - t0

        # Stage 6: Report
        t0 = time.monotonic()
        reports = []
        for reporter in self._reporters:
            report_config = ReportConfig()
            report = await reporter.generate(aggregated, report_config)
            reports.append(report)
        timings["report"] = time.monotonic() - t0

        return PipelineResult(
            aggregated=aggregated,
            reports=reports,
            timings=timings,
            task_count=len(tasks),
            validation_errors=validation.errors,
        )

    async def _execute_all(
        self,
        tasks: list[EvalTask],
        on_progress: ProgressCallback | None,
    ) -> list[EvalResult]:
        semaphore = asyncio.Semaphore(self._config.max_concurrent)
        results: list[EvalResult] = []
        completed = 0
        total = len(tasks)

        async def run_one(task: EvalTask) -> EvalResult:
            nonlocal completed
            async with semaphore:
                if self._budget_guard and await self._budget_guard.is_exceeded():
                    raise BudgetExceededError(
                        self._budget_guard.spent, self._budget_guard.budget
                    )
                result = await self._executor.execute(task)
                if self._budget_guard:
                    await self._budget_guard.record(result.cost.total_cost_usd)
                completed += 1
                if on_progress:
                    await on_progress(task.id, completed, total)
                return result

        gather_results = await asyncio.gather(
            *[run_one(t) for t in tasks],
            return_exceptions=True,
        )

        for i, res in enumerate(gather_results):
            if isinstance(res, BaseException):
                logger.error("Task %s execution failed: %s", tasks[i].id, res)
                results.append(EvalResult(
                    task_id=tasks[i].id,
                    output=None,
                    exit_code=1,
                    stderr=str(res),
                ))
            else:
                results.append(res)

        return results

    async def _score_all(
        self,
        results: list[EvalResult],
        tasks: list[EvalTask],
    ) -> list[EvalScore]:
        task_map = {t.id: t for t in tasks}
        scores: list[EvalScore] = []
        for result in results:
            task = task_map.get(result.task_id)
            if task is None:
                logger.warning("No task found for result %s", result.task_id)
                continue
            try:
                score = await self._scorer.score(result, task.expected)
                scores.append(score)
            except ScoringError as exc:
                logger.error("Scoring failed for task %s: %s", result.task_id, exc)
                scores.append(EvalScore(
                    task_id=result.task_id,
                    overall_score=0.0,
                    reasoning=f"Scoring error: {exc}",
                ))
        return scores


@dataclass
class PipelineResult:
    aggregated: AggregatedResult
    reports: list[ReportOutput] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    task_count: int = 0
    validation_errors: list[ValidationError] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return sum(self.timings.values())
```

### 3.3 Pipeline Construction

```python
class PipelineBuilder:
    """
    Builds an EvalPipeline with explicit stage registration and validation.
    Validates all stages satisfy their Protocols at construction time (Pattern 2.1 mitigation).
    """

    def __init__(self) -> None:
        self._loader: TaskLoader | None = None
        self._validator: TaskValidator | None = None
        self._executor: Executor | None = None
        self._scorer: Scorer | None = None
        self._aggregator: Aggregator | None = None
        self._reporters: list[Reporter] = []
        self._config = PipelineConfig()
        self._budget_guard: BudgetGuard | None = None

    def loader(self, loader: TaskLoader) -> PipelineBuilder:
        if not isinstance(loader, TaskLoader):
            raise ConfigError(f"{type(loader).__name__} does not satisfy TaskLoader protocol")
        self._loader = loader
        return self

    def validator(self, validator: TaskValidator) -> PipelineBuilder:
        if not isinstance(validator, TaskValidator):
            raise ConfigError(f"{type(validator).__name__} does not satisfy TaskValidator protocol")
        self._validator = validator
        return self

    def executor(self, executor: Executor) -> PipelineBuilder:
        if not isinstance(executor, Executor):
            raise ConfigError(f"{type(executor).__name__} does not satisfy Executor protocol")
        self._executor = executor
        return self

    def scorer(self, scorer: Scorer) -> PipelineBuilder:
        if not isinstance(scorer, Scorer):
            raise ConfigError(f"{type(scorer).__name__} does not satisfy Scorer protocol")
        self._scorer = scorer
        return self

    def aggregator(self, aggregator: Aggregator) -> PipelineBuilder:
        if not isinstance(aggregator, Aggregator):
            raise ConfigError(f"{type(aggregator).__name__} does not satisfy Aggregator protocol")
        self._aggregator = aggregator
        return self

    def add_reporter(self, reporter: Reporter) -> PipelineBuilder:
        if not isinstance(reporter, Reporter):
            raise ConfigError(f"{type(reporter).__name__} does not satisfy Reporter protocol")
        self._reporters.append(reporter)
        return self

    def with_config(self, config: PipelineConfig) -> PipelineBuilder:
        self._config = config
        return self

    def with_budget(self, budget: float) -> PipelineBuilder:
        self._budget_guard = BudgetGuard(budget=budget)
        return self

    def build(self) -> EvalPipeline:
        missing = []
        if self._loader is None:
            missing.append("loader")
        if self._validator is None:
            missing.append("validator")
        if self._executor is None:
            missing.append("executor")
        if self._scorer is None:
            missing.append("scorer")
        if self._aggregator is None:
            missing.append("aggregator")
        if missing:
            raise ConfigError(f"Pipeline missing required stages: {', '.join(missing)}")
        if not self._reporters:
            raise ConfigError("Pipeline requires at least one Reporter")

        return EvalPipeline(
            loader=self._loader,       # type: ignore[arg-type]
            validator=self._validator,  # type: ignore[arg-type]
            executor=self._executor,    # type: ignore[arg-type]
            scorer=self._scorer,        # type: ignore[arg-type]
            aggregator=self._aggregator,# type: ignore[arg-type]
            reporters=self._reporters,
            config=self._config,
            budget_guard=self._budget_guard,
        )
```

---

## 4. Scorer Plugin System

The scorer system provides a base `Scorer` Protocol with four built-in implementations plus a registration mechanism for custom scorers. Absorbs EvoBench Patterns 1.4 (CompositeScorer) and 2.7 (Scorer hierarchy).

### 4.1 Built-in Scorers

#### ExactScorer (FR-103)

```python
class ExactScorer:
    """Binary exact-match comparison. Returns 1.0 or 0.0."""

    def name(self) -> str:
        return "exact"

    async def score(self, result: EvalResult, expected: TaskExpected) -> EvalScore:
        if expected is None:
            return EvalScore(task_id=result.task_id, overall_score=0.0, reasoning="No expected output")

        actual = self._extract_comparable(result.output)
        expected_val = self._extract_comparable_expected(expected)
        match = actual.strip() == expected_val.strip()

        return EvalScore(
            task_id=result.task_id,
            overall_score=1.0 if match else 0.0,
            scores=[MetricScore(
                metric_name="exact_match",
                raw_value=1.0 if match else 0.0,
                normalized_value=1.0 if match else 0.0,
                weight=1.0,
            )],
            scorer_name="exact",
            reasoning="Exact match" if match else "Output does not match expected",
        )

    @staticmethod
    def _extract_comparable(output: Any) -> str:
        if isinstance(output, str):
            return output
        return str(output)

    @staticmethod
    def _extract_comparable_expected(expected: TaskExpected) -> str:
        match expected:
            case TextExpected():
                return expected.value
            case CodeExpected():
                return expected.value
            case _:
                return str(expected)
```

#### FuzzyScorer (FR-104)

```python
class FuzzyScorer:
    """
    Token-overlap and edit-distance scoring producing a continuous [0.0, 1.0] score.
    Uses rapidfuzz for performance (Pattern 2.7).
    """

    def __init__(self, threshold: float = 0.0) -> None:
        self._threshold = threshold

    def name(self) -> str:
        return "fuzzy"

    async def score(self, result: EvalResult, expected: TaskExpected) -> EvalScore:
        if expected is None:
            return EvalScore(task_id=result.task_id, overall_score=0.0, reasoning="No expected output")

        actual = str(result.output).strip()
        expected_val = self._extract_expected(expected)

        from rapidfuzz import fuzz
        token_ratio = fuzz.token_sort_ratio(actual, expected_val) / 100.0
        partial_ratio = fuzz.partial_ratio(actual, expected_val) / 100.0
        combined = 0.6 * token_ratio + 0.4 * partial_ratio

        return EvalScore(
            task_id=result.task_id,
            overall_score=combined,
            scores=[
                MetricScore("token_sort_ratio", token_ratio, token_ratio, 0.6),
                MetricScore("partial_ratio", partial_ratio, partial_ratio, 0.4),
            ],
            scorer_name="fuzzy",
            reasoning=f"Fuzzy similarity: {combined:.3f}",
        )

    @staticmethod
    def _extract_expected(expected: TaskExpected) -> str:
        match expected:
            case TextExpected():
                return expected.value
            case CodeExpected():
                return expected.value
            case _:
                return str(expected)
```

#### RubricScorer (FR-105)

```python
@dataclass
class RubricCriterion:
    name: str
    weight: float
    description: str
    max_score: float = 5.0

class RubricScorer:
    """
    Dimension-weighted checklist scorer with per-criterion evaluation.
    Unlike EvoBench's placeholder (hardcoded 3.0), NineS implements actual
    rubric scoring with optional LLM-as-judge integration.
    """

    def __init__(
        self,
        criteria: list[RubricCriterion],
        judge: RubricJudge | None = None,
    ) -> None:
        total_weight = sum(c.weight for c in criteria)
        if abs(total_weight - 1.0) > 1e-9:
            raise ScoringError(f"Rubric weights sum to {total_weight}, expected 1.0")
        self._criteria = criteria
        self._judge = judge or DefaultRubricJudge()

    def name(self) -> str:
        return "rubric"

    async def score(self, result: EvalResult, expected: TaskExpected) -> EvalScore:
        criterion_scores: list[MetricScore] = []
        weighted_sum = 0.0

        for criterion in self._criteria:
            raw = await self._judge.evaluate_criterion(
                criterion, result, expected
            )
            normalized = raw / criterion.max_score
            weighted_sum += normalized * criterion.weight
            criterion_scores.append(MetricScore(
                metric_name=f"rubric::{criterion.name}",
                raw_value=raw,
                normalized_value=normalized,
                weight=criterion.weight,
            ))

        return EvalScore(
            task_id=result.task_id,
            overall_score=weighted_sum,
            scores=criterion_scores,
            scorer_name="rubric",
        )


@runtime_checkable
class RubricJudge(Protocol):
    """Protocol for rubric criterion evaluation — allows swapping in LLM judges."""
    async def evaluate_criterion(
        self,
        criterion: RubricCriterion,
        result: EvalResult,
        expected: TaskExpected,
    ) -> float:
        """Return a raw score in [0, criterion.max_score]."""
        ...


class DefaultRubricJudge:
    """Programmatic rubric judge using heuristic checks."""
    async def evaluate_criterion(
        self,
        criterion: RubricCriterion,
        result: EvalResult,
        expected: TaskExpected,
    ) -> float:
        if result.exit_code != 0:
            return 0.0
        if result.output is None:
            return 0.0
        return criterion.max_score * 0.5
```

#### CompositeScorer (FR-106)

```python
class CompositeScorer:
    """
    Chains multiple scorers with namespace-prefixed metric aggregation.
    Absorbs EvoBench Pattern 1.4 directly.

    Supports two modes:
    - Weighted average: all scorers run, results combined by weight
    - Waterfall: scorers run in order, first decisive result wins
    """

    def __init__(
        self,
        scorers: list[tuple[Scorer, float]],
        mode: str = "weighted",
        waterfall_threshold: float = 0.9,
    ) -> None:
        if not scorers:
            raise ScoringError("CompositeScorer requires at least one scorer")
        names = [s.name() for s, _ in scorers]
        total_weight = sum(w for _, w in scorers)
        if mode == "weighted" and abs(total_weight - 1.0) > 1e-9:
            raise ScoringError(f"Weighted scorer weights sum to {total_weight}, expected 1.0")
        self._scorers = scorers
        self._mode = mode
        self._waterfall_threshold = waterfall_threshold

    def name(self) -> str:
        return "composite"

    async def score(self, result: EvalResult, expected: TaskExpected) -> EvalScore:
        if self._mode == "waterfall":
            return await self._score_waterfall(result, expected)
        return await self._score_weighted(result, expected)

    async def _score_weighted(self, result: EvalResult, expected: TaskExpected) -> EvalScore:
        all_metrics: list[MetricScore] = []
        weighted_sum = 0.0

        for scorer, weight in self._scorers:
            part = await scorer.score(result, expected)
            weighted_sum += part.overall_score * weight
            for m in part.scores:
                all_metrics.append(MetricScore(
                    metric_name=f"composite::{scorer.name()}::{m.metric_name}",
                    raw_value=m.raw_value,
                    normalized_value=m.normalized_value,
                    weight=m.weight * weight,
                ))

        return EvalScore(
            task_id=result.task_id,
            overall_score=weighted_sum,
            scores=all_metrics,
            scorer_name="composite",
        )

    async def _score_waterfall(self, result: EvalResult, expected: TaskExpected) -> EvalScore:
        """
        Waterfall judge pattern (VAKRA-inspired):
        Run scorers in order; if one produces a decisive score (>=threshold or ==0),
        return immediately. Otherwise, fall through to the next scorer.
        """
        for scorer, _ in self._scorers:
            part = await scorer.score(result, expected)
            if part.overall_score >= self._waterfall_threshold or part.overall_score == 0.0:
                prefixed = [
                    MetricScore(
                        metric_name=f"waterfall::{scorer.name()}::{m.metric_name}",
                        raw_value=m.raw_value,
                        normalized_value=m.normalized_value,
                        weight=m.weight,
                    )
                    for m in part.scores
                ]
                return EvalScore(
                    task_id=result.task_id,
                    overall_score=part.overall_score,
                    scores=prefixed,
                    scorer_name=f"waterfall({scorer.name()})",
                    reasoning=f"Decisive at stage: {scorer.name()}",
                )

        last_scorer, _ = self._scorers[-1]
        fallback = await last_scorer.score(result, expected)
        return EvalScore(
            task_id=result.task_id,
            overall_score=fallback.overall_score,
            scores=fallback.scores,
            scorer_name=f"waterfall(fallback:{last_scorer.name()})",
            reasoning="No decisive scorer; using last as fallback",
        )
```

### 4.2 Scorer Registration

```python
class ScorerRegistry:
    """
    Central registry for scorer plugins.
    Supports programmatic registration and entry-point discovery.
    Absorbs EvoBench Pattern 3.2 (simplified plugin system).
    """

    def __init__(self) -> None:
        self._scorers: dict[str, type] = {}
        self._instances: dict[str, Scorer] = {}

    def register(self, name: str, scorer_cls: type) -> None:
        """Register a scorer class by name."""
        if name in self._scorers:
            raise ConfigError(f"Scorer '{name}' already registered")
        self._scorers[name] = scorer_cls
        logger.info("Registered scorer: %s -> %s", name, scorer_cls.__name__)

    def create(self, name: str, **kwargs: Any) -> Scorer:
        """Instantiate a registered scorer with the given parameters."""
        if name not in self._scorers:
            raise ConfigError(
                f"Unknown scorer: '{name}'. Available: {list(self._scorers.keys())}"
            )
        instance = self._scorers[name](**kwargs)
        if not isinstance(instance, Scorer):
            raise ConfigError(f"Scorer '{name}' does not satisfy the Scorer protocol")
        return instance

    def get_or_create(self, name: str, **kwargs: Any) -> Scorer:
        """Return cached instance or create new one."""
        cache_key = f"{name}:{hash(frozenset(kwargs.items()))}"
        if cache_key not in self._instances:
            self._instances[cache_key] = self.create(name, **kwargs)
        return self._instances[cache_key]

    @classmethod
    def with_builtins(cls) -> ScorerRegistry:
        """Create registry pre-loaded with built-in scorers."""
        registry = cls()
        registry.register("exact", ExactScorer)
        registry.register("fuzzy", FuzzyScorer)
        registry.register("rubric", RubricScorer)
        registry.register("composite", CompositeScorer)
        return registry

    @classmethod
    def from_entry_points(cls, group: str = "nines.scorers") -> ScorerRegistry:
        """Discover scorer plugins via setuptools entry_points."""
        import importlib.metadata
        registry = cls.with_builtins()
        for ep in importlib.metadata.entry_points(group=group):
            try:
                scorer_cls = ep.load()
                registry.register(ep.name, scorer_cls)
            except Exception as exc:
                logger.error("Failed to load scorer plugin '%s': %s", ep.name, exc)
        return registry

    def list_available(self) -> list[str]:
        return list(self._scorers.keys())
```

### 4.3 Custom Scorer Example

Registering a custom scorer requires only implementing the `Scorer` protocol — no base class inheritance needed:

```python
# In a third-party package or user code:
class RegexScorer:
    """Scores output by checking if it matches a regex pattern."""

    def name(self) -> str:
        return "regex"

    async def score(self, result: EvalResult, expected: TaskExpected) -> EvalScore:
        import re
        if not isinstance(expected, PatternExpected):
            return EvalScore(task_id=result.task_id, overall_score=0.0,
                             reasoning="RegexScorer requires PatternExpected")
        output_str = str(result.output)
        match = re.search(expected.regex, output_str)
        score_val = 1.0 if match else 0.0
        return EvalScore(
            task_id=result.task_id,
            overall_score=score_val,
            scores=[MetricScore("regex_match", score_val, score_val, 1.0)],
            scorer_name="regex",
        )

# Registration via code:
registry = ScorerRegistry.with_builtins()
registry.register("regex", RegexScorer)

# Or via entry_points in pyproject.toml:
# [project.entry-points."nines.scorers"]
# regex = "my_package.scorers:RegexScorer"
```

### 4.4 Composite Scoring Formula

The composite score for a task using `CompositeScorer` in weighted mode:

```
S_composite = Σ(w_i × S_i) / Σ(w_i)

where:
  w_i = weight of scorer i
  S_i = overall_score from scorer i
  S_i ∈ [0.0, 1.0]
  Σ(w_i) = 1.0 (enforced at construction)
```

Per-metric scores are namespace-prefixed to avoid collision:

```
composite::<scorer_name>::<metric_name>
```

In waterfall mode, the formula is short-circuit evaluation:

```
S_waterfall = first S_i where (S_i >= threshold OR S_i == 0.0)
            fallback: S_last
```

---

## 5. Matrix Evaluation

Combinatorial evaluation across N axes enables systematic exploration of the evaluation space. Absorbs EvoBench Pattern 2.3 (MatrixEngine) with Python-idiomatic implementation.

### 5.1 Matrix Data Model

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from itertools import product as cross_product


@dataclass
class AxisValue:
    """A single value on a matrix axis."""
    id: str
    label: str
    config: dict[str, Any] = field(default_factory=dict)

@dataclass
class MatrixAxis:
    """An evaluation axis (e.g., 'task_type', 'scorer', 'difficulty')."""
    name: str
    values: list[AxisValue]

@dataclass
class MatrixCell:
    """A single cell in the evaluation matrix — one combination of axis values."""
    coordinates: dict[str, str]  # axis_name → value_id
    cell_id: str = ""

    def __post_init__(self) -> None:
        if not self.cell_id:
            parts = sorted(f"{k}={v}" for k, v in self.coordinates.items())
            self.cell_id = "|".join(parts)

@dataclass
class ExclusionRule:
    """Exclude cells matching all specified axis-value conditions."""
    conditions: dict[str, str]  # axis_name → value_id to exclude

    def matches(self, cell: MatrixCell) -> bool:
        return all(
            cell.coordinates.get(axis) == value
            for axis, value in self.conditions.items()
        )

@dataclass
class MatrixSpec:
    """Full specification for a matrix evaluation."""
    axes: list[MatrixAxis]
    strategy: str = "full_cross_product"  # full_cross_product | latin_square | pairwise | random
    max_combinations: int | None = None
    num_trials: int = 3
    exclusions: list[ExclusionRule] = field(default_factory=list)
    random_seed: int | None = None
```

### 5.2 Matrix Engine

```python
import random


class MatrixEngine:
    """
    Generates evaluation matrix cells from a MatrixSpec.
    Implements FR-107 (Matrix Evaluation).
    """

    @staticmethod
    def generate(spec: MatrixSpec) -> list[MatrixCell]:
        strategies = {
            "full_cross_product": MatrixEngine._full_cross,
            "latin_square": MatrixEngine._latin_square,
            "pairwise": MatrixEngine._pairwise,
            "random": MatrixEngine._random_sample,
        }
        if spec.strategy not in strategies:
            raise ConfigError(f"Unknown matrix strategy: {spec.strategy}")
        cells = strategies[spec.strategy](spec)
        cells = MatrixEngine._apply_exclusions(cells, spec.exclusions)
        return cells

    @staticmethod
    def _full_cross(spec: MatrixSpec) -> list[MatrixCell]:
        axis_names = [ax.name for ax in spec.axes]
        axis_values = [[v.id for v in ax.values] for ax in spec.axes]

        total = 1
        for vals in axis_values:
            total *= len(vals)
        if spec.max_combinations and total > spec.max_combinations:
            raise MatrixTooLargeError(
                total, spec.max_combinations,
                "Use 'latin_square', 'pairwise', or 'random' strategy to reduce"
            )

        cells: list[MatrixCell] = []
        for combo in cross_product(*axis_values):
            coords = dict(zip(axis_names, combo))
            cells.append(MatrixCell(coordinates=coords))
        return cells

    @staticmethod
    def _latin_square(spec: MatrixSpec) -> list[MatrixCell]:
        """
        Latin-square sampling: ensures each value on each axis appears
        an equal number of times. Requires exactly 2 axes with the same
        number of values for a proper Latin square; generalizes to N axes
        by pairing and rotating.
        """
        if len(spec.axes) < 2:
            return MatrixEngine._full_cross(spec)

        rng = random.Random(spec.random_seed)
        n = max(len(ax.values) for ax in spec.axes)
        cells: list[MatrixCell] = []

        for row_idx in range(n):
            coords: dict[str, str] = {}
            for ax_idx, axis in enumerate(spec.axes):
                value_idx = (row_idx + ax_idx) % len(axis.values)
                coords[axis.name] = axis.values[value_idx].id
            cells.append(MatrixCell(coordinates=coords))

        rng.shuffle(cells)
        if spec.max_combinations:
            cells = cells[:spec.max_combinations]
        return cells

    @staticmethod
    def _pairwise(spec: MatrixSpec) -> list[MatrixCell]:
        """
        Pairwise coverage: ensures every pair of values across any two axes
        appears in at least one cell. Uses a greedy covering algorithm.
        """
        rng = random.Random(spec.random_seed)
        uncovered_pairs: set[tuple[str, str, str, str]] = set()

        for i, ax_a in enumerate(spec.axes):
            for j, ax_b in enumerate(spec.axes):
                if j <= i:
                    continue
                for va in ax_a.values:
                    for vb in ax_b.values:
                        uncovered_pairs.add((ax_a.name, va.id, ax_b.name, vb.id))

        cells: list[MatrixCell] = []
        while uncovered_pairs:
            best_coords: dict[str, str] = {}
            best_coverage = 0
            for _ in range(50):
                candidate = {
                    ax.name: rng.choice(ax.values).id for ax in spec.axes
                }
                coverage = sum(
                    1 for p in uncovered_pairs
                    if candidate.get(p[0]) == p[1] and candidate.get(p[2]) == p[3]
                )
                if coverage > best_coverage:
                    best_coverage = coverage
                    best_coords = candidate

            cells.append(MatrixCell(coordinates=best_coords))
            uncovered_pairs = {
                p for p in uncovered_pairs
                if not (best_coords.get(p[0]) == p[1] and best_coords.get(p[2]) == p[3])
            }

            if spec.max_combinations and len(cells) >= spec.max_combinations:
                break

        return cells

    @staticmethod
    def _random_sample(spec: MatrixSpec) -> list[MatrixCell]:
        """Random sampling from the full cross-product space."""
        rng = random.Random(spec.random_seed)
        n = spec.max_combinations or 100
        cells: list[MatrixCell] = []
        seen: set[str] = set()

        for _ in range(n * 10):
            if len(cells) >= n:
                break
            coords = {ax.name: rng.choice(ax.values).id for ax in spec.axes}
            cell = MatrixCell(coordinates=coords)
            if cell.cell_id not in seen:
                seen.add(cell.cell_id)
                cells.append(cell)

        return cells

    @staticmethod
    def _apply_exclusions(
        cells: list[MatrixCell],
        exclusions: list[ExclusionRule],
    ) -> list[MatrixCell]:
        if not exclusions:
            return cells
        return [c for c in cells if not any(ex.matches(c) for ex in exclusions)]
```

### 5.3 Parallel Matrix Execution

```python
class MatrixRunner:
    """
    Executes matrix cells with controlled parallelism and budget tracking.
    Absorbs EvoBench Pattern 2.4 (ParallelRunner).
    """

    def __init__(
        self,
        executor: Executor,
        scorer: Scorer,
        max_concurrent: int = 4,
        budget_guard: BudgetGuard | None = None,
    ) -> None:
        self._executor = executor
        self._scorer = scorer
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._budget_guard = budget_guard

    async def run_matrix(
        self,
        cells: list[MatrixCell],
        tasks: list[EvalTask],
        num_trials: int = 3,
    ) -> MatrixResult:
        """
        Execute all cells × tasks × trials with parallel control.
        Returns per-cell aggregated scores for statistical analysis.
        """
        cell_results: dict[str, list[EvalScore]] = {}

        async def run_cell(cell: MatrixCell) -> None:
            cell_scores: list[EvalScore] = []
            async with self._semaphore:
                for trial in range(num_trials):
                    if self._budget_guard and await self._budget_guard.is_exceeded():
                        break
                    for task in tasks:
                        result = await self._executor.execute(task)
                        if self._budget_guard:
                            await self._budget_guard.record(result.cost.total_cost_usd)
                        score = await self._scorer.score(result, task.expected)
                        cell_scores.append(score)
            cell_results[cell.cell_id] = cell_scores

        await asyncio.gather(*[run_cell(cell) for cell in cells])

        return MatrixResult(
            cell_scores=cell_results,
            total_cells=len(cells),
            total_evaluations=sum(len(s) for s in cell_results.values()),
        )


@dataclass
class MatrixResult:
    cell_scores: dict[str, list[EvalScore]] = field(default_factory=dict)
    total_cells: int = 0
    total_evaluations: int = 0
    budget_exceeded: bool = False
```

---

## 6. Reliability Metrics

Statistical functions for measuring evaluation consistency. Absorbs EvoBench Pattern 1.3 (pass@k, pass^k, consistency) as direct translations.

### 6.1 Core Functions

```python
from math import comb, nan, sqrt, log
from typing import Sequence


def pass_at_k(n: int, c: int, k: int) -> float:
    """
    Unbiased estimator: probability that at least 1 of k samples is correct.

    Formula: 1 - C(n-c, k) / C(n, k)

    Args:
        n: total number of samples
        c: number of correct samples
        k: number of draws

    Implements FR-108.
    """
    if k == 0:
        return 1.0
    if n == 0:
        return 0.0
    if c >= n:
        return 1.0
    if c == 0:
        return 0.0
    if k > n:
        return nan
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_pow_k(n: int, c: int, k: int) -> float:
    """
    Pessimistic reliability: probability ALL k independent trials succeed.

    Formula: (c/n)^k

    Implements FR-109.
    """
    if n == 0:
        return nan
    return (c / n) ** k


def pass_cubed(results: Sequence[bool]) -> float:
    """
    Claw-Eval's Pass³ metric: all 3 attempts must pass.
    Special case of pass^k with k=3.

    Implements FR-110.
    """
    if len(results) < 3:
        return nan
    return 1.0 if all(results[:3]) else 0.0


def consistency(scores: Sequence[float]) -> float:
    """
    Coefficient of variation complement: 1 - (std_dev / mean).
    Values near 1.0 indicate high consistency.

    Absorbs EvoBench Pattern 1.3.
    """
    if not scores:
        return nan
    if len(scores) == 1:
        return 1.0
    n = len(scores)
    mean = sum(scores) / n
    if abs(mean) < 1e-15:
        return nan
    variance = sum((x - mean) ** 2 for x in scores) / n
    return 1.0 - (variance ** 0.5) / mean
```

### 6.2 Confidence Intervals

```python
def bootstrap_confidence_interval(
    scores: Sequence[float],
    confidence: float = 0.95,
    n_bootstrap: int = 1000,
    seed: int | None = None,
) -> tuple[float, float]:
    """
    Non-parametric bootstrap confidence interval for the mean score.

    Returns (lower, upper) bounds at the given confidence level.
    """
    rng = random.Random(seed)
    n = len(scores)
    if n == 0:
        return (nan, nan)

    bootstrap_means: list[float] = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(scores) for _ in range(n)]
        bootstrap_means.append(sum(sample) / n)

    bootstrap_means.sort()
    alpha = 1.0 - confidence
    lower_idx = int((alpha / 2) * n_bootstrap)
    upper_idx = int((1 - alpha / 2) * n_bootstrap) - 1
    return (bootstrap_means[lower_idx], bootstrap_means[upper_idx])


def _inv_normal_cdf(p: float) -> float:
    """Pure-Python inverse normal CDF (Abramowitz and Stegun rational approx).

    Accurate to ~4.5e-4. Replaces scipy.stats.norm.ppf (M-07 resolution).
    """
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    if p < 0.5:
        t = sqrt(-2.0 * log(p))
    else:
        t = sqrt(-2.0 * log(1.0 - p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    result = t - (c0 + c1 * t + c2 * t**2) / (1.0 + d1 * t + d2 * t**2 + d3 * t**3)
    return -result if p < 0.5 else result


def wilson_confidence_interval(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Wilson score interval for binomial proportion.
    More robust than Wald interval for small sample sizes.
    Uses pure-Python inverse normal CDF instead of scipy.
    """
    if total == 0:
        return (nan, nan)
    z = _inv_normal_cdf(1 - (1 - confidence) / 2)
    p_hat = successes / total
    denom = 1 + z**2 / total
    center = (p_hat + z**2 / (2 * total)) / denom
    margin = (z / denom) * sqrt(p_hat * (1 - p_hat) / total + z**2 / (4 * total**2))
    return (max(0.0, center - margin), min(1.0, center + margin))
```

### 6.3 Statistical Aggregation

```python
@dataclass
class ReliabilityReport:
    """Complete reliability statistics for a set of evaluation trials."""
    task_id: str
    num_trials: int
    num_passed: int
    pass_at_1: float
    pass_at_k: float
    pass_pow_k: float
    pass_cubed: float | None
    consistency_score: float
    confidence_interval: tuple[float, float]
    individual_scores: list[float]
    is_stable: bool  # CV <= 0.05

    @classmethod
    def compute(
        cls,
        task_id: str,
        scores: list[float],
        pass_threshold: float = 0.5,
        k: int = 3,
        confidence: float = 0.95,
        seed: int | None = None,
    ) -> ReliabilityReport:
        n = len(scores)
        passed = [s >= pass_threshold for s in scores]
        c = sum(passed)

        cv = 0.0
        if n > 1:
            mean = sum(scores) / n
            if abs(mean) > 1e-15:
                var = sum((x - mean) ** 2 for x in scores) / n
                cv = (var ** 0.5) / mean

        return cls(
            task_id=task_id,
            num_trials=n,
            num_passed=c,
            pass_at_1=pass_at_k(n, c, 1),
            pass_at_k=pass_at_k(n, c, k),
            pass_pow_k=pass_pow_k(n, c, k),
            pass_cubed=pass_cubed(passed) if n >= 3 else None,
            consistency_score=consistency(scores),
            confidence_interval=bootstrap_confidence_interval(scores, confidence, seed=seed),
            individual_scores=list(scores),
            is_stable=(cv <= 0.05),
        )
```

---

## 7. Budget Guards

Real-time tracking of evaluation cost with configurable limits. Implements FR-111 (Budget Guards).

### 7.1 Budget Guard

```python
import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class BudgetLimits:
    """Configurable per-run budget limits."""
    max_cost_usd: float | None = None
    max_time_seconds: float | None = None
    max_api_calls: int | None = None
    max_tokens: int | None = None


class BudgetGuard:
    """
    Tracks real-time evaluation expenditure against configurable limits.
    Thread-safe via asyncio.Lock.
    Absorbs EvoBench Pattern 2.4 (CostTracker).
    """

    def __init__(self, budget: float | None = None, limits: BudgetLimits | None = None) -> None:
        self._limits = limits or BudgetLimits(max_cost_usd=budget)
        self._cost_usd = 0.0
        self._api_calls = 0
        self._tokens = 0
        self._start_time = time.monotonic()
        self._lock = asyncio.Lock()
        self._exceeded = False
        self._exceeded_reason: str | None = None

    @property
    def spent(self) -> float:
        return self._cost_usd

    @property
    def budget(self) -> float:
        return self._limits.max_cost_usd or float("inf")

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    async def record(
        self,
        cost_usd: float = 0.0,
        api_calls: int = 0,
        tokens: int = 0,
    ) -> None:
        """Record expenditure and check all limits."""
        async with self._lock:
            self._cost_usd += cost_usd
            self._api_calls += api_calls
            self._tokens += tokens
            self._check_limits()

    async def is_exceeded(self) -> bool:
        async with self._lock:
            self._check_limits()
            return self._exceeded

    def _check_limits(self) -> None:
        if self._exceeded:
            return

        if self._limits.max_cost_usd is not None and self._cost_usd >= self._limits.max_cost_usd:
            self._exceeded = True
            self._exceeded_reason = (
                f"Cost budget exceeded: ${self._cost_usd:.4f} >= ${self._limits.max_cost_usd:.4f}"
            )

        if self._limits.max_time_seconds is not None:
            elapsed = time.monotonic() - self._start_time
            if elapsed >= self._limits.max_time_seconds:
                self._exceeded = True
                self._exceeded_reason = (
                    f"Time budget exceeded: {elapsed:.1f}s >= {self._limits.max_time_seconds:.1f}s"
                )

        if self._limits.max_api_calls is not None and self._api_calls >= self._limits.max_api_calls:
            self._exceeded = True
            self._exceeded_reason = (
                f"API call budget exceeded: {self._api_calls} >= {self._limits.max_api_calls}"
            )

        if self._limits.max_tokens is not None and self._tokens >= self._limits.max_tokens:
            self._exceeded = True
            self._exceeded_reason = (
                f"Token budget exceeded: {self._tokens} >= {self._limits.max_tokens}"
            )

    def summary(self) -> BudgetSummary:
        return BudgetSummary(
            cost_usd=self._cost_usd,
            api_calls=self._api_calls,
            tokens=self._tokens,
            elapsed_seconds=self.elapsed_seconds,
            exceeded=self._exceeded,
            exceeded_reason=self._exceeded_reason,
            limits=self._limits,
        )


@dataclass
class BudgetSummary:
    cost_usd: float = 0.0
    api_calls: int = 0
    tokens: int = 0
    elapsed_seconds: float = 0.0
    exceeded: bool = False
    exceeded_reason: str | None = None
    limits: BudgetLimits = field(default_factory=BudgetLimits)
```

### 7.2 Pipeline Integration

The `BudgetGuard` plugs into the pipeline at the executor level (§3.2 `_execute_all`) and the matrix runner (§5.3 `MatrixRunner`). When any limit is exceeded:

1. The guard sets `exceeded = True`
2. The pipeline terminates the current execution batch
3. Partial results collected so far are returned with `budget_exceeded = True`
4. A `BudgetExceededError` is raised with the `BudgetSummary`

```python
class BudgetExceededError(NinesError):
    def __init__(self, spent: float, budget: float) -> None:
        self.spent = spent
        self.budget = budget
        super().__init__(f"Budget exceeded: ${spent:.4f} of ${budget:.4f}")
```

---

## 8. ADR — Key Differences from EvoBench

### ADR-001: Six NineS Dimensions Replace EvoBench's Four External Dimensions

**Status**: Accepted

**Context**: EvoBench defines 4 dimensions (Tool, Model, Workflow, TaskType) designed to benchmark *external* AI agent performance across different configurations. NineS evaluates *its own capabilities* across its three-vertex architecture.

**Decision**: NineS defines 6 dimensions aligned with its three-vertex model (CodeQuality, ArchitectureInsight, DecompositionDepth, PipelineReliability, InformationFreshness, SystemEfficiency) instead of copying EvoBench's 4. Only the `Dimension` Protocol and `MetricDefinition` model are absorbed directly; the actual dimensions and their metrics are entirely new.

**Consequences**:
- (+) Dimensions are meaningful for self-evaluation — they measure what NineS actually does
- (+) Each dimension maps to specific self-eval spec dimensions (D01–D19), ensuring traceability
- (-) No 1:1 comparison against EvoBench benchmark results is possible
- (-) Initial metric thresholds require empirical calibration (no existing baselines to inherit)

### ADR-002: Six-Stage Pipeline Instead of Eight

**Status**: Accepted

**Context**: EvoBench's pipeline has 8 stages: TaskLoader → MatrixExpander → TaskAdapter → Executor → DataCollector → Scorer → Aggregator → Reporter. The TaskAdapter and DataCollector stages add indirection that served EvoBench's Rust trait system but are unnecessary in Python.

**Decision**: NineS uses a 6-stage pipeline: `load → validate → execute → score → aggregate → report`.
- **DataCollector merged into Executor**: The Python Executor returns a fully populated `EvalResult` including collected metrics. Separating collection from execution added no value in a language where functions naturally return complex objects.
- **TaskAdapter replaced by Validator**: EvoBench's TaskAdapter transforms tasks for different executors. NineS uses a Validator stage instead — tasks are validated for structural correctness, and executor-specific adaptation is handled internally by each Executor implementation.
- **MatrixExpander moved to pre-pipeline**: Matrix expansion is a configuration concern, not a pipeline stage. `MatrixEngine.generate()` runs before the pipeline, producing a list of cells that the pipeline iterates over.

**Consequences**:
- (+) Simpler mental model: 6 stages are easier to understand and debug
- (+) Fewer Protocol interfaces to satisfy when building custom pipelines
- (-) Executor implementations carry more responsibility (must collect their own metrics)
- (-) Matrix expansion is less composable (can't swap matrix strategies mid-pipeline)

### ADR-003: Structural Subtyping (Protocol) Instead of Nominal Inheritance

**Status**: Accepted

**Context**: EvoBench uses Rust traits with `#[async_trait]` and `Arc<dyn Trait>` for runtime polymorphism. This requires explicit `impl Trait for Struct` declarations.

**Decision**: NineS uses Python `Protocol` classes with `@runtime_checkable` decorators. Any class implementing the required methods satisfies the Protocol without explicit opt-in. The `PipelineBuilder` validates Protocol conformance at construction time (not at import time) via `isinstance()` checks.

**Consequences**:
- (+) Third-party scorers, executors, and reporters work without knowing about NineS's base types
- (+) Testing is trivial — any object with matching methods works as a mock
- (-) Accidental Protocol satisfaction is possible (a random class might satisfy `Scorer` by coincidence). Mitigated by `PipelineBuilder` explicit validation.
- (-) `@runtime_checkable` only checks method *existence*, not *signatures*. Type checking at call time catches signature mismatches.

### ADR-004: Entry-Point Plugin Discovery Instead of DAG-Based Plugin System

**Status**: Accepted

**Context**: EvoBench implements a full plugin system with dependency DAG, topological sorting, permission model, panic recovery, and auto-disable after N errors. This is designed for a multi-plugin ecosystem with inter-plugin dependencies.

**Decision**: NineS uses Python's `importlib.metadata.entry_points()` for plugin discovery combined with a simple `ScorerRegistry` for registration. No dependency DAG, no permission model, no auto-disable for MVP.

**Consequences**:
- (+) Dramatically simpler: a custom scorer is one class + one `pyproject.toml` entry point
- (+) Follows Python ecosystem conventions (setuptools entry points)
- (-) No inter-plugin dependency management (if plugin A requires plugin B, they must coordinate independently)
- (-) No permission sandboxing for plugins (all plugins run with full NineS permissions)

**Upgrade path**: If plugin complexity grows, add `graphlib.TopologicalSorter` (stdlib) for dependency ordering.

### ADR-005: Waterfall Judge Mode in CompositeScorer

**Status**: Accepted

**Context**: EvoBench's CompositeScorer only supports weighted-average mode. The VAKRA framework implements a waterfall judge pattern (programmatic → exact → fuzzy → LLM-judge fallback) that is more efficient for scoring pipelines where early stages can be decisive.

**Decision**: NineS's `CompositeScorer` supports two modes: `weighted` (EvoBench-compatible) and `waterfall` (VAKRA-inspired). In waterfall mode, scorers run sequentially; the first decisive result (score >= threshold or score == 0) terminates the chain.

**Consequences**:
- (+) Avoids expensive LLM-judge calls when programmatic scoring is sufficient
- (+) Configurable threshold allows tuning the decisiveness boundary
- (-) Waterfall mode produces scores from a single scorer, losing the multi-perspective signal of weighted mode
- (-) Scorer ordering matters in waterfall mode (a design decision that weighted mode avoids)

### ADR-006: Bootstrap Confidence Intervals Instead of Analytical Only

**Status**: Accepted

**Context**: EvoBench provides `pass_at_k` and `pass_pow_k` as point estimates without confidence intervals. For self-evaluation with noisy metrics, point estimates alone can be misleading.

**Decision**: NineS adds bootstrap confidence intervals (non-parametric) and Wilson score intervals (for binomial metrics) alongside the EvoBench-absorbed point estimators. The `ReliabilityReport` includes both the point estimate and the confidence interval.

**Consequences**:
- (+) Self-evaluation decisions (convergence, regression detection) can use confidence bounds instead of raw scores
- (+) Wilson intervals are robust for small samples (important for MVP with limited trial counts)
- (-) Bootstrap adds computational cost (~1000 resamples per metric per task)
- (~) Wilson interval z-score uses a pure-Python Abramowitz & Stegun approximation, avoiding the `scipy` dependency (M-07 resolution)

---

*Defines the evaluation framework architecture for NineS, absorbing EvoBench patterns where appropriate and redesigning where NineS's self-evaluating scope diverges.*
*Last modified: 2026-04-11*
