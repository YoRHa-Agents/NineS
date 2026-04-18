---
id: "nines/references/evaluation-framework"
version: "1.1.0"
purpose: >
  Documents the evaluation and benchmarking system: task definitions, the
  eval runner pipeline, scorer implementations, benchmark generation from
  key points, and self-evaluation dimensions. v1.1.0 adds the v2.2.0
  resilience-budget integration (`with_retry`, `CostBudget`,
  `evaluator_budget`). Load this reference when working on eval tasks,
  scorers, benchmark suites, self-eval, or any evaluator that needs
  bounded execution.
triggers:
  - "eval"
  - "benchmark"
  - "self-eval"
  - "scoring"
  - "retry"
  - "budget"
tier: 2
token_estimate: 2000
dependencies:
  - "nines/SKILL.md"
  - "nines/references/key-point-extraction"
  - "nines/references/resilience-budgets"
last_updated: "2026-04-18"
---

# Evaluation Framework Reference

## 1. Overview

The NineS evaluation framework provides two complementary systems:

1. **Task Evaluation** (`nines eval`) — runs defined tasks through a
   validate → execute → score → collect pipeline
2. **Self-Evaluation** (`nines self-eval`) — measures NineS's own health
   across multiple dimensions (coverage, test count, lint cleanliness, etc.)

Both systems feed into the iteration cycle for continuous self-improvement.

## 2. Task Evaluation Pipeline

### EvalRunner (`runner.py`, FR-114)

Orchestrates the evaluation pipeline with three entry points:

| Method        | Purpose                                       |
|---------------|-----------------------------------------------|
| `load_tasks()`| Load `TaskDefinition` objects from TOML files |
| `run()`       | Execute a batch of tasks                      |
| `run_single()`| Execute one task through the full pipeline    |

### Pipeline Stages

```
  TaskDefinition (TOML)
       |
       v
  +----------+    +-----------+    +---------+    +----------+
  | validate |----> execute   |----> score   |----> collect  |
  +----------+    +-----------+    +---------+    +----------+
       |                                                |
       v                                                v
  EvalResult (errors)                            EvalResult (scores)
```

- **Validate** — checks task ID and name are present
- **Execute** — calls the provided `ExecutorFn(task) -> ExecutionResult`
- **Score** — runs each `ScorerProtocol` against output + expected
- **Collect** — records `task_id`, `duration_ms`, `token_count`, scores
  via `MetricCollector`

Composite score is the simple mean of all scorer values.

### TaskDefinition (`models.py`, FR-101, FR-102)

```python
@dataclass
class TaskDefinition:
    id: str
    name: str
    description: str
    dimension: str                          # e.g. "compression"
    input_config: dict[str, Any]
    expected: Any
    scoring_criteria: list[ScoringCriterion]
    metadata: dict[str, Any]
```

Supports TOML round-trip via `to_toml()` / `from_toml()` and dictionary
serialization. Bridges to the lightweight `EvalTask` core model via
`to_core_task()` / `from_core_task()`.

### ScoringCriterion

```python
@dataclass
class ScoringCriterion:
    name: str
    weight: float
    description: str
    scorer_type: str     # "exact", "fuzzy", "rubric", "composite"
    params: dict[str, Any]
```

### EvalResult

```python
@dataclass
class EvalResult:
    task_id: str
    task_name: str
    output: Any
    scores: list[Score]
    composite_score: float
    duration_ms: float
    token_count: int
    success: bool
    error: str | None
```

## 3. Scorer Implementations (`scorers.py`, FR-103–106)

### ScorerProtocol

All scorers satisfy this protocol:

```python
class ScorerProtocol(Protocol):
    def score(self, output: Any, expected: Any) -> Score: ...
    def name(self) -> str: ...
```

### Built-in Scorers

| Scorer            | Output         | Description                          |
|-------------------|----------------|--------------------------------------|
| `ExactScorer`     | 0.0 or 1.0    | Binary exact-match comparison        |
| `FuzzyScorer`     | [0.0, 1.0]    | `SequenceMatcher` ratio similarity   |
| `RubricScorer`    | [0.0, 1.0]    | Checklist-based weighted criteria    |
| `CompositeScorer` | [0.0, 1.0]    | Weighted combination of sub-scorers  |

### RubricScorer Check Functions

Each `RubricItem` supports these check functions:

| `check_fn`    | Behavior                                  |
|---------------|-------------------------------------------|
| `contains`    | `check_value in output`                   |
| `equals`      | `output == check_value`                   |
| `starts_with` | `output.startswith(check_value)`          |
| `present`     | `len(output) > 0`                         |

### ScorerRegistry

Central registry for scorer classes with `register()`, `get()`, and
`list_available()`. Factory method `with_builtins()` pre-registers all
four built-in scorers.

## 4. Benchmark Generation (`benchmark_gen.py`, FR-115)

### BenchmarkGenerator

Transforms `KeyPoint` objects into `TaskDefinition` benchmark suites.

### Per-Category Task Generators

