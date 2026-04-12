# 模块详情

<!-- auto-updated: version from src/nines/__init__.py -->

NineS 各模块的详细说明，包括关键类、协议和扩展点。

---

## 模块映射

```
src/nines/
├── core/           # 零依赖基础层
├── eval/           # V1：评估与基准测试
├── collector/      # V2：信息搜索与跟踪
├── analyzer/       # V3：知识分析与分解
├── iteration/      # 自评估与自迭代
├── orchestrator/   # 工作流引擎与跨模块协调
├── sandbox/        # 隔离层
├── skill/          # Agent 技能适配器
└── cli/            # CLI 入口点
```

---

## `core/` — 基础层

所有模块共享的零依赖基础层。`core/` 中的文件不从任何其他 NineS 模块导入。

| 文件 | 职责 |
|------|------|
| `protocols.py` | Protocol 类：`Scorer`、`Executor`、`Collector`、`Analyzer`、`Reporter`、`Loader` |
| `models.py` | 共享数据模型：`TaskDefinition`、`EvalResult`、`ScoreCard`、`SourceItem`、`KnowledgeUnit` |
| `errors.py` | 以 `NinesError` 为根的错误层次结构，包含结构化字段（code、message、hint、location） |
| `events.py` | `EventBus` 单例，同步发布/订阅，类型化的 `Event` 负载 |
| `config.py` | `NinesConfig`，TOML 加载，3 级合并，环境变量覆盖 |

**关键协议：**

- `Scorer` — 对执行结果与预期输出进行评分
- `Executor` — 在隔离环境中执行任务并返回结果
- `Reporter` — 从聚合结果生成输出报告
- `TaskLoader` — 从文件、目录或 glob 模式加载评估任务

**扩展点：** 通过 scorer registry 或 entry points 注册自定义协议实现。

---

## `eval/` — 评估与基准测试（V1）

任务评估、评分、可靠性指标和报告。

| 文件 | 职责 |
|------|------|
| `runner.py` | `EvalRunner`：load → sandbox → execute → score → report 流水线 |
| `scorers.py` | `ExactScorer`、`FuzzyScorer`、`RubricScorer`、`CompositeScorer`，带瀑布式裁判 |
| `metrics.py` | `pass@k`、`pass^k`、`Pass³` 估计器，bootstrap 置信区间 |
| `matrix.py` | `MatrixEvaluator`：N 轴组合评估，带采样策略和预算守卫 |
| `reporters.py` | `JSONReporter`、`MarkdownReporter`、`BaselineComparator` |
| `analysis.py` | `AxisAnalyzer`：逐维度分解、趋势表 |
| `models.py` | `EvalResult`、`ScoreCard`、`MatrixCell`、`ReliabilityMetrics`、`BudgetState` |

**关键类：**

- `EvalRunner` — 编排完整的评估流水线
- `CompositeScorer` — 以加权或瀑布模式链接多个 scorer
- `MatrixEvaluator` — 生成和评估组合测试矩阵

**扩展点：** 通过 `ScorerRegistry.register()` 或 `pyproject.toml` 中 `nines.scorers` 下的 entry points 注册自定义 scorer。

---

## `collector/` — 信息搜索与跟踪（V2）

外部数据发现、采集、跟踪和变更检测。

| 文件 | 职责 |
|------|------|
| `github.py` | `GitHubCollector`：REST 搜索 + GraphQL 深度获取 |
| `arxiv.py` | `ArxivCollector`：关键词搜索、分页、Atom XML 解析 |
| `store.py` | `DataStore`：SQLite CRUD、FTS5 全文搜索、分面筛选 |
| `tracker.py` | `IncrementalTracker`：书签/游标状态、刷新调度 |
| `diff.py` | `ChangeDetector`：快照比较、结构化差异、分类 |
| `scheduler.py` | `CollectionScheduler`：手动触发和基于间隔的周期性采集 |
| `models.py` | `SourceItem`、`Repository`、`Paper`、`ChangeEvent`、`TrackingHandle` |

**关键类：**

- `GitHubCollector` — 完整的 GitHub 集成，支持 REST + GraphQL 和自适应速率限制
- `ArxivCollector` — arXiv 论文采集，支持分页和类别筛选
- `DataStore` — SQLite 存储，支持 CRUD、搜索、导出和缓存操作
- `ChangeDetector` — 基于快照的变更检测，支持字段级差异

**扩展点：** 实现 `SourceProtocol` 并注册到 `SourceRegistry` 即可添加新数据源（≤1 个文件 + ≤20 行注册代码）。

---

## `analyzer/` — 知识分析与分解（V3）

代码分析、结构分解和知识索引。

| 文件 | 职责 |
|------|------|
| `pipeline.py` | `AnalysisPipeline`：ingest → parse → analyze → decompose → index |
| `reviewer.py` | `CodeReviewer`：AST 提取、圈复杂度、导入解析 |
| `structure.py` | `StructureAnalyzer`：目录布局、模块边界、层检测、循环依赖 |
| `decomposer.py` | `Decomposer`：功能、关注点和层级分解策略 |
| `indexer.py` | `KnowledgeIndex`：基于 SQLite FTS5 的存储、关键词 + 分面搜索 |
| `abstraction.py` | `PatternAbstractor`：设计模式识别（Factory、Observer、Strategy、Adapter、Decorator） |
| `search.py` | `SearchEngine`：结合 FTS5 与分面筛选的查询执行 |

