# NineS Growth Evaluation Plan

> **Date**: 2026-04-12 | **Baseline Version**: v1 (overall 0.8787) | **Status**: Active

---

## 1. Methodology: Version-Over-Version Comparison

### 1.1 Growth Rate Formula

For each self-evaluation dimension D_i, the growth rate between version A and version B is:

```
growth_rate(D_i) = (score_B(D_i) - score_A(D_i)) / score_A(D_i)
```

For the composite score:

```
composite_growth = (composite_B - composite_A) / composite_A
```

Where:
- `score_A(D_i)` is the baseline measurement of dimension i at version A
- `score_B(D_i)` is the measurement at version B
- Growth rate is expressed as a fraction (0.05 = 5% improvement)

**Annualized growth rate** (for long-term tracking):

```
annualized_growth(D_i) = ((score_B / score_A) ^ (365 / days_elapsed)) - 1
```

### 1.2 Comparison Protocol

Each version comparison follows this protocol:

1. **Freeze environment**: Record Python version, OS, hardware, NineS version, dependency versions
2. **Run self-eval 3x**: Execute full 19-dimension self-evaluation three independent times
3. **Compute stability**: Verify CV <= 0.05 per dimension across the 3 runs
4. **Record median**: Use median of 3 runs as the official score for each dimension
5. **Compare against baseline**: Load the previous version's baseline from `data/baselines/{version}/`
6. **Compute deltas**: Per-dimension and composite growth rates
7. **Generate report**: Markdown + JSON output with full comparison table

### 1.3 Statistical Significance

To determine whether a score change is statistically significant (not noise):

- **Minimum detectable change**: |delta| > 2 * max(CV_A, CV_B) * score_A
- **Confidence interval**: Use Wilson score interval for proportions (dimensions measured as fractions)
- **Effect size**: Cohen's d = (mean_B - mean_A) / pooled_std; significant if d >= 0.5 (medium effect)

Changes below the minimum detectable change threshold are classified as "unchanged" regardless of direction.

---

## 2. Regression Detection

### 2.1 Alert Thresholds

| Severity | Condition | Action |
|----------|-----------|--------|
| **Critical** | Any dimension drops > 10% from baseline | Block release; mandatory investigation |
| **Warning** | Any dimension drops > 5% from baseline | Flag in PR review; investigation recommended |
| **Info** | Any dimension drops > 2% from baseline | Log for tracking; no action required |
| **Pass** | All dimensions within 2% or improved | No action needed |

For the composite score specifically:

| Severity | Condition | Action |
|----------|-----------|--------|
| **Critical** | Composite drops > 5% | Block release; escalate to project lead |
| **Warning** | Composite drops > 2% | Require sign-off before merge |
| **Info** | Composite drops > 1% | Note in release changelog |

### 2.2 Automated Regression Detection Algorithm

```python
def detect_regressions(current: SelfEvalReport, baseline: SelfEvalReport) -> list[Regression]:
    regressions = []
    for dim in current.dimensions:
        baseline_score = baseline.get_score(dim.name)
        if baseline_score == 0:
            continue  # Skip uninitialized dimensions
        delta_pct = (dim.value - baseline_score) / baseline_score * 100
        if delta_pct < -10:
            regressions.append(Regression(dim.name, "critical", delta_pct))
        elif delta_pct < -5:
            regressions.append(Regression(dim.name, "warning", delta_pct))
        elif delta_pct < -2:
            regressions.append(Regression(dim.name, "info", delta_pct))
    return regressions
```

### 2.3 Regression Root Cause Checklist

When a regression is detected:

1. **Environment change?** — Check Python version, dependency versions, OS updates
2. **Code change?** — Review git diff since last baseline for the affected module
3. **Data change?** — Verify golden test set, reference codebases, canary entities unchanged
4. **Flaky measurement?** — Re-run self-eval 5x; check CV for the regressed dimension
5. **Intentional trade-off?** — Check if another dimension improved proportionally (resource reallocation)
6. **External factor?** — API downtime, rate limit changes, network issues (for V2 dimensions)

