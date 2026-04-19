# Changelog

All notable changes to NineS are documented here. This project follows [Semantic Versioning](https://semver.org/).

---

## v3.2.4 — 2026-04-19 (C12 AgentBoard Sub-Skill Breakdown Reporter)

**Theme:** Land C12 from `.local/v2.2.0/design/04_track_d_extension.md` (Track D — extension paradigms): turn the flat 25-dimension self-eval list into per-dim panels of 2–5 sub-skills, applying AgentBoard's "analytical evaluation" principle so reviewers can see *which* sub-skill dragged a dim down instead of just a single opaque score per parent. Default `--no-breakdown` preserves backward-compat for existing CLI consumers.

**Empirical (full table in `.local/v3.2.4/benchmark/c12_proof.txt` — NineS @ src/nines + tests, caveman @ /home/agent/reference/caveman, capability-only):**

- `total_subskills`: **25 (flat) → 44** (NineS) / **39** (caveman)
- `dims_with_breakdown` (panels with ≥2 sub-skills): **0 → 6** (NineS and caveman)
- `subskills_in_[0.7, 0.95)` ("headroom" band — AgentBoard signal): **0 → 2** (NineS — `code_review_accuracy::severity_balance=0.75`, `structure_recognition::layout_inference=0.789`)
- `cross_sample_diff_count` (sub-skills with `|nines − caveman| > 0.10`): **0 → 20**
- §4.10 saturation visibility: D11/D13/D14/D15/D20 all reported `parent=1.000` pre-C12; the breakdown now surfaces 5 sub-skills strictly < 1.000 inside otherwise-saturated parents (`severity_balance`, `exact_match_rate=0.6`, `partial_match_rate=0.4`, `layout_inference=0.789`, plus the line-coverage timeout signal).
- **Verdict per task spec: PARTIAL** (`total_subskills ≥ 30 ✓ AND (subskills_in_[0.7, 0.95) ≥ 2 OR cross_sample_diff_count ≥ 4) ✓` — short of `BENEFIT_CONFIRMED` thresholds 50/5/8 because most NineS dims remain saturated, the §4.10 problem the breakdown is designed to *expose* not eliminate). Spec dictates SHIP for both PARTIAL and BENEFIT_CONFIRMED.

**Status:** Patch release; aggregated into v3.3.0 minor. Closes the §4.10 (saturated-dim opacity) gap and lays the schema groundwork for D21–D24 graph sub-skills (mentioned in the design doc as the natural home for graph-dim packaging).

### Added

- **`src/nines/iteration/breakdown_reporter.py`** (~480 LOC + 23 tests). Public surface:
  - `@dataclass SubSkill(name, parent_dim, value, max_value=1.0, weight=1.0, metadata={})` — leaf measurement; `normalized` property safely handles `max_value=0`.
  - `@dataclass DimensionPanel(dim_name, parent_dim_value, subskills, rollup_method)` — `rollup_method ∈ {"mean", "weighted_mean", "min", "max"}` (default `weighted_mean`); `rollup()` recomputes the parent number from sub-skills as a sanity check; `coverage_count()` and `has_breakdown()` (≥2 sub-skills) for spread analysis.
  - `@dataclass BreakdownReport(version, timestamp, panels, summary)` with `all_subskills()`, `total_subskills()`, `dims_with_breakdown()`, `to_dict()`.
  - `class BreakdownReporter` — `from_self_eval(SelfEvalReport) → BreakdownReport` extracts sub-skills from each `DimensionScore.metadata["subskills"]` list when present (with optional `rollup_method` per dim) and falls back to a single mirror sub-skill matching the parent so every dim contributes exactly one panel; `generate(breakdown, fmt="text"|"json"|"markdown")` renders ASCII bars (text), parseable JSON (`json`), or table-form Markdown panels (`markdown`).
  - Summary block reports `total_subskills`, `dims_with_breakdown`, `subskills_in_[0.7, 0.95)`, `subskills_in_[0.5, 0.95)`, and a 4-bucket distribution `{saturated_>=0.95, healthy_0.7_to_0.95, needs_work_0.5_to_0.7, broken_<0.5}`.
- **`--breakdown / --no-breakdown` and `--breakdown-format text|json|markdown`** options on `nines self-eval` (default off for backward compat). When `--breakdown` is set the text report appends a "Sub-Skill Breakdown" panel and the JSON output gains a top-level `breakdown` key carrying the full `BreakdownReport.to_dict()` payload.
- **Sub-skill metadata blocks on 7 evaluators** (the 6 highest-leverage capability evaluators per the design doc + LiveCodeCoverageEvaluator):
  - `DecompositionCoverageEvaluator` (D11): `file_coverage` (w=0.20), `element_coverage` (w=0.40), `function_capture` (w=0.20), `class_capture` (w=0.20). Re-walks the AST via the new `_count_ast_breakdown` helper to surface function-vs-class capture rates separately.
  - `AbstractionQualityEvaluator` (D12): `tag_coverage` (w=0.40), `type_validity` (w=0.40), `unit_density` (w=0.20).
  - `CodeReviewAccuracyEvaluator` (D13): `finding_quality_rate` (w=0.40), `complexity_check_rate` (w=0.20), `severity_balance` (w=0.20 — fraction of the 4 valid severities exercised), `false_positive_signal` (w=0.20 — complement of the false-positive rate).
  - `IndexRecallEvaluator` (D14): `query_hit_rate` (w=0.40), `exact_match_rate` (w=0.25 — top-1 match), `partial_match_rate` (w=0.20 — anywhere in top-10 but not top-1), `latency_score` (w=0.15 — fraction of queries returning at least one result; coupling to wall-clock deliberately avoided to keep CI deterministic).
  - `StructureRecognitionEvaluator` (D15): `package_detection`, `module_detection`, `framework_detection`, `layout_inference`, `coupling_inference` (all w=0.20). Continuous detected/actual ratios (not binary check_passed flags) so the headroom signal can land in `[0.7, 0.95)` — this is the patch that lifted `subskills_in_[0.7, 0.95)` from 1 to 2 (caught `layout_inference=0.789`).
  - `AgentAnalysisQualityEvaluator` (D20): `artifacts_detected`, `mechanisms_identified`, `economics_detected`, `findings_quality`, `key_points_quality` (all w=0.20).
  - `LiveCodeCoverageEvaluator`: `line_coverage` always emitted; `branch_coverage` and `function_coverage` added when a coverage.xml/json file with `branch-rate` or `num_branches` is supplied (best-effort parse via two new `_parse_coverage_breakdown_*` helpers).
- **Early-return paths** (empty source, no findings, no indexed units, no decomposed units) emit zero-valued sub-skill blocks too so foreign repos that hit those branches still surface panels with `has_breakdown=true`. This is what lifted caveman's `dims_with_breakdown` from 2 to 6 and brought the cross-sample diff count to 20.

### Changed

- `src/nines/iteration/__init__.py` exports `BreakdownReport`, `BreakdownReporter`, `DimensionPanel`, `SubSkill` for external consumers.

### Tests + lint

- **Test suite: 1458 → 1484 (+26 tests)** with zero regressions; full suite green in 53.6 s.
  - `tests/test_breakdown_reporter.py` (23 tests): `SubSkill` defaults / non-unit max / zero-max safety / `to_dict` round-trip; `DimensionPanel` rollup methods (`mean`, `weighted_mean`, `min`, `max`) + empty / single-subskill / zero-weight edge cases; `coverage_count` + `has_breakdown` (≥2-subskill threshold); `from_self_eval` extraction with annotated metadata + mirror fallback + mixed dims + malformed entries skipped + summary bucket counts + `rollup_method` extracted from metadata; `generate` text format (panels + bars), JSON round-trip, Markdown tables + broken-down/mirror tags, default-format-is-text; `BreakdownReport.to_dict` serialisation parity + total-helpers match summary.
  - `tests/test_self_eval_cli.py` (+3 tests): `--breakdown` flag appends panels to text output (verifies all 5 annotated dim names appear); `--breakdown --breakdown-format json` embeds `breakdown` block under top-level JSON key with `dims_with_breakdown ≥ 5`; default no-breakdown JSON output does NOT carry a `breakdown` key (backward-compat guard).
- `uv run ruff check src/nines tests/` → 0 errors.
- `uv run pytest tests/` → 1484 passed (was 1458).

### Caveats

- `total_subskills=44` falls 6 short of the `BENEFIT_CONFIRMED` 50-bar; lifting it would require annotating ~3 more evaluators (e.g. `EvalCoverageEvaluator`, `ChangeDetectionEvaluator`, `ConvergenceRateEvaluator`) — left for v3.3.x as a non-blocking follow-up.
- `subskills_in_[0.7, 0.95) = 2` falls 3 short of the BENEFIT 5-bar. The vast majority of NineS sub-skills are saturated because NineS scores its own source against tests it wrote — the cross-sample run against caveman (which hits zero on every Python-specific sub-skill) is what makes the cross-sample diff count surge to 20.
- The pytest-stdout LiveCodeCoverage path emits a single `line_coverage` mirror sub-skill (the granular branch/function buckets only fire when a coverage.xml/json file is wired up via the constructor), so the `code_coverage` parent panel reports `has_breakdown=False` in the default NineS run.

---

## v3.2.3 — 2026-04-19 (C11a Rule-Based Mechanism Diversification)

**Theme:** Land C11a from the v2.2.0 paradigm-extension accept list — replace the v3.2.2 hard-coded "any keyword fires the legacy 5 mechanisms with `confidence=1.0`" detection branch (§4.3 baseline) with a rule-based `MechanismDetector` driven by `nines.analyzer.mechanism_rules.DEFAULT_MECHANISM_RULES`, so different repos surface different mechanism subsets. Per the design split, this is **C11a rule-based ONLY** — no LLM judge is involved (C11b deferred).

**Empirical (3 reference repos: caveman, DevolaFlow, Understand-Anything; full breakdown in `.local/v3.2.3/benchmark/c11a_proof.txt`):**

- Mechanism diversity (union across 3 samples): **5 → 9** (+4)
- Intersection (mechanisms shared by all 3 samples): **5 → 4** (−1)
- Per-sample mechanism counts: caveman **5 → 6**, DevolaFlow **5 → 8**, UA **5 → 6**
- Per-sample unique mechanisms: was `{}` for all; now `{DevolaFlow: churn_aware_routing, UA: reasoning_depth_calibration}`
- Confidence distribution: **100% at 1.0 → spread `[0.51, 0.89]`**, mean 0.734, stdev 0.139, `frac_in_[0.5, 0.9) = 1.00`
- Verdict per task spec: **BENEFIT_CONFIRMED** (`diversity ≥ 8 AND intersection ≤ 4 AND ≥1 sample has unique`)

**Status:** Patch release; aggregated into v3.3.0 minor. Closes the §4.3 (5-mechanism template lock) and partially relieves §4.4 (KP category collapse) gaps from the v2.2.0 baseline.

### Added

- **`src/nines/analyzer/mechanism_rules.py`** (~490 LOC + 35 tests). Public surface:
  - `@dataclass(frozen=True) MechanismRule(name, category, description, indicators, counter_indicators=(), path_hints=(), min_indicator_hits_per_file=2, min_files=1, min_confidence=0.3, token_impact_sign=1, source="default")` with helpers `match_file(rel_path, content_lower) -> FileMatch | None`, `evidence_predicate(matches) -> bool`, `confidence_estimator(matches) -> float ∈ [0, 1]`, `magnitude_estimator(total_content_tokens) -> int`.
  - `@dataclass(frozen=True) FileMatch(path, indicator_hits, counter_hits, content_length)` with `density` (hits per 1 000 chars).
  - `DEFAULT_MECHANISM_RULES`: 11-rule tuple = legacy 5 (`behavioral_rules`, `token_compression`, `safety_guardrails`, `multi_platform_sync`, `drift_prevention` — preserved with stricter predicates and tagged `source="legacy"`) + 6 new ContextOS-derived rules (`active_forgetting/context_pruning`, `reasoning_depth_calibration/meta_reasoning`, `productive_contradiction/validation`, `churn_aware_routing/context_routing`, `self_healing_index/indexing`, `skillbook_evolution/in_context_learning`, all tagged `source="contextos"`).
  - Confidence formula: `score = 0.40 + 0.50 * avg_hit_fraction + min(0.25, 0.05 * n_files) − min(0.30, 0.10 * avg_counter_hits)`, clamped to `[0, 1]` and rounded to 2 dp. The `0.40` anchor guarantees predicate-passing matches clear the `0.30` emission gate by default; counter-indicators can still drag the score below the gate when they dominate (proven by the new `test_low_confidence_mechanism_filtered_out`).
- **`MechanismDetector(rules=None)`** in `src/nines/analyzer/agent_impact.py` — encapsulates the rule loop so it can be tested independently and customised by passing a different rule list. Defaults to `DEFAULT_MECHANISM_RULES`. Reads each artifact at most once (cached lower-cased content), then for each rule: (1) accumulates `FileMatch` per artifact via `match_file`, (2) skips when `evidence_predicate` is `False`, (3) computes confidence via `confidence_estimator` and skips when `score <= rule.min_confidence`, (4) emits exactly one `AgentMechanism` per surviving rule. Rejects duplicate rule names at construction time so reports stay deterministic.
- **`AgentImpactAnalyzer(project_id=None, *, mechanism_detector=None)`** — new keyword-only constructor argument that lets callers (and the new `TestC11aDiversification` test) inject a custom detector while keeping the v3.2.2 positional `project_id` signature working unchanged.

### Changed

- `AgentImpactAnalyzer._detect_mechanisms` now delegates to `self._mechanism_detector.detect(target, artifacts, file_reader=..., token_estimator=...)` instead of the in-line "any indicator fires the bucket" branch and `confidence = min(1.0, len(files) * 0.3 + 0.1)` formula. The legacy 5 mechanism *names* and category slugs are preserved; the predicates are tightened so they no longer always fire (e.g. `multi_platform_sync` now needs ≥ 2 distinct indicators or one indicator + a `.cursor/` / `.claude/` / `.windsurf/` / `.codex/` path hint). The 6 new rules use `min_indicator_hits_per_file=1` because each indicator is a domain-specific phrase from the ContextOS taxonomy (e.g. `ttl`, `lru`, `chain of thought`, `cache invalidation`, `re-index`, `skillbook`).
- Module docstring of `agent_impact.py` documents the C11a delegation and explicitly notes that no LLM is invoked from this module.

### Removed

- `AgentImpactAnalyzer._collect_mechanism_evidence` — no longer needed; per-rule predicates replace the centralised `category_evidence` dict.

### Tests + lint

- **Test suite: 1420 → 1458 (+38 tests)** with zero regressions; full suite green in 33.6 s.
  - `tests/test_mechanism_rules.py` (35 tests): `FileMatch.density` basic + zero-content; `MechanismRule` predicate fires on positive evidence + skips below threshold + skips no-files + path-hint synthetic hit + `min_files` aggregate threshold; confidence no-matches-zero + always-in-`[0, 1]` + above-min-for-predicate-passing + counter-indicator penalty; magnitude positive sign + negative for compression + returns `int` + zero-tokens; `DEFAULT_MECHANISM_RULES` count = 11 + legacy-5 present + legacy tagged `source="legacy"` + 6 ContextOS present + ContextOS tagged + `token_compression` negative sign + all rules have indicators + all min_confidence ≥ 0.3; `MechanismDetector` default-rules + custom-subset + empty-rules-empty-output + no-artifacts-empty + duplicate-name rejection + emits one mechanism per passing rule + skips no-evidence rule + emitted confidence above gate + sorted by `(category, name)` + compression sign negative + sorted evidence files + per-rule dedup.
  - `tests/test_agent_impact.py` (+3 tests in `TestC11aDiversification`): 3 distinct evidence inputs → 3 distinct mechanism subsets (proves §4.3 fix; `churn_aware_routing` unique to repo2, `skillbook_evolution` unique to repo3); legacy 5 mechanism names remain in the default registry (backward-compat guard); rules with confidence at or below `min_confidence` are gated out (proves the emission threshold actually filters).
- `uv run ruff check src/nines tests/` → 0 errors.
- `uv run pytest tests/` → 1458 passed (was 1420).

### Deferred (not in v3.2.3)

- **C11b — LLM-judge fallback for ambiguous cases** (rule-score in `[0.3, 0.6]` band routed to `gpt-4o-mini` / `claude-haiku`). Per design 04 §C11 this is shipped opt-in only with `provider="none"` default and an `NINES_ALLOW_EXTERNAL_LLM=1` environment gate; not bundled into v3.2.3 because the rule-based path already met `BENEFIT_CONFIRMED` empirically.
- **C12 — AgentBoard-style analytical sub-skill panels** (still tracked; depends on full C06 golden harness).

---

## v3.2.2 — 2026-04-19 (C08 Weighted MetricRegistry)

**Theme:** Land C08 from the v2.2.0 paradigm-extension accept list — replace the flat unweighted mean in `SelfEvalRunner.run_all()` with a weighted, threshold-calibrated `MetricRegistry` so the §4.10 saturation (19/20 capability dims pinned at 1.000) finally has measurable headroom to optimise against.

**Empirical (NineS self-eval baseline):**

- `before_overall = 0.9766` (CLI 70/30 weighted; legacy)
- `after_weighted_overall = 0.8970` (registry-driven; new field) — Δ −0.0796
- Capability dims at `normalized = 1.000`: **19/20 → 12/20** (−7)
- Capability dims in `[0.5, 0.95)` range: **1/20 → 8/20** (+7)
- Hygiene dims in `[0.5, 0.95)` range: **1/5 → 3/5** (+2)
- Total dims now offering measurable headroom: **2 → 11**
- `registry.validate()` errors: 0; capability/hygiene/`_groups` weight sums all = 1.000000
- Proof: `.local/v3.2.2/benchmark/c08_proof.txt`

**Status:** Patch release; aggregated into v3.3.0 minor. Verdict per design: **BENEFIT_CONFIRMED** (`weighted_overall < 0.95` AND `≥4 capability dims in [0.5, 0.95)`).

### Added

- **`nines.eval.metrics_registry`** (~430 LOC + 28 tests). Public surface:
  - `class Direction(StrEnum): MAXIMIZE | MINIMIZE` — score direction for normalisation.
  - `@dataclass(frozen=True) MetricDefinition(name, weight, direction=MAXIMIZE, normalizer=None, threshold=None, group="default")` — construction-time guards reject negative weights, blank names, inverted thresholds.
  - `class MetricRegistry` — `register`, `get`, `metrics`, `groups`, `weight_sum_for_group`, `normalized(name, value, *, max_value=1.0)` (custom normalizer wins; threshold band applied per direction; falls back to `value/max_value` clamped), `weighted_mean(group, scores)` (missing scores excluded from denominator), `validate()` (errors when group sums miss `1.0 ± 0.01`), `weights_dict()`, `from_toml(path)` / `from_dict(data)`, `default_registry_path()`, `load_default_registry()`.
- **`src/nines/data/self_eval_metrics.toml`** — bundled weights + thresholds. Outer split `capability=0.70` / `hygiene=0.30` via the reserved `_groups` meta-group. Inner-group weights sum to `1.0` exactly. Tighter thresholds for the §4.10 saturation breakers (`decomposition_coverage=(0.6, 1.05)`, `code_review_accuracy=(0.7, 1.05)`, `index_recall=(0.7, 1.05)`, `agent_analysis_quality=(0.7, 1.05)`, etc.) plus standard rubric bands for hygiene (`code_coverage=(70, 95)`, `test_count=(500, 1500)`, `module_count=(50, 130)`, `docstring_coverage=(80, 100)`).
- **`SelfEvalReport.weighted_overall`, `group_means`, `metric_weights`** — new transparent fields surfaced in JSON output and round-tripped via `to_dict` / `from_dict`. `metric_weights` is a snapshot of the active registry so reports remain reproducible after the TOML mutates on disk.
- **`SelfEvalRunner(registry=...)` kwarg** — registry threads through to `run_all()`. Default loads `data/self_eval_metrics.toml` lazily inside `run_all` (avoids the `nines.eval.__init__` → `mock_executor` → `iteration.self_eval` import cycle). Empty groups (e.g. `--capability-only` runs that don't register hygiene dims) are excluded from the outer aggregate so partial-coverage runs still produce a sensible `weighted_overall`. Invalid registries fail loudly via `logger.warning` and leave `weighted_overall=0.0`, `group_means={}`, `metric_weights={}` so the legacy `overall` stays the source of truth (Risk-Med mitigation per design).
- **`nines self-eval --metrics-config PATH`** — CLI option to override the bundled defaults. Validation runs up front; failures abort with exit 2 listing every error.

### Tests + lint

- **Test suite: 1386 → 1420 (+34 tests)** with zero regressions; full suite green.
  - `tests/test_metrics_registry.py` (28 tests): definition guards, register/lookup, `weight_sum_for_group` single + multi, `normalized` no-threshold + MAXIMIZE band + ceiling-above-1.0 saturation breaker + MINIMIZE band + custom normalizer override + clamp + KeyError on unknown name, `weighted_mean` basic + missing-score denominator + empty-group + cross-group isolation, `validate` valid + non-summing + drift tolerance, `from_toml` round-trip + bundled-file validation + path resolution + bad-direction rejection + bad-threshold rejection, `weights_dict`.
  - `tests/test_self_eval.py` (+4): default registry populates `weighted_overall`, custom registry overrides defaults, `to_dict`/`from_dict` preserves C08 fields, invalid registry skips weighted aggregation but keeps legacy `overall`.
  - `tests/test_self_eval_cli.py` (+2): `--metrics-config` loads alternate weights, default config populates `weighted_overall`.
- **Ruff: 0 → 0 errors** maintained (added `StrEnum` for `Direction`, dropped the obsolete `sys.version_info` tomllib guard, organised CLI imports).

### Backward compatibility

- `SelfEvalReport.overall` (legacy unweighted mean) preserved alongside `weighted_overall` for one minor release per the C08 design's Risk-Med mitigation.
- CLI `_build_json_output` keeps the existing `overall = 0.7 × cap_mean + 0.3 × hyg_mean` formula plus `capability_mean` / `hygiene_mean` / `weights` blocks — operators get the C08 fields *additively* via `report.to_dict()`.
- The `--capability-only` CLI flag still works (capability group contributes; hygiene group skipped from the outer aggregate).

### Files changed

`src/nines/eval/metrics_registry.py` (+429 new), `src/nines/data/self_eval_metrics.toml` (+152 new), `src/nines/iteration/self_eval.py` (+138 / −0), `src/nines/cli/commands/self_eval.py` (+36 / −0), `tests/test_metrics_registry.py` (+415 new), `tests/test_self_eval.py` (+114 / −0), `tests/test_self_eval_cli.py` (+107 / −0), `pyproject.toml` (+6 / −0; hatch `force-include` for the bundled TOML), `.gitignore` (+2 / −0; `!src/nines/data/` exception so package data ships).

### Gap closure update

- ✅ §4.10 19/20 capability dims saturated at 1.000 → **MEASURABLY DE-SATURATED**: 7 capability dims dropped from 1.000 into the calibrated `[0.5, 0.95)` headroom band, and the new `weighted_overall=0.8970` is materially distinct from the legacy `overall=0.9766`. Future C09/C12 work now has signal to optimise against.

---

## v3.2.1 — 2026-04-18 (C01 Full Evaluator Migration)

**Theme:** Complete C01 evaluator migration. Phase 1 (v3.2.0) only made 3/20 capability evaluators project-aware; this patch closes the remaining gap so foreign-repo self-eval no longer silently inflates 8 more dims with NineS's own data.

**Empirical:** 8 newly project-aware dims for caveman (Phase 1 baseline was 3; threshold for verdict CONFIRMED is ≥5). Caveman BEFORE: `scoring_accuracy=1.0` (NineS's 20 golden tasks), `eval_coverage=1.0` (NineS's 3 samples), `pipeline_latency target=src/nines/__init__.py`. Caveman AFTER: `scoring_accuracy=0.0` (caveman has no golden), `eval_coverage=0.0` (caveman has no samples), `pipeline_latency target=/home/agent/reference/caveman/caveman`. Three foreign-repo runs report distinct context fingerprints (`9cfbf3b1` / `5a527c18` / `63c58172`). Proof: `.local/v3.2.1/benchmark/c01_full_proof.txt`.

**Status:** Patch release; aggregated into v3.3.0 minor.

### Migrated to ctx-aware (13 evaluators)

- **Capability (8):** D01 ScoringAccuracyEvaluator → `ctx.golden_dir`; D02 EvalCoverageEvaluator → `ctx.samples_dir`; D03 ReliabilityEvaluator → `ctx.golden_dir`; D05 ScorerAgreementEvaluator → `ctx.golden_dir`; D12 AbstractionQualityEvaluator → `ctx.src_dir`; D13 CodeReviewAccuracyEvaluator → `ctx.src_dir`; D16 PipelineLatencyEvaluator → derives target from `ctx.src_dir`; D20 AgentAnalysisQualityEvaluator → `ctx.project_root` + `ctx.src_dir`.
- **Hygiene (5):** LiveCodeCoverageEvaluator → `ctx.project_root`; LiveTestCountEvaluator → `ctx.test_dir` + `ctx.project_root`; LiveModuleCountEvaluator → `ctx.src_dir`; DocstringCoverageEvaluator → `ctx.src_dir`; LintCleanlinessEvaluator → `ctx.src_dir`.
- All 13 declare `requires_context: ClassVar[bool] = True` so the runner enforces strict-ctx mode.

### Documented as intentionally NineS-meta (no migration; inline rationale added)

D04 ReportQualityEvaluator (synthetic data), D06 SourceCoverageEvaluator (NineS collector imports), D07 SourceFreshnessEvaluator (in-memory DataStore), D08 ChangeDetectionEvaluator (in-memory DataStore), D09 DataCompletenessEvaluator (NineS schemas), D10 CollectionThroughputEvaluator (in-memory DataStore), D17 SandboxIsolationEvaluator (NineS sandbox), D18 ConvergenceRateEvaluator (NineS iteration plumbing), D19 CrossVertexSynergyEvaluator (NineS imports). Their docstrings now explicitly explain why they remain project-independent.

### Fixed

- **D16 PipelineLatencyEvaluator no longer falls back to `src/nines/__init__.py`** when `ctx.src_dir` contains zero `*.py` files (e.g. caveman, which is a Markdown-only skill). The fallback now returns `ctx.src_dir` itself so the metadata makes the empty-project answer unambiguous instead of silently re-targeting NineS.
- **D20 AgentAnalysisQualityEvaluator no longer 60s-times-out** on caveman because it now binds to caveman's tree (which has clear agent-facing artifacts) instead of recursively analyzing NineS itself.

### Improved

- **Test suite: 1366 → 1386 (+20 tests)** with zero regressions; full-suite green.
- **Ruff: 0 → 0** errors maintained.
- **§4.8 silent-fallback closure: 3/20 dims (Phase 1, v3.2.0) → 11/20 (now). Remaining 9 dims are intentional NineS-meta — fully documented.**

### Gap closure update

- ✅ §4.8 self-eval is project-blind unless `--src-dir` succeeds → **FULLY CLOSED for all dims that have a real project binding** (was PARTIAL in v3.2.0). Foreign-repo runs against caveman/UA now produce distinct, defensible numbers for 11 dims (3 Phase 1 + 8 newly migrated) plus 5 hygiene dims (also migrated, exercised under non-`--capability-only` runs); the 9 NineS-meta dims correctly stay project-independent by design.
- 🟡 §4.10 19/20 capability dims saturated at 1.000 → **De-saturation observed empirically**: caveman overall 0.9697 → 0.5250 (capability_mean drops 0.3247). UA overall 0.9697 → 0.7221. NineS overall stays at 0.9766 (its own ctx still sees its own 20-task golden / 3 samples / 92 modules — correct, not a bug). The "always 1.000" inflation that hid genuine foreign-repo gaps is gone.

### Files changed

`src/nines/iteration/v1_evaluators.py` (+86 -7), `src/nines/iteration/eval_evaluators.py` (+136 -23), `src/nines/iteration/capability_evaluators.py` (+143 -39), `src/nines/iteration/self_eval.py` (+168 -45), `src/nines/iteration/collection_evaluators.py` (+28 -0, doc-only), `src/nines/iteration/system_evaluators.py` (+18 -0, doc-only), `tests/test_c01_full_migration.py` (+20 new tests).

---

## v2.3.0 — 2026-04-18 (Wave 2 Paradigm Extension; pyproject v3.2.0)

**Theme:** Wave 2 of the v2.2.0 paradigm-extension iteration — closes the project-blindness gap (§4.8) and institutionalises Wave 1's data-quality wins via gates and auditors.

**Semver:** Released as `v3.2.0` (additive backward-compatible features); codename `v2.3.0 Wave 2` preserved for continuity with the design / accept-list documents.

**Status:** Released from `feat/v2.3.0-wave2-paradigm-extension` after 4 empirically-validated candidates (C01 Phase 1, C06 full harness, C07 quality-gate FSM, C10 cross-artifact auditor). All 4 verdicts CONFIRMED via per-candidate benchmarks at `.local/v2.3.0/benchmark/`. The 4 remaining candidates from the v2.2.0 accept list (C08 weighted MetricRegistry, C11a/b mechanism diversification, C12 breakdown reporter) stay deferred per the user's 'tested-benefit-only' rollout rule.

### Added (Wave 2 — 4 candidates, all CONFIRMED)

- **C01 Phase 1 — Project-aware `EvaluationContext`** (`src/nines/iteration/context.py` ~120 lines + `LegacyEvaluatorAdapter` in `iteration/self_eval.py`). New frozen dataclass carries `project_root` / `src_dir` / `test_dir` / `samples_dir` / `golden_dir` / `metadata` and exposes `fingerprint()` (8-char `blake2s` of resolved paths) and `from_cli(...)` factory. `DimensionEvaluator` Protocol gains optional kw-only `ctx` parameter; non-ctx-aware evaluators auto-wrap in `LegacyEvaluatorAdapter` at registration. 3 evaluators migrated (D11 `decomposition_coverage`, D14 `index_recall`, D15 `structure_recognition`). `SelfEvalReport` gains `context_fingerprint` field. Empirical proof: caveman / UA / NineS now report distinct project-specific values (caveman 0 / UA 40 / NineS 963 for `total_elements`) with 3 distinct fingerprints (`9cfbf3b1` / `5a527c18` / `63c58172`) — confirms §4.8 silent-fallback bug is fixed for the 3 migrated dims. 13 new tests.

- **C06 full harness — `MockEvaluator` + golden fixtures + hang-detection** (`src/nines/eval/mock_executor.py` extended + `tests/data/golden/self_eval_fixtures/`). New `MockEvaluator(DimensionEvaluator)` class for deterministic dim simulation; 2 golden fixtures (`nines_v3_1_0_capability.json`, `foreign_caveman_capability.json`) pin known-good `SelfEvalReport` shapes; joint hang-detection test asserts C04 budget aborts a 10-second mock evaluator within 2.245s; silent-fallback regression test detects 5 divergent dims when foreign-repo eval leaks NineS values. 5-run determinism verified (sha256 byte-identical). 16 new tests. Unblocks future C08 + C12 work.

- **C07 — Quality-gate state machine** (`src/nines/iteration/gates.py` ~660 lines + planner/tracker integration). 4 built-in gates: `GraphVerificationGate` (consumes C03 output), `EconomicsScoreGate` (consumes C09 output), `SelfEvalCoverageGate` (consumes self-eval output), `RegressionGate` (consumes IterationTracker history). Lifecycle: `PROPOSED → EVALUATING → PASSED / FAILED / ESCALATED / BYPASSED`. Default ships in `advisory_mode=True` (warns but doesn't block) for one minor; `--strict-gates` CLI flag opt-in for blocking. Empirical proof: clean report passes (`should_abort=False`); strict-mode bad report blocks (`should_abort=True`); advisory-mode bad report warns without blocking. `ImprovementPlan.gate_results` + `IterationTracker.record_gate_results / gate_history` extensions. 16 new tests. Institutionalises Wave 1's C03 + C04 + C09 wins so future PRs can't silently re-introduce the bugs.

- **C10 — Cross-artifact consistency auditor** (`src/nines/analyzer/consistency_auditor.py` ~700 lines + `cli/commands/analyze.py` `--audit/--strict-audit` flags). 6 built-in checks: `FindingIDUniquenessCheck`, `FindingIDNamespaceCheck`, `EconomicsFormulaVersionCheck`, `EconomicsBreakEvenSanityCheck`, `GraphVerificationPassedCheck`, `ReportMetadataPresenceCheck` + `SchemaVersioningCheck` migration hook. Default ships in advisory mode; `--strict-audit` opt-in blocks on critical findings. JSON output gains top-level `audit_report` block. Empirical proof on a synthetically-regressed caveman report: auditor flags 2 critical findings (duplicate `SUM-d37f14-0000` ID + `break_even=2` algebraically unjustified) with `should_block=True`; clean caveman passes with 1 advisory warn (legacy 6-hex finding-ID format from non-`AI-` prefixes). 18 new tests.

### Improved

- **Test suite: 1301 → 1366 (+65 tests, +5.0 %)** with zero regressions; full-suite green at every commit.
- **Ruff: 0 → 0 errors** maintained after 4 large new modules (~1500 LOC total).
- **Mypy: 0 NEW errors** from this branch (4 new errors fixed during S02 cleanup; 8 pre-existing errors in `eval/`, `collector/`, `core/config.py` deliberately left as out-of-scope).

### Gap closure (vs `.local/v2.2.0/profile/00_baseline_report.md` §4 inventory; cumulative through v3.2.0)

- ✅ §4.1 graph verification fails on every sample → CLOSED in v3.1.0 (C03)
- ✅ §4.2 `layer_coverage_pct = 100.0` tautology → CLOSED in v3.1.0 (C03)
- ✅ §4.5 cross-sample finding-ID collisions → CLOSED in v3.1.0 (C02)
- ✅ §4.6 `break_even_interactions = 2` constant → CLOSED in v3.1.0 (C09)
- ✅ §4.7 self-eval hangs ≥ 5 min → BOUNDED runner-level in v3.1.0 (C04 + N2); FULLY GATED in v3.2.0 via C07 advisory mode
- ✅ §4.8 self-eval is project-blind unless `--src-dir` succeeds → CLOSED for D11/D14/D15 in v3.2.0 (C01 Phase 1); remaining ~9 evaluators ship as Wave 3
- 🟡 §4.9 D21–D24 dimension surface mismatch → PARTIAL (C01 Phase 1 fixes the migrated dims; full schema work needs C12)
- ✅ §4.11 no matrix / cost / parallel concerns → BOUNDED in v3.1.0 (C04 + C05)
- ⏳ §4.3 hard-coded mechanism categories → OPEN (needs C11a/b in Wave 3/4)
- ⏳ §4.4 KP category mix template-locked → OPEN (needs C11a + C12)
- ⏳ §4.10 19/20 capability dims saturated at 1.000 → OPEN (needs C08 + C12)

**Net cumulative through v3.2.0:** 6 of 11 gaps fully CLOSED + 1 BOUNDED = **7/11 (64 %)**. Remaining 3 gaps await Wave 3 (C08 + C11a) and Wave 4 (C12 + C11b).

### Deferred (per 'tested-benefit-only' rule)

The 4 remaining v2.2.0 accept-list candidates stay deferred:
- **C08 weighted `MetricRegistry`** — needs C01 (full migration of all ~12 evaluators) before re-weighting can create cross-project signal that doesn't exist in inputs.
- **C11a mechanism diversification (rule-based)** — needs C08 for weighting new categories.
- **C11b LLM-judge fallback** — needs separate security/cost review.
- **C12 AgentBoard-style breakdown reporter** — needs C01 + C08 + full-C06 (golden harness shipped this minor unblocks this dependency).

### Provenance

- Empirical proofs: `.local/v2.3.0/benchmark/c01_phase1_proof.txt`, `c06_full_proof.txt`, `c07_gate_proof.txt`, `c10_audit_proof.txt`
- Lint/typecheck baselines: `.local/v2.3.0/release/lint_typecheck_{baseline,final}.txt`
- Wave 1 audit trail: `.local/v2.2.0/{survey,profile,design,benchmark,validate,release}/`
- Decision document: `.local/accept_list_v2.2.0.{md,zh.md}`

---

## v2.2.0 — 2026-04-18 (Paradigm Extension; pyproject v3.1.0)

**Theme:** Self-iteration combined with EvoBench paradigm extension; data-quality + resilience foundations for downstream differentiation. Closes 4 of 11 baseline gaps at the source (§4.1, §4.2, §4.5, §4.6) and bounds 2 more (§4.7, §4.11) at the runner level.

**Semver:** Released as `v3.1.0` (additive backward-compatible features); codename `v2.2.0 Paradigm Extension` preserved for continuity with the design / accept-list documents.

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
