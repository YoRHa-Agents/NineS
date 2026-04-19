"""Self-evaluation runner and dimension evaluator protocol.

``SelfEvalRunner`` orchestrates evaluation across multiple dimensions
(code coverage, test count, module count, etc.) and produces a
``SelfEvalReport`` summarizing scores for each dimension.

Covers: FR-601, FR-602.
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, cast, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable

    from nines.eval.metrics_registry import MetricRegistry
    from nines.iteration.context import EvaluationContext

from nines.core.budget import (
    EvaluatorBudgetExceeded,
    TimeBudget,
    evaluator_budget,
)
from nines.core.errors import ConfigError


def _budgeted_subprocess_timeout(
    default_seconds: float,
    budget: TimeBudget | None,
    *,
    margin: float = 0.9,
) -> float:
    """Return the subprocess ``timeout=`` value to use under *budget*.

    Computes ``min(default_seconds, budget.hard_seconds * margin)`` so
    the subprocess always returns control to its caller before the
    daemon-thread budget kills the worker.  The 0.9 margin gives the
    evaluator ~10% of the wall budget to clean up after a
    ``subprocess.TimeoutExpired``.

    When ``budget`` is ``None`` (back-compat path used by direct
    instantiation in tests), returns ``default_seconds`` unchanged.

    Release follow-up N2.
    """
    if budget is None:
        return float(default_seconds)
    capped = budget.hard_seconds * margin
    return float(min(default_seconds, capped))


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
        """Return the score normalized to [0, 1]."""
        if self.max_value == 0:
            return 0.0
        return self.value / self.max_value

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "max_value": self.max_value,
            "normalized": self.normalized,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DimensionScore:
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            max_value=data.get("max_value", 1.0),
            metadata=data.get("metadata", {}),
        )


@runtime_checkable
class DimensionEvaluator(Protocol):
    """Protocol for evaluating a single dimension.

    Implementations may *optionally* accept a kw-only ``budget`` argument
    to opt in to the C04 wall-clock budget, and/or a kw-only ``ctx``
    argument (C01 Phase 1) to receive an
    :class:`~nines.iteration.context.EvaluationContext`. ``SelfEvalRunner``
    introspects via :func:`inspect.signature` and only passes the kwargs
    the implementation declares.

    Backward compatibility
    ----------------------
    The Protocol's ``evaluate`` declaration keeps the original
    no-argument shape so legacy evaluators that pre-date C04/C01 still
    structurally satisfy the runtime_checkable Protocol.  The
    :class:`LegacyEvaluatorAdapter` wrapper takes care of stripping
    unwanted kwargs at call time.

    Opt-in marker attribute
    -----------------------
    Subclasses that need ctx-aware project binding may set the
    ``requires_context`` *class attribute* to ``True``::

        class MyEvaluator:
            requires_context: ClassVar[bool] = True

            def evaluate(self, *, ctx): ...

    The runner inspects the attribute at run time via ``getattr(ev,
    "requires_context", False)``.  We deliberately do **not** declare
    the attribute on the Protocol itself because runtime_checkable
    Protocols verify the existence of every declared member, and
    forcing legacy evaluators to define the marker would be a breaking
    change.
    """

    def evaluate(self) -> DimensionScore:
        """Run evaluation and return a score for this dimension."""
        ...


class _BudgetedEvaluator(Protocol):
    """Internal Protocol describing budget-aware evaluators.

    Implementations whose ``evaluate`` accepts a kw-only ``budget`` argument
    structurally match this Protocol. Used by
    :meth:`SelfEvalRunner._bind_evaluator_with_budget` to type-check the
    ``evaluator.evaluate(budget=...)`` call after a runtime
    ``inspect.signature`` gate.
    """

    def evaluate(self, *, budget: TimeBudget | None = None) -> DimensionScore: ...


class LegacyEvaluatorAdapter:
    """Wrap a pre-C01 evaluator so it tolerates the new ``ctx`` kwarg.

    The adapter discards any ``ctx`` keyword argument passed by the
    runner and forwards everything else (notably ``budget``) to the
    wrapped evaluator. It exists so existing evaluators that don't yet
    accept ``ctx`` keep working unchanged for one minor version while
    the evaluator-set is migrated.

    The adapter never sets ``requires_context = True`` — by definition,
    an adapted legacy evaluator does not need a context (it ignores
    one).
    """

    requires_context: ClassVar[bool] = False

    def __init__(self, wrapped: DimensionEvaluator) -> None:
        """Initialise the adapter.

        Parameters
        ----------
        wrapped:
            The legacy evaluator instance whose ``evaluate`` does not
            accept a ``ctx`` parameter.
        """
        self._wrapped = wrapped
        self._accepts_budget = self._detect_budget_kwarg(wrapped)

    @staticmethod
    def _detect_budget_kwarg(evaluator: DimensionEvaluator) -> bool:
        """Return True iff ``evaluator.evaluate`` accepts a ``budget`` kwarg."""
        try:
            sig = inspect.signature(evaluator.evaluate)
        except (TypeError, ValueError):
            return False
        params = sig.parameters
        if "budget" in params:
            return True
        # ``**kwargs`` swallows any kwarg name, including budget.
        return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())

    @property
    def wrapped(self) -> DimensionEvaluator:
        """Expose the wrapped evaluator (useful for tests/introspection)."""
        return self._wrapped

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
        budget: TimeBudget | None = None,
    ) -> DimensionScore:
        """Drop ``ctx``, forward ``budget`` only when the wrapped object wants it.

        Parameters
        ----------
        ctx:
            Ignored. Present so the adapter satisfies the modern
            ``DimensionEvaluator`` Protocol surface.
        budget:
            Forwarded to the wrapped evaluator only when its signature
            declares it (otherwise the wrapped object's no-arg
            ``evaluate`` is invoked unchanged).
        """
        # ``ctx`` is intentionally discarded — that's the whole point of
        # the adapter. Logging happens once at registration time, not
        # per-evaluation, to avoid log spam.
        if self._accepts_budget:
            return self._wrapped.evaluate(budget=budget)  # type: ignore[call-arg]
        return self._wrapped.evaluate()


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
    timeouts:
        Names of dimensions whose evaluators exceeded the configured
        hard wall-clock budget (C04).  Empty when all evaluators
        completed within budget.
    """

    scores: list[DimensionScore] = field(default_factory=list)
    overall: float = 0.0
    version: str = ""
    timestamp: str = ""
    duration: float = 0.0
    timeouts: list[str] = field(default_factory=list)
    #: C01 Phase 1: 8-char fingerprint of the project binding
    #: (project_root + src_dir).  ``None`` when the report was generated
    #: without an :class:`EvaluationContext` (legacy / back-compat path).
    context_fingerprint: str | None = None
    #: C08: weighted-mean aggregate using the :class:`MetricRegistry`
    #: passed to :class:`SelfEvalRunner`.  ``0.0`` when no registry was
    #: supplied (legacy / back-compat path).  Preserved alongside
    #: :attr:`overall` for one minor deprecation window per design.
    weighted_overall: float = 0.0
    #: C08: per-group weighted means, e.g.
    #: ``{"capability": 0.91, "hygiene": 0.86}``.  Empty when no
    #: registry was supplied.
    group_means: dict[str, float] = field(default_factory=dict)
    #: C08: ``{metric_name: weight}`` snapshot from the active
    #: :class:`MetricRegistry` so reports remain reproducible even
    #: after the TOML changes on disk.  Empty when no registry was
    #: supplied.
    metric_weights: dict[str, float] = field(default_factory=dict)

    def get_score(self, dimension: str) -> DimensionScore | None:
        """Return score."""
        for s in self.scores:
            if s.name == dimension:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scores": [s.to_dict() for s in self.scores],
            "overall": self.overall,
            "version": self.version,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "timeouts": list(self.timeouts),
            "context_fingerprint": self.context_fingerprint,
            "weighted_overall": self.weighted_overall,
            "group_means": dict(self.group_means),
            "metric_weights": dict(self.metric_weights),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelfEvalReport:
        """Deserialize from dictionary."""
        return cls(
            scores=[DimensionScore.from_dict(s) for s in data.get("scores", [])],
            overall=data.get("overall", 0.0),
            version=data.get("version", ""),
            timestamp=data.get("timestamp", ""),
            duration=data.get("duration", 0.0),
            timeouts=list(data.get("timeouts", [])),
            context_fingerprint=data.get("context_fingerprint"),
            weighted_overall=float(data.get("weighted_overall", 0.0)),
            group_means=dict(data.get("group_means", {})),
            metric_weights=dict(data.get("metric_weights", {})),
        )


