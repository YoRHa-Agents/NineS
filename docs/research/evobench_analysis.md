# EvoBench (AgenEval v0.6.0) Deep Analysis

> **Task ID**: T01 — Research Team L3
> **Analyzed**: 2026-04-11
> **Source**: `/home/agent/workspace/EvoBench`

---

## 1. Repository Overview

EvoBench is an AI coding agent evaluation framework implemented as a Rust workspace (9 crates) with a Python evaluation scripting layer and an ECharts-powered web dashboard. Version 0.6.0 uses Rust 2021 edition with `serde`, `tokio`, `async-trait`, and `thiserror` as core workspace dependencies.

**Top-level structure**:
- `crates/` — 9 Rust crates forming the evaluation engine
- `benchmarks/` — TOML task definitions organized by benchmark suite (phase1, devolaflow variants)
- `eval_scripts/` — Python evaluation scripts (context density eval, diff analysis, web data generation)
- `web/` — Single-page ECharts dashboard (`index.html` + JSON data)
- `reports/` — Generated evaluation reports (Markdown, JSON, axis analysis)

---

## 2. Rust Crate Architecture

### 2.1 `ageneval-core` — Foundation Types and Traits

**Purpose**: Defines all shared domain types, trait interfaces, error taxonomy, and configuration structures. Every other crate depends on this.

**Key types** (`crates/ageneval-core/src/types.rs`):
- `TaskId(Uuid)`, `RunId(Uuid)` — Newtype-wrapped UUIDs for type safety
- `DimensionKind` — Enum: `Tool`, `Model`, `Workflow`, `TaskType`
- `DifficultyLevel` — 5-tier: `Trivial`, `Easy`, `Medium`, `Hard`, `Expert`
- `TaskInput` — Tagged enum with 6 variants: `Text`, `Conversation`, `ToolUse`, `CodePatch`, `Workflow`, `Custom`
- `TaskExpected` — Tagged enum: `ExactMatch`, `Pattern`, `ToolCalls`, `StateChange`, `Rubric`, `Custom`
- `TaskOutput` — Tagged enum: `Text`, `ToolCalls`, `CodePatch`, `StateChange`, `Error`, `Custom`
- `EvalTask` — Full task definition including id, name, dimension, input, expected, metadata, tags, timeout, resources, difficulty
- `EvalResult` — Execution result: output, trajectory steps, cost record, timing record, environment
- `EvalScore` — Score result: per-metric scores, overall_score, label (Pass/Fail/Partial/Error/Skipped), explanation
- `MetricScore` — Individual metric: name, value, max_value, weight, details HashMap
- `ReliabilityMetrics` — pass@k, pass^k, consistency
- `EvalReport` — Full report: summary, dimension reports, matrix report, optimization report
- `TokenUsage`, `CostRecord`, `TimingRecord`, `EnvironmentRecord`, `TrajectoryStep`

**Key traits** (`crates/ageneval-core/src/traits.rs`):
- `TaskLoader` — `async fn load_tasks(&self, source: &TaskSource) -> Result<Vec<EvalTask>>`
- `MatrixExpander` — `fn expand(&self, tasks, spec) -> Result<Vec<MatrixCell>>`
- `TaskAdapter` — `async fn adapt(&self, task, dimension_config) -> Result<AdaptedTask>`
- `Executor` — `async fn execute(&self, task: &AdaptedTask) -> Result<EvalResult>` + `fn capabilities()`
- `DataCollector` — `async fn collect(&self, result: &mut EvalResult)`
- `Scorer` — `async fn score(&self, result, expected) -> Result<EvalScore>`
- `Aggregator` — `async fn aggregate(&self, scores, config) -> Result<EvalReport>`
- `Reporter` — `async fn generate(&self, report, config) -> Result<ReportOutput>`

**Dimension trait** (`crates/ageneval-core/src/dimension.rs`):
- `Dimension` trait: `kind()`, `name()`, `description()`, `metrics()`, `default_scorer()`, `adapt_task()`, `validate_config()`
- `MetricDefinition` — name, description, value_type (Float/Integer/Boolean/Percentage), direction (HigherIsBetter/LowerIsBetter), default_weight

**Error taxonomy** (`crates/ageneval-core/src/error.rs`):
- `EvalError` — 14 variants covering every pipeline stage: `TaskLoad`, `TaskValidation`, `Execution`, `Scoring`, `Aggregation`, `Report`, `MatrixTooLarge`, `Optimization`, `Plugin`, `Config`, `Cancelled`, `BudgetExceeded`, `Timeout`, `Io`, `Serialization`, `Internal`
- `PluginError` — 7 variants: `DuplicateName`, `MissingDependency`, `CyclicDependency`, `InitFailed`, `Panic`, `PermissionDenied`, `Custom`

