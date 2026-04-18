"""Tests for nines.iteration.v1_evaluators — V1 scoring dimension evaluators.

Covers:
  - ScoringAccuracyEvaluator (D01) validates scoring against golden test set
  - ReliabilityEvaluator (D03) checks deterministic scoring consistency
  - ScorerAgreementEvaluator (D05) measures ExactScorer/FuzzyScorer agreement
  - All evaluators conform to the DimensionEvaluator protocol
  - Golden task loading works correctly
  - Error handling for missing/empty directories
  - Runner integration
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.self_eval import DimensionEvaluator, DimensionScore
from nines.iteration.v1_evaluators import (
    ReliabilityEvaluator,
    ScorerAgreementEvaluator,
    ScoringAccuracyEvaluator,
    load_golden_tasks,
)

GOLDEN_DIR = Path("data/golden_test_set")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [ScoringAccuracyEvaluator, ReliabilityEvaluator, ScorerAgreementEvaluator],
)
def test_protocol_conformance(cls: type) -> None:
    """Every evaluator satisfies the DimensionEvaluator protocol."""
    inst = cls()
    assert isinstance(inst, DimensionEvaluator)


# ---------------------------------------------------------------------------
# load_golden_tasks
# ---------------------------------------------------------------------------


def test_load_golden_tasks_from_real_dir() -> None:
    """Golden tasks load from the real data/golden_test_set directory."""
    tasks = load_golden_tasks(GOLDEN_DIR)
    assert len(tasks) >= 5
    for task in tasks:
        assert "id" in task
        assert "source" in task
        assert "expected" in task
        assert "expected_score" in task
        assert "scorer" in task


def test_load_golden_tasks_missing_dir(tmp_path: Path) -> None:
    """Returns empty list for a non-existent directory."""
    tasks = load_golden_tasks(tmp_path / "nonexistent")
    assert tasks == []


def test_load_golden_tasks_empty_dir(tmp_path: Path) -> None:
    """Returns empty list for a directory with no TOML files."""
    tasks = load_golden_tasks(tmp_path)
    assert tasks == []


def test_load_golden_tasks_skips_no_golden_section(tmp_path: Path) -> None:
    """Files without [task.golden] are silently skipped."""
    (tmp_path / "no_golden.toml").write_text(
        '[task]\nid = "t1"\n[task.input]\nsource = "x"\n[task.expected]\nvalue = "y"\n'
    )
    tasks = load_golden_tasks(tmp_path)
    assert tasks == []


def test_load_golden_tasks_skips_malformed(tmp_path: Path) -> None:
    """Malformed TOML files are skipped without crashing."""
    (tmp_path / "bad.toml").write_text("this is [[[ not valid toml")
    tasks = load_golden_tasks(tmp_path)
    assert tasks == []


def _write_golden_task(
    directory: Path,
    name: str,
    source: str,
    expected: str,
    expected_score: float,
    scorer: str = "exact",
) -> Path:
    """Helper to write a minimal golden task TOML file."""
    content = (
        f'[task]\nid = "{name}"\nname = "{name}"\n'
        f'dimension = "test"\ndifficulty = 1\n\n'
        f'[task.input]\ntype = "code"\nlanguage = "python"\n'
        f'source = "{source}"\n\n'
        f'[task.expected]\ntype = "text"\nvalue = "{expected}"\n\n'
        f"[task.golden]\nexpected_score = {expected_score}\n"
        f'scorer = "{scorer}"\n'
    )
    path = directory / f"{name}.toml"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# ScoringAccuracyEvaluator (D01)
# ---------------------------------------------------------------------------


def test_scoring_accuracy_with_real_golden_set() -> None:
    """ScoringAccuracyEvaluator loads real golden tasks and produces a score."""
    evaluator = ScoringAccuracyEvaluator(golden_dir=GOLDEN_DIR)
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "scoring_accuracy"
    assert score.max_value == 1.0
    assert 0.0 <= score.value <= 1.0
    assert score.metadata["total_tasks"] >= 5


def test_scoring_accuracy_all_match(tmp_path: Path) -> None:
    """Accuracy is 1.0 when all scores match golden expectations."""
    _write_golden_task(tmp_path, "t1", "hello", "hello", 1.0)
    _write_golden_task(tmp_path, "t2", "foo", "bar", 0.0)

    evaluator = ScoringAccuracyEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 1.0
    assert score.metadata["accurate_tasks"] == 2
    assert score.metadata["total_tasks"] == 2


def test_scoring_accuracy_partial_match(tmp_path: Path) -> None:
    """Accuracy reflects correct fraction when some scores mismatch."""
    _write_golden_task(tmp_path, "t1", "hello", "hello", 1.0)
    _write_golden_task(tmp_path, "t2", "foo", "bar", 1.0)

    evaluator = ScoringAccuracyEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 0.5
    assert score.metadata["accurate_tasks"] == 1


def test_scoring_accuracy_missing_dir(tmp_path: Path) -> None:
    """Score is 0.0 when golden directory doesn't exist."""
    evaluator = ScoringAccuracyEvaluator(golden_dir=tmp_path / "nope")
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


