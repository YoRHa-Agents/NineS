"""Score history tracking for self-evaluation trends.

``ScoreHistory`` maintains an in-memory ordered log of
``SelfEvalReport`` snapshots and provides trend analysis for individual
dimensions over a sliding window.

Covers: FR-605.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nines.iteration.self_eval import SelfEvalReport

logger = logging.getLogger(__name__)


class ScoreHistory:
    """Ordered history of self-evaluation reports with trend queries.

    Usage::

        history = ScoreHistory()
        history.record(report_v1)
        history.record(report_v2)
        trend = history.get_trend("code_coverage", window=5)
    """

    def __init__(self) -> None:
        """Initialize score history."""
        self._reports: list[SelfEvalReport] = []

    def record(self, report: SelfEvalReport) -> None:
        """Append a report to the history.

        Parameters
        ----------
        report:
            The evaluation report to record.
        """
        self._reports.append(report)
        logger.debug(
            "Recorded report (version=%s, overall=%.3f), history length=%d",
            report.version, report.overall, len(self._reports),
        )

    def get_trend(self, dimension: str, window: int = 10) -> list[float]:
        """Return recent normalized scores for a specific dimension.

        Parameters
        ----------
        dimension:
            Name of the dimension to query.
        window:
            Maximum number of most-recent reports to include.

        Returns
        -------
        list[float]
            Normalized scores from oldest to newest within the window.
        """
        recent = self._reports[-window:] if window > 0 else self._reports
        values: list[float] = []
        for report in recent:
            score = report.get_score(dimension)
            if score is not None:
                values.append(score.normalized)
        return values

    def get_all(self) -> list[SelfEvalReport]:
        """Return all recorded reports in chronological order."""
        return list(self._reports)

    def get_overall_trend(self, window: int = 10) -> list[float]:
        """Return recent overall scores.

        Parameters
        ----------
        window:
            Maximum number of most-recent reports to include.

        Returns
        -------
        list[float]
            Overall scores from oldest to newest within the window.
        """
        recent = self._reports[-window:] if window > 0 else self._reports
        return [r.overall for r in recent]

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._reports)
