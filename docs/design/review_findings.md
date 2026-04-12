# NineS Architecture Review Findings

> **Task**: T18 — Architecture Review | **Team**: Review L3
> **Scope**: All design documents in `docs/design/` reviewed against 5 goals and 7 check dimensions
> **Last Modified**: 2026-04-11

---

## Review Dimensions

1. **Goal Coverage** — Do all 5 goals (G1–G5) have traceable requirements and design coverage?
2. **Interface Consistency** — Are module interfaces aligned across all design documents?
3. **Extensibility** — Can new data sources, scorers, analyzers, and runtime adapters be added at low cost?
4. **Self-Iteration Completeness** — Is the MAPIM loop fully specified with convergence guarantees?
5. **Sandbox Effectiveness** — Does the isolation model prevent host and cross-sandbox pollution?
6. **Skill Feasibility** — Is Agent Skill integration practical for Cursor and Claude Code?
7. **Performance** — Are NFR performance targets achievable with the proposed architecture?

---

## Summary

| Severity | Count |
|----------|-------|
| **Blocker** | 0 |
| **Critical** | 3 |
| **Major** | 7 |
| **Minor** | 8 |
| **Total** | 18 |

---

## Findings

### Critical Findings

#### C-01: Manifest Format Contradiction (JSON vs TOML)

| Field | Value |
|-------|-------|
| **Severity** | Critical |
| **Dimension** | Interface Consistency |
| **Documents** | `skill_interface_spec.md` §1.1, `skill_adapter.md` §2.1 |

**Description**: `skill_interface_spec.md` defines the skill manifest as **JSON** (with a `$schema` URL and JSONC comments), while `skill_adapter.md` redefines it as **TOML** (under `[skill]`, `[commands.*]`, `[runtimes.*]` sections). These are two incompatible formats for the same artifact.

The `architecture.md` config schema in §4.2 uses TOML for user config and JSON for manifests (CON-08), which supports the `skill_interface_spec.md` approach. However, the `skill_adapter.md` rationale for TOML ("following CON-08's TOML for user config convention") misapplies the convention — the manifest is machine-generated, not user-authored.

**Impact**: Implementers will not know which format to code against. The `SkillManifest.from_toml()` method in `skill_adapter.md` and the JSON schema in `skill_interface_spec.md` cannot coexist without a reconciliation layer.

**Recommendation**: Standardize on JSON for the bundled manifest (consistent with CON-08 and `skill_interface_spec.md`). The `skill_adapter.md` §2 should be revised to load from JSON. Alternatively, if TOML is preferred for authoring, define a single TOML source that is compiled to JSON at install time.

---

#### C-02: `max_actions_per_iteration` Inconsistency Between Requirements and Design

| Field | Value |
|-------|-------|
| **Severity** | Critical |
| **Dimension** | Interface Consistency, Self-Iteration Completeness |
| **Documents** | `requirements.md` FR-407, `architecture.md` §4.2, `self_iteration.md` §5.2 |

**Description**: Three different values for the maximum improvement actions per iteration:

- `requirements.md` FR-407: "≤3 improvement actions per iteration"
- `architecture.md` `[iteration]` config: `max_actions_per_round = 3`
- `self_iteration.md` `ImprovementPlanner.__init__`: `max_actions_per_plan: int = 10`

The self-iteration design document's default of 10 directly contradicts the FR-407 requirement of ≤3 and the architecture config default of 3.

**Impact**: If implemented with `max_actions=10`, each iteration could apply too many changes, violating the FR-407 scope-creep prevention goal (risk R04 in requirements §6.2). This undermines the convergence properties of the MAPIM loop.

**Recommendation**: Align `self_iteration.md` `ImprovementPlanner` default to `max_actions_per_plan=3`, matching FR-407 and the architecture config.

---

#### C-03: `DimensionEvaluator` Uses ABC Instead of Protocol (CON-09 Violation)

| Field | Value |
|-------|-------|
| **Severity** | Critical |
| **Dimension** | Interface Consistency, Extensibility |
| **Documents** | `self_iteration.md` §2.1, `architecture.md` §3.3 Rule R7, CON-09 |

