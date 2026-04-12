# T03 Research Report: Benchmarks & Evaluation Frameworks for AI Agent Effectiveness

> **Task**: Research L3 — Benchmarks, evaluation frameworks, and metrics for measuring AI Agent effectiveness with focus on context management, tool usage, and compression impact.
>
> **Date**: 2026-04-12
> **Status**: Complete

---

## 1. Existing Benchmark Frameworks and What They Measure

### 1.1 Task-Completion Benchmarks

| Benchmark | What It Measures | Metric | Scale | Year |
|-----------|-----------------|--------|-------|------|
| **SWE-bench** (Original) | Real GitHub issue resolution across 12 Python repos | % Resolved (fail-to-pass test) | 2,294 tasks | 2023 |
| **SWE-bench Verified** | Human-curated subset for fair evaluation | % Resolved | 500 tasks | 2024 |
| **SWE-bench Pro** | Long-horizon tasks from 41 repos (hours/days for humans) | % Resolved | 1,865 tasks | 2025 |
| **SWE-bench Multilingual** | Cross-language agent capability (9 languages) | % Resolved | varies | 2025 |
| **SWE-bench++** | Automated benchmark generation from live PRs across 11 languages | pass@10 | 11,133 instances | 2025 |
| **Aider Polyglot** | Code editing across 6 languages (C++, Go, Java, JS, Python, Rust) | Pass rate (2 attempts) | 225 Exercism problems | 2024 |
| **GitTaskBench** | Realistic repo-level tasks across 7 modalities and 7 domains | Alpha-value (success × cost × salary) | 54 tasks | 2025 |
| **AstaBench** | Scientific research agent capabilities | Multi-metric | 2,400+ examples | 2025 |

**Key observation**: These benchmarks primarily measure *task accuracy* (binary pass/fail). They do not capture how efficiently the agent reached its solution, how well it managed context, or how its tool usage patterns affected outcomes.

### 1.2 Long-Context & Agent-Interaction Benchmarks

| Benchmark | What It Measures | Key Metrics | Scale |
|-----------|-----------------|-------------|-------|
| **LoCoBench-Agent** (Salesforce) | Long-context SE agent workflows (10K–1M tokens) | 9 metrics: 5 comprehension + 4 efficiency | 8,000 scenarios, 10 languages, 36 domains |
| **AgentChangeBench** | Goal-shift robustness in dynamic environments | TSR, Tool Use Efficiency, Tool Call Redundancy, Goal-Shift Recovery Time | varies |
| **EvoBench (Multimodal)** | Reasoning, perception, decision-making in dynamic envs | Dynamic Elo ratings, Atomic Element Similarity | varies |

**LoCoBench-Agent's 9 metrics** are particularly relevant to NineS:
- **Comprehension** (5): Execution success rate, multi-session memory retention, cross-file consistency, dependency traversal, solution usability
- **Efficiency** (4): Runtime efficiency, memory efficiency, information coverage, long-range dependency resolution

### 1.3 Efficiency-Focused Benchmarks

| Framework | Focus | Key Innovation |
|-----------|-------|---------------|
| **OckBench** | Joint accuracy + token efficiency (model/hardware agnostic) | "Per-Token Intelligence" metric; OckScore combining accuracy with token penalties |
| **Token-Efficiency Intelligence Matrix (TEIM)** | Three-axis evaluation: accuracy, Token Efficiency Ratio, convergence trajectory | Distinguishes genuine reasoning from efficiency shortcuts |
| **Turn-Control Studies** | Token consumption growth patterns in coding agents | Shows token use grows quadratically per turn; 75th-percentile caps reduce cost 24–68% |

**Critical finding from OckBench**: Models of identical size can differ by **3.4× in token consumption** and **5.0× in latency** despite similar accuracy. This validates the need for efficiency-aware evaluation.

---

## 2. Key Metrics for Agent Effectiveness (Beyond Simple Accuracy)

### 2.1 Multi-Dimensional Frameworks

