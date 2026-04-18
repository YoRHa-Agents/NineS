"""Integration test: end-to-end eval pipeline.

Create task TOML -> load -> run (mock executor) -> score -> report.
Covers the full evaluation lifecycle without external dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import json

import pytest

from nines.core.models import ExecutionResult
from nines.eval.metrics import MetricCollector
from nines.eval.models import ScoringCriterion, TaskDefinition
from nines.eval.reporters import JSONReporter, MarkdownReporter
from nines.eval.runner import EvalRunner
from nines.eval.scorers import (
    CompositeScorer,
    ExactScorer,
    FuzzyScorer,
    RubricItem,
    RubricScorer,
)


def _echo_executor(task: TaskDefinition) -> ExecutionResult:
    return ExecutionResult(
        task_id=task.id,
        output=task.expected,
        metrics={"token_count": 10},
        duration_ms=5.0,
        success=True,
    )


def _partial_executor(task: TaskDefinition) -> ExecutionResult:
    output = str(task.expected)[: len(str(task.expected)) // 2] if task.expected else ""
    return ExecutionResult(
        task_id=task.id,
        output=output,
        metrics={"token_count": 5},
        duration_ms=3.0,
        success=True,
    )


def _failing_executor(task: TaskDefinition) -> ExecutionResult:
    return ExecutionResult(task_id=task.id, output=None, success=False)


class TestEvalEndToEnd:
    """Full lifecycle: TOML -> load -> execute -> score -> report."""

    def test_single_task_perfect_score(self, tmp_path: Path) -> None:
        task = TaskDefinition(
            id="e2e-1",
            name="perfect-match",
            description="Expects exact echo",
            dimension="correctness",
            input_config={"prompt": "say hello"},
            expected="hello world",
            scoring_criteria=[
                ScoringCriterion(name="exact", weight=1.0, scorer_type="exact"),
            ],
            metadata={"difficulty": 1},
        )
        toml_file = tmp_path / "task_e2e.toml"
        toml_file.write_text(task.to_toml(), encoding="utf-8")

        runner = EvalRunner()
        loaded = runner.load_tasks(toml_file)
        assert len(loaded) == 1
        assert loaded[0].id == "e2e-1"

        results = runner.run(loaded, _echo_executor, [ExactScorer()])
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].composite_score == pytest.approx(1.0)

    def test_multi_task_directory(self, tmp_path: Path) -> None:
        for i in range(3):
            task = TaskDefinition(
                id=f"batch-{i}",
                name=f"batch-task-{i}",
                description=f"Batch task {i}",
                dimension="correctness",
                input_config={"prompt": f"task {i}"},
                expected=f"output-{i}",
                metadata={"index": i},
            )
            (tmp_path / f"task_{i}.toml").write_text(task.to_toml(), encoding="utf-8")

        runner = EvalRunner()
        loaded = runner.load_tasks(tmp_path)
        assert len(loaded) == 3

        results = runner.run(loaded, _echo_executor, [ExactScorer()])
        assert all(r.success for r in results)
        assert all(r.composite_score == pytest.approx(1.0) for r in results)

    def test_multi_scorer_pipeline(self, tmp_path: Path) -> None:
        task = TaskDefinition(
            id="multi-scorer",
            name="multi-scorer-test",
            dimension="quality",
            input_config={"prompt": "test"},
            expected="hello world",
        )
        toml_file = tmp_path / "multi_scorer.toml"
        toml_file.write_text(task.to_toml(), encoding="utf-8")

        runner = EvalRunner()
        loaded = runner.load_tasks(toml_file)
        scorers = [ExactScorer(), FuzzyScorer()]
        results = runner.run(loaded, _echo_executor, scorers)

        assert results[0].success is True
        assert len(results[0].scores) == 2
        assert results[0].scores[0].scorer_name == "exact"
        assert results[0].scores[1].scorer_name == "fuzzy"
        assert results[0].composite_score == pytest.approx(1.0)


class TestEvalWithReporting:
    """Full pipeline including report generation."""

    def test_json_report_generation(self, tmp_path: Path) -> None:
        task = TaskDefinition(
            id="report-1",
            name="report-task",
            dimension="test",
            expected="expected output",
        )
        (tmp_path / "task.toml").write_text(task.to_toml(), encoding="utf-8")

        runner = EvalRunner()
        loaded = runner.load_tasks(tmp_path)
        results = runner.run(loaded, _echo_executor, [ExactScorer()])

        reporter = JSONReporter()
        report_json = reporter.generate(results)
        report_data = json.loads(report_json)

        errors = reporter.validate_schema(report_data)
        assert errors == [], f"Schema errors: {errors}"
        assert report_data["summary"]["total"] == 1
        assert report_data["summary"]["passed"] == 1
        assert report_data["summary"]["pass_rate"] == 1.0

    def test_markdown_report_generation(self, tmp_path: Path) -> None:
        tasks = [
            TaskDefinition(id=f"md-{i}", name=f"md-task-{i}", expected=f"out-{i}") for i in range(3)
        ]
        for i, t in enumerate(tasks):
            (tmp_path / f"task_{i}.toml").write_text(t.to_toml(), encoding="utf-8")

        runner = EvalRunner()
        loaded = runner.load_tasks(tmp_path)
        results = runner.run(loaded, _echo_executor, [ExactScorer()])

        md_reporter = MarkdownReporter(title="E2E Test Report")
        markdown = md_reporter.generate(results)
        assert "# E2E Test Report" in markdown
        assert "| Total tasks | 3 |" in markdown
        assert "| Pass rate | 100.0% |" in markdown

    def test_mixed_success_failure_report(self, tmp_path: Path) -> None:
        task_pass = TaskDefinition(
            id="pass-1",
            name="passing-task",
            expected="hello",
        )
        task_fail = TaskDefinition(
            id="fail-1",
            name="failing-task",
            expected="world",
        )
        (tmp_path / "pass.toml").write_text(task_pass.to_toml(), encoding="utf-8")
        (tmp_path / "fail.toml").write_text(task_fail.to_toml(), encoding="utf-8")

        runner = EvalRunner()
        loaded = runner.load_tasks(tmp_path)

        def selective_executor(task: TaskDefinition) -> ExecutionResult:
            if "fail" in task.id:
                return ExecutionResult(task_id=task.id, output=None, success=False)
            return _echo_executor(task)

        results = runner.run(loaded, selective_executor, [ExactScorer()])

        reporter = JSONReporter()
        report = reporter.generate_dict(results)
        assert report["summary"]["total"] == 2
        assert report["summary"]["failed"] >= 1

        md = MarkdownReporter().generate(results)
        assert "## Failures" in md


class TestEvalWithMetrics:
    """Metrics collection through the full pipeline."""

    def test_metrics_collected_for_all_tasks(self, tmp_path: Path) -> None:
        collector = MetricCollector()
        runner = EvalRunner(metric_collector=collector)

        for i in range(3):
            task = TaskDefinition(
                id=f"metrics-{i}",
                name=f"m-task-{i}",
                expected=f"out-{i}",
            )
            (tmp_path / f"task_{i}.toml").write_text(task.to_toml(), encoding="utf-8")

        loaded = runner.load_tasks(tmp_path)
        runner.run(loaded, _echo_executor, [ExactScorer()])

        assert len(collector.all_metrics()) == 3
        summary = collector.summary()
        assert summary["task_count"] == 3
        assert summary["total_tokens"] == 30


class TestEvalWithCompositeScorer:
    """Composite scorer integration through the full pipeline."""

    def test_composite_weighted_scoring(self) -> None:
        task = TaskDefinition(
            id="comp-1",
            name="composite-test",
            expected="hello world",
        )
        runner = EvalRunner()
        composite = CompositeScorer(scorers=[(ExactScorer(), 0.6), (FuzzyScorer(), 0.4)])
        results = runner.run([task], _echo_executor, [composite])

        assert results[0].success is True
        assert results[0].composite_score == pytest.approx(1.0)
        assert "exact" in results[0].scores[0].breakdown
        assert "fuzzy" in results[0].scores[0].breakdown

    def test_rubric_scorer_integration(self) -> None:
        task = TaskDefinition(
            id="rubric-1",
            name="rubric-test",
            expected=None,
        )

        def rubric_executor(t: TaskDefinition) -> ExecutionResult:
            return ExecutionResult(
                task_id=t.id,
                output="hello world from nines",
                metrics={"token_count": 5},
                success=True,
            )

        rubric = RubricScorer(
            criteria=[
                RubricItem(name="has_hello", weight=2.0, check_fn="contains", check_value="hello"),
                RubricItem(name="has_nines", weight=1.0, check_fn="contains", check_value="nines"),
                RubricItem(
                    name="has_missing", weight=1.0, check_fn="contains", check_value="missing"
                ),
            ]
        )

        runner = EvalRunner()
        results = runner.run([task], rubric_executor, [rubric])
        assert results[0].success is True
        assert results[0].composite_score == pytest.approx(3.0 / 4.0)
