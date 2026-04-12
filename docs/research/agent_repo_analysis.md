# Analyzing AI-Oriented Repositories: A Research Synthesis

> **Task**: T04 — Research Synthesis (Agent Repo Analysis)
> **Team**: Research L3
> **Last Modified**: 2026-04-12
> **Status**: Complete

---

## 1. Introduction

Traditional code analysis evaluates repositories along well-understood axes: cyclomatic complexity, coupling and cohesion, architectural pattern adherence, test coverage, and dependency hygiene. These dimensions answer a single question: *is the code well-written?* For repositories designed to enhance AI Agent performance — context compression tools, prompt skills, Agent plugins, AGENTS.md configurations — this question is necessary but fundamentally insufficient.

AI-oriented repositories exist to change how an Agent behaves. A prompt skill file may contain zero executable code yet dramatically alter an Agent's task completion rate. A context compression tool may introduce a 500-token overhead per interaction but save 10,000 tokens over a long-horizon coding session. An AGENTS.md file may be syntactically perfect yet actively degrade Agent performance by poisoning its context window.

The analytical shift required is from **"is the code well-written?"** to **"how does this repository affect Agent effectiveness?"** This reframing demands new evaluation dimensions, new metrics, and new experimental methodologies that the software engineering community has only begun to formalize.

This document synthesizes research across context engineering, evaluation methodology, and benchmark design to establish a rigorous framework for analyzing AI-oriented repositories. It draws on findings from Anthropic's context engineering model, LangChain's failure mode taxonomy, production compression research (Factory.ai, ACON, Caveman), and the benchmark ecosystem surveyed in the [T03 Benchmark Evaluation Research](T03_benchmark_evaluation_research.md) and [External Frameworks Survey](external_frameworks.md).

---

## 2. The Context Engineering Paradigm

### 2.1 Context as a Finite Resource

Anthropic's research on building effective agents introduces a model where context is treated as a **finite resource with diminishing returns**. Unlike traditional software where adding more code linearly increases functionality, adding more context to an Agent follows a concave utility curve: early context tokens provide high marginal value, but each additional token contributes less — and eventually, additional context actively harms performance.

This model has a direct corollary in cognitive science. Human working memory holds approximately 7 ± 2 chunks of information (Miller, 1956). LLM context windows, despite holding millions of tokens, exhibit analogous capacity constraints:

| Property | Human Working Memory | LLM Context Window |
|----------|---------------------|-------------------|
| Nominal capacity | 7 ± 2 chunks | 128K–2M tokens |
| Effective capacity | Task-dependent, far below nominal | Task-dependent, far below nominal |
| Positional bias | Primacy and recency effects | "Lost-in-the-middle" effect (30%+ accuracy drop) |
| Degradation pattern | Interference from competing items | Context rot, distraction, confusion |
| Mitigation strategy | Chunking, rehearsal, external aids | Compression, summarization, retrieval |

!!! warning "Maximum Effective Context Window ≠ Advertised Context Window"
    Research consistently shows that LLMs fail to utilize their full advertised context length. Models can fail at up to **99% short of claimed limits** when measured by actual task performance. The Maximum Effective Context Window (MECW) is the operative constraint for AI-oriented repository analysis, not the model's technical token limit.

A critical implication follows: **clean context on a weaker model can outperform cluttered context on a stronger model**. This finding inverts the intuition that model capability is the dominant variable and elevates context engineering — the discipline of managing what enters the context window — to a first-order concern.

### 2.2 Four Context Failure Modes

LangChain and Anthropic's research identifies four distinct failure modes that degrade Agent performance through context mismanagement. Any AI-oriented repository must be evaluated against all four:

| Failure Mode | Definition | Example in AI-Oriented Repos | Detection Method |
|-------------|-----------|-------------------------------|-----------------|
| **Poisoning** | Incorrect or misleading information enters the context | A compression tool that introduces factual errors during summarization | Factual recall probes comparing pre/post-compression accuracy |
| **Distraction** | Irrelevant but non-harmful information dilutes attention | A verbose plugin that injects boilerplate instructions the Agent ignores | Signal-to-noise ratio measurement; ablation of non-essential content |
| **Confusion** | Contradictory information creates ambiguity | An AGENTS.md file with conflicting instructions across sections | Constraint compliance testing with deliberately contradictory inputs |
| **Clash** | Multiple context sources provide conflicting guidance | Two simultaneously active skills with incompatible behavioral directives | Multi-source activation testing; pairwise skill interaction analysis |

!!! note "Implication for Repository Analysis"
    A repository that introduces *any* of these failure modes — even while providing genuine utility — may have a net-negative impact on Agent effectiveness. Analysis must quantify both the tool's benefits and its context failure mode exposure.

### 2.3 The 65% Failure Attribution