**CLEAR Framework** (Enterprise Agentic AI, 2025):
- **C**ost — 50× cost variations exist for similar accuracy levels
- **L**atency — Per-step and total completion time
- **E**fficacy — Task success rates
- **A**ssurance — Security and policy compliance
- **R**eliability — Consistency across runs (production: 60% single-run vs 25% 8-run consistency)

**Four-Pillar Assessment Framework** (2025):
- LLMs (instruction following, safety alignment)
- Memory (storage and retrieval quality)
- Tools (invocation correctness and efficiency)
- Environment (interaction quality)

**Layered Evaluation** (Maxim.ai):
- System Efficiency: latency, tokens consumed, tool calls made
- Session-Level: task success, trajectory quality
- Node-Level: tool selection accuracy, parameter correctness

### 2.2 Specific Metrics Catalog

| Metric | What It Captures | Source |
|--------|-----------------|--------|
| **Goal Completion Rate (GCR)** | Task success (binary) | Standard |
| **Tool Use Efficiency (TUE)** | Ratio of useful to total tool calls | AgentChangeBench |
| **Tool Call Redundancy Rate (TCRR)** | Wasted/duplicate tool invocations | AgentChangeBench |
| **Autonomy Index (AIx)** | Level of human intervention needed | Outcome-Oriented Framework |
| **Multi-Step Task Resilience (MTR)** | Recovery from intermediate failures | Outcome-Oriented Framework |
| **Decision Turnaround Time (DTT)** | Speed of decision-making | Outcome-Oriented Framework |
| **Goal-Shift Recovery Time (GSRT)** | Adaptation to changing requirements | AgentChangeBench |
| **Per-Token Intelligence** | Accuracy per token consumed | OckBench |
| **Token Efficiency Ratio (TER)** | Output quality normalized by token usage | TEIM |
| **OckScore** | Accuracy with token consumption penalties | OckBench |
| **Business Impact Efficiency (BIE)** | Economic value per unit cost | Outcome-Oriented Framework |
| **Alpha-Value** | Success × token cost × developer salary equivalent | GitTaskBench |

### 2.3 Reliability Metrics

Standard practice now distinguishes single-run accuracy from multi-run consistency:
- **pass@k**: Probability of at least one success in k attempts
- **Pass³**: Three-trial consistency metric
- Production systems show dramatic drops: 60% single-run → 25% at 8-run consistency

---

## 3. How Context Compression Impact Is Typically Measured

### 3.1 Established Measurement Approaches

**A. Token Reduction Metrics**
- **Compression Ratio**: tokens_after / tokens_before (e.g., Caveman achieves ~55% input, ~25% output retention)
- **Peak Token Reduction**: Maximum tokens in context window (ACON: 26–54% reduction)
- **Total Token Consumption**: Across full task lifecycle (Focus Agent: 22.7% reduction, 14.9M → 11.5M)

**B. Accuracy Preservation Metrics**
- **Task Accuracy Delta**: Performance change post-compression (Focus Agent: 0% accuracy loss at 22.7% compression)
- **Semantic Retention Compression Rate (SrCr)**: Novel 2025 metric quantifying compression-vs-preservation trade-off
- **Quality Score (0–5 scale)**: Averaged across accuracy, context awareness, artifact trail, completeness, continuity

**C. Probe-Based Evaluation** (Factory.ai, production-validated)
Four probe types that test what information survives compression:
1. **Recall probes**: "What was the original error?" (factual retention)
2. **Artifact probes**: "Which files were modified and how?" (state tracking)
3. **Continuation probes**: "What should we do next?" (planning chain)
4. **Decision probes**: "Why was this approach chosen?" (reasoning chain)

**D. Compression Threshold Research**
Task-dependent quality retention at different compression ratios:
| Compression | Quality Retention | Assessment |
|------------|-------------------|------------|
| 2×–5× | 95–98% | Recommended |
| 5×–10× | 90–95% | Caution |
| 10×–20× | 85–95% | Task-dependent, risky |

### 3.2 Context Degradation Patterns

Research reveals critical context management findings:
- **65% of enterprise AI failures in 2025** were attributed to context drift/memory loss, not raw context exhaustion
- **"Lost-in-the-middle" effect**: 30%+ accuracy drops for information positioned in conversation middles
- **Maximum Effective Context Window (MECW)** differs from advertised MCW, with models failing up to 99% short of claimed limits
- **Compounding degradation**: At 95% per-step reliability, a 20-step workflow drops to 36% combined success

