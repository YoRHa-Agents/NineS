# Evaluation Guide (V1)

<!-- auto-updated: version from src/nines/__init__.py -->

NineS V1 provides a structured evaluation pipeline for benchmarking AI agent capabilities. Tasks are defined in TOML, executed in sandboxes, scored through a plugin system, and reported in multiple formats.

---

## Task Definition Format

Evaluation tasks are defined as TOML files with typed inputs, expected outputs, and scoring criteria.

### Basic Task Structure

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

### Input Types

| Type | Description | Fields |
|------|-------------|--------|
| `text` | Plain text prompt | `prompt` |
| `code` | Source code input | `language`, `source`, `file_path` |
| `conversation` | Multi-turn messages | `messages` (list of `{role, content}`) |
| `custom` | Arbitrary JSON data | `data` (dict) |

### Expected Output Types

| Type | Description | Fields |
|------|-------------|--------|
| `text` | Exact text match | `value`, `tolerance` |
| `code` | Code output | `value`, `language` |
| `structured` | JSON schema match | `schema`, `value` |
| `pattern` | Regex match | `regex` |

---

## Running Evaluations

### Single Task

```bash
nines eval tasks/coding.toml
```

### Task Suite (Directory)

```bash
nines eval tasks/
```

### With Options

```bash
nines eval tasks/ \
  --scorer composite \
  --sandbox \
  --seed 42 \
  --format json \
  -o results.json
```

---

## Available Scorers

NineS provides four built-in scorers, composable through the `CompositeScorer`:

### ExactScorer

Binary exact-match comparison. Returns `1.0` (match) or `0.0` (no match).

```bash
nines eval task.toml --scorer exact
```

### FuzzyScorer

Token-overlap and edit-distance scoring producing a continuous `[0.0, 1.0]` score. Combines token sort ratio (60%) and partial ratio (40%).

```bash
nines eval task.toml --scorer fuzzy
```

Configuration in `nines.toml`:

```toml
[eval.scorers.fuzzy]
similarity_threshold = 0.8
algorithm = "token_overlap"
```

### RubricScorer

Dimension-weighted checklist scorer with per-criterion evaluation. Criteria are defined in the task TOML:

```toml
[[task.scoring]]
name = "correctness"
weight = 0.6
description = "Output matches expected value"
scorer_type = "rubric"
```

### CompositeScorer

Chains multiple scorers with two modes:

- **Weighted average** — All scorers run, results combined by weight
- **Waterfall** — Scorers run in order; first decisive result wins (VAKRA-inspired)

```bash
nines eval task.toml --scorer composite
```

Configuration:

```toml
[eval.scorers.composite]
chain = ["exact", "fuzzy"]
waterfall = true
```

---

## Matrix Evaluation

Evaluate across multiple axes simultaneously (task types, scorers, difficulty levels):

```bash
nines eval tasks/ --matrix --axes difficulty,scorer
```

### Sampling Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `full_cross_product` | All combinations | Small axis cardinalities |
| `latin_square` | Each value appears equally | Balanced coverage |
| `pairwise` | Every pair covered | Large parameter spaces |
| `random` | Random sampling | Exploration |

Configuration:

```toml
[eval.matrix]
max_cells = 1000
sampling_strategy = "pairwise"
default_trials = 3
```

---

## Reliability Metrics

NineS computes statistical reliability metrics across multiple trials:

### pass@k

Probability that at least 1 of k samples is correct:

$$\text{pass@k} = 1 - \frac{\binom{n-c}{k}}{\binom{n}{k}}$$

### pass^k (Pass-Power-k)

Probability that ALL k independent trials succeed:

$$\text{pass}^k = \left(\frac{c}{n}\right)^k$$

### Pass³

Claw-Eval's strict metric: all 3 attempts must pass. Special case of pass^k with k=3.

Configuration:

```toml
[eval.reliability]
min_trials = 3
report_pass_at_k = [1, 3]
report_pass_hat_k = [3]
report_pass3 = true
```

---

## Report Generation

### Markdown Reports

```bash
nines eval tasks/ --format markdown -o report.md
```

Reports include: summary table, per-task scores, statistical summary, reliability metrics, and recommendations.

### JSON Reports

```bash
nines eval tasks/ --format json -o results.json
```

Machine-readable output with full score data, timing, and metadata.

### Baseline Comparison

Compare results against a stored baseline:

```bash
nines eval tasks/ --baseline v1 --compare
```

---

## Sandboxed Execution

Enable three-layer isolation (process + venv + tmpdir):

```bash
nines eval tasks/ --sandbox --seed 42
```

The sandbox provides:

- **Process isolation** — Separate PID with resource limits and timeout enforcement
- **Environment isolation** — Dedicated virtual environment per evaluation
- **Filesystem isolation** — Temporary working directory cleaned after execution
- **Pollution detection** — Before/after diff verifies host was not modified
- **Determinism** — Master seed propagation to `PYTHONHASHSEED`, `random`, `numpy`, `torch`

!!! warning "Sandbox Overhead"
    Cold sandbox creation takes ~1–5 seconds (with `uv`). Pre-warmed sandbox pools reduce this to <1 second for repeated evaluations.
