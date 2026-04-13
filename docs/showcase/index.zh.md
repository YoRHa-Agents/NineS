# 示例展示

探索 NineS 的实际应用案例。每个示例展示了三顶点模型 — 评估、采集和分析 — 如何协同工作，提供可操作的洞察。

---

## 精选分析

### Caveman 仓库分析

对 [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) 的面向 Agent 分析，展示 NineS 超越传统代码指标分析 AI 化仓库的能力：

- **机制分解** — 识别压缩技术如何影响 Agent 行为
- **上下文经济学** — 量化整个交互预算中的 Token 开销与节省
- **语义保留** — 测量压缩后保留了什么、丢失了什么
- **Agent 行为影响** — 分析跨平台一致性和漂移抵抗
- **抽象与验证** — 六个可测试假设及验证协议
- **社区反馈综合** — 整合来自 HN（333分）和 GitHub 的真实反馈

此示例展示了 `nines analyze --agent-impact` 如何评估 AI 化仓库对 Agent 效能的实际影响。

[阅读完整的 Caveman 分析 →](caveman-analysis.md)

---

### DevolaFlow 仓库分析

对 [YoRHa-Agents/DevolaFlow](https://github.com/YoRHa-Agents/DevolaFlow) 的深度分析，展示 NineS 可执行评测方法论在**编排元框架**上的应用 — 超越简单工具分析，评估结构性决策如何影响 Agent 效能：

- **4 层 Agent 层级** — 分解 L0–L3 调度架构及其对 Token 预算的影响
- **工作流模板分析** — 评估 17 个内置模板的任务自适应路由效率
- **上下文经济学** — 量化层级特定预算相较于单体方案的 Token 节省
- **质量门控评估** — 分析收敛检测和多轮可靠性控制
- **EvoBench 维度映射** — 将 32 个评估维度（T1–T8、M1–M8、W1–W8、TT1–TT8）与面向 Agent 的分析对齐
- **基准测试执行** — 15 个关键点、30 个生成任务、多轮沙箱化评测与验证结论

此示例展示了 NineS 如何将分析从简单工具（Caveman）扩展到元框架（DevolaFlow），评估编排规则而非仅代码制品。

[阅读完整的 DevolaFlow 分析 →](devolaflow-analysis.md)

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