**Description**: `self_iteration.md` defines `DimensionEvaluator` as an `ABC` (abstract base class) with `@abstractmethod`. This violates CON-09 ("All inter-module boundaries use Python Protocol classes for structural subtyping. No abstract base class inheritance required.") and the architecture's dependency rule R7.

All other design documents consistently use `@runtime_checkable Protocol` for their interfaces (`SourceProtocol`, `Scorer`, `PipelineStage`, `KnowledgeIndex`, etc.). `DimensionEvaluator` is the sole exception.

**Impact**: Third-party dimension evaluators would need to inherit from `DimensionEvaluator`, coupling them to NineS's base class. Testing becomes harder since mocks must subclass the ABC rather than simply implementing matching methods.

**Recommendation**: Convert `DimensionEvaluator` from ABC to `@runtime_checkable Protocol`. Move the `normalize()` default implementation to a standalone utility function or a mixin.

---

### Major Findings

#### M-01: Async/Sync Inconsistency Across Module Interfaces

| Field | Value |
|-------|-------|
| **Severity** | Major |
| **Dimension** | Interface Consistency |
| **Documents** | `eval_framework.md` §3.1, `info_pipeline.md` §2.2, `analysis_engine.md` §2.1, `self_iteration.md` §2.1 |

**Description**: The evaluation framework defines all pipeline stage protocols with `async def` methods (e.g., `async def score()`, `async def execute()`), while the collection pipeline, analysis engine, and self-iteration module use synchronous methods (e.g., `def search()`, `def process()`, `def evaluate()`).

This creates a fundamental API-level split: the eval subsystem is async-first, while all other subsystems are sync-first. The `orchestrator/` module — which must coordinate all three vertices — will need to bridge these two models.

**Impact**: The orchestrator must either wrap sync calls in `asyncio.to_thread()` or run everything synchronously, negating the async eval design. Integration tests will need both `pytest-asyncio` and synchronous test patterns.

**Recommendation**: Decide on one primary execution model for MVP. Given that the collection pipeline is I/O-bound (HTTP calls) and would benefit from async, and the analysis pipeline is CPU-bound (AST parsing), a pragmatic MVP approach is: all public APIs are synchronous; internal parallelism uses `concurrent.futures.ThreadPoolExecutor`. Async can be introduced in v2 for the eval and collection hot paths.

---

#### M-02: Built-in `IndexError` Name Shadowing

| Field | Value |
|-------|-------|
| **Severity** | Major |
| **Dimension** | Interface Consistency |
| **Documents** | `analysis_engine.md` §10 |

**Description**: The analysis engine error hierarchy defines `class IndexError(AnalysisError)` for knowledge index failures. This shadows Python's built-in `IndexError`, which will cause confusing behavior when catching exceptions:

```python
try:
    items[5]  # raises built-in IndexError
except IndexError:  # catches both NineS and built-in!
    ...
```

**Impact**: Any code that imports `from nines.analyzer.errors import IndexError` will shadow the built-in, causing subtle bugs in exception handling throughout the module.

**Recommendation**: Rename to `KnowledgeIndexError` to avoid shadowing.

---

#### M-03: Missing Standalone Orchestrator Design Document

| Field | Value |
|-------|-------|
| **Severity** | Major |
| **Dimension** | Goal Coverage (G3), Interface Consistency |
| **Documents** | `architecture.md` §1.1, `requirements.md` FR-401, FR-402 |

**Description**: The architecture defines an `orchestrator/` module (engine.py, pipeline.py, scheduler.py, artifacts.py) responsible for cross-vertex workflow execution (FR-401) and typed artifact passing (FR-402). However, no dedicated design document exists for this module. The orchestrator's behavior is partially described in `self_iteration.md` (MAPIM loop) and `architecture.md` (cross-vertex flow diagram), but critical details are missing:

- How does `WorkflowEngine` define and compose stages?
- What is the `ArtifactStore` schema for typed cross-vertex artifacts?
- How does the `StageScheduler` resolve dependencies between parallel stages?
- How are the six data flows (F1–F6 from `capability_model.md`) actually wired?

**Impact**: Implementers of T32 (Orchestration Engine) will lack a detailed specification. The cross-vertex data flows that are central to the three-vertex mutual reinforcement model (G1) have no concrete interface definitions.

**Recommendation**: Either create a dedicated `docs/design/orchestrator.md` in S04 (this review stage), or expand `architecture.md` §2.4 with full interface definitions for `WorkflowEngine`, `ArtifactStore`, and the F1–F6 flow wiring.

