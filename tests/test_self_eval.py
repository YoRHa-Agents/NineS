"""Tests for nines.iteration — self-evaluation system.

Covers:
  - SelfEvalRunner registers and runs all dimension evaluators
  - Built-in evaluators produce correct scores
  - BaselineManager save/load round-trip
  - BaselineManager.compare detects improvements and regressions
  - ScoreHistory records and returns trends
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from unittest.mock import patch

from nines.iteration.baseline import BaselineManager, ComparisonResult
from nines.iteration.history import ScoreHistory
from nines.iteration.self_eval import (
    CodeCoverageEvaluator,
    DimensionEvaluator,
    DimensionScore,
    LiveCodeCoverageEvaluator,
    LiveTestCountEvaluator,
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
    history.record(
        SelfEvalReport(
            scores=[DimensionScore(name="a", value=1.0)],
            overall=1.0,
        )
    )

    trend = history.get_trend("nonexistent")
    assert trend == []


def test_history_overall_trend() -> None:
    """get_overall_trend returns overall scores in order."""
    history = ScoreHistory()
    for val in [0.3, 0.5, 0.7]:
        history.record(SelfEvalReport(overall=val))

    trend = history.get_overall_trend(window=2)
    assert trend == [0.5, 0.7]


# ---------------------------------------------------------------------------
# LiveCodeCoverageEvaluator
# ---------------------------------------------------------------------------


def test_live_coverage_evaluator_custom_package() -> None:
    """cov_package is used in the subprocess command instead of hardcoded 'nines'."""
    fake_stdout = "Name    Stmts   Miss  Cover\nTOTAL     200     40    80%\n"
    fake_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=fake_stdout,
        stderr="",
    )
    with patch("nines.iteration.self_eval.subprocess.run", return_value=fake_result) as mock_run:
        evaluator = LiveCodeCoverageEvaluator(cov_package="devolaflow")
        score = evaluator.evaluate()

    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "--cov=devolaflow" in cmd
    assert "--cov=nines" not in cmd
    assert score.value == 80.0
    assert score.metadata["source"] == "pytest"


def test_live_coverage_evaluator_coverage_xml(tmp_path: Path) -> None:
    """coverage.xml (Cobertura format) is parsed correctly."""
    xml_content = (
        '<?xml version="1.0" ?>\n'
        '<coverage version="7.0" timestamp="1234" lines-valid="1000"'
        ' lines-covered="850" line-rate="0.85" branches-covered="0"'
        ' branches-valid="0" branch-rate="0" complexity="0">\n'
        "  <packages/>\n"
        "</coverage>\n"
    )
    cov_file = tmp_path / "coverage.xml"
    cov_file.write_text(xml_content)

    evaluator = LiveCodeCoverageEvaluator(coverage_file=cov_file)
    score = evaluator.evaluate()

    assert score.value == pytest.approx(85.0)
    assert score.metadata["source"] == "file"


def test_live_coverage_evaluator_coverage_json(tmp_path: Path) -> None:
    """coverage.json is parsed correctly."""
    import json

    cov_data = {"totals": {"percent_covered": 72.5, "covered_lines": 725, "num_statements": 1000}}
    cov_file = tmp_path / "coverage.json"
    cov_file.write_text(json.dumps(cov_data))

    evaluator = LiveCodeCoverageEvaluator(coverage_file=cov_file)
    score = evaluator.evaluate()

    assert score.value == pytest.approx(72.5)
    assert score.metadata["source"] == "file"


def test_live_coverage_evaluator_fallback(tmp_path: Path) -> None:
    """Falls back to pytest when coverage_file doesn't exist."""
    nonexistent = tmp_path / "does_not_exist.xml"
    fake_stdout = "TOTAL     100     20    80%\n"
    fake_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=fake_stdout,
        stderr="",
    )
    with patch("nines.iteration.self_eval.subprocess.run", return_value=fake_result):
        evaluator = LiveCodeCoverageEvaluator(coverage_file=nonexistent)
        score = evaluator.evaluate()

    assert score.value == 80.0
    assert score.metadata["source"] == "pytest"


# ---------------------------------------------------------------------------
# LiveTestCountEvaluator
# ---------------------------------------------------------------------------


