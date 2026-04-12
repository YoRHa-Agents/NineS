# External AI Agent Evaluation Frameworks Survey

> **Task**: T03 — External AI Agent Evaluation Frameworks Survey
> **Team**: Research | **Stage**: S01 (research)
> **Last Updated**: 2026-04-11

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Framework Deep Dives](#framework-deep-dives)
   - [SWE-Bench Family](#1-swe-bench-family)
   - [Claw-Eval](#2-claw-eval)
   - [Exgentic](#3-exgentic)
   - [VAKRA (IBM)](#4-vakra-ibm)
   - [TAU-Bench / τ³-Bench](#5-tau-bench--τ3-bench)
   - [HumanEval / MBPP (and Pro variants)](#6-humaneval--mbpp-and-pro-variants)
   - [AgenticBench](#7-agenticbench)
   - [Terminal-Bench 2.0](#8-terminal-bench-20)
   - [AppWorld](#9-appworld)
   - [WebArena / OSWorld](#10-webarena--osworld)
3. [Comparison Matrix](#comparison-matrix)
4. [Cross-Cutting Analysis](#cross-cutting-analysis)
5. [Recommendations for NineS](#recommendations-for-nines)

---

## Executive Summary

The AI agent evaluation landscape in 2025-2026 is rapidly evolving from isolated code-generation benchmarks (HumanEval, MBPP) toward comprehensive, multi-dimensional agent evaluation platforms. Key trends include:

- **Reliability over single-shot accuracy**: Pass^k (TAU-Bench) and Pass³ (Claw-Eval) metrics penalize inconsistency, reflecting real-world deployment needs.
- **Docker-based sandbox isolation**: Most modern frameworks (SWE-Bench, Claw-Eval, Terminal-Bench 2.0) use containerized execution environments.
- **Multi-source, multi-hop reasoning**: VAKRA pushes evaluation beyond single-tool interaction toward compositional workflows across APIs and documents.
- **Universal evaluation protocols**: Exgentic proposes a Unified Protocol enabling agent-benchmark integration without benchmark-specific customization.
- **Human verification**: Modern benchmarks increasingly require human-verified task instances to eliminate automated scoring bias.

This survey covers 10 major frameworks, analyzing their evaluation dimensions, task formats, sandbox approaches, scoring methodologies, and relevance to NineS.

---

## Framework Deep Dives

### 1. SWE-Bench Family

**Repository**: [github.com/SWE-bench/SWE-bench](https://github.com/SWE-bench/SWE-bench)
**Origin**: Princeton University, 2023 (original); Scale AI, 2025 (Pro)
**License**: MIT (original), mixed (variants)

#### Purpose and Scope

SWE-Bench is the foundational benchmark for evaluating AI agents on real-world software engineering tasks. It derives task instances from actual GitHub Issues and Pull Requests across popular open-source Python repositories. The family has expanded into several variants:

| Variant | Size | Scope | Year |
|---------|------|-------|------|
| **SWE-Bench (Original)** | 2,294 instances | 12 Python repos | 2023 |
| **SWE-Bench Lite** | 300 instances | Subset of original | 2024 |
| **SWE-Bench Verified** | 500 instances | Human-filtered subset | 2024 |
| **SWE-Bench Pro** | 1,865 instances | 41 repos (enterprise) | 2025 |
| **SWE-Bench-Live** | 1,565+ instances | 164 repos, multi-language | 2025-2026 |

#### Evaluation Dimensions and Task Types

- **Bug fixing**: Resolve failing tests derived from real issue-PR pairs
- **Multi-file editing**: SWE-Bench Pro averages 107.4 source lines across 4.1 files
- **Long-horizon reasoning**: Pro tasks require hours to days for professional engineers
- **Cross-language capability**: Live supports Python, C, C++, C#, Java, Go, JS/TS, Rust

#### Task Definition Format

Each task instance is structured as:

```json
{
  "instance_id": "owner__repo-issue_number",
  "problem_statement": "<GitHub issue text>",
  "base_commit": "<commit hash>",
  "FAIL_TO_PASS": ["test_case_1", "test_case_2"],
  "PASS_TO_PASS": ["existing_test_1", "existing_test_2"],
  "patch": "<gold solution diff>"
}
```

Predictions are submitted in JSONL format with `instance_id`, `model_name_or_path`, and `model_patch`.

#### Sandbox / Isolation Approach

- **Docker containers** per task instance, with the repository installed at `base_commit`
- Each evaluation runs in an isolated containerized environment
- SWE-Bench Pro uses a 250-turn limit for agent runs
- SWE-Bench-Live supports both Linux and Windows containers

#### Scoring Methodology

- **Pass@1**: Primary metric — binary pass/fail per instance based on test execution
- `FAIL_TO_PASS` tests must pass after applying the agent's patch
- `PASS_TO_PASS` tests must continue passing (no regression)
- Aggregate: percentage of instances resolved

#### Strengths

- Gold-standard for software engineering agent evaluation
- Real-world provenance: tasks derived from actual GitHub activity
- Large, growing dataset with contamination-resistant design (Pro)
- Strong community adoption and well-maintained leaderboard
- Multi-language and multi-platform support (Live)

#### Weaknesses

- Primarily single-PR, single-issue scope (no multi-issue coordination)
- Test-based evaluation may miss valid alternative solutions
- Original benchmark suffers from data contamination concerns
- No evaluation of agent planning, communication, or tool selection strategies
- Limited to code modification tasks (no deployment, documentation, design)

#### Relevance to NineS

**High relevance**. SWE-Bench's task definition format (issue + test oracle) is a proven pattern for code-centric evaluation. NineS should adopt:
- The `FAIL_TO_PASS` / `PASS_TO_PASS` test oracle pattern for its evaluation framework
- Docker-based isolation for reproducible execution
- The concept of tiered difficulty (Lite → Verified → Full → Pro)

---

### 2. Claw-Eval

**Repository**: [github.com/claw-eval/claw-eval](https://github.com/claw-eval/claw-eval)
**Origin**: Peking University & University of Hong Kong, March 2026
**License**: Open source (repository public)

#### Purpose and Scope

Claw-Eval is an end-to-end transparent benchmark for evaluating AI agents on real-world tasks across enterprise service environments. Its distinctive contribution is the **Pass³ methodology**, which prioritizes agent reliability over single-attempt performance.

#### Evaluation Dimensions and Task Types

Four primary evaluation dimensions:

1. **Completion** (80% weight): Quality and correctness of task outcomes
2. **Robustness** (20% weight): Stability when facing edge cases or anomalous inputs
3. **Safety**: Security and safety during execution (binary multiplier)
4. **Pass³ Consistency**: Whether the agent passes the same task across 3 independent runs

Task types span 15 mock enterprise services:
- Calendar management, file operations, web search
- Code execution, financial analysis, email processing
- 35 multimodal agentic tasks (v1.1.0) requiring perception, reasoning, creation, and delivery

#### Task Definition Format

Tasks are organized around real-world scenarios with structured evaluation criteria and fixtures. Each task is paired with mock enterprise services in Docker containers. The v1.1.0 release added multimodal task definitions where agents must process images, PDFs, and other non-text inputs.

#### Sandbox / Isolation Approach

- **Docker sandbox per evaluation run**: Each of the 3 independent trials runs in a fresh container
- 15 mock enterprise services running as isolated Docker services
- Human verification of all results (no LLM-as-judge)
- API instability handled by manual re-triggering to ensure exactly 3 trajectories

#### Scoring Methodology

```
task_score = safety × (0.8 × completion + 0.2 × robustness)
pass_threshold ≥ 75%
primary_metric = Pass³ (% of tasks passed in ALL 3 independent runs)
```

The Pass³ metric is the primary ranking criterion. A task only counts as passed if the agent succeeds in all three independent runs, eliminating variance from "lucky" single-run successes.

#### Strengths

- **Pass³ is a paradigm shift**: Tests production-readiness, not just peak capability
- Human-verified results eliminate automated scoring bias
- Docker-based isolation ensures full reproducibility
- Multi-dimensional scoring (completion × robustness × safety) captures diverse quality aspects
- End-to-end transparency: all benchmark results are community-auditable
- Active maintenance (v1.1.0 with multimodal tasks as of April 2026)

#### Weaknesses

- Relatively small task set (139 tasks) compared to SWE-Bench
- Mock enterprise services may not capture full complexity of real systems
- Pass³ (N=3) is a fixed threshold; doesn't scale to arbitrary reliability levels
- Benchmark is still new (March 2026) with limited historical data
- No evaluation of long-horizon planning or multi-day tasks

#### Relevance to NineS

**Very high relevance**. Claw-Eval's design philosophy aligns closely with NineS's needs:
- **Pass³ methodology**: NineS should adopt multi-run reliability testing (generalizable to Pass^k)
- **Multi-dimensional scoring formula**: The `safety × (completion_weight × completion + robustness_weight × robustness)` pattern is directly applicable to NineS's composite scorer design
- **Docker sandbox pattern**: Validates NineS's lightweight sandbox approach (can extend from venv to Docker)
- **Human verification**: NineS should consider a verification layer for its evaluation results

---

### 3. Exgentic

**Repository**: [github.com/Exgentic/exgentic](https://github.com/Exgentic/exgentic)
**Origin**: February 2026
**License**: Apache 2.0

#### Purpose and Scope

Exgentic is a universal evaluation framework that standardizes testing of AI agents across diverse benchmarks. Rather than creating new tasks, it provides a **Unified Protocol** enabling any agent to be evaluated on any benchmark without benchmark-specific customization. It hosts the first Open General Agent Leaderboard.

#### Evaluation Dimensions and Task Types

Exgentic evaluates across existing benchmarks:

| Benchmark | Domain | Type |
|-----------|--------|------|
| TAU2 | Customer support (retail, airline, telecom) | Tool-use + user interaction |
| AppWorld | Multi-app API environments | API integration |
| BrowseComp+ | Web search and browsing | Information retrieval |
| SWE-Bench | Software engineering | Code generation |
| HotpotQA | Multi-hop question answering | Reasoning |
| GSM8K | Math word problems | Mathematical reasoning |

Evaluates agentic components: memory management, context compression, planning strategies.

#### Task Definition Format

Exgentic uses a **Unified Protocol** that wraps existing benchmark task formats. Agents interact through their native tool-calling mechanisms rather than benchmark-specific APIs. This allows fair comparison across different agent architectures (OpenAI Solo Agent, Claude Code, Smolagent, ReAct, etc.).

#### Sandbox / Isolation Approach

Inherits sandbox approaches from constituent benchmarks. Each benchmark environment runs independently with its own isolation model. The framework itself provides orchestration and result aggregation.

#### Scoring Methodology

- Success rate per benchmark task
- Cost per task (economic efficiency)
- Cross-benchmark aggregation for general agent capability assessment
- Results published on the Open General Agent Leaderboard

Key finding: the underlying LLM model drives performance more than agent architecture.

#### Strengths

- **Universal protocol**: Solves the fragmentation problem in agent evaluation
- Tests agent generalization across diverse domains
- Open source (Apache 2.0) with reproducible pipeline
- Evaluates both capability and efficiency (cost per task)
- Growing benchmark coverage
- Demonstrates that general agents can match domain-specific systems

#### Weaknesses

- Meta-framework: quality depends on constituent benchmarks
- Unified Protocol may oversimplify benchmark-specific evaluation nuances
- Limited evaluation of agent internals (mostly black-box)
- Relatively new with limited adoption data
- Does not introduce new evaluation tasks or dimensions

#### Relevance to NineS

**High relevance** for NineS's design philosophy:
- **Unified Protocol concept**: NineS should adopt a similar standardized evaluation interface (TaskLoader protocol)
- **Cross-benchmark aggregation**: NineS's matrix evaluation system can generalize this approach
- **Multi-agent comparison**: NineS should support evaluating different agent implementations on the same tasks
- **Efficiency metrics**: NineS should track cost/resource usage alongside correctness

---

### 4. VAKRA (IBM)

**Repository**: [github.com/IBM/vakra](https://github.com/IBM/vakra)
**Origin**: IBM Research, February-March 2026
**License**: Open source (Apache 2.0)

#### Purpose and Scope

VAKRA (eValuating API and Knowledge Retrieval Agents using multi-hop, multi-source dialogues) evaluates AI agents on complex, compositional reasoning tasks in enterprise-like settings. Its focus is on multi-hop, multi-source tool-calling workflows that combine structured API interactions with unstructured document retrieval.

#### Evaluation Dimensions and Task Types

Four progressively complex capability levels:

| Level | Capability | Description |
|-------|-----------|-------------|
| L1 | **API Chaining** | Nested and compositional API calls |
| L2 | **Tool Selection** | Large-scale tool selection over query-aligned endpoints |
| L3 | **Multihop Reasoning** | 3-7 dependent API calls with output transformation |
| L4 | **MultiHop MultiSource + Policy** | Multi-turn dialogues combining APIs + documents with constraints |

Environment: 8,000+ locally hosted APIs backed by real databases across 62 domains, plus domain-aligned document collections.

#### Task Definition Format

Tasks are defined as multi-turn dialogues with:
- Natural language queries requiring tool calls
- Ground-truth tool-call traces
- Expected final answers
- Policy constraints (for L4 tasks)
- Domain-aligned document collections for retrieval tasks

Available as a Hugging Face dataset (`ibm-research/VAKRA`).

#### Sandbox / Isolation Approach

- **Locally hosted API environment**: 8,000+ APIs running locally with real databases
- Replay-based evaluation: predicted tool trajectories are replayed against live VAKRA APIs
- Execution trace capture for full auditability

#### Scoring Methodology

**Waterfall Judge** — four sequential evaluation components:

1. **Policy Check**: Programmatic validation against policy constraints (L4 only)
2. **Exact-Match Tool-Response Check**: Ground-truth tool responses vs. predicted results
3. **Correctness Check (LLM Judge)**: If exact match fails, an LLM compares predicted vs. ground-truth answers
4. **Groundedness Check**: Verifies answers are grounded in actually executed tool outputs

Turn scores are aggregated into dialogue scores. Evaluation covers entity disambiguation, cross-source grounding, parameter alignment, tool selection accuracy, and policy adherence.

#### Strengths

- **Enterprise realism**: 62 domains with real databases, not mock data
- **Progressive complexity**: L1→L4 capability levels enable fine-grained assessment
- **Multi-source evaluation**: Unique combination of structured APIs + unstructured documents
- **Waterfall scoring**: Multi-layered evaluation catches different failure modes
- **Execution-trace based**: Full auditability of agent behavior
- Open dataset on Hugging Face with active leaderboard

#### Weaknesses

- Enterprise-focused: may not generalize to all agent use cases
- Complex setup: 8,000+ APIs require significant infrastructure
- LLM-as-judge in correctness check introduces subjectivity
- Primarily dialogue-based: doesn't evaluate code generation or file manipulation
- New benchmark (March 2026) with limited baseline data

#### Relevance to NineS

**Medium-high relevance**:
- **Progressive capability levels**: NineS's evaluation framework should support tiered difficulty assessment
- **Waterfall scoring pattern**: Multi-stage scoring (programmatic → exact match → LLM judge → groundedness) is a sophisticated pattern NineS can adopt
- **Multi-source reasoning**: NineS's knowledge analysis vertex needs similar cross-source evaluation
- **Execution trace capture**: NineS should record full agent trajectories for analysis

---

### 5. TAU-Bench / τ³-Bench

**Repository**: [github.com/sierra-research/tau-bench](https://github.com/sierra-research/tau-bench)
**Origin**: Sierra Research, 2024 (TAU-Bench); 2026 (τ³-Bench)
**License**: Open source

#### Purpose and Scope

TAU-Bench evaluates language agents on realistic three-way interactions between tools, agents, and users. It models agent interactions as partially observable Markov decision processes (POMDP) where agents must gather information incrementally through tool calls and simulated user conversations while following domain-specific policies.

#### Evaluation Dimensions and Task Types

Three evaluation domains (expanded in τ³-Bench):

| Domain | Tasks | Scope |
|--------|-------|-------|
| **tau-retail** | 115 tasks | Order modifications, cancellations, returns, exchanges, refunds |
| **tau-airline** | 50 tasks | Flight bookings, reservations, cancellations, membership policies |
| **tau-banking** (τ³) | New | Banking operations (added in 2026) |

Additional τ³-Bench innovations:
- **Voice evaluation modality**: Evaluates agents in speech-based interactions
- Domain fixes and expanded task coverage

#### Task Definition Format

Tasks include:
- Domain-specific scenarios with user intents
- LLM-powered user simulators for dynamic, multi-turn conversation
- Domain-specific API tools and databases
- Policy documents that agents must follow
- Ground-truth expected outcomes

#### Sandbox / Isolation Approach

- Simulated environment with API tools backed by databases
- LLM-powered user simulator creates dynamic, non-deterministic conversations
- Multiple independent trials per task for reliability assessment
- Domain-specific policy enforcement

#### Scoring Methodology

**Pass^k metric**: Measures the probability of succeeding on ALL k independent trials of the same task.

```
pass^k = P(success on all k trials)
```

Key results demonstrating reliability challenges:
- Claude 3.5 Sonnet: 69.2% pass^1, 46.2% pass^4 on retail
- GPT-4o: 60.4% pass^1, <50% overall
- All models: pass^8 < 25% on retail

This metric directly quantifies deployment reliability — if an agent handles 1M conversations, even pass^1 = 90% means 100K failures.

#### Strengths

- **POMDP formulation**: Theoretically grounded model of agent interactions
- **Pass^k metric**: Principled, parameterizable reliability measurement
- **User simulation**: Tests real conversational dynamics, not just tool execution
- **Policy adherence**: Evaluates compliance with domain rules
- **Scalable reliability assessment**: Pass^k reveals reliability curves across any k
- Active evolution (τ³-Bench with banking and voice modalities)

#### Weaknesses

- Limited domains (2-3 customer service scenarios)
- LLM-powered user simulator introduces non-determinism
- Customer service focus may not generalize to development/engineering tasks
- No code generation or file manipulation evaluation
- Pass^k computation requires many independent trials (expensive)

#### Relevance to NineS

**High relevance**:
- **Pass^k metric**: NineS should implement Pass^k as a first-class scoring metric alongside Pass@1
- **POMDP model**: NineS can model agent-tool-user interactions with this formalism
- **User simulation**: NineS's evaluation can use LLM-powered simulators for interactive tasks
- **Reliability curves**: NineS should generate reliability decay curves (pass^1 → pass^k) as a standard output

---

### 6. HumanEval / MBPP (and Pro variants)

**Repository**: [github.com/openai/human-eval](https://github.com/openai/human-eval) (HumanEval), [github.com/google-research/google-research/tree/master/mbpp](https://github.com/google-research/google-research) (MBPP)
**Origin**: OpenAI, 2021 (HumanEval); Google, 2021 (MBPP); CodeEval-Pro, 2025 (Pro variants)
**License**: MIT (HumanEval), Apache 2.0 (MBPP)

#### Purpose and Scope

HumanEval and MBPP are foundational code generation benchmarks that evaluate LLMs on function-level code synthesis from natural language descriptions. The 2025 Pro variants introduce self-invoking code generation — models must solve a base problem and then use that solution to solve a harder, related problem.

| Benchmark | Size | Focus |
|-----------|------|-------|
| **HumanEval** | 164 problems | Function synthesis from docstrings |
| **MBPP** | 974 problems | Function synthesis from descriptions |
| **HumanEval Pro** | 164 problems (paired) | Self-invoking code generation |
| **MBPP Pro** | 974 problems (paired) | Self-invoking code generation |
| **BigCodeBench-Lite Pro** | Extended | Self-invoking with library usage |

#### Evaluation Dimensions and Task Types

- **Functional correctness**: Generated code must pass test cases
- **Self-invoking capability** (Pro): Model must use its own prior solution as a building block
- **Progressive reasoning** (Pro): Tests compositional problem-solving

#### Task Definition Format

HumanEval format:
```python
{
    "task_id": "HumanEval/0",
    "prompt": "def function_name(args):\n    \"\"\"docstring\"\"\"",
    "entry_point": "function_name",
    "canonical_solution": "...",
    "test": "assert function_name(...) == ..."
}
```

Pro variants add a paired structure: base problem + dependent problem requiring self-invocation.

#### Sandbox / Isolation Approach

- **Subprocess execution**: Generated code is executed in isolated Python subprocesses
- Test-case driven evaluation with timeout limits
- No Docker containers (lightweight execution)

#### Scoring Methodology

- **Pass@k**: Probability that at least one of k generated samples passes all test cases
- Standard: pass@1, pass@10, pass@100
- Pro variants reveal 10-15% absolute performance drops vs. original benchmarks

#### Strengths

- Widely adopted baseline benchmarks with massive community adoption
- Simple, well-understood evaluation methodology
- Pro variants address ceiling effects with harder self-invoking tasks
- Lightweight execution (no Docker overhead)
- Clear progression from simple → compositional reasoning

#### Weaknesses

- Function-level only: no repository-level, multi-file, or system-level tasks
- Limited to Python (primarily)
- Test coverage may be insufficient (some valid solutions may fail)
- Saturating: top models achieve >95% on original HumanEval
- No agent interaction, tool use, or multi-turn evaluation
- No evaluation of code understanding, debugging, or refactoring

#### Relevance to NineS

**Medium relevance**:
- **Pass@k scoring**: NineS should support pass@k as a standard metric
- **Self-invoking pattern (Pro)**: Useful concept for testing compositional ability in NineS's analysis vertex
- **Lightweight execution model**: Validates NineS's subprocess-based sandbox approach for simple tasks
- **Ceiling awareness**: NineS should design tasks that avoid saturation

---

### 7. AgenticBench

**Website**: [agenticbench.com](https://agenticbench.com)
**Origin**: 2025-2026 (internal research)
**License**: Research-only (public release pending)

#### Purpose and Scope

AgenticBench is a comprehensive evaluation framework for autonomous AI agents in unpredictable, open-ended environments with complex, long-horizon goals. It focuses on sustained robust performance rather than single-task completion.

#### Evaluation Dimensions and Task Types

Four primary dimensions:

1. **Complex, Long-Horizon Task Execution**: Multi-stage procedures requiring strategic planning, tool use, and adaptation over extended durations
2. **Dynamic Planning, Re-planning & Recovery**: Proactive anticipation and reactive recovery from unexpected obstacles, failures, or environmental shifts
3. **Robustness Under Extreme Uncertainty**: Performance amid severe sensor noise, incomplete information, environmental perturbations, and adversarial interference
4. **Longitudinal Operational Analysis**: Tracking performance, resource consumption, and goal adherence over extended periods

#### Task Definition Format

Not publicly disclosed. The benchmark tests autonomous agent performance in unpredictable, open-ended environments. Tasks require sustained operation, resource management, and dynamic recovery.

#### Sandbox / Isolation Approach

Not publicly disclosed. Expected to use containerized or virtualized environments given the emphasis on dynamic environments and resource management.

#### Scoring Methodology

Multi-dimensional scoring across the four evaluation dimensions. Specific metrics and aggregation formulas are not yet publicly available.

#### Strengths

- **Unique focus on robustness and recovery**: Few benchmarks test dynamic re-planning
- **Longitudinal evaluation**: Tracks sustained performance, not just one-shot capability
- **Extreme uncertainty testing**: Addresses real-world deployment challenges
- **Resource management focus**: Evaluates economic efficiency of agent operation

#### Weaknesses

- **Not yet publicly available**: Internal research evaluation only
- Limited documentation on methodology and scoring
- No published baseline results or community validation
- Unknown task format and sandbox approach
- Cannot be independently reproduced

#### Relevance to NineS

**Medium relevance** (limited by availability):
- **Evaluation dimensions**: NineS should incorporate robustness, recovery, and longitudinal analysis dimensions
- **Resource management**: NineS's self-evaluation system should track resource efficiency
- **Dynamic re-planning**: NineS's self-iteration mechanism can benefit from this concept

---

### 8. Terminal-Bench 2.0

**Repository**: [github.com/harbor-framework/terminal-bench-2](https://github.com/harbor-framework/terminal-bench-2)
**Website**: [tbench.ai](https://www.tbench.ai)
**Origin**: UCSB ML Security Lab, 2025-2026
**License**: Open source

#### Purpose and Scope

Terminal-Bench 2.0 evaluates AI agents on realistic, high-skill command-line interface tasks that reflect actual professional workflows. Tasks range from system administration to security analysis, data processing, and scientific computing.

#### Evaluation Dimensions and Task Types

89 tasks across 10 technical domains:
- Software engineering
- System administration
- Security analysis
- Data processing
- Machine learning / scientific computing
- Network configuration

Difficulty distribution:
- 8% completable by junior engineers in under 1 hour
- 72% completable within one workday
- 4% requiring over a week

#### Task Definition Format

Each task includes:
- A Dockerized environment with pre-configured files and dependencies
- Human-written oracle solutions
- pytest-based verification tests that assess **final container state** (not intermediate steps)
- Clear task description and expected outcomes

#### Sandbox / Isolation Approach

- **Docker containers** per task with pre-configured environments
- Final-state evaluation (checks container state, not agent trajectory)
- Harbor framework for evaluation orchestration
- Compatible with multiple agents (Claude Code, Terminus, etc.)

#### Scoring Methodology

- Binary pass/fail per task based on pytest verification
- Aggregate: percentage of tasks passed
- Frontier models and agents score less than 65%

#### Strengths

- **Professional-grade tasks**: Reflects real engineering workflows
- **Final-state evaluation**: Allows agents to take any path to the solution
- **Pre-configured Docker environments**: Realistic, reproducible setup
- **High difficulty**: Far from saturation (best < 65%)
- **Open evaluation framework** (Harbor)

#### Weaknesses

- Relatively small task set (89 tasks)
- CLI-only: no GUI or web interaction
- Primarily infrastructure/DevOps focused
- Limited evaluation of planning or multi-agent coordination
- No multi-turn user interaction

#### Relevance to NineS

**Medium relevance**:
- **Final-state evaluation**: NineS should support state-based evaluation (not just output matching)
- **Docker environment setup**: Pattern for NineS's sandbox design (pre-configured environments)
- **Professional task difficulty**: NineS should calibrate task difficulty against professional engineer timelines
- **Harbor framework**: Reference architecture for evaluation orchestration

---

### 9. AppWorld

**Repository**: [appworld.dev](https://appworld.dev)
**Origin**: ACL 2024 Best Resource Paper
**License**: Open source

#### Purpose and Scope

AppWorld evaluates autonomous AI agents on realistic, multi-app digital tasks. It simulates 9 day-to-day applications operable via 457 APIs, populated with realistic digital activities of ~100 fictitious users.

#### Evaluation Dimensions and Task Types

750 tasks requiring:
- Multi-app coordination (notes, messaging, shopping, email, music, maps, calendar, contacts)
- Interactive code generation with complex control flow
- Cross-application state management
- Two difficulty levels: normal and challenge

#### Task Definition Format

Tasks are defined as natural language instructions with:
- User context (identity, preferences, history)
- Expected state changes across multiple apps
- Programmatic verification tests (40,000 lines of test code)

#### Sandbox / Isolation Approach

- **Self-contained execution environment**: 60,000 lines of engine code simulating 9 apps
- 457 APIs for agent interaction
- State-based evaluation with collateral damage detection
- Local execution via CLI or Jupyter notebook

#### Scoring Methodology

- Programmatic state-based unit tests
- Checks for "collateral damage" (unexpected state changes)
- Allows different valid solution paths
- Normal vs. challenge difficulty splits

#### Strengths

- **Multi-app realism**: Rich simulation of interconnected digital services
- **Collateral damage detection**: Unique quality of checking for unintended side effects
- **Large-scale verification**: 40,000 lines of test code
- **ACL Best Resource Paper**: Peer-validated quality
- **Interactive code generation**: Tests complex agent behavior

#### Weaknesses

- Simulated environment may not capture real API complexity
- Limited to 9 specific app types
- No code modification or software engineering tasks
- Performance still far below human capability
- Limited multi-turn conversational evaluation

#### Relevance to NineS

**Medium relevance**:
- **Collateral damage detection**: NineS should implement side-effect checking in its evaluation framework
- **Multi-service coordination**: Pattern for evaluating agents across NineS's three capability vertices
- **State-based verification**: NineS should support pre/post-state comparison evaluation

---

### 10. WebArena / OSWorld

**Repositories**: [webarena.dev](https://webarena.dev) / [os-world.github.io](https://os-world.github.io)
**Origin**: CMU (WebArena, 2023), multiple institutions (OSWorld, 2024)
**License**: Open source

#### Purpose and Scope

WebArena and OSWorld evaluate AI agents on real-world computer interaction tasks. WebArena focuses on web navigation, while OSWorld extends to full desktop environments across multiple operating systems.

| Benchmark | Tasks | Environment | Top Agent | Human |
|-----------|-------|-------------|-----------|-------|
| **WebArena** | 812 | Web (shopping, forums, GitLab, maps) | ~39% | 78.24% |
| **OSWorld** | 369 | Desktop (Ubuntu, Windows, macOS) | 12.24% | 72.36% |

#### Evaluation Dimensions and Task Types

- Web navigation and interaction
- Multi-site reasoning and coordination
- Desktop application usage
- Cross-application workflows
- File management and system configuration

#### Task Definition Format

Tasks include:
- Natural language instructions
- Pre-configured web/desktop environments
- Evaluation functions (URL matching, element verification, state checking)
- Screenshot-based observation space

#### Sandbox / Isolation Approach

- **WebArena**: Self-hosted web services (shopping, forums, GitLab, maps)
- **OSWorld**: Virtual machines with full OS environments
- OSWorld-Verified (2025): AWS-hosted with reduced evaluation time (~1 hour)
- Screenshot-based observation for multimodal agents

#### Scoring Methodology

- Task completion rate (binary pass/fail per task)
- Functional correctness via environment-specific evaluation functions
- Aggregate: percentage of tasks completed

#### Strengths

- **Real computer environments**: Not simulated APIs but actual software
- **Multimodal evaluation**: Screenshot-based observation tests visual understanding
- **Cross-platform** (OSWorld): Linux, Windows, macOS
- **Large gap from human performance**: Far from saturation
- **Community-maintained** with active updates

#### Weaknesses

- High infrastructure cost (VMs, web services)
- Slow evaluation cycles
- Limited task diversity within domains
- No code generation or software engineering focus
- Primarily tests GUI interaction, not programmatic API use

#### Relevance to NineS

**Low-medium relevance**:
- **Multimodal evaluation**: NineS may eventually need to evaluate agents that interact visually
- **Real environment execution**: Validates the importance of realistic evaluation environments
- **Performance gap insight**: NineS should target tasks where meaningful improvement is possible

---

## Comparison Matrix

| Framework | Eval Dimensions | Task Format | Sandbox Approach | Scoring Method | Open Source | Active Maintenance | Scale |
|-----------|----------------|-------------|-----------------|---------------|-------------|-------------------|-------|
| **SWE-Bench Family** | Code correctness, multi-file editing, long-horizon reasoning | JSON/JSONL (issue + test oracle + gold patch) | Docker containers per task instance | Pass@1 (binary test execution) | Yes (MIT) | Very active (monthly Live updates) | 300–1,865 tasks |
| **Claw-Eval** | Completion, robustness, safety, consistency | Structured scenarios with fixtures + Docker services | Docker sandbox per run, 15 mock services | Pass³ × (0.8·completion + 0.2·robustness) × safety | Yes | Active (v1.1.0, Apr 2026) | 139 tasks |
| **Exgentic** | Cross-benchmark generalization, efficiency | Unified Protocol wrapping existing benchmark formats | Inherited from constituent benchmarks | Success rate + cost per task, cross-benchmark aggregation | Yes (Apache 2.0) | Active (Feb 2026+) | 6+ benchmarks |
| **VAKRA (IBM)** | API chaining, tool selection, multi-hop reasoning, policy adherence | Multi-turn dialogues with tool traces + policy constraints | 8,000+ locally hosted APIs with real databases | Waterfall judge: policy → exact match → LLM judge → groundedness | Yes (Apache 2.0) | Active (Mar 2026) | 62 domains |
| **TAU-Bench / τ³** | Tool-agent-user interaction, policy compliance, reliability | Scenarios with user simulators + domain APIs + policies | Simulated environment with LLM-powered user simulators | Pass^k (reliability across k independent trials) | Yes | Active (τ³-Bench 2026) | 165+ tasks |
| **HumanEval / MBPP** | Functional correctness, self-invoking reasoning (Pro) | Function signature + docstring + test cases | Subprocess execution with timeout | Pass@k (k samples, at least 1 correct) | Yes (MIT / Apache 2.0) | Moderate (Pro: 2025) | 164–974 problems |
| **AgenticBench** | Long-horizon execution, re-planning, robustness, longitudinal analysis | Not publicly disclosed | Not publicly disclosed | Multi-dimensional (not disclosed) | No (research only) | Internal | Unknown |
| **Terminal-Bench 2.0** | CLI task completion across 10 domains | Dockerized environment + pytest verification | Docker containers, final-state evaluation | Binary pass/fail (pytest on container state) | Yes | Active (2026) | 89 tasks |
| **AppWorld** | Multi-app coordination, code generation, side-effect detection | Natural language + multi-app state context | Self-contained 9-app simulation (457 APIs) | State-based unit tests + collateral damage check | Yes | Moderate | 750 tasks |
| **WebArena / OSWorld** | Web/desktop navigation, multimodal interaction | Natural language + environment state | Self-hosted web/VM environments | Task completion rate (env-specific eval functions) | Yes | Active (OSWorld-Verified 2025) | 369–812 tasks |

---

## Cross-Cutting Analysis

### Trend 1: From Single-Shot to Reliability Metrics

The evolution from Pass@1 (SWE-Bench) → Pass@k (HumanEval, TAU-Bench) → Pass³ (Claw-Eval) reflects a fundamental shift toward measuring **deployment reliability** rather than peak capability. This is driven by the recognition that a 90% pass@1 agent still fails 100,000 times per million interactions.

**Implication for NineS**: NineS's scoring system must support parameterizable reliability metrics (Pass@1, Pass@k, Pass³) as first-class citizens.

### Trend 2: Multi-Dimensional Evaluation

Modern benchmarks reject single-score ranking in favor of multi-dimensional assessment:
- Claw-Eval: completion × robustness × safety
- VAKRA: progressive capability levels (L1-L4)
- AgenticBench: execution × planning × robustness × longitudinal
- TAU-Bench: accuracy × reliability × policy compliance

**Implication for NineS**: NineS's composite scorer should support arbitrary dimension definitions with configurable weights and aggregation strategies.

### Trend 3: Sandbox Sophistication

Sandbox approaches range from lightweight (HumanEval subprocess) to heavyweight (OSWorld VMs):

| Level | Approach | Frameworks | Overhead |
|-------|----------|-----------|----------|
| L0 | Subprocess | HumanEval, MBPP | Minimal |
| L1 | venv + tmpdir | — | Low |
| L2 | Docker container | SWE-Bench, Claw-Eval, Terminal-Bench | Medium |
| L3 | Docker + services | Claw-Eval (15 services), VAKRA (8K APIs) | High |
| L4 | Virtual machine | OSWorld | Very high |

**Implication for NineS**: NineS's sandbox architecture should support a tiered isolation model (L0-L2 for MVP, with L3 as a future extension). The initial venv + subprocess approach aligns with L1, with Docker as a natural upgrade path.

### Trend 4: Human Verification vs. LLM-as-Judge

A tension exists between scalable automated evaluation and human verification:
- **Human-verified**: Claw-Eval, SWE-Bench Verified
- **LLM-as-judge**: VAKRA (correctness check), DevBench
- **Programmatic only**: HumanEval, AppWorld, Terminal-Bench

**Implication for NineS**: NineS should primarily use programmatic evaluation (test oracles) with LLM-as-judge as a configurable fallback for subjective dimensions. Human verification should be supported as an optional overlay.

### Trend 5: Universal Evaluation Protocols

Exgentic's Unified Protocol addresses a real pain point: each benchmark has its own communication protocol, making it expensive to evaluate an agent across multiple benchmarks.

**Implication for NineS**: NineS's TaskLoader and Executor protocols should be designed as universal interfaces that can wrap external benchmark formats.

### Gaps in Current Landscape

| Gap | Description | Current Coverage |
|-----|-------------|-----------------|
| **Self-improvement evaluation** | No benchmark tests an agent's ability to improve itself iteratively | None |
| **Knowledge decomposition** | No benchmark evaluates structured knowledge extraction and abstraction | Partial (code analysis in SWE-Bench) |
| **Information tracking** | No benchmark evaluates ability to track and synthesize evolving information | None |
| **Cross-capability synergy** | No benchmark tests how well multiple agent capabilities reinforce each other | None |
| **Convergence measurement** | No benchmark measures whether agents converge to stable performance | TAU-Bench (pass^k implies convergence) |
| **Auto-curriculum generation** | No benchmark evaluates an agent's ability to generate its own training tasks | None |

---

## Recommendations for NineS

### Concepts to Adopt

#### 1. Scoring Framework: Composite Multi-Metric System

Synthesize the best scoring approaches:

```
NineS Score = Σ(dimension_weight × dimension_score)

Where each dimension supports:
- Pass@1 (SWE-Bench style, single-run)
- Pass@k (HumanEval/TAU-Bench style, best-of-k)
- Pass^k (TAU-Bench style, reliability across k runs)
- Pass³ (Claw-Eval style, all-3-must-pass)
- Composite: safety × (completion_weight × completion + robustness_weight × robustness)
```

This unified scoring approach subsumes all surveyed methodologies and allows NineS to produce comparable results against any external benchmark.

#### 2. Task Definition Format: Structured + Extensible

Adopt SWE-Bench's proven pattern with Claw-Eval's multi-dimensional extensions:

```python
@dataclass
class NinesTask:
    task_id: str
    problem_statement: str
    evaluation_dimensions: list[EvalDimension]  # Claw-Eval: completion, robustness, safety
    test_oracle: TestOracle  # SWE-Bench: FAIL_TO_PASS + PASS_TO_PASS
    capability_level: int  # VAKRA: L1-L4 progressive complexity
    domain: str
    metadata: dict  # Extensible
```

#### 3. Sandbox Architecture: Tiered Isolation

Implement a tiered sandbox model matching task requirements:

| NineS Tier | Approach | Use Case |
|-----------|----------|----------|
| **Tier 0** | Subprocess + tmpdir | Simple code execution, unit tests |
| **Tier 1** | venv + isolated filesystem | Python package evaluation, dependency isolation |
| **Tier 2** | Docker container | Full repo evaluation, system-level tasks |
| **Tier 3** | Docker + services | Multi-service evaluation (future) |

MVP should implement Tiers 0-1, with Tier 2 as a near-term extension.

#### 4. Evaluation Pipeline: Waterfall + Replay

Adopt VAKRA's waterfall scoring pattern:

1. **Programmatic check** (fast, deterministic)
2. **Exact-match check** (test oracle comparison)
3. **Fuzzy-match check** (semantic similarity)
4. **LLM-judge check** (subjective dimensions, configurable)
5. **Groundedness check** (ensure answers are supported by evidence)

#### 5. Reliability Metrics: Pass^k as First-Class Citizen

TAU-Bench's Pass^k and Claw-Eval's Pass³ should be core metrics in NineS. Implement:
- Configurable k parameter (default k=3 for MVP)
- Reliability decay curves (pass^1, pass^2, ..., pass^k)
- Seed control for deterministic sub-runs within each trial

#### 6. Universal Task Interface (from Exgentic)

NineS's TaskLoader protocol should support wrapping external benchmark formats:
- SWE-Bench JSONL → NinesTask
- Claw-Eval scenarios → NinesTask
- Custom TOML definitions → NinesTask

This enables NineS to serve as a meta-evaluation platform.

### Gaps NineS Can Fill

#### Gap 1: Self-Improvement Evaluation
No existing benchmark evaluates an agent's ability to iteratively improve its own performance. NineS's self-iteration vertex directly addresses this with:
- Baseline establishment → gap detection → improvement planning → re-evaluation cycle
- Convergence measurement across iteration rounds
- Auto-curriculum: agents generate their own evaluation tasks

#### Gap 2: Knowledge Decomposition Evaluation
No benchmark evaluates structured knowledge extraction and abstraction. NineS's knowledge analysis vertex can:
- Evaluate code review quality against human expert annotations
- Measure decomposition granularity and completeness
- Test abstraction accuracy (concrete → abstract pattern extraction)

#### Gap 3: Information Tracking Evaluation
No benchmark tests the ability to track and synthesize evolving information sources. NineS's information collection vertex can:
- Evaluate change detection accuracy (precision/recall against known changes)
- Measure tracking timeliness (latency between real change and detection)
- Test synthesis quality (summary accuracy of tracked changes)

#### Gap 4: Cross-Capability Synergy Measurement
Current benchmarks test capabilities in isolation. NineS can evaluate:
- Whether improved evaluation capability leads to better knowledge analysis
- Whether better information tracking improves evaluation task design
- Quantifiable synergy metrics across the three capability vertices

#### Gap 5: Convergence and Stability Analysis
While TAU-Bench's pass^k implies stability, no benchmark explicitly measures convergence behavior. NineS should:
- Track evaluation scores across N iterations and measure convergence rate
- Detect oscillation vs. monotonic improvement
- Define mathematical convergence criteria (e.g., score delta < ε for m consecutive rounds)

### Priority Adoption Roadmap

| Priority | Concept | Source | MVP? | Effort |
|----------|---------|--------|------|--------|
| **P0** | Test oracle pattern (FAIL_TO_PASS / PASS_TO_PASS) | SWE-Bench | Yes | Low |
| **P0** | Docker-ready sandbox with venv fallback | SWE-Bench, Claw-Eval | Yes (venv) | Medium |
| **P0** | Multi-dimensional scoring (composite scorer) | Claw-Eval | Yes | Medium |
| **P1** | Pass^k reliability metrics | TAU-Bench, Claw-Eval | Yes (k=3) | Low |
| **P1** | Waterfall scoring pipeline | VAKRA | Yes (stages 1-3) | Medium |
| **P1** | Universal task interface (TaskLoader protocol) | Exgentic | Yes | Medium |
| **P2** | Progressive capability levels (L1-L4) | VAKRA | Partial | Low |
| **P2** | Collateral damage detection | AppWorld | No | Medium |
| **P2** | Final-state evaluation (not just output) | Terminal-Bench | No | Medium |
| **P3** | LLM-as-judge integration | VAKRA, DevBench | No | High |
| **P3** | User simulation for interactive eval | TAU-Bench | No | High |

---

> **Summary**: The 2025-2026 agent evaluation landscape is converging on reliability-first, multi-dimensional, containerized evaluation. NineS is uniquely positioned to fill gaps in self-improvement evaluation, knowledge decomposition assessment, and cross-capability synergy measurement — areas no existing benchmark addresses. By adopting proven patterns (test oracles, Pass^k, composite scoring, waterfall judges) and filling these gaps, NineS can establish a differentiated position in the evaluation ecosystem.