---

#### M-04: Eval Framework Dimension Model Overlaps with Self-Eval Spec

| Field | Value |
|-------|-------|
| **Severity** | Major |
| **Dimension** | Interface Consistency |
| **Documents** | `eval_framework.md` §1.2, `self_eval_spec.md` §2 |

**Description**: Two distinct dimension systems exist:

1. `eval_framework.md` defines 6 evaluation dimensions (D-CQ, D-AI, D-DD, D-PR, D-IF, D-SE) with their own `Dimension` Protocol, `MetricDefinition` model, and `DimensionRegistry`.
2. `self_eval_spec.md` defines 19 self-evaluation dimensions (D01–D19) with their own `DimensionSpec`, `DimensionEvaluator`, and `SelfEvalRunner`.

The eval framework document includes a mapping table (§1.4) showing how its 6 dimensions map to the 19 self-eval dimensions, but the code-level relationship is unclear. Are eval framework dimensions wrappers around self-eval dimensions? Are they separate implementations? Which `Dimension` Protocol do consumers use?

**Impact**: Confusion during implementation about which dimension model to use for a given context. Potential for score computation inconsistencies between the two systems.

**Recommendation**: Clarify the relationship explicitly: the 19 self-eval dimensions (D01–D19) are the canonical measurement system; the 6 eval framework dimensions (D-CQ etc.) are aggregation views used for evaluation reporting. The eval framework should consume self-eval results rather than duplicating measurement logic.

---

#### M-05: No Network Isolation in Sandbox MVP

| Field | Value |
|-------|-------|
| **Severity** | Major |
| **Dimension** | Sandbox Effectiveness |
| **Documents** | `sandbox_design.md` §11.3 |

**Description**: The sandbox resource limits table explicitly notes "Network: No restriction (MVP)" and "Future: netns or seccomp." This means evaluated code can make arbitrary network calls (HTTP requests, DNS lookups, outbound connections) during sandbox execution.

While NFR-09 (no host pollution) focuses on filesystem/env/path isolation, network access creates an uncontrolled side channel: evaluated code could exfiltrate data, make API calls that consume rate limits, or trigger external side effects.

**Impact**: Evaluation tasks that make network calls cannot be reliably sandboxed. The `PollutionDetector` does not monitor network activity. This weakens trust in sandbox isolation for any task that could contain untrusted code.

**Recommendation**: For MVP, add a configuration flag `sandbox.allow_network = false` (default) that, when disabled, sets the environment variable `no_proxy=*` and `http_proxy=http://0.0.0.0:0` to block most HTTP clients. Document that full network isolation requires Docker (Tier 2). Add a `PollutionReport.network_calls` field as a future extension point.

---

#### M-06: Collection Throughput NFR May Be Unachievable for Search Operations

| Field | Value |
|-------|-------|
| **Severity** | Major |
| **Dimension** | Performance |
| **Documents** | `requirements.md` NFR-03, `info_pipeline.md` §3.6 |

**Description**: NFR-03 targets "≥50 entities/min (REST core), ≥30 entities/min (search)." The rate limiter is calibrated to 30 requests/min for GitHub search. However, the search API returns paginated results (30 items/page by default, max 100/page). With 1 request per 2 seconds (30/min), and 30 items per response, throughput would be 900 entities/min, far exceeding the target.

But if the collector needs to deep-fetch each search result (via GraphQL or REST core), the effective throughput drops to 1 entity per request ≈ 83 entities/min for core API, which meets NFR-03. The issue is that `info_pipeline.md` does not clearly specify whether "entities/min" means search results or fully-fetched entities.

**Impact**: Performance benchmarks may pass or fail depending on interpretation.

**Recommendation**: Clarify NFR-03 to distinguish between "search result items/min" (metadata only) and "fully-fetched entities/min" (deep metadata including README, commits, releases). Define separate targets for each.

---

#### M-07: `self_eval_spec.md` Relies on scipy but `requirements.md` Limits Dependencies

| Field | Value |
|-------|-------|
| **Severity** | Major |
| **Dimension** | Performance, Interface Consistency |
| **Documents** | `eval_framework.md` §6.2, `requirements.md` NFR-27 |

