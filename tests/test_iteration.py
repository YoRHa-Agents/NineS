"""Tests for nines.iteration — self-iteration engine.

Covers:
  - GapDetector categorizes improved/regressed/stagnated dimensions
  - GapDetector sorts priority_gaps by severity
  - ImprovementPlanner maps gaps to suggestions
  - ConvergenceChecker detects convergence via variance
  - ConvergenceChecker rejects insufficient data
  - IterationTracker lifecycle and progress reporting
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.convergence import ConvergenceChecker, ConvergenceResult
from nines.iteration.gap_detector import Gap, GapAnalysis, GapDetector
from nines.iteration.planner import ImprovementPlan, ImprovementPlanner
from nines.iteration.self_eval import DimensionScore, SelfEvalReport
from nines.iteration.tracker import IterationTracker, ProgressReport

# ---------------------------------------------------------------------------
# test_gap_detection
# ---------------------------------------------------------------------------


def test_gap_detection() -> None:
    """GapDetector categorizes dimensions into improved/regressed/stagnated."""
    baseline = SelfEvalReport(
        scores=[
            DimensionScore(name="coverage", value=80.0, max_value=100.0),
            DimensionScore(name="tests", value=30.0, max_value=50.0),
            DimensionScore(name="modules", value=10.0, max_value=10.0),
        ],
        overall=0.7,
    )

    current = SelfEvalReport(
        scores=[
            DimensionScore(name="coverage", value=90.0, max_value=100.0),
            DimensionScore(name="tests", value=20.0, max_value=50.0),
            DimensionScore(name="modules", value=10.0, max_value=10.0),
        ],
        overall=0.73,
    )

    detector = GapDetector(tolerance=0.01)
    analysis = detector.detect(current, baseline)

    assert isinstance(analysis, GapAnalysis)

    improved_dims = [g.dimension for g in analysis.improved]
    assert "coverage" in improved_dims

    regressed_dims = [g.dimension for g in analysis.regressed]
    assert "tests" in regressed_dims

    stagnated_dims = [g.dimension for g in analysis.stagnated]
    assert "modules" in stagnated_dims


def test_gap_priority_ordering() -> None:
    """priority_gaps are sorted by severity (worst regression first)."""
    baseline = SelfEvalReport(
        scores=[
            DimensionScore(name="a", value=0.7, max_value=1.0),
            DimensionScore(name="b", value=0.8, max_value=1.0),
            DimensionScore(name="c", value=0.9, max_value=1.0),
        ],
        overall=0.8,
    )

    current = SelfEvalReport(
        scores=[
            DimensionScore(name="a", value=0.5, max_value=1.0),
            DimensionScore(name="b", value=0.7, max_value=1.0),
            DimensionScore(name="c", value=0.3, max_value=1.0),
        ],
        overall=0.5,
    )

    detector = GapDetector(tolerance=0.01)
    analysis = detector.detect(current, baseline)

    assert len(analysis.priority_gaps) == 3
    assert analysis.priority_gaps[0].dimension == "c"
    assert analysis.priority_gaps[0].severity > analysis.priority_gaps[1].severity


def test_gap_no_regression() -> None:
    """When everything improves, priority_gaps is empty."""
    baseline = SelfEvalReport(
        scores=[DimensionScore(name="x", value=0.5, max_value=1.0)],
        overall=0.5,
    )
    current = SelfEvalReport(
        scores=[DimensionScore(name="x", value=0.9, max_value=1.0)],
        overall=0.9,
    )

    detector = GapDetector()
    analysis = detector.detect(current, baseline)

    assert len(analysis.improved) == 1
    assert len(analysis.regressed) == 0
    assert len(analysis.priority_gaps) == 0


def test_gap_to_dict() -> None:
    """GapAnalysis.to_dict serializes correctly."""
    gap = Gap(dimension="x", current=0.5, baseline=0.8, delta=-0.3, severity=0.3)
    d = gap.to_dict()
    assert d["dimension"] == "x"
    assert d["severity"] == 0.3


# ---------------------------------------------------------------------------
# test_improvement_planning
# ---------------------------------------------------------------------------


def test_improvement_planning() -> None:
    """ImprovementPlanner generates ordered suggestions from gap analysis."""
    analysis = GapAnalysis(
        regressed=[
            Gap(dimension="tests", current=0.4, baseline=0.6, delta=-0.2, severity=0.2),
            Gap(dimension="coverage", current=0.3, baseline=0.8, delta=-0.5, severity=0.5),
        ],
        priority_gaps=[
            Gap(dimension="coverage", current=0.3, baseline=0.8, delta=-0.5, severity=0.5),
            Gap(dimension="tests", current=0.4, baseline=0.6, delta=-0.2, severity=0.2),
        ],
        stagnated=[
            Gap(dimension="modules", current=0.5, baseline=0.5, delta=0.0, severity=0.0),
        ],
    )

    planner = ImprovementPlanner()
    plan = planner.plan(analysis)

    assert isinstance(plan, ImprovementPlan)
    assert plan.total_gaps == 3
    assert len(plan.suggestions) == 3

    assert plan.suggestions[0].dimension == "coverage"
    assert plan.suggestions[0].priority == 1
    assert plan.suggestions[0].estimated_effort == "high"

    assert plan.suggestions[1].dimension == "tests"
    assert plan.suggestions[1].priority == 2
    assert plan.suggestions[1].estimated_effort == "medium"

    stagnated_suggestion = plan.suggestions[2]
    assert stagnated_suggestion.dimension == "modules"
    assert "no progress" in stagnated_suggestion.action


def test_improvement_plan_empty_gaps() -> None:
    """Empty gap analysis produces an empty plan."""
    planner = ImprovementPlanner()
    plan = planner.plan(GapAnalysis())

    assert plan.total_gaps == 0
    assert plan.suggestions == []


def test_improvement_plan_to_dict() -> None:
    """ImprovementPlan.to_dict serializes correctly."""
    plan = ImprovementPlan(total_gaps=1)
    d = plan.to_dict()
    assert d["total_gaps"] == 1
    assert d["suggestions"] == []


# ---------------------------------------------------------------------------
# test_convergence_check
# ---------------------------------------------------------------------------


def test_convergence_check() -> None:
    """ConvergenceChecker detects stable sequences."""
    checker = ConvergenceChecker(window_size=5, min_rounds=3)

    stable = [0.80, 0.81, 0.80, 0.81, 0.80]
    result = checker.check(stable, threshold=0.01)

    assert isinstance(result, ConvergenceResult)
    assert result.converged is True
    assert result.variance < 0.01
    assert result.rounds_checked == 5


def test_convergence_unstable() -> None:
    """ConvergenceChecker rejects unstable sequences."""
    checker = ConvergenceChecker(window_size=5, min_rounds=3)

    unstable = [0.1, 0.5, 0.9, 0.2, 0.8]
    result = checker.check(unstable, threshold=0.01)

    assert result.converged is False
    assert result.variance > 0.01


def test_convergence_insufficient_data() -> None:
    """Not enough rounds returns not-converged with infinite variance."""
    checker = ConvergenceChecker(window_size=5, min_rounds=3)

    short = [0.5, 0.5]
    result = checker.check(short, threshold=0.05)

    assert result.converged is False
    assert result.variance == float("inf")
    assert result.rounds_checked == 2


def test_convergence_exact_threshold() -> None:
    """Variance equal to threshold counts as converged."""
    checker = ConvergenceChecker(window_size=3, min_rounds=3)

    constant = [0.5, 0.5, 0.5]
    result = checker.check(constant, threshold=0.0)

    assert result.converged is True
    assert result.variance == 0.0
    assert result.rounds_checked == 3


def test_convergence_window_smaller_than_history() -> None:
    """Only the last window_size values are considered."""
    checker = ConvergenceChecker(window_size=3, min_rounds=3)

    # First 5 are wildly unstable, last 3 are stable
    history = [0.1, 0.9, 0.2, 0.8, 0.5, 0.50, 0.50, 0.50]
    result = checker.check(history, threshold=0.01)

    assert result.converged is True
    assert result.rounds_checked == 3


def test_convergence_result_to_dict() -> None:
    """ConvergenceResult.to_dict serializes correctly."""
    result = ConvergenceResult(converged=True, variance=0.001, rounds_checked=5, mean=0.8)
    d = result.to_dict()
    assert d["converged"] is True
    assert d["variance"] == 0.001
    assert d["mean"] == 0.8


# ---------------------------------------------------------------------------
# IterationTracker
# ---------------------------------------------------------------------------


def test_iteration_tracker_lifecycle() -> None:
    """IterationTracker tracks start/complete cycle and reports progress."""
    tracker = IterationTracker()

    tracker.start_iteration("v1")
    report_v1 = SelfEvalReport(
        scores=[DimensionScore(name="x", value=0.5, max_value=1.0)],
        overall=0.5,
    )
    tracker.complete_iteration(report_v1)

    tracker.start_iteration("v2")
    report_v2 = SelfEvalReport(
        scores=[DimensionScore(name="x", value=0.7, max_value=1.0)],
        overall=0.7,
    )
    tracker.complete_iteration(report_v2)

    progress = tracker.get_progress()
    assert isinstance(progress, ProgressReport)
    assert progress.total_iterations == 2
    assert progress.current_version == "v2"
    assert progress.improving is True
    assert progress.best_score == 0.7
    assert progress.overall_trend == [0.5, 0.7]


def test_iteration_tracker_empty_progress() -> None:
    """Empty tracker returns default ProgressReport."""
    tracker = IterationTracker()
    progress = tracker.get_progress()
    assert progress.total_iterations == 0
    assert progress.overall_trend == []


def test_iteration_tracker_complete_without_start() -> None:
    """Completing without starting raises OrchestrationError."""
    from nines.core.errors import OrchestrationError

    tracker = IterationTracker()
    with pytest.raises(OrchestrationError, match="No iteration"):
        tracker.complete_iteration(SelfEvalReport())


def test_iteration_tracker_regression() -> None:
    """Tracker detects when latest iteration regressed."""
    tracker = IterationTracker()

    tracker.start_iteration("v1")
    tracker.complete_iteration(SelfEvalReport(overall=0.8))

    tracker.start_iteration("v2")
    tracker.complete_iteration(SelfEvalReport(overall=0.6))

    progress = tracker.get_progress()
    assert progress.improving is False
    assert progress.best_score == 0.8


# ---------------------------------------------------------------------------
# C07 — ImprovementPlan.gate_results integration (Step 4 / planner)
# ---------------------------------------------------------------------------


def test_improvement_plan_records_gate_results() -> None:
    """ImprovementPlan.gate_results round-trips through to_dict."""
    from nines.iteration.gates import GateResult, GateStatus

    g1 = GateResult(
        gate_name="self_eval_coverage",
        status=GateStatus.PASSED,
        metric_name="overall",
        metric_value=0.92,
        threshold=0.85,
        verdict="overall=0.92 >= threshold=0.85",
        severity="info",
        metadata={"dim_count": 5},
    )
    g2 = GateResult(
        gate_name="regression",
        status=GateStatus.FAILED,
        metric_name="overall_regression_delta",
        metric_value=0.10,
        threshold=0.05,
        verdict="overall=0.80 dropped by 0.10 vs trailing mean 0.90",
        severity="warn",
        metadata={"history_size": 3},
    )

    plan = ImprovementPlan(
        suggestions=[],
        total_gaps=0,
        gate_results=[g1, g2],
    )

    assert len(plan.gate_results) == 2
    assert plan.gate_results[0].gate_name == "self_eval_coverage"
    assert plan.gate_results[1].status == GateStatus.FAILED

    serialised = plan.to_dict()
    assert "gate_results" in serialised
    assert len(serialised["gate_results"]) == 2
    assert serialised["gate_results"][1]["status"] == "failed"
    assert serialised["gate_results"][1]["severity"] == "warn"


def test_planner_create_plan_accepts_gate_results() -> None:
    """ImprovementPlanner.create_plan attaches gate_results to the plan."""
    from nines.iteration.gates import GateResult, GateStatus

    analysis = GapAnalysis(
        regressed=[
            Gap(
                dimension="coverage",
                current=0.3,
                baseline=0.8,
                delta=-0.5,
                severity=0.5,
            ),
        ],
        priority_gaps=[
            Gap(
                dimension="coverage",
                current=0.3,
                baseline=0.8,
                delta=-0.5,
                severity=0.5,
            ),
        ],
    )

    g_pass = GateResult(
        gate_name="self_eval_coverage",
        status=GateStatus.PASSED,
        metric_name="overall",
        metric_value=0.90,
        threshold=0.85,
        verdict="overall=0.90 >= threshold=0.85",
        severity="info",
        metadata={},
    )

    planner = ImprovementPlanner()
    plan = planner.create_plan(analysis, gate_results=[g_pass])

    # Suggestion logic is unchanged - gate_results is a parallel channel.
    assert len(plan.suggestions) == 1
    assert plan.suggestions[0].dimension == "coverage"
    # Gate channel populated.
    assert len(plan.gate_results) == 1
    assert plan.gate_results[0].gate_name == "self_eval_coverage"

    # ``create_plan`` accepts a None analysis and still records gates.
    empty_with_gate = planner.create_plan(gate_results=[g_pass])
    assert empty_with_gate.suggestions == []
    assert empty_with_gate.total_gaps == 0
    assert len(empty_with_gate.gate_results) == 1


# ---------------------------------------------------------------------------
# C07 — IterationTracker.gate history (Step 4 / tracker)
# ---------------------------------------------------------------------------


def test_tracker_records_gate_results_per_version() -> None:
    """IterationTracker.record_gate_results stores results per version."""
    from nines.iteration.gates import GateResult, GateStatus

    tracker = IterationTracker()

    g_v1 = GateResult(
        gate_name="self_eval_coverage",
        status=GateStatus.PASSED,
        metric_name="overall",
        metric_value=0.92,
        threshold=0.85,
        verdict="ok",
        severity="info",
        metadata={},
    )
    g_v2 = GateResult(
        gate_name="self_eval_coverage",
        status=GateStatus.FAILED,
        metric_name="overall",
        metric_value=0.50,
        threshold=0.85,
        verdict="below",
        severity="warn",
        metadata={},
    )

    tracker.record_gate_results("v1", [g_v1])
    tracker.record_gate_results("v2", [g_v2])

    v1_history = tracker.gate_history("v1")
    v2_history = tracker.gate_history("v2")
    missing_history = tracker.gate_history("v9")

    assert len(v1_history) == 1
    assert v1_history[0].gate_name == "self_eval_coverage"
    assert v1_history[0].status == GateStatus.PASSED

    assert len(v2_history) == 1
    assert v2_history[0].status == GateStatus.FAILED

    # Unknown versions produce empty list (not KeyError).
    assert missing_history == []

    # Empty version label is rejected.
    with pytest.raises(ValueError, match="non-empty"):
        tracker.record_gate_results("", [g_v1])


def test_tracker_gate_history_returns_chronological() -> None:
    """Multiple record calls for the same version preserve append order."""
    from nines.iteration.gates import GateResult, GateStatus

    tracker = IterationTracker()

    first_batch = [
        GateResult(
            gate_name=f"gate_{i}",
            status=GateStatus.PASSED,
            metric_name="metric",
            metric_value=float(i),
            threshold=0.0,
            verdict=f"first batch #{i}",
            severity="info",
            metadata={"order": i},
        )
        for i in range(3)
    ]
    second_batch = [
        GateResult(
            gate_name=f"gate_{i}",
            status=GateStatus.FAILED,
            metric_name="metric",
            metric_value=float(i + 100),
            threshold=0.0,
            verdict=f"second batch #{i}",
            severity="warn",
            metadata={"order": i + 100},
        )
        for i in range(2)
    ]

    tracker.record_gate_results("v1", first_batch)
    tracker.record_gate_results("v1", second_batch)

    history = tracker.gate_history("v1")
    assert len(history) == 5
    # First batch precedes second batch.
    assert history[0].metadata["order"] == 0
    assert history[1].metadata["order"] == 1
    assert history[2].metadata["order"] == 2
    assert history[3].metadata["order"] == 100
    assert history[4].metadata["order"] == 101

    # Re-querying must return a fresh list (mutating it should not
    # corrupt the tracker state).
    history.append(
        GateResult(
            gate_name="poison",
            status=GateStatus.PASSED,
            metric_name="x",
            metric_value=0.0,
            threshold=0.0,
            verdict="external mutation attempt",
            severity="info",
            metadata={},
        )
    )
    assert len(tracker.gate_history("v1")) == 5
