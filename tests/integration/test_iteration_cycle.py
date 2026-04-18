"""Integration test: iteration cycle (self-eval -> baseline -> compare -> detect gaps).

Covers:
1. Run self-eval, save baseline
2. Run again with different scores, compare
3. Detect gaps between runs
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import json

import pytest

from nines.iteration.baseline import BaselineManager, ComparisonResult
from nines.iteration.convergence import ConvergenceChecker
from nines.iteration.gap_detector import Gap, GapAnalysis, GapDetector
from nines.iteration.self_eval import (
    CodeCoverageEvaluator,
    DimensionScore,
    ModuleCountEvaluator,
    SelfEvalReport,
    SelfEvalRunner,
    UnitTestCountEvaluator,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def baseline_dir(tmp_path: Path) -> Path:
    return tmp_path / "baselines"


@pytest.fixture()
def baseline_mgr(baseline_dir: Path) -> BaselineManager:
    return BaselineManager(baselines_dir=baseline_dir)


def _make_runner_with_scores(
    coverage: float = 80.0,
    test_count: int = 100,
    module_count: int = 20,
) -> SelfEvalRunner:
    runner = SelfEvalRunner()
    runner.register_dimension("coverage", CodeCoverageEvaluator(coverage))
    runner.register_dimension("tests", UnitTestCountEvaluator(test_count))
    runner.register_dimension("modules", ModuleCountEvaluator(module_count))
    return runner


# ---------------------------------------------------------------------------
# 1. Run self-eval, save baseline
# ---------------------------------------------------------------------------


class TestSelfEvalBaseline:
    """Run self-eval, verify report, save as baseline."""

    def test_run_self_eval_produces_report(self) -> None:
        runner = _make_runner_with_scores(coverage=85.0, test_count=50)
        report = runner.run_all(version="v1.0")

        assert isinstance(report, SelfEvalReport)
        assert len(report.scores) == 3
        assert report.overall > 0.0
        assert report.version == "v1.0"
        assert report.timestamp != ""
        assert report.duration >= 0.0

    def test_save_and_load_baseline(self, baseline_mgr: BaselineManager) -> None:
        runner = _make_runner_with_scores(coverage=80.0, test_count=100)
        report = runner.run_all(version="v1.0")

        path = baseline_mgr.save_baseline(report, "v1.0")
        assert path.exists()
        assert path.suffix == ".json"

        loaded = baseline_mgr.load_baseline("v1.0")
        assert loaded.version == "v1.0"
        assert len(loaded.scores) == len(report.scores)
        assert loaded.overall == pytest.approx(report.overall, abs=1e-6)

    def test_list_baselines(self, baseline_mgr: BaselineManager) -> None:
        runner = _make_runner_with_scores()
        for v in ["v1.0", "v1.1", "v2.0"]:
            report = runner.run_all(version=v)
            baseline_mgr.save_baseline(report, v)

        versions = baseline_mgr.list_baselines()
        assert versions == ["v1.0", "v1.1", "v2.0"]

    def test_load_nonexistent_baseline_raises(self, baseline_mgr: BaselineManager) -> None:
        with pytest.raises(FileNotFoundError):
            baseline_mgr.load_baseline("nonexistent")

    def test_baseline_json_structure(self, baseline_mgr: BaselineManager) -> None:
        runner = _make_runner_with_scores(coverage=90.0)
        report = runner.run_all(version="v1.0")
        path = baseline_mgr.save_baseline(report, "v1.0")

        data = json.loads(path.read_text(encoding="utf-8"))
        assert "scores" in data
        assert "overall" in data
        assert "version" in data
        assert data["version"] == "v1.0"


# ---------------------------------------------------------------------------
# 2. Run again, compare against baseline
# ---------------------------------------------------------------------------


class TestBaselineComparison:
    """Run eval twice with different scores, compare results."""

    def test_improvement_detected(self, baseline_mgr: BaselineManager) -> None:
        baseline_runner = _make_runner_with_scores(coverage=70.0, test_count=50)
        baseline_report = baseline_runner.run_all(version="baseline")
        baseline_mgr.save_baseline(baseline_report, "baseline")

        improved_runner = _make_runner_with_scores(coverage=90.0, test_count=80)
        improved_report = improved_runner.run_all(version="improved")

        comparison = baseline_mgr.compare(improved_report, baseline_report)
        assert isinstance(comparison, ComparisonResult)
        assert comparison.overall_delta > 0.0
        assert "code_coverage" in comparison.improved

    def test_regression_detected(self, baseline_mgr: BaselineManager) -> None:
        baseline_runner = _make_runner_with_scores(coverage=90.0, test_count=100)
        baseline_report = baseline_runner.run_all(version="baseline")

        regressed_runner = _make_runner_with_scores(coverage=60.0, test_count=50)
        regressed_report = regressed_runner.run_all(version="regressed")

        comparison = baseline_mgr.compare(regressed_report, baseline_report)
        assert comparison.overall_delta < 0.0
        assert len(comparison.regressed) > 0

    def test_no_change_detected(self, baseline_mgr: BaselineManager) -> None:
        runner = _make_runner_with_scores(coverage=80.0, test_count=100)
        report1 = runner.run_all(version="v1")
        report2 = runner.run_all(version="v2")

        comparison = baseline_mgr.compare(report2, report1)
        assert abs(comparison.overall_delta) < 1e-4
        assert len(comparison.unchanged) == 3

    def test_comparison_details_structure(self, baseline_mgr: BaselineManager) -> None:
        base = _make_runner_with_scores(coverage=70.0).run_all(version="base")
        current = _make_runner_with_scores(coverage=85.0).run_all(version="current")

        comparison = baseline_mgr.compare(current, base)
        assert isinstance(comparison.details, dict)
        for _dim, detail in comparison.details.items():
            assert "current" in detail
            assert "baseline" in detail
            assert "delta" in detail


# ---------------------------------------------------------------------------
# 3. Detect gaps between runs
# ---------------------------------------------------------------------------


class TestGapDetection:
    """Detect and prioritize gaps between eval reports."""

    def test_gap_detection_finds_regressions(self) -> None:
        baseline = SelfEvalReport(
            scores=[
                DimensionScore(name="coverage", value=90.0, max_value=100.0),
                DimensionScore(name="tests", value=100.0, max_value=100.0),
                DimensionScore(name="modules", value=20.0, max_value=20.0),
            ],
            overall=0.97,
        )
        current = SelfEvalReport(
            scores=[
                DimensionScore(name="coverage", value=70.0, max_value=100.0),
                DimensionScore(name="tests", value=100.0, max_value=100.0),
                DimensionScore(name="modules", value=15.0, max_value=20.0),
            ],
            overall=0.85,
        )

        detector = GapDetector(tolerance=0.01)
        analysis = detector.detect(current, baseline)

        assert isinstance(analysis, GapAnalysis)
        assert len(analysis.regressed) == 2
        assert len(analysis.stagnated) == 1
        assert len(analysis.priority_gaps) == 2
        assert analysis.priority_gaps[0].severity >= analysis.priority_gaps[1].severity

    def test_gap_detection_finds_improvements(self) -> None:
        baseline = SelfEvalReport(
            scores=[
                DimensionScore(name="coverage", value=60.0, max_value=100.0),
            ],
            overall=0.6,
        )
        current = SelfEvalReport(
            scores=[
                DimensionScore(name="coverage", value=95.0, max_value=100.0),
            ],
            overall=0.95,
        )

        detector = GapDetector()
        analysis = detector.detect(current, baseline)
        assert len(analysis.improved) == 1
        assert analysis.improved[0].dimension == "coverage"
        assert analysis.improved[0].delta > 0

    def test_gap_priority_ordering(self) -> None:
        baseline = SelfEvalReport(
            scores=[
                DimensionScore(name="a", value=90.0, max_value=100.0),
                DimensionScore(name="b", value=80.0, max_value=100.0),
                DimensionScore(name="c", value=70.0, max_value=100.0),
            ],
        )
        current = SelfEvalReport(
            scores=[
                DimensionScore(name="a", value=50.0, max_value=100.0),
                DimensionScore(name="b", value=70.0, max_value=100.0),
                DimensionScore(name="c", value=60.0, max_value=100.0),
            ],
        )

        detector = GapDetector()
        analysis = detector.detect(current, baseline)
        assert len(analysis.priority_gaps) > 0
        severities = [g.severity for g in analysis.priority_gaps]
        assert severities == sorted(severities, reverse=True)

    def test_gap_to_dict(self) -> None:
        gap = Gap(dimension="test", current=0.5, baseline=0.8, delta=-0.3, severity=0.3)
        d = gap.to_dict()
        assert d["dimension"] == "test"
        assert d["severity"] == 0.3

    def test_gap_analysis_to_dict(self) -> None:
        analysis = GapAnalysis(
            improved=[Gap(dimension="a", current=0.9, baseline=0.7, delta=0.2)],
            regressed=[Gap(dimension="b", current=0.5, baseline=0.8, delta=-0.3, severity=0.3)],
        )
        d = analysis.to_dict()
        assert len(d["improved"]) == 1
        assert len(d["regressed"]) == 1


# ---------------------------------------------------------------------------
# Full cycle: eval -> baseline -> eval -> compare -> gaps
# ---------------------------------------------------------------------------


class TestFullIterationCycle:
    """Complete iteration cycle integration test."""

    def test_full_cycle(self, baseline_mgr: BaselineManager) -> None:
        report_v1 = SelfEvalReport(
            scores=[
                DimensionScore(name="code_coverage", value=70.0, max_value=100.0),
                DimensionScore(name="test_count", value=50.0, max_value=100.0),
                DimensionScore(name="module_count", value=15.0, max_value=20.0),
            ],
            overall=0.6,
            version="v1.0",
        )
        baseline_mgr.save_baseline(report_v1, "v1.0")

        report_v2 = SelfEvalReport(
            scores=[
                DimensionScore(name="code_coverage", value=85.0, max_value=100.0),
                DimensionScore(name="test_count", value=80.0, max_value=100.0),
                DimensionScore(name="module_count", value=15.0, max_value=20.0),
            ],
            overall=0.8,
            version="v2.0",
        )

        comparison = baseline_mgr.compare(report_v2, report_v1)
        assert comparison.overall_delta > 0.0

        detector = GapDetector()
        analysis = detector.detect(report_v2, report_v1)
        assert len(analysis.improved) >= 2
        assert len(analysis.regressed) == 0

        baseline_mgr.save_baseline(report_v2, "v2.0")
        versions = baseline_mgr.list_baselines()
        assert "v1.0" in versions
        assert "v2.0" in versions

    def test_cycle_with_regression_and_recovery(
        self,
        baseline_mgr: BaselineManager,
    ) -> None:
        r1 = _make_runner_with_scores(coverage=80.0, test_count=100).run_all(version="v1")
        baseline_mgr.save_baseline(r1, "v1")

        r2 = _make_runner_with_scores(coverage=60.0, test_count=80).run_all(version="v2")
        comparison_12 = baseline_mgr.compare(r2, r1)
        assert comparison_12.overall_delta < 0.0

        detector = GapDetector()
        gaps_12 = detector.detect(r2, r1)
        assert len(gaps_12.regressed) > 0

        r3 = _make_runner_with_scores(coverage=90.0, test_count=120).run_all(version="v3")
        comparison_32 = baseline_mgr.compare(r3, r2)
        assert comparison_32.overall_delta > 0.0

        gaps_31 = detector.detect(r3, r1)
        assert len(gaps_31.improved) > 0


class TestConvergenceCheck:
    """Convergence checking across iteration history."""

    def test_convergence_when_stable(self) -> None:
        checker = ConvergenceChecker(window_size=5, min_rounds=3)
        scores = [0.85, 0.86, 0.855, 0.858]
        result = checker.check(scores, threshold=0.05)
        assert result.converged is True
        assert result.variance < 0.05

    def test_not_converged_when_volatile(self) -> None:
        checker = ConvergenceChecker(window_size=5, min_rounds=3)
        scores = [0.5, 0.7, 0.6, 0.8]
        result = checker.check(scores, threshold=0.001)
        assert result.converged is False

    def test_not_converged_insufficient_rounds(self) -> None:
        checker = ConvergenceChecker(window_size=5, min_rounds=5)
        scores = [0.85, 0.86]
        result = checker.check(scores, threshold=0.05)
        assert result.converged is False
        assert result.rounds_checked == 2

    def test_convergence_result_to_dict(self) -> None:
        from nines.iteration.convergence import ConvergenceResult

        cr = ConvergenceResult(converged=True, variance=0.001, rounds_checked=5, mean=0.85)
        d = cr.to_dict()
        assert d["converged"] is True
        assert d["mean"] == 0.85


class TestDimensionScoreDetails:
    """DimensionScore edge cases."""

    def test_normalized_zero_max(self) -> None:
        ds = DimensionScore(name="test", value=5.0, max_value=0.0)
        assert ds.normalized == 0.0

    def test_to_dict_includes_normalized(self) -> None:
        ds = DimensionScore(name="test", value=8.0, max_value=10.0)
        d = ds.to_dict()
        assert d["normalized"] == pytest.approx(0.8)

    def test_from_dict_round_trip(self) -> None:
        ds = DimensionScore(name="cov", value=75.0, max_value=100.0, metadata={"unit": "%"})
        restored = DimensionScore.from_dict(ds.to_dict())
        assert restored.name == "cov"
        assert restored.value == 75.0
        assert restored.metadata["unit"] == "%"


class TestSelfEvalReport:
    """SelfEvalReport edge cases."""

    def test_get_score_found(self) -> None:
        report = SelfEvalReport(
            scores=[
                DimensionScore(name="a", value=0.5),
                DimensionScore(name="b", value=0.8),
            ],
        )
        assert report.get_score("a").value == 0.5
        assert report.get_score("b").value == 0.8

    def test_get_score_not_found(self) -> None:
        report = SelfEvalReport(scores=[DimensionScore(name="a", value=0.5)])
        assert report.get_score("nonexistent") is None

    def test_report_to_dict_round_trip(self) -> None:
        report = SelfEvalReport(
            scores=[DimensionScore(name="cov", value=80.0, max_value=100.0)],
            overall=0.8,
            version="v1",
            timestamp="2024-01-01T00:00:00Z",
            duration=1.5,
        )
        restored = SelfEvalReport.from_dict(report.to_dict())
        assert restored.version == "v1"
        assert restored.overall == pytest.approx(0.8)
        assert len(restored.scores) == 1

    def test_comparison_result_to_dict(self) -> None:
        cr = ComparisonResult(
            improved=["a", "b"],
            regressed=["c"],
            unchanged=["d"],
            overall_delta=0.1,
            details={"a": {"current": 0.9, "baseline": 0.7, "delta": 0.2}},
        )
        d = cr.to_dict()
        assert d["improved"] == ["a", "b"]
        assert d["overall_delta"] == 0.1
