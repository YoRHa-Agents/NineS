"""Tests for nines.orchestrator — workflow engine and pipelines.

Covers:
  - WorkflowEngine runs sequential steps
  - WorkflowEngine respects dependency ordering (topological sort)
  - WorkflowEngine detects cycles
  - WorkflowEngine handles step failures gracefully
  - Pipeline.eval_pipeline wires real EvalRunner
  - Pipeline.analyze_pipeline wires real AnalysisPipeline
  - Pipeline.benchmark_pipeline runs full workflow
  - Pipeline error handling returns graceful failures
"""

from __future__ import annotations

import json
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

_TASK_TOML = """\
[task]
id = "eval-test-001"
name = "Greeting Test"
description = "Tests greeting output"
dimension = "test"

[task.expected]
value = "hello world"
"""


def test_pipeline_eval(tmp_path: Path) -> None:
    """Pipeline.eval_pipeline loads real tasks and runs evaluation."""
    (tmp_path / "task_001.toml").write_text(_TASK_TOML)
    output = tmp_path / "report.json"

    result = Pipeline.eval_pipeline(
        tasks_path=str(tmp_path),
        output_path=str(output),
    )

    assert result.success
    assert "load" in result.steps_completed
    assert "execute" in result.steps_completed
    assert "score" in result.steps_completed
    assert "report" in result.steps_completed
    assert result.results["load"]["task_count"] == 1
    assert result.results["execute"]["results_count"] == 1
    assert result.results["report"]["report_generated"] is True
    assert output.exists()

    report_data = json.loads(output.read_text())
    assert report_data["task_count"] == 1


def test_pipeline_eval_multiple_tasks(tmp_path: Path) -> None:
    """eval_pipeline handles multiple task files."""
    for i in range(3):
        toml = f"""\
[task]
id = "multi-{i}"
name = "Task {i}"
dimension = "test"

[task.expected]
value = "output-{i}"
"""
        (tmp_path / f"task_{i:03d}.toml").write_text(toml)

    output = tmp_path / "report.json"
    result = Pipeline.eval_pipeline(
        tasks_path=str(tmp_path),
        output_path=str(output),
    )

    assert result.success
    assert result.results["load"]["task_count"] == 3
    assert result.results["execute"]["results_count"] == 3


def test_pipeline_eval_error_handling() -> None:
    """eval_pipeline returns graceful failure for missing path."""
    result = Pipeline.eval_pipeline(
        tasks_path="/nonexistent/path/tasks",
        output_path="/tmp/nines_test_report.json",
    )

    assert not result.success
    assert result.errors


# ---------------------------------------------------------------------------
# test_pipeline_collect
# ---------------------------------------------------------------------------


def test_pipeline_collect() -> None:
    """Pipeline.collect_pipeline remains a working stub."""
    result = Pipeline.collect_pipeline(
        sources=["github", "arxiv"],
        store_path="/tmp/store",
    )

    assert result.success
    assert "discover" in result.steps_completed
    assert "fetch" in result.steps_completed
    assert "store" in result.steps_completed


# ---------------------------------------------------------------------------
# test_pipeline_analyze
# ---------------------------------------------------------------------------


def test_pipeline_analyze(tmp_path: Path) -> None:
    """Pipeline.analyze_pipeline runs real analysis on Python code."""
    src = tmp_path / "sample.py"
    src.write_text(
        "def greet(name: str) -> str:\n    return f'Hello, {name}'\n",
    )
    index = tmp_path / "index.json"

    result = Pipeline.analyze_pipeline(
        target_path=str(src),
        index_path=str(index),
    )

    assert result.success
    assert "parse" in result.steps_completed
    assert "analyze" in result.steps_completed
    assert "index" in result.steps_completed
    assert index.exists()

    idx_data = json.loads(index.read_text())
    assert idx_data["target"] == str(src)


def test_pipeline_analyze_error_handling() -> None:
    """analyze_pipeline returns graceful failure for missing path."""
    result = Pipeline.analyze_pipeline(
        target_path="/nonexistent/code.py",
        index_path="/tmp/nines_test_index.json",
    )

    assert not result.success
    assert result.errors


# ---------------------------------------------------------------------------
# test_pipeline_benchmark
# ---------------------------------------------------------------------------


def test_pipeline_benchmark_with_keypoints(tmp_path: Path) -> None:
    """benchmark_pipeline runs full workflow with provided key points."""
    src = tmp_path / "code.py"
    src.write_text("x = 1\n")

    kp_data = [
        {
            "id": "kp-test-1",
            "category": "engineering",
            "title": "Test Key Point",
            "description": "A test observation about code quality",
        },
    ]

    result = Pipeline.benchmark_pipeline(
        target_path=str(src),
        key_points_data=kp_data,
        suite_id="test-suite",
        scorer_names=["exact"],
    )

    assert result.success
    assert "analyze" in result.steps_completed
    assert "extract_keypoints" in result.steps_completed
    assert "generate_benchmarks" in result.steps_completed
    assert "evaluate" in result.steps_completed
    assert "map_results" in result.steps_completed

    kps = result.results["extract_keypoints"]["key_points"]
    assert len(kps) == 1
    assert kps[0].id == "kp-test-1"

    mapping = result.results["map_results"]["mapping"]
    assert "conclusions" in mapping


def test_pipeline_benchmark_derives_keypoints(
    tmp_path: Path,
) -> None:
    """benchmark_pipeline derives key points from analysis findings."""
    src = tmp_path / "sample.py"
    src.write_text(
        "def greet(name: str) -> str:\n    return f'Hello, {name}'\n",
    )

    result = Pipeline.benchmark_pipeline(
        target_path=str(src),
        suite_id="auto-kp-suite",
    )

    assert result.success
    assert "extract_keypoints" in result.steps_completed


def test_pipeline_benchmark_error_handling() -> None:
    """benchmark_pipeline returns graceful failure for bad input."""
    result = Pipeline.benchmark_pipeline(
        target_path="/nonexistent/code.py",
    )

    assert not result.success
    assert result.errors


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
    step = WorkflowStep(
        name="x",
        handler=lambda d: None,
        depends_on=["y", "z"],
    )
    d = step.to_dict()
    assert d["name"] == "x"
    assert d["depends_on"] == ["y", "z"]