def test_scoring_accuracy_fuzzy_scorer(tmp_path: Path) -> None:
    """Fuzzy scorer golden tasks are handled correctly."""
    _write_golden_task(tmp_path, "t1", "hello world", "hello world", 1.0, scorer="fuzzy")

    evaluator = ScoringAccuracyEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 1.0


# ---------------------------------------------------------------------------
# ReliabilityEvaluator (D03)
# ---------------------------------------------------------------------------


def test_reliability_with_real_golden_set() -> None:
    """ReliabilityEvaluator loads real golden tasks and checks consistency."""
    evaluator = ReliabilityEvaluator(golden_dir=GOLDEN_DIR)
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "scoring_reliability"
    assert score.max_value == 1.0
    assert score.value == 1.0, "ExactScorer should be perfectly deterministic"
    assert score.metadata["runs_per_task"] == 3


def test_reliability_all_consistent(tmp_path: Path) -> None:
    """Consistency is 1.0 when all repeat runs agree."""
    _write_golden_task(tmp_path, "t1", "ok", "ok", 1.0)
    _write_golden_task(tmp_path, "t2", "x", "y", 0.0)

    evaluator = ReliabilityEvaluator(golden_dir=tmp_path, runs=3)
    score = evaluator.evaluate()

    assert score.value == 1.0
    assert score.metadata["consistent_tasks"] == 2


def test_reliability_missing_dir(tmp_path: Path) -> None:
    """Score is 0.0 when golden directory doesn't exist."""
    evaluator = ReliabilityEvaluator(golden_dir=tmp_path / "nope")
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


def test_reliability_respects_max_tasks(tmp_path: Path) -> None:
    """Only processes up to max_tasks."""
    for i in range(10):
        _write_golden_task(tmp_path, f"t{i}", "a", "a", 1.0)

    evaluator = ReliabilityEvaluator(golden_dir=tmp_path, max_tasks=3)
    score = evaluator.evaluate()

    assert score.metadata["total_tasks"] == 3


# ---------------------------------------------------------------------------
# ScorerAgreementEvaluator (D05)
# ---------------------------------------------------------------------------


def test_scorer_agreement_with_real_golden_set() -> None:
    """ScorerAgreementEvaluator loads real golden tasks and computes agreement."""
    evaluator = ScorerAgreementEvaluator(golden_dir=GOLDEN_DIR)
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "scorer_agreement"
    assert score.max_value == 1.0
    assert 0.0 <= score.value <= 1.0
    assert score.metadata["total_tasks"] >= 5


def test_scorer_agreement_perfect_match(tmp_path: Path) -> None:
    """Agreement is 1.0 when both scorers agree on all tasks."""
    _write_golden_task(tmp_path, "t1", "same", "same", 1.0)
    _write_golden_task(tmp_path, "t2", "x", "y", 0.0)

    evaluator = ScorerAgreementEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 1.0
    assert score.metadata["agreed_tasks"] == 2


def test_scorer_agreement_partial(tmp_path: Path) -> None:
    """Agreement reflects the fraction of tasks where scorers agree."""
    _write_golden_task(tmp_path, "t1", "same", "same", 1.0)
    _write_golden_task(tmp_path, "t2", "abc", "abd", 0.0)

    evaluator = ScorerAgreementEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    details = score.metadata["details"]
    t2 = details["t2"]
    assert t2["exact_pass"] is False
    assert t2["fuzzy_pass"] is True
    assert t2["agreed"] is False
    assert score.value == 0.5


def test_scorer_agreement_missing_dir(tmp_path: Path) -> None:
    """Score is 0.0 when golden directory doesn't exist."""
    evaluator = ScorerAgreementEvaluator(golden_dir=tmp_path / "nope")
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


