# Showcase

Explore real-world examples of NineS in action. Each showcase demonstrates how the three-vertex model — Evaluation, Collection, and Analysis — works together to provide actionable insights.

---

## Featured Analyses

### Caveman Repository Analysis

A complete V3 analysis of an open-source Python repository, demonstrating:

- **AST-based code parsing** — Extracting functions, classes, and module structure
- **Architectural pattern detection** — Identifying design patterns and code organization
- **Dependency graph construction** — Mapping cross-file relationships
- **Knowledge unit extraction** — Breaking code into searchable, reusable units
- **Multi-strategy decomposition** — Functional, concern-based, and layer-based views

This showcase illustrates how `nines analyze` transforms a raw codebase into structured knowledge.

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
