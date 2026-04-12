# Architecture Overview

<!-- auto-updated: version from src/nines/__init__.py -->

NineS {{ nines_version }} is organized around a three-vertex capability model with supporting infrastructure for orchestration, isolation, and agent runtime integration.

---

## System Architecture

```mermaid
graph TB
    subgraph CLI["CLI Layer"]
        cli_eval[nines eval]
        cli_collect[nines collect]
        cli_analyze[nines analyze]
        cli_selfeval[nines self-eval]
        cli_iterate[nines iterate]
        cli_install[nines install]
    end

    subgraph Orchestrator["Orchestrator"]
        engine[WorkflowEngine]
        pipeline[Pipeline Composer]
        artifacts[ArtifactStore]
    end

    subgraph V1["V1: Evaluation"]
        runner[EvalRunner]
        scorers[Scorers]
        metrics[Metrics]
        reporters[Reporters]
        matrix[MatrixEvaluator]
    end

    subgraph V2["V2: Collection"]
        github[GitHubCollector]
        arxiv[ArxivCollector]
        store[DataStore]
        tracker[IncrementalTracker]
        diff[ChangeDetector]
    end

    subgraph V3["V3: Analysis"]
        reviewer[CodeReviewer]
        structure[StructureAnalyzer]
        decomposer[Decomposer]
        indexer[KnowledgeIndex]
        abstraction[PatternAbstractor]
    end

    subgraph Iteration["Self-Iteration"]
        selfeval[SelfEvalRunner]
        baseline[BaselineManager]
        gap[GapDetector]
        planner[ImprovementPlanner]
        convergence[ConvergenceChecker]
    end

    subgraph Sandbox["Sandbox"]
        sbmgr[SandboxManager]
        isorunner[IsolatedRunner]
        venv[VenvFactory]
        pollution[PollutionDetector]
    end

    subgraph Core["Core Foundation"]
        protocols[Protocols]
        models[Models]
        config[Config]
        errors[Errors]
        events[EventBus]
    end

    subgraph Skill["Skill Adapters"]
        installer[SkillInstaller]
        cursor_adapter[CursorAdapter]
        claude_adapter[ClaudeAdapter]
    end

    CLI --> Orchestrator
    CLI --> V1
    CLI --> V2
    CLI --> V3
    CLI --> Iteration
    CLI --> Skill

    Orchestrator --> V1
    Orchestrator --> V2
    Orchestrator --> V3
    Orchestrator --> Iteration

    V1 --> Sandbox
    V1 --> Core
    V2 --> Core
    V3 --> Core
    Iteration --> Core
    Iteration --> V1
    Sandbox --> Core
    Skill --> Core
```

---

## Three-Vertex Model

The three vertices form a mutual reinforcement loop through six directed data flows:

```mermaid
graph LR
    V1((V1<br/>Evaluation)) -->|F1: Eval gaps trigger search| V2((V2<br/>Collection))
    V2 -->|F3: New sources feed analysis| V3((V3<br/>Analysis))
    V3 -->|F5: Knowledge units become eval tasks| V1
    V2 -->|F4: Collected repos feed eval| V1
    V3 -->|F6: Knowledge gaps become queries| V2
    V1 -->|F2: Eval results feed self-iteration| SI((Self-Iteration))
    SI -->|Targeted improvements| V1
    SI -->|Targeted queries| V2
    SI -->|Targeted analysis| V3
```

| Flow | Direction | Purpose |
|------|-----------|---------|
| F1 | V1 → V2 | Evaluation gaps trigger targeted information collection |
| F2 | V1 → Iteration | Evaluation scores feed the MAPIM self-improvement loop |
| F3 | V2 → V3 | Collected repositories become analysis targets |
| F4 | V2 → V1 | Collected data generates evaluation benchmarks |
| F5 | V3 → V1 | Knowledge units become evaluation task candidates |
| F6 | V3 → V2 | Knowledge gaps generate new search queries |

---

## Module Dependency Graph

Dependencies follow a strict DAG with `core/` at the foundation. No circular dependencies exist.