def test_live_test_count_pytest_collect() -> None:
    """pytest --collect-only output is parsed to count tests."""
    collect_stdout = (
        "tests/test_a.py::test_one\n"
        "tests/test_a.py::test_two\n"
        "tests/test_b.py::TestClass::test_method\n"
        "tests/test_b.py::test_param[1]\n"
        "tests/test_b.py::test_param[2]\n"
        "\n"
        "5 tests collected\n"
    )
    fake_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=collect_stdout,
        stderr="",
    )
    with patch("nines.iteration.self_eval.subprocess.run", return_value=fake_result):
        evaluator = LiveTestCountEvaluator(project_root="/some/project")
        score = evaluator.evaluate()

    assert score.value == 5.0
    assert score.metadata["method"] == "pytest-collect"


def test_live_test_count_ast_fallback(tmp_path: Path) -> None:
    """Falls back to AST walk when pytest --collect-only fails."""
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_example.py").write_text(
        "def test_alpha():\n    pass\n\ndef test_beta():\n    pass\n"
    )

    with patch(
        "nines.iteration.self_eval.subprocess.run",
        side_effect=OSError("pytest not available"),
    ):
        evaluator = LiveTestCountEvaluator(test_dir=test_dir, project_root=str(tmp_path))
        score = evaluator.evaluate()

    assert score.value == 2.0
    assert score.metadata["method"] == "ast-walk"


# ---------------------------------------------------------------------------
# Release follow-up N2 — runner threads budget into evaluators that accept it
# ---------------------------------------------------------------------------


def test_runner_make_invocation_detects_budget_kwarg() -> None:
    """N2: SelfEvalRunner._make_invocation introspects evaluator.evaluate
    and binds ``budget=`` only when the signature accepts it (Approach
    A — backward compat for evaluators that predate this contract)."""
    from nines.core.budget import TimeBudget
    from nines.iteration.self_eval import (
        DimensionScore,
        SelfEvalRunner,
    )

    captured: dict[str, object] = {}

    class BudgetAwareEvaluator:
        """Modern evaluator — accepts kw-only ``budget``."""

        def evaluate(self, *, budget: TimeBudget | None = None) -> DimensionScore:
            captured["budget"] = budget
            return DimensionScore(name="ba", value=0.5)

    class LegacyEvaluator:
        """Pre-N2 evaluator with no ``budget`` kwarg."""

        def evaluate(self) -> DimensionScore:
            captured["legacy_called"] = True
            return DimensionScore(name="legacy", value=0.7)

    bud = TimeBudget(soft_seconds=2.0, hard_seconds=8.0)

    aware_call = SelfEvalRunner._make_invocation(BudgetAwareEvaluator(), bud)
    score_aware = aware_call()
    assert score_aware.value == 0.5
    assert captured["budget"] is bud, "budget not threaded into modern evaluator"

    legacy_call = SelfEvalRunner._make_invocation(LegacyEvaluator(), bud)
    score_legacy = legacy_call()
    assert score_legacy.value == 0.7
    assert captured.get("legacy_called") is True


def test_self_eval_report_to_dict_includes_timeouts_field() -> None:
    """N1 prerequisite: SelfEvalReport.to_dict already exposes
    ``timeouts`` so the CLI can simply forward the dict.  This guards
    against accidental removal of the field."""
    from nines.iteration.self_eval import (
        DimensionScore,
        SelfEvalReport,
    )

    report = SelfEvalReport(
        scores=[DimensionScore(name="a", value=0.5)],
        timeouts=["a"],
        version="v",
        timestamp="t",
        duration=1.0,
    )
    d = report.to_dict()
    assert "timeouts" in d
    assert d["timeouts"] == ["a"]
    # Round-trip safety.
    restored = SelfEvalReport.from_dict(d)
    assert restored.timeouts == ["a"]


def test_runner_records_timeouts_in_report_field() -> None:
    """N1 + N2 wire-through: a hung evaluator triggers the daemon-thread
    budget, and the dim's name lands in ``SelfEvalReport.timeouts``
    (the field that N1 then exposes via the CLI JSON)."""
    import time

    from nines.core.budget import TimeBudget
    from nines.iteration.self_eval import (
        DimensionScore,
        SelfEvalRunner,
    )

    class HungEvaluator:
        """Sleeps past the hard budget — never returns in time."""

        def evaluate(self) -> DimensionScore:
            time.sleep(2.0)
            return DimensionScore(name="hung", value=1.0)

    runner = SelfEvalRunner(
        default_budget=TimeBudget(soft_seconds=0.05, hard_seconds=0.2),
    )
    runner.register_dimension("hung", HungEvaluator())
    report = runner.run_all(version="t")

    assert "hung" in report.timeouts, f"expected 'hung' in report.timeouts, got {report.timeouts}"
    hung_score = report.get_score("hung")
    assert hung_score is not None
    assert hung_score.metadata.get("status") == "timeout"


