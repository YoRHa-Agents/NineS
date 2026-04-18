"""Quality-gate state machine — institutionalises Wave 1 data-quality wins.

C07 (v3.2.0): rather than passively reporting graph verification (C03),
context-economics (C09), and self-eval coverage as informational metrics,
:mod:`nines.iteration.gates` exposes them as *enforced* gates with a
documented lifecycle.  Gates are run by :class:`GateRunner` in either
*advisory* mode (warns on failure, never aborts — default for one minor
release) or *strict* mode (fails build on any blocking severity).

The module ships four built-in gates:

* :class:`GraphVerificationGate` — consumes ``analyze --strategy graph``
  output and fails when ``verification.passed`` regresses or when
  critical-severity issues exceed a threshold.
* :class:`EconomicsScoreGate` — consumes an ``analyze`` report and
  fails when the C09 ``economics.economics_score`` falls below a floor.
* :class:`SelfEvalCoverageGate` — consumes a
  :class:`~nines.iteration.self_eval.SelfEvalReport` and fails when the
  ``overall`` weighted average falls below a coverage minimum.
* :class:`RegressionGate` — flags a meaningful drop versus a trailing
  window of historical snapshots.

Covers: FR-608 (improvement-plan lifecycle), FR-320 (verification gating),
FR-313 (economics gating).
"""

from __future__ import annotations

import logging
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class GateStatus(str, Enum):  # noqa: UP042 — keep (str, Enum) form to preserve __str__ semantics
    """Lifecycle state of a single gate evaluation.

    The values are deliberately ordered to read as a state machine:

    ``PROPOSED`` → ``EVALUATING`` → (``PASSED`` | ``FAILED`` |
    ``ESCALATED`` | ``BYPASSED``).

    * ``PROPOSED`` — the gate exists but has not run yet.
    * ``EVALUATING`` — the gate is mid-evaluation (transient).
    * ``PASSED`` — the gate's metric satisfied the threshold.
    * ``FAILED`` — the metric breached the threshold (severity is
      promoted to ``"warn"`` in advisory mode, ``"block"`` in strict).
    * ``ESCALATED`` — the gate raised an exception and the runner had
      to escalate the failure rather than mask it.
    * ``BYPASSED`` — the gate could not run (e.g. missing metrics) and
      was skipped without a verdict.
    """

    PROPOSED = "proposed"
    EVALUATING = "evaluating"
    PASSED = "passed"
    FAILED = "failed"
    ESCALATED = "escalated"
    BYPASSED = "bypassed"


Severity = Literal["info", "warn", "block"]


