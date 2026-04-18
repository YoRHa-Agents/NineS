---
id: "nines/references/derived-metrics"
version: "1.0.0"
purpose: >
  Documents NineS's derived-metric algebra and weighted aggregation
  paradigm. Codifies the EvoBench `MetricDefinition` + `MetricRegistry`
  pattern (gap 1.2 — NOT_ABSORBED in v3.0.0) and the HELM holistic
  multi-metric capability surface, applied to NineS's
  `context_economics`, self-eval dimensions, and (planned) sub-skill
  panels. Load this reference when adding a new score-like output, when
  designing weights for a self-eval group, or when bumping a metric's
  formula version.
triggers:
  - "metric"
  - "weighted"
  - "registry"
  - "formula_version"
  - "score"
  - "economics"
  - "derived"
tier: 2
token_estimate: 1200
dependencies:
  - "nines/SKILL.md"
  - "nines/references/agent-impact-analysis"
  - "nines/references/evaluation-framework"
last_updated: "2026-04-18"
---

# Derived Metrics Reference

## 1. Why This Reference Exists

NineS v3.0.0 reported `context_economics.break_even_interactions = 2`
for **every** project (caveman / DevolaFlow / UA), regardless of
overhead (41 k → 126 k tokens) or savings ratio (0.5 / 0.6 / 0.8). The
empirical evidence in `.local/v2.2.0/profile/00_baseline_report.md`
§4.6 made the cause clear: the v3.0.0 formula was

```python
savings_ratio = min(0.95, len(artifacts) * 0.05)
break_even = max(1, (overhead + saved - 1) // saved)
```

With `len(artifacts) ≈ 12` and `overhead` proportional to artifacts,
the algebra collapses to `break_even ≈ 1 / savings_ratio = 1.66 → 2`
for every project. **The metric was not a true derived measure; it was
a flat default with a mathematical-looking expression.**

Compounding this: `SelfEvalRunner.run_all` (lines 197-199 in v3.0.0)
computed `overall = sum(s.normalized for s in scores) / len(scores)` —
a flat unweighted mean. Self-eval outer weights (capability 0.7,
hygiene 0.3) were applied at the CLI; *inside* each block, every
dimension counted equally. §4.10 shows the result: 19 of 20 capability
dims pinned at 1.000 → headline `overall = 0.9697` with no headroom
for measuring v3.x improvements.

EvoBench's `ageneval-dimensions` defines `MetricDefinition` with
direction (`MAXIMIZE` / `MINIMIZE`), value-type, `normalize()`, and
per-dimension weight-sum validation. HELM's holistic suites attach
weights to orthogonal metrics so a single "model quality" score is
interpretable. The migration analysis in
`.local/v2.2.0/survey/01_evobench_gap_analysis.md` §2 row 1.2 listed
this as **NOT_ABSORBED** — the highest-leverage gap on the entire
EvoBench paradigm-extension axis.

This reference codifies the merged solution: **score-like outputs are
derived from real inputs, normalised against documented thresholds,
and weighted in a single registry that validates per-group sums.**

**Empirical evidence file motivating this reference:**
`.local/v2.2.0/profile/00_baseline_report.md` §4.6 + §4.10; raw POC
proof `.local/v2.2.0/benchmark/c09_economics_variance.txt`.

## 2. The Pattern: Algebra over Constants

### Three primitives

1. **Derived metric algebra.** Every score-like output is computed from
   measurable inputs by an explicit formula, not a hard-coded ceiling
   or a clipped default. The formula is documented in source comments
   and in this reference; the inputs are exposed in `to_dict()` so
   downstream consumers can reproduce the calculation.
2. **`formula_version: int` schema migration.** When the formula
   changes, the version number bumps. Backward-compat parsers
   (`from_dict`) default `formula_version=1` for legacy reports and
   apply v1 semantics; new reports set `formula_version=2` and use the
   new formula. C09 is the canonical pattern (see `src/nines/analyzer/
   agent_impact.py:91-181` and `tests/analyzer/test_agent_impact_economics.py`
   `test_from_dict_legacy_v1_report_defaults_filled`).
3. **Weighted `MetricRegistry`** *(planned, C08)*. Replaces flat
   unweighted means with per-group weighted aggregation. Each
   `MetricDefinition(name, weight, direction, threshold, group)`
   declares its weight; `MetricRegistry.weight_sum_for_group(group)`
   validates that weights sum to 1.0 ± 0.01; `weighted_mean(group,
   scores)` computes the aggregate. Per-dim `threshold = (min, max)`
   tightens the normalisation so dims like `decomposition_coverage`
   can't trivially saturate at 1.000.

