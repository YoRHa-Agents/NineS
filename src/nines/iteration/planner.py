"""Improvement planning based on detected gaps.

``ImprovementPlanner`` maps gaps from ``GapAnalysis`` to concrete
improvement suggestions with priority levels and estimated effort.

C07 (v3.2.0): :class:`ImprovementPlan` now carries an optional
``gate_results`` channel for :class:`~nines.iteration.gates.GateResult`
objects produced alongside the plan.  Gate verdicts are a *parallel*
signal — they do not influence the existing severity-based suggestion
ordering, and the planner exposes them via :meth:`ImprovementPlan.to_dict`
so downstream consumers can audit a plan together with the gates that
were observed when it was generated.

Covers: FR-608.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.iteration.gap_detector import GapAnalysis
    from nines.iteration.gates import GateResult

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
    gate_results:
        C07 gate verdicts captured alongside the plan.  Optional —
        callers that don't run gates leave it empty.  Gate results do
        *not* influence ``suggestions`` ordering; they are a parallel
        signal channel for downstream auditors.
    """

    suggestions: list[Suggestion] = field(default_factory=list)
    total_gaps: int = 0
    gate_results: list["GateResult"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary, including gate results when present."""
        return {
            "suggestions": [s.to_dict() for s in self.suggestions],
            "total_gaps": self.total_gaps,
            "gate_results": [g.to_dict() for g in self.gate_results],
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
            len(suggestions),
            plan.total_gaps,
        )
        return plan

    def create_plan(
        self,
        gap_analysis: GapAnalysis | None = None,
        *,
        gate_results: list["GateResult"] | None = None,
    ) -> ImprovementPlan:
        """Build an :class:`ImprovementPlan` with optional gate verdicts.

        Convenience wrapper around :meth:`plan` that lets callers
        attach a list of :class:`~nines.iteration.gates.GateResult`
        objects directly to the produced plan.  When ``gap_analysis``
        is ``None`` an empty plan is returned (useful when gates are
        the only signal available).

        Parameters
        ----------
        gap_analysis:
            Optional output from :meth:`GapDetector.detect`.
        gate_results:
            Optional list of gate verdicts to attach to the plan.

        Returns
        -------
        ImprovementPlan
            A plan with both severity-ordered suggestions and any
            attached gate verdicts.
        """
        if gap_analysis is not None:
            plan = self.plan(gap_analysis)
        else:
            plan = ImprovementPlan()

        if gate_results:
            plan.gate_results = list(gate_results)
            logger.info(
                "Attached %d gate result(s) to ImprovementPlan",
                len(plan.gate_results),
            )

        return plan

    @staticmethod
    def _estimate_effort(severity: float) -> str:
        """Estimate effort."""
        for threshold, label in _EFFORT_THRESHOLDS.items():
            if severity >= threshold:
                return label
        return "low"
