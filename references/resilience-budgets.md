---
id: "nines/references/resilience-budgets"
version: "1.0.0"
purpose: >
  Documents NineS's wall-clock + cost budgeting and retry semantics.
  Codifies the EvoBench `ageneval-runner` budget guard and the pydantic-ai
  / coevolved "validated, pausable" agent-run paradigm, applied to NineS
  evaluators and self-eval. Load this reference when adding new evaluators,
  wiring subprocess timeouts, integrating LLM judges, or designing CI that
  must terminate within a wall-clock envelope.
triggers:
  - "budget"
  - "timeout"
  - "retry"
  - "with_retry"
  - "cost"
  - "evaluator_budget"
  - "resilience"
tier: 2
token_estimate: 1200
dependencies:
  - "nines/SKILL.md"
  - "nines/references/evaluation-framework"
  - "nines/references/iteration-protocol"
last_updated: "2026-04-18"
---

# Resilience Budgets Reference

## 1. Why This Reference Exists

NineS v3.0.0's self-eval runner (`SelfEvalRunner.run_all`) wrapped each
evaluator in a `try/except` but had no `signal.alarm`, no
`Future.result(timeout=)`, and no `asyncio.wait_for`. The empirical
evidence in `.local/v2.2.0/profile/00_baseline_report.md` §4.7 made the
cost concrete:

| Run                                                                     | Wall   | Exit          |
|-------------------------------------------------------------------------|-------:|---------------|
| `caveman_selfeval` (`--src-dir caveman/benchmarks --test-dir caveman/tests`) | 353.0 s | 137 (killed) |
| `caveman_selfeval_v2` (`--src-dir`, no `--test-dir`)                    | 195.7 s | 137 (killed)  |
| `caveman_selfeval_v3` (`--src-dir … --capability-only`)                  | 60.1 s  | 124 (timeout) |
| `caveman_selfeval_v4` (`--project-root` only — capability silently fell back to NineS) | 5.7 s | 0 |
| `ua_selfeval` (`--src-dir understand-anything-plugin --test-dir scripts`) | 210.8 s | 137 (killed) |

**Total wasted compute on hangs: 819.6 s** of wall (caveman 353 + 196 +
60, UA 211 + 60). The timeouts were not bounded by NineS itself — only
external `coreutils timeout` saved the v3 attempts. `--capability-only`
did **not** rescue the run (so the loop is in a capability evaluator,
not in hygiene).

EvoBench's `ageneval-runner/src/retry.rs` exposes `with_retry(fn,
attempts, base_backoff_ms)` and the companion `parallel.rs` wraps a
budget-aware semaphore. Pydantic-AI describes "validated, pausable"
agent runs. Coevolved's `UsagePolicy` makes time / token / dollar
budgets first-class. Together these say: **time and cost are bounded
resources, not ambient assumptions**. This reference codifies the
NineS implementation.

**Empirical evidence file motivating this reference:**
`.local/v2.2.0/profile/00_baseline_report.md` §4.7 + `_timings.txt`;
raw POC proofs `.local/v2.2.0/benchmark/c04_budget_proof.txt` and
`c05_retry_proof.txt`.

## 2. The Pattern: Bounded Execution

### Three primitives

1. **`TimeBudget(soft_seconds, hard_seconds)`** + **`evaluator_budget`**
   context manager — wraps work on a daemon thread; raises
   `EvaluatorBudgetExceeded` after `hard_seconds`; sets a cooperative
   `cancel_flag: threading.Event` for well-behaved evaluators to poll.
2. **`RetryPolicy(attempts, base_backoff_s, max_backoff_s, retry_on)`**
   + **`with_retry(fn, policy)`** — synchronous exponential-backoff
   helper for transient failures (LLM rate-limits, sandbox flakiness,
   GitHub API throttling). Re-raises non-retry-eligible exceptions
   immediately (no silent swallow per workspace rule "No Silent
   Failures").
3. **`CostBudget(token_limit, dollar_limit, time_limit_s)`** +
   **`CostExceeded`** — `add(tokens=..., dollars=..., elapsed_s=...) ->
   bool` returns `False` when exhausted; raises `CostExceeded`
   informatively for upstream `EvalRunner.run` to catch, append a
   partial-error entry, and break the outer loop.

### Combined invariants

A well-behaved evaluator opts into all three:

```python
from nines.core.budget import TimeBudget, evaluator_budget
from nines.core.retry import RetryPolicy, with_retry
from nines.core.cost_budget import CostBudget, CostExceeded

