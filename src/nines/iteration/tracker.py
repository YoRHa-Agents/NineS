"""Iteration lifecycle tracking with trend analysis.

``IterationTracker`` records the start and completion of each
iteration round, accumulating reports for trend analysis.

Covers: FR-609.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from nines.core.errors import OrchestrationError
from nines.iteration.self_eval import SelfEvalReport

logger = logging.getLogger(__name__)


@dataclass
class IterationRecord:
    """Record of a single iteration round.

    Attributes
    ----------
    version:
        Version label for this iteration.
    started_at:
        ISO-8601 timestamp when the iteration started.
    completed_at:
        ISO-8601 timestamp when the iteration completed, or empty.
    report:
        The evaluation report produced upon completion.
    duration:
        Wall-clock seconds for this iteration.
    """

    version: str
    started_at: str = ""
    completed_at: str = ""
    report: SelfEvalReport | None = None
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "report": self.report.to_dict() if self.report else None,
            "duration": self.duration,
        }


@dataclass
class ProgressReport:
    """Summary of iteration progress with trend analysis.

    Attributes
    ----------
    total_iterations:
        Number of completed iterations.
    current_version:
        Version label of the most recent completed iteration.
    overall_trend:
        List of overall scores from each iteration.
    improving:
        Whether the most recent score improved over the previous one.
    best_score:
        Highest overall score seen so far.
    """

    total_iterations: int = 0
    current_version: str = ""
    overall_trend: list[float] = field(default_factory=list)
    improving: bool = False
    best_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_iterations": self.total_iterations,
            "current_version": self.current_version,
            "overall_trend": list(self.overall_trend),
            "improving": self.improving,
            "best_score": self.best_score,
        }


class IterationTracker:
    """Tracks iteration lifecycle and provides progress summaries.

    Usage::

        tracker = IterationTracker()
        tracker.start_iteration("v1")
        # ... run iteration ...
        tracker.complete_iteration(report_v1)
        progress = tracker.get_progress()
    """

    def __init__(self) -> None:
        self._iterations: list[IterationRecord] = []
        self._current: IterationRecord | None = None
        self._start_time: float = 0.0

    def start_iteration(self, version: str) -> None:
        """Begin a new iteration round.

        Parameters
        ----------
        version:
            Version label for this iteration.
        """
        self._current = IterationRecord(
            version=version,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._start_time = time.monotonic()
        logger.info("Started iteration '%s'", version)

    def complete_iteration(self, report: SelfEvalReport) -> None:
        """Complete the current iteration with the given report.

        Parameters
        ----------
        report:
            Evaluation report produced by this iteration.

        Raises
        ------
        RuntimeError
            If no iteration is currently in progress.
        """
        if self._current is None:
            raise OrchestrationError(
                "No iteration in progress",
                details={"hint": "Call start_iteration() before complete_iteration()"},
            )

        self._current.completed_at = datetime.now(timezone.utc).isoformat()
        self._current.report = report
        self._current.duration = time.monotonic() - self._start_time
        self._iterations.append(self._current)
        logger.info(
            "Completed iteration '%s' (overall=%.3f, duration=%.3fs)",
            self._current.version, report.overall, self._current.duration,
        )
        self._current = None

    def get_progress(self) -> ProgressReport:
        """Generate a summary of iteration progress.

        Returns
        -------
        ProgressReport
            Trend analysis and summary statistics.
        """
        if not self._iterations:
            return ProgressReport()

        overall_trend = [
            it.report.overall
            for it in self._iterations
            if it.report is not None
        ]

        improving = False
        if len(overall_trend) >= 2:
            improving = overall_trend[-1] > overall_trend[-2]

        best = max(overall_trend) if overall_trend else 0.0
        latest = self._iterations[-1]

        return ProgressReport(
            total_iterations=len(self._iterations),
            current_version=latest.version,
            overall_trend=overall_trend,
            improving=improving,
            best_score=best,
        )