Enterprise AI deployment data from 2025 attributes **65% of AI system failures** to context drift and memory loss, not to raw context exhaustion or model capability limitations. This finding reframes the value proposition of AI-oriented repositories: the most impactful tools are not those that extend context capacity, but those that **maintain context integrity** over extended interactions.

Context degradation compounds across multi-step workflows. At 95% per-step reliability, a 20-step workflow drops to 36% combined success (0.95²⁰ ≈ 0.36). AI-oriented repositories that improve per-step context reliability therefore have multiplicative impact on end-to-end task completion — a property that single-step evaluations systematically underestimate.

---

## 3. Evaluation Dimensions for AI-Oriented Repos

### 3.1 Agent Behavioral Impact

The primary question for any AI-oriented repository is whether it changes Agent behavior, and if so, whether the change is beneficial. This requires trajectory-level comparison, not just output-level comparison.

**Key evaluation questions:**

1. **Does it change Agent behavior?** Compare Agent execution trajectories (tool calls, reasoning steps, output structure) with and without the repository's tool active. Identical trajectories indicate the tool has no effect.
2. **How does it change behavior?** Characterize the nature of behavioral change along observable dimensions:
    - Output style (verbosity, formatting, terminology)
    - Tool usage patterns (call frequency, parameter choices, tool selection)
    - Reasoning depth (chain-of-thought length, intermediate step quality)
    - Error handling (recovery strategies, fallback behavior)
3. **Is the change beneficial?** Map behavioral changes to task-level outcomes:
    - Task completion rate (pass@1, pass@k)
    - Code correctness (test pass rate, regression rate)
    - Efficiency (tokens consumed, turns required, wall-clock time)

!!! tip "Trajectory Comparison Protocol"
    Record full Agent trajectories (every LLM call, tool invocation, and intermediate output) for both baseline and treatment conditions. Trajectory divergence analysis — identifying the *first point* at which behavior differs — often reveals the tool's mechanism of action more clearly than aggregate outcome metrics.

### 3.2 Context Economics