# ---------------------------------------------------------------------------
# C01 Phase 1 — runner threads ctx, report carries fingerprint, missing src
# logs a warning
# ---------------------------------------------------------------------------


def test_runner_threads_ctx_to_evaluators(tmp_path: Path) -> None:
    """SelfEvalRunner.run_all(ctx=...) forwards ctx to ctx-aware evaluators
    and reports the ctx fingerprint on the resulting :class:`SelfEvalReport`.
    """
    from nines.iteration.context import EvaluationContext

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def main(): pass\n", encoding="utf-8")

    captured: dict[str, object] = {}

    class CtxRecorder:
        requires_context = True

        def evaluate(
            self,
            *,
            ctx=None,  # type: ignore[no-untyped-def]
        ) -> DimensionScore:
            captured["ctx"] = ctx
            return DimensionScore(name="rec", value=1.0)

    ctx = EvaluationContext.from_cli(project_root=str(tmp_path), src_dir="src")

    runner = SelfEvalRunner()
    runner.register_dimension("recorder", CtxRecorder())
    report = runner.run_all(version="ctx-thread", ctx=ctx)

    assert captured["ctx"] is ctx, "runner failed to forward ctx into evaluator"
    rec_score = report.get_score("rec")
    assert rec_score is not None
    assert rec_score.value == 1.0
    assert report.context_fingerprint == ctx.fingerprint()


def test_self_eval_report_includes_context_fingerprint(tmp_path: Path) -> None:
    """The new ``context_fingerprint`` field round-trips through
    ``to_dict``/``from_dict`` and is populated on ctx-aware runs."""
    from nines.iteration.context import EvaluationContext

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "lib.py").write_text("", encoding="utf-8")

    ctx = EvaluationContext.from_cli(project_root=str(tmp_path), src_dir="src")
    expected_fp = ctx.fingerprint()

    runner = SelfEvalRunner()
    runner.register_dimension("stub_cap", CodeCoverageEvaluator(coverage_pct=70.0))
    report = runner.run_all(version="fp-test", ctx=ctx)

    assert report.context_fingerprint == expected_fp

    # Round-trip through to_dict/from_dict preserves the field.
    payload = report.to_dict()
    assert "context_fingerprint" in payload
    assert payload["context_fingerprint"] == expected_fp

    rebuilt = SelfEvalReport.from_dict(payload)
    assert rebuilt.context_fingerprint == expected_fp

    # And a run *without* ctx leaves context_fingerprint as None.
    runner_no_ctx = SelfEvalRunner()
    runner_no_ctx.register_dimension("stub_cap", CodeCoverageEvaluator(coverage_pct=70.0))
    no_ctx_report = runner_no_ctx.run_all(version="legacy")
    assert no_ctx_report.context_fingerprint is None


