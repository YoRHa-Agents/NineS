"""Tests for nines.orchestrator — workflow engine and pipelines.

Covers:
  - WorkflowEngine runs sequential steps
  - WorkflowEngine respects dependency ordering (topological sort)
  - WorkflowEngine detects cycles
  - WorkflowEngine handles step failures gracefully
  - Pipeline.eval_pipeline wires modules together
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.core.errors import OrchestrationError
from nines.orchestrator.engine import WorkflowEngine
from nines.orchestrator.models import WorkflowResult, WorkflowStep
from nines.orchestrator.pipeline import Pipeline


# ---------------------------------------------------------------------------
# test_workflow_sequential
# ---------------------------------------------------------------------------


def test_workflow_sequential() -> None:
    """Steps with no dependencies run in definition order."""
    execution_order: list[str] = []

    def make_handler(name: str):
        def handler(deps: dict[str, Any]) -> str:
            execution_order.append(name)
            return f"{name}_done"
        return handler

    steps = [
        WorkflowStep(name="a", handler=make_handler("a")),
        WorkflowStep(name="b", handler=make_handler("b")),
        WorkflowStep(name="c", handler=make_handler("c")),
    ]

    engine = WorkflowEngine()
    engine.define(steps)
    result = engine.run()

    assert result.success
    assert result.steps_completed == ["a", "b", "c"]
    assert execution_order == ["a", "b", "c"]
    assert result.results["a"] == "a_done"
    assert result.results["b"] == "b_done"
    assert result.results["c"] == "c_done"
    assert result.total_duration > 0


# ---------------------------------------------------------------------------
# test_workflow_with_deps
# ---------------------------------------------------------------------------


def test_workflow_with_deps() -> None:
    """Steps with dependencies execute after their prerequisites."""
    execution_order: list[str] = []

    def step_load(deps: dict[str, Any]) -> dict[str, int]:
        execution_order.append("load")
        return {"task_count": 5}

    def step_process(deps: dict[str, Any]) -> dict[str, int]:
        execution_order.append("process")
        count = deps["load"]["task_count"]
        return {"processed": count * 2}

    def step_report(deps: dict[str, Any]) -> str:
        execution_order.append("report")
        processed = deps["process"]["processed"]
        return f"Processed {processed} items"

    steps = [
        WorkflowStep(name="report", handler=step_report, depends_on=["process"]),
        WorkflowStep(name="process", handler=step_process, depends_on=["load"]),
        WorkflowStep(name="load", handler=step_load),
    ]

    engine = WorkflowEngine()
    engine.define(steps)
    result = engine.run()

    assert result.success
    assert execution_order == ["load", "process", "report"]
    assert result.results["load"] == {"task_count": 5}
    assert result.results["process"] == {"processed": 10}
    assert result.results["report"] == "Processed 10 items"


def test_workflow_diamond_deps() -> None:
    """Diamond dependency pattern: A -> B, A -> C, B+C -> D."""
    execution_order: list[str] = []

    def handler_a(deps: dict[str, Any]) -> int:
        execution_order.append("a")
        return 1

    def handler_b(deps: dict[str, Any]) -> int:
        execution_order.append("b")
        return deps["a"] + 10

    def handler_c(deps: dict[str, Any]) -> int:
        execution_order.append("c")
        return deps["a"] + 100

    def handler_d(deps: dict[str, Any]) -> int:
        execution_order.append("d")
        return deps["b"] + deps["c"]

    steps = [
        WorkflowStep(name="a", handler=handler_a),
        WorkflowStep(name="b", handler=handler_b, depends_on=["a"]),
        WorkflowStep(name="c", handler=handler_c, depends_on=["a"]),
        WorkflowStep(name="d", handler=handler_d, depends_on=["b", "c"]),
    ]

    engine = WorkflowEngine()
    engine.define(steps)
    result = engine.run()

    assert result.success
    assert execution_order.index("a") < execution_order.index("b")
    assert execution_order.index("a") < execution_order.index("c")
    assert execution_order.index("b") < execution_order.index("d")
    assert execution_order.index("c") < execution_order.index("d")
    assert result.results["d"] == 11 + 101


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def test_workflow_cycle_detection() -> None:
    """Cyclic dependencies raise OrchestrationError."""
    steps = [
        WorkflowStep(name="a", handler=lambda d: None, depends_on=["c"]),
        WorkflowStep(name="b", handler=lambda d: None, depends_on=["a"]),
        WorkflowStep(name="c", handler=lambda d: None, depends_on=["b"]),
    ]

    engine = WorkflowEngine()
    engine.define(steps)
    with pytest.raises(OrchestrationError, match="cycle"):
        engine.run()


# ---------------------------------------------------------------------------
# Duplicate step names
# ---------------------------------------------------------------------------


def test_workflow_duplicate_names() -> None:
    """Duplicate step names raise OrchestrationError."""
    steps = [
        WorkflowStep(name="a", handler=lambda d: None),
        WorkflowStep(name="a", handler=lambda d: None),
    ]

    engine = WorkflowEngine()
    with pytest.raises(OrchestrationError, match="Duplicate"):
        engine.define(steps)


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------


def test_workflow_missing_dependency() -> None:
    """Reference to unknown step raises OrchestrationError."""
    steps = [
        WorkflowStep(name="a", handler=lambda d: None, depends_on=["nonexistent"]),
    ]

    engine = WorkflowEngine()
    with pytest.raises(OrchestrationError, match="unknown step"):
        engine.define(steps)


# ---------------------------------------------------------------------------
# Step failure handling
# ---------------------------------------------------------------------------


def test_workflow_step_failure_skips_dependents() -> None:
    """A failing step causes dependents to be skipped."""
    def fail_handler(deps: dict[str, Any]) -> None:
        raise ValueError("intentional failure")

    steps = [
        WorkflowStep(name="a", handler=lambda d: "ok"),
        WorkflowStep(name="b", handler=fail_handler, depends_on=["a"]),
        WorkflowStep(name="c", handler=lambda d: "should not run", depends_on=["b"]),
    ]

    engine = WorkflowEngine()
    engine.define(steps)
    result = engine.run()

    assert not result.success
    assert "a" in result.steps_completed
    assert "b" not in result.steps_completed
    assert "c" not in result.steps_completed
    assert "b" in result.errors
    assert "c" in result.errors


# ---------------------------------------------------------------------------
# Empty workflow
# ---------------------------------------------------------------------------


def test_workflow_empty() -> None:
    """Running an empty workflow produces an empty result."""
    engine = WorkflowEngine()
    engine.define([])
    result = engine.run()

    assert result.success
    assert result.steps_completed == []
    assert result.total_duration == 0


# ---------------------------------------------------------------------------
# test_pipeline_eval
# ---------------------------------------------------------------------------


def test_pipeline_eval() -> None:
    """Pipeline.eval_pipeline wires load->execute->score->report."""
    result = Pipeline.eval_pipeline(
        tasks_path="/tmp/tasks",
        output_path="/tmp/report.json",
    )

    assert result.success
    assert "load" in result.steps_completed
    assert "execute" in result.steps_completed
    assert "score" in result.steps_completed
    assert "report" in result.steps_completed
    assert result.results["report"]["output_path"] == "/tmp/report.json"
    assert result.total_duration > 0


def test_pipeline_collect() -> None:
    """Pipeline.collect_pipeline wires discover->fetch->store."""
    result = Pipeline.collect_pipeline(
        sources=["github", "arxiv"],
        store_path="/tmp/store",
    )

    assert result.success
    assert "discover" in result.steps_completed
    assert "fetch" in result.steps_completed
    assert "store" in result.steps_completed


def test_pipeline_analyze() -> None:
    """Pipeline.analyze_pipeline wires parse->analyze->index."""
    result = Pipeline.analyze_pipeline(
        target_path="/tmp/code",
        index_path="/tmp/index",
    )

    assert result.success
    assert "parse" in result.steps_completed
    assert "analyze" in result.steps_completed
    assert "index" in result.steps_completed


# ---------------------------------------------------------------------------
# WorkflowResult model
# ---------------------------------------------------------------------------


def test_workflow_result_to_dict() -> None:
    """WorkflowResult.to_dict serializes correctly."""
    result = WorkflowResult(
        steps_completed=["a", "b"],
        results={"a": 1, "b": 2},
        total_duration=1.23,
        errors={"c": "failed"},
    )
    d = result.to_dict()
    assert d["steps_completed"] == ["a", "b"]
    assert d["success"] is False
    assert d["total_duration"] == 1.23


def test_workflow_step_to_dict() -> None:
    """WorkflowStep.to_dict serializes name and depends_on."""
    step = WorkflowStep(name="x", handler=lambda d: None, depends_on=["y", "z"])
    d = step.to_dict()
    assert d["name"] == "x"
    assert d["depends_on"] == ["y", "z"]
