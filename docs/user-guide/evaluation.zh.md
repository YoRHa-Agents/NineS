# 评估指南 (V1)

<!-- auto-updated: version from src/nines/__init__.py -->

NineS V1 提供了一套结构化的评估流水线，用于对 AI 代理能力进行基准测试。任务以 TOML 格式定义，在沙箱中执行，通过插件系统进行评分，并支持多种格式的报告输出。

---

## 任务定义格式

评估任务以 TOML 文件定义，包含类型化输入、期望输出和评分标准。

### 基本任务结构

```toml
[task]
id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
name = "cyclomatic-complexity-detection"
description = "Verify correct cyclomatic complexity computation"
dimension = "code_quality"
difficulty = 3          # 1=trivial, 2=simple, 3=moderate, 4=complex, 5=expert
tags = ["ast", "complexity", "v3-analysis"]
timeout_seconds = 30.0
version = "1.0"

[task.input]
type = "code"           # "text", "code", "conversation", "custom"
language = "python"
source = """
def process(data, mode):
    if mode == 'fast':
        for item in data:
            if item.valid:
                yield item.transform()
    return []
"""

[task.expected]
type = "structured"     # "text", "code", "structured", "pattern"
value = { cyclomatic_complexity = 4 }

[[task.scoring]]
name = "complexity_exact"
weight = 1.0
scorer_type = "exact"
scorer_params = { field = "cyclomatic_complexity" }
```

### 输入类型

| 类型 | 描述 | 字段 |
|------|------|------|
| `text` | 纯文本提示 | `prompt` |
| `code` | 源代码输入 | `language`、`source`、`file_path` |
| `conversation` | 多轮对话消息 | `messages`（`{role, content}` 列表） |
| `custom` | 任意 JSON 数据 | `data`（字典） |

### 期望输出类型

| 类型 | 描述 | 字段 |
|------|------|------|
| `text` | 精确文本匹配 | `value`、`tolerance` |
| `code` | 代码输出 | `value`、`language` |
| `structured` | JSON Schema 匹配 | `schema`、`value` |
| `pattern` | 正则匹配 | `regex` |

---

## 运行评估

### 单个任务

```bash
nines eval tasks/coding.toml
```

### 任务套件（目录）

```bash
nines eval tasks/
```

### 附加选项

```bash
nines eval tasks/ \
  --scorer composite \
  --sandbox \
  --seed 42 \
  --format json \
  -o results.json
```

---

## 可用评分器

NineS 提供四种内置评分器，可通过 `CompositeScorer` 进行组合：

### ExactScorer

二元精确匹配比较。返回 `1.0`（匹配）或 `0.0`（不匹配）。

```bash
nines eval task.toml --scorer exact
```

### FuzzyScorer

基于词元重叠和编辑距离的评分，产生连续的 `[0.0, 1.0]` 分数。组合了词元排序比率（60%）和部分比率（40%）。

```bash
nines eval task.toml --scorer fuzzy
```

在 `nines.toml` 中的配置：

```toml
[eval.scorers.fuzzy]
similarity_threshold = 0.8
algorithm = "token_overlap"
```

### RubricScorer

维度加权的检查清单评分器，支持逐条标准评估。标准在任务 TOML 中定义：

```toml
[[task.scoring]]
name = "correctness"
weight = 0.6
description = "Output matches expected value"
scorer_type = "rubric"
```

### CompositeScorer

链式组合多个评分器，支持两种模式：

- **加权平均** — 所有评分器运行后，结果按权重组合
- **瀑布模式** — 评分器按顺序运行；第一个决定性结果胜出（受 VAKRA 启发）

```bash
nines eval task.toml --scorer composite
```

配置：

```toml
[eval.scorers.composite]
chain = ["exact", "fuzzy"]
waterfall = true
```

---

## 矩阵评估

同时在多个轴上进行评估（任务类型、评分器、难度级别）：

```bash
nines eval tasks/ --matrix --axes difficulty,scorer
```

### 采样策略

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| `full_cross_product` | 所有组合 | 轴基数较小时 |
| `latin_square` | 每个值均匀出现 | 平衡覆盖 |
| `pairwise` | 覆盖每一对 | 大参数空间 |
| `random` | 随机采样 | 探索性评估 |

配置：

```toml
[eval.matrix]
max_cells = 1000
sampling_strategy = "pairwise"
default_trials = 3
```

---

## 可靠性指标

NineS 在多次试验中计算统计可靠性指标：

### pass@k

k 次采样中至少有 1 次正确的概率：

$$\text{pass@k} = 1 - \frac{\binom{n-c}{k}}{\binom{n}{k}}$$

### pass^k（Pass-Power-k）

所有 k 次独立试验均成功的概率：

$$\text{pass}^k = \left(\frac{c}{n}\right)^k$$

### Pass³

Claw-Eval 的严格指标：3 次尝试必须全部通过。是 pass^k 在 k=3 时的特例。

配置：

```toml
[eval.reliability]
min_trials = 3
report_pass_at_k = [1, 3]
report_pass_hat_k = [3]
report_pass3 = true
```

---

## 报告生成

### Markdown 报告

```bash
nines eval tasks/ --format markdown -o report.md
```

报告包含：汇总表、逐任务评分、统计摘要、可靠性指标和建议。

### JSON 报告

```bash
nines eval tasks/ --format json -o results.json
```

机器可读的输出，包含完整的评分数据、耗时和元数据。

### 基线对比

将结果与已存储的基线进行对比：

```bash
nines eval tasks/ --baseline v1 --compare
```

---

## 沙箱执行

启用三层隔离（进程 + 虚拟环境 + 临时目录）：

```bash
nines eval tasks/ --sandbox --seed 42
```

沙箱提供：

- **进程隔离** — 独立 PID，带有资源限制和超时强制执行
- **环境隔离** — 每次评估使用专用虚拟环境
- **文件系统隔离** — 临时工作目录，执行后自动清理
- **污染检测** — 执行前后差异对比，验证宿主未被修改
- **确定性** — 主种子传播至 `PYTHONHASHSEED`、`random`、`numpy`、`torch`

!!! warning "沙箱开销"
    冷启动沙箱创建耗时约 1–5 秒（使用 `uv` 时）。预热沙箱池可将重复评估的耗时降至 1 秒以内。
