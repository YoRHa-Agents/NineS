# CLI 参考

<!-- auto-updated: version from src/nines/__init__.py -->

`nines` CLI 的完整命令参考（版本 {{ nines_version }}）。

---

## 全局选项

所有命令继承以下全局选项：

```
nines [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]
```

| 选项 | 缩写 | 描述 | 默认值 |
|------|------|------|--------|
| `--config PATH` | `-c` | `nines.toml` 配置文件路径 | 自动发现 |
| `--verbose` | `-v` | 启用详细/调试输出 | 关闭 |
| `--quiet` | `-q` | 抑制非错误输出 | 关闭 |
| `--output PATH` | `-o` | 将主输出写入文件 | stdout |
| `--format FORMAT` | `-f` | 输出格式：`text`、`json`、`markdown` | `text` |
| `--no-color` | | 禁用彩色输出 | 关闭 |
| `--version` | | 显示版本并退出 | |
| `--help` | | 显示帮助并退出 | |

---

## `nines eval`

运行评估基准测试以评测代理能力。

```
nines eval <TASK_OR_SUITE> [OPTIONS]
```

### 参数

| 参数 | 描述 |
|------|------|
| `TASK_OR_SUITE` | `.toml` 任务文件路径、任务目录或 glob 模式 |

### 选项

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `--scorer TYPE` | 使用的评分器：`exact`、`fuzzy`、`rubric`、`composite` | `composite` |
| `--sandbox` | 启用沙箱执行 | 从配置读取 |
| `--seed N` | 确定性主种子 | 随机 |
| `--format FORMAT` | 输出格式：`text`、`json`、`markdown` | `text` |
| `--trials N` | 每个任务的独立试验次数 | 1 |
| `--timeout N` | 单任务执行超时（秒） | 120 |
| `--parallel N` | 并行评估工作线程数 | 1 |
| `--baseline VERSION` | 与已存储的基线进行结果对比 | 无 |
| `--compare` | 在报告中显示基线对比 | 关闭 |
| `--matrix` | 启用矩阵评估 | 关闭 |

### 示例

```bash
nines eval tasks/coding.toml
nines eval tasks/ --scorer composite --sandbox --seed 42
nines eval tasks/ --format json -o results.json
nines eval tasks/ --trials 3 --baseline v1 --compare
```

---

## `nines collect`

从已配置的数据源搜索和采集信息。

```
nines collect <SOURCE> <QUERY> [OPTIONS]
```

### 参数

| 参数 | 描述 |
|------|------|
| `SOURCE` | 数据源：`github`、`arxiv` |
| `QUERY` | 搜索查询字符串 |

### 选项

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `--limit N` | 最大结果数 | 50 |
| `--incremental` | 仅获取上次运行后的新项目 | 从配置读取 |
| `--store PATH` | 覆盖数据存储路径 | 从配置读取 |
| `--no-incremental` | 强制完全采集 | 关闭 |

### 示例

```bash
nines collect github "AI agent evaluation" --limit 20
nines collect arxiv "LLM self-improvement" --limit 10
nines collect github "AI agent evaluation" --incremental --store ./data
```

---

## `nines analyze`

分析和分解采集到的知识为结构化单元。

```
nines analyze <TARGET> [OPTIONS]
```

### 参数

| 参数 | 描述 |
|------|------|
| `TARGET` | 要分析的目录或仓库路径 |

### 选项

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `--depth LEVEL` | 分析深度：`shallow`、`standard`、`deep` | `standard` |
| `--decompose` | 启用知识分解 | 从配置读取 |
| `--index` | 启用知识索引 | 从配置读取 |
| `--strategies LIST` | 分解策略（逗号分隔） | `functional,concern,layer` |
| `--output FORMAT` | 报告格式：`text`、`json`、`markdown` | `text` |
| `--incremental` | 仅重新分析已变更的文件 | 关闭 |

### 示例

```bash
nines analyze ./target-repo
nines analyze ./target-repo --depth deep --decompose --index
nines analyze ./target-repo --output markdown -o analysis.md
```

---

## `nines self-eval`

跨能力维度运行自评估。

```
nines self-eval [OPTIONS]
```

### 选项

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `--dimensions DIM,...` | 逗号分隔的维度 ID（如 `D01,D02`） | 全部 |
| `--baseline VERSION` | 与已存储的基线进行对比 | 最新 |
| `--compare` | 显示差异对比 | 关闭 |
| `--report` | 生成详细报告 | 关闭 |
| `--save-baseline TAG` | 将结果保存为新基线 | 无 |
| `--list-baselines` | 列出所有已存储的基线 | 关闭 |
| `--stability-runs N` | 稳定性验证运行次数 | 3 |

### 示例

```bash
nines self-eval
nines self-eval --dimensions D01,D02,D03 --baseline v1 --compare
nines self-eval --report -o self_eval_report.md
nines self-eval --save-baseline v1.1
```

---

## `nines iterate`

执行自改进迭代循环（MAPIM 循环）。

```
nines iterate [OPTIONS]
```

### 选项

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `--max-rounds N` | 最大 MAPIM 迭代次数 | 10 |
| `--convergence-threshold F` | 收敛方差阈值 | 0.001 |
| `--dry-run` | 显示计划的改进但不执行 | 关闭 |
| `--baseline VERSION` | 用于对比的基线 | 最新 |

### 示例

```bash
nines iterate --max-rounds 5
nines iterate --max-rounds 10 --convergence-threshold 0.001 --dry-run
```

---

## `nines install`

安装或卸载 NineS 代理技能。

```
nines install [OPTIONS]
```

### 选项

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `--target TARGET` | 目标运行时：`cursor`、`claude`、`codex`、`copilot`、`all` | 必填 |
| `--uninstall` | 从目标运行时移除 NineS 技能文件 | 关闭 |
| `--global` | 安装到全局用户目录 | 关闭 |
| `--project-dir PATH` | 项目根目录 | 当前目录 |
| `--dry-run` | 显示将执行的操作 | 关闭 |
| `--force` | 覆盖现有安装 | 关闭 |

### 目标运行时

| 目标 | 描述 | 安装目录 |
|------|------|---------|
| `cursor` | Cursor IDE 智能体技能 | `.cursor/skills/nines/` |
| `claude` | Claude Code 斜杠命令 | `.claude/commands/nines/` |
| `codex` | Codex 智能体技能 | `.codex/skills/nines/` |
| `copilot` | GitHub Copilot 指令 | `.github/copilot-instructions.md` |
| `all` | 所有检测到的运行时 | 以上全部 |

### 示例

```bash
nines install --target cursor
nines install --target claude --global
nines install --target codex
nines install --target copilot
nines install --target all --dry-run
nines install --target cursor --uninstall
nines install --target all --uninstall
```

---

## 退出码

| 代码 | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 无效参数或一般错误 |
| 2 | 任务或资源未找到 |
| 3 | 执行失败 |
| 4 | 评分错误 |
| 5 | 沙箱错误 |
| 6 | 预算超限 |
| 7 | 配置错误 |
| 10 | 采集 API 错误 |
| 11 | 速率限制超出 |
| 12 | 认证错误 |

---

## 输出格式

### Text（默认）

可读的彩色输出，包含表格和摘要。

### JSON

机器可读的结构化输出。使用 `-o` 写入文件：

```bash
nines eval tasks/ --format json -o results.json
```

### Markdown

报告风格的输出，包含表格、标题和格式化章节：

```bash
nines eval tasks/ --format markdown -o report.md
```
