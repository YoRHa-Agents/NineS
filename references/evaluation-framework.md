---
id: "nines/references/evaluation-framework"
version: "1.0.0"
purpose: >
  Documents the evaluation and benchmarking system: task definitions, the
  eval runner pipeline, scorer implementations, benchmark generation from
  key points, and self-evaluation dimensions. Load this reference when
  working on eval tasks, scorers, benchmark suites, or self-eval.
triggers:
  - "eval"
  - "benchmark"
  - "self-eval"
  - "scoring"
tier: 2
token_estimate: 1800
dependencies:
  - "nines/SKILL.md"
  - "nines/references/key-point-extraction"
last_updated: "2026-04-14"
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

## 6. Source Files

| File              | Role                          | FRs              |
|-------------------|-------------------------------|------------------|
| `runner.py`       | Eval pipeline orchestration   | FR-114           |
| `models.py`       | TaskDefinition, EvalResult    | FR-101, 102      |
| `scorers.py`      | Scorer implementations        | FR-103, 104, 105, 106 |
| `benchmark_gen.py`| Benchmark suite generation    | FR-115           |
| `metrics.py`      | Metric collection             | (internal)       |
| `analysis.py`     | Result analysis utilities     | (internal)       |
| `matrix.py`       | Evaluation matrix             | (internal)       |
| `mapping.py`      | Mapping utilities             | (internal)       |
| `multi_round.py`  | Multi-round evaluation        | (internal)       |
| `reporters.py`    | Report formatting             | (internal)       |
| `self_eval.py`    | Self-evaluation runner        | FR-601, 602      |
