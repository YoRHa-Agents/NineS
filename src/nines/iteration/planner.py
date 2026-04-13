"""Improvement planning based on detected gaps.

``ImprovementPlanner`` maps gaps from ``GapAnalysis`` to concrete
improvement suggestions with priority levels and estimated effort.

Covers: FR-608.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.iteration.gap_detector import GapAnalysis

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    """A single improvement suggestion.

    Attributes
    ----------
    dimension:
        The dimension this suggestion targets.
    action:
        Recommended action to address the gap.
    priority:
        Priority level (1 = highest).
    estimated_effort:
        Estimated effort label (``"low"``, ``"medium"``, ``"high"``).
    rationale:
        Why this suggestion was generated.
    """

    dimension: str
    action: str
    priority: int
    estimated_effort: str = "medium"
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "dimension": self.dimension,
            "action": self.action,
            "priority": self.priority,
            "estimated_effort": self.estimated_effort,
            "rationale": self.rationale,
        }


@dataclass
class ImprovementPlan:
    """Ordered list of improvement suggestions.

    Attributes
    ----------
    suggestions:
        Suggestions sorted by priority (highest first).
    total_gaps:
        Number of gaps that triggered planning.
    """

    suggestions: list[Suggestion] = field(default_factory=list)
    total_gaps: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "suggestions": [s.to_dict() for s in self.suggestions],
            "total_gaps": self.total_gaps,
        }


_EFFORT_THRESHOLDS = {
    0.3: "high",
    0.15: "medium",
    0.0: "low",
}


class ImprovementPlanner:
    """Maps gap analysis results to prioritized improvement suggestions."""

    def plan(self, gap_analysis: GapAnalysis) -> ImprovementPlan:
        """Generate an improvement plan from gap analysis.

        Priority is assigned based on severity ranking within the
        ``priority_gaps`` list (worst regression gets priority 1).
        Estimated effort is derived from the gap severity magnitude.

        Parameters
        ----------
        gap_analysis:
            Output from ``GapDetector.detect()``.

        Returns
        -------
        ImprovementPlan
            Ordered suggestions for closing detected gaps.
        """
        suggestions: list[Suggestion] = []

        for rank, gap in enumerate(gap_analysis.priority_gaps, start=1):
            effort = self._estimate_effort(gap.severity)
            suggestion = Suggestion(
                dimension=gap.dimension,
                action=f"Improve {gap.dimension}: regressed by {abs(gap.delta):.3f}",
                priority=rank,
                estimated_effort=effort,
                rationale=(
                    f"Score dropped from {gap.baseline:.3f} to {gap.current:.3f} "
                    f"(delta={gap.delta:+.3f})"
                ),
            )
            suggestions.append(suggestion)

        for gap in gap_analysis.stagnated:
            suggestion = Suggestion(
                dimension=gap.dimension,
                action=f"Review {gap.dimension}: no progress detected",
                priority=len(suggestions) + 1,
                estimated_effort="low",
                rationale=f"Score stagnated at {gap.current:.3f}",
            )
            suggestions.append(suggestion)

        plan = ImprovementPlan(
            suggestions=suggestions,
            total_gaps=len(gap_analysis.regressed) + len(gap_analysis.stagnated),
        )
        logger.info(
            "Generated improvement plan: %d suggestions for %d gaps",
            len(suggestions), plan.total_gaps,
        )
        return plan

    @staticmethod
    def _estimate_effort(severity: float) -> str:
        """Estimate effort."""
        for threshold, label in _EFFORT_THRESHOLDS.items():
            if severity >= threshold:
                return label
        return "low"
