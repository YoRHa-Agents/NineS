"""Tests for ``nines.eval.mock_executor`` (C06 — DeterministicMockExecutor + MockEvaluator)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.eval.mock_executor import DeterministicMockExecutor, MockEvaluator  # noqa: E402
from nines.eval.models import ScoringCriterion, TaskDefinition  # noqa: E402
from nines.iteration.self_eval import (  # noqa: E402
    DimensionEvaluator,
    DimensionScore,
    SelfEvalRunner,
)


def _task(task_id: str, *, criteria: int = 0) -> TaskDefinition:
    crit = [ScoringCriterion(name=f"c{i}", weight=1.0 / max(criteria, 1)) for i in range(criteria)]
    return TaskDefinition(id=task_id, name=task_id, scoring_criteria=crit)


# ---------------------------------------------------------------------------
# DeterministicMockExecutor — Determinism
# ---------------------------------------------------------------------------


def test_same_input_produces_same_output_across_runs() -> None:
    """5 invocations of the same executor on the same task agree."""
    executor = DeterministicMockExecutor()
    task = _task("alpha")
    outputs = [executor(task).output for _ in range(5)]
    assert len(set(outputs)) == 1, f"non-deterministic: {outputs}"


def test_distinct_task_ids_produce_distinct_outputs() -> None:
    """Different task IDs produce different deterministic outputs."""
    executor = DeterministicMockExecutor()
    outputs = {executor(_task(f"task-{i}")).output for i in range(20)}
    # 20 distinct IDs → 20 distinct outputs (16-byte hash, ~zero collisions).
    assert len(outputs) == 20


def test_seed_changes_output_stream_but_keeps_determinism() -> None:
    """Same task ID + different seed → different stable output."""
    a = DeterministicMockExecutor(seed="run-A")
    b = DeterministicMockExecutor(seed="run-B")
    task = _task("alpha")
    out_a = a(task).output
    out_b = b(task).output
    # Different seeds yield different outputs ...
    assert out_a != out_b
    # ... but each seed is internally deterministic.
    assert a(task).output == out_a
    assert b(task).output == out_b


# ---------------------------------------------------------------------------
# DeterministicMockExecutor — Weights / criteria respected
# ---------------------------------------------------------------------------


def test_criteria_count_scales_token_count() -> None:
    """token_count scales linearly with the number of scoring criteria."""
    executor = DeterministicMockExecutor(base_token_count=10)
    one = executor(_task("one", criteria=1))
    five = executor(_task("five", criteria=5))
    assert one.metrics["token_count"] == 10
    assert five.metrics["token_count"] == 50


def test_fixed_output_override_takes_precedence() -> None:
    """Entries in ``fixed_outputs`` override the hash-derived value."""
    executor = DeterministicMockExecutor(
        fixed_outputs={"alpha": "PINNED"},
    )
    assert executor(_task("alpha")).output == "PINNED"
    # Other tasks still use the hash derivation.
    assert executor(_task("beta")).output != "PINNED"


def test_rejects_non_task_definition_input() -> None:
    """Type-confused inputs raise TypeError, never silently coerce."""
    executor = DeterministicMockExecutor()
    with pytest.raises(TypeError):
        executor("not-a-task")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# MockEvaluator — Protocol conformance & deterministic output
# ---------------------------------------------------------------------------


def test_mock_evaluator_satisfies_dimension_evaluator_protocol() -> None:
    """MockEvaluator structurally satisfies the runtime-checkable Protocol."""
    mock = MockEvaluator(name="x")
    assert isinstance(mock, DimensionEvaluator), (
        "MockEvaluator must satisfy DimensionEvaluator runtime Protocol "
        "so SelfEvalRunner.register_dimension accepts it without warning"
    )


def test_mock_evaluator_returns_configured_dimension_score() -> None:
    """evaluate() returns a DimensionScore matching constructor args."""
    mock = MockEvaluator(
        name="test_count",
        value=42.0,
        max_value=100.0,
        metadata={"unit": "tests", "method": "mock"},
    )
    score = mock.evaluate()
    assert isinstance(score, DimensionScore)
    assert score.name == "test_count"
    assert score.value == 42.0
    assert score.max_value == 100.0
    assert score.metadata == {"unit": "tests", "method": "mock"}
    assert abs(score.normalized - 0.42) < 1e-9


def test_mock_evaluator_is_deterministic_across_invocations() -> None:
    """Calling evaluate() repeatedly yields byte-identical to_dict output."""
    mock = MockEvaluator(
        name="stable",
        value=0.7,
        max_value=1.0,
        metadata={"k": "v"},
    )
    first = mock.evaluate().to_dict()
    later = [mock.evaluate().to_dict() for _ in range(10)]
    assert all(d == first for d in later), "MockEvaluator output is non-deterministic"


def test_mock_evaluator_default_metadata_is_independent_per_call() -> None:
    """Mutating one returned score's metadata does not affect later calls."""
    mock = MockEvaluator(name="m", metadata={"unit": "pct"})
    score_1 = mock.evaluate()
    score_1.metadata["leaked"] = "yes"  # external mutation
    score_2 = mock.evaluate()
    assert "leaked" not in score_2.metadata, (
        "metadata copy is shared between calls — caller mutation should not leak"
    )
    assert "leaked" not in (mock.metadata or {})


