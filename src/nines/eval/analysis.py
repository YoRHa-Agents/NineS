"""Per-dimension analysis of evaluation results.

``AxisAnalyzer`` groups ``EvalResult`` objects by their task dimension and
computes per-dimension statistics: mean, std, min, max, and pass_rate.

Covers: FR-117.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.eval.models import EvalResult

logger = logging.getLogger(__name__)


@dataclass
class DimensionStats:
    """Aggregated statistics for a single evaluation dimension."""

    dimension: str
    count: int = 0
    mean: float = 0.0
    std: float = 0.0
    min: float = 0.0
    max: float = 0.0
    pass_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "dimension": self.dimension,
            "count": self.count,
            "mean": self.mean,
            "std": self.std,
            "min": self.min,
            "max": self.max,
            "pass_rate": self.pass_rate,
        }


class AxisAnalyzer:
    """Groups evaluation results by dimension and computes per-dimension stats."""

    def __init__(self, pass_threshold: float = 0.5) -> None:
        """Initialize axis analyzer."""
        self._pass_threshold = pass_threshold

    def group_by_dimension(self, results: list[EvalResult]) -> dict[str, list[EvalResult]]:
        """Group results by dimension using task_id prefix as a heuristic.

        Prefer :meth:`group_by` with an explicit ``dimension_map`` for
        reliable grouping.
        """
        groups: dict[str, list[EvalResult]] = defaultdict(list)
        for r in results:
            dim = r.task_id.rsplit("-", 1)[0] or "unknown"
            groups[dim].append(r)
        return dict(groups)

    def group_by(
        self,
        results: list[EvalResult],
        dimension_map: dict[str, str] | None = None,
    ) -> dict[str, list[EvalResult]]:
        """Group results by dimension using an explicit task_id → dimension map."""
        groups: dict[str, list[EvalResult]] = defaultdict(list)
        dm = dimension_map or {}
        for r in results:
            dim = dm.get(r.task_id, "unknown")
            groups[dim].append(r)
        return dict(groups)

    def compute_stats(self, results: list[EvalResult]) -> DimensionStats:
        """Compute aggregate stats for a flat list of results sharing one dimension."""
        if not results:
            return DimensionStats(dimension="empty")

        scores = [r.composite_score for r in results]
        n = len(scores)
        mean = sum(scores) / n
        variance = sum((s - mean) ** 2 for s in scores) / n
        std = math.sqrt(variance)
        passed = sum(1 for r in results if r.success and r.composite_score >= self._pass_threshold)

        return DimensionStats(
            dimension="",
            count=n,
            mean=mean,
            std=std,
            min=min(scores),
            max=max(scores),
            pass_rate=passed / n,
        )

    def analyze(
        self,
        results: list[EvalResult],
        dimension_map: dict[str, str] | None = None,
    ) -> dict[str, DimensionStats]:
        """Full analysis: group by dimension, compute stats per group."""
        groups = self.group_by(results, dimension_map)
        stats: dict[str, DimensionStats] = {}
        for dim, group_results in groups.items():
            ds = self.compute_stats(group_results)
            ds.dimension = dim
            stats[dim] = ds
        return stats
