# 分析指南 (V3)

<!-- auto-updated: version from src/nines/__init__.py -->

NineS V3 对源代码进行摄取、解析为 AST、分析架构和质量、分解为原子知识单元，并建立索引以支持搜索和检索。

---

## 分析流水线概述

流水线通过五个顺序阶段处理代码：

```mermaid
graph LR
    A[Ingest] --> B[Parse]
    B --> C[Analyze]
    C --> D[Decompose]
    D --> E[Index]
```

| 阶段 | 输入 | 输出 | 关键操作 |
|------|------|------|---------|
| **摄取（Ingest）** | 目录路径 | `RawSource` 列表 | 遍历目录、检查缓存、跳过未变更文件 |
| **解析（Parse）** | 源文件 | `ParsedFile` 列表 | AST 解析、函数/类/导入提取、复杂度计算 |
| **分析（Analyze）** | 解析后的文件 | `StructureMap`、`CouplingMetrics` | 模块边界、层级检测、模式识别、依赖图 |
| **分解（Decompose）** | 分析结果 | `KnowledgeUnit` 列表 | 功能分解、关注点分解、层级分解 |
| **索引（Index）** | 知识单元 | 可搜索索引 | SQLite FTS5、关键词 + 分面搜索 |

---

## 运行分析

### 基本分析

```bash
nines analyze ./target-repo
```

### 深度分析（含分解和索引）

```bash
nines analyze ./target-repo --depth deep --decompose --index
```

### 增量重新分析

仅重新分析自上次运行以来发生变更的文件：

```bash
nines analyze ./target-repo --incremental
```

### 输出格式

```bash
# Markdown 报告
nines analyze ./target-repo --output markdown -o analysis.md

# JSON 输出
nines analyze ./target-repo --output json -o analysis.json
```

---

## 代码审查能力

`CodeReviewer` 对 Python 文件执行基于 AST 的分析：

- **函数提取** — 名称、参数、返回注解、装饰器、文档字符串、行范围
- **类提取** — 名称、基类、方法、类变量、抽象状态
- **导入解析** — 项目内的模块到模块依赖映射
- **圈复杂度** — McCabe 方法，计数 `If`、`While`、`For`、`ExceptHandler`、`BoolOp`、`Assert`、`With` 节点

### 复杂度分布

函数按复杂度分级：

| 级别 | 复杂度 | 评估 |
|------|--------|------|
| 低 | 1–5 | 简单，易于测试 |
| 中 | 6–10 | 中等，可能需要重构 |
| 高 | 11–20 | 复杂，应进行分解 |
| 极高 | 21+ | 需要立即关注 |

配置：

```toml
[analyze.reviewer]
complexity_threshold = 10
extract_docstrings = true
resolve_imports = true
```

---

## 结构分析

`StructureAnalyzer` 检查项目布局和架构：

### 模块边界检测

识别 Python 包（包含 `__init__.py` 的目录）及其关系。

### 架构层级检测

目录通过关键词匹配被分类到架构层级：

| 层级 | 指示关键词 |
|------|-----------|
| 表示层（Presentation） | `cli`、`api`、`web`、`ui`、`views`、`routes`、`controllers` |
| 应用层（Application） | `services`、`usecases`、`commands`、`orchestrator`、`workflows` |
| 领域层（Domain） | `models`、`entities`、`domain`、`core`、`types`、`schemas` |
| 基础设施层（Infrastructure） | `db`、`database`、`repos`、`adapters`、`storage`、`external` |
| 测试层（Testing） | `tests`、`test`、`fixtures`、`conftest`、`mocks` |

### 架构模式检测

| 模式 | 检测信号 | 最低置信度 |
|------|---------|-----------|
| MVC | `models/`、`views/`、`controllers/` | 0.5 |
| 六边形架构（Hexagonal） | `ports/`、`adapters/`、`domain/`、`core/` | 0.5 |
| 分层架构（Layered） | `presentation/`、`application/`、`domain/`、`infrastructure/` | 0.5 |
| 插件/扩展（Plugin/Extension） | ≥3 个基于 Protocol 的类 | 0.5 |

### 耦合度指标

NineS 为每个模块计算：

- **Ca**（传入耦合） — 依赖于该模块的其他模块数量
- **Ce**（传出耦合） — 该模块所依赖的其他模块数量
- **不稳定性** — I = Ce / (Ca + Ce)；0.0 = 最大稳定性

---

## 分解策略

NineS 支持三种分解策略，均可在单次流水线运行中执行：

### 功能分解

每个函数和类成为一个 `KnowledgeUnit`。方法作为其所属类的子单元进行嵌套。

```bash
nines analyze ./target-repo --decompose --strategies functional
```

### 关注点分解

按横切关注点对代码元素进行分组：

| 关注点 | 检测关键词 |
|--------|-----------|
| 错误处理 | `except`、`raise`、`Error`、`Exception`、`try` |
| 日志 | `logger`、`logging`、`log.` |
| 校验 | `validate`、`assert`、`check`、`verify` |
| 序列化 | `to_dict`、`from_dict`、`serialize`、`json` |
| 配置 | `config`、`settings`、`options`、`defaults` |
| I/O 操作 | `read`、`write`、`open`、`save`、`fetch` |

```bash
nines analyze ./target-repo --decompose --strategies concern
```

### 层级分解

将单元分配到结构分析中识别出的架构层级。不匹配任何层级的单元被归类为"未分类"。

```bash
nines analyze ./target-repo --decompose --strategies layer
```

配置：

```toml
[analyze.decomposer]
strategies = ["functional", "concern", "layer"]
functional_granularity = "function"
```

---

## 知识索引与搜索

`KnowledgeIndex` 将分解后的单元存储在 SQLite 中，使用 FTS5 进行搜索：

```bash
# 分析时建立索引
nines analyze ./target-repo --index

# 搜索索引
nines analyze search "authentication middleware"
```

### 搜索能力

- **关键词搜索** — FTS5 全文匹配，涵盖名称、描述、签名、标签
- **分面过滤** — 按语言、类型（函数/类/模块）、复杂度级别、抽象层级过滤
- **排序结果** — BM25 相关性评分

配置：

```toml
[analyze.index]
fts_enabled = true
facets = ["language", "type", "complexity_tier", "source"]
```

---

## 模式抽象

抽象层检测更高层级的设计模式：

| 模式 | 结构信号 |
|------|---------|
| 工厂模式（Factory） | 名为 `create`/`make`/`build` 的方法，返回不同类型 |
| 观察者模式（Observer） | `subscribe`/`register` + `notify`/`emit` 方法 |
| 策略模式（Strategy） | Protocol/ABC 基类 + ≥2 个具体实现 |
| 适配器模式（Adapter） | 包装外部类型并提供 Protocol 兼容方法的类 |
| 装饰器模式（Decorator） | 接受并返回同签名可调用对象的函数 |

!!! note "错误隔离"
    单文件解析错误不会中断流水线。失败的文件会被记录并跳过，结果中会包含结构化的 `FileError` 条目。
