"""Metric collection and reliability calculation for evaluation runs.

``MetricCollector`` gathers per-task metrics (duration, token count, scores)
during pipeline execution.

``ReliabilityCalculator`` computes statistical reliability metrics:
``pass_at_k``, ``pass_power_k``, and ``consistency_score`` from multiple
trial results.

Covers: FR-108, FR-109, FR-110 (reliability metrics).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import comb, nan
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.core.models import Score


@dataclass
class TaskMetrics:
    """Collected metrics for a single task execution."""

    task_id: str
    duration_ms: float = 0.0
    token_count: int = 0
    score_values: list[float] = field(default_factory=list)
    scorer_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "duration_ms": self.duration_ms,
            "token_count": self.token_count,
            "score_values": list(self.score_values),
            "scorer_names": list(self.scorer_names),
        }


class MetricCollector:
    """Collects per-task metrics during evaluation pipeline execution."""

    def __init__(self) -> None:
        """Initialize metric collector."""
        self._metrics: dict[str, TaskMetrics] = {}

    def collect(
        self,
        task_id: str,
        duration_ms: float = 0.0,
        token_count: int = 0,
        scores: list[Score] | None = None,
    ) -> TaskMetrics:
        """Record metrics for a task, overwriting any prior entry."""
        score_values = [s.value for s in scores] if scores else []
        scorer_names = [s.scorer_name for s in scores] if scores else []

        metrics = TaskMetrics(
            task_id=task_id,
            duration_ms=duration_ms,
            token_count=token_count,
            score_values=score_values,
            scorer_names=scorer_names,
        )
        self._metrics[task_id] = metrics
        return metrics

    def get(self, task_id: str) -> TaskMetrics | None:
        """Return a metric value by name."""
        return self._metrics.get(task_id)

    def all_metrics(self) -> list[TaskMetrics]:
        """All metrics."""
        return list(self._metrics.values())

    def summary(self) -> dict[str, Any]:
        """Aggregate summary across all collected tasks."""
        if not self._metrics:
            return {"task_count": 0}
        all_durations = [m.duration_ms for m in self._metrics.values()]
        all_tokens = [m.token_count for m in self._metrics.values()]
        return {
            "task_count": len(self._metrics),
            "total_duration_ms": sum(all_durations),
            "avg_duration_ms": sum(all_durations) / len(all_durations),
            "total_tokens": sum(all_tokens),
        }


class ReliabilityCalculator:
    """Computes statistical reliability metrics from multiple trial scores.

    Designed for repeated evaluation runs where the same task is executed
    ``n`` times, producing ``n`` scores. The calculator determines how
    consistently the task passes.
    """

    @staticmethod
    def pass_at_k(n: int, c: int, k: int) -> float:
        """Unbiased estimator for probability of at least 1 correct in k draws.

        Formula: ``1 - C(n-c, k) / C(n, k)``

        Parameters
        ----------
        n:  total number of samples
        c:  number of correct/passing samples
        k:  number of draws
        """
        if k == 0:
            return 1.0
        if n == 0:
            return 0.0
        if c >= n:
            return 1.0
        if c == 0:
            return 0.0
        if k > n:
            return nan
        return 1.0 - comb(n - c, k) / comb(n, k)

    @staticmethod
    def pass_power_k(n: int, c: int, k: int) -> float:
        """Pessimistic reliability: probability ALL k trials succeed.

        Formula: ``(c/n)^k``

        Parameters
        ----------
        n:  total number of samples
        c:  number of correct/passing samples
        k:  exponent (number of required successes)
        """
        if n == 0:
            return nan
        return (c / n) ** k

    @staticmethod
    def consistency_score(scores: list[float]) -> float:
        """Coefficient-of-variation complement: ``1 - (std / mean)``.

        Values near 1.0 indicate high consistency across trials.
        Returns NaN for empty input or zero-mean scores.
        """
        if not scores:
            return nan
        if len(scores) == 1:
            return 1.0
        n = len(scores)
        mean = sum(scores) / n
        if abs(mean) < 1e-15:
            return nan
        variance = sum((x - mean) ** 2 for x in scores) / n
        std = variance**0.5
        return 1.0 - std / mean
