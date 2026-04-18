---
id: "nines/references/cross-artifact-audit"
version: "1.0.0"
purpose: >
  Documents the cross-artifact consistency audit pattern for NineS analyzer
  outputs. Codifies the EvoBench v2.2.0 "deep cross-file data-consistency
  audit" plus the GSD canonical quality-gates taxonomy, applied to NineS
  knowledge-graph JSON, agent-impact reports, and self-eval reports. Load
  this reference when adding new analyzer outputs, building consistency
  checks, or designing release-blocking gates over published JSON.
triggers:
  - "audit"
  - "consistency"
  - "gate"
  - "verifier"
  - "cross-artifact"
tier: 2
token_estimate: 1200
dependencies:
  - "nines/SKILL.md"
  - "nines/references/analysis-pipeline"
  - "nines/references/project-identity"
last_updated: "2026-04-18"
---

# Cross-Artifact Consistency Audit Reference

## 1. Why This Reference Exists

NineS v3.0.0's analyze pipeline emits 4–5 JSON files per run (per-strategy
`analysis_report.json`, agent-impact rollups, self-eval reports) plus a
Markdown summary. Until v2.2.0 nothing checked that those files were
*mutually consistent*; the empirical evidence in
`.local/v2.2.0/profile/00_baseline_report.md` §4.1, §4.2, and §4.5 shows
this is not theoretical:

| Symptom (baseline §4)                                        | Manifested as                                                                                                                              |
|--------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| §4.1 graph verification `passed = False` on every sample     | `verification.passed = False` × 3 fixtures; 49 / 803 / 40 critical referential-integrity issues; report still emitted with no gate.        |
| §4.2 `verification.layer_coverage_pct = 100.0` tautology     | Tautology emitted alongside `graph.layers = []`; two producers (graph builder vs verifier) wrote inconsistent shapes; no audit caught it.  |
| §4.5 cross-sample finding-ID collisions                      | `AI-0000` / `AI-0001` / `AI-0002` reused across 3 samples; downstream dashboards would silently dedupe 2/3 rollups; humans found this by diff. |

The user-facing root cause is that NineS treated emission as
unconditional: build → verify → emit. EvoBench v2.2.0's CHANGELOG entry
("deep cross-file data-consistency audit") elevates audits to first-class
CI gates. GSD's gates taxonomy (`pre-flight / revision / escalation /
abort`) treats verification failures as **blocking** artifact emission,
not as a side-channel warning. This reference codifies the merged
pattern for NineS.

**Empirical evidence file motivating this reference:**
`.local/v2.2.0/profile/00_baseline_report.md` §4.1, §4.2, §4.5; raw JSON
in `profile/<sample>_graph/analysis_report.json` →
`metrics.knowledge_graph.verification`.

## 2. The Pattern: Audit-as-Gate

Three primitive operations in increasing order of strictness:

```
  +-------------------+    +---------------------+    +-----------------------+
  | (1) verify        |--->| (2) audit          |--->| (3) gate              |
  | per-artifact      |    | cross-artifact     |    | release-blocking      |
  | (within-file)     |    | (across files)      |    | (CI exit non-zero)    |
  +-------------------+    +---------------------+    +-----------------------+