class SelfEvalRunner:
    """Orchestrates evaluation across multiple registered dimensions.

    Usage::

        runner = SelfEvalRunner()
        runner.register_dimension("test_count", TestCountEvaluator())
        runner.register_dimension("module_count", ModuleCountEvaluator())
        report = runner.run_all()
    """

    def __init__(
        self,
        default_budget: TimeBudget | None = None,
        *,
        strict_ctx: bool = False,
        registry: MetricRegistry | None = None,
    ) -> None:
        """Initialize self eval runner.

        Parameters
        ----------
        default_budget:
            Per-evaluator wall-clock budget applied to every dimension
            unless overridden by ``register_dimension(..., budget=...)``.
            Defaults to ``TimeBudget(soft_seconds=20, hard_seconds=60)``
            per the C04 design.
        strict_ctx:
            C01 Phase 1.  When ``True`` and any registered evaluator
            declares ``requires_context = True`` while :meth:`run_all`
            is called with ``ctx=None``, the runner raises
            :class:`~nines.core.errors.ConfigError`.  When ``False``
            (the back-compat default used by ``nines iterate``), the
            runner only logs a warning and lets each evaluator fall
            back to its constructor-time default.  The new
            ``nines self-eval`` CLI sets ``strict_ctx=True`` so
            foreign-repo runs can never silently re-evaluate NineS
            itself (closes baseline §4.8).
        registry:
            C08.  Optional :class:`~nines.eval.metrics_registry.MetricRegistry`
            used by :meth:`run_all` to compute the new
            :attr:`SelfEvalReport.weighted_overall` /
            :attr:`SelfEvalReport.group_means` /
            :attr:`SelfEvalReport.metric_weights` fields.  When
            ``None`` the runner loads
            :func:`~nines.eval.metrics_registry.load_default_registry`
            (the bundled ``data/self_eval_metrics.toml``) so the
            weighted aggregate is always available; pass an explicit
            registry to swap weights/thresholds without editing the
            on-disk TOML.  When the registry fails ``validate()``
            the runner logs the errors and skips weighted
            aggregation, keeping :attr:`SelfEvalReport.overall`
            (legacy unweighted mean) intact.
        """
        self._evaluators: dict[str, DimensionEvaluator] = {}
        self._budgets: dict[str, TimeBudget] = {}
        self._default_budget = default_budget or TimeBudget(
            soft_seconds=20.0,
            hard_seconds=60.0,
        )
        self._strict_ctx = bool(strict_ctx)
        # C08: store the registry as-given; load_default_registry()
        # is invoked lazily inside run_all() when registry is None
        # so legacy callers (and tests that monkeypatch the default
        # registry path) never pay the TOML-parse cost up front.
        self._registry = registry

    def register_dimension(
        self,
        name: str,
        evaluator: DimensionEvaluator,
        *,
        budget: TimeBudget | None = None,
    ) -> None:
        """Register an evaluator for a named dimension.

        Parameters
        ----------
        name:
            Unique dimension identifier.
        evaluator:
            Object implementing the ``DimensionEvaluator`` protocol.
            If the evaluator's ``evaluate`` method does **not** accept
            a ``ctx`` keyword argument (legacy / pre-C01 evaluators),
            it is automatically wrapped in
            :class:`LegacyEvaluatorAdapter` so the runner can still
            invoke it uniformly.  An INFO-level log is emitted to aid
            migration.
        budget:
            Optional per-dimension wall-clock budget overriding the
            runner-wide default.
        """
        if not self._evaluator_accepts_ctx(evaluator):
            logger.info(
                "Wrapping %s in LegacyEvaluatorAdapter (no ctx parameter detected)",
                name,
            )
            evaluator = LegacyEvaluatorAdapter(evaluator)
        self._evaluators[name] = evaluator
        if budget is not None:
            self._budgets[name] = budget
        logger.debug("Registered evaluator for dimension '%s'", name)

    @staticmethod
    def _evaluator_accepts_ctx(evaluator: DimensionEvaluator) -> bool:
        """Return ``True`` iff ``evaluator.evaluate`` declares a ``ctx`` kwarg.

        Detection rule:
        * explicit ``ctx`` parameter (any kind)         → ``True``
        * ``**kwargs`` catch-all that swallows ``ctx``  → ``True``
        * neither                                       → ``False``

        The adapter wraps everything that returns ``False``.  A C-level
        callable whose signature can't be introspected also counts as
        ``False`` (we conservatively wrap rather than risk passing an
        unknown kwarg into a built-in).
        """
        try:
            sig = inspect.signature(evaluator.evaluate)
        except (TypeError, ValueError):
            return False
        params = sig.parameters
        if "ctx" in params:
            return True
        return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())

    @staticmethod
    def _make_invocation(
        evaluator: DimensionEvaluator,
        budget: TimeBudget,
        ctx: EvaluationContext | None = None,
    ) -> Callable[[], DimensionScore]:
        """Bind ``budget`` and ``ctx`` to ``evaluator.evaluate`` per signature.

        Returns a zero-arg callable that invokes the evaluator with the
        kwargs its signature declares.  Backward-compat: third-party
        evaluators that don't accept ``budget`` and/or ``ctx`` keep
        working (Approach A from the C04 follow-up; extended for C01
        Phase 1).

        Detection rules:

        * ``budget`` kw → forward when present in the signature.
        * ``ctx``    kw → forward when present in the signature.
        * ``**kwargs`` swallows everything → forward both.
        """
        accepts_budget = False
        accepts_ctx = False
        try:
            sig = inspect.signature(evaluator.evaluate)
            params = sig.parameters
            has_var_keyword = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
            accepts_budget = "budget" in params or has_var_keyword
            accepts_ctx = "ctx" in params or has_var_keyword
        except (TypeError, ValueError):
            # ``signature`` can fail on C-level callables — fall back to
            # the no-kwarg call shape.  We never silently swallow:
            # downstream evaluator errors still surface through the
            # ``except Exception`` branch in run_all.
            logger.debug(
                "inspect.signature failed for evaluator %r; calling without budget/ctx",
                evaluator,
            )

        if accepts_budget and accepts_ctx:
            budgeted = cast("_BudgetedEvaluator", evaluator)
            return lambda: budgeted.evaluate(budget=budget, ctx=ctx)  # type: ignore[call-arg]
        if accepts_budget:
            budgeted = cast("_BudgetedEvaluator", evaluator)
            return lambda: budgeted.evaluate(budget=budget)
        if accepts_ctx:
            return lambda: evaluator.evaluate(ctx=ctx)  # type: ignore[call-arg]
        return evaluator.evaluate

    def run_all(
        self,
        version: str = "",
        *,
        ctx: EvaluationContext | None = None,
    ) -> SelfEvalReport:
        """Run all registered evaluators and produce a report.

        Parameters
        ----------
        version:
            Optional version tag for the report.
        ctx:
            Optional :class:`EvaluationContext`.  When supplied:

            * Threaded into every evaluator that accepts a ``ctx`` kwarg.
            * Its :meth:`EvaluationContext.fingerprint` is written to
              :attr:`SelfEvalReport.context_fingerprint`.

            When ``None`` *and* the runner was constructed with
            ``strict_ctx=True``, evaluators that declare
            ``requires_context = True`` raise
            :class:`~nines.core.errors.ConfigError` (fail fast).  When
            ``strict_ctx=False`` (the back-compat default) the runner
            only logs a warning and the evaluator's own legacy fallback
            takes over.

        Returns
        -------
        SelfEvalReport
            Aggregate scores from all dimensions.

        Raises
        ------
        ConfigError
            If ``strict_ctx=True`` and any registered evaluator declares
            ``requires_context = True`` while ``ctx is None``.
        """
        from datetime import datetime

        if ctx is None:
            offenders = [
                n for n, ev in self._evaluators.items() if getattr(ev, "requires_context", False)
            ]
            if offenders:
                if self._strict_ctx:
                    msg = (
                        "EvaluationContext is required for dim(s) "
                        f"{sorted(offenders)} but run_all() was called "
                        "with ctx=None"
                    )
                    raise ConfigError(
                        msg,
                        details={"dimensions": sorted(offenders)},
                    )
                logger.warning(
                    "run_all() called with ctx=None but %d ctx-aware dim(s) "
                    "registered (%s); they will fall back to their "
                    "constructor-time src_dir defaults",
                    len(offenders),
                    sorted(offenders),
                )

        start = time.monotonic()
        scores: list[DimensionScore] = []
        timeouts: list[str] = []

        for name, evaluator in self._evaluators.items():
            logger.info("Evaluating dimension '%s'", name)
            budget = self._budgets.get(name, self._default_budget)
            # N2: thread the budget into evaluators that accept it so
            # internal subprocess.run calls can derive their own
            # ``timeout=`` from the wall-clock budget.  C01 Phase 1
            # extends the same detection to ``ctx=`` so project-aware
            # evaluators get the right project binding.
            invoke = self._make_invocation(evaluator, budget, ctx)
            try:
                with evaluator_budget(name, budget) as run:
                    score = run(invoke)
                scores.append(score)
                logger.info(
                    "Dimension '%s': %.3f / %.3f (%.1f%%)",
                    name,
                    score.value,
                    score.max_value,
                    score.normalized * 100,
                )
            except EvaluatorBudgetExceeded as exc:
                # C04: append a placeholder score with status='timeout'
                # so the report records exactly which dim breached.
                logger.warning(
                    "Evaluator '%s' timed out after %.1fs: %s",
                    name,
                    exc.elapsed_s,
                    exc,
                )
                scores.append(
                    DimensionScore(
                        name=name,
                        value=0.0,
                        max_value=1.0,
                        metadata={
                            "status": "timeout",
                            "hard_seconds": exc.hard_seconds,
                            "elapsed_s": exc.elapsed_s,
                        },
                    )
                )
                timeouts.append(name)
            except Exception as exc:
                logger.error("Evaluator for '%s' failed: %s", name, exc, exc_info=True)
                scores.append(DimensionScore(name=name, value=0.0, max_value=1.0))

        overall = 0.0
        if scores:
            overall = sum(s.normalized for s in scores) / len(scores)

        # C08 — weighted aggregation via the MetricRegistry.
        # When the registry fails validate() we log loudly and
        # leave the new fields empty so the legacy ``overall`` stays
        # the source of truth (Risk-Med mitigation per design).
        weighted_overall = 0.0
        group_means: dict[str, float] = {}
        metric_weights: dict[str, float] = {}
        # C08 — lazy import to avoid the eager nines.eval.__init__
        # cycle (mock_executor -> iteration.self_eval).
        from nines.eval.metrics_registry import (
            GROUPS_META_GROUP,
            load_default_registry,
        )

        registry = self._registry
        if registry is None:
            try:
                registry = load_default_registry()
            except (FileNotFoundError, ValueError) as exc:
                logger.warning(
                    "C08: default MetricRegistry unavailable (%s); "
                    "weighted_overall stays 0.0",
                    exc,
                )
                registry = None
        if registry is not None:
            errors = registry.validate()
            if errors:
                logger.warning(
                    "C08: MetricRegistry.validate() returned %d "
                    "error(s); weighted aggregation skipped: %s",
                    len(errors),
                    errors,
                )
            else:
                metric_weights = registry.weights_dict()
                # Build the per-metric normalised score map by
                # asking the registry to apply its threshold/normalizer
                # per dim.  When a metric has no registry-side
                # threshold, ``normalized()`` falls back to
                # ``value / max_value`` so existing evaluator outputs
                # in [0, 1] flow through unchanged.
                normalised: dict[str, float] = {}
                for s in scores:
                    if registry.get(s.name) is None:
                        continue
                    try:
                        normalised[s.name] = registry.normalized(
                            s.name,
                            s.value,
                            max_value=s.max_value,
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning(
                            "C08: registry.normalized(%r) failed: %s",
                            s.name,
                            exc,
                        )
                # Per-group weighted means (capability / hygiene / ...).
                # Only groups that have at least one matching score
                # contribute to the outer aggregate — empty groups are
                # excluded from group_means entirely so partial-
                # coverage runs (e.g. --capability-only, or unit
                # tests with a 3-dim subset) don't spuriously drag
                # weighted_overall down.
                for group in registry.groups():
                    if group == GROUPS_META_GROUP:
                        continue
                    has_score = any(
                        d.group == group and d.name in normalised
                        for d in registry.metrics().values()
                    )
                    if not has_score:
                        continue
                    group_means[group] = registry.weighted_mean(
                        group, normalised
                    )
                # Outer weighted overall: combine the per-group means
                # using the reserved ``_groups`` meta-group weights,
                # restricted to the groups we actually evaluated.
                if group_means:
                    weighted_overall = registry.weighted_mean(
                        GROUPS_META_GROUP, group_means
                    )
                    # Fall back to a simple mean when the meta-group
                    # is missing or all its weights resolved to zero.
                    if weighted_overall == 0.0 and any(
                        v != 0.0 for v in group_means.values()
                    ):
                        weighted_overall = sum(group_means.values()) / len(
                            group_means
                        )

        duration = time.monotonic() - start
        return SelfEvalReport(
            scores=scores,
            overall=overall,
            version=version,
            timestamp=datetime.now(UTC).isoformat(),
            duration=duration,
            timeouts=timeouts,
            context_fingerprint=ctx.fingerprint() if ctx is not None else None,
            weighted_overall=weighted_overall,
            group_means=group_means,
            metric_weights=metric_weights,
        )


# ---------------------------------------------------------------------------
# Built-in evaluators for simple dimensions
# ---------------------------------------------------------------------------


class CodeCoverageEvaluator:
    """Evaluator that reports a configured code coverage percentage."""

    def __init__(self, coverage_pct: float = 0.0) -> None:
        """Initialize code coverage evaluator."""
        self._coverage = coverage_pct

    def evaluate(self) -> DimensionScore:
        """Evaluate and return a code coverage score."""
        return DimensionScore(
            name="code_coverage",
            value=self._coverage,
            max_value=100.0,
            metadata={"unit": "percent"},
        )


class UnitTestCountEvaluator:
    """Evaluator that reports a count of tests."""

    def __init__(self, count: int = 0) -> None:
        """Initialize unit test count evaluator."""
        self._count = count

    def evaluate(self) -> DimensionScore:
        """Evaluate and return a test count score."""
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
        """Initialize module count evaluator."""
        self._count = count

    def evaluate(self) -> DimensionScore:
        """Evaluate and return a module count score."""
        return DimensionScore(
            name="module_count",
            value=float(self._count),
            max_value=float(max(self._count, 1)),
            metadata={"unit": "modules"},
        )


# ---------------------------------------------------------------------------
# Live evaluators — auto-discover metrics from the project
# ---------------------------------------------------------------------------


class LiveCodeCoverageEvaluator:
    """Evaluator that runs pytest --cov and parses real coverage.

    Supports three coverage sources (checked in order):
    1. Pre-existing coverage file (coverage.xml or coverage.json)
    2. pytest ``--cov`` subprocess execution

    C01 Phase 3: project-aware. Uses ``ctx.project_root`` as the
    pytest cwd so coverage is measured against the *target* project
    rather than the constructor-time default (closes baseline §4.8 —
    today every foreign-repo run silently re-measures NineS's own
    coverage).
    """

    requires_context: ClassVar[bool] = True

    def __init__(
        self,
        project_root: str | Path = ".",
        cov_package: str = "nines",
        coverage_file: str | Path | None = None,
    ) -> None:
        """Initialize live code coverage evaluator.

        Parameters
        ----------
        project_root:
            Working directory for running pytest.
        cov_package:
            Package name passed to ``--cov=<package>``.
        coverage_file:
            Optional path to a pre-existing coverage.xml (Cobertura) or
            coverage.json file.  When provided and the file exists, the
            evaluator parses coverage from it instead of running pytest.
        """
        self._project_root = Path(project_root)
        self._cov_package = cov_package
        self._coverage_file = Path(coverage_file) if coverage_file is not None else None

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
        budget: TimeBudget | None = None,
    ) -> DimensionScore:
        """Evaluate and return live code coverage.

        Parameters
        ----------
        ctx:
            Project context. When supplied, the cwd for pytest is
            ``ctx.project_root`` (legacy fallback: constructor arg).
            ``cov_package`` and ``coverage_file`` remain configured by
            the constructor since they're not part of the project-path
            binding.
        budget:
            Optional :class:`TimeBudget` from the runner.  When set, the
            inner ``pytest --cov`` subprocess uses
            ``min(default_timeout, budget.hard_seconds * 0.9)`` so the
            child returns control before the daemon-thread budget fires
            (release follow-up N2).
        """
        project_root = ctx.project_root if ctx is not None else self._project_root
        coverage_pct = self._try_coverage_file()
        source = "file"

        if coverage_pct is None:
            source = "pytest"
            coverage_pct = self._run_pytest_cov(project_root, budget=budget)

        # C12: attempt to surface line / branch sub-skills when a
        # coverage file is wired up.  When only the aggregate line
        # number is available (the pytest-stdout path), we emit a
        # single line_coverage sub-skill so the panel still has
        # something to display.
        breakdown_data: dict[str, float] | None = None
        if self._coverage_file is not None and self._coverage_file.exists():
            suffix = self._coverage_file.suffix.lower()
            if suffix == ".xml":
                breakdown_data = self._parse_coverage_breakdown_xml(self._coverage_file)
            elif suffix == ".json":
                breakdown_data = self._parse_coverage_breakdown_json(self._coverage_file)

        subskills_block: list[dict[str, Any]] = []
        if breakdown_data:
            for kind in ("line", "branch", "function"):
                if kind in breakdown_data:
                    subskills_block.append(
                        {
                            "name": f"{kind}_coverage",
                            "value": float(breakdown_data[kind]),
                            "max_value": 100.0,
                            "weight": 1.0,
                            "metadata": {"unit": "percent", "source": source},
                        }
                    )
        if not subskills_block:
            subskills_block = [
                {
                    "name": "line_coverage",
                    "value": float(coverage_pct),
                    "max_value": 100.0,
                    "weight": 1.0,
                    "metadata": {"unit": "percent", "source": source},
                }
            ]

        return DimensionScore(
            name="code_coverage",
            value=coverage_pct,
            max_value=100.0,
            metadata={
                "unit": "percent",
                "source": source,
                "project_root": str(project_root),
                "cov_package": self._cov_package,
                # C12 sub-skill block
                "subskills": subskills_block,
                "rollup_method": "weighted_mean",
            },
        )

    # -- private helpers -----------------------------------------------------

    def _try_coverage_file(self) -> float | None:
        """Attempt to read coverage from a pre-existing file."""
        if self._coverage_file is None or not self._coverage_file.exists():
            return None

        suffix = self._coverage_file.suffix.lower()
        try:
            if suffix == ".xml":
                return self._parse_coverage_xml(self._coverage_file)
            if suffix == ".json":
                return self._parse_coverage_json(self._coverage_file)
            logger.warning(
                "Unsupported coverage file format '%s'; falling back to pytest",
                suffix,
            )
        except Exception as exc:
            logger.error(
                "Failed to parse coverage file %s: %s",
                self._coverage_file,
                exc,
            )
        return None

    def _run_pytest_cov(
        self,
        project_root: Path,
        *,
        budget: TimeBudget | None = None,
    ) -> float:
        """Run pytest --cov and return the coverage percentage.

        N2: ``timeout`` defaults to 300s but is shrunk to
        ``budget.hard_seconds * 0.9`` whenever the runner passes a
        TimeBudget through, so the child subprocess returns before the
        daemon-thread guard kills it.
        """
        timeout_s = _budgeted_subprocess_timeout(300.0, budget)
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    f"--cov={self._cov_package}",
                    "--cov-report=term-missing",
                    "-q",
                ],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(project_root),
            )
            return self._parse_coverage(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error(
                "pytest --cov timed out after %.1fs (budget-derived)",
                timeout_s,
            )
            return 0.0
        except Exception as exc:
            logger.error("Failed to run pytest --cov: %s", exc)
            return 0.0

    @staticmethod
    def _parse_coverage(stdout: str) -> float:
        """Extract total coverage percentage from pytest-cov TOTAL line."""
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("TOTAL"):
                parts = stripped.split()
                for part in reversed(parts):
                    cleaned = part.rstrip("%")
                    try:
                        return float(cleaned)
                    except ValueError:
                        continue
        logger.warning("Could not parse coverage from pytest output")
        return 0.0

    @staticmethod
    def _parse_coverage_xml(path: Path) -> float:
        """Parse Cobertura coverage.xml and return coverage percentage."""
        tree = ET.parse(path)  # noqa: S314
        root = tree.getroot()
        line_rate = root.get("line-rate")
        if line_rate is None:
            msg = "coverage.xml missing 'line-rate' attribute on root element"
            raise ValueError(msg)
        return float(line_rate) * 100.0

    @staticmethod
    def _parse_coverage_breakdown_xml(path: Path) -> dict[str, float] | None:
        """C12: extract ``line``/``branch`` rates from coverage.xml when present.

        Returns ``None`` when the file can't be parsed; otherwise a
        dict like ``{"line": 95.2, "branch": 88.0}`` (each in
        percent).  Branch coverage is only included when the file
        actually carries a ``branch-rate`` attribute.
        """
        try:
            tree = ET.parse(path)  # noqa: S314
            root = tree.getroot()
            out: dict[str, float] = {}
            line_rate = root.get("line-rate")
            if line_rate is not None:
                out["line"] = float(line_rate) * 100.0
            branch_rate = root.get("branch-rate")
            if branch_rate is not None:
                out["branch"] = float(branch_rate) * 100.0
            return out or None
        except Exception:  # noqa: BLE001 — best-effort parse for sub-skills
            return None

    @staticmethod
    def _parse_coverage_json(path: Path) -> float:
        """Parse coverage.json and return coverage percentage."""
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            return float(data["totals"]["percent_covered"])
        except (KeyError, TypeError) as exc:
            msg = "coverage.json missing 'totals.percent_covered'"
            raise ValueError(msg) from exc

    @staticmethod
    def _parse_coverage_breakdown_json(path: Path) -> dict[str, float] | None:
        """C12: extract per-aspect rates from coverage.json when present.

        coverage.py's JSON ``totals`` block exposes
        ``percent_covered``, ``percent_covered_display``,
        ``num_branches``/``covered_branches``, etc.  Returns whatever
        of those map onto our line / branch / function buckets.
        """
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            totals = data.get("totals") or {}
            out: dict[str, float] = {}
            if "percent_covered" in totals:
                out["line"] = float(totals["percent_covered"])
            if (
                totals.get("num_branches", 0) > 0
                and "covered_branches" in totals
            ):
                out["branch"] = (
                    float(totals["covered_branches"])
                    / float(totals["num_branches"])
                    * 100.0
                )
            return out or None
        except Exception:  # noqa: BLE001 — best-effort parse for sub-skills
            return None


class LiveTestCountEvaluator:
    """Evaluator that counts test functions.

    Prefers ``pytest --collect-only -q`` for an accurate count (handles
    parameterized tests, fixture-generated tests, class-based methods,
    etc.).  Falls back to an AST walk when pytest collection is
    unavailable or fails.

    C01 Phase 3: project-aware. When the runner supplies a context,
    ``ctx.test_dir`` (when set) drives both the pytest argument and
    the AST-walk fallback; ``ctx.project_root`` becomes the pytest
    cwd. Closes baseline §4.8 silent-fallback for foreign-repo runs.
    """

    requires_context: ClassVar[bool] = True

    def __init__(
        self,
        test_dir: str | Path = "tests",
        project_root: str | Path = ".",
    ) -> None:
        """Initialize live test count evaluator.

        Parameters
        ----------
        test_dir:
            Directory to scan when using the AST-walk fallback.
        project_root:
            Working directory for running ``pytest --collect-only``.
        """
        self._test_dir = Path(test_dir)
        self._project_root = Path(project_root)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
        budget: TimeBudget | None = None,
    ) -> DimensionScore:
        """Evaluate and return live test count.

        Parameters
        ----------
        ctx:
            Project context. When supplied with a non-None ``test_dir``,
            that path is used in preference to the constructor default;
            otherwise falls back to constructor ``test_dir``.
            ``ctx.project_root`` (when ctx supplied) drives the pytest
            cwd.
        budget:
            Optional runner-supplied :class:`TimeBudget`.  When set, the
            inner ``pytest --collect-only`` subprocess uses
            ``min(120s, budget.hard_seconds * 0.9)`` (release follow-up
            N2).
        """
        if ctx is not None:
            test_dir = ctx.test_dir if ctx.test_dir is not None else self._test_dir
            project_root = ctx.project_root
        else:
            test_dir = self._test_dir
            project_root = self._project_root

        count, method = self._try_pytest_collect(test_dir, project_root, budget=budget)

        if count is None:
            count, method = self._ast_walk(test_dir), "ast-walk"

        return DimensionScore(
            name="test_count",
            value=float(count),
            max_value=float(max(count, 1)),
            metadata={
                "unit": "tests",
                "method": method,
                "test_dir": str(test_dir),
                "project_root": str(project_root),
            },
        )

    # -- private helpers -----------------------------------------------------

    def _try_pytest_collect(
        self,
        test_dir: Path,
        project_root: Path,
        *,
        budget: TimeBudget | None = None,
    ) -> tuple[int | None, str]:
        """Run ``pytest --collect-only -q`` and count collected items.

        N2: caps the subprocess timeout to
        ``budget.hard_seconds * 0.9`` when the runner forwards a
        TimeBudget; defaults to 120s otherwise.
        """
        timeout_s = _budgeted_subprocess_timeout(120.0, budget)
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    "--collect-only",
                    "-q",
                    str(test_dir),
                ],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(project_root),
            )
            count = self._parse_collect_output(result.stdout)
            if count is not None:
                return count, "pytest-collect"
            logger.warning(
                "pytest --collect-only did not produce a parseable summary; "
                "falling back to AST walk"
            )
        except subprocess.TimeoutExpired:
            logger.error(
                "pytest --collect-only timed out after %.1fs (budget-derived)",
                timeout_s,
            )
        except Exception as exc:
            logger.error("pytest --collect-only failed: %s", exc)
        return None, ""

    @staticmethod
    def _parse_collect_output(stdout: str) -> int | None:
        """Parse the ``N tests collected`` summary line from pytest -q."""
        for line in reversed(stdout.splitlines()):
            match = re.search(r"(\d+)\s+tests?\s+collected", line)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _ast_walk(test_dir: Path) -> int:
        """Count test functions via AST analysis (fallback)."""
        count = 0
        files_scanned = 0
        try:
            for py_file in test_dir.rglob("test_*.py"):
                files_scanned += 1
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError) as exc:
                    logger.warning("Skipping %s: %s", py_file, exc)
                    continue
                for node in ast.walk(tree):
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and node.name.startswith("test_"):
                        count += 1
        except Exception as exc:
            logger.error("Failed to scan test directory %s: %s", test_dir, exc)
        logger.debug("AST walk: scanned %d files, found %d tests", files_scanned, count)
        return count