---

## 3. Benchmark Suite

### 3.1 Suite Structure

The repeatable benchmark suite measures all 19 self-evaluation dimensions in a single automated run:

```
benchmark/
├── config.toml                  # Benchmark configuration
├── golden_test_set/             # D01, D03, D04, D05: Evaluation tasks with expected scores
│   ├── trivial/                 # 10 trivial tasks
│   ├── moderate/                # 10 moderate tasks
│   └── complex/                 # 10 complex tasks
├── reference_codebases/         # D11, D12, D13, D15: Annotated projects
│   ├── flask_mvc/               # MVC architecture
│   ├── hexagonal/               # Hexagonal architecture
│   └── flat_scripts/            # Simple flat structure
├── review_test_set/             # D13: Code files with annotated issues
│   └── *.py                     # 5–10 files, 30+ annotated issues
├── search_benchmark/            # D14: Search queries with ground-truth
│   └── queries.json             # 15+ queries with relevant KnowledgeUnit IDs
├── canary_entities.toml         # D07, D08: Tracked repos and queries
└── run_benchmark.py             # Orchestrator script
```

### 3.2 Dimension-to-Data Mapping

| Dimension | Data Source | Measurement |
|-----------|------------|-------------|
| D01: Scoring Accuracy | `golden_test_set/` | accuracy = correct_scores / total_tasks |
| D02: Evaluation Coverage | TaskDefinition schema | covered_types / total_types |
| D03: Reliability (Pass^k) | `golden_test_set/` × 3 runs | consistent_tasks / total_tasks |
| D04: Report Quality | Latest eval report | valid_sections / required_sections |
| D05: Scorer Agreement | Multi-scorer eval on golden set | Mean pairwise Cohen's κ |
| D06: Source Coverage | Config source registry | active_sources / configured_sources |
| D07: Tracking Freshness | `canary_entities.toml` | Median detection lag (minutes) |
| D08: Change Detection Recall | Canary ground-truth log | detected_changes / actual_changes |
| D09: Data Completeness | DataStore entity scan | populated_fields / total_fields |
| D10: Collection Throughput | Timed collection run | entities / minute |
| D11: Decomposition Coverage | `reference_codebases/` | decomposed_elements / total_elements |
| D12: Abstraction Quality | Annotated reference codebases | Macro-averaged F1 |
| D13: Code Review Accuracy | `review_test_set/` | F1 of findings vs annotations |
| D14: Index Recall | `search_benchmark/queries.json` | Mean Recall@10 |
| D15: Structure Recognition | Annotated reference codebases | correct_patterns / total_patterns |
| D16: Pipeline Latency | Golden test set timing | p50 and p95 (seconds) |
| D17: Sandbox Isolation | PollutionReport from eval runs | clean_runs / total_runs |
| D18: Convergence Rate | Iteration history | 1 - (iters_to_converge / max_iters) |
| D19: Cross-Vertex Synergy | ScoreHistory (>=5 points) | Mean lagged cross-correlation |

### 3.3 Benchmark Execution

```bash
# Full benchmark run (approximately 65 minutes)
nines self-eval --benchmark --output json -o reports/benchmark_$(date +%Y%m%d).json

# Quick smoke test (V1 dimensions only, ~15 minutes)
nines self-eval --benchmark --dimensions D01,D02,D03,D04,D05

# Compare against a specific baseline
nines self-eval --benchmark --baseline v1 --compare
```

### 3.4 Reproducibility Requirements

- All random operations use a configurable seed (default: 42)
- Sandbox environments are created fresh for each benchmark run
- External API calls are recorded and replayed in offline mode
- Hardware specs are recorded in benchmark metadata
- Python dependency versions are pinned via `uv.lock`

---

## 4. CI Integration

### 4.1 GitHub Actions Workflow

