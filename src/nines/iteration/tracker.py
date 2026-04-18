"""Iteration lifecycle tracking with trend analysis.

``IterationTracker`` records the start and completion of each
iteration round, accumulating reports for trend analysis.

C07 (v3.2.0): the tracker also stores per-version
:class:`~nines.iteration.gates.GateResult` history so that a
``QualityGate`` regression can be correlated with the iteration that
introduced it.

Covers: FR-609.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from nines.core.errors import OrchestrationError

if TYPE_CHECKING:
    from nines.iteration.gates import GateResult
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
        """Serialize to dictionary."""
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
        """Serialize to dictionary."""
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

    C07: each iteration's gate results can be recorded and queried::

        tracker.record_gate_results("v1", [graph_gate_result, econ_gate_result])
        history = tracker.gate_history("v1")
    """

    def __init__(self) -> None:
        """Initialize iteration tracker."""
        self._iterations: list[IterationRecord] = []
        self._current: IterationRecord | None = None
        self._start_time: float = 0.0
        # Per-version history of gate verdicts.  ``list`` (not ``dict``)
        # values preserve append order for chronological replay.
        self._gate_history: dict[str, list[GateResult]] = {}

    def start_iteration(self, version: str) -> None:
        """Begin a new iteration round.

        Parameters
        ----------
        version:
            Version label for this iteration.
        """
        self._current = IterationRecord(
            version=version,
            started_at=datetime.now(UTC).isoformat(),
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

        self._current.completed_at = datetime.now(UTC).isoformat()
        self._current.report = report
        self._current.duration = time.monotonic() - self._start_time
        self._iterations.append(self._current)
        logger.info(
            "Completed iteration '%s' (overall=%.3f, duration=%.3fs)",
            self._current.version,
            report.overall,
            self._current.duration,
        )
        self._current = None

    def record_gate_results(
        self,
        version: str,
        results: list[GateResult],
    ) -> None:
        """Append C07 gate results to the per-version history.

        Calling this multiple times for the same version *appends*
        rather than overwrites — useful when gates are re-run after
        partial-run remediation.  Each call's results are appended in
        the order provided so :meth:`gate_history` returns them in
        chronological order.

        Parameters
        ----------
        version:
            Iteration version label (matches
            :attr:`IterationRecord.version`).
        results:
            List of :class:`~nines.iteration.gates.GateResult` to
            record.  Empty lists are accepted (they create the bucket
            without adding entries).

        Raises
        ------
        ValueError
            If ``version`` is empty.
        """
        if not version:
            raise ValueError("version must be a non-empty string")
        bucket = self._gate_history.setdefault(version, [])
        bucket.extend(results)
        logger.info(
            "Recorded %d gate result(s) for iteration '%s' (total now %d)",
            len(results),
            version,
            len(bucket),
        )

    def gate_history(self, version: str) -> list[GateResult]:
        """Return the chronological gate results for ``version``.

        Returns an empty list when no gates have been recorded for the
        requested version (rather than raising) so callers can use the
        accessor unconditionally.
        """
        return list(self._gate_history.get(version, []))

    def get_progress(self) -> ProgressReport:
        """Generate a summary of iteration progress.

        Returns
        -------
        ProgressReport
            Trend analysis and summary statistics.
        """
        if not self._iterations:
            return ProgressReport()

        overall_trend = [it.report.overall for it in self._iterations if it.report is not None]

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