def test_all_evaluators_return_dimension_score() -> None:
    """All evaluators return DimensionScore even with default arguments."""
    evaluators = [
        ScoringAccuracyEvaluator(),
        ReliabilityEvaluator(),
        ScorerAgreementEvaluator(),
    ]
    for evaluator in evaluators:
        score = evaluator.evaluate()
        assert isinstance(score, DimensionScore)
        assert isinstance(score.value, float)
        assert isinstance(score.max_value, float)
        assert isinstance(score.metadata, dict)
        assert score.name != ""


# ---------------------------------------------------------------------------
# Integration: register in SelfEvalRunner
# ---------------------------------------------------------------------------


def test_register_with_self_eval_runner() -> None:
    """All three evaluators can be registered and run via SelfEvalRunner."""
    from nines.iteration.self_eval import SelfEvalRunner

    runner = SelfEvalRunner()
    runner.register_dimension(
        "scoring_accuracy", ScoringAccuracyEvaluator(golden_dir=GOLDEN_DIR),
    )
    runner.register_dimension(
        "scoring_reliability", ReliabilityEvaluator(golden_dir=GOLDEN_DIR),
    )
    runner.register_dimension(
        "scorer_agreement", ScorerAgreementEvaluator(golden_dir=GOLDEN_DIR),
    )

    report = runner.run_all(version="test-v1-scoring")

    assert len(report.scores) == 3
    assert report.version == "test-v1-scoring"
    assert 0.0 <= report.overall <= 1.0

    names = {s.name for s in report.scores}
    assert names == {"scoring_accuracy", "scoring_reliability", "scorer_agreement"}


# ---------------------------------------------------------------------------
# Release follow-up N2 — Live* evaluators wire TimeBudget into subprocess.run
#
# The Live* evaluators live in ``nines.iteration.self_eval`` (not
# ``v1_evaluators``), but per the v2.2.0 release follow-up these tests are
# co-located with the other release-blocker checks.  The tests mock
# ``subprocess.run`` and assert that ``timeout=`` matches
# ``min(default_timeout, budget.hard_seconds * 0.9)``.
# ---------------------------------------------------------------------------

import subprocess  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

from nines.core.budget import TimeBudget  # noqa: E402
from nines.iteration.self_eval import (  # noqa: E402
    LintCleanlinessEvaluator,
    LiveCodeCoverageEvaluator,
    LiveTestCountEvaluator,
)


_BUDGET = TimeBudget(soft_seconds=5.0, hard_seconds=10.0)
_HARD_MARGIN = 0.9  # mirrors ``_budgeted_subprocess_timeout`` default
_EXPECTED_TIMEOUT = _BUDGET.hard_seconds * _HARD_MARGIN  # 9.0s for hard=10


def _captured_timeout(mock_run: MagicMock) -> float:
    """Pull the ``timeout=`` kwarg from the most recent subprocess.run call."""
    call = mock_run.call_args
    assert call is not None, "subprocess.run was never invoked"
    timeout_kw = call.kwargs.get("timeout")
    assert timeout_kw is not None, (
        "subprocess.run invoked without timeout= kwarg "
        f"(args={call.args}, kwargs={call.kwargs})"
    )
    return float(timeout_kw)


# ---------------------------------------------------------------------------
# LiveCodeCoverageEvaluator (D-cov)
# ---------------------------------------------------------------------------


@patch("nines.iteration.self_eval.subprocess.run")
def test_live_coverage_evaluator_respects_budget(mock_run: MagicMock) -> None:
    """N2: pytest --cov subprocess timeout shrinks to budget.hard*0.9."""
    mock_run.return_value = MagicMock(
        stdout="TOTAL   100   20   80%\n", returncode=0,
    )
    ev = LiveCodeCoverageEvaluator(project_root="/fake")
    score = ev.evaluate(budget=_BUDGET)

    assert score.value == 80.0
    timeout_used = _captured_timeout(mock_run)
    assert timeout_used <= 9.0, (
        f"expected timeout <= 9.0s under budget hard=10s, got {timeout_used}"
    )
    assert abs(timeout_used - _EXPECTED_TIMEOUT) < 1e-6