```

1. **Verify (per-artifact, within-file).** A single JSON's internal
   integrity. Example: `GraphVerifier._check_referential_integrity`
   confirms every edge endpoint resolves to a node in the same file.
2. **Audit (cross-artifact).** Multiple JSONs published from the same
   run agree on cross-cutting facts. Example: a finding-ID emitted in
   `agent_impact.findings` matches one in the top-level `findings` list.
3. **Gate (release-blocking).** Wrap (1) and (2) in a state machine
   (PROPOSED → VALIDATED → APPLIED) and refuse to write the artifact —
   or refuse the CI exit code — when validation fails. CLI exposes
   `--strict-graph` / `--strict-audit` opt-out flags.

### Pre-emit verification

Verification runs **before** the report is written to disk, not after.
The `analysis_report.json` produced by `nines analyze --strategy graph`
must contain `verification.passed = True` (post-C03) by the time the
file appears under `profile/<sample>_graph/`. If verification fails, the
write is skipped (when `--strict-graph` is set, the default in v2.2.x+)
or proceeds with a clearly flagged `gate.state = REJECTED` (advisory
mode, `gates_advisory_mode = True` for one minor release).

### Fail-closed gates

The default exit code is **non-zero** when any `severity == "critical"`
issue is detected. `--no-strict-graph` exists for forensic use only —
operators should never disable strict mode in production CI. When the
gate fires:

1. The full report still writes to disk for forensic inspection.
2. `<output>/gates.jsonl` records the rejected gate with reason +
   evidence + timestamp.
3. CLI prints a one-line summary to stderr and exits with code `1`
   (or another non-zero code distinct from genuine analyzer crashes).

### Cross-file consistency checks

The `ConsistencyAuditor` (planned C10, see §3) runs five categories of
cross-file checks against a directory of analyzer outputs:

| Method                                              | What it checks                                                          | §4 gap covered |
|-----------------------------------------------------|--------------------------------------------------------------------------|:--------------:|
| `audit_finding_uniqueness(reports)`                | No two reports share a finding ID without a project_id namespace        | §4.5           |
| `audit_graph_referential_integrity(graph_report)`  | Every persisted edge endpoint resolves to a persisted node ID           | §4.1           |
| `audit_layer_field_consistency(graph_report)`      | `layer_coverage_pct > 0` requires `graph.layers != []`                  | §4.2           |
| `audit_dim_metadata_provenance(self_evals, ctxs)`  | Self-eval metadata for project A doesn't equal project B's              | §4.8           |
| `audit_cross_run_drift(reports, baseline)`         | Same fixture across N runs → divergence within `tolerance`              | §4.10 (latent) |

Each method returns `list[ConsistencyIssue(severity, category, message,
artifacts)]`. Aggregating method `run_all(report_dir) -> AuditReport`
serialises to `audit_report.json`.

## 3. NineS Implementation Hooks

### Already in tree (Wave 1)

- **`src/nines/analyzer/graph_canonicalizer.py`** — POC for C03.
  Public entry point `canonicalize_id(raw, *, project_root)` makes
  `file:` and `function:` IDs comparable across the builder and
  verifier consumer. Tests at `tests/analyzer/test_graph_canonicalizer.py`
  (17 cases including 2 verifier-integration cases).
- **`src/nines/analyzer/graph_verifier.py`** (modified) — `verify(graph,
  *, project_root)` accepts the explicit project root from the
  pipeline, canonicalises both endpoints before set-membership
  comparison. Empty-layers branch returns `0.0` correctly (see
  `c03_verification.txt` lines 28-34 ADDENDUM).
- **`src/nines/analyzer/pipeline.py`** (modified, lines ~236-238) —
  passes `project_root=str(target)` to the verifier so the canonicalizer
  always has the precise anchor.

### Planned (Wave 2 — C10)

- **`src/nines/analyzer/consistency_auditor.py`** (new) — exports
  `ConsistencyAuditor`, `ConsistencyIssue`, `AuditReport` per §2.
- **`src/nines/cli/commands/audit.py`** (new) — `nines audit
  --report-dir PATH [--baseline PATH]` CLI; emits `audit_report.json`;
  exits non-zero on critical issues (joint with C07's gate FSM).
- **`src/nines/iteration/gates.py`** (new, C07) — `QualityGateMachine`
  with `GateState(PROPOSED → VALIDATED → APPLIED → ROLLED_BACK |
  REJECTED)`; persists to `<output>/gates.jsonl`. Wires to
  `analyze.py` (graph gate), `agent_impact.py` (economics gate),
  `self_eval.py` (partial-run gate), and `iteration/planner.py`
  (improvement-plan lifecycle).

## 4. Developer Workflow — Adding a New Analyzer Output

When adding a new JSON output to the analyze / self-eval / iterate
pipelines:

1. **Identify cross-artifact invariants.** What fields must agree
   across other published JSONs? Common examples: finding IDs (must be
   globally unique post-C02), schema version (must match the parser
   contract), project fingerprint (must match `EvaluationContext`
   when C01 lands), timestamps (must be monotonic across files in the
   same run).
2. **Add a verifier method.** Either extend `GraphVerifier` (graph
   artifacts) or add a new `verify_<artifact>(report) ->
   VerificationResult` helper. Verifier checks **within-file**
   integrity only.
3. **Add an auditor method.** Extend `ConsistencyAuditor` with a new
   `audit_<invariant>(reports, ...)` method that takes multiple JSONs
   and returns `list[ConsistencyIssue]`. The auditor checks
   **across-file** integrity.
4. **Register a gate.** In the producer CLI (e.g.
   `cli/commands/analyze.py`), call `gates.propose("name",
   evidence={...})` then `gates.validate(gate, validator)`. On
   `state != VALIDATED`, fail-fast with non-zero exit.
5. **Backfill a regression test.** `tests/integration/test_consistency_audit.py`
   should include a synthetic-regression fixture that intentionally
   breaks the invariant and asserts the auditor flags it. Per
   `.local/v2.2.0/validate/02_analytical_validation.md` §C10, the POC
   plan was revised from "detect known bugs" (now fixed at the source)
   to "detect synthetic regressions".
6. **Document the fail mode.** Add an entry to
   `docs/analyzer/consistency_audit.md` (planned) listing the issue
   category, the JSON path that triggered it, and how to fix the
   producer.

## 5. Worked Example — `c03_verification.txt`

The §4.1 root cause was that `graph_decomposer.py` (producer) wrote
`file:CONTRIBUTING.md` (relative) on a node while the corresponding
edge wrote `file:/home/agent/reference/caveman/CONTRIBUTING.md`
(absolute). The verifier's `_check_referential_integrity` (line 96 in
v3.0.0) did set-membership comparison after no normalisation, so 49
edges in caveman / 803 in DevolaFlow / 40 in UA failed.

After C03's fix:

```
$ uv run nines analyze --strategy graph --target-path /home/agent/reference/caveman
caveman:
  passed=True            # was False
  critical_issues=0      # was 49
  layer_coverage_pct=100.0
  layer_count=4
  total_issues=1         # the 1 is an info-level orphan-node note
