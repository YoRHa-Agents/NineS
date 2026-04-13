# 快速开始

<!-- auto-updated: version from src/nines/__init__.py -->

5 分钟内完成 NineS 的安装和上手。本指南将引导你完成安装、首次评估、信息采集和代码分析。

---

## 前置条件

| 依赖项 | 版本 | 说明 |
|--------|------|------|
| Python | 3.12+ | 通过 `python --version` 检查 |
| [uv](https://docs.astral.sh/uv/) | 最新版 | 推荐的包管理器 |
| Git | 任意版本 | 用于克隆仓库 |

---

## 安装

最快的入门方式是使用一键安装脚本：

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/NineS/main/scripts/install.sh | bash
```

或手动安装：

```bash
git clone https://github.com/YoRHa-Agents/NineS.git && cd NineS
uv sync
```

验证安装：

```bash
uv run nines --version
# nines, version {{ nines_version }}
```

如需了解更多安装方式（pip、可编辑模式、从源码安装），请参阅[安装指南](installation.md)。

---

## 首次评估

创建任务文件 `my_task.toml`：

```toml
[task]
id = "00000000-0000-0000-0000-000000000001"
name = "hello-world-check"
description = "Verify a simple greeting function"
dimension = "code_quality"
difficulty = 1

[task.input]
type = "code"
language = "python"
source = "def greet(name): return f'Hello, {name}!'"

[task.expected]
type = "text"
value = "Hello, World!"
```

运行评估：

```bash
nines eval my_task.toml
```

使用特定评分器和输出格式运行：

```bash
nines eval my_task.toml --scorer composite --format markdown -o report.md
```

!!! tip "沙箱执行"
    添加 `--sandbox` 参数可在隔离环境中运行评估，该环境拥有独立的虚拟环境和临时目录，防止对宿主环境造成任何污染。

---

## 首次采集

在 GitHub 上搜索与 AI 智能体评估相关的仓库：

```bash
nines collect github "AI agent evaluation" --limit 10
```

在 arXiv 上搜索最新论文：

```bash
nines collect arxiv "LLM self-improvement" --limit 5
```

使用增量模式仅获取上次运行以来的新条目：

```bash
nines collect github "AI agent evaluation" --incremental --store ./data/collections
```

---

## 首次分析

分析代码库（或 NineS 自身）：

```bash
nines analyze ./src/nines --depth standard
```

运行深度分析，包含分解和知识索引：

```bash
nines analyze ./src/nines --depth deep --decompose --index
```

输出结构化 Markdown 报告：

```bash
nines analyze ./src/nines --output markdown -o analysis_report.md
```

---

## 配置智能体技能

将 NineS 安装为智能体技能，使 AI 助手能够直接在 IDE 中使用 NineS。NineS 支持 4 种运行时：Cursor、Claude Code、Codex 和 GitHub Copilot。

```bash
# 一次性为所有支持的运行时安装
nines install --target all

# 或为特定运行时安装
nines install --target cursor
nines install --target claude
nines install --target codex
nines install --target copilot
```

!!! tip "一键安装"
    `scripts/install.sh` 脚本可一步完成包安装和技能配置。使用 `--target <runtime>` 为特定运行时安装。

有关智能体技能配置和验证的完整详情，请参阅[智能体技能安装](agent-skill-setup.md)指南。

---

## 后续步骤

| 目标 | 资源 |
|------|------|
| 了解所有安装方式 | [安装指南](installation.md) |
| 将 NineS 安装为智能体技能 | [智能体技能安装](agent-skill-setup.md) |
| 深入了解评估工作流 | [评估指南](user-guide/evaluation.md) |
| 了解自我改进循环 | [自迭代指南](user-guide/self-iteration.md) |
| 浏览完整 CLI | [CLI 参考](user-guide/cli-reference.md) |
| 了解系统架构 | [架构概览](architecture/overview.md) |