```mermaid
graph BT
    core[core/] --> sandbox[sandbox/]
    core --> eval[eval/]
    core --> collector[collector/]
    core --> analyzer[analyzer/]
    core --> skill[skill/]
    core --> iteration[iteration/]
    eval --> iteration
    core --> orchestrator[orchestrator/]
    eval --> orchestrator
    collector --> orchestrator
    analyzer --> orchestrator
    iteration --> orchestrator
    core --> cli[cli/]
    eval --> cli
    collector --> cli
    analyzer --> cli
    iteration --> cli
    orchestrator --> cli
    sandbox --> cli
    skill --> cli
```

### Dependency Rules

| Rule | Description |
|------|-------------|
| R1 | `core/` has zero imports from any other NineS module |
| R2 | No circular dependencies between any two modules |
| R3 | Vertex modules (`eval/`, `collector/`, `analyzer/`) do not import each other |
| R4 | `orchestrator/` is the only module permitted to import all vertex modules |
| R5 | `cli/` may import from any module (composition root) |
| R6 | `sandbox/` depends only on `core/` |
| R7 | `iteration/` depends on `core/` and `eval/` only |
| R8 | `skill/` depends only on `core/` |

### Topological Order

```
core → sandbox → eval → collector → analyzer → skill → iteration → orchestrator → cli
```

---

## Data Flow Diagrams

### Evaluation Flow (V1)

```mermaid
sequenceDiagram
    participant CLI
    participant EvalRunner
    participant TaskLoader
    participant SandboxMgr
    participant Scorer
    participant Reporter

    CLI->>EvalRunner: eval(config)
    EvalRunner->>TaskLoader: load(glob)
    TaskLoader-->>EvalRunner: tasks[]
    loop For each task
        EvalRunner->>SandboxMgr: create(seed, timeout)
        SandboxMgr-->>EvalRunner: sandbox handle
        EvalRunner->>SandboxMgr: execute(task)
        SandboxMgr-->>EvalRunner: ExecutionResult
        EvalRunner->>Scorer: score(result, expected)
        Scorer-->>EvalRunner: ScoreCard
        EvalRunner->>SandboxMgr: destroy()
    end
    EvalRunner->>Reporter: report(eval_result)
    Reporter-->>CLI: files[json, md]
```

### Collection Flow (V2)

```mermaid
sequenceDiagram
    participant CLI
    participant Registry
    participant Tracker
    participant Collector
    participant DataStore
    participant ChangeDetector

    CLI->>Registry: collect(config)
    Registry->>Tracker: get_bookmark(source)
    Tracker-->>Registry: cursor
    Registry->>Collector: search(query, since)
    Collector-->>Registry: items[]
    Registry->>DataStore: upsert(items)
    Registry->>Tracker: update_bookmark()
    Registry->>ChangeDetector: diff(prev, current)
    ChangeDetector-->>CLI: changes[]
```

### MAPIM Iteration Flow

```mermaid
sequenceDiagram
    participant Loop as MAPIMOrchestrator
    participant Eval as SelfEvalRunner
    participant Gap as GapDetector
    participant Conv as ConvergenceChecker
    participant Plan as ImprovementPlanner

    loop Until converged or max iterations
        Loop->>Eval: measure(19 dimensions)
        Eval-->>Loop: SelfEvalReport
        Loop->>Gap: detect(report, baseline)
        Gap-->>Loop: GapAnalysisReport
        Loop->>Conv: check(composite_scores)
        Conv-->>Loop: ConvergenceReport
        alt Converged
            Loop->>Loop: terminate & report
        else Not converged
            Loop->>Plan: plan(gaps, history)
            Plan-->>Loop: ImprovementPlan
            Loop->>Loop: execute actions
        end
    end
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Structural subtyping | Python `Protocol` | Third-party extensions work without knowing NineS base types |
| Storage backend | SQLite (WAL mode) | Zero-config, single-file, sufficient for single-user MVP |
| Configuration format | TOML | Human-readable, well-typed, Python ecosystem standard |
| Template engine | Jinja2 | Flexible, familiar, maintains separation of concerns |
| Rate limiting | Token bucket | Per-source calibration with adaptive backoff |
| Convergence detection | 4-method majority vote | Statistical rigor avoids premature/missed convergence |
| Sandbox isolation | Process + venv + tmpdir | Docker-free MVP (CON-05) with full isolation |
| Logging | structlog | Structured JSON for CI, colored console for development |