@dataclass
class GateResult:
    """One gate evaluation outcome.

    Attributes
    ----------
    gate_name:
        Stable identifier for the gate (e.g. ``"graph_verification"``).
    status:
        :class:`GateStatus` after evaluation.
    metric_name:
        Human-readable name of the metric that was checked.
    metric_value:
        Numeric value observed.
    threshold:
        Numeric threshold the value was compared against.
    verdict:
        One-line human reason describing the outcome.
    severity:
        ``"info"`` for passing/bypassed gates, ``"warn"`` for failures
        in advisory mode, ``"block"`` for failures in strict mode.
    metadata:
        Free-form structured payload (e.g. raw verification dict).
    """

    gate_name: str
    status: GateStatus
    metric_name: str
    metric_value: float
    threshold: float
    verdict: str
    severity: Severity = "info"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary for JSON output."""
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "verdict": self.verdict,
            "severity": self.severity,
            "metadata": dict(self.metadata),
        }


def _attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    """Return ``obj.key`` or ``obj[key]`` or ``default``.

    Gates consume a mix of dataclasses (``SelfEvalReport``,
    ``VerificationResult``) and serialised dicts (the
    ``AnalysisResult.metrics["knowledge_graph"]["verification"]``
    payload is a ``dict``).  Centralising the lookup here keeps the
    gates liberal in what they accept.
    """
    if obj is None:
        return default
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict) and key in obj:
        return obj[key]
    return default


class QualityGate(ABC):
    """Abstract base class for all quality gates.

    Subclasses implement :meth:`evaluate` and expose a stable
    :attr:`name` used for registry lookup and result correlation.
    """

    name: str = "quality_gate"

    @abstractmethod
    def evaluate(self, report: Any) -> GateResult:
        """Run the gate against ``report`` and return a verdict."""
        raise NotImplementedError


class GraphVerificationGate(QualityGate):
    """Fails when graph verification regresses or critical issues exceed a threshold.

    Consumes an analyze-strategy-graph result whose ``metrics`` dict
    contains ``knowledge_graph.verification``.  When that payload is
    absent the gate becomes :attr:`GateStatus.BYPASSED` rather than
    falsely passing or failing.

    Parameters
    ----------
    threshold_critical_issues:
        Maximum allowed number of critical-severity verification
        issues.  Default ``0`` enforces the C03 invariant that no
        critical findings ship in a release.
    """

    name = "graph_verification"

    def __init__(self, threshold_critical_issues: int = 0) -> None:
        if threshold_critical_issues < 0:
            raise ValueError(
                f"threshold_critical_issues must be >= 0, got {threshold_critical_issues}"
            )
        self.threshold_critical_issues = threshold_critical_issues

    def evaluate(self, report: Any) -> GateResult:
        """Inspect ``report.metrics.knowledge_graph.verification``."""
        metrics = _attr_or_key(report, "metrics", {}) or {}
        kg = _attr_or_key(metrics, "knowledge_graph", {}) or {}
        verification = _attr_or_key(kg, "verification", None)

        if verification is None:
            return GateResult(
                gate_name=self.name,
                status=GateStatus.BYPASSED,
                metric_name="knowledge_graph.verification.passed",
                metric_value=0.0,
                threshold=float(self.threshold_critical_issues),
                verdict=("No knowledge_graph.verification metrics present; gate bypassed."),
                severity="info",
                metadata={"reason": "missing_metrics"},
            )

        passed = bool(_attr_or_key(verification, "passed", False))
        issues = _attr_or_key(verification, "issues", []) or []
        critical_count = 0
        for iss in issues:
            sev = _attr_or_key(iss, "severity", "info")
            if sev == "critical":
                critical_count += 1

        if (not passed) or critical_count > self.threshold_critical_issues:
            verdict = (
                f"verification.passed={passed}, critical_issues={critical_count} "
                f"(threshold={self.threshold_critical_issues})"
            )
            return GateResult(
                gate_name=self.name,
                status=GateStatus.FAILED,
                metric_name="critical_issue_count",
                metric_value=float(critical_count),
                threshold=float(self.threshold_critical_issues),
                verdict=verdict,
                severity="warn",
                metadata={
                    "verification_passed": passed,
                    "critical_count": critical_count,
                },
            )

        return GateResult(
            gate_name=self.name,
            status=GateStatus.PASSED,
            metric_name="critical_issue_count",
            metric_value=float(critical_count),
            threshold=float(self.threshold_critical_issues),
            verdict=(
                f"verification passed with {critical_count} critical issue(s) "
                f"(<= threshold={self.threshold_critical_issues})"
            ),
            severity="info",
            metadata={
                "verification_passed": True,
                "critical_count": critical_count,
            },
        )


class EconomicsScoreGate(QualityGate):
    """Fails when the C09 ``economics_score`` falls below ``min_score``.

    Consumes an analyze result whose ``metrics["agent_impact"]`` is a
    serialised :class:`~nines.analyzer.agent_impact.AgentImpactReport`.
    Missing economics produces a :attr:`GateStatus.BYPASSED` verdict.
    """

    name = "economics_score"

    def __init__(self, min_score: float = 0.10) -> None:
        if not 0.0 <= min_score <= 1.0:
            raise ValueError(f"min_score must be in [0.0, 1.0], got {min_score}")
        self.min_score = float(min_score)

    def evaluate(self, report: Any) -> GateResult:
        """Inspect ``report.metrics.agent_impact.economics.economics_score``."""
        metrics = _attr_or_key(report, "metrics", {}) or {}
        agent_impact = _attr_or_key(metrics, "agent_impact", {}) or {}
        economics = _attr_or_key(agent_impact, "economics", None)

        if economics is None:
            return GateResult(
                gate_name=self.name,
                status=GateStatus.BYPASSED,
                metric_name="agent_impact.economics.economics_score",
                metric_value=0.0,
                threshold=self.min_score,
                verdict=("No agent_impact.economics metrics present; gate bypassed."),
                severity="info",
                metadata={"reason": "missing_metrics"},
            )

        score = float(_attr_or_key(economics, "economics_score", 0.0))
        formula_version = _attr_or_key(economics, "formula_version", None)

        if score < self.min_score:
            return GateResult(
                gate_name=self.name,
                status=GateStatus.FAILED,
                metric_name="economics_score",
                metric_value=score,
                threshold=self.min_score,
                verdict=(f"economics_score={score:.4f} < threshold={self.min_score:.4f}"),
                severity="warn",
                metadata={"formula_version": formula_version},
            )

        return GateResult(
            gate_name=self.name,
            status=GateStatus.PASSED,
            metric_name="economics_score",
            metric_value=score,
            threshold=self.min_score,
            verdict=(f"economics_score={score:.4f} >= threshold={self.min_score:.4f}"),
            severity="info",
            metadata={"formula_version": formula_version},
        )


class SelfEvalCoverageGate(QualityGate):
    """Fails when the self-eval ``overall`` weighted score is below a floor.

    Consumes a :class:`~nines.iteration.self_eval.SelfEvalReport` and
    treats ``report.overall`` as the metric.  Reports missing
    ``overall`` are :attr:`GateStatus.BYPASSED` rather than counted as
    failures (defensive against partial reports from C04 timeouts).
    """

    name = "self_eval_coverage"

    def __init__(self, min_overall: float = 0.85) -> None:
        if not 0.0 <= min_overall <= 1.0:
            raise ValueError(f"min_overall must be in [0.0, 1.0], got {min_overall}")
        self.min_overall = float(min_overall)

    def evaluate(self, report: Any) -> GateResult:
        """Inspect ``report.overall`` (or ``report["overall"]``)."""
        overall = _attr_or_key(report, "overall", None)
        if overall is None:
            return GateResult(
                gate_name=self.name,
                status=GateStatus.BYPASSED,
                metric_name="overall",
                metric_value=0.0,
                threshold=self.min_overall,
                verdict="Report has no overall score; gate bypassed.",
                severity="info",
                metadata={"reason": "missing_overall"},
            )

        overall_f = float(overall)
        if overall_f < self.min_overall:
            return GateResult(
                gate_name=self.name,
                status=GateStatus.FAILED,
                metric_name="overall",
                metric_value=overall_f,
                threshold=self.min_overall,
                verdict=(f"overall={overall_f:.4f} < threshold={self.min_overall:.4f}"),
                severity="warn",
                metadata={},
            )

        return GateResult(
            gate_name=self.name,
            status=GateStatus.PASSED,
            metric_name="overall",
            metric_value=overall_f,
            threshold=self.min_overall,
            verdict=(f"overall={overall_f:.4f} >= threshold={self.min_overall:.4f}"),
            severity="info",
            metadata={},
        )


@dataclass
class Snapshot:
    """Lightweight historical record consumed by :class:`RegressionGate`.

    Use a fresh dataclass (rather than re-using
    :class:`~nines.iteration.tracker.IterationRecord`) so a caller can
    feed the gate either real iteration history *or* synthetic
    fixtures without needing an entire :class:`SelfEvalReport`.
    """

    version: str
    overall: float


class RegressionGate(QualityGate):
    """Flags a meaningful regression vs. a trailing window of snapshots.

    The gate computes the arithmetic mean of the last ``window_size``
    historical ``overall`` scores and fails when the current report
    drops below that mean by more than ``regression_threshold``.

    With fewer than ``window_size`` snapshots the gate is
    :attr:`GateStatus.BYPASSED` rather than producing a noisy verdict
    on cold-start.

    Parameters
    ----------
    history:
        Trailing snapshots in chronological order (oldest first).
    regression_threshold:
        Acceptable drop versus the trailing mean.  Default ``0.05`` —
        anything more than five percentage points below the mean
        triggers a failure.
    window_size:
        Number of trailing snapshots to average (default ``3``).
    """

    name = "regression"

    def __init__(
        self,
        history: list[Snapshot] | None = None,
        regression_threshold: float = 0.05,
        window_size: int = 3,
    ) -> None:
        if regression_threshold < 0.0:
            raise ValueError(f"regression_threshold must be >= 0, got {regression_threshold}")
        if window_size < 1:
            raise ValueError(f"window_size must be >= 1, got {window_size}")
        self.history: list[Snapshot] = list(history or [])
        self.regression_threshold = float(regression_threshold)
        self.window_size = int(window_size)

    def evaluate(self, report: Any) -> GateResult:
        """Compute regression vs. trailing mean of ``self.history``."""
        overall = _attr_or_key(report, "overall", None)
        if overall is None:
            return GateResult(
                gate_name=self.name,
                status=GateStatus.BYPASSED,
                metric_name="overall_regression_delta",
                metric_value=0.0,
                threshold=self.regression_threshold,
                verdict="Report has no overall score; gate bypassed.",
                severity="info",
                metadata={"reason": "missing_overall"},
            )

        if len(self.history) < self.window_size:
            return GateResult(
                gate_name=self.name,
                status=GateStatus.BYPASSED,
                metric_name="overall_regression_delta",
                metric_value=0.0,
                threshold=self.regression_threshold,
                verdict=(
                    f"Insufficient history "
                    f"({len(self.history)} of {self.window_size}); gate bypassed."
                ),
                severity="info",
                metadata={"history_size": len(self.history)},
            )

        recent = self.history[-self.window_size :]
        mean_recent = statistics.fmean(snap.overall for snap in recent)
        delta = mean_recent - float(overall)

        if delta > self.regression_threshold:
            return GateResult(
                gate_name=self.name,
                status=GateStatus.FAILED,
                metric_name="overall_regression_delta",
                metric_value=delta,
                threshold=self.regression_threshold,
                verdict=(
                    f"overall={float(overall):.4f} dropped by {delta:.4f} "
                    f"vs trailing mean {mean_recent:.4f} "
                    f"(threshold={self.regression_threshold:.4f})"
                ),
                severity="warn",
                metadata={
                    "history_mean": mean_recent,
                    "history_size": len(self.history),
                },
            )

        return GateResult(
            gate_name=self.name,
            status=GateStatus.PASSED,
            metric_name="overall_regression_delta",
            metric_value=delta,
            threshold=self.regression_threshold,
            verdict=(
                f"overall={float(overall):.4f} within tolerance vs trailing "
                f"mean {mean_recent:.4f} (delta={delta:.4f} <= "
                f"{self.regression_threshold:.4f})"
            ),
            severity="info",
            metadata={
                "history_mean": mean_recent,
                "history_size": len(self.history),
            },
        )


class GateRunner:
    """Runs a list of gates against a report and aggregates their verdicts.

    Parameters
    ----------
    gates:
        Concrete :class:`QualityGate` instances to evaluate.
    advisory_mode:
        When ``True`` (default), :attr:`GateStatus.FAILED` verdicts
        carry severity ``"warn"`` so :meth:`should_abort` returns
        ``False``.  When ``False`` (strict), failed gates are promoted
        to ``"block"`` severity and :meth:`should_abort` returns
        ``True`` if any blocked.
    """

    def __init__(
        self,
        gates: list[QualityGate],
        advisory_mode: bool = True,
    ) -> None:
        self.gates: list[QualityGate] = list(gates)
        self.advisory_mode = bool(advisory_mode)

    def evaluate_all(self, report: Any) -> list[GateResult]:
        """Run every gate and apply the advisory/strict severity policy."""
        results: list[GateResult] = []
        for gate in self.gates:
            try:
                result = gate.evaluate(report)
            except Exception as exc:
                # Per workspace rule "no silent failures": surface as an
                # ESCALATED gate result rather than swallowing.
                logger.error(
                    "Gate '%s' raised %s while evaluating; treating as ESCALATED.",
                    getattr(gate, "name", gate.__class__.__name__),
                    exc,
                )
                result = GateResult(
                    gate_name=getattr(gate, "name", gate.__class__.__name__),
                    status=GateStatus.ESCALATED,
                    metric_name="evaluator_error",
                    metric_value=0.0,
                    threshold=0.0,
                    verdict=f"Gate raised {type(exc).__name__}: {exc}",
                    severity="warn",
                    metadata={"error": str(exc), "error_type": type(exc).__name__},
                )

            # Apply advisory/strict promotion policy.  PASSED and
            # BYPASSED stay informational regardless of mode.
            if result.status in (GateStatus.FAILED, GateStatus.ESCALATED):
                result.severity = "block" if not self.advisory_mode else "warn"
            elif result.status in (GateStatus.PASSED, GateStatus.BYPASSED):
                result.severity = "info"

            results.append(result)
        return results

    def summary(self, results: list[GateResult]) -> dict[str, Any]:
        """Aggregate verdicts into a JSON-friendly summary dict."""
        passed = sum(1 for r in results if r.status == GateStatus.PASSED)
        failed = sum(1 for r in results if r.status == GateStatus.FAILED)
        escalated = sum(1 for r in results if r.status == GateStatus.ESCALATED)
        bypassed = sum(1 for r in results if r.status == GateStatus.BYPASSED)
        warned = sum(1 for r in results if r.severity == "warn")
        blocked = sum(1 for r in results if r.severity == "block")
        return {
            "passed": passed,
            "failed": failed,
            "escalated": escalated,
            "bypassed": bypassed,
            "warned": warned,
            "blocked": blocked,
            "total": len(results),
            "advisory_mode": self.advisory_mode,
            "results": [r.to_dict() for r in results],
        }

    def should_abort(self, results: list[GateResult]) -> bool:
        """Return ``True`` only in strict mode when at least one gate blocks."""
        if self.advisory_mode:
            return False
        return any(r.severity == "block" for r in results)


class GateRegistry:
    """Central registry where users can add custom gates by name.

    The registry holds *factories* (zero-arg callables returning a
    :class:`QualityGate`) so each ``create()`` produces a fresh
    instance — important because gates such as :class:`RegressionGate`
    keep mutable history.

    The :meth:`default_runner` factory returns a :class:`GateRunner`
    seeded with the four built-in gates.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], QualityGate]] = {}

    def register(self, name: str, factory: Callable[[], QualityGate]) -> None:
        """Register a zero-arg factory under ``name``.

        Re-registering an existing name overwrites it (callers can
        rely on this for monkey-patching in tests).
        """
        if not name:
            raise ValueError("Gate name must be a non-empty string")
        self._factories[name] = factory

    def create(self, name: str) -> QualityGate:
        """Instantiate a registered gate by name.

        Raises
        ------
        KeyError
            If ``name`` is not registered.
        """
        if name not in self._factories:
            raise KeyError(f"Gate '{name}' is not registered")
        return self._factories[name]()

    def names(self) -> list[str]:
        """Return the list of registered gate names."""
        return list(self._factories.keys())

    @staticmethod
    def default_runner(advisory_mode: bool = True) -> GateRunner:
        """Build a :class:`GateRunner` seeded with the 4 built-in gates."""
        gates: list[QualityGate] = [
            GraphVerificationGate(),
            EconomicsScoreGate(),
            SelfEvalCoverageGate(),
            RegressionGate(),
        ]
        return GateRunner(gates=gates, advisory_mode=advisory_mode)


def default_gate_runner(advisory_mode: bool = True) -> GateRunner:
    """Module-level convenience for :meth:`GateRegistry.default_runner`."""
    return GateRegistry.default_runner(advisory_mode=advisory_mode)


__all__ = [
    "EconomicsScoreGate",
    "GateRegistry",
    "GateResult",
    "GateRunner",
    "GateStatus",
    "GraphVerificationGate",
    "QualityGate",
    "RegressionGate",
    "SelfEvalCoverageGate",
    "Severity",
    "Snapshot",
    "default_gate_runner",
]