**Plugin system** (`crates/ageneval-core/src/plugin.rs`):
- `PluginRegistry` with topological sort for dependency resolution
- `Plugin` trait with `on_init`/`on_shutdown` lifecycle hooks
- `PluginMetadata` with permissions (NetworkAccess, FileSystemRead/Write, DockerAccess, LlmApiAccess, ShellExec)
- Plugin capabilities: Dimension, Scorer, Reporter, Metric, Executor, TaskLoader
- Panic-safe init with `catch_unwind`
- Auto-disable after `MAX_ERRORS_BEFORE_DISABLE` (5 errors)

**Configuration** (`crates/ageneval-core/src/config.rs`):
- `PipelineConfig` — num_trials (5), max_concurrent (4), timeout (300s), cost_budget, retry_max (3), retry_base_delay_ms (1000)
- `ReportConfig` — formats (Markdown, Json, Feishu, Html, Csv), output_dir, include_trajectories, chart_options
- `ChartOptions` — accuracy_vs_cost, dimension_radar, reliability_histogram, trend_line

**Matrix types** (`crates/ageneval-core/src/matrix.rs`):
- `MatrixSpec` — axes, strategy, max_combinations, parallelism
- `CombinationStrategy` — `FullCrossProduct`, `LatinSquare`, `Pairwise`, `Random{sample_size}`, `IrtFiltered{pass_rate_min, pass_rate_max}`
- `MatrixConstraints` — max_cells, sampling strategy (Uniform/Stratified/LatinHypercube/PriorityWeighted/AdaptiveIRT), exclusion rules
- `SamplingStrategy` — includes `AdaptiveIRT{initial_ratio}` for Item Response Theory-based adaptive sampling

**Optimization types** (`crates/ageneval-core/src/optimization.rs`):
- `OptimizationPlan` — recommendations, constraints, status lifecycle (Proposed→Approved→Applied→Validated/Rejected/RolledBack)
- `OptimizationTarget` — Prompt, ToolConfig, WorkflowStep, ModelSelection, SkillComposition
- `OptimizationConstraints` — max_cost_increase_pct (50%), min_accuracy_threshold (0.6), regression_gate_metrics, require_human_approval
- `DriftAssessment` — semantic_drift, behavioral_drift, performance_regression items

**Dependencies**: serde, serde_json, toml, thiserror, uuid, chrono, async-trait, tracing

### 2.2 `ageneval-runner` — Pipeline Orchestration

**Purpose**: Implements the evaluation pipeline runner, parallel execution engine, retry logic, and executor backends.

**Key components**:

- `EvalPipeline` (`crates/ageneval-runner/src/pipeline.rs`) — Composes loader→adapter→executor→scorer. The `run_evaluation` method iterates tasks × trials, calling `run_single_task` which chains adapt→execute→score.

- `ParallelRunner` (`crates/ageneval-runner/src/parallel.rs`) — Semaphore-bounded concurrent execution of matrix cells. Uses `tokio::sync::Semaphore` for concurrency limiting, `CostTracker` (with `Mutex`) for real-time budget enforcement, and `mpsc` channels for result collection. Budget checks happen before each trial.

- `RetryConfig` + `with_retry` (`crates/ageneval-runner/src/retry.rs`) — Exponential backoff retry with configurable max_retries, base_delay, max_delay. Uses `2^attempt * base_delay` capped at max_delay.

- Executors (`crates/ageneval-runner/src/executors/`):
  - `CursorAgentExecutor` — Spawns `cursor-agent` CLI with model and thinking mode flags
  - `ClaudeCodeExecutor` — Spawns `claude` CLI with model and thinking mode flags
  - Both support dry-run mode (returns synthetic results) and real execution via `tokio::process::Command`
  - `ModelRegistry` — Maps aliases (`opus4.6`, `sonnet4.6`, `gpt5.4`) to provider/model/display info
  - `thinking_mode_param()` — Maps agent tool + thinking mode to CLI arguments

**Dependencies**: ageneval-core, tokio, tracing, async-trait, serde_json, uuid, chrono

### 2.3 `ageneval-dimensions` — 4-Dimension Evaluation System

**Purpose**: Implements the four evaluation dimensions, each with 8 metrics.

**Tool Dimension** (`crates/ageneval-dimensions/src/tool.rs`) — Metrics T1–T8:
| Metric | Weight | Direction |
|--------|--------|-----------|
| call_success_rate | 0.20 | HigherIsBetter |
| tool_selection_accuracy | 0.20 | HigherIsBetter |
| parameter_quality | 0.15 | HigherIsBetter |
| latency_p95 | 0.10 | LowerIsBetter |
| error_handling_quality | 0.10 | HigherIsBetter |
| multi_tool_orchestration | 0.15 | HigherIsBetter |
| resource_consumption | 0.05 | LowerIsBetter |
| mcp_compliance | 0.05 | HigherIsBetter |

