"""Tests for multi-round evaluation: data models, runner, convergence, reliability."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from nines.core.models import ExecutionResult, Score
from nines.eval.models import EvalResult, TaskDefinition
from nines.eval.multi_round import (
    MultiRoundReport,
    MultiRoundRunner,
    RoundResult,
)
from nines.eval.runner import EvalRunner
from nines.eval.scorers import ExactScorer
from nines.sandbox.manager import SandboxManager

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _task(task_id: str = "t1", name: str = "task-1") -> TaskDefinition:
    return TaskDefinition(
        id=task_id,
        name=name,
        description="test",
        expected="hello",
    )


def _echo_executor(task: TaskDefinition) -> ExecutionResult:
    return ExecutionResult(
        task_id=task.id,
        output=task.expected,
        metrics={"token_count": 10},
        success=True,
    )


def _wrong_executor(task: TaskDefinition) -> ExecutionResult:
    return ExecutionResult(
        task_id=task.id,
        output="wrong",
        metrics={"token_count": 5},
        success=True,
    )


def _make_eval_result(
    task_id: str = "t1",
    composite: float = 0.8,
    success: bool = True,
) -> EvalResult:
    return EvalResult(
        task_id=task_id,
        task_name=f"name-{task_id}",
        output="out",
        scores=[Score(value=composite, scorer_name="exact")],
        composite_score=composite,
        duration_ms=10.0,
        success=success,
    )


def _make_round(
    round_num: int,
    composite: float = 0.8,
    task_ids: tuple[str, ...] = ("t1",),
) -> RoundResult:
    results = [_make_eval_result(tid, composite) for tid in task_ids]
    return RoundResult(
        round_number=round_num,
        results=results,
        composite_score=composite,
        duration_ms=50.0,
    )


# ---------------------------------------------------------------------------
# RoundResult serialization
# ---------------------------------------------------------------------------


class TestRoundResult:
    def test_to_dict(self) -> None:
        rr = _make_round(1, 0.9)
        d = rr.to_dict()
        assert d["round_number"] == 1
        assert d["composite_score"] == 0.9
        assert len(d["results"]) == 1
        assert d["results"][0]["task_id"] == "t1"

    def test_from_dict(self) -> None:
        original = _make_round(2, 0.75)
        d = original.to_dict()
        restored = RoundResult.from_dict(d)
        assert restored.round_number == 2
        assert restored.composite_score == pytest.approx(0.75)
        assert len(restored.results) == 1

    def test_round_trip(self) -> None:
        rr = _make_round(3, 0.6, task_ids=("a", "b"))
        restored = RoundResult.from_dict(rr.to_dict())
        assert restored.round_number == rr.round_number
        assert restored.composite_score == pytest.approx(rr.composite_score)
        assert len(restored.results) == len(rr.results)

    def test_metadata_preserved(self) -> None:
        rr = RoundResult(
            round_number=1,
            results=[],
            composite_score=0.5,
            duration_ms=10.0,
            metadata={"key": "value"},
        )
        restored = RoundResult.from_dict(rr.to_dict())
        assert restored.metadata == {"key": "value"}

    def test_from_dict_defaults(self) -> None:
        minimal = {"round_number": 1}
        rr = RoundResult.from_dict(minimal)
        assert rr.results == []
        assert rr.composite_score == 0.0
        assert rr.duration_ms == 0.0
        assert rr.metadata == {}


# ---------------------------------------------------------------------------
# MultiRoundReport serialization
# ---------------------------------------------------------------------------


class TestMultiRoundReport:
    def _sample_report(self) -> MultiRoundReport:
        rounds = [_make_round(i, 0.7 + i * 0.05) for i in range(1, 4)]
        return MultiRoundReport(
            suite_id="suite-1",
            rounds=rounds,
            total_rounds=3,
            mean_composite=0.8,
            std_composite=0.04,
            min_composite=0.75,
            max_composite=0.85,
            reliability={"pass_at_1": 1.0, "consistency": 0.95},
            converged=True,
            convergence_round=3,
            total_duration_ms=150.0,
            metadata={"min_rounds": 3},
        )

    def test_to_dict(self) -> None:
        report = self._sample_report()
        d = report.to_dict()
        assert d["suite_id"] == "suite-1"
        assert d["total_rounds"] == 3
        assert d["converged"] is True
        assert d["convergence_round"] == 3
        assert len(d["rounds"]) == 3

    def test_from_dict(self) -> None:
        report = self._sample_report()
        restored = MultiRoundReport.from_dict(report.to_dict())
        assert restored.suite_id == "suite-1"
        assert restored.total_rounds == 3
        assert restored.converged is True
        assert restored.convergence_round == 3
        assert len(restored.rounds) == 3

    def test_round_trip(self) -> None:
        report = self._sample_report()
        restored = MultiRoundReport.from_dict(report.to_dict())
        assert restored.mean_composite == pytest.approx(report.mean_composite)
        assert restored.std_composite == pytest.approx(report.std_composite)
        assert restored.reliability == report.reliability

    def test_from_dict_defaults(self) -> None:
        minimal = {"suite_id": "s1"}
        report = MultiRoundReport.from_dict(minimal)
        assert report.rounds == []
        assert report.total_rounds == 0
        assert report.converged is False
        assert report.convergence_round is None

    def test_per_task_summary(self) -> None:
        rounds = [
            RoundResult(
                round_number=1,
                results=[
                    _make_eval_result("t1", 0.8),
                    _make_eval_result("t2", 0.6),
                ],
                composite_score=0.7,
                duration_ms=10.0,
            ),
            RoundResult(
                round_number=2,
                results=[
                    _make_eval_result("t1", 0.9),
                    _make_eval_result("t2", 0.7),
                ],
                composite_score=0.8,
                duration_ms=10.0,
            ),
        ]
        report = MultiRoundReport(
            suite_id="s",
            rounds=rounds,
            total_rounds=2,
            mean_composite=0.75,
            std_composite=0.05,
            min_composite=0.7,
            max_composite=0.8,
            reliability={},
            converged=False,
            convergence_round=None,
            total_duration_ms=20.0,
        )
        summary = report.per_task_summary()
        assert "t1" in summary
        assert "t2" in summary
        assert summary["t1"]["mean"] == pytest.approx(0.85)
        assert summary["t1"]["min"] == pytest.approx(0.8)
        assert summary["t1"]["max"] == pytest.approx(0.9)
        assert summary["t1"]["count"] == 2
        assert summary["t2"]["mean"] == pytest.approx(0.65)

    def test_per_task_summary_single_round(self) -> None:
        rounds = [
            RoundResult(
                round_number=1,
                results=[_make_eval_result("t1", 0.5)],
                composite_score=0.5,
                duration_ms=5.0,
            ),
        ]
        report = MultiRoundReport(
            suite_id="s",
            rounds=rounds,
            total_rounds=1,
            mean_composite=0.5,
            std_composite=0.0,
            min_composite=0.5,
            max_composite=0.5,
            reliability={},
            converged=False,
            convergence_round=None,
            total_duration_ms=5.0,
        )
        summary = report.per_task_summary()
        assert summary["t1"]["std"] == pytest.approx(0.0)
        assert summary["t1"]["count"] == 1


# ---------------------------------------------------------------------------
# MultiRoundRunner — init validation
# ---------------------------------------------------------------------------


class TestMultiRoundRunnerInit:
    def test_default_construction(self) -> None:
        runner = MultiRoundRunner()
        assert runner._min_rounds == 3
        assert runner._max_rounds == 10

    def test_custom_params(self) -> None:
        runner = MultiRoundRunner(
            convergence_threshold=0.05,
            min_rounds=5,
            max_rounds=20,
        )
        assert runner._convergence_threshold == 0.05
        assert runner._min_rounds == 5
        assert runner._max_rounds == 20

    def test_min_rounds_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="min_rounds"):
            MultiRoundRunner(min_rounds=0)

    def test_max_less_than_min_raises(self) -> None:
        with pytest.raises(ValueError, match="max_rounds"):
            MultiRoundRunner(min_rounds=5, max_rounds=3)

    def test_negative_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="convergence_threshold"):
            MultiRoundRunner(convergence_threshold=-0.1)


# ---------------------------------------------------------------------------
# MultiRoundRunner._check_convergence
# ---------------------------------------------------------------------------


class TestConvergence:
    def test_converges_on_identical_scores(self) -> None:
        runner = MultiRoundRunner(convergence_threshold=0.02, min_rounds=3)
        rounds = [_make_round(i, 0.8) for i in range(1, 4)]
        converged, at = runner._check_convergence(rounds)
        assert converged is True
        assert at == 3

    def test_does_not_converge_with_high_variance(self) -> None:
        runner = MultiRoundRunner(convergence_threshold=0.02, min_rounds=3)
        rounds = [
            _make_round(1, 0.5),
            _make_round(2, 0.8),
            _make_round(3, 0.3),
        ]
        converged, at = runner._check_convergence(rounds)
        assert converged is False
        assert at is None

    def test_not_enough_rounds(self) -> None:
        runner = MultiRoundRunner(min_rounds=3)
        rounds = [_make_round(1, 0.8), _make_round(2, 0.8)]
        converged, at = runner._check_convergence(rounds)
        assert converged is False
        assert at is None

    def test_convergence_uses_sliding_window(self) -> None:
        runner = MultiRoundRunner(convergence_threshold=0.02, min_rounds=3)
        rounds = [
            _make_round(1, 0.3),
            _make_round(2, 0.5),
            _make_round(3, 0.8),
            _make_round(4, 0.8),
            _make_round(5, 0.8),
        ]
        converged, at = runner._check_convergence(rounds)
        assert converged is True
        assert at == 5

    def test_convergence_boundary(self) -> None:
        runner = MultiRoundRunner(convergence_threshold=0.02, min_rounds=3)
        rounds = [
            _make_round(1, 0.80),
            _make_round(2, 0.81),
            _make_round(3, 0.80),
        ]
        converged, _ = runner._check_convergence(rounds)
        assert converged is True


# ---------------------------------------------------------------------------
# MultiRoundRunner._compute_reliability
# ---------------------------------------------------------------------------


class TestReliability:
    def test_all_passing(self) -> None:
        runner = MultiRoundRunner()
        rounds = [_make_round(i, 0.9) for i in range(1, 6)]
        rel = runner._compute_reliability(rounds)
        assert rel["pass_at_1"] == pytest.approx(1.0)
        assert rel["consistency"] == pytest.approx(1.0)

    def test_mixed_passing(self) -> None:
        runner = MultiRoundRunner()
        rounds = [
            _make_round(1, 0.9),
            _make_round(2, 0.3),
            _make_round(3, 0.8),
        ]
        rel = runner._compute_reliability(rounds)
        assert "pass_at_1" in rel
        assert "consistency" in rel
        assert rel["pass_at_1"] < 1.0
        assert rel["pass_at_1"] > 0.0

    def test_none_passing(self) -> None:
        runner = MultiRoundRunner()
        rounds = [_make_round(i, 0.2) for i in range(1, 4)]
        rel = runner._compute_reliability(rounds)
        assert rel["pass_at_1"] == pytest.approx(0.0)

    def test_pass_power_k_included(self) -> None:
        runner = MultiRoundRunner()
        rounds = [_make_round(i, 0.9) for i in range(1, 6)]
        rel = runner._compute_reliability(rounds)
        assert "pass_power_1" in rel
        assert "pass_power_3" in rel
        assert "pass_power_5" in rel

    def test_small_n_skips_large_k(self) -> None:
        runner = MultiRoundRunner(min_rounds=1, max_rounds=2)
        rounds = [_make_round(1, 0.9), _make_round(2, 0.9)]
        rel = runner._compute_reliability(rounds)
        assert "pass_at_1" in rel
        assert "pass_at_5" not in rel


# ---------------------------------------------------------------------------
# MultiRoundRunner._compute_per_task_stats
# ---------------------------------------------------------------------------


class TestPerTaskStats:
    def test_basic(self) -> None:
        runner = MultiRoundRunner()
        rounds = [
            RoundResult(
                round_number=1,
                results=[
                    _make_eval_result("t1", 0.8),
                    _make_eval_result("t2", 0.6),
                ],
                composite_score=0.7,
                duration_ms=10.0,
            ),
            RoundResult(
                round_number=2,
                results=[
                    _make_eval_result("t1", 1.0),
                    _make_eval_result("t2", 0.8),
                ],
                composite_score=0.9,
                duration_ms=10.0,
            ),
        ]
        stats = runner._compute_per_task_stats(rounds)
        assert stats["t1"]["mean"] == pytest.approx(0.9)
        assert stats["t1"]["min"] == pytest.approx(0.8)
        assert stats["t1"]["max"] == pytest.approx(1.0)
        assert stats["t2"]["count"] == 2

    def test_single_round(self) -> None:
        runner = MultiRoundRunner()
        rounds = [_make_round(1, 0.5, task_ids=("a",))]
        stats = runner._compute_per_task_stats(rounds)
        assert stats["a"]["std"] == pytest.approx(0.0)
        assert stats["a"]["count"] == 1


# ---------------------------------------------------------------------------
# MultiRoundRunner.run — integration with EvalRunner
# ---------------------------------------------------------------------------


class TestMultiRoundRun:
    def test_basic_run(self) -> None:
        tasks = [_task("t1"), _task("t2")]
        runner = MultiRoundRunner(min_rounds=3, max_rounds=5)
        report = runner.run(tasks, _echo_executor, [ExactScorer()])

        assert report.total_rounds >= 3
        assert report.total_rounds <= 5
        assert report.mean_composite > 0
        assert len(report.rounds) == report.total_rounds
        assert report.suite_id != ""

    def test_converges_with_deterministic_executor(self) -> None:
        tasks = [_task()]
        runner = MultiRoundRunner(convergence_threshold=0.02, min_rounds=3, max_rounds=10)
        report = runner.run(tasks, _echo_executor, [ExactScorer()])
        assert report.converged is True
        assert report.convergence_round == 3
        assert report.total_rounds == 3

    def test_max_rounds_reached(self) -> None:
        call_count = 0

        def _varying_executor(task: TaskDefinition) -> ExecutionResult:
            nonlocal call_count
            call_count += 1
            output = "hello" if call_count % 2 == 0 else "wrong"
            return ExecutionResult(
                task_id=task.id,
                output=output,
                metrics={"token_count": 1},
                success=True,
            )

        tasks = [_task()]
        runner = MultiRoundRunner(convergence_threshold=0.001, min_rounds=2, max_rounds=4)
        report = runner.run(tasks, _varying_executor, [ExactScorer()])
        assert report.total_rounds == 4
        assert report.converged is False

    def test_custom_suite_id(self) -> None:
        tasks = [_task()]
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(tasks, _echo_executor, [ExactScorer()], suite_id="my-suite")
        assert report.suite_id == "my-suite"

    def test_report_metadata(self) -> None:
        runner = MultiRoundRunner(convergence_threshold=0.05, min_rounds=3, max_rounds=5)
        report = runner.run([_task()], _echo_executor, [ExactScorer()])
        assert report.metadata["min_rounds"] == 3
        assert report.metadata["max_rounds"] == 5
        assert report.metadata["convergence_threshold"] == 0.05
        assert report.metadata["sandboxed"] is False

    def test_report_statistics(self) -> None:
        tasks = [_task()]
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(tasks, _echo_executor, [ExactScorer()])
        assert report.mean_composite == pytest.approx(1.0)
        assert report.std_composite == pytest.approx(0.0)
        assert report.min_composite == pytest.approx(1.0)
        assert report.max_composite == pytest.approx(1.0)

    def test_report_reliability_keys(self) -> None:
        tasks = [_task()]
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(tasks, _echo_executor, [ExactScorer()])
        assert "consistency" in report.reliability
        assert "pass_at_1" in report.reliability
        assert "pass_at_3" in report.reliability

    def test_report_total_duration(self) -> None:
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run([_task()], _echo_executor, [ExactScorer()])
        assert report.total_duration_ms > 0

    def test_per_task_summary_from_run(self) -> None:
        tasks = [_task("a"), _task("b")]
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(tasks, _echo_executor, [ExactScorer()])
        summary = report.per_task_summary()
        assert "a" in summary
        assert "b" in summary
        assert summary["a"]["count"] == 3
        assert summary["b"]["count"] == 3

    def test_empty_task_list(self) -> None:
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run([], _echo_executor, [ExactScorer()])
        assert report.total_rounds == 3
        assert report.mean_composite == pytest.approx(0.0)

    def test_custom_eval_runner(self) -> None:
        custom_runner = EvalRunner()
        runner = MultiRoundRunner(eval_runner=custom_runner, min_rounds=3, max_rounds=3)
        report = runner.run([_task()], _echo_executor, [ExactScorer()])
        assert report.total_rounds == 3
        assert report.converged is True


# ---------------------------------------------------------------------------
# Sandbox integration
# ---------------------------------------------------------------------------


class TestSandboxIntegration:
    def test_with_sandbox_manager(self) -> None:
        mock_ctx = MagicMock()
        mock_ctx.sandbox_id = "test-sandbox"

        mock_manager = MagicMock(spec=SandboxManager)
        mock_manager.create.return_value = mock_ctx

        runner = MultiRoundRunner(sandbox_manager=mock_manager, min_rounds=3, max_rounds=3)
        report = runner.run([_task()], _echo_executor, [ExactScorer()])

        assert mock_manager.create.call_count == 3
        assert mock_manager.destroy.call_count == 3
        assert report.metadata["sandboxed"] is True
        for rnd in report.rounds:
            assert rnd.metadata["sandboxed"] is True
            assert rnd.metadata["sandbox_id"] == "test-sandbox"

    def test_sandbox_cleanup_on_error(self) -> None:
        mock_ctx = MagicMock()
        mock_ctx.sandbox_id = "fail-sandbox"

        mock_manager = MagicMock(spec=SandboxManager)
        mock_manager.create.return_value = mock_ctx

        def _raise_executor(task: TaskDefinition) -> ExecutionResult:
            raise RuntimeError("executor boom")

        runner = MultiRoundRunner(sandbox_manager=mock_manager, min_rounds=1, max_rounds=1)
        report = runner.run([_task()], _raise_executor, [ExactScorer()])

        assert mock_manager.destroy.call_count == 1
        assert report.rounds[0].results[0].success is False

    def test_without_sandbox_manager(self) -> None:
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run([_task()], _echo_executor, [ExactScorer()])
        assert report.metadata["sandboxed"] is False
        for rnd in report.rounds:
            assert rnd.metadata["sandboxed"] is False


# ---------------------------------------------------------------------------
# Aggregate composite helper
# ---------------------------------------------------------------------------


class TestAggregateComposite:
    def test_empty_results(self) -> None:
        assert MultiRoundRunner._aggregate_composite([]) == pytest.approx(0.0)

    def test_single_result(self) -> None:
        results = [_make_eval_result("t1", 0.75)]
        assert MultiRoundRunner._aggregate_composite(results) == pytest.approx(0.75)

    def test_multiple_results(self) -> None:
        results = [
            _make_eval_result("t1", 0.6),
            _make_eval_result("t2", 0.8),
        ]
        assert MultiRoundRunner._aggregate_composite(results) == pytest.approx(0.7)