| Category                | Method                          | Tasks Generated |
|-------------------------|---------------------------------|-----------------|
| `compression`           | `_compression_tasks()`          | 2 (size reduction + semantic similarity) |
| `context_management`    | `_context_management_tasks()`   | 1 (token overhead measurement) |
| `behavioral_shaping`    | `_behavioral_shaping_tasks()`   | 1 (rule compliance) |
| `cross_platform`        | `_cross_platform_tasks()`       | 1 (output consistency) |
| `semantic_preservation` | `_semantic_preservation_tasks()` | 1 (semantic equivalence) |
| `engineering`           | `_engineering_tasks()`          | 1 (quality metric check) |

### BenchmarkSuite

```python
@dataclass
class BenchmarkSuite:
    id: str
    name: str
    description: str
    tasks: list[TaskDefinition]
    source_keypoints: list[str]
    metadata: dict[str, Any]
```

Supports `to_toml_dir(path)` to write each task as an individual TOML file
plus a `suite.toml` manifest.

## 5. Self-Evaluation System (`self_eval.py`, FR-601, FR-602)

### SelfEvalRunner

Orchestrates evaluation across registered dimension evaluators.

```python
runner = SelfEvalRunner()
runner.register_dimension("code_coverage", LiveCodeCoverageEvaluator())
runner.register_dimension("test_count", LiveTestCountEvaluator())
report = runner.run_all(version="v1.0.0")
```

### DimensionScore

```python
@dataclass
class DimensionScore:
    name: str           # dimension identifier
    value: float        # raw score
    max_value: float    # upper bound (default 1.0)
    metadata: dict      # additional context
    # normalized property: value / max_value
```

### SelfEvalReport

```python
@dataclass
class SelfEvalReport:
    scores: list[DimensionScore]
    overall: float       # mean of normalized scores
    version: str
    timestamp: str       # ISO-8601
    duration: float      # seconds
```

### Built-in Evaluators

| Evaluator                  | Dimension            | What it Measures         |
|----------------------------|----------------------|--------------------------|
| `CodeCoverageEvaluator`    | `code_coverage`      | Pre-configured coverage % |
| `UnitTestCountEvaluator`   | `test_count`         | Pre-configured test count |
| `ModuleCountEvaluator`     | `module_count`       | Pre-configured module count |
| `LiveCodeCoverageEvaluator`| `code_coverage`      | Real pytest --cov run    |
| `LiveTestCountEvaluator`   | `test_count`         | pytest --collect-only or AST walk |
| `LiveModuleCountEvaluator` | `module_count`       | Counts .py files in src/ |
| `DocstringCoverageEvaluator`| `docstring_coverage`| % of public funcs/classes with docstrings |
| `LintCleanlinessEvaluator` | `lint_cleanliness`   | 100 - (violations * 2)   |

### Live Evaluator Details

**LiveCodeCoverageEvaluator** checks sources in order:
1. Pre-existing coverage file (XML Cobertura or JSON)
2. `pytest --cov={package}` subprocess

**LiveTestCountEvaluator** checks sources in order:
1. `pytest --collect-only -q` (accurate, handles parameterized tests)
2. AST walk fallback (counts `test_*` functions in `test_*.py` files)

## 6. Resilience: `with_retry`, `CostBudget`, `evaluator_budget` (v2.2.0)

The v2.2.0 paradigm-extension work added three composable primitives so
evaluators and the eval runner can opt into bounded execution. **These
shipped in Wave 1** (POCs C04, C05) and are used at the call site —
not auto-applied — so v3.0.0 callers keep working unchanged. For the
full pattern documentation, design history, and worked example, see
`references/resilience-budgets.md`.

### 6.1 `EvalRunner` retry + cost budget (C05)

```python
from nines.core.retry import RetryPolicy, with_retry, TransientError
from nines.core.cost_budget import CostBudget, CostExceeded
from nines.eval.runner import EvalRunner

runner = EvalRunner(
    executor=my_executor,
    scorer=my_scorer,
    retry_policy=RetryPolicy(attempts=cfg.eval_max_retries, base_backoff_s=0.5),
    cost_budget=CostBudget(token_limit=10_000, dollar_limit=1.00),
)
results = runner.run(tasks)  # break-on-CostExceeded; partial-results report
```

- `RetryPolicy` re-raises non-retry-eligible exceptions immediately
  (no silent swallow per workspace rule). `retry_on` defaults to
  `(TransientError,)`; subclass `TransientError` for your own
  retry-eligible failures.
- `EvalRunner.run` catches `CostExceeded`, appends a partial-error
  entry (`{"task_id": ..., "error": "cost_budget_exceeded: ..."}`),
  and breaks the outer loop. Tasks not yet executed are *not* in the
  result list — operators can detect partial completion via the error
  entry.
- `eval_max_retries` (in `NinesConfig`, formerly dead code per
  `01_evobench_gap_analysis.md` §1) now drives the runner's retry
  attempts when wired through the eval CLI.

