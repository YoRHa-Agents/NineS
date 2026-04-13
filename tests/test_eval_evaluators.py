"""Tests for nines.iteration.eval_evaluators — V1 + System evaluators.

Covers:
  - EvalCoverageEvaluator validates TOML task files and scores correctly
  - ReportQualityEvaluator generates and checks markdown/JSON reports
  - PipelineLatencyEvaluator runs the analysis pipeline and scores latency
  - SandboxIsolationEvaluator creates, runs, and cleans up a sandbox
  - All evaluators conform to the DimensionEvaluator protocol
  - All evaluators handle error conditions gracefully
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.eval_evaluators import (
    EvalCoverageEvaluator,
    PipelineLatencyEvaluator,
    ReportQualityEvaluator,
    SandboxIsolationEvaluator,
)
from nines.iteration.self_eval import DimensionEvaluator, DimensionScore

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [
        EvalCoverageEvaluator,
        ReportQualityEvaluator,
        PipelineLatencyEvaluator,
        SandboxIsolationEvaluator,
    ],
)
def test_protocol_conformance(cls: type) -> None:
    """Every evaluator satisfies the DimensionEvaluator protocol."""
    inst = cls()
    assert isinstance(inst, DimensionEvaluator)


# ---------------------------------------------------------------------------
# EvalCoverageEvaluator (D02)
# ---------------------------------------------------------------------------


def test_eval_coverage_with_real_samples() -> None:
    """EvalCoverageEvaluator loads real sample TOML files."""
    evaluator = EvalCoverageEvaluator(sample_dir="samples/eval")
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "eval_coverage"
    assert score.max_value == 1.0
    assert 0.0 < score.value <= 1.0
    assert score.metadata["total_files"] >= 3
    assert score.metadata["valid_tasks"] >= 1


def test_eval_coverage_valid_files(tmp_path: Path) -> None:
    """Score is 1.0 when all TOML files are valid."""
    task_toml = tmp_path / "task1.toml"
    task_toml.write_text(
        '[task]\nid = "t1"\nname = "test"\n'
        '[task.input]\ntype = "code"\nsource = "x"\n'
        '[task.expected]\nvalue = "y"\n'
    )
    evaluator = EvalCoverageEvaluator(sample_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 1.0
    assert score.metadata["valid_tasks"] == 1
    assert score.metadata["total_files"] == 1


def test_eval_coverage_empty_dir(tmp_path: Path) -> None:
    """Score is 0.0 for a directory with no TOML files."""
    evaluator = EvalCoverageEvaluator(sample_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert score.metadata["total_files"] == 0


def test_eval_coverage_invalid_toml(tmp_path: Path) -> None:
    """Score is 0.0 when TOML files are malformed."""
    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("this is not valid toml [[[")
    evaluator = EvalCoverageEvaluator(sample_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert score.metadata["total_files"] == 1
    assert "bad.toml" in score.metadata["details"]
    assert score.metadata["details"]["bad.toml"]["status"] == "error"


def test_eval_coverage_missing_fields(tmp_path: Path) -> None:
    """Tasks missing required fields are scored as invalid."""
    task_toml = tmp_path / "incomplete.toml"
    task_toml.write_text('[task]\nid = "t1"\nname = "test"\n')
    evaluator = EvalCoverageEvaluator(sample_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 0.0
    details = score.metadata["details"]["incomplete.toml"]
    assert details["status"] == "invalid"
    assert "expected" in details["missing"]


# ---------------------------------------------------------------------------
# ReportQualityEvaluator (D04)
# ---------------------------------------------------------------------------


def test_report_quality_full_score() -> None:
    """ReportQualityEvaluator generates valid reports and scores them."""
    evaluator = ReportQualityEvaluator()
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "report_quality"
    assert score.max_value == 1.0
    assert score.value == 1.0
    assert score.metadata["passed"] == score.metadata["total"]

    checks = score.metadata["checks"]
    assert checks["md_generates"] is True
    assert checks["md_has_summary"] is True
    assert checks["md_has_results"] is True
    assert checks["md_has_scores"] is True
    assert checks["json_valid"] is True
    assert checks["json_has_required_keys"] is True


# ---------------------------------------------------------------------------
# PipelineLatencyEvaluator (D16)
# ---------------------------------------------------------------------------


def test_pipeline_latency_real_file() -> None:
    """PipelineLatencyEvaluator runs on the real __init__.py."""
    evaluator = PipelineLatencyEvaluator(target="src/nines/__init__.py")
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "pipeline_latency"
    assert score.max_value == 1.0
    assert 0.0 <= score.value <= 1.0
    assert "elapsed_seconds" in score.metadata
    assert score.metadata["elapsed_seconds"] >= 0


def test_pipeline_latency_missing_target(tmp_path: Path) -> None:
    """Score is 0.0 when the target file does not exist."""
    evaluator = PipelineLatencyEvaluator(target=tmp_path / "nonexistent.py")
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


def test_pipeline_latency_small_file(tmp_path: Path) -> None:
    """Pipeline completes quickly on a tiny Python file."""
    tiny = tmp_path / "tiny.py"
    tiny.write_text("x = 1\n")
    evaluator = PipelineLatencyEvaluator(target=tiny)
    score = evaluator.evaluate()

    assert score.value > 0.5
    assert score.metadata["elapsed_seconds"] < 10


# ---------------------------------------------------------------------------
# SandboxIsolationEvaluator (D17)
# ---------------------------------------------------------------------------


def test_sandbox_isolation_basic() -> None:
    """SandboxIsolationEvaluator creates, runs, and cleans up a sandbox."""
    evaluator = SandboxIsolationEvaluator()
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "sandbox_isolation"
    assert score.max_value == 1.0
    assert 0.0 <= score.value <= 1.0

    checks = score.metadata.get("checks", {})
    if score.value > 0.5:
        assert checks.get("executed") is True
        assert checks.get("correct_output") is True


# ---------------------------------------------------------------------------
# Error resilience: evaluators should never crash
# ---------------------------------------------------------------------------


def test_all_evaluators_return_dimension_score() -> None:
    """All evaluators return DimensionScore even with default arguments."""
    evaluators = [
        EvalCoverageEvaluator(),
        ReportQualityEvaluator(),
        PipelineLatencyEvaluator(),
        SandboxIsolationEvaluator(),
    ]
    for evaluator in evaluators:
        score = evaluator.evaluate()
        assert isinstance(score, DimensionScore)
        assert isinstance(score.value, float)
        assert isinstance(score.max_value, float)
        assert isinstance(score.metadata, dict)
        assert score.name != ""


# ---------------------------------------------------------------------------
# Integration: register all in SelfEvalRunner
# ---------------------------------------------------------------------------


def test_register_with_self_eval_runner() -> None:
    """All four evaluators can be registered and run via SelfEvalRunner."""
    from nines.iteration.self_eval import SelfEvalRunner

    runner = SelfEvalRunner()
    runner.register_dimension("eval_coverage", EvalCoverageEvaluator(sample_dir="samples/eval"))
    runner.register_dimension("report_quality", ReportQualityEvaluator())
    runner.register_dimension(
        "pipeline_latency",
        PipelineLatencyEvaluator(target="src/nines/__init__.py"),
    )
    runner.register_dimension("sandbox_isolation", SandboxIsolationEvaluator())

    report = runner.run_all(version="test-v1")

    assert len(report.scores) == 4
    assert report.version == "test-v1"
    assert 0.0 <= report.overall <= 1.0

    for score in report.scores:
        assert isinstance(score, DimensionScore)
        assert score.name in {
            "eval_coverage",
            "report_quality",
            "pipeline_latency",
            "sandbox_isolation",
        }