{% raw %}
```yaml
name: NineS Self-Evaluation

on:
  pull_request:
    branches: [main, yc_dev]
  release:
    types: [published]
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6 AM UTC

permissions:
  contents: read
  pull-requests: write
  checks: write

jobs:
  self-eval:
    name: Self-Evaluation Benchmark
    runs-on: ubuntu-latest
    timeout-minutes: 90
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync

      - name: Run unit tests
        run: uv run pytest --tb=short -q

      - name: Run self-evaluation benchmark
        run: |
          uv run nines self-eval --benchmark \
            --output json \
            -o reports/benchmark_${{ github.sha }}.json

      - name: Check for regressions
        id: regression_check
        run: |
          uv run python -c "
          import json, sys
          with open('reports/benchmark_${{ github.sha }}.json') as f:
              current = json.load(f)
          with open('data/baselines/v1/baseline.json') as f:
              baseline = json.load(f)

          regressions = []
          for dim_name, dim_data in current.get('dimensions', {}).items():
              base_val = baseline.get('dimensions', {}).get(dim_name, {}).get('value', 0)
              if base_val > 0:
                  delta = (dim_data['value'] - base_val) / base_val * 100
                  if delta < -5:
                      regressions.append(f'{dim_name}: {delta:+.1f}%')

          if regressions:
              print('::warning::Regressions detected: ' + '; '.join(regressions))
              with open('regression_report.txt', 'w') as f:
                  f.write('\n'.join(regressions))
              sys.exit(1) if any('critical' in r for r in regressions) else None
          else:
              print('No regressions detected.')
          "

      - name: Post PR comment with results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync(
              `reports/benchmark_${context.sha}.json`, 'utf8'
            ));
            const composite = report.overall || report.aggregates?.composite || 'N/A';
            let body = `## NineS Self-Evaluation Results\n\n`;
            body += `**Composite Score**: ${composite}\n\n`;
            body += `| Category | Score |\n|----------|-------|\n`;
            for (const [cat, score] of Object.entries(report.aggregates || {})) {
              body += `| ${cat} | ${score} |\n`;
            }
            const regFile = 'regression_report.txt';
            if (fs.existsSync(regFile)) {
              body += `\n### ⚠ Regressions\n\`\`\`\n${fs.readFileSync(regFile, 'utf8')}\n\`\`\`\n`;
            }
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });

      - name: Upload benchmark artifact
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-${{ github.sha }}
          path: reports/benchmark_${{ github.sha }}.json
          retention-days: 90

  update-baseline:
    name: Update Baseline (Release Only)
    needs: self-eval
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - name: Download benchmark artifact
        uses: actions/download-artifact@v4
        with:
          name: benchmark-${{ github.sha }}
          path: reports/

      - name: Update baseline
        run: |
          VERSION="${{ github.event.release.tag_name }}"
          mkdir -p "data/baselines/${VERSION}"
          cp "reports/benchmark_${{ github.sha }}.json" \
             "data/baselines/${VERSION}/baseline.json"

      - name: Commit updated baseline
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/baselines/
          git commit -m "chore: update baseline for ${{ github.event.release.tag_name }}"
          git push
```
{% endraw %}

### 4.2 Workflow Triggers

| Trigger | Scope | Action on Regression |
|---------|-------|---------------------|
| Pull Request | Full 19-dimension benchmark | Post comment; block merge on critical regression |
| Release | Full benchmark + baseline update | Update stored baseline in `data/baselines/` |
| Weekly schedule | Full benchmark | Create issue if regression detected since last release |

### 4.3 PR Merge Gate

The self-evaluation check is configured as a **required status check** on protected branches:

- **Pass**: No dimension regresses > 5%
- **Warning**: Dimension regresses 2–5% (merge allowed with reviewer approval)
- **Fail**: Any dimension regresses > 10% OR composite drops > 5% (merge blocked)

---

## 5. Dashboard

### 5.1 Overview

A lightweight HTML dashboard (inspired by EvoBench's web interface) for visualizing self-evaluation trends across versions. Designed to be statically generated from benchmark JSON files and served without a backend.

### 5.2 Dashboard Structure

```
dashboard/
├── index.html              # Main entry point
├── assets/
│   ├── style.css           # Styling
│   └── dashboard.js        # Chart rendering and data loading
├── data/
│   └── *.json              # Benchmark result files (copied from reports/)
└── generate.py             # Static site generator script
```

### 5.3 Dashboard Panels

| Panel | Content | Visualization |
|-------|---------|---------------|
| **Composite Trend** | Composite score over time | Line chart with version labels on x-axis |
| **Category Breakdown** | V1, V2, V3, System scores per version | Stacked area chart or grouped bar chart |
| **Dimension Heatmap** | All 19 dimensions × all versions | Color-coded heatmap (red=regression, green=improvement) |
| **Regression Alerts** | Dimensions that regressed since last version | Table with severity badges |
| **Growth Rates** | Per-dimension growth rate | Bar chart sorted by growth rate |
| **Convergence Tracker** | Iterations to convergence over time | Line chart for D18 |
| **Synergy Matrix** | Cross-vertex correlation matrix | 3×3 heatmap for V1↔V2↔V3 synergy |

### 5.4 Generation

```bash
# Generate dashboard from all benchmark files
python dashboard/generate.py --input reports/ --output dashboard/

