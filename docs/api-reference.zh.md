# API 参考

<!-- auto-updated: version from src/nines/__init__.py -->

NineS {{ nines_version }} 的 Python API 概览。本页文档化关键的公开类、协议接口和配置对象。

---

## 包入口点

```python
import nines

print(nines.__version__)  # "{{ nines_version }}"
```

---

## 关键公开类

### `EvalRunner`

编排完整的评估流水线：load → sandbox → execute → score → report。

```python
from nines.eval import EvalRunner

runner = EvalRunner(config=eval_config)
result = runner.run(task_source="tasks/coding.toml")

print(result.composite_score)
print(result.per_task_scores)
```

**关键方法：**

| 方法 | 描述 |
|------|------|
| `run(task_source)` | 执行完整的评估流水线并返回 `EvalResult` |
| `run_matrix(spec)` | 执行跨 N 轴的矩阵评估 |

---

### `GitHubCollector`

使用 REST API v3 + GraphQL v4 的 GitHub 数据采集器。

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

**关键方法：**

| 方法 | 描述 |
|------|------|
| `search(query)` | 通过 REST API 搜索仓库 |
| `fetch(source_id)` | 获取完整的仓库元数据（REST 或 GraphQL） |
| `track(source_id)` | 开始跟踪一个仓库 |
| `check_updates(since)` | 检查被跟踪仓库的变更 |
| `health_check()` | 验证 API 可达性 |

---

### `ArxivCollector`

使用 Atom XML API 的 arXiv 论文采集器。

```python
from nines.collector.arxiv import ArxivCollector, ArxivConfig

collector = ArxivCollector(config=ArxivConfig(), rate_limiter=limiter, cache=cache)

results = collector.search(SearchQuery(
    query="LLM self-improvement",
    source_type=SourceType.ARXIV,
    limit=10,
))
```

**关键方法：**

| 方法 | 描述 |
|------|------|
| `search(query)` | 按关键词、作者、类别搜索论文 |
| `fetch(source_id)` | 按 arXiv ID 获取论文 |
| `collect_by_category(categories, max_total)` | 带分页的批量采集 |

---

### `CodeReviewer`

基于 AST 的代码审查，支持依赖分析和复杂度指标。

```python
from nines.analyzer.reviewer import CodeReviewer

reviewer = CodeReviewer()
report = reviewer.review_project(parsed_files, project_root=Path("./src"))

print(f"Total functions: {report.total_functions}")
print(f"Avg complexity: {report.avg_complexity}")
for dep in report.dependencies:
    print(f"  {dep.source_module} → {dep.target_module}")
```

**关键方法：**

| 方法 | 描述 |
|------|------|
| `review_file(parsed)` | 审查单个已解析文件 |
| `review_project(files, root)` | 多文件审查，支持跨文件依赖 |

---

### `SelfEvalRunner`

执行所有 19 个维度评估并产生综合分数。

```python
from nines.iteration.self_eval import SelfEvalRunner, EvalContext

runner = SelfEvalRunner(evaluators=dimension_evaluators)
context = EvalContext(nines_version="0.1.0")
report = runner.run(context)

print(f"Composite score: {report.composite_score}")
for dim_id, result in report.results.items():
    print(f"  {dim_id}: {result.value}")
```

**关键方法：**

| 方法 | 描述 |
|------|------|
| `run(context)` | 执行所有维度评估器 |

---

### `SandboxManager`

隔离执行环境的生命周期管理。

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

上下文管理器支持：

```python
from nines.sandbox import sandbox_scope

with sandbox_scope(manager, config) as handle:
    result = manager.execute(handle, script)
```

**关键方法：**

| 方法 | 描述 |
|------|------|
| `create(config)` | 创建新沙箱，可选带 venv |
| `execute(handle, script)` | 在沙箱内执行脚本字符串 |
| `execute_file(handle, path)` | 执行脚本文件 |
| `execute_with_pollution_check(handle, script)` | 执行 + 验证无宿主机污染 |
| `destroy(sandbox_id)` | 清理沙箱资源 |
| `destroy_all()` | 销毁所有活跃沙箱 |

---

## 协议接口

NineS 使用 Python `Protocol` 类实现结构化子类型。任何匹配方法签名的类都满足协议——无需继承。

### `Scorer`

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Scorer(Protocol):
    async def score(self, result: EvalResult, expected: TaskExpected) -> EvalScore: ...
    def name(self) -> str: ...
```

内置实现：`ExactScorer`、`FuzzyScorer`、`RubricScorer`、`CompositeScorer`。

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

内置实现：`GitHubCollector`、`ArxivCollector`。

### `DimensionEvaluator`

```python
@runtime_checkable
class DimensionEvaluator(Protocol):
    spec: DimensionSpec
    def evaluate(self, context: EvalContext) -> DimensionResult: ...
```

19 个内置实现，每个自评估维度一个。

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

内置实现：`CursorAdapter`、`ClaudeAdapter`。

---

## 配置类

### `NinesConfig`

从 TOML 加载的中央配置，支持 4 级优先合并：

```python
from nines.core.config import NinesConfig

config = NinesConfig.load(config_path="nines.toml")

print(config.eval.default_scorer)      # "composite"
print(config.collect.default_limit)    # 50
print(config.analyze.default_depth)    # "standard"
print(config.sandbox.default_timeout)  # 300
```

### `SandboxConfig`

单个沙箱实例的不可变配置：

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

## 错误层次结构

所有 NineS 错误继承自 `NinesError`：

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

每个错误携带结构化字段：

```python
@dataclass
class NinesError(Exception):
    code: str           # "E001"、"E010" 等
    message: str        # 可读的摘要
    category: str       # "config"、"eval"、"collection" 等
    detail: str | None  # 扩展说明
    hint: str | None    # 可操作的建议
```

---

## 事件系统

`EventBus` 提供轻量级同步发布/订阅：

```python
from nines.core.events import EventBus, EventType

bus = EventBus.get()

@bus.on(EventType.EVAL_TASK_COMPLETE)
def on_task_complete(event):
    print(f"Task {event.payload['task_id']}: {event.payload['score']}")

bus.emit(EventType.EVAL_TASK_COMPLETE, task_id="t1", score=0.95)
```

关键事件类型：`EVAL_TASK_COMPLETE`、`COLLECTION_COMPLETE`、`ANALYSIS_COMPLETE`、`SELF_EVAL_COMPLETE`、`GAP_DETECTED`、`CONVERGENCE_REACHED`、`SANDBOX_POLLUTION_DETECTED`。