**Model Dimension** (`crates/ageneval-dimensions/src/model.rs`) — Metrics M1–M8:
| Metric | Weight | Direction |
|--------|--------|-----------|
| task_accuracy | 0.20 | HigherIsBetter |
| inference_speed | 0.10 | HigherIsBetter |
| token_efficiency | 0.15 | HigherIsBetter |
| cost_efficiency | 0.10 | HigherIsBetter |
| consistency | 0.15 | HigherIsBetter |
| instruction_following | 0.10 | HigherIsBetter |
| reasoning_quality | 0.10 | HigherIsBetter |
| context_utilization | 0.10 | HigherIsBetter |

**Workflow Dimension** (`crates/ageneval-dimensions/src/workflow.rs`) — Metrics W1–W8:
| Metric | Weight | Direction |
|--------|--------|-----------|
| completion_rate | 0.20 | HigherIsBetter |
| step_efficiency | 0.15 | HigherIsBetter |
| backtrack_rate | 0.10 | LowerIsBetter |
| robustness | 0.15 | HigherIsBetter |
| recovery_capability | 0.15 | HigherIsBetter |
| planning_quality | 0.10 | HigherIsBetter |
| parallelism_effectiveness | 0.10 | HigherIsBetter |
| time_to_completion | 0.05 | LowerIsBetter |

Also defines `WorkflowPattern` enum: `ReAct`, `PlanAndExecute`, `TreeOfThought`, `Reflexion`, `MultiAgent`, `Custom`.

**TaskType Dimension** (`crates/ageneval-dimensions/src/task_type.rs`) — Metrics TT1–TT8:
| Metric | Weight | Direction |
|--------|--------|-----------|
| coding_score | 0.15 | HigherIsBetter |
| research_score | 0.15 | HigherIsBetter |
| debugging_score | 0.15 | HigherIsBetter |
| design_score | 0.15 | HigherIsBetter |
| documentation_score | 0.10 | HigherIsBetter |
| data_analysis_score | 0.10 | HigherIsBetter |
| adaptability_score | 0.10 | HigherIsBetter |
| cross_category_transfer | 0.10 | HigherIsBetter |

Also defines `TaskCategory` enum: `Coding`, `Conversation`, `KnowledgeRetrieval`, `Creative`, `DataAnalysis`, `Planning`, `ToolUse`, `Safety`, `Custom`.

Each dimension enforces **weights summing to 1.0** (validated in unit tests). Each provides a `DefaultScorer` (placeholder) and implements `Dimension::adapt_task` for task transformation.

**Dependencies**: ageneval-core, serde, serde_json, async-trait

### 2.4 `ageneval-matrix` — Combinatorial Test Generation

**Purpose**: Generates matrix cells from axis specifications using multiple combination strategies.

**MatrixEngine** (`crates/ageneval-matrix/src/engine.rs`):
- `full_cross_product` — Odometer-style cartesian product with optional max cap (returns `MatrixTooLarge` error)
- `latin_square` — N cells where N = max axis length, rotating indices for coverage
- `pairwise` — Greedy algorithm ensuring every pair of values from any two axes appears at least once. Uses deterministic seeded pseudo-random with tracked pair coverage
- `random_sample` — Full cross product then deterministic shuffle + truncate
- `IrtFiltered` — Currently delegates to full cross product (Phase 2 planned)
- `generate_with_constraints` — Applies exclusion rules and max_cells cap post-generation

**Dependencies**: ageneval-core, serde, serde_json, itertools

### 2.5 `ageneval-scorers` — Scoring Strategies

**Purpose**: Implements scoring algorithms from binary to composite weighted aggregation.

**ExactScorer** (`crates/ageneval-scorers/src/exact.rs`):
- Trimmed string equality. Returns 1.0/Pass or 0.0/Fail.

**FuzzyScorer** (`crates/ageneval-scorers/src/fuzzy.rs`):
- Combines Levenshtein edit distance similarity with substring containment ratio
- `fuzzy_similarity(expected, output)` → [0, 1]: `max(edit_sim, contains_sim)`
- Case-insensitive, whitespace-normalized
- Labels: ≥0.999 = Pass, >0 = Partial, else Fail

**RubricScorer** (`crates/ageneval-scorers/src/rubric.rs`):
- Per-criterion scoring on a scale. Currently uses placeholder score (3.0)
- Weighted aggregation: `Σ(normalized_score × weight) / Σ(weight)`
- Each criterion has levels with score, label, and description