policy = RetryPolicy(attempts=cfg.eval_max_retries, base_backoff_s=0.5)
budget = TimeBudget(soft_seconds=20, hard_seconds=60)
cost = CostBudget(token_limit=10_000)

with evaluator_budget("my_dim", budget):
    result = with_retry(lambda: run_subprocess_or_api(), policy)
    cost.add(tokens=result.token_count)  # raises CostExceeded if over limit
```

The three primitives are independent — opt-in at the call site, default
no-op when the kwargs are not passed. This preserves backward
compatibility for v1 callers.

### Cooperative vs cooperative-plus-hard cancellation

**Cooperative cancellation works for IO-bound code** (HTTP requests,
async sleeps, file reads) when the evaluator polls
`cancel_flag.is_set()` between operations. **Pure-CPU Python loops are
not interruptible** under the GIL — `evaluator_budget` raises after
`hard_seconds` and the daemon thread continues to consume CPU until the
process exits. For the four `Live*` evaluators that shell out to
subprocesses, the design's POC item (§C04 "Per-evaluator subprocess
timeouts not wired") is to wire `subprocess.run(timeout=min(
dim_budget.hard_seconds, current_default))`. The full child-process
executor (which can SIGKILL hung subprocesses) is deferred to v2.3.

## 3. NineS Implementation Hooks

### Already in tree (Wave 1)

- **`src/nines/core/budget.py`** (POC for C04, ~184 lines) — exports
  `TimeBudget`, `EvaluatorBudgetExceeded`, `evaluator_budget`. Uses
  `threading.Thread(daemon=True)` per call (not
  `ThreadPoolExecutor` — daemon-flag was unreliable in some Python
  versions; see `.local/v2.2.0/benchmark/00_benchmark_report.md` §2.5
  *Unexpected finding*). Tests at `tests/core/test_budget.py` (5 cases:
  no-timeout, soft-budget warning, hard-timeout cancel, exception
  passthrough, validation rejects bad bounds).
- **`src/nines/core/retry.py`** (POC for C05, ~153 lines) — exports
  `RetryPolicy`, `with_retry`, `TransientError`. Sleep injection point
  at lines 84-150 for testing. Re-raises non-retry-eligible
  exceptions immediately (lines 141-144). Tests at
  `tests/core/test_retry.py` (7 cases).
- **`src/nines/core/cost_budget.py`** (POC for C05, ~117 lines) —
  exports `CostBudget`, `CostExceeded`. `add` raises *after* updating
  counters so the caller sees breaching totals. Tests at
  `tests/core/test_cost_budget.py` (3 cases).
- **`src/nines/iteration/self_eval.py`** (modified by C04) —
  `SelfEvalRunner.__init__` accepts `default_budget: TimeBudget`;
  `register_dimension(name, evaluator, budget=None)` allows per-dim
  overrides; `run_all` wraps each evaluator in `evaluator_budget`,
  appends `DimensionScore(value=0.0, metadata={"status": "timeout",
  ...})` on `EvaluatorBudgetExceeded`, and records the dim name in
  `report.timeouts`.
- **`src/nines/eval/runner.py`** (modified by C05) —
  `EvalRunner.__init__` accepts `retry_policy` and `cost_budget`;
  `run_single` wraps executor in `with_retry`; `run` catches
  `CostExceeded`, appends a partial-error entry, breaks the outer loop.
- **`src/nines/cli/commands/self_eval.py`** (modified by C04) —
  `--evaluator-timeout SECONDS` flag (default 60); wires to
  `TimeBudget(soft=min(20, max(1, t/2)), hard=max(1, t))`.
- **`src/nines/core/config.py`** (modified by C05) —
  `eval_max_retries` (formerly dead code, gap-analysis §1) now drives
  `RetryPolicy(attempts=cfg.eval_max_retries)` in the eval CLI.

### Wave 1 follow-up (required before v2.2.0 ships)

- **CLI JSON exposure (N1 risk).** `_build_json_output` in
  `cli/commands/self_eval.py` (lines 189-217) does NOT include
  `report.timeouts` despite `SelfEvalReport.to_dict()` exposing it.
  Operators running `nines self-eval --format json` cannot see which
  dimensions timed out. Fix: refactor `_build_json_output` to forward
  `report.to_dict()` rather than constructing a parallel payload.
- **Subprocess timeouts (N2 risk).** Wire
  `subprocess.run(timeout=min(dim_budget.hard_seconds, current_default))`
  into the four `Live*` evaluators that shell out
  (`LiveCodeCoverageEvaluator`, `LiveTestCountEvaluator`,
  `LintCleanlinessEvaluator`, `AgentAnalysisQualityEvaluator`).
- **Integration test.** Add
  `tests/iteration/test_self_eval.py::test_runner_respects_budget`
  asserting `SelfEvalRunner.run_all` actually invokes
  `evaluator_budget` and that the report has `timeouts` populated when
  budgets breach.

### Planned (Wave 1 cleanup + Wave 2)

- **`with_retry_async`** — async variant for future `asyncio`-based
  evaluators / LLM judges. Same shape as `with_retry`; uses
  `asyncio.sleep` for backoff.
- **Collector refactor.** `src/nines/collector/github.py` and
  `arxiv.py` have ad-hoc retry code (~40 lines each). Replace with
  `with_retry(... policy=RetryPolicy(attempts=cfg.collector_retries))`.
  Design predicted **−60 LOC** net.
- **Child-process executor (v2.3).** Replaces
  `threading.Thread(daemon=True)` with a subprocess executor that can
  SIGKILL pure-CPU hangs. Today the daemon thread holding
  `subprocess.run(...)` continues to consume process resources after
  `EvaluatorBudgetExceeded` is raised.

## 4. Developer Workflow — Opting a New Evaluator into Budgets

When adding a new evaluator under `src/nines/iteration/`:

1. **Choose a sensible default `TimeBudget`.** Capability evaluators
   that read in-memory data: `TimeBudget(5, 15)`. Capability evaluators
   that shell out (`Live*`): `TimeBudget(20, 60)`. Hygiene evaluators
   that run `pytest --collect-only` against foreign repos:
   `TimeBudget(60, 180)`. Document the choice in the evaluator's
   docstring.
2. **Register with the runner.** Use `runner.register_dimension(name,
   evaluator, budget=TimeBudget(...))` rather than relying on
   `default_budget`.
3. **Poll `cancel_flag` for IO-bound work.** If the evaluator does its
   own `for path in walk(...):` loop, accept `cancel_flag:
   threading.Event | None = None` as a kw-only parameter and check
   `if cancel_flag and cancel_flag.is_set(): raise
   EvaluatorBudgetExceeded(...)` at the start of each iteration.
4. **Wire subprocess timeouts.** For evaluators that shell out, set
   `subprocess.run(..., timeout=min(self._budget.hard_seconds,
   current_default))`. Catch `subprocess.TimeoutExpired` and re-raise
   as `EvaluatorBudgetExceeded` so the runner records it in `timeouts`
   uniformly.
5. **Wrap retry-eligible IO in `with_retry`.** Network calls, sandbox
   container starts, GitHub API requests should all use
   `with_retry(... policy=RetryPolicy(attempts=cfg.eval_max_retries))`.
   Define your own `TransientError` subclass for the failures you
   consider retry-eligible.
6. **Charge the cost budget.** If the evaluator consumes tokens or
   dollars (LLM calls), call `cost_budget.add(tokens=..., dollars=...)`
   after each successful call; let the resulting `CostExceeded`
   propagate to the runner's catch.
7. **Test the timeout path.** Add a `tests/iteration/test_<your_eval>.py`
   case that injects a synthetic `time.sleep` and asserts the runner
   raises `EvaluatorBudgetExceeded` and records the dim in
   `report.timeouts`.

## 5. Worked Example — `c04_budget_proof.txt`

The §4.7 evidence said `caveman_selfeval` with `--src-dir` was killed
at 195 s. After C04's runner-level wrap with `--evaluator-timeout 30`:

```
$ uv run nines self-eval \
    --project-root /home/agent/reference/caveman \
    --src-dir caveman/scripts --capability-only \
    --evaluator-timeout 30

