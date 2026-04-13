# Showcase

Explore real-world examples of NineS in action. Each showcase demonstrates how the three-vertex model — Evaluation, Collection, and Analysis — works together to provide actionable insights.

---

## Featured Analyses

### Caveman Repository Analysis

An Agent-oriented analysis of [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman), demonstrating NineS's capability to analyze AI-oriented repositories beyond traditional code metrics:

- **Mechanism decomposition** — Identifying how compression techniques influence Agent behavior
- **Context economics** — Quantifying token overhead vs. savings across the full interaction budget
- **Semantic preservation** — Measuring what survives compression and what's at risk
- **Agent behavioral impact** — Analyzing cross-platform consistency and drift resistance
- **Abstraction & verification** — Six testable hypotheses with verification protocols
- **Community synthesis** — Integrating real-world feedback from HN (333pts) and GitHub

This showcase illustrates how `nines analyze --agent-impact` evaluates AI-oriented repos for their actual effect on Agent effectiveness.

[Read the full Caveman analysis →](caveman-analysis.md)

---

### DevolaFlow Repository Analysis

A deep analysis of [YoRHa-Agents/DevolaFlow](https://github.com/YoRHa-Agents/DevolaFlow), demonstrating NineS's executable evaluation methodology applied to an **orchestration meta-framework** — going beyond simple tool analysis to evaluate how structural decisions shape Agent effectiveness:

- **4-layer agent hierarchy** — Decomposing L0–L3 dispatch architecture and its impact on token budgets
- **Workflow template analysis** — Evaluating 17 built-in templates for task-adaptive routing efficiency
- **Context economics** — Quantifying token savings from layer-specific budgets vs. monolithic approaches
- **Quality gate evaluation** — Analyzing convergence detection and multi-round reliability controls
- **EvoBench dimension mapping** — Aligning 32 evaluation dimensions (T1–T8, M1–M8, W1–W8, TT1–TT8) with agent-facing analysis
- **Benchmark execution** — 15 key points, 30 generated tasks, multi-round sandboxed evaluation with validated conclusions

This showcase demonstrates how NineS extends analysis from simple tools (Caveman) to meta-frameworks (DevolaFlow), evaluating orchestration rules rather than just code artifacts.

[Read the full DevolaFlow analysis →](devolaflow-analysis.md)

---

## Sample Evaluation Tasks

NineS ships with ready-to-run sample tasks in the `samples/` directory:

| Sample | Description | Command |
|--------|-------------|---------|
| Hello World | Basic greeting function evaluation | `nines eval samples/eval/hello_world.toml` |
| FizzBuzz | Classic programming challenge evaluation | `nines eval samples/eval/fizzbuzz.toml` |
| Sorting Algorithm | Merge sort implementation assessment | `nines eval samples/eval/sorting_algorithm.toml` |

### Running a Sample

```bash
# Clone and set up NineS
git clone https://github.com/YoRHa-Agents/NineS.git && cd NineS
uv sync

# Run your first evaluation
uv run nines eval samples/eval/hello_world.toml

# Run with detailed output
uv run nines eval samples/eval/fizzbuzz.toml --scorer composite --format markdown -o report.md
```

---

## Collection Examples

Discover and track AI-related repositories and papers:

```bash
# Search GitHub for AI agent frameworks
uv run nines collect github "AI agent evaluation framework" --limit 10

# Search arXiv for LLM self-improvement research
uv run nines collect arxiv "LLM self-improvement" --limit 5

# Incremental collection with local storage
uv run nines collect github "code analysis tool" --incremental --store ./data/collections
```

---

## Analysis Workflow

Analyze any Python codebase:

```bash
# Quick analysis
uv run nines analyze ./path/to/project --depth standard

# Deep analysis with knowledge indexing
uv run nines analyze ./path/to/project --depth deep --decompose --index

# Generate structured report
uv run nines analyze ./path/to/project --output markdown -o analysis_report.md
```

---

## Self-Improvement Loop

Run the MAPIM self-iteration cycle:

```bash
# Run self-evaluation across all 19 dimensions
uv run nines self-eval

# Start a MAPIM improvement iteration
uv run nines iterate --max-rounds 5

# Compare against a baseline
uv run nines self-eval --baseline v1 --compare
```

---

## Contributing a Showcase

Want to share your NineS analysis? We welcome community showcases:

1. Run your analysis and save the report
2. Create a page under `docs/showcase/` with your findings
3. Open a pull request with your showcase

See the [Contributing Guide](../development/contributing.md) for details.