**CompositeScorer** (`crates/ageneval-scorers/src/composite.rs`):
- Chains multiple scorers with individual weights
- `CompositeScorer::new(scorers, weights)` or `CompositeScorer::uniform(scorers)`
- Weighted combination: `Σ(scorer.overall_score × weight) / Σ(weight)`
- Metric names prefixed with `composite::` to avoid collision
- Labels: ≥1.0-ε = Pass, ≤ε = Fail, else Partial

**Statistics** (`crates/ageneval-scorers/src/stats.rs`):
- `pass_at_k(n, c, k)` — Probability at least 1 of k samples is correct: `1 - C(n-c,k)/C(n,k)`
- `pass_pow_k(n, c, k)` — Probability ALL k trials succeed: `(c/n)^k`
- `consistency(scores)` — `1 - (std_dev / mean)` for score stability

**Dependencies**: ageneval-core, serde, serde_json, regex, async-trait

### 2.6 `ageneval-reporters` — Multi-Format Report Generation

**Purpose**: Generates evaluation reports in multiple formats.

**JsonReporter** (`crates/ageneval-reporters/src/json.rs`):
- Serializes `EvalReport` to pretty-printed JSON, writes to output_dir/report.json

**MarkdownReporter** (`crates/ageneval-reporters/src/markdown.rs`):
- Uses Tera templates for Markdown generation
- Default template includes executive summary, dimension details tables
- Supports custom template directories via `with_template_dir()`

**PlottersRenderer** (`crates/ageneval-reporters/src/charts.rs`):
- Placeholder SVG generation for dimension radar, Pareto scatter, and heatmap charts
- Designed for Phase 2 implementation with the `plotters` crate

**Dependencies**: ageneval-core, serde, serde_json, tokio, tera, async-trait

### 2.7 `ageneval-optimizer` — Benchmark Optimization

**Purpose**: Planned optimization engine (currently empty `lib.rs`). The optimization data model is fully defined in `ageneval-core/src/optimization.rs` including `OptimizationPlan`, `Recommendation`, `DriftAssessment`, and the full lifecycle status machine.

**Dependencies**: ageneval-core, serde, serde_json, async-trait

### 2.8 `ageneval-cli` — Command-Line Interface

**Purpose**: CLI entry point for running matrix benchmarks and cross-version comparisons.

**Commands** (`crates/ageneval-cli/src/main.rs`):
- `ageneval matrix <config.toml>` — Run matrix benchmark with progress bar (`indicatif`), per-cell scoring, reliability stats, and multi-format report generation
- `ageneval compare <inputs...>` — Cross-version comparison across configurable dimensions (model, agent_tool, thinking_mode, workflow)
- `ageneval plugins` — List registered plugins and their metrics

**Key implementation details**:
- TOML config deserialization into `MatrixTomlConfig` → `MatrixSpec` + `MatrixConstraints`
- Deterministic simulation via `hash_seed()` function for reproducible dry-run benchmarks
- Quality factors: per-model (`opus4.6=0.92`, `sonnet4.6=0.85`, `gpt5.4=0.88`), per-thinking-mode (`max=+0.06`, `high=+0.03`), per-workflow (DevolaFlow versions scale from 0.97 to 1.13)
- Multi-dimensional scoring: quality_score = weighted(accuracy × 0.45, token_eff × 0.25, consistency × 0.30), cost_score = weighted(cost_eff × 0.60, latency_eff × 0.40)
- Report generation: benchmark_results.json, benchmark_report.md, axis_analysis.md
- Cross-version comparison generates per-dimension analysis with deltas, version trend, best combinations, and penetrating matrix

**Dependencies**: ageneval-core, ageneval-matrix, ageneval-runner, ageneval-scorers, ageneval-reporters, clap, tokio, tracing-subscriber, serde, serde_json, toml, uuid, chrono, indicatif, color-eyre

### 2.9 `ageneval-web` — Web Dashboard Server

**Purpose**: Placeholder Axum web server (currently just `fn main() {}`). The actual dashboard is a static HTML file at `web/index.html` with ECharts visualizations consuming JSON data files.

**Dependencies**: ageneval-core, ageneval-runner, axum, tokio, tower, tracing-subscriber

---

## 3. TOML Task Definition Format

Tasks are defined in TOML files under `benchmarks/*/tasks/*.toml`. The schema has three main sections:

### 3.1 Schema Structure

```toml
[task]
name = "task_identifier"              # unique snake_case name
description = "Human description"     # what the task tests
dimension = "Model"                   # DimensionKind: Model, Tool, Workflow, TaskType
complexity = "high"                   # optional: low/medium/high
source_benchmark = "..."              # optional: attribution

[task.input]
type = "Text"                         # TaskInput variant
prompt = """multi-line prompt"""       # for Text type

[task.expected]
type = "ExactMatch"                   # TaskExpected variant
value = "expected output"             # for ExactMatch type
```

### 3.2 Supported TaskExpected Types