# Serve locally for preview
python -m http.server 8080 --directory dashboard/
```

The generator script:

1. Scans `reports/` for all `benchmark_*.json` files
2. Extracts dimension scores, timestamps, and version labels
3. Computes growth rates and regression flags
4. Renders `index.html` using a Jinja2 template with embedded Chart.js data
5. Copies benchmark JSON files to `dashboard/data/` for client-side access

### 5.5 Chart.js Configuration

The dashboard uses Chart.js (CDN-loaded, no build step) for all visualizations:

- **Line charts**: Composite trend and convergence tracker (time series)
- **Bar charts**: Growth rates per dimension (sorted horizontal bars)
- **Heatmap**: Custom canvas rendering for dimension × version matrix
- **Tables**: Regression alerts with color-coded severity

### 5.6 Data Format

Each benchmark JSON file is loaded and normalized to this schema:

```json
{
  "version": "v1.0",
  "timestamp": "2026-04-12T00:00:00Z",
  "composite": 0.8787,
  "categories": {
    "V1_evaluation": 0.89,
    "V2_search": 0.87,
    "V3_analysis": 0.72,
    "system_wide": 0.95
  },
  "dimensions": {
    "D01_scoring_accuracy": 0.92,
    "D02_evaluation_coverage": 1.0,
    "...": "..."
  }
}
```

### 5.7 Future Enhancements

- **Live mode**: WebSocket connection to a running NineS instance for real-time updates
- **Comparison view**: Side-by-side comparison of two selected versions
- **Export**: PDF/PNG export of charts for inclusion in documentation
- **Annotations**: User-added notes on specific data points (e.g., "upgraded to v2 scorers")

---

## 6. Operational Procedures

### 6.1 Baseline Update Process

1. Tag a release (e.g., `v1.1.0`)
2. CI runs full benchmark and stores result as new baseline
3. Previous baseline is preserved in `data/baselines/{previous_version}/`
4. All subsequent PR comparisons use the new baseline

### 6.2 Dimension Addition Process

When adding a new self-eval dimension:

1. Define the dimension in `docs/design/self_eval_spec.md`
2. Implement the evaluator in `src/nines/iteration/self_eval.py`
3. Add benchmark data (golden set, reference codebases, etc.) as needed
4. Run initial measurement to establish the dimension's baseline value
5. Update `data/baselines/{current}/baseline.json` with the new dimension
6. Update CI regression thresholds if needed
7. Add the dimension to the dashboard

### 6.3 Alert Escalation

| Alert | First Response | Escalation |
|-------|---------------|------------|
| Info regression (2–5%) | Log in release notes | None |
| Warning regression (5–10%) | Investigate in next sprint | Project lead review if not addressed in 1 sprint |
| Critical regression (>10%) | Immediate investigation | Block release; hotfix priority |
| Composite drop (>5%) | Block release; emergency investigation | Rollback candidate |

---

*Last modified: 2026-04-12T00:00:00Z*
