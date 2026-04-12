# NineS

<!-- auto-updated: version from src/nines/__init__.py -->

**多顶点 AI 智能体评估、采集、分析与自迭代**

![Version](https://img.shields.io/badge/version-{{ nines_version }}-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

NineS 是一个基于 Python 的工具包，用于对 AI 智能体能力进行基准测试、发现和追踪外部信息源、将代码库解析为结构化知识，以及通过 MAPIM（度量–分析–规划–改进–度量）循环运行自我改进流程。

---

## 三顶点能力模型

NineS 围绕三个相互关联的顶点组织其能力，通过跨顶点的数据流实现相互增强。

!!! abstract "V1 — 评估与基准测试"

    对 AI 智能体输出进行结构化评估，支持多种评分策略、N 轴矩阵评估，以及 pass@k 和 Pass³ 等可靠性指标。

    **核心功能：** TOML 任务定义、Exact/Fuzzy/Rubric/Composite 评分器、沙箱执行、预算控制、Markdown 和 JSON 报告。

!!! abstract "V2 — 信息采集与追踪"

    发现、获取和追踪与 AI 智能体研究相关的外部数据源。支持带变更检测的增量采集。

    **核心功能：** GitHub REST + GraphQL、arXiv 搜索、SQLite 存储（FTS5）、速率限制采集、基于快照的变更检测。

!!! abstract "V3 — 知识分析与分解"

    通过 AST 解析、架构模式检测和多策略分解，将代码库分析为结构化知识单元。

    **核心功能：** 圈复杂度、跨文件依赖图、功能/关注点/层次分解、知识索引与搜索。

---

## 核心特性

- **智能体技能支持** — 通过 `nines install` 将 NineS 作为技能安装到 Cursor 或 Claude Code
- **自迭代（MAPIM）** — 覆盖 19 个可量化维度的闭环自我改进
- **沙箱评估** — 三层隔离（进程 + 虚拟环境 + 临时目录）并带有污染检测
- **19 个评估维度** — 涵盖从 V1 评分准确性到 V3 结构识别再到全系统收敛率
- **可扩展评分器系统** — 基于协议的评分器，支持注册表和入口点插件发现
- **确定性执行** — 主种子传播，确保评估结果可复现

---

## 快速安装

```bash
# Requires Python 3.12+ and uv
git clone https://github.com/YoRHa-Agents/NineS.git && cd NineS
uv sync
uv run nines --version
```

更多安装方式请参阅[安装指南](installation.md)。

---

## 开始使用

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **快速开始**

    ---

    5 分钟内完成首次评估、采集和分析。

    [:octicons-arrow-right-24: 快速开始](quick-start.md)

-   :material-book-open-variant:{ .lg .middle } **用户指南**

    ---

    评估、采集、分析和自迭代工作流的深入指南。

    [:octicons-arrow-right-24: 用户指南](user-guide/index.md)

-   :material-sitemap:{ .lg .middle } **系统架构**

    ---

    系统设计、模块依赖、数据流图和三顶点模型。

    [:octicons-arrow-right-24: 系统架构](architecture/overview.md)

-   :material-api:{ .lg .middle } **API 参考**

    ---

    Python API 概览，包含核心公开类、协议和配置。

    [:octicons-arrow-right-24: API 参考](api-reference.md)

</div>
