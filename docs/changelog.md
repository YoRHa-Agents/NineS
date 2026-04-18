# Changelog

All notable changes to NineS are documented here. This project follows [Semantic Versioning](https://semver.org/).

---

## v2.2.0 — 2026-04-18 (Paradigm Extension)

**Theme:** Self-iteration combined with EvoBench paradigm extension; data-quality + resilience foundations for downstream differentiation. Closes 4 of 11 baseline gaps at the source (§4.1, §4.2, §4.5, §4.6) and bounds 2 more (§4.7, §4.11) at the runner level.

**Status:** Released as v2.2.0 from `feat/v2.2.0-paradigm-extension` after merging the 6 empirically-validated POCs (C02, C03, C04, C05, C06 executor primitive, C09) plus their release follow-ups (N1 CLI JSON exposure, N2 subprocess timeout audit, N3 graph builder canonicalization, C05 collector refactor, C02 metadata, lint+typecheck cleanup). The 6 analytically-validated candidates (C01 EvaluationContext, C07 quality-gate FSM, C08 weighted MetricRegistry, C10 consistency auditor, C11 mechanism diversification, C12 breakdown reporter) remain on the accept list for Wave 2-4 release pending empirical proof — per the user's strict 'tested-benefit-only' rollout rule.

> Backward-compatible: legacy v3.0.0 reports continue to parse via `formula_version=1` defaults; legacy `AI-NNNN` finding-IDs keep parsing alongside new `AI-{fp}-NNNN`. The first observable schema break (`EvaluationContext` Protocol) is deferred to Wave 2 / v2.3.0-rc1.

### ⚠️ Breaking Output Shape Changes (read this before upgrading from v3.0.0)

The values are still numbers, but **what those numbers mean has changed**. A naive parser that compares against v3.0.0 constants will silently get wrong answers. Gate on the new schema-version fields below.

| Field | v3.0.0 (before) | v2.2.0-rc1 (now) | How to detect the new format |
|---|---|---|---|
| `agent_impact.context_economics.break_even_interactions` | constant `2` (regardless of overhead/savings) | derived `ceil(overhead_tokens / max(per_interaction_savings_tokens, 1))` — observed `{6, 7, 8}` on the §3.1 caveman / DevolaFlow / UA fixture triplet | `agent_impact.context_economics.formula_version == 2` |
| `agent_impact.context_economics.economics_score` | absent | **NEW** — float in `[0.0, 1.0]`; replaces ad-hoc consumption of `savings_ratio` for downstream ROI rankings. Computed as `clamp(saved × retention × diversity / overhead, 0, 1)` | `economics_score in payload` *and* `formula_version == 2` |
| `agent_impact.context_economics.formula_version` | absent (implicitly v1) | **NEW** — integer; value `2`. `from_dict` defaults to `1` for legacy reports so v1 round-trips silently | gate every consumer on `formula_version == 2` |
| `report_metadata` (top-level of `analyze --format json`) | absent | **NEW** — `{id_namespace_version: 2, analyzer_schema_version: 1, nines_version: <str>}` so dashboards can detect the new format without sniffing finding IDs | check `payload["report_metadata"]["id_namespace_version"] == 2` |
| Finding IDs (`AI-NNNN` family in `agent_impact.py`) | unscoped — `AI-0000` collided across every project (3 collisions / 271 IDs in §3.1) | namespaced — `AI-{8-hex-fp}-NNNN`, e.g. `AI-45961152-0000` for caveman | the same `report_metadata.id_namespace_version` flag (also see `parse_finding_id` for both forms) |

**Operator action — within 30 seconds of upgrading:**

1. Search your dashboards/integrations for `break_even_interactions == 2`. If you find any, the legacy comparison is now **always false** for non-trivial repos; switch to gating on `formula_version`.
2. If you dedupe findings on raw `id` strings, switch to `(project_id, prefix, idx)` tuples via `nines.core.identity.parse_finding_id`. Otherwise three different repos' first agent-impact rollups will dedupe to one.
3. Have downstream tooling read `report_metadata.id_namespace_version` once at parse time and branch accordingly. Reports lacking the field are pre-v2.2.0; treat them as v1.

The legacy parsers themselves still run — `from_dict` defaults `formula_version=1`, `parse_finding_id` accepts both `AI-0007` and `AI-deadbeef-0007`. The break is **interpretive** (a v3.0.0 reader silently gets a different number for `break_even_interactions`), not structural (no fields are removed).

### Added (Wave 1 POCs)

- **C02 — Project-scoped finding-ID namespacing** (`src/nines/core/identity.py`, ~225 lines). Exports `project_fingerprint(project_root) -> str` (8-char `blake2s` of resolved path + optional git remote), `format_finding_id(prefix, idx, project_id)`, and a backward-compat `parse_finding_id` that handles both legacy `AI-0007` and namespaced `AI-12345678-0007`. Six `f"AI-{idx:04d}"` sites in `agent_impact.py` now use the namespaced format. Empirical proof: 271 / 271 unique IDs across the §3.1 fixture triplet (was 265 / 271 with 6 collisions); 3 distinct fingerprints (`45961152`, `05645815`, `8c1e11cc`). 23 unit tests including a 2 000-path collision-rate stress test. See [`references/project-identity.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/project-identity.md).
- **C03 — Graph node↔edge ID canonicalizer + verifier-as-gate** (`src/nines/analyzer/graph_canonicalizer.py`, ~185 lines). Exports `canonicalize_id(raw, *, project_root)` that resolves `file:` / `function:` IDs to POSIX-relative form against the project root. `GraphVerifier.verify` now accepts an optional `project_root` from the pipeline and canonicalises both endpoints before set-membership comparison. Empirical proof: `verification.passed = True / True / True` on caveman / DevolaFlow / UA (was F/F/F); critical referential-integrity issues 0 / 0 / 0 (was 49 / 803 / 40); `layer_coverage_pct = 0.0` when `graph.layers == []` (was the 100.0 tautology). 17 tests including 2 verifier-integration cases. See [`references/cross-artifact-audit.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/cross-artifact-audit.md).
- **C04 — Per-evaluator wall-clock budget** (`src/nines/core/budget.py`, ~184 lines, **PARTIAL**). Exports `TimeBudget(soft_seconds, hard_seconds)` and the `evaluator_budget(name, budget)` context manager that runs work on a `threading.Thread(daemon=True)` and raises `EvaluatorBudgetExceeded` after `hard_seconds`. `SelfEvalRunner.run_all` wraps each evaluator; on budget breach it appends a zero-score `DimensionScore` with `metadata["status"] = "timeout"` and records the dim name in `report.timeouts`. CLI gains `--evaluator-timeout SECONDS` (default 60). Empirical proof: caveman `--src-dir … --capability-only --evaluator-timeout 30` completes in **33.3 s** (was killed at >195 s — 5.9× speed-up); 20 / 20 dims populated; `report.timeouts = ['agent_analysis_quality']` (at the dataclass — N1 risk: not yet in CLI JSON). 5 unit tests. See [`references/resilience-budgets.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/resilience-budgets.md).
- **C05 — `with_retry` + `CostBudget`** (`src/nines/core/retry.py` ~153 lines + `src/nines/core/cost_budget.py` ~117 lines). Exports `RetryPolicy(attempts, base_backoff_s, max_backoff_s, retry_on)`, `with_retry(fn, policy)`, `TransientError`, `CostBudget(token_limit, dollar_limit, time_limit_s)`, `CostExceeded`. `EvalRunner.__init__` accepts `retry_policy` and `cost_budget`; `run` catches `CostExceeded`, appends a partial-error entry, and breaks the outer loop. `eval_max_retries` (formerly dead code per gap-analysis §1) now drives the runner. Empirical proof: 5×50-token tasks vs `CostBudget(token_limit=100)` → 2 success + 1 `cost_budget_exceeded` partial-error + 2 not-executed; flaky-then-OK executor recovers in 3 invocations. 12 unit tests. See [`references/resilience-budgets.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/resilience-budgets.md).
- **C06 — `DeterministicMockExecutor` (executor primitive only)** (`src/nines/eval/mock_executor.py`, ~99 lines, **PARTIAL**). Exports `DeterministicMockExecutor` callable with `seed`, `fixed_outputs`, `base_token_count`; `__call__` hashes `(task.id, task.input_data)` via `blake2s(payload, digest_size=16)` and returns a deterministic synthetic `ExecutionResult`. Empirical proof: 5 runs of a 10-task fixture byte-identical at ≈ 0.02 ms / call; 10 distinct task IDs → 10 distinct outputs; seed isolation (`alpha` vs `beta` produce different stable streams). 6 unit tests. **Wave 2 must complete the harness:** `MockEvaluator(DimensionEvaluator)`, `tests/data/golden/self_eval_fixtures/*.json`, `tests/iteration/test_self_eval_golden.py` with hang-detection (joint with C04) + silent-fallback regression detector. Block C08 + C12 on full-C06.
- **C09 — Derived `context_economics`** (`src/nines/analyzer/agent_impact.py` lines 91-181 + 451-553, ~80 lines of formula rewrite + 30 lines of dataclass fields). Replaces constant `break_even_interactions = 2` with `ceil(overhead_tokens / max(per_interaction_savings_tokens, 1))`; adds `economics_score = clamp(saved × retention × diversity / overhead, 0, 1)`. New fields: `per_interaction_savings_tokens`, `expected_retention_rate` (default 0.85), `mechanism_diversity_factor` (`1.0 + 0.1 × (distinct_categories - 1)`), `economics_score`, `formula_version: int = 2`. Backward-compat parser: `from_dict` defaults `formula_version=1` for legacy reports. Empirical proof: caveman / DevolaFlow / UA `break_even = 6 / 7 / 8` (was constant 2 — matches design's predicted {6, 7, 8} exactly); `economics_score = 0.1992 / 0.1879 / 0.1556` (spread 0.0436 > 0.03 target). 9 unit tests including v1 round-trip. See [`references/derived-metrics.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/derived-metrics.md).

### Improved

- **Test suite: 1189 → 1261 (+72 tests, +6.0 %)** with zero regressions; full-suite green at every commit (`f885040` … `5247a1a`).
- **`eval_max_retries` config knob resurrected.** Was dead code in v3.0.0 (per `01_evobench_gap_analysis.md` §1); now drives `RetryPolicy(attempts=cfg.eval_max_retries)` via the eval CLI.
- **`SelfEvalReport.timeouts: list[str]`** field added; populated when any evaluator breaches its `TimeBudget`. (CLI JSON exposure pending — N1 risk in Wave 1 follow-up.)
- **`ContextEconomics`** schema-evolves from `formula_version=1` to `formula_version=2`; legacy parsers see v1 semantics, new parsers see derived `break_even` + `economics_score`.
- **References folder** grows by 4 new tier-2 reference docs: [`cross-artifact-audit.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/cross-artifact-audit.md), [`resilience-budgets.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/resilience-budgets.md), [`project-identity.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/project-identity.md), [`derived-metrics.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/derived-metrics.md). [`references/index.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/index.md), [`iteration-protocol.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/iteration-protocol.md), and [`evaluation-framework.md`](https://github.com/.../tree/feat/v2.2.0-paradigm-extension/references/evaluation-framework.md) bumped to v1.1.0 with cross-references to the new docs.

### Known Gaps (Wave 1 follow-up — release-blocker for v2.2.0)

- **N1 (Med):** `_build_json_output` in `cli/commands/self_eval.py` (lines 189-217) silently drops `report.timeouts`. Operators running `nines self-eval --format json` cannot detect partial runs. Fix: refactor to forward `report.to_dict()` rather than constructing a parallel payload.
- **N2 (Low–Med):** `evaluator_budget`'s daemon-thread cancellation cannot kill `subprocess.run` hangs; the four `Live*` evaluators that shell out still have hard-coded subprocess timeouts. Wire `subprocess.run(timeout=min(dim_budget.hard_seconds, current_default))` in Wave 1; full child-process executor deferred to v2.3.
- **N3 (Med):** C03 patched the verifier consumer but not `graph_decomposer.py` (the producer); future graph consumers can re-introduce §4.1 mismatch. Wave 1 follow-up: builder-side fix + add `_check_id_canonicalisation` regression detector.
- **N4 (Med-High):** C06 shipped only the executor primitive (~10 % of the design); the golden harness is Wave 2.
- **N5 (Low):** lint debt grew silently — `ruff check src/nines` 6 → 15 errors (+9 stylistic SIM108 / TC005). Address in a single cleanup commit before v2.2.0 ships; add a pre-commit hook in Wave 2.
- **N6 (Low–Med):** `make typecheck` not run in S04. Run before v2.2.0 release; treat any new mypy errors as merge blockers.

### Deferred to Wave 2 (v2.2.x or v2.3.0-rc1)

- **C01 — Project-aware `EvaluationContext`.** The foundation gap that closes §4.8 + §4.9. POC plan: 3 evaluators first; full migration of all ~12 evaluators with `src_dir` defaults. Reuses `nines.core.identity.project_fingerprint` (shipped in C02) — see `02_analytical_validation.md` §C01 recommendation.
- **C06 (full harness).** Build `MockEvaluator(DimensionEvaluator)`, fixtures at `tests/data/golden/self_eval_fixtures/*.json`, `tests/iteration/test_self_eval_golden.py` including the joint hang-detection test and silent-fallback regression detector. Unblocks C08 + C12.
- **C07 — Quality-gate state machine.** All three deps (C03, C04, C09) now in tree. Reframe as "institutionalise Wave 1 wins so future PRs can't re-introduce the bugs". Ship in `gates_advisory_mode=True` for one minor.
- **C10 — Cross-artifact consistency auditor.** Revised POC plan (since §4.1 / §4.5 are fixed at the source): inject synthetic regression and assert auditor flags it. Add `audit_schema_versioning` for C09 / future C08 migrations. Soft gate first; hard gate after one minor.

### Deferred to Wave 3 (v2.3.0)

- **C08 — Weighted `MetricRegistry`.** Closes §4.10. Gated on C01 (cross-project signal) + full-C06 (regression pinning) + N1 fix (CLI JSON exposure of new fields).
- **C11a — Mechanism-detection diversification (rule-based).** Closes §4.3 / §4.4 with 4 new ContextOS-derived categories. Will automatically lift `economics_score` ≈ +0.05 absolute via C09's already-wired `mechanism_diversity_factor` — pre-document.

### Deferred to Wave 4 (v2.4.0+)

- **C12 — AgentBoard-style breakdown reporter.** Closes §4.10 fully via per-dim sub-skill panels. Gated on C01 + C08 + full-C06.
- **C11b — Opt-in LLM-judge fallback.** `provider="none"` default; `NINES_ALLOW_EXTERNAL_LLM=1` env-var gate; CI-skipped via `@pytest.mark.live_llm`. Separate security/cost review required.

---

## v3.0.0 — 2026-04-14

**Theme:** Knowledge Graph Analysis Engine — Integrates [Understand-Anything](https://github.com/Lum1104/Understand-Anything) repo decomposition and analysis capabilities into a complete analyze → decompose → verify → summarize pipeline.

> Breaking changes: New `graph` decomposition strategy, self-eval expanded to 24 dimensions, analysis pipeline supports multi-language scanning and knowledge graph construction.

### Added
- **Multi-language project scanner** (`scanner.py`) — Discovers 30+ programming languages, detects file categories (code/config/docs/infra/data/script/markup), identifies frameworks from manifests
- **Cross-language import graph builder** (`import_graph.py`) — AST-based (Python) and regex-based (JS/TS/Go/Rust) project-internal dependency graph construction
- **Knowledge graph data models** (`graph_models.py`) — `GraphNode`, `GraphEdge`, `ArchitectureLayer`, `KnowledgeGraph`, `VerificationResult`, `AnalysisSummary` with typed constants and full serialization
- **Graph decomposition strategy** (`graph_decomposer.py`) — New `--strategy graph` builds a complete knowledge graph with typed nodes, edges, and architecture layers
- **Graph verifier** (`graph_verifier.py`) — 7 verification checks: referential integrity, duplicate edges, orphan nodes, layer coverage, node/edge type validity, self-loops
- **Analysis summarizer** (`summarizer.py`) — Produces structured summaries with fan-in/fan-out rankings, entry point detection, and agent impact text
- **4 new self-eval dimensions** (D21-D24): graph decomposition coverage, verification pass rate, layer assignment quality, summary completeness
- **Pipeline graph strategy integration** — `nines analyze --strategy graph` auto-executes: scan → import graph → knowledge graph → verify → summarize
- **CLI graph output** — Text report includes knowledge graph statistics (scanned files, languages, frameworks, import edges, graph nodes/edges/layers, verification results)
- 67 new tests (total: 1189)

### Design Decisions
- **Deterministic-first, LLM-assist-second** — Following Understand-Anything's two-phase design (scripts first → LLM enrichment), all core logic is AST/regex/path-heuristic based with no LLM dependency
- **Typed graph contract** — 11 node types, 10 edge types, 7 file categories constrained by `frozenset` constants; verifier enforces schema compliance
- **Path + fan-in hybrid layer assignment** — Combines path-pattern matching with fan-in ranking promotion; high-dependency nodes auto-promoted to core layer
- **Everything serves Agent capability verification** — D21-D24 directly measure graph decomposition and verification quality, driving iterative improvement

### Improved
- **Self-eval expanded from 20 to 24 dimensions** — D21-D24 cover graph decomposition, verification, layer assignment, summary
- **Pipeline constructor expanded** — `AnalysisPipeline.__init__` accepts `scanner`, `graph_decomposer`, `graph_verifier`, `summarizer` injection
- **`analyzer/__init__.py` public API expanded** — Exports all new module public classes
- **Full test suite**: 1189 tests passing, 0 lint errors

---

## v2.1.0 — 2026-04-14

**Theme:** Self-update iteration — analysis quality improvements, strategy routing, reference system, driven by DevolaFlow self-update workflow analyzing [Understand-Anything](https://github.com/Lum1104/Understand-Anything).

### Added
- **Decomposition strategy routing** — `--strategy concern|layer|functional` now correctly dispatches to the corresponding `Decomposer` method (was hardcoded to `functional`)
- **Strategy and depth in metrics** — `strategy` and `depth` recorded in analysis result metrics for traceability
- **Reference system** — 6 DevolaFlow-style reference documents in `references/` with YAML frontmatter (analysis-pipeline, agent-impact-analysis, key-point-extraction, evaluation-framework, iteration-protocol, index)
- **SKILL.md Reference Navigation Guide** — quick-reference table for selective context loading
- **Semantic key-point deduplication** — second-pass dedup merging points with >60% word overlap within same category
- 27 new tests (1093 total)

### Fixed
- **Finding ID collision** — IDs now include a deterministic file-path hash prefix (`CC-{hash}-{idx}`), eliminating duplicates across multi-file analysis (was: 10 duplicates on Understand-Anything repo)
- **Beneficial mechanism impact** — `behavioral_instruction`, `safety`, and `persistence` mechanisms correctly classified as `"positive"` impact (was: `"negative"` due to token-count-only heuristic)
- **Impact magnitude saturation** — switched from linear to logarithmic scale (`log1p`), producing differentiated magnitudes (was: all 1.0 for >5K tokens; now: 0.817–0.862 range)
- **arxiv collector** — `_DEFAULT_BASE_URL` upgraded from `http://` to `https://`

### Improved
- **Analysis of Understand-Anything**: 0 duplicate finding IDs, 5 differentiated mechanism magnitudes, 3 correctly-positive beneficial mechanisms
- **Full test suite**: 1093 tests passing, 0 lint errors

---

## v2.0.0 — 2026-04-13

**Theme:** Agent-facing repository analysis realignment — NineS is now a purpose-built tool for analyzing how repositories improve AI Agent effectiveness.

> Breaking: analysis pipeline defaults changed, self-eval expanded to 20 dimensions, benchmark executor replaced.

### Added
- **AgentAnalysisQualityEvaluator (D20)** — measures NineS's ability to detect artifacts, mechanisms, economics, findings, and key points on real repos
- **SourceFreshnessEvaluator (D07)** — measures data staleness within configurable window (default 30 days)
- **ChangeDetectionEvaluator (D08)** — verifies DataStore update detection capability
- **Real benchmark executor** — dimension-aware comparison scoring replaces passthrough executor (compression, context, behavioral, semantic, cross-platform, engineering)
- **`ingest_all()` method** in AnalysisPipeline — discovers non-Python agent artifacts (.yaml, .md, .json, .toml, .cfg, .ini, .rules)
- **`--tasks-path` option** for `nines benchmark` — load custom TOML task definitions
- **`--project-root`/`--src-dir`/`--test-dir`** options for `nines iterate` with live evaluators
- **Configurable `cov_package`** and **coverage file parsing** (coverage.xml/json) in LiveCodeCoverageEvaluator
- **pytest --collect-only** for accurate test counting with AST-walk fallback
- 13 new tests (1069 total)

### Changed
- **[BREAKING] `nines analyze` defaults to agent-impact analysis** — `--agent-impact/--no-agent-impact` flag pair, default enabled. Use `--no-agent-impact` to disable.
- **[BREAKING] `nines analyze` defaults to key-point extraction** — `--keypoints/--no-keypoints` flag pair, default enabled
- **[BREAKING] Benchmark executor** produces differentiated scores (mean 0.4) instead of passthrough 1.0
- **Self-eval expanded from 17 to 20 dimensions** (D07, D08, D20)
- **Context Economics enriched** with mechanism-derived tokens, expanded artifact patterns (pyproject.toml, copilot, aider), minimum fallback estimate
- **KeyPointExtractor** filters generic metric noise — 23→10 key points, engineering observations capped at 5 (critical/error only)
- **`nines iterate`** registers all 20 capability dimensions (was 0) plus 5 hygiene dimensions
- **README** rewritten: Agent-facing repo analysis mission, all CLI examples fixed
- **SKILL.md** rewritten: core workflow description (analyze→benchmark→self-eval→iterate)
- D07/D08 numbering gap filled in dimension labels

### Improved
- **Self-eval overall: 0.9727** — 20 dimensions, D07=50% (real freshness signal), D20=100%
- **Benchmark mean: 0.4** — real differentiation across compression/context/behavioral dimensions
- **Context Economics**: overhead=3575 tokens, savings=15%, breakeven=7 interactions (was empty `{}`)
- **Agent-impact key points**: 9/10 are agent-relevant (was 9/23)

---

## v1.1.0 — 2026-04-13

**Theme:** External project support and DevolaFlow integration feedback fixes.

> Based on integration testing feedback from DevolaFlow v4.3.1, this release fixes 4 core issues when NineS evaluates external projects, transforming NineS from "can only evaluate itself" to a general-purpose project quality scanner.

### Added
- **Configurable coverage package** in `LiveCodeCoverageEvaluator` — new `cov_package` parameter replaces hardcoded `--cov=nines`, enabling correct coverage measurement for external projects (e.g. DevolaFlow)
- **Coverage file parsing** — new `coverage_file` parameter supports reading pre-existing `coverage.xml` (Cobertura format) and `coverage.json` files without re-running pytest
- **`LiveTestCountEvaluator` prefers pytest collection** — uses `pytest --collect-only -q` for accurate counting (handles parameterized tests, class methods, etc.), with AST-walk fallback
- **`nines iterate` project context flags** — new `--project-root`, `--src-dir`, `--test-dir` options with auto-detection of source and test directories
- **`nines iterate` live evaluators** — uses 5 live evaluators (coverage, test count, modules, docstring coverage, lint) when `--project-root` is specified, replacing fixed-zero stub evaluators
- **`nines benchmark --tasks-path`** — new custom TOML task directory option, skips auto-generated generic tasks and loads user-defined project-specific benchmark tasks directly
- 24 new tests (self_eval: 6, iterate_cmd: 14, benchmark_cmd: 4), bringing total to 1052

### Changed
- `LiveCodeCoverageEvaluator` metadata includes `source` field (`"file"` or `"pytest"`) indicating data origin
- `LiveTestCountEvaluator` metadata includes `method` field (`"pytest-collect"` or `"ast-walk"`) indicating counting method
- `nines iterate` warns when no `--project-root` is given and uses non-zero stub values (avoids immediate convergence at 0.0)
- Fixed potential `UnboundLocalError` on `conv_result` in iterate command

### Improved
- **Self-eval score: 0.9928** — capability dimensions 17/17 at 100%, hygiene 97.6% (coverage 90%, tests 1052, modules 65, docstrings 100%, lint 98%)
- NineS now usable as a general-purpose project quality scanner, no longer limited to evaluating itself
- In DevolaFlow integration scenario, `nines iterate --project-root .` correctly produces a 0.976 composite score

---

## v1.0.0 — 2026-04-13

**Theme:** Multi-runtime skill integration, 19-dimension capability evaluation, and production readiness.

### Added
- **Codex adapter** — install NineS as a Codex skill at `.codex/skills/nines/` with SKILL.md + per-command workflows
- **GitHub Copilot adapter** — install NineS as Copilot instructions at `.github/copilot-instructions.md`
- **One-click install script** (`scripts/install.sh`) — `curl | bash` style installer with Python detection, uv/pip fallback, and automatic skill file generation
- **`--uninstall` CLI flag** for `nines install` — clean removal of skill files from any target runtime
- **DevolaFlow integration feedback** — proposed NineS as quality gate scorer, research tool, and advisor plugin for DevolaFlow v4.2.0
- 12 new tests for Codex adapter, Copilot adapter, installer integration, and uninstall flow
- **19-dimension capability evaluation framework** — all design dimensions (D01–D19) now have live evaluators
- **V1 Evaluation evaluators** (D01 ScoringAccuracy, D03 Reliability, D05 ScorerAgreement) with 20-task golden test set
- **V2 Collection evaluators** (D06 SourceCoverage, D09 DataCompleteness, D10 CollectionThroughput)
- **V3 Analysis evaluators** (D11–D15) measuring decomposition, abstraction, code review, index recall, structure recognition
- **System evaluators** (D16 PipelineLatency, D17 SandboxIsolation, D18 ConvergenceRate, D19 CrossVertexSynergy)
- Golden test set at `data/golden_test_set/` with 20 calibrated TOML tasks
- Self-eval CLI restructured: 70% capability / 30% hygiene weighting, grouped output by V1/V2/V3/System
- `--capability-only` and `--golden-dir` CLI options for focused evaluation (total: 1005 tests)

### Changed
- `nines install --target` now accepts 5 targets: `cursor`, `claude`, `codex`, `copilot`, `all`
- Installer `ADAPTERS` registry expanded from 2 to 4 runtimes
- Skill `__init__.py` public API includes `CopilotAdapter` alongside existing adapters

### Improved
- **Self-eval score: 0.9940** — capability dimensions 17/17 at 100%, hygiene 98%
  - V1 Evaluation: D01–D05 all 100% (scoring accuracy, coverage, reliability, report quality, scorer agreement)
  - V2 Collection: D06/D09/D10 all 100% (source coverage, data completeness, throughput)
  - V3 Analysis: D11–D15 all 100% (decomposition, abstraction, code review, index recall, structure recognition)
  - System: D16–D19 all 100% (pipeline latency, sandbox isolation, convergence, cross-vertex synergy)
- Documentation updated for all 4 runtime targets (EN + ZH)
- Agent skill setup guide, quick start, CLI reference, installation guide, and design spec all reflect v1.0.0-pre capabilities
- README updated with one-click install and 4-runtime support

---

## v0.6.0 — 2026-04-13

**Theme:** DevolaFlow analysis showcase and EvoBench evaluation integration.

### Added
- DevolaFlow repository deep analysis showcase — 15 key points, 30 benchmark tasks, multi-round evaluation with EvoBench dimension mapping
- EvoBench integration insights section documenting 32 evaluation dimensions (T1–T8, M1–M8, W1–W8, TT1–TT8) alignment with agent-facing analysis
- NineS capabilities assessment and v0.6.0 improvement roadmap in showcase reports
- Chinese translation for DevolaFlow analysis showcase

### Changed
- Showcase index updated to feature DevolaFlow as second case study alongside Caveman
- Analysis methodology extended to meta-framework evaluation (orchestration rules, not just tools)

### Improved
- Documentation of NineS evaluation pipeline capabilities and identified gaps
- Cross-repository analysis patterns established (simple tool → meta-framework)

---

## v0.5.0 — 2026-04-12

**Theme:** Executable evaluation framework and self-driven improvement.

### Added
- Key point extraction module (`KeyPointExtractor`) — decomposes Agent impact reports into categorized, prioritized key points with validation approaches
- Benchmark generation module (`BenchmarkGenerator`) — generates `TaskDefinition` benchmark suites from key points with per-category task templates
- Multi-round evaluation runner (`MultiRoundRunner`) — sandboxed multi-round evaluation with convergence detection and reliability metrics (pass@k, consistency)
- Key point → conclusion mapping module (`MappingTableGenerator`) — maps key points to effectiveness conclusions with confidence scores and recommendations
- Five live self-evaluation evaluators: `LiveCodeCoverageEvaluator`, `LiveTestCountEvaluator`, `LiveModuleCountEvaluator`, `DocstringCoverageEvaluator`, `LintCleanlinessEvaluator`
- New CLI command `nines benchmark` — full analysis→benchmark→evaluate→mapping workflow
- CLI options `--agent-impact` and `--keypoints` for `nines analyze`
- CLI options `--project-root`, `--src-dir`, `--test-dir` for `nines self-eval`
- 18 new integration tests for benchmark workflow and enhanced analysis pipeline
- `BenchmarkSuite` with TOML directory export (`to_toml_dir()`)
- `MappingTable` with markdown and JSON export
- `MultiRoundReport` with per-task summary statistics

### Changed
- Caveman showcase completely rewritten to demonstrate v0.5.0 executable evaluation methodology — key points, benchmarks, multi-round results, mapping table, lessons learnt
- `AnalysisPipeline.run()` now accepts `agent_impact` and `keypoints` keyword arguments
- Self-evaluation CLI wires live evaluators instead of placeholder zeros
- Orchestrator `Pipeline` methods now wire real component calls (eval, analyze, benchmark)
- `nines analyze` CLI now supports `--depth` option

### Improved
- Self-evaluation produces real measurements from project introspection (coverage, test counts, docstrings, lint)
- Analysis pipeline integrates `AgentImpactAnalyzer` and `KeyPointExtractor` into the main flow
- 914+ tests with comprehensive coverage across all new modules

---

## v0.4.0 — 2026-04-12

**Theme:** Agent-oriented analysis and AI repository evaluation.

### Added
- Agent impact analysis module (`AgentImpactAnalyzer`) for evaluating how repositories influence AI Agent effectiveness
- New data models: `AgentMechanism`, `ContextEconomics`, `AgentImpactReport` with full serialization
- Research synthesis document on analyzing AI-oriented repositories
- Agent artifact detection covering 14+ patterns across 7 AI agent platforms
- Mechanism decomposition with 5 detection categories: behavioral instruction, context compression, safety, distribution, persistence
- Context economics estimation with token overhead, savings ratio, and break-even analysis
- 45 new tests for the Agent impact analyzer with 100% pass rate

### Changed
- Caveman showcase completely rewritten with Agent-oriented focus — mechanism decomposition, context economics, semantic preservation, behavioral impact analysis
- Showcase index updated to reflect Agent-oriented analysis capabilities
- Analysis module exports expanded with Agent impact types

### Improved
- V3 Analysis now supports dual-track mode: traditional code analysis + Agent impact analysis
- Documentation coverage for AI repository evaluation methodology

---

## v0.3.0 — 2026-04-12

**Theme:** Documentation completeness and international polish.

### Added
- Development plan documentation with MAPIM-aligned engineering methodology
- Caveman repository analysis showcase demonstrating V3 capabilities
- Sample task files for quick evaluation demos

### Fixed
- Chinese site i18n issues: language switcher, nav translations, and UI locale
- Deploy workflow updated with i18n plugin dependency

### Improved
- Navigation restructured to surface design documents, research reports, and internal references
- Emoji icon rendering for Material card grids on homepage

---

## v0.2.0 — 2026-04

**Theme:** Visual identity and internationalization.

### Added
- NieR: Automata custom theme (`nier.css`) — warm cream/parchment light mode, deep charcoal dark mode
- Full i18n support with `mkdocs-static-i18n` — English (default) and Chinese
- Chinese translations for all user-facing documentation pages
- Light/dark mode toggle with NieR-inspired color palettes
- HUD-style geometric accents, custom typography (JetBrains Mono, Noto Sans/SC)
- MkDocs Material theme with navigation tabs, search, code copy

### Changed
- Documentation site deployed to GitHub Pages via `deploy-pages.yml`
- Version macro system (`{{ nines_version }}`) for automatic version tracking

---

## v0.1.0 — 2026-03

**Theme:** MVP — Full implementation of three-vertex architecture.

### Added
- **V1 Evaluation & Benchmarking**
    - TOML-based task definitions with structured input/expected schemas
    - Multiple scorer types: Exact, Fuzzy, Rubric, Composite
    - `EvalRunner` with configurable execution pipeline
    - Matrix evaluation across N configurable axes
    - Statistical reliability metrics: pass@k, Pass^k, Pass³
    - Sandboxed execution with three-layer isolation (process + venv + tmpdir)
    - Pollution detection across 4 dimensions (env vars, files, dirs, sys.path)
    - Markdown and JSON report generation
- **V2 Information Collection**
    - GitHub REST and GraphQL source collectors
    - arXiv search and metadata collector
    - SQLite storage with FTS5 full-text search
    - Token-bucket rate limiting per source
    - Incremental collection with snapshot-based change detection
- **V3 Code Analysis**
    - AST-based code parsing and element extraction
    - Cyclomatic complexity calculation
    - Cross-file dependency graph construction
    - Multi-strategy decomposition (functional, concern, layer)
    - Knowledge unit indexing and search
    - Architectural pattern detection
- **Self-Iteration (MAPIM)**
    - 19 self-evaluation dimensions across 4 categories
    - Gap detection with severity classification
    - Improvement planning with ≤3 actions per iteration
    - 4-method convergence detection (sliding variance, relative improvement, Mann-Kendall, CUSUM)
    - Composite scoring with configurable weights
- **Agent Skill Support**
    - `nines install` command for Cursor and Claude Code integration
    - Skill templates for both platforms
- **CLI**
    - `nines eval` — Run evaluations on TOML task files
    - `nines collect` — Collect from GitHub and arXiv
    - `nines analyze` — Analyze codebases
    - `nines self-eval` — Run self-evaluation
    - `nines iterate` — Run MAPIM self-improvement loop
- **Documentation**
    - MkDocs site with user guide, architecture docs, API reference
    - Quick start guide with step-by-step examples
    - Comprehensive design philosophy page
    - 19-dimension evaluation criteria reference
    - Development plan and roadmap
    - Contributing guide with module ownership matrix
- **Infrastructure**
    - Python 3.12+ with `uv` package management
    - GitHub Actions: version sync check, documentation deployment
    - Deterministic execution with master seed propagation
    - Protocol-based extensibility (PEP 544)
    - Structured logging with `structlog`
    - Progressive configuration depth (CLI → project → user → defaults)