Total dimensions evaluated: 20
Dimensions with status='timeout': 1
  - agent_analysis_quality: hard_seconds=30.0 elapsed_s=30.0

wall = 33.3s, exit=0, capability-only complete
timed-out dims: ['agent_analysis_quality']
```

**5.9× speed-up on the failure case** (195 s → 33.3 s) while emitting a
usable partial report (20 / 20 dims populated; 1 marked `status =
timeout`). The remaining N1 / N2 work is:

- **N1:** the `timeouts: ['agent_analysis_quality']` field is in the
  in-memory `SelfEvalReport.timeouts` but **not** in the CLI
  `--format json` payload. Wave 1 follow-up.
- **N2:** the daemon thread holding the runaway
  `agent_analysis_quality` evaluator's `subprocess.run` still consumes
  process resources until pytest finishes. Wave 1 follow-up wires
  `subprocess.run(timeout=min(dim_budget.hard_seconds, …))`.

## 6. References

- **EvoBench `ageneval-runner/src/retry.rs`** — `with_retry(fn, attempts,
  base_backoff_ms)` source pattern (see
  `.local/v2.2.0/survey/01_evobench_gap_analysis.md` §2 row 2.5).
- **EvoBench `ageneval-runner/src/parallel.rs`** — budget-aware
  semaphore (`02_track_b_resilience.md` C04 source paradigm).
- **Pydantic-AI durable execution** — "validated, pausable" agent runs
  (`.local/v2.2.0/survey/02_reference_repo_catalog.md` §3 P18).
- **Coevolved `UsagePolicy`** — time / token / dollar budgets as
  first-class (`02_reference_repo_catalog.md` §2 coevolved entry).
- **GSD canonical gates** — `pre-flight / revision / escalation /
  abort` (P9 in `02_reference_repo_catalog.md` §3).
- **Empirical motivation** —
  `.local/v2.2.0/profile/00_baseline_report.md` §4.7 + `_timings.txt`;
  raw POC proofs `c04_budget_proof.txt` and `c05_retry_proof.txt`.

## 7. Source Files

| File                                                | Status                | Role                                                                  |
|-----------------------------------------------------|:---------------------:|-----------------------------------------------------------------------|
| `src/nines/core/budget.py`                          | **shipped** (C04)     | `TimeBudget`, `evaluator_budget`, `EvaluatorBudgetExceeded`           |
| `src/nines/core/retry.py`                           | **shipped** (C05)     | `RetryPolicy`, `with_retry`, `TransientError`                          |
| `src/nines/core/cost_budget.py`                     | **shipped** (C05)     | `CostBudget`, `CostExceeded`                                           |
| `src/nines/iteration/self_eval.py`                  | **modified** (C04)    | `SelfEvalRunner` wraps each evaluator in `evaluator_budget`           |
| `src/nines/eval/runner.py`                          | **modified** (C05)    | `EvalRunner` accepts `retry_policy` + `cost_budget`                    |
| `src/nines/cli/commands/self_eval.py`               | **modified** (C04)    | `--evaluator-timeout` flag (CLI JSON exposure pending — N1)            |
| `src/nines/cli/commands/eval.py`                    | **modified** (C05)    | Wires `eval_max_retries` from `NinesConfig` into the runner            |
| `tests/core/test_budget.py`                         | **shipped** (C04)     | 5 cases: happy path / soft warn / hard cancel / exception / validation |
| `tests/core/test_retry.py`                          | **shipped** (C05)     | 7 cases incl. `eval_max_retries` resurrection                          |
| `tests/core/test_cost_budget.py`                    | **shipped** (C05)     | 3 cases: under-limit, exceeded, partial-results contract               |
| `tests/eval/test_runner_retry.py`                   | **shipped** (C05)     | 2 integration cases                                                     |
| `src/nines/iteration/gates.py`                      | *planned* (C07)       | `partial_run` gate fires when `report.timeouts` non-empty              |
| Subprocess timeout audit in 4 `Live*` evaluators    | *planned* (Wave 1 follow-up, N2) | Wires `subprocess.run(timeout=min(dim_budget.hard_seconds, …))` |
| `with_retry_async` in `core/retry.py`               | *planned* (Wave 1 follow-up) | Async variant with `asyncio.sleep`                                |
| Collector refactor (`collector/{github,arxiv}.py`)   | *planned* (Wave 1 follow-up) | Replaces ad-hoc retries with `with_retry` (predicted −60 LOC)    |