**Description**: The `wilson_confidence_interval()` function in `eval_framework.md` §6.2 imports `from scipy.stats import norm`. NFR-27 constrains direct runtime dependencies to ≤15. `scipy` is a large dependency (~30MB installed) that would significantly impact CLI cold start time (NFR-06: ≤2s) and dependency count.

**Impact**: Adding scipy for a single z-score computation is disproportionate. It also conflicts with the lightweight, fast-startup design philosophy.

**Recommendation**: Replace `scipy.stats.norm.ppf()` with a pure-Python approximation (e.g., the Abramowitz and Stegun rational approximation for the inverse normal CDF, which is ~10 lines of code and accurate to 4.5×10⁻⁴). This eliminates the scipy dependency entirely.

---

### Minor Findings

#### m-01: Event Type `SANDBOX_EXECUTION_COMPLETE` Not in Architecture Event Registry

| Field | Value |
|-------|-------|
| **Severity** | Minor |
| **Dimension** | Interface Consistency |
| **Documents** | `sandbox_design.md` §4.1, `architecture.md` §7.2 |

**Description**: `sandbox_design.md` emits `EventType.SANDBOX_EXECUTION_COMPLETE` from `SandboxManager.execute_file()`, but this event type is not listed in the `EventType` enum in `architecture.md` §7.2. The architecture defines `SANDBOX_CREATED`, `SANDBOX_DESTROYED`, and `SANDBOX_POLLUTION_DETECTED`, but not execution completion.

**Recommendation**: Add `SANDBOX_EXECUTION_COMPLETE` to the `EventType` enum in `architecture.md` with payload keys: `sandbox_id`, `exit_code`, `duration_ms`, `timed_out`.

---

#### m-02: `skill_interface_spec.md` Manifest Uses JSON Comments (JSONC) Without Tooling Support

| Field | Value |
|-------|-------|
| **Severity** | Minor |
| **Dimension** | Skill Feasibility |
| **Documents** | `skill_interface_spec.md` §1.1 |

**Description**: The manifest schema in §1.1 uses `//` comments (JSONC syntax), but standard `json.loads()` cannot parse JSONC. The document does not specify whether the actual manifest file uses JSONC or plain JSON.

**Recommendation**: Clarify that the schema example uses JSONC for documentation only. The actual `manifest.json` must be valid JSON (no comments). Alternatively, if TOML is adopted per C-01 resolution, this becomes moot.

---

#### m-03: `ResponseCache` Defined in Both `collector/cache.py` and `DataStore`

| Field | Value |
|-------|-------|
| **Severity** | Minor |
| **Dimension** | Interface Consistency |
| **Documents** | `architecture.md` §1.1, `info_pipeline.md` §6.2 |

**Description**: `architecture.md` lists `collector/cache.py` as a separate module (`ResponseCache: local TTL-based caching layer`), while `info_pipeline.md` §6.2 implements caching as methods on `DataStore` (`cache_get`, `cache_set`, `cache_invalidate`, `cache_cleanup`) backed by the `response_cache` SQLite table. The `GitHubCollector` and `ArxivCollector` both receive a `cache: ResponseCache` parameter, but the actual implementation lives in `DataStore`.

**Recommendation**: Either `cache.py` should be a thin wrapper around `DataStore.cache_*` methods, or the cache should be extracted from `DataStore` into `cache.py` as a standalone class. Choose one ownership model.

---

#### m-04: `eval_framework.md` Uses `async` for `TaskLoader` but Tasks Are Local Files

| Field | Value |
|-------|-------|
| **Severity** | Minor |
| **Dimension** | Performance |
| **Documents** | `eval_framework.md` §3.1 |

**Description**: `TaskLoader.load()` is defined as `async def load(self, source: str | Path) -> list[EvalTask]`. Since task loading reads local TOML files from disk, making it async adds unnecessary complexity without performance benefit. Async file I/O in Python requires `aiofiles` or `asyncio.to_thread()`, adding either a dependency or overhead.

**Recommendation**: Make `TaskLoader.load()` synchronous. If future remote task sources are needed, a separate `RemoteTaskLoader` can be async.

---

#### m-05: `IterationPhase` Enum Referenced but Not Defined in `self_iteration.md`