### Real derived metric — `context_economics` after C09

```python
# C09 formula (formula_version = 2)
saved_per_interaction = sum(
    abs(m.estimated_token_impact)
    for m in mechanisms
    if m.category == "context_compression"
)
break_even = math.ceil(overhead_tokens / max(saved_per_interaction, 1))

mechanism_diversity_factor = 1.0 + 0.1 * (distinct_categories - 1)

economics_score = clamp(
    (saved_per_interaction * expected_retention_rate * mechanism_diversity_factor)
    / overhead_tokens,
    0, 1,
)

confidence = (
    min(1.0, mechanism_count / 5)
    * mean(m.confidence for m in mechanisms)
)
```

Per-sample empirical evidence (`c09_economics_variance.txt`):

| Sample      | overhead | saved/int | break_even | retention | diversity | eco_score | fmt_v |
|-------------|---------:|----------:|-----------:|----------:|----------:|----------:|------:|
| caveman     | 41 343   | 6 919     | **6**      | 0.85      | 1.4       | 0.1992    | 2     |
| devolaflow  | 229 249  | 36 202    | **7**      | 0.85      | 1.4       | 0.1879    | 2     |
| ua          | 55 531   | 7 260     | **8**      | 0.85      | 1.4       | 0.1556    | 2     |

`break_even` distinct values: **3** (was constant 2 in v3.0.0); spread
in `economics_score`: **0.0436** (was 0). The score is now sensitive
to overhead, savings, retention, and mechanism diversity — all
measurable at the source.

### Weighted aggregation — proposed for C08

```python
@dataclass
class MetricDefinition:
    name: str
    weight: float                # contribution to the group's weighted_mean
    direction: Direction = MAXIMIZE
    normalizer: Callable[[float, float], float] | None = None
    threshold: tuple[float, float] | None = None  # (min_acceptable, max_excellent)
    group: str = "default"

class MetricRegistry:
    def register(self, m: MetricDefinition) -> None: ...
    def weight_sum_for_group(self, group: str) -> float: ...
    def normalized(self, name: str, value: float) -> float: ...
    def weighted_mean(self, group: str, scores: dict[str, float]) -> float: ...
    def validate(self) -> list[str]: ...  # weight-sum errors per group
```

Per-dim threshold examples for self-eval (proposed in
`.local/v2.2.0/design/03_track_c_differentiation.md` §C08):

| Dim                       | v3.0.0 effective range | C08 proposed `threshold` | Rationale                                                |
|---------------------------|------------------------|--------------------------|----------------------------------------------------------|
| `decomposition_coverage`  | (0.0, 1.0) — saturates | (0.6, 0.95)              | Reaching 1.0 should require near-perfect capture; v3.0.0 hits 1.000 trivially |
| `code_review_accuracy`    | (0.0, 1.0)             | (0.7, 1.0)               | Lower bound rejects sub-skill failures                    |
| `index_recall`            | (0.0, 1.0) — 5/5 trivially passes | (0.6, 1.0) on stricter query set | Today: 5 fixed queries; future: stricter query bar |
| `code_coverage` (hygiene) | (0.0, 1.0)             | (0.4, 0.95)              | 0–60 % maps to 0; ≥ 95 % maps to 1; linear in between    |
| `lint_cleanliness`        | (0.0, 1.0)             | (0.5, 1.0)               | Below 50 % is unacceptable; above 95 % is excellent       |

After C08, `capability_mean` falls from `0.9750` → ≈ `0.85–0.92`
(prediction in `02_analytical_validation.md` §C08), unblocking
measurable v2.x improvements.

## 3. NineS Implementation Hooks

### Already in tree (Wave 1)

- **`src/nines/analyzer/agent_impact.py`** (modified by C09, lines
  91-181 + 451-553) — `ContextEconomics` dataclass with
  `formula_version: int = 2`; new fields `per_interaction_savings_tokens`,
  `expected_retention_rate`, `mechanism_diversity_factor`,
  `economics_score`. `_estimate_context_economics` rewrite at lines
  493-518 implements the C09 algebra.
- **`ContextEconomics.from_dict`** (lines 158-181) — defaults
  `formula_version=1` for legacy reports; preserves legacy fields
  (`overhead_tokens`, `estimated_savings_ratio`,
  `break_even_interactions`) for backward compat.
