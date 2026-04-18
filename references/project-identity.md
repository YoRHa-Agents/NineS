---
id: "nines/references/project-identity"
version: "1.0.0"
purpose: >
  Documents NineS's project-fingerprint and finding-ID namespacing
  paradigm. Codifies the EvoBench v2.2.0 cross-artifact-audit identity
  requirements + nearai-bench's "workspace identity files" pattern,
  applied to NineS analyzer findings, key-points, and (planned)
  EvaluationContext. Load this reference when adding new analyzers or
  evaluators that produce findings, when designing cross-run dashboards,
  or when wiring per-project context into evaluators.
triggers:
  - "fingerprint"
  - "project_id"
  - "identity"
  - "namespace"
  - "context_fingerprint"
  - "EvaluationContext"
tier: 2
token_estimate: 1200
dependencies:
  - "nines/SKILL.md"
  - "nines/references/agent-impact-analysis"
  - "nines/references/cross-artifact-audit"
last_updated: "2026-04-18"
---

# Project Identity Reference

## 1. Why This Reference Exists

NineS v3.0.0 emitted finding IDs as `f"AI-{idx:04d}"` at six call sites
in `src/nines/analyzer/agent_impact.py` (lines 564 / 577 / 591 / 614 /
631 / 645 in v3.0.0). The empirical evidence in
`.local/v2.2.0/profile/00_baseline_report.md` §4.5 made the cost
concrete:

| Sample        | Findings | Unique IDs                                         |
|---------------|---------:|----------------------------------------------------|
| caveman       | 24       | 24 / 24 within sample                              |
| DevolaFlow    | 225      | 225 / 225 within sample                            |
| Understand-Anything | 22  | 22 / 22 within sample                              |
| **Cross-sample (3 samples × 3 AI- IDs)** | — | **3** unique (3 × `AI-0000` / `AI-0001` / `AI-0002` collide) |
| **Total** | 271      | **265** unique → 6 collisions                       |

A downstream dashboard that dedupes on `finding.id` would silently
**drop two of the three samples' agent-impact rollups** because all
three repos emit the same first 3 IDs. EvoBench v2.2.0's deep
cross-file consistency audit relies on every record having a globally
unique key. Nearai-bench uses workspace-derived prefixes for trajectory
assertions to keep them addressable across runs. The v3.0.0 NineS
output was not compatible with either pattern.

A second, related problem: §4.8 documented that when `--src-dir` is
omitted (the only way to run on caveman / UA today), capability
dimension metadata reports `total_elements=837, files_analyzed=83` for
**both** caveman and UA — these are NineS's own counts, not the
sample's. Even `decomposition_coverage`, `code_review_accuracy`,
`index_recall`, and `agent_analysis_quality` collapse to NineS values.
The two foreign-repo runs differ from NineS by **zero** in 24 of 25
dims; only DevolaFlow shows project-specific data because its
`--src-dir` happened to work. The root cause is that `DimensionEvaluator`
constructors take `src_dir: str = "src/nines"` as a default, and there
is no `EvaluationContext` to bind the evaluator to a specific project
at runtime.

This reference codifies the merged solution: **identity is an explicit,
immutable input to every NineS analyzer and evaluator, not an inherited
ambient default.**

**Empirical evidence file motivating this reference:**
`.local/v2.2.0/profile/00_baseline_report.md` §4.5 + §4.8 + §4.9; raw
proof `.local/v2.2.0/benchmark/c02_id_uniqueness.txt`.

## 2. The Pattern: Identity as Explicit Input

### Three primitives

1. **`project_fingerprint(project_root: Path) -> str`** — stable 8-char
   blake2s hash of the *resolved absolute path* + the repo's git remote
   URL when available, else just the path. Returns hex digits only;
   never user-displayable text. Implemented in
   `src/nines/core/identity.py` (POC for C02, lines 70-119).
2. **Namespaced finding IDs** — `f"AI-{project_fingerprint}-{idx:04d}"`
   replaces `f"AI-{idx:04d}"` at every emission site. Backward-compat
   parser `parse_finding_id(s) -> (project_id|None, prefix, idx)`
   accepts both legacy and namespaced forms.