# ---------------------------------------------------------------------------
# MockEvaluator — Failure / sleep paths
# ---------------------------------------------------------------------------


def test_mock_evaluator_sleeps_when_configured() -> None:
    """sleep_seconds > 0 makes evaluate() block for at least that long."""
    mock = MockEvaluator(name="slow", sleep_seconds=0.15)
    t0 = time.monotonic()
    mock.evaluate()
    elapsed = time.monotonic() - t0
    # Wall-clock granularity / scheduling jitter — assert ≥90% of the
    # requested sleep arrived. We don't assert an upper bound here (the
    # hang-detection test does that against TimeBudget).
    assert elapsed >= 0.135, f"sleep_seconds=0.15 only blocked for {elapsed:.3f}s"


def test_mock_evaluator_raises_when_configured() -> None:
    """raise_on_call=Exception → evaluate() raises that exception class."""
    mock = MockEvaluator(name="boom", raise_on_call=RuntimeError)
    with pytest.raises(RuntimeError, match="boom"):
        mock.evaluate()


def test_mock_evaluator_rejects_invalid_max_value() -> None:
    """Negative max_value is rejected at construction time."""
    with pytest.raises(ValueError, match="max_value"):
        MockEvaluator(name="bad", max_value=-0.1)


def test_mock_evaluator_rejects_invalid_sleep_seconds() -> None:
    """Negative sleep_seconds is rejected at construction time."""
    with pytest.raises(ValueError, match="sleep_seconds"):
        MockEvaluator(name="bad", sleep_seconds=-1.0)


def test_mock_evaluator_rejects_non_exception_raise_on_call() -> None:
    """raise_on_call must be a BaseException subclass (rejects e.g. int)."""
    with pytest.raises(TypeError, match="raise_on_call"):
        MockEvaluator(name="bad", raise_on_call=int)  # type: ignore[arg-type]


def test_mock_evaluator_integrates_with_self_eval_runner() -> None:
    """Registered MockEvaluator runs through SelfEvalRunner without warning."""
    runner = SelfEvalRunner()
    runner.register_dimension(
        "fixture_dim",
        MockEvaluator(name="fixture_dim", value=0.5, max_value=1.0, metadata={"unit": "ratio"}),
    )
    report = runner.run_all(version="v3.2.0-test")
    assert len(report.scores) == 1
    s = report.scores[0]
    assert s.name == "fixture_dim"
    assert s.value == 0.5
    assert s.metadata == {"unit": "ratio"}
    assert report.timeouts == []
    assert report.version == "v3.2.0-test"
