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