1. **ExactMatch** — Exact string comparison (used in `simple_bug_fix.toml`, `code_review.toml`)
   ```toml
   [task.expected]
   type = "ExactMatch"
   value = "exact expected string"
   ```

2. **QualityCriteria** — List of human-readable evaluation criteria (used in `architecture_design.toml`)
   ```toml
   [task.expected]
   type = "QualityCriteria"
   criteria = [
       "Criterion 1 description",
       "Criterion 2 description",
   ]
   ```

3. **Pattern** — Regex matching (`types.rs`: `Pattern { regex: String }`)

4. **ToolCalls** — Expected tool call sequence with optional argument matching and ordering (`types.rs`: `ToolCalls { calls: Vec<ExpectedToolCall> }`)

5. **StateChange** — Before/after state diff as JSON values

6. **Rubric** — Weighted multi-criterion rubric with score levels

### 3.3 Task Coverage (Phase 1)

22 tasks spanning difficulty 0.2–0.93:
- **Low** (0.2–0.4): simple_bug_fix, code_generation, research_question, code_review
- **Medium** (0.5–0.7): debugging, test_generation, codebase_comprehension
- **High** (0.75–0.93): multi_file_refactoring, feature_implementation, architecture_design, security_vulnerability, cross_language_port, concurrent_system_debugging, issue_to_patch, library_orchestration, review_iteration_loop, monorepo_api_migration, data_pipeline_recovery, container_build_repair, competitive_algorithm, cross_service_saga, flaky_test_diagnosis

---

## 4. 4-Dimension Evaluation System

The evaluation model measures AI agents across four orthogonal dimensions, each with 8 weighted metrics summing to 1.0:

| Dimension | Focus | Example Metrics |
|-----------|-------|-----------------|
| **Tool** (T1–T8) | Tool calling and orchestration | call_success_rate, tool_selection_accuracy, mcp_compliance |
| **Model** (M1–M8) | Model intelligence and efficiency | task_accuracy, token_efficiency, reasoning_quality |
| **Workflow** (W1–W8) | Agent workflow patterns | completion_rate, recovery_capability, planning_quality |
| **TaskType** (TT1–TT8) | Cross-category competence | coding_score, debugging_score, cross_category_transfer |

Each dimension is implemented as a struct implementing the `Dimension` trait, which provides:
- Metric definitions with value types and optimization directions
- A default scorer for that dimension
- A task adapter that transforms tasks for dimension-specific evaluation
- Config validation

The `MetricDirection` enum (`HigherIsBetter`, `LowerIsBetter`) enables correct aggregation: some metrics like latency and backtrack_rate are "lower is better."

---

## 5. Evaluation Pipeline Flow

The pipeline follows an 8-stage architecture defined by the trait hierarchy in `ageneval-core/src/traits.rs`:

```
[1] TaskLoader → load tasks from source (File, Directory, Url, Inline)
        ↓
[2] MatrixExpander → expand tasks × axis combinations into MatrixCells
        ↓
[3] TaskAdapter → adapt each task for dimension-specific evaluation
        ↓
[4] Executor → execute adapted task (real or dry-run)
        ↓
[5] DataCollector → collect additional metrics from execution
        ↓
[6] Scorer → score result against expected output
        ↓
[7] Aggregator → aggregate scores into reports with reliability metrics
        ↓
[8] Reporter → generate output in multiple formats
```

**Concrete execution flow** in `EvalPipeline::run_evaluation` (`crates/ageneval-runner/src/pipeline.rs`):
1. Load tasks via `self.loader.load_tasks(source)`
2. For each task × trial: `adapter.adapt()` → `executor.execute()` → `scorer.score()`
3. Collect all `EvalScore` results

**Parallel execution** in `ParallelRunner::run_matrix` (`crates/ageneval-runner/src/parallel.rs`):
1. Create semaphore-bounded async tasks per matrix cell
2. Each cell iterates trials × tasks with adapt→execute→score
3. Budget checked via `CostTracker` before each trial
4. Results collected via `mpsc` channel

**CLI orchestration** in `run_matrix_benchmark` (`crates/ageneval-cli/src/main.rs`):
1. Parse TOML config into `MatrixSpec` + `MatrixConstraints`
2. Generate cells via `MatrixEngine::generate_with_constraints`
3. For each cell × task × trial: deterministic execution + scoring
4. Compute reliability stats (pass@k, pass^k, consistency) per cell
5. Generate JSON, Markdown, and axis analysis reports

---

## 6. Scoring Mechanism

### 6.1 Scorer Hierarchy

```
Scorer (trait)
├── ExactScorer — binary string match
├── FuzzyScorer — edit distance + substring similarity
├── RubricScorer — weighted multi-criterion
├── CompositeScorer — chains multiple scorers
└── Dimension-specific scorers (DefaultToolScorer, DefaultModelScorer, etc.)
```

