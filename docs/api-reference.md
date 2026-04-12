# API Reference

<!-- auto-updated: version from src/nines/__init__.py -->

Python API overview for NineS {{ nines_version }}. This page documents the key public classes, protocol interfaces, and configuration objects.

---

## Package Entry Point

```python
import nines

print(nines.__version__)  # "{{ nines_version }}"
```

---

## Key Public Classes

### `EvalRunner`

Orchestrates the full evaluation pipeline: load → sandbox → execute → score → report.

```python
from nines.eval import EvalRunner

runner = EvalRunner(config=eval_config)
result = runner.run(task_source="tasks/coding.toml")

print(result.composite_score)
print(result.per_task_scores)
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `run(task_source)` | Execute the full eval pipeline and return `EvalResult` |
| `run_matrix(spec)` | Execute matrix evaluation across N axes |

---

### `GitHubCollector`

GitHub data collector using REST API v3 + GraphQL v4.

```python
from nines.collector.github import GitHubCollector, GitHubConfig

config = GitHubConfig(token="ghp_xxx")
collector = GitHubCollector(config=config, rate_limiter=limiter, cache=cache)

results = collector.search(SearchQuery(
    query="AI agent evaluation",
    source_type=SourceType.GITHUB,
    limit=20,
))

for item in results.items:
    print(f"{item.title} — {item.url}")
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `search(query)` | Search repositories via REST API |
| `fetch(source_id)` | Fetch full repo metadata (REST or GraphQL) |
| `track(source_id)` | Begin tracking a repository |
| `check_updates(since)` | Check tracked repos for changes |
| `health_check()` | Verify API reachability |

---

### `ArxivCollector`

arXiv paper collector using the Atom XML API.

```python
from nines.collector.arxiv import ArxivCollector, ArxivConfig

collector = ArxivCollector(config=ArxivConfig(), rate_limiter=limiter, cache=cache)

results = collector.search(SearchQuery(
    query="LLM self-improvement",
    source_type=SourceType.ARXIV,
    limit=10,
))
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `search(query)` | Search papers by keyword, author, category |
| `fetch(source_id)` | Fetch a paper by arXiv ID |
| `collect_by_category(categories, max_total)` | Bulk collection with pagination |

---

### `CodeReviewer`

AST-based code review with dependency analysis and complexity metrics.

```python
from nines.analyzer.reviewer import CodeReviewer

reviewer = CodeReviewer()
report = reviewer.review_project(parsed_files, project_root=Path("./src"))

print(f"Total functions: {report.total_functions}")
print(f"Avg complexity: {report.avg_complexity}")
for dep in report.dependencies:
    print(f"  {dep.source_module} → {dep.target_module}")
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `review_file(parsed)` | Review a single parsed file |
| `review_project(files, root)` | Multi-file review with cross-file dependencies |

---

### `SelfEvalRunner`

Executes all 19 dimension evaluations and produces a composite score.

```python
from nines.iteration.self_eval import SelfEvalRunner, EvalContext

runner = SelfEvalRunner(evaluators=dimension_evaluators)
context = EvalContext(nines_version="0.1.0")
report = runner.run(context)

print(f"Composite score: {report.composite_score}")
for dim_id, result in report.results.items():
    print(f"  {dim_id}: {result.value}")
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `run(context)` | Execute all dimension evaluators |

---

### `SandboxManager`

Lifecycle management for isolated execution environments.

```python
from nines.sandbox import SandboxManager, SandboxConfig

manager = SandboxManager()
config = SandboxConfig(timeout_seconds=30, seed=42)

handle = manager.create(config)
try:
    result = manager.execute(handle, "print('Hello from sandbox')")
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.stdout}")
    print(f"Fingerprint: {result.fingerprint}")
finally:
    manager.destroy(handle.id)
```

Context manager support:

```python
from nines.sandbox import sandbox_scope

with sandbox_scope(manager, config) as handle:
    result = manager.execute(handle, script)
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `create(config)` | Create a new sandbox with optional venv |
| `execute(handle, script)` | Execute a script string inside the sandbox |
| `execute_file(handle, path)` | Execute a script file |
| `execute_with_pollution_check(handle, script)` | Execute + verify no host pollution |
| `destroy(sandbox_id)` | Clean up sandbox resources |
| `destroy_all()` | Tear down all active sandboxes |

---

## Protocol Interfaces

NineS uses Python `Protocol` classes for structural subtyping. Any class matching the method signatures satisfies the protocol — no inheritance required.