@patch("nines.iteration.self_eval.subprocess.run")
def test_live_coverage_evaluator_uses_default_when_no_budget(
    mock_run: MagicMock,
) -> None:
    """N2: backward compat — without a budget the original 300s timeout
    is preserved."""
    mock_run.return_value = MagicMock(
        stdout="TOTAL   100   20   80%\n", returncode=0,
    )
    ev = LiveCodeCoverageEvaluator(project_root="/fake")
    ev.evaluate()  # no budget kwarg

    timeout_used = _captured_timeout(mock_run)
    assert timeout_used == 300.0, (
        f"expected default 300s timeout without budget, got {timeout_used}"
    )


@patch("nines.iteration.self_eval.subprocess.run")
def test_live_coverage_evaluator_caps_at_default_when_budget_huge(
    mock_run: MagicMock,
) -> None:
    """N2: when the budget is larger than the default, the default wins
    (``min`` semantics)."""
    mock_run.return_value = MagicMock(
        stdout="TOTAL   100   20   80%\n", returncode=0,
    )
    ev = LiveCodeCoverageEvaluator(project_root="/fake")
    huge = TimeBudget(soft_seconds=600.0, hard_seconds=600.0)
    ev.evaluate(budget=huge)

    timeout_used = _captured_timeout(mock_run)
    # 600 * 0.9 = 540 > 300 default, so default 300 wins.
    assert timeout_used == 300.0


# ---------------------------------------------------------------------------
# LiveTestCountEvaluator (D-test_count)
# ---------------------------------------------------------------------------


@patch("nines.iteration.self_eval.subprocess.run")
def test_live_test_count_evaluator_respects_budget(mock_run: MagicMock) -> None:
    """N2: pytest --collect-only subprocess timeout shrinks to budget*0.9."""
    mock_run.return_value = MagicMock(
        stdout="5 tests collected\n", returncode=0,
    )
    ev = LiveTestCountEvaluator(test_dir="/fake/tests", project_root="/fake")
    score = ev.evaluate(budget=_BUDGET)

    assert score.value == 5.0
    timeout_used = _captured_timeout(mock_run)
    assert timeout_used <= 9.0, (
        f"expected timeout <= 9.0s under budget hard=10s, got {timeout_used}"
    )
    assert abs(timeout_used - _EXPECTED_TIMEOUT) < 1e-6


@patch("nines.iteration.self_eval.subprocess.run")
def test_live_test_count_evaluator_uses_default_when_no_budget(
    mock_run: MagicMock,
) -> None:
    """N2: backward compat — without a budget the original 120s timeout
    is preserved."""
    mock_run.return_value = MagicMock(
        stdout="5 tests collected\n", returncode=0,
    )
    ev = LiveTestCountEvaluator(test_dir="/fake/tests", project_root="/fake")
    ev.evaluate()

    timeout_used = _captured_timeout(mock_run)
    assert timeout_used == 120.0


# ---------------------------------------------------------------------------
# LintCleanlinessEvaluator (D-lint)
# ---------------------------------------------------------------------------


@patch("nines.iteration.self_eval.subprocess.run")
def test_lint_cleanliness_evaluator_respects_budget(mock_run: MagicMock) -> None:
    """N2: ruff check subprocess timeout shrinks to budget*0.9."""
    mock_run.return_value = MagicMock(stdout="", returncode=0)
    ev = LintCleanlinessEvaluator(src_dir="/fake")
    score = ev.evaluate(budget=_BUDGET)

    assert score.value == 100.0
    timeout_used = _captured_timeout(mock_run)
    assert timeout_used <= 9.0, (
        f"expected timeout <= 9.0s under budget hard=10s, got {timeout_used}"
    )
    assert abs(timeout_used - _EXPECTED_TIMEOUT) < 1e-6


@patch("nines.iteration.self_eval.subprocess.run")
def test_lint_cleanliness_evaluator_uses_default_when_no_budget(
    mock_run: MagicMock,
) -> None:
    """N2: backward compat — without a budget the original 300s timeout
    is preserved."""
    mock_run.return_value = MagicMock(stdout="", returncode=0)
    ev = LintCleanlinessEvaluator(src_dir="/fake")
    ev.evaluate()

    timeout_used = _captured_timeout(mock_run)
    assert timeout_used == 300.0


# ---------------------------------------------------------------------------
# N2 — runner threads the budget through register_dimension(... budget=)
# ---------------------------------------------------------------------------