### 6.2 Composite Score Calculation

The CLI implements a practical composite scoring formula (`score_result` in `crates/ageneval-cli/src/main.rs`):

- **quality_score** = weighted_average(task_accuracy × 0.45, token_efficiency × 0.25, consistency × 0.30)
- **cost_score** = weighted_average(cost_efficiency × 0.60, latency_efficiency × 0.40)
- **cost_efficiency** = `1.0 - (cost_usd / $0.15)` capped at [0, 1]
- **latency_efficiency** = `1.0 - (duration_secs / 5.0)` capped at [0, 1]
- **Labels**: quality ≥ 0.70 = Pass, ≥ 0.45 = Partial, else Fail

### 6.3 Reliability Statistics (`crates/ageneval-scorers/src/stats.rs`)

- **pass@k**: `1 - C(n-c, k) / C(n, k)` — probability at least 1 of k samples is correct
- **pass^k**: `(c/n)^k` — probability ALL k independent trials succeed (stricter)
- **consistency**: `1 - σ/μ` — coefficient of variation complement

These three metrics together capture reliability vs. best-case vs. worst-case agent behavior. The CLI computes them per matrix cell with k = min(3, n_trials).

---

## 7. Python Evaluation Scripts

### 7.1 `eval_scripts/context_density_eval.py` (1,300+ lines)

The most substantial Python script. Evaluates context optimization strategies for DevolaFlow's multi-agent hierarchy.

**Data model** (dataclasses):
- `TokenMetrics` — total_tokens, high/medium/low_density_tokens, redundant_tokens, with computed `effective_tokens` and `removable_tokens`
- `QualityScore` — 8 sub-scores: triage_accuracy, workflow_selection, stage_sequence, wave_decomposition, yaml_validity, context_isolation, gate_criteria, overall_coherence. Composite = mean of non-zero scores
- `DensityScores` — information_density_score, quality_preservation_rate, redundancy_ratio, effective_ratio
- `TrialResult` — single trial: token_metrics, quality_score, density_scores, raw_output, judge_reasoning
- `AggregateResult` — aggregated: mean/std for density and quality, go/no-go decision

**Token analysis**:
- Uses `tiktoken` (GPT-4 encoder) for token counting
- Heuristic density classification: high (code, tables, constraints), medium (useful prose), low (verbose/navigation), redundant (duplicated)
- Allocation ratios from audit: ~55-60% high, ~20-25% medium, ~10-12% low, ~5-8% redundant

**Scoring formulas**:
- `information_density_score = (quality_composite / token_count) × 1000` — quality per token
- `quality_preservation_rate = (optimized_quality / baseline_quality) × 100` — target ≥ 95%
- `redundancy_ratio = (removed_tokens / total_tokens) × 100`
- `effective_ratio = (tokens_saved × quality_preservation) / original_tokens × 100`

**Go/No-Go gates**:
- Primary (rounds 1–3): quality_preservation ≥ 95% AND density_improvement ≥ 15%
- Fallback (round > 3): quality_preservation ≥ 95% AND density_improvement ≥ 8%
- Decisions: "go", "no-go", or "inconclusive"

**LLM-as-judge pattern**: Uses Anthropic API (when ANTHROPIC_API_KEY present) to judge output quality with structured prompts. Falls back to heuristic scoring when unavailable.

### 7.2 Other Scripts

- `generate_diff_analysis.py` — Generates diff comparison reports between benchmark runs
- `generate_full_analysis.py` — Generates comprehensive analysis across all dimensions
- `generate_web_dashboard_data.py` / `generate_web_data.py` — Transform benchmark JSON results into format consumed by the web dashboard
- `test_context_density_eval.py` — Test suite for context_density_eval.py

---

## 8. Web Dashboard

The dashboard (`web/index.html`, ~627 lines) is a single-page application using ECharts 5 with dark/light theme support.

**Tabs and visualizations**:
1. **Baseline Benchmark** — KPI cards (cells, quality, pass rate, cost), radar chart per model, bar chart by model × thinking mode, bar chart by agent tool, heatmap (model vs thinking), results table with sorting
2. **DevolaFlow Growth** — Version trend line chart (quality + cost over versions), version scatter plot, results table for growth data
3. **Baseline vs DevolaFlow Latest** — KPI comparison with delta badges, grouped bar chart, side-by-side radar chart, per-task comparison table

**Data loading**: Fetches `data/baseline_benchmark.json` and `data/devolaflow_growth.json`. Uses fallback to generate synthetic data if fetch fails.

**ECharts patterns**: Radar charts for multi-dimensional comparison, bar charts for categorical comparison, line charts for version trends, heatmaps for matrix visualization, and sortable HTML tables for detailed results.

---