- **`tests/analyzer/test_agent_impact_economics.py`** (POC for C09, 9
  cases) — empty repo edge case (line 45), real savings drive
  break_even (54), distinct overhead → distinct break_even (74),
  diversity raises score (91), score clamped to [0, 1] (110), legacy
  fallback for no-mechanisms call (120), zero-savings yields
  overhead-sized break_even (132), to_dict / from_dict round-trip with
  v1 default (149-181).
- **`mechanism_diversity_factor = 1.0 + 0.1 * (distinct_categories -
  1)`** is *already wired* (line 504) — when C11a lands and adds 4
  ContextOS-derived mechanism categories, `mechanism_diversity_factor`
  rises from `1.4` (current §2 fixtures) → `~1.8`, lifting
  `economics_score` ≈ +0.05 absolute on the same fixtures. Pre-document
  this in v2.3 release notes so reviewers don't read it as a
  regression.

### Planned (Wave 3 — C08)

- **`src/nines/eval/metrics_registry.py`** (new) — exports `Direction`,
  `MetricDefinition`, `MetricRegistry` per §2 above.
- **`data/self_eval_metrics.toml`** (new) — declarative configuration
  for capability and hygiene group weights + per-dim thresholds.
  Reviewable in PRs; weights are configuration, not code.
- **`src/nines/iteration/self_eval.py`** (modified by C08) —
  `SelfEvalRunner.__init__(self, registry: MetricRegistry | None =
  None)`. `run_all()` calls
  `registry.weighted_mean("capability", {s.name: s.normalized for s in
  cap_scores})` instead of flat mean.
- **`SelfEvalReport`** (schema-evolve) — adds `weighted_overall:
  float`, `group_means: dict[str, float]`, `metric_weights: dict[str,
  float]` for transparency. Legacy `overall` (unweighted) preserved
  for one minor.
- **`src/nines/cli/commands/self_eval.py`** (modified by C08) — builds
  registry from `--metrics-config PATH` (default ships at
  `data/self_eval_metrics.toml`). Removes hard-coded `CAPABILITY_WEIGHT
  = 0.70` constant. **Wires `weighted_overall` / `group_means` /
  `metric_weights` into `_build_json_output`** (closing the N1 risk).
- **`report_schema_version: int = 2`** field on `SelfEvalReport` —
  signals consumers to use the weighted aggregation; legacy v1 reports
  continue to expose `overall` only.

### Planned (Wave 4 — C12)

- **`src/nines/iteration/breakdown_reporter.py`** — sub-skill panels
  (`SubSkill`, `DimensionPanel`, `BreakdownReport`) consume the
  weighted registry from C08 to produce per-sub-skill weighted scores
  per dim.
- Per-evaluator metadata annotations: ≥ 6 evaluators expose
  `metadata["subskills"]` blocks so the reporter can decompose flat
  `1.000` scores into actionable sub-skills.

## 4. Developer Workflow — Adding a New Score-Like Output

When adding a new score field to NineS (analyzer, evaluator, or
reporter):

1. **Identify the underlying inputs.** What raw measurements does the
   score depend on? Document them as explicit inputs in the dataclass
   (e.g. `overhead_tokens`, `per_interaction_savings_tokens` instead of
   a clipped `savings_ratio`).
2. **Write the formula in source comments.** Show the equation in the
   docstring of the producing function. The S05 review of C09 caught
   the "DevolaFlow overhead inflation 126 k → 229 k" surprise because
   the new ordering was visible in the source comments — not buried in
   data.
3. **Bump `formula_version`.** Add a `formula_version: int = N` field
   to the dataclass. Default `from_dict` to the previous version when
   the field is absent. Add a regression test that legacy reports
   round-trip.
4. **Add a clamp / bounds check.** Every score-like output should have
   asserted bounds (`0 ≤ score ≤ 1` for normalised scores;
   `1 ≤ count ≤ overhead_tokens` for derived integer counts). C09's
   `test_economics_score_clamped_to_unit_interval` (line 110) is the
   pattern.
5. **Register with the `MetricRegistry` (post-C08).** Add a
   `MetricDefinition` to `data/self_eval_metrics.toml` (or analogous
   config file) with an explicit weight, direction, and threshold.
   Run `MetricRegistry.validate()` in tests to confirm group weights
   sum to 1.0 ± 0.01.
6. **Wire CLI exposure.** Always update `_build_json_output` (or
   analogous) to include the new field in the CLI `--format json`
   payload. The N1 risk surfaced when C04's `timeouts` field was
   silently dropped from CLI JSON; do not repeat.