### 3.3 Production Compression Strategies (Ranked by Effectiveness)

| Strategy | Compression Ratio | Quality Score | Notes |
|----------|-------------------|---------------|-------|
| Anchored Iterative Summarization | 98.6% | 3.70/5.0 | Best overall; structured persistent summaries |
| Regenerative Full Summary | 98.7% | 3.44/5.0 | Detailed but higher compute cost |
| Opaque Compression | 99.3% | 3.35/5.0 | Maximum compression, lowest fidelity |
| Caveman (output compression) | ~75% output tokens | ~100% technical accuracy | Removes linguistic redundancy, preserves facts |
| ACON (guideline-driven) | 26–54% peak tokens | 95%+ accuracy | Failure-driven iterative optimization |

---

## 4. Caveman Tool: Effectiveness Analysis

### 4.1 What Caveman Does

Caveman is a context compression technique that forces AI models to communicate in minimalist, stripped-down language. It operates on the principle that natural language in AI coding interactions contains significant redundancy.

**What is removed** (predictable/redundant):
- Grammar articles ("a", "the")
- Connectives ("therefore", "however")
- Passive constructions
- Filler words and pleasantries

**What is retained** (high information density):
- Facts, numbers, technical terms
- Constraints and specifics
- Code blocks (untouched)
- Technical nomenclature

### 4.2 Measured Effectiveness

| Metric | Value | Source |
|--------|-------|--------|
| Output token reduction | ~75% | Multiple implementations |
| Input token reduction | ~45% | wilpel/caveman-compression |
| Speed improvement | ~3× faster | JuliusBrussee/caveman |
| Technical accuracy | 100% preserved | Benchmarked tests |
| Accuracy improvement claim | +26 percentage points | JuliusBrussee/caveman benchmarks |

### 4.3 Key Analysis Points for NineS

Caveman's effectiveness stems from several decomposable factors:

1. **Linguistic redundancy removal**: Natural language has ~50% redundancy; removing it preserves information density
2. **Cognitive load reduction**: Forcing brevity may improve model focus on technical content
3. **Context window efficiency**: Fewer tokens per message = more useful context fits in the window
4. **Compounding effect**: Over multi-turn conversations, savings multiply (critical for long-horizon tasks)
5. **Counterintuitive accuracy gain**: Suggests models may perform better with constrained output patterns

These factors should be independently validated through NineS's evaluation framework.

---

## 5. How Major Companies Evaluate Tool/Plugin Effectiveness

### 5.1 Anthropic's Methodology

From "Demystifying Evals for AI Agents" and "Writing Effective Tools for Agents":

- **Eval Components**: Tasks (test cases with inputs + success criteria), Trials (multiple attempts for consistency), Graders (scoring logic), Transcripts (complete interaction records), Outcomes (final states)
- **Tool Optimization Loop**: Build prototype → Create eval → Measure → Use agents to improve tools against evals → Repeat
- **Key Principles**: Clear namespacing, return meaningful context, optimize tool descriptions

### 5.2 OpenAI's Methodology

From "Evaluate Agent Workflows" and "Trace Grading":

- **Trace Grading**: Capture end-to-end records of model calls, tool calls, and handoffs per run
- **Progression**: Start with trace grading for debugging → Move to repeatable datasets → Formal eval runs for benchmarking
- **Continuous evaluation** to identify regressions

### 5.3 GitHub Copilot Research (SPACE Framework)

- Uses multi-dimensional productivity framework beyond speed metrics
- **Acceptance rate** of AI suggestions is the best predictor of perceived productivity
- Measures: task time, product quality, cognitive load, enjoyment, learning
- Reports 10.6% increase in PRs and 3.5-hour cycle time reduction

---

## 6. Prompt/Skill Optimization Evaluation

### 6.1 Frameworks