| Field | Value |
|-------|-------|
| **Severity** | Minor |
| **Dimension** | Interface Consistency |
| **Documents** | `self_iteration.md` §8.4 |

**Description**: `IterationRecord.phase` is typed as `IterationPhase`, and the `MAPIMOrchestrator` sets `record.phase = IterationPhase.MEASURE`, but the `IterationPhase` enum is never defined in the document.

**Recommendation**: Add the enum definition:
```python
class IterationPhase(Enum):
    MEASURE = "measure"
    ANALYZE = "analyze"
    PLAN = "plan"
    IMPROVE = "improve"
```

---

#### m-06: `analysis_engine.md` Uses Generic Syntax `StageResult[T]` (Python 3.12+)

| Field | Value |
|-------|-------|
| **Severity** | Minor |
| **Dimension** | Interface Consistency |
| **Documents** | `analysis_engine.md` §2.1 |

**Description**: `StageResult[T]` uses Python 3.12's PEP 695 generic syntax (`class StageResult[T]`), which is appropriate given CON-01 (Python 3.12+). However, the `PipelineStage` Protocol uses `Protocol[T_In, T_Out]` with the older `TypeVar` syntax. The two styles should be consistent within the same document.

**Recommendation**: Use one generic syntax consistently. Since `from __future__ import annotations` is already imported, the older `TypeVar` style works everywhere. Alternatively, use PEP 695 syntax throughout for Python 3.12+ consistency.

---

#### m-07: Eval Framework's `BudgetExceededError` Uses `NineSError` (Typo)

| Field | Value |
|-------|-------|
| **Severity** | Minor |
| **Dimension** | Interface Consistency |
| **Documents** | `eval_framework.md` §7.2 |

**Description**: `class BudgetExceededError(NineSError)` uses `NineSError` (with capital S) as the base class, while `architecture.md` §5.1 defines the root error as `NinesError` (lowercase s). This is likely a typo.

**Recommendation**: Correct to `NinesError`.

---

#### m-08: `skill_adapter.md` Module Layout Differs from `architecture.md`

| Field | Value |
|-------|-------|
| **Severity** | Minor |
| **Dimension** | Interface Consistency |
| **Documents** | `skill_adapter.md` §11, `architecture.md` §1.1 |

**Description**: `architecture.md` defines `skill/` with flat files (`cursor_adapter.py`, `claude_adapter.py`, `templates/`), while `skill_adapter.md` §11 proposes a nested structure (`adapters/base.py`, `adapters/cursor.py`, `adapters/claude.py`, plus `engine.py`, `versions.py`, `detector.py`, `cli.py`). The architecture doc has `manifest.py`, `installer.py`, `models.py` while the skill adapter doc has `manifest.py`, `installer.py` plus additional files.

**Recommendation**: Align on one layout. The `skill_adapter.md` layout is more detailed and should be adopted; update `architecture.md` §1.1 accordingly.

---

## Goal Coverage Assessment

### G1: Capability and Responsibility Division

| Status | Evidence |
|--------|----------|
| **Fully Covered** | `capability_model.md` defines the three-vertex model with 18 sub-capabilities across 5 maturity levels. `requirements.md` §4.1 traces 22 FRs to G1. The mutual reinforcement model (§5) defines 6 data flows (F1–F6) with concrete examples. |

**Gap**: The orchestrator that wires the F1–F6 flows lacks a detailed design document (see M-03).

### G2: First-Round Knowledge Collection and Research

| Status | Evidence |
|--------|----------|
| **Fully Covered** | `requirements.md` §4.1 traces 18 FRs and 6 NFRs to G2. Technology choices (Python, uv, SQLite, structlog) are justified in the research-phase documents. `eval_framework.md` ADR section documents key deviations from EvoBench. |

### G3: Architecture Design

| Status | Evidence |
|--------|----------|
| **Fully Covered** | All 7 design documents (`architecture.md`, `eval_framework.md`, `info_pipeline.md`, `analysis_engine.md`, `self_iteration.md`, `sandbox_design.md`, `skill_adapter.md`) provide detailed module layouts, data flow diagrams, interface definitions, and requirement traceability. `requirements.md` traces 42 FRs and 18 NFRs to G3. |

**Gap**: Orchestrator module lacks standalone design (M-03). Interface inconsistencies noted in C-01, C-02, C-03, M-01.