3. **`EvaluationContext`** *(planned, C01)* — frozen dataclass exporting
   `project_root`, `src_dir`, `test_dir`, `samples_dir`, `golden_dir`,
   `metadata`. Every `DimensionEvaluator.evaluate(ctx)` reads paths from
   `ctx`, never from a constructor-time default. Persisted as
   `SelfEvalReport.context_fingerprint` so JSON output proves which
   project was scored.

### Identity hierarchy

```
  +---------------------------------------------+
  | EvaluationContext                            |
  | (planned C01)                                |
  +-------------------+--------------------------+
                      |
                      | .fingerprint() ===
                      v
  +---------------------------------------------+
  | project_fingerprint(project_root)            |
  | shipped C02; src/nines/core/identity.py:70   |
  +-------------------+--------------------------+
                      |
                      | format_finding_id("AI", idx, project_id=fp)
                      v
  +---------------------------------------------+
  | "AI-{8-hex}-{4-digit}"                       |
  | shipped C02; agent_impact.py @ 6 sites       |
  +---------------------------------------------+
```

The fingerprint is the *single source of identity*. `EvaluationContext`
exposes it through `.fingerprint()`; finding-ID namespacing consumes
it; the cross-artifact auditor (C10) uses it as the join key when
detecting collisions. **Recommendation in
`.local/v2.2.0/validate/02_analytical_validation.md` §C01:** C01's
`EvaluationContext.fingerprint()` should *call* the existing C02
helper, not re-implement it.

### Backward compatibility

Legacy reports with `AI-0007` IDs continue to parse via
`parse_finding_id`:

| Input            | Returns                            |
|------------------|------------------------------------|
| `AI-0007`        | `(project_id=None, prefix="AI", idx=7)` |
| `AI-12345678-0007` | `(project_id="12345678", prefix="AI", idx=7)` |
| `KP-d37f14-0001` | `(project_id="d37f14", prefix="KP", idx=1)` |
| `SUM-d37f14-0000` | `(project_id="d37f14", prefix="SUM", idx=0)` |

Reports older than v2.2.0 keep working; the new
`report_metadata.id_namespace_version=2` field signals consumers to use
the namespaced parser. JSON dashboards that deduplicated by raw
`finding.id` should switch to `(project_id, prefix, idx)` tuple keys.

## 3. NineS Implementation Hooks

### Already in tree (Wave 1)

- **`src/nines/core/identity.py`** (POC for C02, ~225 lines) — exports
  `project_fingerprint(project_root, *, include_git_remote=True) -> str`
  (lines 70-119), `format_finding_id(prefix, idx, project_id=None) ->
  str` (lines 175-185), `parse_finding_id(s) -> (project_id|None,
  prefix, idx)` (lines 102-121). Uses `hashlib.blake2s(payload,
  digest_size=4).hexdigest()` → 8 hex chars exactly. Optional git
  remote inclusion via `subprocess` lookup (logs DEBUG on failure).
- **`src/nines/analyzer/agent_impact.py`** (modified by C02) — six
  `f"AI-{idx:04d}"` sites replaced with
  `format_finding_id("AI", idx, project_id)`. Constructor accepts an
  optional `project_id: str | None`; `analyze()` computes a fingerprint
  from `project_root` if not supplied (lines 332-342). On
  fingerprint-computation failure (`OSError` or `ValueError`) logs
  WARNING and falls back to legacy unscoped IDs — explicit fallback,
  not silent suppression (per workspace rule "No Silent Failures").
- **`tests/core/test_identity.py`** (POC for C02, 23 cases) — covers
  fingerprint stability across `__repr__`, distinctness on different
  paths, relative-path resolution (lines 53-60), empty-path rejection
  (68-71), 2 000-path collision-rate stress (81-94), legacy +
  namespaced round-trip parser (142-151).

### Planned (Wave 2 — C01)

- **`src/nines/iteration/context.py`** (new) — `EvaluationContext`
  frozen dataclass + `from_cli` / `from_dict` / `fingerprint()`
  classmethods. Reuses `nines.core.identity.project_fingerprint`
  rather than reinventing.
