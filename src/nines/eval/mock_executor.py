"""Deterministic mock executor for the eval framework.

Eval-framework regressions are hard to spot in CI today because the
default executor depends on live LLM calls / sandbox subprocesses.
``DeterministicMockExecutor`` produces hash-seeded outputs keyed on
``task.id`` so the same input always yields the same
:class:`ExecutionResult` across runs.  Different task IDs produce
distinct outputs; per-criterion weights are honoured when the task
defines them.

This module also ships ``MockEvaluator``, a deterministic
:class:`~nines.iteration.self_eval.DimensionEvaluator` implementation
used by the golden test harness.  It returns a fixed
:class:`~nines.iteration.self_eval.DimensionScore` so self-eval golden
tests can bypass live ``pytest --collect-only`` / ``ruff`` subprocess
calls (covers C06 design's *MockEvaluator* + *hang-detection* +
*silent-fallback regression* deliverables).

Usage example::

    from nines.eval.mock_executor import DeterministicMockExecutor
    from nines.eval.runner import EvalRunner
    runner = EvalRunner()
    results = runner.run(tasks, DeterministicMockExecutor(), [scorer])

    from nines.eval.mock_executor import MockEvaluator
    from nines.iteration.self_eval import SelfEvalRunner
    runner = SelfEvalRunner()
    runner.register_dimension(
        "test_count",
        MockEvaluator(name="test_count", value=42.0, max_value=100.0),
    )
    report = runner.run_all(version="v3.1.0")

Covers: C06 (deterministic mock executor + MockEvaluator for golden harness).
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Mapping

from nines.core.models import ExecutionResult
from nines.eval.models import TaskDefinition
from nines.iteration.self_eval import DimensionScore

logger = logging.getLogger(__name__)


@dataclass
class DeterministicMockExecutor:
    """Reproducible :class:`ExecutionResult` factory keyed on ``task.id``.

    Attributes
    ----------
    seed:
        Optional global salt mixed into the hash so different test
        suites can ask for different deterministic streams while still
        getting reproducibility within a suite.
    fixed_outputs:
        Optional mapping ``{task_id: output}`` that overrides the
        hash-derived value for specific task IDs.  Useful for golden
        fixtures where a particular value matters.
    base_token_count:
        Tokens reported in ``ExecutionResult.metrics`` for a single-
        criterion task; the per-task value scales with the number of
        scoring criteria so weighted scenarios stay measurable.
    """

    seed: str = ""
    fixed_outputs: Mapping[str, Any] = field(default_factory=dict)
    base_token_count: int = 8

    def __call__(self, task: TaskDefinition) -> ExecutionResult:
        """Return a deterministic :class:`ExecutionResult` for *task*."""
        if not isinstance(task, TaskDefinition):
            msg = f"DeterministicMockExecutor expects a TaskDefinition, got {type(task).__name__}"
            raise TypeError(msg)

        if task.id in self.fixed_outputs:
            output = self.fixed_outputs[task.id]
        else:
            output = self._derive_output(task.id)

        # Token count scales with the criteria count so weighted scoring
        # exercises see a non-trivial ``token_count`` per task.
        criteria_factor = max(1, len(task.scoring_criteria))
        tokens = self.base_token_count * criteria_factor

        return ExecutionResult(
            task_id=task.id,
            output=output,
            metrics={
                "token_count": tokens,
                "executor": "DeterministicMockExecutor",
                "seed": self.seed,
            },
            duration_ms=0.0,
            success=True,
        )

    def _derive_output(self, task_id: str) -> str:
        """Return a stable string derived from ``task_id`` (and seed)."""
        payload = f"{self.seed}\x1f{task_id}".encode()
        digest = hashlib.blake2s(payload, digest_size=16).hexdigest()
        # Format: 'mock-<8-hex>-<8-hex>' so equality assertions are
        # readable in test diff output.
        return f"mock-{digest[:8]}-{digest[8:16]}"


@dataclass
class MockEvaluator:
    """Deterministic ``DimensionEvaluator`` for the golden test harness.

    Implements the
    :class:`~nines.iteration.self_eval.DimensionEvaluator` Protocol
    structurally — call sites can register an instance with
    :meth:`~nines.iteration.self_eval.SelfEvalRunner.register_dimension`
    and the runner will treat it like any built-in evaluator.

    The constructor accepts everything needed to reconstruct a
    ``DimensionScore`` (name / value / max_value / metadata) plus two
    test-only knobs:

    * ``sleep_seconds`` — inject a ``time.sleep`` before returning the
      score.  Used by the C04 × C06 hang-detection joint test to verify
      that ``TimeBudget(hard_seconds=...)`` actually aborts a runaway
      evaluator.
    * ``raise_on_call`` — raise the given exception class instead of
      returning a score.  Used to verify the runner's
      ``except Exception`` fallback path produces a 0-value placeholder
      and doesn't cascade-fail subsequent dimensions.

    Determinism: identical constructor arguments yield byte-identical
    :class:`DimensionScore` outputs across calls and processes — there
    is *no* clock-based randomness in the result path.

    Examples
    --------
    >>> mock = MockEvaluator(name="test_count", value=42.0, max_value=100.0)
    >>> score = mock.evaluate()
    >>> score.name, score.value, score.normalized
    ('test_count', 42.0, 0.42)

    >>> hangs = MockEvaluator(name="slow", sleep_seconds=10.0)  # used with TimeBudget
    >>> boom = MockEvaluator(name="bad", raise_on_call=RuntimeError)

    Parameters
    ----------
    name:
        Dimension identifier (mirrored into :attr:`DimensionScore.name`).
    value:
        Numeric score value (default ``1.0``).
    max_value:
        Upper bound for normalisation (default ``1.0``).  Must be ``>= 0``.
    metadata:
        Optional metadata dict copied onto the returned
        ``DimensionScore``.  ``None`` → empty dict.
    sleep_seconds:
        Optional pre-return sleep in seconds.  ``0`` (default) means no
        sleep.  Negative values are rejected at construction time.
    raise_on_call:
        Optional ``Exception`` subclass.  When set, :meth:`evaluate`
        raises an instance of this class instead of returning a score —
        useful for failure-path tests.

    Notes
    -----
    The class is a frozen ``@dataclass`` semantically (no mutating
    methods exist) but is left mutable so test fixtures can patch
    ``value`` between calls when needed.
    """

    #: Class-level flag honored by ``SelfEvalRunner`` (see
    #: ``DimensionEvaluator`` Protocol). ``False`` keeps MockEvaluator
    #: backward-compatible with the no-context call shape used by C06's
    #: golden harness.
    requires_context: ClassVar[bool] = False

    name: str
    value: float = 1.0
    max_value: float = 1.0
    metadata: dict[str, Any] | None = None
    sleep_seconds: float = 0.0
    raise_on_call: type[BaseException] | None = None

    def __post_init__(self) -> None:
        # Validate up-front so mis-configured fixtures fail loudly at
        # construction time, not during a long test run.
        if self.max_value < 0:
            msg = f"MockEvaluator.max_value must be >= 0, got {self.max_value}"
            raise ValueError(msg)
        if self.sleep_seconds < 0:
            msg = f"MockEvaluator.sleep_seconds must be >= 0, got {self.sleep_seconds}"
            raise ValueError(msg)
        if self.raise_on_call is not None and not (
            isinstance(self.raise_on_call, type) and issubclass(self.raise_on_call, BaseException)
        ):
            msg = (
                "MockEvaluator.raise_on_call must be a BaseException subclass, "
                f"got {self.raise_on_call!r}"
            )
            raise TypeError(msg)

    def evaluate(self) -> DimensionScore:
        """Return the configured :class:`DimensionScore`.

        Behaviour matrix:

        * If ``sleep_seconds > 0`` → :func:`time.sleep` first (lets the
          C04 budget fire when the runner wraps the call in
          :func:`evaluator_budget`).
        * If ``raise_on_call`` is set → raise an instance of that class
          (lets the runner's ``except Exception`` branch produce a
          zero-value placeholder).
        * Otherwise → return a deep-copied
          :class:`DimensionScore` so callers cannot mutate the
          evaluator's stored ``metadata`` by mutating the returned
          score's metadata dict.

        Raises
        ------
        BaseException
            The class given to ``raise_on_call``, when set.
        """
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)

        if self.raise_on_call is not None:
            raise self.raise_on_call(f"MockEvaluator(name={self.name!r}) configured to raise")

        # Copy metadata so external callers cannot mutate the
        # evaluator's stored dict via the returned score.
        meta_copy: dict[str, Any] = dict(self.metadata) if self.metadata else {}
        return DimensionScore(
            name=self.name,
            value=self.value,
            max_value=self.max_value,
            metadata=meta_copy,
        )


__all__ = ["DeterministicMockExecutor", "MockEvaluator"]