7. **Document the score in the relevant `references/<area>.md`.** Add
   a row to the file's "Source Files" table; update the "Worked
   Example" section with before/after numbers from a real fixture.

## 5. Worked Example — `c09_economics_variance.txt`

Before C09 (v3.0.0):

```
caveman:    overhead=41343,  savings_ratio=0.6, break_even=2
devolaflow: overhead=126308, savings_ratio=0.8, break_even=2  <-- constant
ua:         overhead=55531,  savings_ratio=0.5, break_even=2  <-- constant
spread on break_even: 0
spread on economics_score: n/a (field did not exist)
```

After C09 (formula_version=2):

```
caveman:    overhead=41343,  saved/int=6919,  break_even=6, eco_score=0.1992
devolaflow: overhead=229249, saved/int=36202, break_even=7, eco_score=0.1879
ua:         overhead=55531,  saved/int=7260,  break_even=8, eco_score=0.1556
spread on break_even: 3 distinct values (was 0)
spread on economics_score: 0.0436 (was 0; target ≥ 0.03)
```

The DevolaFlow overhead change (126 k → 229 k) is a *known
behavioural shift* documented in
`.local/v2.2.0/benchmark/00_benchmark_report.md` §2.3: the new
ordering runs mechanism detection *before* economics so the mechanism
token impacts inflate the published overhead. Downstream consumers
that read `overhead_tokens` as a stable number must opt in via
`formula_version=2`; legacy parsers see `formula_version=1` and
preserve v1 semantics.

The `mechanism_diversity_factor=1.4` (current §2 fixtures) is wired but
dormant — `distinct_categories = 5` since v3.0.0's hard-coded taxonomy
emits 5 mechanisms regardless. After C11a lands with 4 new ContextOS
categories, the same caveman fixture should show
`mechanism_diversity_factor ≈ 1.8` and `economics_score ≈ 0.256`
(+0.05 absolute on the §2 baseline).

## 6. References

- **EvoBench `ageneval-dimensions`** — `MetricDefinition` + per-dim
  `normalize()` + weight-sum validation
  (`.local/v2.2.0/survey/01_evobench_gap_analysis.md` §2 row 1.2 —
  listed NOT_ABSORBED in v3.0.0).
- **HELM holistic capability surfaces** — bundle orthogonal metrics
  (`.local/v2.2.0/survey/02_reference_repo_catalog.md` §3 P4).
- **Inspect model-graded scorers** — composable metric components
  (`02_reference_repo_catalog.md` §3 P12 / row inspect_ai entry; future
  C11b inspiration).
- **AgentBoard analytical evaluation** — fine-grained metrics +
  trajectory visualisation (`02_reference_repo_catalog.md` §3 P2;
  future C12 inspiration).
- **Empirical motivation** —
  `.local/v2.2.0/profile/00_baseline_report.md` §4.6 + §4.10; raw POC
  proof `.local/v2.2.0/benchmark/c09_economics_variance.txt`.

## 7. Source Files

| File                                              | Status            | Role                                                                  |
|---------------------------------------------------|:-----------------:|-----------------------------------------------------------------------|
| `src/nines/analyzer/agent_impact.py`              | **modified** (C09) | C09 economics formula + `formula_version=2` + new fields              |
| `tests/analyzer/test_agent_impact_economics.py`   | **shipped** (C09) | 9 cases incl. v1 round-trip                                            |
| `src/nines/eval/metrics_registry.py`              | *planned* (C08)   | `Direction`, `MetricDefinition`, `MetricRegistry`                      |
| `data/self_eval_metrics.toml`                     | *planned* (C08)   | Declarative weights + per-dim thresholds                               |
| `src/nines/iteration/self_eval.py`                | *planned* (C08)   | `SelfEvalRunner.run_all` consumes registry; emits `weighted_overall`   |
| `src/nines/cli/commands/self_eval.py`             | *planned* (C08)   | Wires `weighted_overall` / `group_means` / `metric_weights` to JSON     |
| `SelfEvalReport.weighted_overall`                 | *planned* (C08)   | New field; legacy `overall` preserved for one minor                     |
| `report_schema_version: int = 2`                  | *planned* (C08)   | Schema migration signal                                                 |
| `src/nines/iteration/breakdown_reporter.py`       | *planned* (C12)   | Sub-skill panels consume weighted registry                              |
| `docs/iteration/metric_weights.md`                | *planned* (C08)   | Per-dim threshold rationale                                             |
