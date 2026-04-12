# EvoBench → NineS Pattern Migration Plan

> **Task ID**: T05 — Research Team L3
> **Based on**: `docs/research/evobench_analysis.md` (T01)
> **Date**: 2026-04-11

---

## Classification Legend

| Category | Meaning | Typical Risk |
|----------|---------|-------------|
| **Direct Absorb** | Concept translates cleanly to Python with idiomatic substitutions (Rust enum → dataclass, trait → Protocol). Core logic and data structures are preserved. | Low |
| **Adapt/Transform** | Concept is valid but requires reworking for Python idioms, runtime model, or NineS-specific scope differences. | Medium |
| **New Design Needed** | EvoBench provides inspiration, but NineS requires a fundamentally different approach due to language, scope, or architectural divergence. | High |

---

## 1. Direct Absorb Patterns

### 1.1 Tagged-Enum Domain Modeling

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-core/src/types.rs` — `TaskInput`, `TaskExpected`, `TaskOutput` enums with `#[serde(tag = "type")]` + `Custom(serde_json::Value)` escape hatch |
| **NineS Target** | `src/nines/core/models.py` — Discriminated union dataclasses |
| **Classification** | Direct Absorb |

**Mapping**:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

@dataclass
class TextInput:
    type: Literal["Text"] = "Text"
    prompt: str = ""

@dataclass
class ConversationInput:
    type: Literal["Conversation"] = "Conversation"
    messages: list[Message] = field(default_factory=list)

@dataclass
class CodePatchInput:
    type: Literal["CodePatch"] = "CodePatch"
    repo: str = ""
    issue: str = ""

@dataclass
class CustomInput:
    type: Literal["Custom"] = "Custom"
    data: dict[str, Any] = field(default_factory=dict)

TaskInput = TextInput | ConversationInput | CodePatchInput | CustomInput
```

**Key Differences**:
- Rust: compile-time exhaustive match; Python: runtime `isinstance` checks or `match` statements
- Rust: `serde` handles `tag = "type"` automatically; Python: requires a `type` discriminator field plus a deserialization factory
- NineS keeps the `Custom` escape hatch via `dict[str, Any]` for the same extensibility

**Migration Risk**: **Low**. Python 3.12 `type` aliases and `match` statements provide equivalent functionality. The main risk is forgetting exhaustive handling — mitigated by a shared `deserialize_task_input()` factory function with an explicit `else` branch.

---

### 1.2 Weighted Multi-Metric Scoring with Normalization

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-dimensions/src/tool.rs` (and model.rs, workflow.rs, task_type.rs) — 8 metrics per dimension, weights summing to 1.0, `MetricDirection` (HigherIsBetter/LowerIsBetter), `MetricValueType` |
| **NineS Target** | `src/nines/eval/metrics.py` — `MetricDefinition` dataclass, `MetricRegistry` |
| **Classification** | Direct Absorb |

**Mapping**:

```python
from dataclasses import dataclass
from enum import Enum

class MetricDirection(Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"

class MetricValueType(Enum):
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"

@dataclass(frozen=True)
class MetricDefinition:
    name: str
    description: str
    value_type: MetricValueType
    direction: MetricDirection
    default_weight: float
```

**Key Differences**:
- EvoBench hardcodes 8 metrics per dimension with compile-time weight validation via tests; NineS uses a runtime `MetricRegistry` with `validate_weights()` that raises `ConfigError` if weights don't sum to 1.0
- NineS adds `normalize(raw_value) → float` method to `MetricDefinition` that inverts LowerIsBetter metrics to a uniform [0, 1] scale before aggregation

**Migration Risk**: **Low**. Arithmetic is identical. Only risk is weight-sum validation — covered by a unit test asserting `abs(sum(weights) - 1.0) < 1e-9` per dimension.

---

### 1.3 Reliability Statistics (pass@k, pass^k, consistency)

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-scorers/src/stats.rs` — `pass_at_k()`, `pass_pow_k()`, `consistency()` |
| **NineS Target** | `src/nines/eval/metrics.py` — Module-level functions |
| **Classification** | Direct Absorb |

**Mapping**:

```python
from math import comb, nan

