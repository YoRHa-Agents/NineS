"""Convergence detection using sliding window variance.

``ConvergenceChecker`` determines whether a sequence of scores has
stabilized by measuring the variance within a recent window and
comparing it against a threshold.

Covers: FR-610.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConvergenceResult:
    """Outcome of a convergence check.

    Attributes
    ----------
    converged:
        Whether the series has converged.
    variance:
        Computed variance within the checked window.
    rounds_checked:
        Number of data points in the checked window.
    mean:
        Mean of the values in the checked window.
    """

    converged: bool
    variance: float
    rounds_checked: int
    mean: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "converged": self.converged,
            "variance": self.variance,
            "rounds_checked": self.rounds_checked,
            "mean": self.mean,
        }


class ConvergenceChecker:
    """Detects convergence via sliding window variance.

    The series is considered converged when the variance of the last
    ``window_size`` values falls below the specified ``threshold``.

    Parameters
    ----------
    window_size:
        Number of recent values to consider.
    min_rounds:
        Minimum number of data points required before convergence
        can be declared.
    """

    def __init__(self, window_size: int = 5, min_rounds: int = 3) -> None:
        """Initialize convergence checker."""
        self._window_size = window_size
        self._min_rounds = min_rounds

    def check(
        self, history: list[float], threshold: float = 0.05
    ) -> ConvergenceResult:
        """Check whether the score history has converged.

        Parameters
        ----------
        history:
            Ordered list of score values (oldest to newest).
        threshold:
            Maximum variance to consider the series converged.

        Returns
        -------
        ConvergenceResult
            Whether convergence was detected and supporting statistics.
        """
        if len(history) < self._min_rounds:
            logger.debug(
                "Not enough rounds (%d < %d) for convergence check",
                len(history), self._min_rounds,
            )
            return ConvergenceResult(
                converged=False,
                variance=float("inf"),
                rounds_checked=len(history),
            )

        window = history[-self._window_size:]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)

        converged = variance <= threshold
        logger.info(
            "Convergence check: variance=%.6f, threshold=%.6f, converged=%s "
            "(window=%d values)",
            variance, threshold, converged, len(window),
        )

        return ConvergenceResult(
            converged=converged,
            variance=variance,
            rounds_checked=len(window),
            mean=mean,
        )
