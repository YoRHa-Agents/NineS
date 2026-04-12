# 示例展示

探索 NineS 的实际应用案例。每个示例展示了三顶点模型 — 评估、采集和分析 — 如何协同工作，提供可操作的洞察。

---

## 精选分析

### Caveman 仓库分析

对一个开源 Python 仓库的完整 V3 分析，展示了：

- **基于 AST 的代码解析** — 提取函数、类和模块结构
- **架构模式识别** — 识别设计模式和代码组织方式
- **依赖图构建** — 映射跨文件关系
- **知识单元提取** — 将代码分解为可搜索、可复用的单元
- **多策略分解** — 功能、关注点和层次视角

此示例展示了 `nines analyze` 如何将原始代码库转换为结构化知识。

---

## 示例评估任务

NineS 在 `samples/` 目录中提供了可直接运行的示例任务：

| 示例 | 描述 | 命令 |
|------|------|------|
| Hello World | 基础问候函数评估 | `nines eval samples/eval/hello_world.toml` |
| FizzBuzz | 经典编程挑战评估 | `nines eval samples/eval/fizzbuzz.toml` |
| 排序算法 | 归并排序实现评估 | `nines eval samples/eval/sorting_algorithm.toml` |

### 运行示例

```bash
# 克隆并设置 NineS
git clone https://github.com/YoRHa-Agents/NineS.git && cd NineS
uv sync

# 运行首次评估
uv run nines eval samples/eval/hello_world.toml

# 运行并输出详细报告
uv run nines eval samples/eval/fizzbuzz.toml --scorer composite --format markdown -o report.md
```

---

## 采集示例

发现和追踪 AI 相关的仓库和论文：

```bash
# 搜索 GitHub 上的 AI 智能体框架
uv run nines collect github "AI agent evaluation framework" --limit 10

# 搜索 arXiv 上的 LLM 自改进研究
uv run nines collect arxiv "LLM self-improvement" --limit 5

# 增量采集并保存到本地
uv run nines collect github "code analysis tool" --incremental --store ./data/collections
```

---

## 分析工作流

分析任意 Python 代码库：

```bash
# 快速分析
uv run nines analyze ./path/to/project --depth standard

# 深度分析并建立知识索引
uv run nines analyze ./path/to/project --depth deep --decompose --index

# 生成结构化报告
uv run nines analyze ./path/to/project --output markdown -o analysis_report.md
```

---

## 自改进循环

运行 MAPIM 自迭代循环：

```bash
# 运行全部 19 个维度的自评估
uv run nines self-eval

# 启动 MAPIM 改进迭代
uv run nines iterate --max-rounds 5

# 与基线进行比较
uv run nines self-eval --baseline v1 --compare
```

---

## 贡献示例

想要分享你的 NineS 分析？我们欢迎社区贡献：

1. 运行分析并保存报告
2. 在 `docs/showcase/` 下创建你的展示页面
3. 提交 Pull Request

详情请参阅[贡献指南](../development/contributing.md)。