### G4: MVP Implementation and Verification

| Status | Evidence |
|--------|----------|
| **Fully Covered** | `requirements.md` traces 55 FRs and 22 NFRs to G4. Every FR has a testable acceptance condition. The priority split (38 P0, 21 P1, 2 P2) provides clear scope management. Design documents include implementation-ready code for most interfaces. |

### G5: Self-Iterating Toolflow

| Status | Evidence |
|--------|----------|
| **Fully Covered** | `self_iteration.md` provides a complete MAPIM loop with mathematical convergence definitions (§7.1), escalation policies (§8.3), and growth tracking (§9). `self_eval_spec.md` defines all 19 dimensions with executable measurement methods and baseline collection plans. `requirements.md` traces 15 FRs and 3 NFRs to G5. |

**Gap**: `max_actions` inconsistency (C-02) could weaken scope control.

---

## Dimension-Level Conclusions

### 1. Goal Coverage
**Verdict**: All 5 goals are fully covered with traceable requirements. No goal lacks design support. The requirements traceability matrix in `requirements.md` §4 is comprehensive.

### 2. Interface Consistency
**Verdict**: 3 critical and 4 minor inconsistencies found. The manifest format contradiction (C-01) and async/sync split (M-01) are the most impactful. All are fixable without architectural redesign.

### 3. Extensibility
**Verdict**: Excellent. Protocol-based interfaces throughout (except C-03) enable low-cost extension. `NFR-13` (≤1 file for new source), `NFR-14` (≤1 file for new scorer), `NFR-15` (≤1 file for new analyzer), `NFR-16` (1 adapter class for new runtime) are all achievable with the current design. The `ScorerRegistry`, `SourceRegistry`, and `DimensionRegistry` patterns provide clean extension points.

### 4. Self-Iteration Completeness
**Verdict**: Complete. The MAPIM loop is fully specified with 4 convergence methods, majority-vote decision logic, 5 termination conditions, and 3-level escalation policy. The growth tracking system with lagged cross-correlations provides the mathematical foundation for measuring inter-vertex synergy (D19).

### 5. Sandbox Effectiveness
**Verdict**: Strong for the MVP scope. Three-layer isolation (process + venv + tmpdir), pollution detection via before/after snapshots, seed control with fingerprint verification, and multi-round stability checking cover NFR-09 through NFR-12. The lack of network isolation (M-05) is the primary gap.

### 6. Skill Feasibility
**Verdict**: Feasible with one critical fix (C-01). Both Cursor and Claude Code adapters are well-specified with concrete file layouts, template systems, and CLI integration. The single-source multi-target pattern from GSD is correctly applied. Version management semantics are clear.

### 7. Performance
**Verdict**: Achievable with noted caveats. Lazy imports (NFR-06), uv venv creation (NFR-02), SQLite WAL mode (NFR-07), and per-stage timing instrumentation (NFR-01) are well-designed. The scipy dependency issue (M-07) and throughput ambiguity (M-06) need resolution.

---

## Action Items for T19 (Architecture Revision)

### Must Fix (Critical)
1. **C-01**: Standardize manifest format to JSON; revise `skill_adapter.md` §2
2. **C-02**: Set `ImprovementPlanner.max_actions_per_plan = 3` in `self_iteration.md`
3. **C-03**: Convert `DimensionEvaluator` from ABC to Protocol in `self_iteration.md`

### Should Fix (Major)
4. **M-01**: Document sync-first policy for MVP; add note about async v2 path
5. **M-02**: Rename `IndexError` → `KnowledgeIndexError` in `analysis_engine.md`
6. **M-03**: Add orchestrator interface definitions to `architecture.md` §2.4
7. **M-04**: Add clarifying note on eval dimension vs self-eval dimension relationship
8. **M-05**: Add `sandbox.allow_network` config flag and proxy-based blocking
9. **M-06**: Clarify NFR-03 entity throughput definition
10. **M-07**: Replace scipy dependency with pure-Python z-score approximation

### Should Acknowledge (Minor)
11. **m-01** through **m-08**: Fix during implementation; low risk of blocking.

---

*Reviewed all 11 design documents in `docs/design/` against the execution plan's 5 goals and 7 review dimensions.*
*Last modified: 2026-04-11*