| Framework | Approach | Key Innovation |
|-----------|----------|----------------|
| **SkillCompass** | 6-dimensional skill evaluation | Structure (10%), Trigger (15%), Security (20%), Functional (30%) scoring; evolutionary improvement engine |
| **SCOPE** | Self-evolving context optimization | Dual-Stream balancing tactical (immediate errors) vs strategic (long-term principles); 14.23% → 38.64% task success |
| **ZERA** | Zero-init instruction refinement | 8 evaluation principles with auto-inferred weights |
| **Promptfoo** | LLM-as-judge evaluation harness | 5-criteria scoring (1–5); pass threshold at 3.5+ average |

### 6.2 Evaluation Principles (from ZERA)

Eight evaluation axes for prompt/skill quality:
1. Completeness
2. Conciseness
3. Correctness
4. Expression Style
5. Faithfulness
6. Meaning Accuracy
7. Reasoning Quality
8. Structural Alignment

---

## 7. Recommended Evaluation Dimensions for NineS

Based on the research, NineS should adopt a multi-layered evaluation framework that covers dimensions no single existing benchmark addresses.

### 7.1 Core Evaluation Layers

**Layer 1 — Agent Effectiveness (Task-Level)**
| Dimension | Metric | Source Inspiration |
|-----------|--------|--------------------|
| Task Accuracy | % Resolved (binary pass/fail) | SWE-bench |
| Multi-Attempt Consistency | pass@k, Pass³ | SWE-bench, CLEAR |
| Error Recovery | Goal-Shift Recovery Time | AgentChangeBench |
| Generalization | Cross-language/cross-domain success | SWE-bench Multilingual |

**Layer 2 — Efficiency (Resource-Level)**
| Dimension | Metric | Source Inspiration |
|-----------|--------|--------------------|
| Token Efficiency | Per-Token Intelligence, OckScore | OckBench |
| Cost Effectiveness | Alpha-value (success × cost × salary) | GitTaskBench |
| Turn Efficiency | Useful turns / total turns | Turn-Control Studies |
| Context Utilization | Effective context used / context available | LoCoBench-Agent |
| Compression ROI | Accuracy preserved / tokens saved | ACON, Factory.ai |

**Layer 3 — Context Management Quality**
| Dimension | Metric | Source Inspiration |
|-----------|--------|--------------------|
| Information Retention | Probe-based recall (factual, artifact, continuation, decision) | Factory.ai |
| Semantic Preservation | SrCr metric | Compression research |
| Context Degradation Rate | Accuracy drop per compression cycle | Iterative summarization studies |
| Memory Efficiency | Multi-session retention score | LoCoBench-Agent |
| Cross-File Consistency | State coherence across files | LoCoBench-Agent |

**Layer 4 — Tool/Skill Impact**
| Dimension | Metric | Source Inspiration |
|-----------|--------|--------------------|
| Tool Use Efficiency | Useful / total tool calls | AgentChangeBench |
| Tool Call Redundancy | Duplicate/wasted calls | AgentChangeBench |
| Skill Quality Score | 6-dimensional SkillCompass score | SkillCompass |
| Skill Effectiveness Delta | Performance with skill − Performance without skill | A/B testing |
| Compression Factor Impact | Per-factor accuracy contribution | Decomposition analysis |

**Layer 5 — System-Level Quality**
| Dimension | Metric | Source Inspiration |
|-----------|--------|--------------------|
| Pipeline Latency | End-to-end time | CLEAR |
| Reliability | Multi-run consistency | CLEAR |
| Autonomy Index | Human intervention frequency | Outcome-Oriented Framework |
| Economic Value | Business Impact Efficiency | Outcome-Oriented Framework |

### 7.2 NineS-Specific Innovation: Factor Decomposition Evaluation

For analyzing repositories like Caveman, NineS should decompose effectiveness into independent testable factors:

```
Effectiveness = Σ (Factor_i × Weight_i)

Where factors for a compression tool might include:
  F1: Linguistic redundancy removal impact
  F2: Cognitive focus improvement
  F3: Context window space savings
  F4: Multi-turn compounding benefit
  F5: Output pattern constraint benefit
  F6: Technical vocabulary preservation
```

