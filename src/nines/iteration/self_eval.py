"""Self-evaluation runner and dimension evaluator protocol.

``SelfEvalRunner`` orchestrates evaluation across multiple dimensions
(code coverage, test count, module count, etc.) and produces a
``SelfEvalReport`` summarizing scores for each dimension.

Covers: FR-601, FR-602.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension.

    Attributes
    ----------
    name:
        Dimension identifier (e.g. ``"code_coverage"``).
    value:
        Numeric score value.
    max_value:
        Upper bound of the score range.
    metadata:
        Additional context or breakdown.
    """

    name: str
    value: float
    max_value: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized(self) -> float:
        if self.max_value == 0:
            return 0.0
        return self.value / self.max_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "max_value": self.max_value,
            "normalized": self.normalized,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DimensionScore:
        return cls(
            name=data["name"],
            value=data["value"],
            max_value=data.get("max_value", 1.0),
            metadata=data.get("metadata", {}),
        )


@runtime_checkable
class DimensionEvaluator(Protocol):
    """Protocol for evaluating a single dimension."""

    def evaluate(self) -> DimensionScore:
        """Run evaluation and return a score for this dimension."""
        ...


@dataclass
class SelfEvalReport:
    """Aggregate report from running all dimension evaluators.

    Attributes
    ----------
    scores:
        Per-dimension scores.
    overall:
        Weighted average of normalized dimension scores.
    version:
        Optional version tag for baseline comparison.
    timestamp:
        ISO-8601 timestamp of when the report was generated.
    duration:
        Total evaluation time in seconds.
    """

    scores: list[DimensionScore] = field(default_factory=list)
    overall: float = 0.0
    version: str = ""
    timestamp: str = ""
    duration: float = 0.0

    def get_score(self, dimension: str) -> DimensionScore | None:
        for s in self.scores:
            if s.name == dimension:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": [s.to_dict() for s in self.scores],
            "overall": self.overall,
            "version": self.version,
            "timestamp": self.timestamp,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelfEvalReport:
        return cls(
            scores=[DimensionScore.from_dict(s) for s in data.get("scores", [])],
            overall=data.get("overall", 0.0),
            version=data.get("version", ""),
            timestamp=data.get("timestamp", ""),
            duration=data.get("duration", 0.0),
        )


class SelfEvalRunner:
    """Orchestrates evaluation across multiple registered dimensions.

    Usage::

        runner = SelfEvalRunner()
        runner.register_dimension("test_count", TestCountEvaluator())
        runner.register_dimension("module_count", ModuleCountEvaluator())
        report = runner.run_all()
    """

    def __init__(self) -> None:
        self._evaluators: dict[str, DimensionEvaluator] = {}

    def register_dimension(self, name: str, evaluator: DimensionEvaluator) -> None:
        """Register an evaluator for a named dimension.

        Parameters
        ----------
        name:
            Unique dimension identifier.
        evaluator:
            Object implementing the ``DimensionEvaluator`` protocol.
        """
        self._evaluators[name] = evaluator
        logger.debug("Registered evaluator for dimension '%s'", name)

    def run_all(self, version: str = "") -> SelfEvalReport:
        """Run all registered evaluators and produce a report.

        Parameters
        ----------
        version:
            Optional version tag for the report.

        Returns
        -------
        SelfEvalReport
            Aggregate scores from all dimensions.
        """
        from datetime import datetime, timezone

        start = time.monotonic()
        scores: list[DimensionScore] = []

        for name, evaluator in self._evaluators.items():
            logger.info("Evaluating dimension '%s'", name)
            try:
                score = evaluator.evaluate()
                scores.append(score)
                logger.info(
                    "Dimension '%s': %.3f / %.3f (%.1f%%)",
                    name, score.value, score.max_value, score.normalized * 100,
                )
            except Exception as exc:
                logger.error("Evaluator for '%s' failed: %s", name, exc, exc_info=True)
                scores.append(DimensionScore(name=name, value=0.0, max_value=1.0))

        overall = 0.0
        if scores:
            overall = sum(s.normalized for s in scores) / len(scores)

        duration = time.monotonic() - start
        return SelfEvalReport(
            scores=scores,
            overall=overall,
            version=version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration=duration,
        )


# ---------------------------------------------------------------------------
# Built-in evaluators for simple dimensions
# ---------------------------------------------------------------------------


class CodeCoverageEvaluator:
    """Evaluator that reports a configured code coverage percentage."""

    def __init__(self, coverage_pct: float = 0.0) -> None:
        self._coverage = coverage_pct

    def evaluate(self) -> DimensionScore:
        return DimensionScore(
            name="code_coverage",
            value=self._coverage,
            max_value=100.0,
            metadata={"unit": "percent"},
        )


class UnitTestCountEvaluator:
    """Evaluator that reports a count of tests."""

    def __init__(self, count: int = 0) -> None:
        self._count = count

    def evaluate(self) -> DimensionScore:
        return DimensionScore(
            name="test_count",
            value=float(self._count),
            max_value=float(max(self._count, 1)),
            metadata={"unit": "tests"},
        )


TestCountEvaluator = UnitTestCountEvaluator


class ModuleCountEvaluator:
    """Evaluator that reports a count of modules."""

    def __init__(self, count: int = 0) -> None:
        self._count = count

    def evaluate(self) -> DimensionScore:
        return DimensionScore(
            name="module_count",
            value=float(self._count),
            max_value=float(max(self._count, 1)),
            metadata={"unit": "modules"},
        )