### `Scorer`

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Scorer(Protocol):
    async def score(self, result: EvalResult, expected: TaskExpected) -> EvalScore: ...
    def name(self) -> str: ...
```

Built-in implementations: `ExactScorer`, `FuzzyScorer`, `RubricScorer`, `CompositeScorer`.

### `SourceProtocol`

```python
@runtime_checkable
class SourceProtocol(Protocol):
    @property
    def source_type(self) -> SourceType: ...
    def search(self, query: SearchQuery) -> SearchResult: ...
    def fetch(self, source_id: str) -> SourceItem: ...
    def track(self, source_id: str) -> TrackingHandle: ...
    def check_updates(self, since: datetime) -> list[ChangeEvent]: ...
    def health_check(self) -> HealthStatus: ...
```

Built-in implementations: `GitHubCollector`, `ArxivCollector`.

### `DimensionEvaluator`

```python
@runtime_checkable
class DimensionEvaluator(Protocol):
    spec: DimensionSpec
    def evaluate(self, context: EvalContext) -> DimensionResult: ...
```

19 built-in implementations, one per self-evaluation dimension.

### `PipelineStage`

```python
@runtime_checkable
class PipelineStage(Protocol[T_In, T_Out]):
    @property
    def name(self) -> str: ...
    def process(self, input_data: T_In) -> StageResult[T_Out]: ...
    def supports(self, input_data: T_In) -> bool: ...
```

### `SkillAdapterProtocol`

```python
@runtime_checkable
class SkillAdapterProtocol(Protocol):
    @property
    def runtime_name(self) -> str: ...
    def emit(self, manifest: SkillManifest, engine: TemplateEngine) -> list[EmittedFile]: ...
```

Built-in implementations: `CursorAdapter`, `ClaudeAdapter`.

---

## Configuration Classes

### `NinesConfig`

Central configuration loaded from TOML with 4-level priority merge:

```python
from nines.core.config import NinesConfig

config = NinesConfig.load(config_path="nines.toml")

print(config.eval.default_scorer)      # "composite"
print(config.collect.default_limit)    # 50
print(config.analyze.default_depth)    # "standard"
print(config.sandbox.default_timeout)  # 300
```

### `SandboxConfig`

Immutable configuration for a single sandbox instance:

```python
from nines.sandbox import SandboxConfig, IsolationLevel

config = SandboxConfig(
    timeout_seconds=30,
    max_memory_mb=512,
    seed=42,
    isolation=IsolationLevel.FULL,
    requirements=("numpy",),
)
```

---

## Error Hierarchy

All NineS errors derive from `NinesError`:

```
NinesError
├── ConfigError
│   ├── ConfigFileNotFoundError
│   ├── ConfigParseError
│   └── ConfigValidationError
├── EvalError
│   ├── TaskLoadError
│   ├── TaskExecutionError
│   ├── ScoringError
│   └── BudgetExceededError
├── CollectionError
│   ├── SourceNotFoundError
│   ├── APIError (RateLimitError, AuthenticationError)
│   └── StoreError
├── AnalysisError
│   ├── ParseError
│   ├── ImportResolutionError
│   └── IndexError
├── IterationError
│   ├── BaselineError
│   ├── ConvergenceError
│   └── PlanningError
└── SandboxError
    ├── SandboxCreationError
    ├── SandboxTimeoutError
    └── SandboxPollutionError
```

Every error carries structured fields:

```python
@dataclass
class NinesError(Exception):
    code: str           # "E001", "E010", etc.
    message: str        # Human-readable summary
    category: str       # "config", "eval", "collection", etc.
    detail: str | None  # Extended explanation
    hint: str | None    # Actionable suggestion
```

---

## Event System

The `EventBus` provides lightweight synchronous pub/sub:

```python
from nines.core.events import EventBus, EventType

bus = EventBus.get()

@bus.on(EventType.EVAL_TASK_COMPLETE)
def on_task_complete(event):
    print(f"Task {event.payload['task_id']}: {event.payload['score']}")

bus.emit(EventType.EVAL_TASK_COMPLETE, task_id="t1", score=0.95)
```

Key event types: `EVAL_TASK_COMPLETE`, `COLLECTION_COMPLETE`, `ANALYSIS_COMPLETE`, `SELF_EVAL_COMPLETE`, `GAP_DETECTED`, `CONVERGENCE_REACHED`, `SANDBOX_POLLUTION_DETECTED`.
