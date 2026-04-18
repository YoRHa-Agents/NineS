"""Tests for ``nines.eval.mock_executor`` (C06 — DeterministicMockExecutor)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.eval.mock_executor import DeterministicMockExecutor  # noqa: E402
from nines.eval.models import ScoringCriterion, TaskDefinition  # noqa: E402


def _task(task_id: str, *, criteria: int = 0) -> TaskDefinition:
    crit = [ScoringCriterion(name=f"c{i}", weight=1.0 / max(criteria, 1)) for i in range(criteria)]
    return TaskDefinition(id=task_id, name=task_id, scoring_criteria=crit)


# ---------------------------------------------------------------------------
# Determinism
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
# Weights / criteria respected
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