```

The fix is one canonicalizer call applied at the verifier's set-membership
boundary; full builder-side fix in `graph_decomposer.py` is Wave 1
follow-up. **N3 risk:** without the builder-side fix, any new consumer
of `KnowledgeGraph` IDs (e.g. a future pipeline writing edges to a
sidecar JSON) re-introduces the §4.1 mismatch. Mitigation: add
`_check_id_canonicalisation(graph)` to the verifier so future builder
regressions are caught even when the verifier-side fix masks them.

## 6. References

- **EvoBench v2.2.0 CHANGELOG** — "deep cross-file data-consistency audit"
  entry (see `.local/v2.2.0/survey/01_evobench_gap_analysis.md` §4 row
  "Deep cross-artifact data-consistency audit").
- **GSD canonical gates taxonomy** — `pre-flight / revision /
  escalation / abort` (see
  `.local/v2.2.0/survey/02_reference_repo_catalog.md` §3 P9
  "Spec-Driven Gates and Context-Rot Control").
- **GoEx propose → validate → commit** — separation of action proposal
  from execution (see `02_reference_repo_catalog.md` §3 P14).
- **HAL trace governance** — encrypted trace upload pattern for
  contamination control (`02_reference_repo_catalog.md` §3 P3).
- **Empirical motivation** — `.local/v2.2.0/profile/00_baseline_report.md`
  §4.1, §4.2, §4.5; raw proof `.local/v2.2.0/benchmark/c03_verification.txt`.

## 7. Source Files

| File                                              | Status     | Role                                                              |
|---------------------------------------------------|:----------:|-------------------------------------------------------------------|
| `src/nines/analyzer/graph_canonicalizer.py`       | **shipped** (C03) | Single canonicalizer for `file:` / `function:` IDs                 |
| `src/nines/analyzer/graph_verifier.py`            | **modified** (C03) | Per-artifact verification; accepts `project_root` parameter        |
| `src/nines/analyzer/pipeline.py`                  | **modified** (C03) | Threads `project_root` to the verifier                              |
| `tests/analyzer/test_graph_canonicalizer.py`      | **shipped** (C03) | 17 cases incl. 2 verifier-integration cases                        |
| `src/nines/analyzer/consistency_auditor.py`       | *planned* (C10) | Cross-artifact auditor (5 audit methods + `run_all`)               |
| `src/nines/cli/commands/audit.py`                 | *planned* (C10) | `nines audit` CLI command                                           |
| `src/nines/iteration/gates.py`                    | *planned* (C07) | `QualityGateMachine` + `GateState` + transition history            |
| `tests/integration/test_consistency_audit.py`     | *planned* (C10) | Synthetic-regression fixtures gate CI merges                        |
