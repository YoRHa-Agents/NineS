"""Tests for nines.iteration — self-evaluation system.

Covers:
  - SelfEvalRunner registers and runs all dimension evaluators
  - Built-in evaluators produce correct scores
  - BaselineManager save/load round-trip
  - BaselineManager.compare detects improvements and regressions
  - ScoreHistory records and returns trends
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.baseline import BaselineManager, ComparisonResult
from nines.iteration.history import ScoreHistory
from nines.iteration.self_eval import (
    CodeCoverageEvaluator,
    DimensionEvaluator,
    DimensionScore,
    ModuleCountEvaluator,
    SelfEvalReport,
    SelfEvalRunner,
    UnitTestCountEvaluator,
)


# ---------------------------------------------------------------------------
# test_self_eval_runner
# ---------------------------------------------------------------------------


def test_self_eval_runner() -> None:
    """SelfEvalRunner runs all registered evaluators and produces a report."""
    runner = SelfEvalRunner()
    runner.register_dimension("coverage", CodeCoverageEvaluator(coverage_pct=80.0))
    runner.register_dimension("tests", UnitTestCountEvaluator(count=42))
    runner.register_dimension("modules", ModuleCountEvaluator(count=10))

    report = runner.run_all(version="v1")

    assert len(report.scores) == 3
    assert report.version == "v1"
    assert report.timestamp != ""
    assert report.duration >= 0

    coverage = report.get_score("code_coverage")
    assert coverage is not None
    assert coverage.value == 80.0
    assert coverage.max_value == 100.0
    assert abs(coverage.normalized - 0.8) < 1e-6

    tests = report.get_score("test_count")
    assert tests is not None
    assert tests.value == 42.0

    modules = report.get_score("module_count")
    assert modules is not None
    assert modules.value == 10.0

    assert 0.0 <= report.overall <= 1.0


def test_self_eval_runner_no_evaluators() -> None:
    """Running with no evaluators produces an empty report."""
    runner = SelfEvalRunner()
    report = runner.run_all()
    assert report.scores == []
    assert report.overall == 0.0


def test_self_eval_runner_handles_evaluator_error() -> None:
    """A failing evaluator gets a zero score instead of crashing."""
    class FailingEvaluator:
        def evaluate(self) -> DimensionScore:
            raise RuntimeError("evaluation exploded")

    runner = SelfEvalRunner()
    runner.register_dimension("bad", FailingEvaluator())
    runner.register_dimension("good", CodeCoverageEvaluator(coverage_pct=50.0))

    report = runner.run_all()
    assert len(report.scores) == 2

    bad = report.get_score("bad")
    assert bad is not None
    assert bad.value == 0.0


# ---------------------------------------------------------------------------
# DimensionScore
# ---------------------------------------------------------------------------


def test_dimension_score_normalized() -> None:
    """DimensionScore.normalized computes value/max_value."""
    score = DimensionScore(name="test", value=3.0, max_value=10.0)
    assert abs(score.normalized - 0.3) < 1e-6


def test_dimension_score_zero_max() -> None:
    """DimensionScore.normalized handles zero max_value."""
    score = DimensionScore(name="test", value=5.0, max_value=0.0)
    assert score.normalized == 0.0


def test_dimension_score_round_trip() -> None:
    """DimensionScore to_dict/from_dict preserves data."""
    original = DimensionScore(name="x", value=7.5, max_value=10.0, metadata={"k": "v"})
    restored = DimensionScore.from_dict(original.to_dict())
    assert restored.name == original.name
    assert restored.value == original.value
    assert restored.max_value == original.max_value
    assert restored.metadata == original.metadata


# ---------------------------------------------------------------------------
# SelfEvalReport
# ---------------------------------------------------------------------------


def test_self_eval_report_round_trip() -> None:
    """SelfEvalReport to_dict/from_dict preserves data."""
    report = SelfEvalReport(
        scores=[
            DimensionScore(name="a", value=0.5, max_value=1.0),
            DimensionScore(name="b", value=80.0, max_value=100.0),
        ],
        overall=0.65,
        version="v2",
        timestamp="2026-01-01T00:00:00Z",
        duration=1.23,
    )
    restored = SelfEvalReport.from_dict(report.to_dict())
    assert len(restored.scores) == 2
    assert restored.overall == 0.65
    assert restored.version == "v2"


def test_self_eval_report_get_score_missing() -> None:
    """get_score returns None for unknown dimension."""
    report = SelfEvalReport(scores=[DimensionScore(name="x", value=1.0)])
    assert report.get_score("nonexistent") is None


# ---------------------------------------------------------------------------
# DimensionEvaluator protocol
# ---------------------------------------------------------------------------


def test_dimension_evaluator_protocol() -> None:
    """Built-in evaluators satisfy the DimensionEvaluator protocol."""
    assert isinstance(CodeCoverageEvaluator(), DimensionEvaluator)
    assert isinstance(UnitTestCountEvaluator(), DimensionEvaluator)
    assert isinstance(ModuleCountEvaluator(), DimensionEvaluator)


# ---------------------------------------------------------------------------
# test_baseline_save_load
# ---------------------------------------------------------------------------


def test_baseline_save_load(tmp_path: Path) -> None:
    """BaselineManager saves and loads a report by version."""
    manager = BaselineManager(baselines_dir=tmp_path / "baselines")

    report = SelfEvalReport(
        scores=[
            DimensionScore(name="coverage", value=80.0, max_value=100.0),
            DimensionScore(name="tests", value=42.0, max_value=42.0),
        ],
        overall=0.9,
        version="v1",
    )

    path = manager.save_baseline(report, "v1")
    assert path.is_file()

    loaded = manager.load_baseline("v1")
    assert loaded.overall == 0.9
    assert len(loaded.scores) == 2
    assert loaded.version == "v1"


def test_baseline_load_missing(tmp_path: Path) -> None:
    """Loading a non-existent baseline raises FileNotFoundError."""
    manager = BaselineManager(baselines_dir=tmp_path / "baselines")
    with pytest.raises(FileNotFoundError):
        manager.load_baseline("nonexistent")


def test_baseline_list(tmp_path: Path) -> None:
    """list_baselines returns all saved version labels."""
    manager = BaselineManager(baselines_dir=tmp_path / "baselines")
    report = SelfEvalReport(overall=0.5)

    manager.save_baseline(report, "v1")
    manager.save_baseline(report, "v2")
    manager.save_baseline(report, "v3")

    versions = manager.list_baselines()
    assert versions == ["v1", "v2", "v3"]


# ---------------------------------------------------------------------------
# test_comparison
# ---------------------------------------------------------------------------


def test_comparison() -> None:
    """BaselineManager.compare categorizes dimension changes."""
    manager = BaselineManager()

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
        overall=0.75,
    )

    result = manager.compare(current, baseline)

    assert isinstance(result, ComparisonResult)
    assert "coverage" in result.improved
    assert "tests" in result.regressed
    assert "modules" in result.unchanged
    assert result.overall_delta == pytest.approx(0.05, abs=1e-6)

    assert result.details["coverage"]["delta"] > 0
    assert result.details["tests"]["delta"] < 0
    assert abs(result.details["modules"]["delta"]) < 1e-6


def test_comparison_new_dimension() -> None:
    """A dimension present in current but not baseline counts as improved."""
    manager = BaselineManager()

    baseline = SelfEvalReport(
        scores=[DimensionScore(name="a", value=0.5, max_value=1.0)],
        overall=0.5,
    )
    current = SelfEvalReport(
        scores=[
            DimensionScore(name="a", value=0.5, max_value=1.0),
            DimensionScore(name="b", value=0.8, max_value=1.0),
        ],
        overall=0.65,
    )

    result = manager.compare(current, baseline)
    assert "b" in result.improved


# ---------------------------------------------------------------------------
# test_history_trend
# ---------------------------------------------------------------------------


def test_history_trend() -> None:
    """ScoreHistory tracks reports and returns dimension trends."""
    history = ScoreHistory()

    for i in range(5):
        report = SelfEvalReport(
            scores=[
                DimensionScore(name="coverage", value=float(50 + i * 10), max_value=100.0),
            ],
            overall=(50 + i * 10) / 100.0,
            version=f"v{i}",
        )
        history.record(report)

    assert len(history) == 5
    all_reports = history.get_all()
    assert len(all_reports) == 5

    trend = history.get_trend("coverage", window=3)
    assert len(trend) == 3
    assert trend == [0.7, 0.8, 0.9]

    full_trend = history.get_trend("coverage", window=10)
    assert len(full_trend) == 5
    assert full_trend == [0.5, 0.6, 0.7, 0.8, 0.9]


def test_history_trend_missing_dimension() -> None:
    """get_trend for a non-existent dimension returns empty list."""
    history = ScoreHistory()
    history.record(SelfEvalReport(
        scores=[DimensionScore(name="a", value=1.0)],
        overall=1.0,
    ))

    trend = history.get_trend("nonexistent")
    assert trend == []


def test_history_overall_trend() -> None:
    """get_overall_trend returns overall scores in order."""
    history = ScoreHistory()
    for val in [0.3, 0.5, 0.7]:
        history.record(SelfEvalReport(overall=val))

    trend = history.get_overall_trend(window=2)
    assert trend == [0.5, 0.7]