**关键类：**

- `AnalysisPipeline` — 端到端流水线，支持逐文件错误隔离
- `CodeReviewer` — 基于 AST 的代码审查，支持耦合度指标（Ca、Ce、I）
- `Decomposer` — 三策略分解为 `KnowledgeUnit` 树
- `KnowledgeIndex` — 可搜索索引，支持 FTS5 和分面筛选

**扩展点：** 实现 `PipelineStage` 协议以添加自定义分析阶段。实现 `Decomposer` 协议以添加新的分解策略。

---

## `iteration/` — 自评估与自迭代

持续自我改进的 MAPIM 循环引擎。

| 文件 | 职责 |
|------|------|
| `self_eval.py` | `SelfEvalRunner`：19 维度评估套件执行 |
| `baseline.py` | `BaselineManager`：创建、存储、列出、比较基线 |
| `gap_detector.py` | `GapDetector`：当前值与目标值比较，排序的差距列表 |
| `planner.py` | `ImprovementPlanner`：每次迭代 ≤3 个行动，行动生成 |
| `convergence.py` | `ConvergenceChecker`：4 方法多数投票（sliding variance、relative improvement、Mann-Kendall、CUSUM） |
| `tracker.py` | `IterationTracker`：MAPIM 循环状态机、进度报告 |
| `history.py` | `ScoreHistory`：时间序列存储、趋势检测 |

**关键类：**

- `SelfEvalRunner` — 执行所有 19 个维度评估器并产生综合分数
- `GapDetector` — 将差距分类为 critical/major/minor/acceptable，并提供根因提示
- `ConvergenceChecker` — 使用 4 方法复合决策的统计收敛检测
- `ImprovementPlanner` — 将差距映射到具体的模块级改进行动

**扩展点：** 实现 `DimensionEvaluator` 协议以添加自定义评估维度。

---

## `orchestrator/` — 工作流引擎

跨模块协调和工作流执行。

| 文件 | 职责 |
|------|------|
| `engine.py` | `WorkflowEngine`：多步工作流定义和执行 |
| `pipeline.py` | `Pipeline`：串行、并行、条件阶段组合 |
| `models.py` | `Workflow`、`Stage`、`StageResult`、`ArtifactRef` |

**关键类：**

- `WorkflowEngine` — 协调多顶点工作流和跨顶点数据流
- `ArtifactStore` — 基于 SQLite 的类型化制品传递，用于顶点间通信

---

## `sandbox/` — 隔离层

无 Docker 的沙箱化执行，三层隔离。

| 文件 | 职责 |
|------|------|
| `manager.py` | `SandboxManager`：生命周期管理（create/reuse/destroy）、池化管理 |
| `runner.py` | `IsolatedRunner`：带资源限制和超时的子进程执行 |
| `isolation.py` | `VenvFactory`：通过 `uv` 或标准库创建虚拟环境、种子控制 |
| `pollution.py` | `PollutionDetector`：执行前后的环境快照差异比较 |

**关键类：**

- `SandboxManager` — 组合三层隔离并管理生命周期
- `IsolatedRunner` — 底层子进程执行，支持 `RLIMIT_AS`、进程组和指纹验证
- `PollutionDetector` — 跨 4 个维度（环境变量、文件、目录、sys.path）验证宿主机未被修改

---

## `skill/` — Agent 技能适配器

Agent 运行时适配器的生成和安装。

| 文件 | 职责 |
|------|------|
| `installer.py` | `SkillInstaller`：安装/卸载编排、版本管理 |
| `manifest.py` | `ManifestGenerator`：从配置 + 版本生成 JSON 清单 |
| `cursor_adapter.py` | `CursorSkillEmitter`：生成 `.cursor/skills/nines/` 目录，包含 SKILL.md 和命令工作流 |
| `claude_adapter.py` | `ClaudeCodeEmitter`：生成 `.claude/commands/nines/` + CLAUDE.md 集成 |

**关键类：**

- `SkillInstaller` — 协调清单加载、版本检查、模板渲染和文件写入
- `CursorAdapter` — 生成 Cursor 兼容的 SKILL.md、命令工作流和参考文档
- `ClaudeAdapter` — 生成 Claude Code 斜杠命令和 CLAUDE.md 集成

**扩展点：** 实现 `SkillAdapterProtocol` 以添加对新 Agent 运行时的支持。

---

## `cli/` — CLI 入口点

面向用户的 Click 命令接口。

| 文件 | 职责 |
|------|------|
| `main.py` | 根命令组：`nines`，全局选项（`--config`、`-v`、`-q`、`--format`、`--no-color`） |
| `commands/eval.py` | `nines eval <TASK_OR_SUITE> [OPTIONS]` |
| `commands/collect.py` | `nines collect <SOURCE> <QUERY> [OPTIONS]` |
| `commands/analyze.py` | `nines analyze <TARGET> [OPTIONS]` |
| `commands/self_eval.py` | `nines self-eval [OPTIONS]` |
| `commands/iterate.py` | `nines iterate [OPTIONS]` |
| `commands/install.py` | `nines install [OPTIONS]` |

CLI 是组合根——它从所有模块导入并在入口时组装完整的依赖图。重型模块使用延迟导入以最小化冷启动时间。