## 9. Matrix Evaluation System

### 9.1 Matrix TOML Format

Matrix configs define combinatorial evaluation runs in `benchmarks/*/matrix.toml`:

```toml
[matrix]
name = "Benchmark Name"
description = "..."

[[matrix.axes]]
name = "agent_tool"
[[matrix.axes.values]]
id = "cursor-agent"
label = "Cursor Agent CLI"

[[matrix.axes]]
name = "model"
[[matrix.axes.values]]
id = "opus4.6"
label = "Claude Opus 4.6"

[matrix.constraints]
max_cells = 500
[[matrix.constraints.exclusions]]
agent_tool = "claude-code"
workflow = "nexis_skills"

[matrix.execution]
max_parallel_cells = 4
n_trials = 3
timeout_per_cell_seconds = 600
```

### 9.2 Phase 1 Matrix

Axes: 2 agent_tools × 3 models × 2 thinking_modes × 3 workflows = 36 cells (minus 6 excluded = 30 cells). With 22 tasks and 3 trials = 1,980 total evaluations.

### 9.3 Context Density Matrix

Axes: 4 context_policies × 1 workflow × 3 task_types = 12 cells. With 7 trials = 84 evaluations. Includes scoring config referencing `eval_scripts/context_density_eval.py` and threshold definitions.

---

## 10. Design Patterns for NineS Absorption

### Pattern 1: Tagged-Enum Domain Modeling

EvoBench uses Rust's `#[serde(tag = "type")]` enums for `TaskInput`, `TaskExpected`, and `TaskOutput`, each with a `Custom(serde_json::Value)` variant as escape hatch. **NineS absorption**: Use Python discriminated unions (`Literal` + dataclasses or Pydantic discriminated unions) for the same extensible type-safe input/output modeling.

**Reference**: `crates/ageneval-core/src/types.rs` lines 172–202

### Pattern 2: Trait-Based Pipeline Composition

The 8-stage pipeline is defined as composable traits (TaskLoader, TaskAdapter, Executor, Scorer, etc.) that are injected via `Arc<dyn Trait>` into the pipeline struct. **NineS absorption**: Define Python ABCs (or Protocol classes) for each pipeline stage, compose via dependency injection.

**Reference**: `crates/ageneval-core/src/traits.rs` lines 19–139

### Pattern 3: Weighted Multi-Metric Scoring with Normalization

Each dimension has exactly 8 metrics with weights summing to 1.0, directionality (higher/lower is better), and value types. Scores are normalized to [0, 1] before weighted aggregation. **NineS absorption**: Define metric registries with weight/direction/type metadata; compute weighted scores with normalized values.

**Reference**: `crates/ageneval-dimensions/src/tool.rs` lines 13–72 (metric definitions)

### Pattern 4: Combinatorial Matrix with Exclusion Rules

Matrix evaluation generates the cartesian product of axes, then applies exclusion rules and cell caps. Multiple strategies (FullCross, LatinSquare, Pairwise, Random) handle scale. **NineS absorption**: Implement matrix generation with `itertools.product` + post-filtering exclusion rules + strategy pattern for sampling.

**Reference**: `crates/ageneval-matrix/src/engine.rs` lines 8–225

### Pattern 5: Composite Scorer Chaining

`CompositeScorer` wraps multiple scorers with weights, runs all, and aggregates. Metric names are prefixed (`composite::exact_match`) to avoid collision. **NineS absorption**: Build a ScorerPipeline that chains scorers with namespace-prefixed metrics.

**Reference**: `crates/ageneval-scorers/src/composite.rs` lines 1–117

### Pattern 6: pass@k + pass^k Dual Reliability Metrics

Using both `pass@k` (optimistic: at least 1 success) and `pass^k` (pessimistic: all succeed) gives a complete reliability picture. Combined with `consistency` (1 - CV), these three metrics capture different failure modes. **NineS absorption**: Implement all three reliability metrics and report them together.

**Reference**: `crates/ageneval-scorers/src/stats.rs` lines 1–68

### Pattern 7: Cost Budget Guard with Real-Time Tracking

`CostTracker` in the parallel runner checks budget before each trial, enabling graceful early termination when spending exceeds limits. The `BudgetExceeded` error variant provides exact spent/budget figures. **NineS absorption**: Implement a budget guard that checks cumulative cost before each agent invocation.

**Reference**: `crates/ageneval-runner/src/parallel.rs` lines 11–35

### Pattern 8: Plugin System with Dependency DAG

The plugin registry uses topological sort for initialization order, supports dependency declarations, detects cycles, and has panic-safe init. Permission model controls network/filesystem/docker/LLM access. **NineS absorption**: Build a plugin registry with declared dependencies, capability-based permissions, and automatic ordering.

**Reference**: `crates/ageneval-core/src/plugin.rs` lines 92–245

