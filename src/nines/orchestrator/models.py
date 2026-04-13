"""Data models for the workflow orchestration engine.

Provides ``WorkflowStep`` to define individual pipeline steps with
dependency edges, and ``WorkflowResult`` to capture the aggregate
outcome of a full workflow run.

Covers: FR-501, FR-502.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class WorkflowStep:
    """A single step in a workflow graph.

    Attributes
    ----------
    name:
        Unique identifier for this step within a workflow.
    handler:
        Callable that performs the step's work.  Receives a dict of
        upstream results keyed by dependency step name. Returns an
        arbitrary result value.
    depends_on:
        Names of steps that must complete before this step can execute.
    """

    name: str
    handler: Callable[[dict[str, Any]], Any]
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "depends_on": list(self.depends_on),
        }


@dataclass
class WorkflowResult:
    """Aggregate outcome of running a full workflow.

    Attributes
    ----------
    steps_completed:
        Names of steps that finished successfully.
    results:
        Mapping of step name -> step return value.
    total_duration:
        Wall-clock seconds for the entire workflow run.
    errors:
        Mapping of step name -> error message for any failed steps.
    """

    steps_completed: list[str] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    total_duration: float = 0.0
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Return True if the workflow completed without errors."""
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "steps_completed": list(self.steps_completed),
            "results": dict(self.results),
            "total_duration": self.total_duration,
            "errors": dict(self.errors),
            "success": self.success,
        }