- **`src/nines/iteration/self_eval.py`** (modified) — extends
  `DimensionEvaluator` Protocol with `evaluate(ctx: EvaluationContext)`;
  `SelfEvalRunner.run_all(ctx)` passes it through; refuses to run
  when `ctx is None` and an evaluator declares `requires_context =
  True`.
- **All ~12 capability evaluators** in
  `src/nines/iteration/capability_evaluators.py`,
  `collection_evaluators.py`, `eval_evaluators.py`,
  `system_evaluators.py`, `v1_evaluators.py`, `graph_evaluators.py` —
  replace constructor-time `src_dir: str = "src/nines"` with read-time
  `ctx.src_dir`. Each `evaluate(self, ctx: EvaluationContext)`.
- **`src/nines/cli/commands/self_eval.py`** (modified) — builds an
  `EvaluationContext` from the Click options, passes to
  `runner.run_all(ctx)`. Removes the silent default
  `src_dir="src/nines"`. Wires `context_fingerprint` into
  `_build_json_output` (closing the N1 risk that surfaced in C04).
- **`SelfEvalReport.context_fingerprint: str | None`** — non-empty in
  100 % of post-C01 runs; absence on a v2.2.x report signals the
  hidden-fallback bug from §4.8.
- **`LegacyEvaluatorAdapter`** — shim for one minor release so external
  forks have a deprecation window. Documented in
  `docs/migration/v2.2.0.md`.

### Wave 1 follow-up — shipped (C02a)

- **`report_metadata.id_namespace_version: int = 2`** field — added to
  the top level of `nines analyze --format json` output. Built by
  `AnalysisPipeline.build_report_metadata()` (in
  `src/nines/analyzer/pipeline.py`) and injected by the analyze CLI
  command before serialization. The block also exposes
  `analyzer_schema_version: int = 1` (reserved for future top-level
  shape bumps) and `nines_version: str` (looked up via
  `importlib.metadata.version("nines")`, fallback to
  `nines.__version__`). Downstream parsers should gate on
  `report_metadata.id_namespace_version == 2` before consuming
  namespaced finding IDs (`AI-{8-hex-fp}-NNNN`); legacy reports omit
  the block entirely. See `tests/cli/test_analyze.py` for the
  contract tests.

## 4. Developer Workflow — Adding a New Analyzer / Evaluator

When adding a new analyzer or evaluator that produces findings or scores:

1. **Decide whether the artifact is per-project or cross-project.**
   Findings tied to a specific repo file (e.g.
   `SUM-d37f14-0000`) need a per-file hash *and* a per-project
   fingerprint. Cross-project rollups (e.g. agent-impact summary) need
   only the project fingerprint.
2. **Use the existing helper.** Always import
   `nines.core.identity.format_finding_id` and
   `project_fingerprint` rather than rolling your own. The 8-char
   blake2s fingerprint is the standard width across the codebase.
3. **Compute the fingerprint once per `analyze()` call.** Store it on
   the analyzer instance; pass it down to internal helpers as a
   parameter. Avoid recomputing it per finding — `project_fingerprint`
   does a `Path.resolve()` plus an optional `subprocess` call to
   `git remote get-url`, both of which are non-trivial.
4. **For evaluators (post-C01): accept `ctx: EvaluationContext`.** Read
   `ctx.src_dir`, `ctx.test_dir`, etc. Never default `src_dir =
   "src/nines"`. If an evaluator genuinely cannot read a per-project
   value, declare `requires_context = False` and document the limit;
   the runner will still pass `ctx` so the evaluator can surface
   `metadata["context_fingerprint"] = ctx.fingerprint()` in its
   `DimensionScore` for provenance.
5. **Backfill cross-run uniqueness tests.** Add a
   `tests/<area>/test_<name>_identity.py` case that runs your
   analyzer / evaluator against ≥ 3 different fixtures (caveman /
   DevolaFlow / UA make a good triplet) and asserts that `set(all
   finding IDs)` has length equal to the sum across fixtures.
6. **For dashboards or cross-run consumers:** dedupe on `(project_id,
   prefix, idx)` tuples returned by `parse_finding_id`, not on raw
   `finding.id` strings. The `report_metadata.id_namespace_version`
   field signals which scheme to use.

## 5. Worked Example — `c02_id_uniqueness.txt`