Each factor should be:
1. **Isolated** — Tested independently via controlled experiments
2. **Quantified** — Measured with specific metrics
3. **Validated** — Verified against task-completion benchmarks
4. **Weighted** — Importance determined through ablation studies

---

## 8. Gaps in Current Evaluation Approaches That NineS Could Fill

### 8.1 Identified Gaps

| Gap | Description | NineS Opportunity |
|-----|-------------|-------------------|
| **No unified efficiency-aware agent benchmark** | SWE-bench measures accuracy only; OckBench measures token efficiency but not for agents | Combine task accuracy with token/cost efficiency in a single agent benchmark |
| **No decomposition framework for tool impact** | Existing benchmarks test tools holistically, not their individual mechanisms | Build factor-decomposition evaluation that isolates how each mechanism of a tool contributes |
| **No context compression quality standard** | Factory.ai's probes are proprietary; no open standard exists | Define and publish open probe-based compression quality metrics |
| **No longitudinal agent evaluation** | Current benchmarks are snapshot evaluations | Track how agent performance evolves over multi-session interactions |
| **No skill/plugin comparative evaluation** | No standard way to compare competing skills (e.g., Caveman vs. other compression approaches) | Create standardized A/B evaluation protocol for agent skills |
| **No "context ROI" metric** | No metric captures "value generated per context token consumed" | Define and formalize Context ROI = (Task Value × Quality) / Total Tokens |
| **No evaluation of AI-oriented repositories** | Current analysis tools focus on code quality, not on how repos make agents more effective | Build evaluation criteria specifically for repos that enhance agent capabilities |
| **No compound effect measurement** | Individual tool benefits measured, but compound/interaction effects across tools unknown | Multi-tool interaction evaluation |
| **Lost-in-the-middle mitigation evaluation** | Known problem, but no benchmark specifically tests an agent's ability to mitigate it | Targeted evaluation of context management strategies against positional bias |

### 8.2 NineS's Unique Position

NineS is uniquely positioned to fill these gaps because its three-vertex architecture (Evaluation, Collection, Analysis) naturally supports:

1. **V1 (Eval)**: Running task-completion benchmarks with efficiency instrumentation
2. **V2 (Collect)**: Gathering real-world data on tool effectiveness from GitHub, arXiv, and community sources
3. **V3 (Analyze)**: Decomposing tool mechanisms into testable factors through codebase analysis
4. **MAPIM Loop**: Continuously iterating on evaluation criteria themselves based on findings

The self-improvement loop means NineS can treat its own evaluation methodology as something to be optimized — a meta-evaluation capability no existing benchmark possesses.

---

## 9. References

### Benchmarks
- SWE-bench: https://swebench.com/
- SWE-bench Pro: https://scaleapi.github.io/SWE-bench_Pro-os/
- Aider Polyglot: https://aider.chat/docs/leaderboards/
- OckBench: https://ockbench.github.io/
- LoCoBench-Agent: https://github.com/SalesforceAIResearch/LoCoBench-Agent
- GitTaskBench: arXiv:2508.18993

### Frameworks
- CLEAR: arXiv:2511.14136
- Four-Pillar Assessment: arXiv:2512.12791
- AgentChangeBench: arXiv:2510.18170
- SkillCompass: dev.to/john_spaghetti
- SCOPE: arXiv:2512.15374
- TEIM: boscotba.github.io/token-efficient-benchmarking

### Context Compression
- ACON: arXiv:2510.00615
- Active Context Compression (Focus Agent): arXiv:2601.07190
- Semantic Retention Compression Rate: arXiv:2505.07289
- Factory.ai Compression Evaluation: docs.factory.ai/guides/evaluating-context-compression
- Caveman: github.com/JuliusBrussee/caveman

### Industry Practices
- Anthropic Evals: anthropic.com/engineering/demystifying-evals-for-ai-agents
- Anthropic Tools: anthropic.com/engineering/writing-tools-for-agents
- OpenAI Evals: platform.openai.com/docs/guides/agent-evals
- GitHub Copilot Research: github.blog/research-quantifying-copilot-impact

---

*Report generated as part of NineS T03 Research Task. Timestamp: 2026-04-12T00:00:00Z*
