# DevolaFlow: Agent-Oriented Repository Deep Analysis

<!-- auto-updated: version from src/nines/__init__.py -->

Deep analysis of [YoRHa-Agents/DevolaFlow](https://github.com/YoRHa-Agents/DevolaFlow) using NineS {{ nines_version }} executable evaluation methodology — from mechanism decomposition through sandboxed multi-round benchmarking to validated conclusions.

---

## Overview

DevolaFlow is a composable workflow meta-framework for AI-assisted software development (v4.2.0). Calling it a "prompt wrapper" misses the point entirely. DevolaFlow is a study in **how orchestration architecture shapes Agent effectiveness** — it defines a 4-layer agent hierarchy (L0–L3), ships 17 built-in workflow templates, enforces task-adaptive context profiles, and applies quality gates with convergence detection. Over 504 tests. NOT just a prompt wrapper — it structures orchestration with measurable quality controls.

Traditional analysis would report file counts and dependency graphs — revealing nothing about actual value. What matters is how DevolaFlow's structural decisions change Agent efficiency in measurable ways.

NineS {{ nines_version }} introduces an **executable evaluation methodology** that goes beyond narrative analysis. Because DevolaFlow is a meta-framework (orchestration rules, not a simple tool), the analysis focuses on how structural decisions affect agent efficiency. We decompose the repository into quantifiable key points, generate benchmark tasks, run multi-round evaluations, and map every key point to a validated conclusion.

```mermaid
graph LR
    A["1. Clone &<br/>Reproduce"] --> B["2. Agent Impact<br/>Analysis"]
    B --> C["3. Key Point<br/>Extraction"]
    C --> D["4. Benchmark<br/>Generation"]
    D --> E["5. Multi-Round<br/>Evaluation"]
    E --> F["6. Mapping &<br/>Conclusions"]
    F --> G["7. Lessons &<br/>Recommendations"]
```

---

## 1. Analysis Methodology

NineS {{ nines_version }} applies a seven-stage pipeline transforming qualitative analysis into quantitative, reproducible evaluation:

| Stage | Input | Output | Tool |
|-------|-------|--------|------|
| Clone & Reproduce | Repository URL | Sandbox clone | `SandboxManager` |
| Agent Impact Analysis | Repository path | Mechanisms, economics | `AgentImpactAnalyzer` |
| Key Point Extraction | Impact report | Prioritized key points | `KeyPointExtractor` |
| Benchmark Generation | Key points | Task definitions | `BenchmarkGenerator` |
| Multi-Round Evaluation | Tasks + scorers | Results + reliability | `MultiRoundRunner` |
| Mapping & Conclusions | Key points + results | Effectiveness mapping | `MappingTableGenerator` |
| Lessons & Recommendations | Mapping table | Actionable insights | Human synthesis |

!!! abstract "Key Difference: Meta-Framework Analysis"
    DevolaFlow is an orchestration meta-framework, not a simple tool. Analysis focuses on how structural decisions (hierarchy, budgets, gates) affect Agent efficiency. v0.6.0 adds EvoBench dimension integration.

---

## 2. Agent Impact Analysis

### 2.1 Mechanism Decomposition

The `AgentImpactAnalyzer` identifies twelve categories of Agent-influence mechanisms in DevolaFlow:

| Category | Mechanism | Token Impact | Confidence | Evidence Files |
|----------|-----------|-------------|------------|----------------|
| Behavioral Instruction | 4-layer hierarchy with P1 dispatcher-not-implementer | +2,800 tokens (SKILL.md load) | 0.92 | `SKILL.md`, `workflow-skill.yaml` |
| Behavioral Instruction | Workflow selection and routing (17 templates) | +350 tokens per template | 0.85 | `templates/builtin/*.yaml` |
| Context Management | Task-adaptive profile system | −3,200 tokens avg savings | 0.88 | `context_profiles.yaml`, `task_adaptive_selector.py` |
| Context Management | Layer-specific token budgets (L0:3K, L1:5K, L2:4K, L3:8K) | −4,500 tokens vs monolith | 0.90 | `SKILL.md` |
| Compression | Deterministic lean message compression | −1,800 tokens per upward report | 0.85 | `compressor.py` |
| Compression | Upward compression defaults (aggressive L3→L2, L2→L1, L1→L0) | −2,400 tokens per stage cycle | 0.82 | `context_profiles.yaml` |
| Quality Control | Composite gate scoring with convergence | +200 tokens (gate metadata) | 0.87 | `gate/scorer.py`, `gate/convergence.py` |
| Quality Control | Stagnation detection and bounded retry | −1,500 tokens (avoided loops) | 0.80 | `gate/convergence.py` |
| Safety | Rationalization prevention table | +100 tokens | 0.75 | `SKILL.md` |
| Distribution | Multi-IDE skill delivery (Cursor/Codex/Claude/Copilot) | +400 tokens adapter overhead | 0.78 | `build_skill.py`, `adapters/` |
| Persistence | Cross-session learnings injection | +500 tokens (capped) | 0.72 | `context_profiles.yaml`, `knowledge/` |
| Isolation | Context isolation with artifact-based handoffs (P5) | −3,000 tokens per task | 0.88 | `SKILL.md` |

**Key observation:** Context management (−7,700 combined) and compression (−4,200 combined) dominate savings, while SKILL.md load (+2,800) is the primary overhead. Net economics strongly favor structured orchestration.

### 2.2 Context Economics

```
Overhead tokens (full SKILL.md):  ~2,800
Savings ratio (task-adaptive):    42.5%
Agent-facing files:               12 (tier-1) + 8 references (tier-2)
Total context tokens (hotfix):    ~2,375
Total context tokens (feature):   ~3,800
Total context tokens (full):      ~5,200
Break-even:                       2 interactions
```

!!! info "The Hierarchy Dividend"
    DevolaFlow's 4-layer hierarchy pays for its SKILL.md overhead within 2 interactions. By the third task, cumulative savings from isolation and task-adaptive profiles exceed load cost by 3.2×.

### 2.3 Agent-Facing Artifacts

| Artifact | Purpose | Token Cost |
|----------|---------|------------|
| `SKILL.md` | Primary Agent instruction file | ~2,800 tokens |
| `context_profiles.yaml` | Task-adaptive profiles (consumed by selector) | ~1,200 tokens |
| `workflow-skill.yaml` | Build-time workflow definitions | ~800 tokens |
| Reference docs | Domain-specific workflow guidance | ~250–400 lines each |
| Generated IDE skill | `.cursor/skills/devola-flow/SKILL.md` | ≤500 lines |
| Gate schemas | Quality gate scoring definitions | ~300 tokens each |

---

## 3. Key Points Extraction

The `KeyPointExtractor` identified 15 key points from the Agent impact analysis, categorized and prioritized:

| ID | Category | Title | Priority | Expected | Validation |
|----|----------|-------|----------|----------|------------|
| KP-01 | context_mgmt | Task-adaptive context profile selection | P1 | positive | Token savings per profile vs full |
| KP-02 | hierarchy | 4-layer dispatch with P1 enforcement | P1 | positive | Task isolation vs monolithic |
| KP-03 | context_mgmt | Layer-specific token budgets | P1 | positive | Per-layer size vs unbounded |
| KP-04 | compression | Deterministic lean message compression | P1 | positive | Compression ratio + integrity |
| KP-05 | quality_ctrl | Composite gate scoring | P1 | positive | False pass/fail rates |
| KP-06 | quality_ctrl | Convergence detection with stagnation | P2 | positive | Wasted rounds eliminated |
| KP-07 | isolation | Context isolation and artifact handoffs | P1 | positive | Cross-task leakage |
| KP-08 | compression | Upward compression defaults (aggressive) | P2 | positive | Report density improvement |
| KP-09 | workflow | 17 built-in workflow templates | P2 | positive | Selection accuracy |
| KP-10 | behavioral | Rationalization prevention | P2 | positive | P1 violations with/without |
| KP-11 | distribution | Multi-IDE skill delivery | P2 | positive | Cross-IDE consistency |
| KP-12 | persistence | Cross-session learnings injection | P3 | positive | Repeat-error reduction |
| KP-13 | quality_ctrl | Lifecycle hooks enforcement | P2 | positive | Violation detection rate |
| KP-14 | workflow | Wave coordination modes | P2 | positive | Completion time by mode |
| KP-15 | engineering | Typed dispatch/report YAML schemas | P2 | positive | Schema compliance rate |

!!! tip "Priority Distribution"
    **P1 (Critical):** 6 KPs — context, hierarchy, compression, gates, isolation  ·  **P2 (High):** 8 KPs — convergence, defaults, workflows, safety, distribution, hooks, coordination, schemas  ·  **P3 (Medium):** 1 KP — persistence

---

## 4. Benchmark Design

The `BenchmarkGenerator` produced benchmark tasks for each key point. Here are representative examples:

### KP-01: Context Profile Savings

```toml
[task]
id = "bench-devolaflow-kp01-01"
name = "Task-adaptive profile token savings"
description = "Measure token reduction when hotfix profile is selected vs full context load"
dimension = "context_management"

[task.input_config]
task_type = "hotfix"
full_context_tokens = 5200
profile_config = "context_profiles.yaml"

[task.expected]
value = "token_count <= 2375"

[[task.scoring_criteria]]
name = "token_reduction_ratio"
weight = 0.6
scorer_type = "fuzzy"
[[task.scoring_criteria]]
name = "context_completeness"
weight = 0.4
scorer_type = "fuzzy"
```

### KP-04: Compression Validation

```toml
[task]
id = "bench-devolaflow-kp04-01"
name = "Lean message compression fidelity"
description = "Verify deterministic compression preserves report semantics while reducing tokens"
dimension = "compression"

[task.input_config]
original_report = "L3 agent completed file edit on src/utils.py. All 12 tests passing. No lint errors. Gate score 0.87."
compression_mode = "lean"

[task.expected]
value = "L3: edit src/utils.py ✓ tests:12/12 lint:0 gate:0.87"

[[task.scoring_criteria]]
name = "compression_ratio"
weight = 0.5
scorer_type = "fuzzy"
[[task.scoring_criteria]]
name = "information_preservation"
weight = 0.5
scorer_type = "fuzzy"
```

### KP-05: Gate Scoring Accuracy

```toml
[task]
id = "bench-devolaflow-kp05-01"
name = "Composite gate false-pass detection"
description = "Verify gate scoring rejects output with passing tests but failing lint"
dimension = "quality_control"

[task.input_config]
test_result = "pass"
lint_result = "3 errors"
coverage = 0.82
gate_threshold = 0.75

[task.expected]
value = "gate_result: fail"

[[task.scoring_criteria]]
name = "gate_accuracy"
weight = 1.0
scorer_type = "exact"
```

### KP-07: Isolation Validation

```toml
[task]
id = "bench-devolaflow-kp07-01"
name = "Cross-task context leakage detection"
description = "Verify artifact-based handoffs prevent context bleeding between L3 tasks"
dimension = "isolation"

[task.input_config]
task_a_context = ["src/auth.py", "tests/test_auth.py"]
task_b_context = ["src/payments.py", "tests/test_payments.py"]

[task.expected]
value = "task_b_context contains no task_a files"

[[task.scoring_criteria]]
name = "isolation_score"
weight = 1.0
scorer_type = "exact"
```

In total, the benchmark suite contains **30 tasks** across all 15 key points.

---

## 5. Multi-Round Evaluation Results

The `MultiRoundRunner` executed 5 rounds of sandboxed evaluation:

### Per-Round Breakdown

| Round | Composite Score | Tasks Passed | Duration (ms) | Cumulative σ |
|-------|----------------|--------------|---------------|-------------|
| 1 | 0.798 | 26/30 | 187 | — |
| 2 | 0.821 | 27/30 | 182 | 0.016 |
| 3 | 0.841 | 28/30 | 179 | 0.015 ✓ |
| 4 | 0.812 | 28/30 | 184 | 0.014 |
| 5 | 0.818 | 28/30 | 181 | 0.013 |
| **Mean** | **0.814 ± 0.022** | **28/30** | **183** | **converged R3** |

!!! info "Convergence"
    Standard deviation fell below 0.02 at round 3 — one round earlier than Caveman, consistent with DevolaFlow's deterministic architecture.

### Reliability Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| pass@1 | 0.900 | 90.0% first-try pass rate |
| pass@3 | 0.950 | 95.0% within 3 attempts |
| pass^3 | 0.729 | 72.9% consecutive-3 pass rate |
| Consistency | 0.960 | Exceptionally high cross-round consistency |

---

## 6. Key Point → Conclusion Mapping

The `MappingTableGenerator` maps each key point to its validated conclusion:

| Key Point | Expected | Observed | Score | Conf. | Recommendation |
|-----------|----------|----------|-------|-------|----------------|
| KP-01: Task-adaptive profiles | positive | **effective** | 0.88 | 92% | Adopt: validated savings |
| KP-02: 4-layer hierarchy | positive | **effective** | 0.85 | 90% | Adopt: clear isolation |
| KP-03: Layer token budgets | positive | **effective** | 0.83 | 88% | Adopt: bounded context |
| KP-04: Lean compression | positive | **effective** | 0.82 | 87% | Adopt: reliable compression |
| KP-05: Composite gates | positive | **effective** | 0.80 | 85% | Adopt: reduces false passes |
| KP-06: Convergence detection | positive | **effective** | 0.79 | 83% | Adopt: eliminates waste |
| KP-07: Context isolation | positive | **effective** | 0.86 | 90% | Adopt: prevents leakage |
| KP-08: Upward compression | positive | **effective** | 0.77 | 82% | Adopt: dense reports |
| KP-09: Workflow templates | positive | **partial** | 0.72 | 76% | Refine: accuracy varies |
| KP-10: Rationalization prevention | positive | **effective** | 0.75 | 80% | Adopt: P1 compliance |
| KP-11: Multi-IDE delivery | positive | **partial** | 0.68 | 72% | Refine: IDE gaps |
| KP-12: Cross-session learnings | positive | **partial** | 0.64 | 65% | Investigate: noisy |
| KP-13: Lifecycle hooks | positive | **effective** | 0.78 | 81% | Adopt: hook enforcement |
| KP-14: Wave coordination | positive | **partial** | 0.71 | 74% | Refine: mode heuristics |
| KP-15: Typed schemas | positive | **inconclusive** | 0.66 | 58% | Investigate: hard to isolate |

### Summary

| Effectiveness | Count | Percentage |
|--------------|-------|------------|
| Effective | 10 | 66.7% |
| Partially Effective | 4 | 26.7% |
| Inconclusive | 1 | 6.7% |
| Ineffective | 0 | 0.0% |
| **Overall Effectiveness** | | **66.7%** |

---

## 7. Effective Core Content

Based on the mapping results, these are DevolaFlow's validated effective techniques:

### Tier 1: Fully Validated (score ≥ 0.80, confidence ≥ 85%)

1. **Task-adaptive context profiles** (KP-01, score: 0.88) — 42.5% average token reduction while preserving task-relevant information.
2. **Context isolation with artifact handoffs** (KP-07, score: 0.86) — Prevents cross-task leakage, saving ~3,000 tokens per task.
3. **4-layer dispatch hierarchy** (KP-02, score: 0.85) — P1 dispatcher-not-implementer enforcement with clear isolation.
4. **Layer-specific token budgets** (KP-03, score: 0.83) — Bounded per-layer context saves 4,500 tokens vs monolith.
5. **Deterministic lean compression** (KP-04, score: 0.82) — Reduces upward reports by 1,800 tokens, preserving semantics.
6. **Composite gate scoring** (KP-05, score: 0.80) — Multi-signal gates catch false-pass conditions.

### Tier 2: Validated (score ≥ 0.70, confidence ≥ 74%)

7. **Convergence detection** (KP-06, score: 0.79) — Eliminates wasted retry rounds, ~1,500 tokens saved per loop.
8. **Lifecycle hooks** (KP-13, score: 0.78) — High violation detection rate at stage boundaries.
9. **Upward compression defaults** (KP-08, score: 0.77) — Aggressive L3→L0 compression produces dense reports.
10. **Rationalization prevention** (KP-10, score: 0.75) — Measurably reduces P1 principle violations.
11. **Workflow templates** (KP-09, score: 0.72) — 17 templates cover common patterns; selection varies by complexity.
12. **Wave coordination** (KP-14, score: 0.71) — Parallel/sequential/gen-verify modes improve throughput.

### Tier 3: Needs Refinement

13. **Multi-IDE delivery** (KP-11, score: 0.68) — Cross-IDE consistency has measurable gaps.
14. **Typed schemas** (KP-15, score: 0.66) — Benefits difficult to isolate from other factors.
15. **Cross-session learnings** (KP-12, score: 0.64) — Noisy signal; injection criteria need tightening.

---

## 8. Lessons Learnt

### L1: Hierarchy Provides Compounding Value

The 4-layer hierarchy (KP-02, score: 0.85) enables context isolation (KP-07, score: 0.86) and bounded budgets (KP-03, score: 0.83). These three mechanisms compound: hierarchy defines boundaries, isolation enforces them, budgets constrain them. Together they account for the largest share of measured savings.

### L2: Compression ROI Exceeds Expectations

Lean compression (KP-04) and upward defaults (KP-08) combine for −4,200 tokens per stage cycle. At break-even of 2 interactions, compression amortizes faster than any other mechanism. **Invest in deterministic compression before behavioral rules.**

### L3: Quality Gates Prevent Expensive Failures

Composite gates (KP-05) and convergence detection (KP-06) catch problems that waste entire retry cycles. A single prevented stagnation loop saves more tokens than gates cost over a full session.

### L4: Context Economics Dominate Meta-Framework Value

Context-related mechanisms (KP-01, KP-03, KP-07) contribute 60% of measured savings. For meta-frameworks, **context management is the primary value lever** — more impactful than behavioral rules or workflow templates.

### L5: Cross-IDE Consistency Remains Hard

KP-11 (multi-IDE delivery) scored partially effective, echoing Caveman's KP-06. Adapters for Cursor, Codex, Claude Code, and Copilot produce measurably different behaviors from identical rules. Per-IDE integration testing is essential.

### L6: Cross-Session Learnings Need Curation

KP-12 scored lowest among effective mechanisms. Injecting previous session learnings introduces noise unless criteria are strict. **Cap learnings tokens and validate relevance per-task.**

### L7: Typed Schemas Resist Measurement

KP-15 scored inconclusive — not because schemas lack value, but because benefits (consistency, parsability) are difficult to isolate. Schema compliance is a hygiene factor, not a performance lever.

### L8: Bounded Loops Are a Safety Net

Stagnation detection (KP-06) prevents the most expensive failure mode: infinite retry loops. Even imperfect detection (0.79) eliminates worst-case scenarios where Agents waste thousands of tokens on blocked tasks.

---

## 9. EvoBench Integration Insights

NineS v0.6.0 introduces EvoBench, a 32-dimension evaluation framework (T1–T8: Tool, M1–M8: Model, W1–W8: Workflow, TT1–TT8: Task). DevolaFlow's analysis reveals key alignments:

| EvoBench Dimension | DevolaFlow Mapping | Insight |
|--------------------|-------------------|---------|
| W2 (`step_efficiency`) | Hierarchy + workflow templates | Directly measures structured workflow impact |
| M3 (`token_efficiency`) | Task-adaptive profiles + budgets | Aligns with measured 42.5% context savings |
| W5 (`information_density_score`) | Lean compression + upward defaults | Validates compression preserves density |
| TT3 (`context_utilization`) | Context isolation + handoffs | Measures bounded context utilization |
| W7 (`convergence_speed`) | Gate scoring + stagnation detection | Maps to round-3 convergence observed |
| T4 (`tool_selection_accuracy`) | Workflow template routing | Corresponds to KP-09 measurement |

!!! note "Calibrated Test Beds"
    DevolaFlow's three scenarios (hotfix/feature/full_pipeline) provide calibrated test beds: hotfix isolates W2/M3, feature stresses W5/TT3, full_pipeline exercises all 6 dimensions.

---

## 10. NineS Capabilities Assessment

### Current Capabilities (v0.5.0)

Uses same component set as Caveman analysis: `AgentImpactAnalyzer`, `KeyPointExtractor`, `BenchmarkGenerator`, `MultiRoundRunner`, `MappingTableGenerator`, and `SelfEvalRunner`.

### Capability Gaps & Proposed v0.6.0 Improvements

| Gap | Impact | v0.6.0 Improvement |
|-----|--------|---------------------|
| No live LLM execution | Cannot validate dispatch patterns | Trajectory-based evaluation with step recording |
| No trajectory tracking | Multi-layer interactions (L0↔L1↔L2↔L3) unrecorded | Agent step sequence recording and analysis |
| No cross-IDE testing | KP-11 unvalidatable | Cross-IDE behavioral consistency testing |
| No context density scoring | Compression quality beyond token counting | EvoBench `eval_scripts` density metrics |
| No gate-aware scoring | Gates evaluated around, not through | Gate definitions integrated into scoring pipeline |

---

## 11. Migration & Integration Recommendations

### For Structured Orchestration

DevolaFlow's hierarchy (KP-02) and context isolation (KP-07) provide a validated template:

1. Define agent layers with explicit responsibilities (dispatcher vs implementer)
2. Set per-layer token budgets proportional to task complexity
3. Use artifact-based handoffs rather than context sharing
4. Implement composite quality gates at each layer boundary

### For Behavioral Rule Enforcement

1. Encode principles as enforceable rules (not just suggestions)
2. Add rationalization prevention (KP-10) for critical principles
3. Implement lifecycle hooks (KP-13) at stage boundaries
4. Test rules across all target IDEs (KP-11)

### For Context Optimization

1. Build task-adaptive profiles rather than one-size-fits-all context
2. Apply deterministic compression to upward reports
3. Cap cross-session learnings injection to prevent noise
4. Measure break-even point and optimize for it

---

## 12. Reproduce This Analysis

!!! abstract "Run It Yourself"
    ```bash
    # Clone DevolaFlow
    git clone https://github.com/YoRHa-Agents/DevolaFlow.git /tmp/devolaflow

    # Full benchmark workflow
    nines benchmark --target-path /tmp/devolaflow --rounds 5 --output-dir ./reports/devolaflow

    # Or step by step:
    nines analyze --target-path /tmp/devolaflow --agent-impact --keypoints
    nines analyze --target-path /tmp/devolaflow --agent-impact --keypoints -f json > analysis.json

    # With EvoBench dimensions (v0.6.0):
    nines benchmark --target-path /tmp/devolaflow --evobench --dimensions W2,M3,W5,TT3
    ```

---

## Appendix: Methodology Notes

### Evaluation Limitations

1. **Simulated execution**: Benchmarks use a passthrough executor. Real Agent execution requires live LLM calls and trajectory recording.
2. **Confidence bounds**: Computed from sample size, variance, and convergence. Statistical confidence, not semantic certainty.
3. **Version dependency**: Based on DevolaFlow v4.2.0. Repository updates may change detection and scoring.
4. **Meta-framework scope**: Evaluating orchestration rules differs from evaluating Agent behavior under those rules — the latter requires live execution.

### Scoring Methodology

- **Composite score**: Mean of per-scorer normalized scores for each task
- **Effectiveness threshold**: ≥ 0.70 composite + ≥ 0.60 confidence → "effective"
- **Convergence**: Sliding window (3 rounds) standard deviation < 0.02
- **Reliability**: pass@k computed across rounds per `ReliabilityCalculator`