Before C02:

```
AI-0000   (caveman agent-impact rollup)
AI-0000   (devolaflow agent-impact rollup)   <-- collision
AI-0000   (ua agent-impact rollup)            <-- collision
AI-0001   (caveman context-economics)
AI-0001   (devolaflow context-economics)      <-- collision
...
Total: 271 generated, 265 unique, 6 collisions.
```

After C02:

```
AI-45961152-0000   (caveman agent-impact rollup; fp=45961152)
AI-05645815-0000   (devolaflow agent-impact rollup; fp=05645815)
AI-8c1e11cc-0000   (ua agent-impact rollup; fp=8c1e11cc)
AI-45961152-0001   (caveman context-economics)
AI-05645815-0001   (devolaflow context-economics)
...
Total: 271 generated, 271 unique, 0 collisions.
```

The fix is one 8-char prefix per project. Hash-collision risk for
1 000 distinct projects against a 32-bit fingerprint is < 10⁻³ (verified
in `tests/core/test_identity.py` lines 81-94 with a 2 000-path stress
test). For very large NineS installs (≥ 100 000 projects), the
fingerprint width can be widened to 12 chars (48 bits) without
breaking the parser.

**Note from
`.local/v2.2.0/validate/01_empirical_validation.md` C02:** the design
overstated the surface area. `keypoint.py` already used per-file 6-char
hashes (`KP-d37f14-0000`); `reviewer.py` already used `(prefix, fhash,
idx)` triples. The actual collision was *only* in the agent-impact
`AI-` prefix family. The C02 POC scope correctly targets just those
six sites.

## 6. References

- **EvoBench v2.2.0 cross-file data-consistency audit** — relies on
  globally-unique record keys (`.local/v2.2.0/survey/01_evobench_gap_analysis.md`
  §4 row 1).
- **nearai-bench workspace identity files** (`SOUL.md`, `IDENTITY.md`)
  — production prompts mirrored in eval workspace
  (`.local/v2.2.0/survey/02_reference_repo_catalog.md` §3 P16; §2
  nearai-benchmarks entry).
- **HAL trace governance** — encrypted trace upload assumes addressable
  identity (`02_reference_repo_catalog.md` §3 P3).
- **IronClaw identity files** — capability-based per-tool identity
  (`02_reference_repo_catalog.md` §3 P19).
- **Empirical motivation** —
  `.local/v2.2.0/profile/00_baseline_report.md` §4.5, §4.8, §4.9; raw
  proof `.local/v2.2.0/benchmark/c02_id_uniqueness.txt`.

## 7. Source Files

| File                                              | Status            | Role                                                                  |
|---------------------------------------------------|:-----------------:|-----------------------------------------------------------------------|
| `src/nines/core/identity.py`                      | **shipped** (C02) | `project_fingerprint`, `format_finding_id`, `parse_finding_id`         |
| `src/nines/analyzer/agent_impact.py`              | **modified** (C02) | Six AI-prefix sites use `format_finding_id`; `analyze()` computes fp  |
| `tests/core/test_identity.py`                     | **shipped** (C02) | 23 cases incl. 2 000-path collision stress + legacy parse tests        |
| `report_metadata.id_namespace_version: int = 2`   | **shipped** (C02a) | Top-level field in `analyze --format json` output; built by `AnalysisPipeline.build_report_metadata()` |
| `src/nines/iteration/context.py`                  | *planned* (C01)   | `EvaluationContext` frozen dataclass; reuses `project_fingerprint`     |
| `src/nines/iteration/self_eval.py`                | *planned* (C01)   | `DimensionEvaluator.evaluate(ctx)` Protocol bump                       |
| `src/nines/cli/commands/self_eval.py`             | *planned* (C01)   | Builds `EvaluationContext` from CLI; wires `context_fingerprint` to JSON |
| `SelfEvalReport.context_fingerprint`              | *planned* (C01)   | Non-empty in 100 % of post-C01 runs                                    |
| `LegacyEvaluatorAdapter`                          | *planned* (C01)   | One-minor compatibility shim for external forks                         |
| `docs/migration/v2.2.0.md`                        | *planned* (C01)   | Migration note for the evaluator-Protocol break                         |