def test_runner_logs_warning_on_missing_src_dir(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Loose-mode runner.run_all(ctx=None) emits a WARNING when ctx-aware
    evaluators are registered (so operators notice the silent fallback)."""

    class CtxAware:
        requires_context = True

        def evaluate(
            self,
            *,
            ctx=None,  # type: ignore[no-untyped-def]
        ) -> DimensionScore:
            return DimensionScore(name="ca", value=0.0)

    runner = SelfEvalRunner()  # default strict_ctx=False
    runner.register_dimension("ca", CtxAware())

    with caplog.at_level("WARNING", logger="nines.iteration.self_eval"):
        report = runner.run_all()  # ctx=None, loose mode

    assert any("ca" in rec.getMessage() and rec.levelname == "WARNING" for rec in caplog.records), (
        "expected a WARNING about ctx=None + ctx-aware dim; "
        f"got: {[r.getMessage() for r in caplog.records]}"
    )
    # The run still completes (ctx=None fallback).
    assert report.get_score("ca") is not None


# ---------------------------------------------------------------------------
# C08 — Weighted MetricRegistry integration
# ---------------------------------------------------------------------------


def test_runner_default_registry_populates_weighted_overall() -> None:
    """run_all() with no explicit registry loads the bundled TOML and
    fills weighted_overall + group_means + metric_weights."""
    from nines.iteration.self_eval import (
        LiveCodeCoverageEvaluator,  # noqa: F401 — kept for parity
    )

    runner = SelfEvalRunner()
    runner.register_dimension("code_coverage", CodeCoverageEvaluator(coverage_pct=80.0))
    runner.register_dimension("test_count", UnitTestCountEvaluator(count=1200))
    runner.register_dimension("module_count", ModuleCountEvaluator(count=80))

    report = runner.run_all()

    assert report.weighted_overall > 0.0, "weighted_overall should be populated"
    assert "hygiene" in report.group_means, (
        f"hygiene should appear in group_means; got {list(report.group_means)}"
    )
    # capability is excluded because no capability dim was registered
    assert "capability" not in report.group_means
    # metric_weights snapshot covers ALL bundled metrics, not just the
    # 3 we registered, so reports remain reproducible.
    assert len(report.metric_weights) >= 25, (
        f"expected >=25 metric weights from default registry, "
        f"got {len(report.metric_weights)}"
    )
    # Backward-compat: legacy unweighted overall is still reported.
    assert 0.0 < report.overall <= 1.0


def test_runner_custom_registry_overrides_default() -> None:
    """Passing a custom registry replaces the bundled defaults entirely."""
    from nines.eval.metrics_registry import MetricDefinition, MetricRegistry

    custom = MetricRegistry()
    custom.register(
        MetricDefinition(name="custom_cov", weight=1.0, group="hygiene"),
    )
    custom.register(
        MetricDefinition(name="hygiene", weight=1.0, group="_groups"),
    )
    assert custom.validate() == []

    class CustomCovEvaluator:
        def evaluate(self) -> DimensionScore:
            return DimensionScore(name="custom_cov", value=0.6, max_value=1.0)

    runner = SelfEvalRunner(registry=custom)
    runner.register_dimension("custom_cov", CustomCovEvaluator())

    report = runner.run_all()

    assert report.weighted_overall == pytest.approx(0.6)
    assert report.group_means == {"hygiene": pytest.approx(0.6)}
    assert report.metric_weights == {"custom_cov": 1.0, "hygiene": 1.0}


def test_report_to_dict_round_trip_preserves_weighted_fields() -> None:
    """SelfEvalReport.to_dict / from_dict round-trip the C08 fields."""
    report = SelfEvalReport(
        scores=[DimensionScore(name="x", value=0.5)],
        overall=0.5,
        weighted_overall=0.91,
        group_means={"capability": 0.92, "hygiene": 0.86},
        metric_weights={"x": 0.5, "y": 0.5},
    )
    data = report.to_dict()
    assert data["weighted_overall"] == pytest.approx(0.91)
    assert data["group_means"]["capability"] == pytest.approx(0.92)
    assert data["metric_weights"] == {"x": 0.5, "y": 0.5}

    restored = SelfEvalReport.from_dict(data)
    assert restored.weighted_overall == pytest.approx(0.91)
    assert restored.group_means == {
        "capability": pytest.approx(0.92),
        "hygiene": pytest.approx(0.86),
    }
    assert restored.metric_weights == {"x": 0.5, "y": 0.5}


def test_runner_invalid_registry_skips_weighted_aggregation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A registry that fails validate() leaves weighted_overall=0.0 but
    keeps the legacy overall intact (Risk-Med mitigation per design)."""
    from nines.eval.metrics_registry import MetricDefinition, MetricRegistry

    bad = MetricRegistry()
    bad.register(MetricDefinition(name="a", weight=0.4, group="capability"))
    bad.register(MetricDefinition(name="b", weight=0.3, group="capability"))
    # Sum = 0.7, fails validate()
    assert bad.validate() != []

    runner = SelfEvalRunner(registry=bad)
    runner.register_dimension("a", CodeCoverageEvaluator(coverage_pct=80.0))

    with caplog.at_level("WARNING", logger="nines.iteration.self_eval"):
        report = runner.run_all()

    assert report.weighted_overall == 0.0
    assert report.group_means == {}
    assert report.metric_weights == {}
    # Legacy unweighted overall is still computed.
    assert report.overall > 0.0
    assert any(
        "MetricRegistry.validate" in rec.getMessage() for rec in caplog.records
    ), "expected warning about validate() failures"