AI-oriented repositories impose token costs (the tool's own instructions, prompts, or injected context) and may generate token savings (compression, summarization, selective retrieval). The net economic impact determines whether the tool is worth its context budget.

| Metric | Formula | What It Captures |
|--------|---------|-----------------|
| **Tool Overhead** | `T_overhead = tokens_injected_per_interaction` | The context cost of having the tool active |
| **Token Savings** | `T_savings = tokens_baseline - tokens_with_tool` | Reduction in total tokens consumed per task |
| **Net Token Impact** | `NTI = T_savings - T_overhead` | Whether the tool saves more than it costs |
| **Break-even Length** | `L_break = T_overhead / savings_per_turn` | Interaction length where cumulative savings exceed cumulative overhead |
| **Context ROI** | `CROI = (TaskValue × Quality) / TotalTokens` | Value generated per context token consumed |

!!! warning "Full-Budget Accounting"
    Token savings must be computed over the **full interaction budget** (input + output, across all turns), not just the output of a single turn. A tool that reduces output tokens by 50% but increases input tokens by 30% (through prompt injection) may have a far smaller net impact than its headline compression ratio suggests.

The break-even length is a particularly important metric for context compression tools. A tool with high per-interaction overhead but strong per-turn savings becomes cost-effective only beyond a minimum conversation length. Short interactions subsidize the tool's overhead without recouping it.

### 3.3 Semantic Preservation

When an AI-oriented repository transforms context (through compression, summarization, or restructuring), it must preserve the semantic content that drives correct Agent behavior. Four sub-dimensions capture preservation quality:

**Instruction Survival Probability (Ψ)**

Not all tokens in a context window contribute equally to task outcomes. *Task-critical elements* — specific constraints, numerical values, ordering requirements, negation conditions — must survive transformation intact. Instruction Survival Probability measures the fraction of task-critical elements that remain actionable after the tool's transformation:

```
Ψ = (task-critical elements preserved and actionable) / (total task-critical elements)
```

Factory.ai's production-validated probe methodology tests survival through four probe types:

| Probe Type | What It Tests | Example |
|-----------|--------------|---------|
| **Recall** | Factual retention | "What was the original error message?" |
| **Artifact** | State tracking | "Which files were modified and how?" |
| **Continuation** | Planning chain | "What should we do next based on prior discussion?" |
| **Decision** | Reasoning chain | "Why was this approach chosen over alternatives?" |

**Constraint Compliance**

Beyond preserving factual content, the Agent must continue to follow explicit instructions after transformation. Constraint compliance testing provides the Agent with constrained tasks (e.g., "do NOT modify file X", "use only library Y") and measures whether constraints are obeyed post-transformation at the same rate as without the tool.

**Semantic Accuracy**

Meaning-level equivalence between pre-transformation and post-transformation context, measured via semantic similarity scores (embedding distance) and LLM-as-judge comparison. Semantic accuracy captures cases where facts survive but their relationships or implications are distorted.

**Reasoning Quality**

Chain-of-thought degradation is a subtle failure mode where the Agent's intermediate reasoning steps become shallower or less coherent after context transformation, even if final answers remain correct. Measured by comparing chain-of-thought depth, logical coherence, and intermediate step accuracy between baseline and treatment conditions.

### 3.4 Context Health

Beyond individual transformations, AI-oriented repositories affect the long-term health of the Agent's context across extended interactions.

| Dimension | Definition | Measurement Approach |
|-----------|-----------|---------------------|
| **Context Rot Resistance** | Whether the tool helps or hurts as context grows over many turns | Track task accuracy at interaction lengths of 10, 50, 100, 200 turns with and without tool |
| **Context Poisoning Prevention** | Whether the tool introduces factual errors that compound over time | Longitudinal recall probe accuracy across conversation length |
| **Context Relevance** | Whether the tool improves signal-to-noise ratio in the context | Information-theoretic analysis: mutual information between context tokens and task outcomes |
| **Lost-in-the-Middle Mitigation** | Whether the tool helps the Agent access information regardless of its position in the context | Positional probe testing: place critical information at beginning, middle, and end; measure recall variance |

!!! info "Context Rot: The Hidden Degradation"
    Chroma's research on context rot demonstrates that context quality degrades monotonically with conversation length in the absence of active management. A tool that merely maintains constant context quality across turns is already providing value — the baseline is *degradation*, not stability.

The **Degradation Cliff** is the interaction length at which Agent performance drops below a usability threshold (e.g., pass@1 < 50%). Tools that extend the degradation cliff — pushing it from turn 50 to turn 200, for example — provide compounding value that single-interaction evaluations cannot capture.

### 3.5 Mechanism Decomposition

AI-oriented repositories typically achieve their effects through multiple interacting mechanisms. Holistic evaluation (tool on vs. tool off) conflates these mechanisms and prevents understanding *why* a tool works or fails. Mechanism decomposition isolates each discrete mechanism for independent verification.

**Decomposition protocol:**

1. **Identify** each discrete mechanism the repository uses to affect Agent behavior (e.g., for a compression tool: linguistic redundancy removal, cognitive load reduction, context window space savings, output pattern constraints)
2. **Isolate** each mechanism through controlled experiment design — activate one mechanism at a time while holding others constant
3. **Quantify** each mechanism's individual contribution to the tool's aggregate effect
4. **Assess interactions** between mechanisms (synergistic, antagonistic, independent)
5. **Analyze failure modes** per mechanism — which mechanisms degrade under which conditions?

```
Aggregate_Effect ≈ Σ(Mechanism_i × Weight_i) + Σ(Interaction_ij)

Where:
  Mechanism_i = isolated effect of mechanism i
  Weight_i    = prevalence/frequency of mechanism i
  Interaction_ij = pairwise interaction between mechanisms i and j
```

!!! example "Decomposition Example: Caveman Compression"
    Caveman achieves ~75% output token reduction and claims +26 percentage points accuracy improvement. Decomposition would isolate:

    - **F1**: Linguistic redundancy removal (articles, connectives, filler) → token savings
    - **F2**: Cognitive focus improvement (brevity forces technical precision) → accuracy gain
    - **F3**: Context window space savings (more useful context fits) → long-horizon benefit
    - **F4**: Output pattern constraint (structured output reduces variance) → consistency gain
    - **F5**: Technical vocabulary preservation (code blocks untouched) → no information loss

    A terse-control condition (see §4.2) that applies F1 without F2–F5 isolates whether savings come from generic brevity or the tool's specific mechanism.

### 3.6 Cross-Benchmark Robustness

Single-benchmark evaluations produce misleading conclusions because they confound the tool's general effectiveness with its fit to one specific task distribution.

**Compression Robustness Index (CRI)**

The CRI methodology requires evaluation across a minimum of three diverse benchmarks and measures how consistently a tool's effect holds:

```
CRI = 1 - (σ_across_benchmarks / μ_across_benchmarks)

Where:
  σ = standard deviation of the tool's effect size across benchmarks
  μ = mean effect size across benchmarks
```

A CRI of 1.0 indicates perfectly consistent effect across benchmarks (zero variance). A CRI approaching 0 indicates that the tool's effect is highly benchmark-dependent and therefore unreliable as a general-purpose recommendation.

!!! warning "The Single-Benchmark Trap"
    A compression tool that shows +26 percentage points improvement on one benchmark but -5 on another and +2 on a third has a CRI of approximately 0.3 — indicating that the headline result is benchmark-specific, not generalizable. Without cross-benchmark testing, the +26 result would be reported as the tool's effectiveness.

**Recommended benchmark diversity dimensions:**

| Dimension | Why It Matters | Example Benchmarks |
|-----------|---------------|-------------------|
| Task type | Tools may help code tasks but hurt reasoning tasks | SWE-bench (code), HotpotQA (reasoning), GSM8K (math) |
| Interaction length | Tools may help long sessions but hurt short ones | Short (HumanEval), Medium (SWE-bench), Long (multi-session tasks) |
| Domain | Tools may be domain-specific in their effectiveness | Software engineering, customer service, data analysis |
| Difficulty | Tools may help easy tasks but fail on hard ones | SWE-bench Lite vs. SWE-bench Pro |

---

## 4. Evaluation Methodology

### 4.1 Three-Layer Evaluation

AI-oriented repository evaluation follows a three-layer approach, progressing from fast automated checks to comprehensive robustness testing. Each layer filters candidates: only repositories that pass Layer 1 proceed to Layer 2, and only those passing Layer 2 proceed to Layer 3.

#### Layer 1: Static Analysis (automated, <5 seconds)

Static analysis requires no Agent execution. It examines the repository's artifacts (prompts, configuration files, code) directly.

| Check | What It Detects | Method |
|-------|----------------|--------|
| **Token overhead estimation** | Context budget cost of the tool | Tokenize all injected content (system prompts, skill files, AGENTS.md) |
| **Mechanism classification** | What the tool claims to do | Pattern matching on README, configuration, and prompt content |
| **Claim verification** | Whether stated claims are plausible | Cross-reference claimed metrics against known baselines |
| **Security surface** | Prompt injection, data exfiltration risk | Static pattern scan for injection vectors, external URL references, credential handling |
| **Dependency analysis** | External requirements and compatibility | Dependency graph extraction, version constraint analysis |

Layer 1 produces a **Static Profile** summarizing the tool's overhead, mechanism, claims, and risk level. Tools with overhead exceeding a configurable threshold (e.g., >2,000 tokens per interaction with no compression mechanism) are flagged for manual review.

#### Layer 2: Controlled Comparison (automated, ~2 minutes)

Layer 2 runs the Agent on a standardized task set with and without the tool active, measuring behavioral and outcome differences.

| Test | What It Measures | Design |
|------|-----------------|--------|
| **A/B task completion** | Whether the tool changes pass@1 | Run identical tasks: baseline vs. tool-active, 3+ trials each |
| **LLM-as-Judge quality** | Subjective output quality delta | Blind LLM-as-Judge comparison of paired outputs (no tool labels) |
| **Ablation study** | Per-mechanism contribution | Activate mechanisms individually (see §3.5) |
| **Overhead measurement** | Actual token cost in practice | Instrument token counting across full interaction lifecycle |

Layer 2 produces a **Comparative Profile** with effect sizes, confidence intervals, and per-mechanism attribution. Results below a minimum effect size threshold (e.g., |Δ pass@1| < 2 percentage points) are classified as "no significant effect."

#### Layer 3: Robustness Testing (automated, ~10 minutes)

Layer 3 stress-tests tools that showed significant effects in Layer 2 across diverse conditions.

| Test | What It Measures | Design |
|------|-----------------|--------|
| **Multi-benchmark evaluation** | Cross-benchmark consistency | Run on 3+ diverse benchmarks; compute CRI |
| **Context scaling** | Performance across interaction lengths | Test at 10, 50, 100, 200 turns; identify degradation cliff |
| **Monte Carlo variation** | Sensitivity to prompt wording | Paraphrase task descriptions 10+ ways; measure outcome variance |
| **Adversarial probing** | Failure mode discovery | Edge cases: empty input, contradictory instructions, maximum-length context |

Layer 3 produces a **Robustness Profile** with CRI score, degradation cliff, variance metrics, and identified failure modes.

### 4.2 The Three-Arm Experimental Design

Controlled evaluation of AI-oriented repositories requires three experimental conditions, not two. The standard baseline/treatment design conflates the tool's specific mechanism with generic effects (e.g., any form of brevity improves performance).

| Arm | Condition | Purpose |
|-----|-----------|---------|
| **Baseline** | No tool active; Agent operates with default prompts and full-verbosity output | Establishes unmodified Agent performance |
| **Terse Control** | No tool active; Agent instructed to be concise via a generic brevity prompt | Isolates the effect of generic brevity/compression from the tool's specific mechanism |
| **Treatment** | Tool active as designed | Measures the tool's actual effect |

!!! warning "Why the Terse Control Is Critical"
    Without a terse control, a compression tool that achieves +10% accuracy could be attributed to its novel compression algorithm when the actual mechanism is simply "being brief helps." The terse control arm answers: *does this tool provide value beyond what a simple 'be concise' instruction achieves?*

    The tool's **incremental contribution** = Treatment effect - Terse control effect.

    If Treatment ≈ Terse Control >> Baseline, the tool provides no value beyond generic brevity.
    If Treatment >> Terse Control ≥ Baseline, the tool's specific mechanism provides genuine additional value.

### 4.3 Key Metrics

The following table consolidates the metrics required for comprehensive AI-oriented repository evaluation. Metrics are grouped by evaluation dimension and include formulas, interpretation guidance, and source references.

#### Efficiency Metrics

| Metric | Formula | Interpretation | Source |
|--------|---------|---------------|--------|
| **Token Reduction Ratio** | `TRR = 1 - (tokens_with_tool / tokens_baseline)` | Fraction of tokens saved; higher is better | Compression research |
| **Net Token Impact** | `NTI = T_savings - T_overhead` (per interaction) | Positive means net savings; must account for full budget | This synthesis |
| **Break-even Length** | `L_break = T_overhead / savings_per_turn` | Interactions needed before tool pays for itself | This synthesis |
| **Context ROI** | `CROI = (TaskValue × Quality) / TotalTokens` | Value generated per token consumed | T03 Gap Analysis |

#### Accuracy Metrics

| Metric | Formula | Interpretation | Source |
|--------|---------|---------------|--------|
| **pass@k** | `pass@k = 1 - C(n-c, k) / C(n, k)` | Probability of ≥1 success in k samples | HumanEval |
| **pass^k** | `pass^k = P(success on all k trials)` | Probability of consistent success (reliability) | TAU-Bench |
| **Task Completion Rate** | `TCR = tasks_passed / tasks_total` | Aggregate success rate | SWE-bench |
| **Trajectory Quality** | LLM-as-Judge score on reasoning trace (1–5 scale) | Quality of the Agent's problem-solving process | VAKRA waterfall judge |

#### Preservation Metrics

| Metric | Formula | Interpretation | Source |
|--------|---------|---------------|--------|
| **Instruction Survival Probability (Ψ)** | `Ψ = critical_elements_preserved / total_critical_elements` | Fraction of task-critical information surviving transformation | Factory.ai probes |
| **Context Recall** | `Recall = relevant_retrieved / total_relevant` | Completeness of information retrieval from context | Information retrieval |
| **Context Precision** | `Precision = relevant_retrieved / total_retrieved` | Purity of retrieved context (signal-to-noise) | Information retrieval |
| **Degradation Cliff** | Interaction length where pass@1 drops below threshold | How long the tool maintains effectiveness | Longitudinal testing |

#### Robustness Metrics

| Metric | Formula | Interpretation | Source |
|--------|---------|---------------|--------|
| **CRI** | `CRI = 1 - (σ_effect / μ_effect)` across 3+ benchmarks | Cross-benchmark consistency; 1.0 = perfectly consistent | This synthesis |
| **Semantic Retention** | `SrCr = semantic_similarity × (1 / compression_ratio)` | Preservation-vs-compression trade-off | arXiv:2505.07289 |

#### Composite Metrics

| Metric | Formula | Interpretation | Source |
|--------|---------|---------------|--------|
| **CLASSic** | Cost / Latency / Accuracy / Stability / Security — 5-axis profile | Multi-dimensional system-level assessment | Enterprise frameworks |
| **OckScore** | `accuracy - α × log(token_consumption)` | Accuracy penalized by token usage | OckBench |
| **Alpha-Value** | `success × token_cost × developer_salary_equivalent` | Economic value of agent performance | GitTaskBench |

---

## 5. Anti-Patterns in AI Repo Analysis

The following anti-patterns represent common methodological errors that produce misleading conclusions when evaluating AI-oriented repositories. Each anti-pattern is described with its mechanism of distortion and recommended mitigation.

### Anti-Pattern 1: Single-Benchmark Evaluation

**The error**: Evaluating a tool on one benchmark and reporting the result as the tool's general effectiveness.

**Why it misleads**: Tools frequently show strong effects on benchmarks that happen to align with their mechanism of action and weak or negative effects elsewhere. A compression tool optimized for code tasks may harm reasoning tasks by removing logical connectives that carry semantic weight.

**Mitigation**: Require CRI computation across ≥3 diverse benchmarks (§3.6). Report the mean and variance of effect sizes, not just the best result.

### Anti-Pattern 2: Output-Only Token Counting

**The error**: Measuring only output token reduction and ignoring input token overhead.

**Why it misleads**: A tool that reduces output tokens by 75% but injects 1,000 tokens of instructions per interaction has a net savings of `0.75 × output_tokens - 1,000` per turn. For short interactions with small outputs, this can be net-negative.

**Mitigation**: Compute NTI (§3.2) over the full token budget. Report both input and output token counts separately.

### Anti-Pattern 3: Cherry-Picked Examples

**The error**: Demonstrating a tool's effectiveness through hand-selected examples that showcase its strengths.

**Why it misleads**: Selection bias produces an unrepresentative picture. The tool's performance on the full task distribution may be substantially worse — or more variable — than the selected examples suggest.

**Mitigation**: Run controlled evaluations on standardized task sets. Report aggregate metrics with confidence intervals, not individual examples.

### Anti-Pattern 4: Ignoring Tool Overhead

**The error**: Treating the tool's prompt, configuration, and injected context as "free" when computing efficiency gains.

**Why it misleads**: In a 128K context window, a 2,000-token tool prompt consumes 1.5% of the window on every interaction. Over a 100-turn session, the tool has consumed 200K tokens of cumulative input budget — more than the window itself — before any savings are realized.

**Mitigation**: Include the tool's full overhead in break-even analysis (§3.2). Report the interaction length at which cumulative savings exceed cumulative overhead.

### Anti-Pattern 5: Conflating Tokens and Words

**The error**: Reporting compression ratios in terms of word count rather than token count.

**Why it misleads**: Tokenization is non-uniform. Removing common English words ("the", "a", "and") eliminates few tokens relative to their word count because they are typically single-token items. Conversely, technical terms and code fragments consume multiple tokens per word. Word-level compression ratios systematically overstate actual token savings.

**Mitigation**: Always measure and report token counts using the target model's tokenizer. Convert word counts to token counts before computing ratios.

### Anti-Pattern 6: Ignoring Reasoning Degradation

**The error**: Measuring only final-answer accuracy without examining chain-of-thought quality.

**Why it misleads**: A tool may maintain final-answer accuracy on simple tasks while degrading the Agent's reasoning process. This degradation becomes catastrophic on harder tasks where correct reasoning is necessary for correct answers. The tool appears effective on easy benchmarks and fails silently on hard ones.

**Mitigation**: Evaluate chain-of-thought quality independently of final-answer accuracy. Use reasoning probes and trajectory quality metrics (§4.3) alongside task completion rates.

### Anti-Pattern 7: Static-Only Analysis Without Agent Execution

**The error**: Drawing conclusions about a tool's effectiveness from code/prompt analysis alone, without running it in an Agent system.

**Why it misleads**: The interaction between a tool and an Agent is emergent. A prompt that reads well to a human may confuse the model. A compression algorithm that preserves semantic content according to similarity metrics may disrupt the model's internal representation in unpredictable ways. The AGENTS.md study (§6) demonstrates that well-intentioned context files can *reduce* Agent success rates.

**Mitigation**: Layer 1 static analysis (§4.1) is a filter, not a verdict. All tools that pass static analysis must proceed to Layer 2 controlled comparison before any effectiveness claims are made.

---

## 6. Existing Frameworks and References

### 6.1 Benchmark and Evaluation Frameworks

The following frameworks provide established methodologies for evaluating AI Agent performance. Their strengths and gaps are analyzed in detail in the [External Frameworks Survey](external_frameworks.md) and the [T03 Benchmark Evaluation Research](T03_benchmark_evaluation_research.md).

| Framework | Focus | Key Contribution to AI Repo Analysis |
|-----------|-------|--------------------------------------|
| **SWE-bench** | Real-world software engineering task completion | Gold-standard task completion measurement; FAIL_TO_PASS / PASS_TO_PASS test oracle pattern |
| **SWE-bench Pro** | Long-horizon, enterprise-scale tasks from 41 repos | Tests tool effectiveness on complex, multi-file problems where context management matters most |
| **Aider Polyglot** | Cross-language code editing (6 languages) | Cross-language robustness testing for tools claiming language-agnostic benefits |
| **Vercel agent-eval** | Agent evaluation in production-like settings | Production-oriented evaluation methodology |
| **OckBench** | Joint accuracy + token efficiency | Per-Token Intelligence metric; OckScore combining accuracy with consumption penalties |
| **LoCoBench-Agent** | Long-context agent workflows (10K–1M tokens) | 9 metrics across comprehension and efficiency; directly tests context management |

### 6.2 Context and Compression Frameworks

| Framework | Focus | Key Contribution |
|-----------|-------|-----------------|
| **ContextBench** | Context window utilization benchmarking | Standard benchmarks for measuring how well tools use available context |
| **OCTOBENCH** | Context management evaluation | Multi-dimensional context quality assessment |
| **ContextForge** | Context construction and management | Six-pillar model for context engineering quality |
| **CRI Methodology** | Cross-benchmark compression robustness | Standardized approach to measuring compression consistency across benchmarks |
| **CLASSic** | System-level assessment (Cost/Latency/Accuracy/Stability/Security) | Five-axis profile for holistic tool evaluation |

### 6.3 Skill and Plugin Evaluation

| Framework | Focus | Key Contribution |
|-----------|-------|-----------------|
| **SkillCompass** | 6-dimensional prompt/skill quality scoring | Structure (10%), Trigger (15%), Security (20%), Functional (30%) weighting; evolutionary improvement |
| **PluginEval** | Agent plugin effectiveness measurement | Standardized plugin comparison methodology |
| **SCOPE** | Self-evolving context optimization | Dual-Stream optimization balancing tactical and strategic improvement |
| **ZERA** | Zero-init instruction refinement | 8 evaluation principles with auto-inferred weights |

### 6.4 Critical Research Findings

#### The AGENTS.md Paradox

!!! danger "Counterintuitive Finding"
    Studies of AGENTS.md and similar context files reveal that **well-intentioned context injection can reduce Agent success rates**. Additional context does not monotonically improve performance. Beyond a tool-specific threshold, the marginal context token degrades the Agent's ability to focus on task-critical information.

This finding is the strongest argument for treating AI-oriented repository analysis as fundamentally different from traditional code analysis. A syntactically perfect, semantically coherent AGENTS.md file can actively harm the Agent it was designed to help — a failure mode that no traditional code quality metric would detect.

#### Chroma Context Rot Research

Chroma's production research demonstrates that context quality degrades over time as conversations accumulate information. Key findings:

- Degradation follows a predictable curve with an identifiable inflection point (the "degradation cliff")
- Active context management (compression, summarization, retrieval) can delay but not eliminate degradation
- The rate of degradation depends on the information density and diversity of the conversation

#### ContextForge Six-Pillar Model

ContextForge proposes six pillars for evaluating context engineering quality:

1. **Relevance** — Is the context pertinent to the current task?
2. **Completeness** — Does the context contain all necessary information?
3. **Accuracy** — Is the context factually correct?
4. **Freshness** — Is the context up to date?
5. **Structure** — Is the context organized for optimal consumption?
6. **Efficiency** — Is the context delivered with minimal token overhead?

These pillars map directly to the evaluation dimensions in §3: Relevance and Completeness → Context Health (§3.4), Accuracy → Semantic Preservation (§3.3), Freshness → Context Rot Resistance (§3.4), Structure → Agent Behavioral Impact (§3.1), Efficiency → Context Economics (§3.2).

---

## 7. Implications for NineS

### 7.1 Reshaping V3 Analysis

The research synthesized in this document fundamentally reshapes what NineS's V3 (Analysis) vertex must do when evaluating AI-oriented repositories. Traditional code analysis — which V3 already supports via AST-based structural analysis (see [Domain Knowledge](domain_knowledge.md) §2) — remains necessary for code quality assessment but is insufficient for determining a repository's impact on Agent effectiveness.

V3 must adopt a **dual-track analysis model**:

| Track | Focus | Methods | Output |
|-------|-------|---------|--------|
| **Track A: Code Quality** (existing) | Is the code well-written? | AST analysis, complexity metrics, architecture detection, dependency analysis | Code Quality Profile |
| **Track B: Agent Impact** (new) | How does this repo affect Agent effectiveness? | Three-layer evaluation (§4.1), three-arm experiments (§4.2), mechanism decomposition (§3.5) | Agent Impact Profile |

The Agent Impact Profile is the primary deliverable for AI-oriented repositories. It includes:

1. **Static Profile** (Layer 1): Token overhead, mechanism classification, risk assessment
2. **Comparative Profile** (Layer 2): Effect sizes with confidence intervals, per-mechanism attribution
3. **Robustness Profile** (Layer 3): CRI score, degradation cliff, failure modes

### 7.2 New Evaluation Dimensions to Implement

Based on the research, NineS should implement the following evaluation dimensions that are not covered by any existing tool or benchmark:

| Dimension | Priority | Implementation Complexity | Gap Filled |
|-----------|----------|--------------------------|------------|
| **Context Economics** (§3.2) — NTI, break-even, CROI | P0 | Medium | No existing tool performs full-budget token accounting |
| **Mechanism Decomposition** (§3.5) — per-mechanism isolation and quantification | P0 | High | No existing framework decomposes tool mechanisms |
| **Semantic Preservation** (§3.3) — Ψ, constraint compliance, reasoning quality | P1 | High | Factory.ai's probes are proprietary; no open standard |
| **Cross-Benchmark Robustness** (§3.6) — CRI across 3+ benchmarks | P1 | Medium | Single-benchmark evaluation is the norm |
| **Context Health** (§3.4) — degradation cliff, rot resistance, poisoning detection | P2 | Medium | Chroma research identifies the problem but provides no evaluation tool |
| **Three-Arm Experiment Design** (§4.2) — baseline, terse control, treatment | P0 | Low | No existing evaluation uses a terse control arm |

### 7.3 The Gap NineS Fills

The central finding of this research synthesis is that **no unified, efficiency-aware Agent benchmark exists** for evaluating AI-oriented repositories. The current landscape offers:

- **Task-completion benchmarks** (SWE-bench, HumanEval) that measure accuracy but not efficiency or context impact
- **Efficiency benchmarks** (OckBench, TEIM) that measure token efficiency but not for Agent-tool interactions
- **Context compression research** (Factory.ai, ACON) that evaluates compression quality but not end-to-end Agent impact
- **Skill evaluation frameworks** (SkillCompass, ZERA) that score prompt quality but not behavioral impact

NineS is uniquely positioned to bridge these gaps because its three-vertex architecture (Evaluation, Collection, Analysis) naturally supports the full evaluation pipeline:

```
V2 (Collect) → Identify AI-oriented repositories from GitHub, arXiv, RSS
     ↓
V3 (Analyze) → Dual-track analysis: Code Quality + Agent Impact
     ↓
V1 (Evaluate) → Three-layer evaluation with three-arm experiments
     ↓
MAPIM Loop → Iterate on evaluation methodology itself
```

The MAPIM self-improvement loop (see [Synthesis Report](synthesis_report.md) §3.5) means NineS can treat its own evaluation criteria as something to be optimized — a meta-evaluation capability that no existing benchmark possesses. As the landscape of AI-oriented repositories evolves, NineS's evaluation methodology evolves with it.

---

## References

### Benchmarks and Evaluation Platforms
- SWE-bench: [swebench.com](https://swebench.com/)
- SWE-bench Pro: [scaleapi.github.io/SWE-bench_Pro-os](https://scaleapi.github.io/SWE-bench_Pro-os/)
- Aider Polyglot: [aider.chat/docs/leaderboards](https://aider.chat/docs/leaderboards/)
- OckBench: [ockbench.github.io](https://ockbench.github.io/)
- LoCoBench-Agent: [github.com/SalesforceAIResearch/LoCoBench-Agent](https://github.com/SalesforceAIResearch/LoCoBench-Agent)
- GitTaskBench: arXiv:2508.18993
- Vercel agent-eval: [github.com/vercel/agent-eval](https://github.com/vercel/agent-eval)

### Context Engineering and Compression
- Anthropic, "Building Effective Agents": [anthropic.com/research/building-effective-agents](https://anthropic.com/research/building-effective-agents)
- Anthropic, "Writing Effective Tools for Agents": [anthropic.com/engineering/writing-tools-for-agents](https://anthropic.com/engineering/writing-tools-for-agents)
- ACON (Failure-Driven Context Optimization): arXiv:2510.00615
- Active Context Compression (Focus Agent): arXiv:2601.07190
- Semantic Retention Compression Rate: arXiv:2505.07289
- Factory.ai Compression Evaluation: [docs.factory.ai/guides/evaluating-context-compression](https://docs.factory.ai/guides/evaluating-context-compression)
- Chroma Context Rot Research: [research.trychroma.com/context-rot](https://research.trychroma.com/context-rot)
- Caveman Compression: [github.com/JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)

### Skill and Plugin Evaluation
- SkillCompass: 6-dimensional skill evaluation framework
- SCOPE (Self-Evolving Context Optimization): arXiv:2512.15374
- ZERA (Zero-Init Instruction Refinement): arXiv:2503.XXXXX
- ContextForge: [contextforge.dev](https://contextforge.dev)

### Metrics and Methodology
- CLEAR Framework (Enterprise Agentic AI): arXiv:2511.14136
- Token Efficiency Intelligence Matrix (TEIM): [boscotba.github.io/token-efficient-benchmarking](https://boscotba.github.io/token-efficient-benchmarking)
- OckBench Per-Token Intelligence: [ockbench.github.io](https://ockbench.github.io/)
- CLASSic (Cost/Latency/Accuracy/Stability/Security): Enterprise evaluation standard
- Pass^k (TAU-Bench): [github.com/sierra-research/tau-bench](https://github.com/sierra-research/tau-bench)
- Pass³ (Claw-Eval): [github.com/claw-eval/claw-eval](https://github.com/claw-eval/claw-eval)

### Industry Practices
- Anthropic Evals: [anthropic.com/engineering/demystifying-evals-for-ai-agents](https://anthropic.com/engineering/demystifying-evals-for-ai-agents)
- OpenAI Evals: [platform.openai.com/docs/guides/agent-evals](https://platform.openai.com/docs/guides/agent-evals)
- GitHub Copilot Research (SPACE Framework): [github.blog/research-quantifying-copilot-impact](https://github.blog/research-quantifying-copilot-impact)

### NineS Internal References
- [T03 Benchmark Evaluation Research](T03_benchmark_evaluation_research.md)
- [External Frameworks Survey](external_frameworks.md)
- [Synthesis Report](synthesis_report.md)
- [Domain Knowledge](domain_knowledge.md)

---

*Report generated as part of NineS T04 Research Task (Agent Repo Analysis). Timestamp: 2026-04-12T00:00:00Z*
