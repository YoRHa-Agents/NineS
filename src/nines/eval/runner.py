"""Evaluation runner implementing the validate → execute → score → collect pipeline.

``EvalRunner`` is the main entry-point for running evaluation tasks.
It coordinates:

1. **load_tasks** — load ``TaskDefinition`` objects from TOML files
2. **run** — execute a batch of tasks through the full pipeline
3. **run_single** — execute a single task

Covers: FR-114 (Evaluation Orchestration).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nines.core.cost_budget import CostBudget, CostExceeded
from nines.core.errors import EvalError
from nines.core.models import ExecutionResult, Score
from nines.core.retry import RetryPolicy, with_retry
from nines.eval.metrics import MetricCollector
from nines.eval.models import EvalResult, TaskDefinition

if TYPE_CHECKING:
    from nines.eval.scorers import ScorerProtocol

logger = logging.getLogger(__name__)

ExecutorFn = Callable[[TaskDefinition], ExecutionResult]


class EvalRunner:
    """Orchestrates the evaluation pipeline for a set of tasks.

    The pipeline stages for each task are:
    ``validate → execute → score → collect metrics``
    """

    def __init__(
        self,
        metric_collector: MetricCollector | None = None,
        *,
        retry_policy: RetryPolicy | None = None,
        cost_budget: CostBudget | None = None,
    ) -> None:
        """Initialize eval runner.

        Parameters
        ----------
        metric_collector:
            Optional :class:`MetricCollector` (defaults to a fresh one).
        retry_policy:
            Optional :class:`RetryPolicy`; when supplied, ``run_single``
            wraps the executor call in :func:`with_retry`.
        cost_budget:
            Optional :class:`CostBudget`; ``run`` aborts the batch
            when :exc:`CostExceeded` is raised by ``run_single``.
        """
        self._metric_collector = metric_collector or MetricCollector()
        self._retry_policy = retry_policy
        self._cost_budget = cost_budget

    def load_tasks(self, path: str | Path) -> list[TaskDefinition]:
        """Load task definitions from a TOML file or directory of TOML files."""
        p = Path(path)
        if p.is_file():
            return [TaskDefinition.from_toml(p)]
        if p.is_dir():
            tasks: list[TaskDefinition] = []
            for toml_path in sorted(p.glob("*.toml")):
                try:
                    tasks.append(TaskDefinition.from_toml(toml_path))
                except EvalError as exc:
                    logger.error("Failed to load %s: %s", toml_path, exc)
            return tasks
        raise EvalError(f"Path not found: {path}")

    def run(
        self,
        tasks: list[TaskDefinition],
        executor: ExecutorFn,
        scorers: list[ScorerProtocol],
    ) -> list[EvalResult]:
        """Run the full pipeline for a batch of tasks.

        When a :class:`CostBudget` was passed to the constructor the
        loop breaks early on :exc:`CostExceeded` and the remaining
        tasks are skipped.  An ``EvalResult`` flagged
        ``error='cost_budget_exceeded'`` is appended for the task that
        triggered the breach so the caller can inspect provenance.
        """
        results: list[EvalResult] = []
        for task in tasks:
            try:
                result = self.run_single(task, executor, scorers)
            except CostExceeded as exc:
                logger.warning(
                    "Cost budget exhausted while running task %s: %s",
                    task.id,
                    exc,
                )
                results.append(
                    EvalResult(
                        task_id=task.id,
                        task_name=task.name,
                        success=False,
                        error=f"cost_budget_exceeded: {exc}",
                    )
                )
                break
            results.append(result)
        return results

    def run_single(
        self,
        task: TaskDefinition,
        executor: ExecutorFn,
        scorers: list[ScorerProtocol],
    ) -> EvalResult:
        """Run the full pipeline for a single task."""
        errors = self._validate(task)
        if errors:
            return EvalResult(
                task_id=task.id,
                task_name=task.name,
                success=False,
                error=f"Validation failed: {'; '.join(errors)}",
            )

        start = time.monotonic()
        try:
            if self._retry_policy is not None:
                execution = with_retry(
                    lambda: self._execute(task, executor),
                    self._retry_policy,
                )
            else:
                execution = self._execute(task, executor)
        except Exception as exc:
            logger.error("Execution failed for task %s: %s", task.id, exc)
            return EvalResult(
                task_id=task.id,
                task_name=task.name,
                success=False,
                error=f"Execution error: {exc}",
            )
        duration_ms = (time.monotonic() - start) * 1000

        if not execution.success:
            return EvalResult(
                task_id=task.id,
                task_name=task.name,
                output=execution.output,
                duration_ms=duration_ms,
                token_count=execution.metrics.get("token_count", 0),
                success=False,
                error="Execution reported failure",
            )

        scores = self._score(execution, task.expected, scorers)
        composite = self._compute_composite(scores)

        token_count = execution.metrics.get("token_count", 0)
        self._metric_collector.collect(
            task_id=task.id,
            duration_ms=duration_ms,
            token_count=token_count,
            scores=scores,
        )

        # C05: charge the cost budget, if configured.  The CostExceeded
        # exception propagates up to run() which converts it into a
        # break-out + final EvalResult so callers can see what happened.
        if self._cost_budget is not None:
            self._cost_budget.add(
                tokens=int(token_count),
                elapsed_s=duration_ms / 1000.0,
            )

        return EvalResult(
            task_id=task.id,
            task_name=task.name,
            output=execution.output,
            scores=scores,
            composite_score=composite,
            duration_ms=duration_ms,
            token_count=token_count,
            success=True,
        )

    @staticmethod
    def _validate(task: TaskDefinition) -> list[str]:
        """Validate a task definition, returning a list of error messages."""
        errors: list[str] = []
        if not task.id:
            errors.append("Task ID is required")
        if not task.name:
            errors.append("Task name is required")
        return errors

    @staticmethod
    def _execute(task: TaskDefinition, executor: ExecutorFn) -> ExecutionResult:
        """Execute a single evaluation task."""
        return executor(task)

    @staticmethod
    def _score(
        execution: ExecutionResult,
        expected: Any,
        scorers: list[ScorerProtocol],
    ) -> list[Score]:
        """Score task output against expected results."""
        scores: list[Score] = []
        for scorer in scorers:
            try:
                s = scorer.score(execution.output, expected)
                scores.append(s)
            except Exception as exc:
                logger.error("Scorer %s failed: %s", scorer.name(), exc)
                scores.append(
                    Score(
                        value=0.0,
                        scorer_name=scorer.name(),
                        breakdown={"error": str(exc)},
                    )
                )
        return scores

    @staticmethod
    def _compute_composite(scores: list[Score]) -> float:
        """Compute composite."""
        if not scores:
            return 0.0
        return sum(s.value for s in scores) / len(scores)