class LiveModuleCountEvaluator:
    """Evaluator that counts Python modules in the configured src tree.

    C01 Phase 3: project-aware. Reads ``ctx.src_dir`` so foreign-repo
    runs report their own module count rather than NineS's 72
    (closes baseline §4.8 silent-fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize live module count evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Evaluate and return live module count."""
        src_dir = ctx.src_dir if ctx is not None else self._src_dir
        count = 0
        try:
            for py_file in src_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                if "__pycache__" in py_file.parts:
                    continue
                count += 1
        except Exception as exc:
            logger.error("Failed to scan source directory %s: %s", src_dir, exc)

        return DimensionScore(
            name="module_count",
            value=float(count),
            max_value=float(max(count, 1)),
            metadata={"unit": "modules", "src_dir": str(src_dir)},
        )


class DocstringCoverageEvaluator:
    """Evaluator that measures docstring coverage of public functions/classes.

    C01 Phase 3: project-aware. Reads ``ctx.src_dir`` so foreign-repo
    runs report their own docstring density rather than NineS's
    99.65 (closes baseline §4.8 silent-fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize docstring coverage evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Evaluate and return docstring coverage."""
        src_dir = ctx.src_dir if ctx is not None else self._src_dir
        total = 0
        documented = 0
        try:
            for py_file in src_dir.rglob("*.py"):
                if "__pycache__" in py_file.parts:
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError) as exc:
                    logger.warning("Skipping %s: %s", py_file, exc)
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name.startswith("_"):
                            continue
                        total += 1
                        if ast.get_docstring(node):
                            documented += 1
        except Exception as exc:
            logger.error("Failed to scan source directory %s: %s", src_dir, exc)

        pct = (documented / total * 100.0) if total > 0 else 0.0
        return DimensionScore(
            name="docstring_coverage",
            value=pct,
            max_value=100.0,
            metadata={
                "unit": "percent",
                "total": total,
                "documented": documented,
                "src_dir": str(src_dir),
            },
        )


