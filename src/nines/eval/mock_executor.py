"""Deterministic mock executor for the eval framework.

Eval-framework regressions are hard to spot in CI today because the
default executor depends on live LLM calls / sandbox subprocesses.
``DeterministicMockExecutor`` produces hash-seeded outputs keyed on
``task.id`` so the same input always yields the same
:class:`ExecutionResult` across runs.  Different task IDs produce
distinct outputs; per-criterion weights are honoured when the task
defines them.

Usage example::

    from nines.eval.mock_executor import DeterministicMockExecutor
    from nines.eval.runner import EvalRunner
    runner = EvalRunner()
    results = runner.run(tasks, DeterministicMockExecutor(), [scorer])

Covers: C06 (deterministic mock executor for golden harness).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from nines.core.models import ExecutionResult
from nines.eval.models import TaskDefinition

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
            msg = (
                "DeterministicMockExecutor expects a TaskDefinition, "
                f"got {type(task).__name__}"
            )
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


__all__ = ["DeterministicMockExecutor"]