### Pattern 9: Token Density Classification with Go/No-Go Gates

The Python eval script classifies tokens into high/medium/low/redundant density tiers, then applies quality-preservation gates (≥ 95%) with fallback thresholds. Decisions are "go"/"no-go"/"inconclusive". **NineS absorption**: Implement tiered quality gates with configurable thresholds and fallback logic.

**Reference**: `eval_scripts/context_density_eval.py` lines 267–364

### Pattern 10: Optimization Lifecycle State Machine

The optimization system defines a clear lifecycle: Proposed → Approved → Applied → Validated/Rejected/RolledBack. Each recommendation has target, rationale, expected_improvement, confidence, and risk_level. Drift assessment measures semantic + behavioral drift with regression detection. **NineS absorption**: Implement an optimization recommendation pipeline with a state machine for tracking application and validation.

**Reference**: `crates/ageneval-core/src/optimization.rs` lines 1–76

### Pattern 11: Deterministic Simulation for Testing

The CLI uses `hash_seed()` with per-cell coordinates to generate deterministic pseudo-random quality/cost values, enabling reproducible benchmark testing without real agent execution. Quality factors are parameterized per model/thinking/workflow. **NineS absorption**: Build deterministic mock executors with tunable quality/cost models for testing the evaluation pipeline.

**Reference**: `crates/ageneval-cli/src/main.rs` lines 286–414

### Pattern 12: Environment Capture for Reproducibility

`EnvironmentRecord::capture()` records OS, arch, Rust version, ageneval version, model, provider, random seed, config hash, and timestamp. This metadata accompanies every evaluation result. **NineS absorption**: Capture a similar environment snapshot (Python version, package versions, model info) with every evaluation run.

**Reference**: `crates/ageneval-core/src/types.rs` lines 276–302

### Pattern 13: Cross-Version Penetrating Analysis

The comparison system builds a "penetrating matrix" that tracks the same configuration combination across versions, computing quality/pass_rate/cost deltas. This enables detecting regressions introduced by workflow changes. **NineS absorption**: Implement cross-run comparison with stable cell identifiers for regression detection.

**Reference**: `crates/ageneval-cli/src/main.rs` lines 1217–1249

### Pattern 14: Multi-Format Report Generation with Templates

Reports are generated in parallel formats (JSON, Markdown, HTML) using the Reporter trait. Markdown uses Tera templates for customizable output. Chart data is separated from visualization. **NineS absorption**: Implement pluggable reporters with Jinja2 templates for Markdown and JSON serialization for data.

**Reference**: `crates/ageneval-reporters/src/markdown.rs` lines 1–108

---

## 11. Crate Dependency Graph

```
ageneval-core (foundation - no internal deps)
    ├── ageneval-runner       (core)
    ├── ageneval-dimensions   (core)
    ├── ageneval-matrix       (core)
    ├── ageneval-scorers      (core)
    ├── ageneval-reporters    (core)
    ├── ageneval-optimizer    (core)
    ├── ageneval-cli          (core, matrix, runner, scorers, reporters)
    └── ageneval-web          (core, runner)
```

The CLI crate is the integration point, pulling together matrix generation, runner execution, scoring, and reporting. All other crates depend only on `ageneval-core`.

---

## 12. Key Takeaways for NineS

1. **Core-first architecture**: Define all domain types and trait interfaces in a foundation module before implementing any specific functionality. This enables clean dependency flow.

2. **Tagged enums for extensibility**: `TaskInput`, `TaskExpected`, `TaskOutput` all use tagged discrimination with a `Custom` escape hatch. This balances type safety with open extensibility.

3. **4-axis evaluation is orthogonal**: Tool, Model, Workflow, and TaskType dimensions are independent and can be evaluated separately or composed. NineS should maintain this orthogonality.

4. **Reliability needs multiple metrics**: pass@k alone is insufficient — pass^k (all-correct) and consistency (variance) capture different failure modes critical for production agent evaluation.

5. **Budget guards are essential**: Real-time cost tracking with early termination prevents runaway evaluation costs, especially in matrix evaluations where cell count × trials × tasks multiplies rapidly.

6. **Deterministic simulation enables testing**: A hash-seeded mock executor with parameterized quality factors allows testing the entire pipeline without real agent calls or API costs.

7. **Matrix exclusions are pragmatic**: Not all axis combinations are valid (e.g., claude-code cannot use Cursor-specific features). Exclusion rules handle this cleanly.

8. **Quality gates with fallback thresholds**: The go/no-go pattern with primary/fallback thresholds prevents premature optimization abandonment while maintaining quality floors.

---

*Document generated from EvoBench commit tree at `/home/agent/workspace/EvoBench` — AgenEval v0.6.0*
*Last modified: 2026-04-11*