class LintCleanlinessEvaluator:
    """Evaluator that measures lint cleanliness via ruff.

    C01 Phase 3: project-aware. Reads ``ctx.src_dir`` so foreign-repo
    runs lint their own sources rather than NineS's (closes baseline
    §4.8 silent-fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize lint cleanliness evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
        budget: TimeBudget | None = None,
    ) -> DimensionScore:
        """Evaluate and return lint cleanliness score.

        Parameters
        ----------
        ctx:
            Project context. When supplied, ``ctx.src_dir`` overrides
            the constructor default.
        budget:
            Optional runner-supplied :class:`TimeBudget`.  When set, the
            inner ``ruff check`` subprocess uses
            ``min(300s, budget.hard_seconds * 0.9)`` (release follow-up
            N2).
        """
        src_dir = ctx.src_dir if ctx is not None else self._src_dir
        timeout_s = _budgeted_subprocess_timeout(300.0, budget)
        violation_count = 0
        try:
            result = subprocess.run(
                ["python", "-m", "ruff", "check", str(src_dir), "--output-format=json", "-q"],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            if result.stdout.strip():
                violations = json.loads(result.stdout)
                violation_count = len(violations)
        except subprocess.TimeoutExpired:
            logger.error(
                "ruff check timed out after %.1fs (budget-derived)",
                timeout_s,
            )
        except Exception as exc:
            logger.error("Failed to run ruff check: %s", exc)

        raw_score = max(0.0, 100.0 - violation_count * 2.0)
        return DimensionScore(
            name="lint_cleanliness",
            value=raw_score,
            max_value=100.0,
            metadata={
                "unit": "score",
                "violation_count": violation_count,
                "src_dir": str(src_dir),
            },
        )
