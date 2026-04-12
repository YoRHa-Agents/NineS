"""Gap detection between evaluation reports.

``GapDetector`` compares a current ``SelfEvalReport`` against a baseline
to identify improved, regressed, and stagnated dimensions, then
prioritizes gaps by severity for the improvement planner.

Covers: FR-606, FR-607.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from nines.iteration.self_eval import SelfEvalReport

logger = logging.getLogger(__name__)


@dataclass
class Gap:
    """A single detected gap between current and baseline scores.

    Attributes
    ----------
    dimension:
        Name of the affected dimension.
    current:
        Current normalized score.
    baseline:
        Baseline normalized score.
    delta:
        Change amount (current - baseline).
    severity:
        Absolute magnitude of regression, 0.0 for non-regressions.
    """

    dimension: str
    current: float
    baseline: float
    delta: float
    severity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "current": self.current,
            "baseline": self.baseline,
            "delta": self.delta,
            "severity": self.severity,
        }


@dataclass
class GapAnalysis:
    """Result of comparing current scores against a baseline.

    Attributes
    ----------
    improved:
        Dimensions that scored higher than baseline.
    regressed:
        Dimensions that scored lower than baseline.
    stagnated:
        Dimensions with no meaningful change.
    priority_gaps:
        Regressed dimensions sorted by severity (worst first).
    """

    improved: list[Gap] = field(default_factory=list)
    regressed: list[Gap] = field(default_factory=list)
    stagnated: list[Gap] = field(default_factory=list)
    priority_gaps: list[Gap] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "improved": [g.to_dict() for g in self.improved],
            "regressed": [g.to_dict() for g in self.regressed],
            "stagnated": [g.to_dict() for g in self.stagnated],
            "priority_gaps": [g.to_dict() for g in self.priority_gaps],
        }


class GapDetector:
    """Detects and prioritizes gaps between evaluation reports.

    Parameters
    ----------
    tolerance:
        Minimum absolute delta to consider a change significant.
    """

    def __init__(self, tolerance: float = 0.01) -> None:
        self._tolerance = tolerance

    def detect(
        self, current: SelfEvalReport, baseline: SelfEvalReport
    ) -> GapAnalysis:
        """Compare current report against baseline and categorize gaps.

        Parameters
        ----------
        current:
            The fresh evaluation report.
        baseline:
            The reference baseline report.

        Returns
        -------
        GapAnalysis
            Categorized gaps with priority ordering.
        """
        analysis = GapAnalysis()
        baseline_map: dict[str, float] = {}
        for score in baseline.scores:
            baseline_map[score.name] = score.normalized

        for score in current.scores:
            base_val = baseline_map.get(score.name, 0.0)
            delta = score.normalized - base_val
            severity = abs(delta) if delta < -self._tolerance else 0.0

            gap = Gap(
                dimension=score.name,
                current=score.normalized,
                baseline=base_val,
                delta=delta,
                severity=severity,
            )

            if delta > self._tolerance:
                analysis.improved.append(gap)
            elif delta < -self._tolerance:
                analysis.regressed.append(gap)
            else:
                analysis.stagnated.append(gap)

        analysis.priority_gaps = sorted(
            analysis.regressed, key=lambda g: g.severity, reverse=True
        )

        logger.info(
            "Gap analysis: %d improved, %d regressed, %d stagnated, %d priority",
            len(analysis.improved),
            len(analysis.regressed),
            len(analysis.stagnated),
            len(analysis.priority_gaps),
        )
        return analysis