@patch("nines.iteration.self_eval.subprocess.run")
def test_runner_threads_budget_into_live_evaluators(mock_run: MagicMock) -> None:
    """N2 integration: SelfEvalRunner.register_dimension(name, ev,
    budget=...) routes the budget into ``evaluate(budget=...)`` for
    evaluators whose signature accepts it."""
    from nines.iteration.self_eval import SelfEvalRunner

    mock_run.return_value = MagicMock(
        stdout="TOTAL   100   20   80%\n", returncode=0,
    )
    runner = SelfEvalRunner(default_budget=TimeBudget(5.0, 30.0))
    # register with a dim-specific budget that will dominate.
    dim_budget = TimeBudget(soft_seconds=2.0, hard_seconds=8.0)
    runner.register_dimension(
        "code_coverage",
        LiveCodeCoverageEvaluator(project_root="/fake"),
        budget=dim_budget,
    )

    report = runner.run_all(version="t")
    assert len(report.scores) == 1
    assert report.timeouts == []  # no real subprocess timeout

    # The evaluator's subprocess.run should see the dim's budget,
    # not the runner default.
    timeout_used = _captured_timeout(mock_run)
    assert abs(timeout_used - dim_budget.hard_seconds * 0.9) < 1e-6


def test_runner_calls_legacy_evaluators_without_budget() -> None:
    """N2 backward compat: evaluators whose ``evaluate`` doesn't accept
    ``budget`` are invoked with no kwargs (no TypeError)."""
    from nines.iteration.self_eval import (
        DimensionScore,
        SelfEvalRunner,
    )

    class LegacyEvaluator:
        """Pre-N2 evaluator with a no-arg evaluate signature."""

        called_with: dict = {}

        def evaluate(self) -> DimensionScore:  # no budget kwarg
            return DimensionScore(name="legacy", value=0.5, max_value=1.0)

    runner = SelfEvalRunner(default_budget=TimeBudget(1.0, 5.0))
    runner.register_dimension("legacy", LegacyEvaluator())
    report = runner.run_all()

    assert len(report.scores) == 1
    assert report.scores[0].name == "legacy"
    assert report.scores[0].value == 0.5
    assert report.timeouts == []


def test_budgeted_subprocess_timeout_helper() -> None:
    """N2 helper: ``min(default, budget.hard*0.9)`` semantics + None
    passthrough."""
    from nines.iteration.self_eval import _budgeted_subprocess_timeout

    # No budget => default unchanged.
    assert _budgeted_subprocess_timeout(120.0, None) == 120.0

    # Budget shrinks below default.
    out = _budgeted_subprocess_timeout(120.0, TimeBudget(5.0, 30.0))
    assert abs(out - 27.0) < 1e-6  # 30 * 0.9 = 27

    # Budget larger than default => default wins.
    out = _budgeted_subprocess_timeout(60.0, TimeBudget(60.0, 600.0))
    assert out == 60.0

    # Custom margin (passes through).
    out = _budgeted_subprocess_timeout(
        100.0, TimeBudget(5.0, 50.0), margin=0.5,
    )
    assert out == 25.0

    # Catch the realistic timeout-budget mismatch — subprocess timeout
    # must always be < budget.hard_seconds so the daemon-thread guard
    # doesn't fire while the subprocess is mid-call.
    budget = TimeBudget(5.0, 60.0)
    out = _budgeted_subprocess_timeout(300.0, budget)
    assert out < budget.hard_seconds, (
        f"subprocess timeout {out} must stay below daemon budget "
        f"{budget.hard_seconds}"
    )


# ---------------------------------------------------------------------------
# N2 documentation — AgentAnalysisQualityEvaluator is pure-Python
# ---------------------------------------------------------------------------


def test_agent_analysis_quality_is_pure_python() -> None:
    """Documents the design choice: ``AgentAnalysisQualityEvaluator``
    runs the AnalysisPipeline + AgentImpactAnalyzer in-process, never
    shelling out, so the only safety net under hang is the
    daemon-thread budget from C04 (no subprocess timeout to wire).

    This test is a regression detector: if a future contributor adds a
    ``subprocess.run`` to that evaluator, this assertion fails and they
    must wire it through the same N2 mechanism as the Live* family.
    """
    import inspect as _inspect

    from nines.iteration.capability_evaluators import (
        AgentAnalysisQualityEvaluator,
    )

    source = _inspect.getsource(AgentAnalysisQualityEvaluator)
    assert "subprocess" not in source, (
        "AgentAnalysisQualityEvaluator gained a subprocess call; "
        "wire its budget through _budgeted_subprocess_timeout per N2"
    )
