"""Integration test: EvalRunner.run_single retries flaky executors per C05."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.core.cost_budget import CostBudget  # noqa: E402
from nines.core.models import ExecutionResult  # noqa: E402
from nines.core.retry import RetryPolicy, TransientError  # noqa: E402
from nines.eval.models import TaskDefinition  # noqa: E402
from nines.eval.runner import EvalRunner  # noqa: E402
from nines.eval.scorers import ExactScorer  # noqa: E402


def test_run_single_retries_flaky_executor() -> None:
    """An executor that raises TransientError twice then succeeds wins."""
    counter = {"n": 0}

    def flaky_executor(task: TaskDefinition) -> ExecutionResult:
        counter["n"] += 1
        if counter["n"] < 3:
            raise TransientError(f"flake-{counter['n']}")
        return ExecutionResult(
            task_id=task.id,
            output="hello",
            metrics={"token_count": 10},
            success=True,
        )

    runner = EvalRunner(
        retry_policy=RetryPolicy(attempts=5, base_backoff_s=0.0),
    )
    task = TaskDefinition(id="t1", name="t1", expected="hello")
    result = runner.run_single(task, flaky_executor, [ExactScorer()])
    assert result.success is True
    assert counter["n"] == 3
    assert result.token_count == 10


def test_run_aborts_on_cost_exceeded() -> None:
    """When the budget is exhausted, run() breaks the loop."""
    def cheap_executor(task: TaskDefinition) -> ExecutionResult:
        return ExecutionResult(
            task_id=task.id,
            output="x",
            metrics={"token_count": 50},
            success=True,
        )

    runner = EvalRunner(
        cost_budget=CostBudget(token_limit=100),
    )
    tasks = [
        TaskDefinition(id=f"t{i}", name=f"t{i}", expected="x") for i in range(5)
    ]
    results = runner.run(tasks, cheap_executor, [ExactScorer()])
    # First 2 succeed (50 + 50 = 100, exactly at limit, no breach yet);
    # third charge takes us to 150 > 100 → CostExceeded → break-out
    # entry appended.  Remaining tasks (4 & 5) NOT executed.
    success_count = sum(1 for r in results if r.success)
    error_entries = [r for r in results if not r.success]
    assert success_count == 2
    assert len(error_entries) == 1
    assert "cost_budget_exceeded" in (error_entries[0].error or "")
    assert len(results) == 3