def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability at least 1 of k samples is correct: 1 - C(n-c,k)/C(n,k)."""
    if k == 0: return 1.0
    if n == 0: return 0.0
    if c >= n: return 1.0
    if c == 0: return 0.0
    if k > n: return nan
    return 1.0 - comb(n - c, k) / comb(n, k)

def pass_pow_k(n: int, c: int, k: int) -> float:
    """Probability ALL k independent trials succeed: (c/n)^k."""
    if n == 0: return nan
    return (c / n) ** k

def consistency(scores: list[float]) -> float:
    """1 - (std_dev / mean) — coefficient of variation complement."""
    if not scores: return nan
    if len(scores) == 1: return 1.0
    mean = sum(scores) / len(scores)
    if abs(mean) < 1e-15: return nan
    variance = sum((x - mean) ** 2 for x in scores) / len(scores)
    return 1.0 - (variance ** 0.5) / mean
```

**Key Differences**:
- Python `math.comb` replaces the manual binomial coefficient loop
- EvoBench uses `f64::NAN`; Python uses `float('nan')` (identical IEEE-754 semantics)

**Migration Risk**: **Low**. The formulas are pure math with no language-specific behavior. One-to-one translation with identical test cases.

---

### 1.4 Composite Scorer Chaining

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-scorers/src/composite.rs` — `CompositeScorer` wrapping `Vec<Box<dyn Scorer>>` with weights, `composite::` metric prefix |
| **NineS Target** | `src/nines/eval/scorers.py` — `CompositeScorer` class |
| **Classification** | Direct Absorb |

**Mapping**:

```python
class CompositeScorer:
    def __init__(self, scorers: list[Scorer], weights: list[float]):
        if len(scorers) != len(weights):
            raise ScoringError("scorers/weights length mismatch")
        self._scorers = scorers
        self._weights = weights

    async def score(self, result: EvalResult, expected: TaskExpected | None) -> EvalScore:
        total_weight = sum(self._weights)
        weighted_sum = 0.0
        combined_metrics: list[MetricScore] = []
        for scorer, weight in zip(self._scorers, self._weights):
            part = await scorer.score(result, expected)
            weighted_sum += part.overall_score * weight
            for m in part.scores:
                m.metric_name = f"composite::{m.metric_name}"
                combined_metrics.append(m)
        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        return EvalScore(scores=combined_metrics, overall_score=overall, ...)
```

**Key Differences**:
- EvoBench uses `Arc<dyn Scorer>` for shared ownership; Python passes by reference naturally
- `composite::` namespace prefix is preserved identically

**Migration Risk**: **Low**. The chaining pattern is idiomatic in both languages. Risk is only in async execution order — mitigated by sequential scorer invocation (no parallel scoring within a composite).

---

### 1.5 Error Taxonomy

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-core/src/error.rs` — `EvalError` (16 variants), `PluginError` (7 variants) using `thiserror` |
| **NineS Target** | `src/nines/core/errors.py` — Exception class hierarchy |
| **Classification** | Direct Absorb |

**Mapping**:

```python
class NineSError(Exception):
    """Base exception for all NineS errors."""

class TaskLoadError(NineSError): ...
class TaskValidationError(NineSError): ...
class ExecutionError(NineSError): ...
class ScoringError(NineSError): ...
class AggregationError(NineSError): ...
class ReportError(NineSError): ...
class MatrixTooLargeError(NineSError):
    def __init__(self, total: int, max_cells: int, suggestion: str): ...
class BudgetExceededError(NineSError):
    def __init__(self, spent: float, budget: float): ...
class TimeoutError(NineSError):
    def __init__(self, elapsed_seconds: float): ...
class ConfigError(NineSError): ...
class CancelledError(NineSError): ...
class PluginError(NineSError): ...
```

**Key Differences**:
- Rust: enum variants with structured data; Python: exception subclasses with `__init__` parameters
- Rust: `#[from]` for automatic conversion; Python: explicit `raise ... from ...` chaining
- NineS drops `Io` and `Serialization` variants (Python handles these with stdlib exceptions)

**Migration Risk**: **Low**. Python exception hierarchies map cleanly. No silent failures (per workspace rules) — every catch block must log or re-raise.

---

### 1.6 Environment Capture for Reproducibility

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-core/src/types.rs` lines 276–302 — `EnvironmentRecord::capture()` |
| **NineS Target** | `src/nines/core/models.py` — `EnvironmentRecord.capture()` classmethod |
| **Classification** | Direct Absorb |

**Mapping**:

```python
import platform, sys
from datetime import datetime, timezone

@dataclass
class EnvironmentRecord:
    os: str
    arch: str
    python_version: str
    nines_version: str
    model_id: str | None = None
    model_provider: str | None = None
    random_seed: int | None = None
    config_hash: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def capture(cls) -> EnvironmentRecord:
        return cls(
            os=platform.system(),
            arch=platform.machine(),
            python_version=platform.python_version(),
            nines_version=importlib.metadata.version("nines"),
        )
```

**Key Differences**:
- Replaces `rust_version`/`ageneval_version` with `python_version`/`nines_version`
- Python `platform` module replaces Rust `std::env::consts`

**Migration Risk**: **Low**. Straightforward platform-info substitution.

---

## 2. Adapt/Transform Patterns

### 2.1 Trait-Based Pipeline Composition (8-Stage Pipeline)

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-core/src/traits.rs` — 8 `#[async_trait]` traits: `TaskLoader`, `MatrixExpander`, `TaskAdapter`, `Executor`, `DataCollector`, `Scorer`, `Aggregator`, `Reporter` |
| **NineS Target** | `src/nines/core/protocols.py` — `typing.Protocol` classes |
| **Classification** | Adapt/Transform |

**Mapping**:

EvoBench uses Rust's `async_trait` macro + `Arc<dyn Trait>` for runtime polymorphism. NineS uses Python `Protocol` (structural subtyping) for the same decoupling, but without explicit `Arc` wrapping.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class TaskLoader(Protocol):
    async def load_tasks(self, source: TaskSource) -> list[EvalTask]: ...
    def supported_formats(self) -> list[str]: ...

@runtime_checkable
class Executor(Protocol):
    async def execute(self, task: AdaptedTask) -> EvalResult: ...
    def capabilities(self) -> ExecutorCapabilities: ...

@runtime_checkable
class Scorer(Protocol):
    async def score(self, result: EvalResult, expected: TaskExpected | None) -> EvalScore: ...
```

**Key Differences**:
- Rust traits are nominal (must `impl Trait for Struct`); Python Protocols are structural (any class with matching methods satisfies the Protocol)
- `@runtime_checkable` enables `isinstance()` checks but with caveats — it only checks method existence, not signatures
- EvoBench's `Send + Sync` bounds are unnecessary in Python (GIL handles thread safety; asyncio is single-threaded)
- NineS **merges DataCollector into Executor** — the Python Executor returns a fully populated `EvalResult` including collected metrics, eliminating one pipeline stage. This reduces the 8-stage pipeline to a 7-stage pipeline:
  `TaskLoader → MatrixExpander → TaskAdapter → Executor → Scorer → Aggregator → Reporter`

**Migration Risk**: **Medium**. The structural typing approach is more flexible but loses compile-time exhaustiveness. Risk: a class may accidentally satisfy a Protocol without intending to. Mitigation: use `@runtime_checkable` + explicit registration in a `PipelineBuilder` that validates all stages at construction time.

---

### 2.2 Task Definition Format (TOML → Python Dataclass)

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `benchmarks/*/tasks/*.toml` — TOML files with `[task]`, `[task.input]`, `[task.expected]` sections |
| **NineS Target** | `src/nines/eval/models.py` — Python dataclasses with TOML serialization |
| **Classification** | Adapt/Transform |

**Mapping**:

EvoBench defines tasks in standalone TOML files loaded by a Rust deserializer. NineS preserves TOML as the external format but adds Python dataclass as the canonical in-memory representation with bidirectional serialization.

```python
@dataclass
class EvalTask:
    id: str  # UUID string, not newtype-wrapped
    name: str
    description: str
    dimension: DimensionKind
    input: TaskInput
    expected: TaskExpected | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    timeout_seconds: float | None = None
    resources: list[TaskResource] = field(default_factory=list)
    difficulty: DifficultyLevel | None = None

    @classmethod
    def from_toml(cls, path: Path) -> EvalTask:
        """Load from TOML file, deserializing tagged unions."""
        ...

    def to_toml(self) -> str:
        """Serialize back to TOML."""
        ...
```

**Key Differences**:
- EvoBench: `TaskId(Uuid)` newtype for compile-time type safety; NineS: plain `str` (UUID validation in `__post_init__`)
- EvoBench: `Duration` requires custom serde (nanosecond encoding); NineS: `float` seconds (simpler, no custom serializer)
- EvoBench: `serde_json::Value` for arbitrary metadata; NineS: `dict[str, Any]` (equivalent, but requires `tomli` for TOML-specific types)
- NineS adds `from_toml()`/`to_toml()` methods directly on the dataclass (EvoBench delegates to the `TaskLoader` trait)

**Migration Risk**: **Medium**. TOML's type system is less expressive than JSON for nested tagged unions. The `[task.input]` → `TaskInput` deserialization requires a manual factory that reads the `type` field and dispatches to the correct dataclass. Risk: TOML doesn't support arbitrary nesting as cleanly as JSON — mitigated by keeping the TOML schema flat and using `toml.loads()` + post-processing.

---

### 2.3 Combinatorial Matrix Evaluation

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-matrix/src/engine.rs` — `MatrixEngine` with 5 strategies (FullCrossProduct, LatinSquare, Pairwise, Random, IrtFiltered) |
| **NineS Target** | `src/nines/eval/matrix.py` — `MatrixEngine` class |
| **Classification** | Adapt/Transform |

**Mapping**:

```python
from itertools import product as cross_product

class MatrixEngine:
    @staticmethod
    def generate(spec: MatrixSpec) -> list[MatrixCell]:
        strategies = {
            "full_cross_product": MatrixEngine._full_cross,
            "latin_square": MatrixEngine._latin_square,
            "pairwise": MatrixEngine._pairwise,
            "random": MatrixEngine._random_sample,
        }
        return strategies[spec.strategy](spec)

    @staticmethod
    def generate_with_constraints(spec: MatrixSpec, constraints: MatrixConstraints) -> list[MatrixCell]:
        cells = MatrixEngine.generate(spec)
        cells = [c for c in cells if not MatrixEngine._is_excluded(c, constraints.exclusions)]
        return cells[:constraints.max_cells]

    @staticmethod
    def _full_cross(spec: MatrixSpec) -> list[MatrixCell]:
        axis_values = [(ax.name, [v.id for v in ax.values]) for ax in spec.axes]
        names = [name for name, _ in axis_values]
        value_lists = [vals for _, vals in axis_values]
        total = 1
        for v in value_lists:
            total *= len(v)
        if spec.max_combinations and total > spec.max_combinations:
            raise MatrixTooLargeError(total, spec.max_combinations, "Use latin_square or pairwise")
        return [
            MatrixCell(coordinates=list(zip(names, combo)))
            for combo in cross_product(*value_lists)
        ]
```

**Key Differences**:
- EvoBench uses a manual odometer-style loop for cross product; NineS uses `itertools.product` (cleaner, identical semantics)
- EvoBench's pairwise uses a hand-rolled PRNG (`seed.wrapping_mul(...)`); NineS uses `random.Random(seed)` with explicit seed for determinism
- IRT filtering is deferred in both implementations — NineS marks it as `NotImplementedError` with a docstring placeholder
- Exclusion rules use the same `all(condition matches)` logic but expressed as a list comprehension filter

**Migration Risk**: **Medium**. The `LatinSquare` and `Pairwise` algorithms require careful reimplementation to ensure identical coverage guarantees. Risk: subtle differences in pseudo-random number generation could cause different coverage patterns — mitigated by testing coverage invariants (e.g., all pairs covered) rather than testing exact cell sequences.

---

### 2.4 Parallel Execution with Budget Guard

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-runner/src/parallel.rs` — `ParallelRunner` (tokio Semaphore + Mutex CostTracker + mpsc channel) |
| **NineS Target** | `src/nines/eval/runner.py` — `ParallelRunner` class |
| **Classification** | Adapt/Transform |

**Mapping**:

```python
import asyncio

class CostTracker:
    def __init__(self, budget: float | None = None):
        self._accumulated = 0.0
        self._budget = budget
        self._lock = asyncio.Lock()

    async def record_and_check(self, cost: float) -> bool:
        async with self._lock:
            self._accumulated += cost
            if self._budget is not None and self._accumulated >= self._budget:
                return True  # budget exceeded
            return False

class ParallelRunner:
    def __init__(self, max_concurrent: int, cost_budget: float | None = None):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tracker = CostTracker(cost_budget)

    async def run_matrix(self, cells, executor, scorer, adapter, tasks, num_trials):
        async def run_cell(cell):
            async with self._semaphore:
                scores = []
                for trial in range(num_trials):
                    if await self._tracker.is_exceeded():
                        break
                    for task in tasks:
                        adapted = await adapter.adapt(task, cell.to_dim_config())
                        result = await executor.execute(adapted)
                        exceeded = await self._tracker.record_and_check(result.cost.total_cost_usd)
                        score = await scorer.score(result, task.expected)
                        scores.append(score)
                        if exceeded:
                            break
                return scores

        results = await asyncio.gather(*[run_cell(cell) for cell in cells])
        return [score for cell_scores in results for score in cell_scores]
```

**Key Differences**:
- EvoBench: `tokio::sync::Semaphore` + `Mutex<CostTracker>` + `mpsc` channel; NineS: `asyncio.Semaphore` + `asyncio.Lock` + `asyncio.gather`
- EvoBench: `tokio::spawn` per cell (true OS-thread parallelism via tokio runtime); NineS: `asyncio.gather` (cooperative concurrency, single-threaded — sufficient for IO-bound agent calls)
- NineS simplifies the channel pattern: `asyncio.gather` returns results directly instead of collecting via mpsc
- Budget guard logic is identical: check before each trial, break on exceed

**Migration Risk**: **Medium**. Python's asyncio provides concurrency but not parallelism. For CPU-bound scoring, this is fine (scoring is fast). For actual agent execution (subprocess calls), `asyncio.create_subprocess_exec` provides true parallelism. Risk: forgetting to use `asyncio.Lock` on the `CostTracker` could cause race conditions — mitigated by encapsulating the lock inside `record_and_check()`.

---

### 2.5 Retry with Exponential Backoff

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-runner/src/retry.rs` — `with_retry()` generic function, `2^attempt * base_delay` capped at `max_delay` |
| **NineS Target** | `src/nines/core/retry.py` — `with_retry()` async decorator/function |
| **Classification** | Adapt/Transform |

**Mapping**:

```python
import asyncio, logging

async def with_retry(
    fn,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    operation_name: str = "operation",
):
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logging.warning(f"{operation_name}: attempt {attempt+1}/{max_retries} failed ({e}), retrying in {delay}s")
                await asyncio.sleep(delay)
    raise last_error
```

**Key Differences**:
- Rust: generic over `FnMut() -> Fut` closure; Python: accepts any async callable
- EvoBench's `tracing::warn!` → Python `logging.warning`
- NineS adds an optional `retry_on: tuple[type[Exception], ...]` parameter to selectively retry only specific exception types (EvoBench retries all errors)

**Migration Risk**: **Low-Medium**. The algorithm is trivial. Risk: Python exceptions are more permissive than Rust errors — a `KeyboardInterrupt` or `SystemExit` should not be retried. Mitigation: catch `Exception` (not `BaseException`) in the retry loop.

---

### 2.6 Multi-Format Report Generation with Templates

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-reporters/src/markdown.rs` — `MarkdownReporter` using Tera templates; `json.rs` — `JsonReporter` |
| **NineS Target** | `src/nines/eval/reporters.py` — `MarkdownReporter` (Jinja2), `JSONReporter` |
| **Classification** | Adapt/Transform |

**Mapping**:

```python
from jinja2 import Environment, FileSystemLoader, BaseLoader
import json

class MarkdownReporter:
    def __init__(self, template_dir: str | None = None):
        if template_dir:
            self._env = Environment(loader=FileSystemLoader(template_dir))
        else:
            self._env = Environment(loader=BaseLoader())
            self._env.from_string(DEFAULT_TEMPLATE)

    async def generate(self, report: EvalReport, config: ReportConfig) -> ReportOutput:
        template = self._env.get_template("report.md")
        rendered = template.render(
            title=report.title,
            run_id=str(report.run_id),
            overall_score=report.summary.overall_score,
            dimensions=report.dimension_reports,
            ...
        )
        output_path = config.output_dir / "report.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered)
        return ReportOutput(path=output_path, size_bytes=len(rendered.encode()))
```

**Key Differences**:
- EvoBench: Tera (Rust template engine, Jinja2-inspired syntax); NineS: Jinja2 directly (identical template syntax)
- EvoBench serializes dimension reports to JSON before inserting into context; NineS passes dataclass objects directly (Jinja2 can access attributes natively)
- NineS adds `CSVReporter` for tabular export (not in EvoBench)

**Migration Risk**: **Low-Medium**. Tera and Jinja2 have nearly identical syntax ({% raw %}`{{ }}`, `{% for %}`{% endraw %}, `| round`). Templates can be migrated with minimal changes. Risk: Tera's `round(precision=N)` filter → Jinja2's `round(N)` — slight syntax difference in filters.

---

### 2.7 Scorer Hierarchy (Exact, Fuzzy, Rubric)

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-scorers/src/exact.rs`, `fuzzy.rs`, `rubric.rs` |
| **NineS Target** | `src/nines/eval/scorers.py` |
| **Classification** | Adapt/Transform |

**Mapping**:

| EvoBench Scorer | NineS Scorer | Notes |
|-----------------|-------------|-------|
| `ExactScorer` | `ExactScorer` | Trimmed string equality → `str.strip()` comparison |
| `FuzzyScorer` | `FuzzyScorer` | Levenshtein + substring ratio. Use `rapidfuzz` library instead of hand-rolled implementation |
| `RubricScorer` | `RubricScorer` | Weighted multi-criterion. EvoBench uses placeholder 3.0 score; NineS integrates LLM-as-judge from the start |
| `CompositeScorer` | `CompositeScorer` | (See Pattern 1.4 above) |

**Key Differences**:
- EvoBench hand-rolls Levenshtein distance; NineS uses `rapidfuzz.distance.Levenshtein` for performance and correctness
- EvoBench's `RubricScorer` is a placeholder (hardcoded 3.0); NineS implements actual rubric scoring with optional LLM-as-judge integration (similar to `context_density_eval.py`'s Anthropic API pattern)
- NineS adds a `RegexScorer` (Python `re` module) that EvoBench defines in types (`Pattern { regex }`) but doesn't implement as a standalone scorer

**Migration Risk**: **Medium**. The `FuzzyScorer` swap to `rapidfuzz` changes the similarity calculation slightly (different normalization). Risk: test results may differ at edge cases. Mitigation: validate against EvoBench's test cases and accept `rapidfuzz` as the reference implementation.

---

### 2.8 Configuration System

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-core/src/config.rs` — `PipelineConfig`, `ReportConfig`, `ChartOptions`, `TracingConfig` with `Default` impls |
| **NineS Target** | `src/nines/core/config.py` — `NinesConfig` with TOML file loading + env/CLI override |
| **Classification** | Adapt/Transform |

**Mapping**:

```python
@dataclass
class PipelineConfig:
    num_trials: int = 5
    max_concurrent: int = 4
    timeout_seconds: float | None = 300.0
    cost_budget: float | None = None
    retry_max: int = 3
    retry_base_delay_seconds: float = 1.0

@dataclass
class ReportConfig:
    formats: list[str] = field(default_factory=lambda: ["markdown", "json"])
    output_dir: str = "reports"
    include_trajectories: bool = True
    include_cost_analysis: bool = True

@dataclass
class NinesConfig:
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    ...

    @classmethod
    def load(cls, path: Path | None = None) -> NinesConfig:
        """3-level merge: defaults → config file → env vars."""
        ...
```

**Key Differences**:
- EvoBench: config is purely in-memory defaults, no file-loading mechanism in `ageneval-core` (TOML loading happens in CLI); NineS: config loading is first-class in `core` with 3-level merge (defaults → file → env/CLI)
- EvoBench: `retry_base_delay_ms` in milliseconds; NineS: `retry_base_delay_seconds` in seconds (Python convention)
- NineS adds environment variable overrides (`NINES_PIPELINE_NUM_TRIALS=10`)

**Migration Risk**: **Low-Medium**. Config structures are nearly identical. The 3-level merge logic is new to NineS but well-understood in Python ecosystems (similar to `pydantic-settings`).

---

## 3. New Design Needed Patterns

### 3.1 4-Dimension Evaluation System → NineS Evaluation Dimensions

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-dimensions/src/` — Tool, Model, Workflow, TaskType dimensions with `Dimension` trait |
| **NineS Target** | `src/nines/eval/dimensions/` — Custom dimension system |
| **Classification** | New Design Needed |

**Why New Design**:

EvoBench's 4 dimensions (Tool, Model, Workflow, TaskType) are designed to evaluate external AI agents in a benchmark setting. NineS has a fundamentally different scope — it evaluates **itself** across three capability vertices:

1. **Evaluation & Benchmarking** — how well NineS evaluates agents
2. **Information Search & Tracking** — how well NineS collects and tracks information
3. **Knowledge Analysis & Decomposition** — how well NineS analyzes and decomposes knowledge

**NineS Dimension Design**:

```python
class NineSDimension(Protocol):
    def kind(self) -> str: ...
    def name(self) -> str: ...
    def description(self) -> str: ...
    def metrics(self) -> list[MetricDefinition]: ...
    def default_scorer(self) -> Scorer: ...
    async def evaluate(self, context: EvalContext) -> DimensionScore: ...
```

| EvoBench Dimension | NineS Absorbs As | Rationale |
|--------------------|-----------------|-----------|
| Tool (T1–T8) | Metric definitions pattern only | NineS doesn't evaluate external tool use; it evaluates its own tool integration quality |
| Model (M1–M8) | Not applicable | NineS doesn't benchmark LLMs directly |
| Workflow (W1–W8) | Partial: `step_efficiency`, `recovery_capability` metrics adapt to self-iteration evaluation | Workflow efficiency metrics apply to NineS's own pipeline |
| TaskType (TT1–TT8) | Not applicable | NineS doesn't categorize external tasks |

NineS defines its own dimensions (from `docs/design/self_eval_spec.md` requirements):
- **Collection Quality** — source coverage, freshness, completeness
- **Analysis Depth** — AST accuracy, decomposition coverage, abstraction quality
- **Eval Fidelity** — scorer accuracy, pipeline reliability, reproducibility
- **Iteration Effectiveness** — gap detection accuracy, improvement rate, convergence speed
- **System Health** — latency, throughput, error rate, resource usage

**Migration Risk**: **High**. The `Dimension` trait structure and `MetricDefinition` model are absorbed directly, but the actual dimensions and their metrics are entirely new. Risk: designing metrics that are meaningful for self-evaluation is an open design problem — mitigated by starting with easily measurable metrics (latency, error rates, test pass rates) and adding judgment-based metrics iteratively.

---

### 3.2 Plugin System with Dependency DAG

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-core/src/plugin.rs` — `PluginRegistry` with topological sort, `Permission` enum, `PluginCapabilityKind`, panic-safe init, auto-disable after 5 errors |
| **NineS Target** | `src/nines/core/plugins.py` — Simplified plugin system |
| **Classification** | New Design Needed |

**Why New Design**:

EvoBench's plugin system is over-engineered for NineS's MVP scope. It includes:
- Full DAG dependency resolution with topological sort
- Permission model (NetworkAccess, FileSystemRead/Write, DockerAccess, etc.)
- Panic recovery (`catch_unwind`)
- Auto-disable after `MAX_ERRORS_BEFORE_DISABLE`
- 6 capability kinds

NineS needs a simpler extensibility mechanism for MVP:

```python
class PluginRegistry:
    """Entry-point based plugin discovery. No DAG, no permissions for MVP."""

    def __init__(self):
        self._scorers: dict[str, type[Scorer]] = {}
        self._reporters: dict[str, type[Reporter]] = {}
        self._collectors: dict[str, type[Collector]] = {}

    def register_scorer(self, name: str, scorer_cls: type[Scorer]) -> None: ...
    def register_reporter(self, name: str, reporter_cls: type[Reporter]) -> None: ...

    @classmethod
    def from_entry_points(cls, group: str = "nines.plugins") -> PluginRegistry:
        """Discover plugins via setuptools entry_points."""
        ...
```

**What NineS Absorbs**:
- The **concept** of typed plugin capabilities (scorer, reporter, collector)
- The **pattern** of a central registry
- The **error resilience** idea (catch exceptions during init, log and continue)

**What NineS Drops for MVP**:
- Dependency DAG and topological sort (no inter-plugin dependencies in MVP)
- Permission model (Python sandbox handles isolation differently — see sandbox design)
- Panic recovery (Python doesn't have `catch_unwind`; use `try/except` at init boundaries)
- Auto-disable after N errors (MVP: fail fast with clear error messages)

**Post-MVP Upgrade Path**: If NineS plugins grow complex, add `graphlib.TopologicalSorter` (stdlib since Python 3.9) for dependency ordering and a `Permission` enum for sandboxed plugin execution.

**Migration Risk**: **Medium-High**. The risk is in scope management: the EvoBench plugin system is sophisticated, and there's pressure to replicate it. Mitigation: start with the minimal entry-point-based registry and add complexity only when actual plugin interdependencies emerge.

---

### 3.3 Deterministic Simulation for Testing

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-cli/src/main.rs` lines 286–414 — `hash_seed()` with per-model/thinking/workflow quality factors, deterministic cost/latency generation |
| **NineS Target** | `src/nines/eval/mock_executor.py` — `DeterministicMockExecutor` |
| **Classification** | New Design Needed |

**Why New Design**:

EvoBench's deterministic simulation is deeply tied to its matrix evaluation of external AI agents (Cursor Agent, Claude Code) with specific quality factors per model/thinking mode/workflow version. NineS doesn't benchmark external models — it evaluates its own capabilities. The simulation needs are fundamentally different:

**NineS Mock Executor Design**:

```python
class DeterministicMockExecutor:
    """Generates deterministic results for testing the eval pipeline without real execution."""

    def __init__(self, seed: int = 42, quality_profile: QualityProfile | None = None):
        self._rng = random.Random(seed)
        self._profile = quality_profile or QualityProfile.default()

    async def execute(self, task: AdaptedTask) -> EvalResult:
        task_hash = hashlib.sha256(task.original.id.encode()).digest()
        combined_seed = int.from_bytes(task_hash[:8], 'big') ^ self._rng.getrandbits(64)
        local_rng = random.Random(combined_seed)

        quality = self._profile.base_quality + local_rng.gauss(0, self._profile.variance)
        quality = max(0.0, min(1.0, quality))

        cost = self._profile.base_cost * local_rng.uniform(0.8, 1.2)
        duration = self._profile.base_duration * local_rng.uniform(0.7, 1.3)

        return EvalResult(
            task_id=task.original.id,
            output=TextOutput(value=f"mock-output-{quality:.4f}"),
            cost=CostRecord(total_cost_usd=cost),
            timing=TimingRecord(total_duration=duration),
            environment=EnvironmentRecord.capture(),
            ...
        )

@dataclass
class QualityProfile:
    base_quality: float = 0.75
    variance: float = 0.1
    base_cost: float = 0.05
    base_duration: float = 2.0

    @classmethod
    def default(cls) -> QualityProfile:
        return cls()
```

**What NineS Absorbs**:
- The **concept** of hash-seeded deterministic execution per cell
- The **pattern** of parameterized quality profiles
- The **principle** that same seed → same results for pipeline testing

**What NineS Redesigns**:
- Drops model/thinking/workflow-specific quality factors (irrelevant for self-evaluation)
- Uses `random.Random(seed)` instead of manual `wrapping_mul` PRNG
- Adds `QualityProfile` as a configurable object (more flexible than hardcoded model tables)

**Migration Risk**: **Medium**. The deterministic property is critical for testing — any non-determinism breaks test reproducibility. Risk: Python's `random.Random` may produce different sequences than Rust's manual PRNG for the same seed. Mitigation: NineS defines its own deterministic contract (tested independently) without trying to match EvoBench's exact outputs.

---

### 3.4 Cross-Version Penetrating Analysis

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-cli/src/main.rs` lines 1217–1249 — Cross-version comparison with stable cell identifiers, quality/pass_rate/cost deltas |
| **NineS Target** | `src/nines/iteration/tracker.py` — `IterationTracker` |
| **Classification** | New Design Needed |

**Why New Design**:

EvoBench compares benchmark runs of external agents across workflow versions (DevolaFlow v3.2→v3.3→v3.4). NineS compares **its own capability scores** across self-iteration cycles. The comparison unit is different:

| Aspect | EvoBench | NineS |
|--------|----------|-------|
| What's compared | Agent benchmark scores across workflow versions | NineS self-evaluation scores across iteration cycles |
| Stable identifier | Matrix cell coordinates (model × tool × workflow) | Capability dimension + metric name |
| Delta computation | quality_delta, cost_delta, pass_rate_delta | metric_delta, convergence_rate |
| Regression detection | Score decreased beyond threshold | Metric regressed beyond acceptable noise margin |
| Output | Cross-version comparison report (Markdown + JSON) | Iteration progress report with convergence analysis |

**NineS Design**:

```python
@dataclass
class IterationSnapshot:
    version: str
    timestamp: datetime
    dimension_scores: dict[str, DimensionScore]
    overall_score: float
    environment: EnvironmentRecord

class IterationTracker:
    def compare(self, baseline: IterationSnapshot, current: IterationSnapshot) -> ComparisonReport:
        """Compare two iteration snapshots, computing deltas and detecting regressions."""
        ...

    def detect_regressions(self, history: list[IterationSnapshot], threshold: float = 0.05) -> list[RegressionItem]:
        """Flag metrics that decreased beyond noise margin across consecutive snapshots."""
        ...

    def convergence_analysis(self, history: list[IterationSnapshot]) -> ConvergenceReport:
        """Determine if iteration is converging (diminishing returns)."""
        ...
```

**What NineS Absorbs**:
- The **pattern** of stable identifiers for cross-run comparison
- The **concept** of delta computation with regression detection
- The `RegressionItem` data model (metric, before, after, change_pct, is_regression)

**What NineS Redesigns**:
- Comparison unit: dimension scores instead of matrix cells
- Adds convergence analysis (not in EvoBench): detecting when self-improvement plateaus
- Adds trend fitting (linear regression on score history) for projection

**Migration Risk**: **High**. The comparison logic is conceptually similar but operationally different. Risk: NineS's self-evaluation scores may be noisy, making regression detection unreliable. Mitigation: use statistical significance tests (e.g., t-test) instead of simple threshold comparison, and require multiple consecutive regressions before flagging.

---

### 3.5 Token Density Classification with Quality Gates

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `eval_scripts/context_density_eval.py` — Token classification (high/medium/low/redundant), go/no-go gates with primary/fallback thresholds |
| **NineS Target** | `src/nines/analyzer/density.py` + `src/nines/iteration/gates.py` |
| **Classification** | New Design Needed |

**Why New Design**:

EvoBench's context density evaluation is specific to DevolaFlow's multi-agent context optimization. NineS needs quality gates for a broader purpose — gating self-iteration cycles.

**What NineS Absorbs**:
- The **tiered gate pattern**: primary threshold → fallback threshold → inconclusive
- The **go/no-go/inconclusive** decision model
- The **quality preservation** concept: optimizations must not degrade quality below a floor

**NineS Gate Design**:

```python
@dataclass
class GateConfig:
    primary_threshold: float
    fallback_threshold: float
    max_fallback_rounds: int = 3

@dataclass
class GateDecision:
    decision: Literal["go", "no-go", "inconclusive"]
    metric_value: float
    threshold_used: float
    round_number: int
    reasoning: str

class QualityGate:
    def __init__(self, config: GateConfig):
        self._config = config

    def evaluate(self, metric_value: float, round_number: int) -> GateDecision:
        threshold = self._config.primary_threshold
        if round_number > self._config.max_fallback_rounds:
            threshold = self._config.fallback_threshold
        if metric_value >= threshold:
            return GateDecision(decision="go", ...)
        elif metric_value < threshold * 0.8:
            return GateDecision(decision="no-go", ...)
        else:
            return GateDecision(decision="inconclusive", ...)
```

**What NineS Drops**:
- Token-level density classification (high/medium/low/redundant) — this is DevolaFlow-specific
- `tiktoken`-based token counting — NineS may add this later for LLM integration but not for MVP

**Migration Risk**: **Medium**. The gate pattern is simple, but choosing the right thresholds for self-iteration requires empirical calibration. Risk: thresholds set too high stall iteration; too low allow quality regression. Mitigation: start with conservative thresholds (inspired by EvoBench's 95% quality preservation) and tune based on baseline measurements.

---

### 3.6 Optimization Lifecycle State Machine

| Field | Detail |
|-------|--------|
| **EvoBench Source** | `crates/ageneval-core/src/optimization.rs` — `OptimizationPlan`, `OptimizationStatus` (Proposed→Approved→Applied→Validated/Rejected/RolledBack), `OptimizationTarget`, `DriftAssessment` |
| **NineS Target** | `src/nines/iteration/planner.py` — `ImprovementPlan` |
| **Classification** | New Design Needed |

**Why New Design**:

EvoBench's optimization system targets external agent configurations (prompts, tools, models). NineS's improvement system targets **its own code and capabilities**. The lifecycle states are similar but the actions and targets differ:

| EvoBench Target | NineS Target |
|-----------------|-------------|
| `Prompt { agent_id }` | Not applicable (NineS doesn't tune agent prompts) |
| `ToolConfig { tool_name }` | `CollectorConfig` (tune collection parameters) |
| `WorkflowStep { step_name }` | `PipelineStep` (tune analysis/eval pipeline) |
| `ModelSelection { current, suggested }` | Not applicable for MVP |
| `SkillComposition { skills }` | `AnalyzerComposition` (tune analyzer combinations) |

**NineS Design**:

```python
class ImprovementStatus(Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLIED = "applied"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"

@dataclass
class ImprovementRecommendation:
    target: str  # module/component path
    action: str
    rationale: str
    expected_improvement: float
    confidence: float
    risk_level: str  # low/medium/high/critical

@dataclass
class ImprovementPlan:
    id: str
    created_at: datetime
    source_eval_id: str
    recommendations: list[ImprovementRecommendation]
    status: ImprovementStatus = ImprovementStatus.PROPOSED
```

**What NineS Absorbs**:
- The **state machine** pattern (Proposed→Approved→Applied→Validated/Rejected/RolledBack)
- The **recommendation model** (target, action, rationale, expected_improvement, confidence, risk_level)
- The **drift assessment** concept (detecting when applied changes cause unintended regressions)
- The **constraints** model (max_cost_increase, min_accuracy_threshold, regression_gate_metrics)

**What NineS Redesigns**:
- Targets are NineS-internal components, not external agent configurations
- `require_human_approval` defaults to `True` for MVP (safety gate)
- Adds `auto_apply` option for low-risk improvements in future iterations

**Migration Risk**: **High**. The state machine is well-defined, but the actual improvement execution (automatically modifying NineS's own code/config) is an open problem for MVP. Risk: the MVP may only reach the "Proposed" state, with human review required for "Applied". Mitigation: for MVP, generate improvement plans as Markdown documents and TOML config patches rather than auto-applying code changes.

---

## 4. Summary Migration Matrix

| # | Pattern | Category | EvoBench Module | NineS Module | Risk |
|---|---------|----------|-----------------|-------------|------|
| 1.1 | Tagged-enum domain modeling | Direct Absorb | `ageneval-core/types.rs` | `nines/core/models.py` | Low |
| 1.2 | Weighted multi-metric scoring | Direct Absorb | `ageneval-dimensions/src/*.rs` | `nines/eval/metrics.py` | Low |
| 1.3 | Reliability statistics | Direct Absorb | `ageneval-scorers/stats.rs` | `nines/eval/metrics.py` | Low |
| 1.4 | Composite scorer chaining | Direct Absorb | `ageneval-scorers/composite.rs` | `nines/eval/scorers.py` | Low |
| 1.5 | Error taxonomy | Direct Absorb | `ageneval-core/error.rs` | `nines/core/errors.py` | Low |
| 1.6 | Environment capture | Direct Absorb | `ageneval-core/types.rs` | `nines/core/models.py` | Low |
| 2.1 | Pipeline composition (traits→Protocols) | Adapt/Transform | `ageneval-core/traits.rs` | `nines/core/protocols.py` | Medium |
| 2.2 | Task definition (TOML→dataclass) | Adapt/Transform | `benchmarks/*/tasks/*.toml` | `nines/eval/models.py` | Medium |
| 2.3 | Matrix evaluation | Adapt/Transform | `ageneval-matrix/engine.rs` | `nines/eval/matrix.py` | Medium |
| 2.4 | Parallel execution + budget guard | Adapt/Transform | `ageneval-runner/parallel.rs` | `nines/eval/runner.py` | Medium |
| 2.5 | Retry with exponential backoff | Adapt/Transform | `ageneval-runner/retry.rs` | `nines/core/retry.py` | Low-Med |
| 2.6 | Multi-format report generation | Adapt/Transform | `ageneval-reporters/src/*.rs` | `nines/eval/reporters.py` | Low-Med |
| 2.7 | Scorer hierarchy | Adapt/Transform | `ageneval-scorers/src/*.rs` | `nines/eval/scorers.py` | Medium |
| 2.8 | Configuration system | Adapt/Transform | `ageneval-core/config.rs` | `nines/core/config.py` | Low-Med |
| 3.1 | Evaluation dimensions | New Design | `ageneval-dimensions/src/` | `nines/eval/dimensions/` | High |
| 3.2 | Plugin system | New Design | `ageneval-core/plugin.rs` | `nines/core/plugins.py` | Med-High |
| 3.3 | Deterministic simulation | New Design | `ageneval-cli/main.rs` | `nines/eval/mock_executor.py` | Medium |
| 3.4 | Cross-version analysis | New Design | `ageneval-cli/main.rs` | `nines/iteration/tracker.py` | High |
| 3.5 | Quality gates | New Design | `eval_scripts/context_density_eval.py` | `nines/iteration/gates.py` | Medium |
| 3.6 | Optimization lifecycle | New Design | `ageneval-core/optimization.rs` | `nines/iteration/planner.py` | High |

---

## 5. Risk Mitigation Priorities

### Critical Path Risks (address first)

1. **Evaluation Dimensions (3.1)**: NineS must define meaningful self-evaluation metrics before any scoring logic is useful. Start with easily measurable operational metrics (latency, error rate, test coverage) and iterate toward capability metrics.

2. **Cross-Version Analysis (3.4)**: Noisy self-evaluation scores can produce false regression alerts. Use statistical tests and require N consecutive regressions before flagging.

3. **Optimization Lifecycle (3.6)**: Auto-applying improvements is an open research problem. For MVP, generate human-readable improvement plans only.

### Implementation Sequence Recommendation

```
Phase 1 (MVP foundation):
  1.1 Domain models → 1.5 Error taxonomy → 2.8 Config →
  2.1 Pipeline protocols → 2.2 Task definitions

Phase 2 (Scoring & evaluation):
  1.2 Metric definitions → 2.7 Scorer hierarchy → 1.4 Composite scorer →
  1.3 Reliability stats → 2.3 Matrix evaluation

Phase 3 (Execution & reporting):
  2.4 Parallel runner → 2.5 Retry → 3.3 Mock executor →
  2.6 Report generation

Phase 4 (Self-iteration):
  3.1 NineS dimensions → 3.5 Quality gates →
  3.4 Cross-version analysis → 3.6 Optimization lifecycle

Phase 5 (Extensibility):
  3.2 Plugin system (post-MVP)
```

### Dependency from EvoBench Not Carried Over

| EvoBench Component | Reason for Exclusion |
|--------------------|---------------------|
| `ageneval-web` (Axum server) | NineS uses CLI-first approach; web dashboard is post-MVP |
| `CursorAgentExecutor`, `ClaudeCodeExecutor` | NineS doesn't benchmark external agents; it IS the agent tool |
| `ModelRegistry` (model aliases) | NineS doesn't manage LLM model configurations |
| ECharts dashboard (`web/index.html`) | Post-MVP visualization; NineS generates data files, visualization is separate |
| `ageneval-optimizer` (empty crate) | Not yet implemented in EvoBench; NineS redesigns from scratch (3.6) |

---

*Document generated for NineS migration planning. Source: EvoBench (AgenEval v0.6.0) analysis.*
*Last modified: 2026-04-12*
