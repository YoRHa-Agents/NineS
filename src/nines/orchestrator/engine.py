"""Workflow execution engine with dependency-aware topological scheduling.

``WorkflowEngine`` accepts a list of ``WorkflowStep`` objects, builds a
dependency DAG, resolves execution order via topological sort, and
runs each step sequentially while forwarding upstream results.

Covers: FR-501, FR-502, FR-510.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from nines.core.errors import OrchestrationError
from nines.orchestrator.models import WorkflowResult, WorkflowStep

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Dependency-aware workflow execution engine.

    Usage::

        engine = WorkflowEngine()
        engine.define([step_a, step_b, step_c])
        result = engine.run()
    """

    def __init__(self) -> None:
        self._steps: list[WorkflowStep] = []
        self._step_map: dict[str, WorkflowStep] = {}

    def define(self, steps: list[WorkflowStep]) -> None:
        """Register the steps that make up this workflow.

        Parameters
        ----------
        steps:
            Ordered list of ``WorkflowStep`` objects.  Duplicate names
            raise ``OrchestrationError``.

        Raises
        ------
        OrchestrationError
            On duplicate step names or missing dependency references.
        """
        seen: set[str] = set()
        for step in steps:
            if step.name in seen:
                raise OrchestrationError(
                    f"Duplicate step name: '{step.name}'",
                    details={"step": step.name},
                )
            seen.add(step.name)

        step_map = {s.name: s for s in steps}
        for step in steps:
            for dep in step.depends_on:
                if dep not in step_map:
                    raise OrchestrationError(
                        f"Step '{step.name}' depends on unknown step '{dep}'",
                        details={"step": step.name, "missing_dep": dep},
                    )

        self._steps = list(steps)
        self._step_map = step_map

    def run(self) -> WorkflowResult:
        """Execute all defined steps in topological order.

        Each step handler receives a dict of results from its declared
        dependencies.  If a step raises, the error is recorded and
        downstream dependents are skipped.

        Returns
        -------
        WorkflowResult
            Aggregate outcome with per-step results and timing.
        """
        if not self._steps:
            return WorkflowResult()

        order = self._topological_sort()
        result = WorkflowResult()
        all_results: dict[str, Any] = {}
        failed: set[str] = set()
        start = time.monotonic()

        for step_name in order:
            step = self._step_map[step_name]

            if any(dep in failed for dep in step.depends_on):
                msg = f"Skipped due to failed dependency"
                result.errors[step_name] = msg
                failed.add(step_name)
                logger.warning("Step '%s' skipped: upstream dependency failed", step_name)
                continue

            dep_results = {dep: all_results[dep] for dep in step.depends_on}
            logger.info("Running step '%s'", step_name)
            step_start = time.monotonic()

            try:
                value = step.handler(dep_results)
            except Exception as exc:
                elapsed = time.monotonic() - step_start
                result.errors[step_name] = str(exc)
                failed.add(step_name)
                logger.error(
                    "Step '%s' failed after %.3fs: %s",
                    step_name, elapsed, exc,
                    exc_info=True,
                )
                continue

            elapsed = time.monotonic() - step_start
            all_results[step_name] = value
            result.steps_completed.append(step_name)
            result.results[step_name] = value
            logger.info("Step '%s' completed in %.3fs", step_name, elapsed)

        result.total_duration = time.monotonic() - start
        return result

    def _topological_sort(self) -> list[str]:
        """Kahn's algorithm for topological ordering.

        Raises
        ------
        OrchestrationError
            If the dependency graph contains a cycle.
        """
        in_degree: dict[str, int] = {s.name: 0 for s in self._steps}
        adjacency: dict[str, list[str]] = {s.name: [] for s in self._steps}

        for step in self._steps:
            for dep in step.depends_on:
                adjacency[dep].append(step.name)
                in_degree[step.name] += 1

        queue: deque[str] = deque(
            name for name, deg in in_degree.items() if deg == 0
        )
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._steps):
            raise OrchestrationError(
                "Dependency cycle detected in workflow steps",
                details={"resolved": order, "total": len(self._steps)},
            )

        return order