Tests: `tests/core/test_retry.py` (7 cases), `tests/core/test_cost_budget.py`
(3 cases), `tests/eval/test_runner_retry.py` (2 integration cases).

### 6.2 `SelfEvalRunner` per-evaluator wall budget (C04)

```python
from nines.core.budget import TimeBudget, evaluator_budget
from nines.iteration.self_eval import SelfEvalRunner

runner = SelfEvalRunner(default_budget=TimeBudget(soft_seconds=20, hard_seconds=60))
runner.register_dimension(
    "live_test_count",
    LiveTestCountEvaluator(),
    budget=TimeBudget(soft_seconds=60, hard_seconds=180),  # per-dim override
)
report = runner.run_all(version="v2.2.0")
# report.timeouts == ['agent_analysis_quality']  # populated when budgets breach
```

- Each evaluator runs on a daemon thread (`threading.Thread(daemon=
  True)`); after `hard_seconds` the runner raises
  `EvaluatorBudgetExceeded`, sets the cooperative `cancel_flag`, and
  appends a `DimensionScore(value=0.0, metadata={"status": "timeout",
  "hard_seconds": ..., "elapsed_s": ...})`. The dim name is recorded
  in `report.timeouts`.
- Evaluators that shell out (`Live*`) should also wire
  `subprocess.run(..., timeout=min(self._budget.hard_seconds,
  current_default))` — the daemon-thread cancellation alone cannot
  kill subprocess hangs (N2 risk; planned for Wave 1 follow-up).
- CLI exposes `--evaluator-timeout SECONDS` (default 60); wired via
  `TimeBudget(soft=min(20, max(1, t/2)), hard=max(1, t))`.

**N1 risk reminder:** `_build_json_output` in
`src/nines/cli/commands/self_eval.py` (lines 189-217) currently does
**not** include `report.timeouts` despite `SelfEvalReport.to_dict()`
exposing it. Wave 1 follow-up wires CLI JSON exposure of `timeouts`
and (post-C01) `context_fingerprint` so operators running
`nines self-eval --format json` can detect partial runs.

### 6.3 Worked example — caveman self-eval

Before C04: `nines self-eval --project-root /home/agent/reference/caveman
--src-dir caveman/scripts` hangs ≥ 195 s, killed by external `coreutils
timeout` (exit 137). After C04 with `--evaluator-timeout 30`:

```
wall = 33.3s, exit=0, capability-only complete
20 / 20 dims populated; report.timeouts = ['agent_analysis_quality']
```

A 5.9× speed-up on the failure case while emitting a usable partial
report. See `.local/v2.2.0/benchmark/c04_budget_proof.txt` for the
raw output and `references/resilience-budgets.md` §5 for the
design rationale.

### 6.4 When to opt in

| Evaluator type                                         | `TimeBudget` (default) | Use `with_retry`?     | Use `CostBudget`?  |
|--------------------------------------------------------|------------------------|-----------------------|---------------------|
| In-memory data reads (e.g. `ScoringAccuracyEvaluator`) | `TimeBudget(5, 15)`    | No                    | No                  |
| Subprocess shellout (e.g. `LiveTestCountEvaluator`)    | `TimeBudget(20, 60)`   | If subprocess flaky   | No                  |
| `pytest --collect-only` against foreign repos           | `TimeBudget(60, 180)`  | No (deterministic)    | No                  |
| LLM-judge calls (planned C11b)                          | `TimeBudget(15, 45)`   | **Yes**               | **Yes** (token + $) |
| GitHub / arxiv collectors                               | n/a                    | **Yes** (Wave 1 follow-up) | No             |

## 7. Source Files

| File              | Role                          | FRs / Notes              |
|-------------------|-------------------------------|--------------------------|
| `runner.py`       | Eval pipeline orchestration   | FR-114; v2.2.0 accepts `retry_policy` + `cost_budget` |
| `models.py`       | TaskDefinition, EvalResult    | FR-101, 102              |
| `scorers.py`      | Scorer implementations        | FR-103, 104, 105, 106    |
| `benchmark_gen.py`| Benchmark suite generation    | FR-115                   |
| `metrics.py`      | Metric collection             | (internal)               |
| `analysis.py`     | Result analysis utilities     | (internal)               |
| `matrix.py`       | Evaluation matrix             | (internal)               |
| `mapping.py`      | Mapping utilities             | (internal)               |
| `multi_round.py`  | Multi-round evaluation        | (internal)               |
| `reporters.py`    | Report formatting             | (internal)               |
| `mock_executor.py` | Deterministic mock executor   | v2.2.0 (C06 POC); golden harness pending Wave 2 |
| `self_eval.py`    | Self-evaluation runner        | FR-601, 602; v2.2.0 wraps each evaluator in `evaluator_budget` |
| `core/budget.py`  | `TimeBudget`, `evaluator_budget` | v2.2.0 (C04)         |
| `core/retry.py`   | `RetryPolicy`, `with_retry`   | v2.2.0 (C05)             |
| `core/cost_budget.py` | `CostBudget`, `CostExceeded` | v2.2.0 (C05)         |
