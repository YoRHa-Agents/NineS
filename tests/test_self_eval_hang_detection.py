"""Joint hang-detection harness for SelfEvalRunner (C04 × C06).

Three guarantees:

1. **Runaway evaluator is aborted by the budget.**  A
   :class:`~nines.eval.mock_executor.MockEvaluator` configured with
   ``sleep_seconds=10`` registered against a ``TimeBudget(soft=1,
   hard=2)`` must trigger the C04 hard-budget breach within ≤ 4 s wall
   time.  This is the falsifiable assertion that proves the C04
   daemon-thread budget actually fires in CI — without C04, this test
   would block for 10 s (or forever if the evaluator did not return).

2. **Well-behaved evaluator runs to completion.**  Same setup but
   ``sleep_seconds=0`` — assert the run completes without recording a
   timeout.  Together with (1), this falsifies the "budget always
   fires" failure mode (i.e., budget false-positives).

3. **Exception in one evaluator does not crash the run.**  An
   evaluator that raises ``RuntimeError`` is recorded as a
   zero-value ``DimensionScore`` and subsequent evaluators still run.
   This pins the runner's existing ``except Exception`` branch in
   :py:meth:`SelfEvalRunner.run_all` so a future refactor cannot
   silently turn one failing evaluator into a whole-run failure.

Covers: C06 (golden harness) × C04 (per-evaluator wall budget).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.core.budget import TimeBudget  # noqa: E402
from nines.eval.mock_executor import MockEvaluator  # noqa: E402
from nines.iteration.self_eval import SelfEvalRunner  # noqa: E402

# ---------------------------------------------------------------------------
# Test 1 — runaway evaluator aborted by C04 budget
# ---------------------------------------------------------------------------


def test_evaluator_budget_aborts_runaway_mock_evaluator() -> None:
    """A 10s-sleeping MockEvaluator must be aborted by a 2s hard budget.

    Wall-clock budget: ≤ 4 s.  Without C04 this test would block for
    ≥ 10 s and CI would hit its per-test timeout.
    """
    runner = SelfEvalRunner()
    budget = TimeBudget(soft_seconds=1.0, hard_seconds=2.0)
    runner.register_dimension(
        "hangs",
        MockEvaluator(name="hangs", sleep_seconds=10.0),
        budget=budget,
    )

    t0 = time.monotonic()
    report = runner.run_all(version="v3.2.0-hang-test")
    elapsed = time.monotonic() - t0

    # Wall-time bound: budget hard=2s, allow generous 4s ceiling
    # to absorb thread-startup + GIL scheduling jitter.
    assert elapsed < 4.0, (
        f"Runner took {elapsed:.2f}s — C04 budget did not abort the "
        "runaway evaluator (expected < 4s, hard budget = 2s). The "
        "joint C04 × C06 hang-detection guarantee is BROKEN."
    )

    # Crucially, must NOT have waited for the full sleep.
    assert elapsed < 10.0, (
        f"Runner waited the full {elapsed:.2f}s sleep — budget did not fire at all."
    )

    # Report must record exactly which dim breached.
    assert report.timeouts == ["hangs"], f"report.timeouts={report.timeouts}, expected ['hangs']"

    # Placeholder score must encode timeout status.
    assert len(report.scores) == 1
    placeholder = report.scores[0]
    assert placeholder.name == "hangs"
    assert placeholder.value == 0.0
    assert placeholder.metadata.get("status") == "timeout", (
        f"placeholder metadata={placeholder.metadata} — expected "
        "status='timeout' (set by SelfEvalRunner on EvaluatorBudgetExceeded)"
    )
    assert placeholder.metadata.get("hard_seconds") == 2.0


# ---------------------------------------------------------------------------
# Test 2 — well-behaved evaluator finishes under budget
# ---------------------------------------------------------------------------


def test_well_behaved_mock_evaluator_completes_under_budget() -> None:
    """sleep_seconds=0 → no timeout recorded; identical setup to test 1."""
    runner = SelfEvalRunner()
    budget = TimeBudget(soft_seconds=1.0, hard_seconds=2.0)
    runner.register_dimension(
        "fast",
        MockEvaluator(
            name="fast",
            value=0.9,
            max_value=1.0,
            sleep_seconds=0.0,
        ),
        budget=budget,
    )

    t0 = time.monotonic()
    report = runner.run_all(version="v3.2.0-happy-path")
    elapsed = time.monotonic() - t0

    assert elapsed < 1.0, f"Fast evaluator wallclock {elapsed:.3f}s > 1s"
    assert report.timeouts == [], (
        f"Unexpected timeout(s) {report.timeouts} on a well-behaved evaluator"
    )
    assert len(report.scores) == 1
    score = report.scores[0]
    assert score.name == "fast"
    assert score.value == 0.9


# ---------------------------------------------------------------------------
# Test 3 — exception in one evaluator does not block downstream dims
# ---------------------------------------------------------------------------


def test_evaluator_exception_propagates_via_partial_score() -> None:
    """A raising evaluator yields a 0-score and the next dim still runs.

    Pins the existing ``except Exception`` branch in
    :py:meth:`SelfEvalRunner.run_all`: the failing dim gets a placeholder
    ``DimensionScore(value=0.0, max_value=1.0)`` and subsequent dims
    continue execution.
    """
    runner = SelfEvalRunner()
    runner.register_dimension(
        "boom",
        MockEvaluator(name="boom", raise_on_call=RuntimeError),
    )
    runner.register_dimension(
        "ok",
        MockEvaluator(
            name="ok",
            value=0.75,
            max_value=1.0,
            metadata={"unit": "ratio"},
        ),
    )

    report = runner.run_all(version="v3.2.0-error-path")

    # Both dims got recorded — the exception did not abort the run.
    assert len(report.scores) == 2
    names = [s.name for s in report.scores]
    assert names == ["boom", "ok"], f"unexpected ordering: {names}"

    # The raising dim becomes a 0-score placeholder (matches the
    # existing pattern in SelfEvalRunner.run_all's `except Exception`
    # branch — see iteration/self_eval.py).
    boom = report.scores[0]
    assert boom.name == "boom"
    assert boom.value == 0.0
    assert boom.max_value == 1.0
    # No timeout — the exception path is distinct from the timeout
    # path (which adds the dim to report.timeouts and sets
    # metadata['status'] = 'timeout').
    assert "boom" not in report.timeouts

    # Downstream dim ran with its true value.
    ok = report.scores[1]
    assert ok.name == "ok"
    assert ok.value == 0.75
    assert ok.metadata == {"unit": "ratio"}
