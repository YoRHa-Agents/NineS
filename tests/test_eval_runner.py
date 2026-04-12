"""Tests for the evaluation framework: runner pipeline, all 4 scorers,
metrics collection, TOML round-trip, and JSON serialization.
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from nines.core.models import EvalTask, ExecutionResult, Score
from nines.eval.metrics import MetricCollector, ReliabilityCalculator, TaskMetrics
from nines.eval.models import EvalResult, ScoringCriterion, TaskDefinition
from nines.eval.runner import EvalRunner
from nines.eval.scorers import (
    CompositeScorer,
    ExactScorer,
    FuzzyScorer,
    RubricItem,
    RubricScorer,
    ScorerRegistry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_task(
    task_id: str = "task-1",
    name: str = "test-task",
    expected: str = "hello world",
) -> TaskDefinition:
    return TaskDefinition(
        id=task_id,
        name=name,
        description="A test task",
        dimension="code_quality",
        input_config={"prompt": "Say hello"},
        expected=expected,
        scoring_criteria=[
            ScoringCriterion(name="accuracy", weight=1.0, scorer_type="exact"),
        ],
        metadata={"difficulty": 1},
    )


def _echo_executor(task: TaskDefinition) -> ExecutionResult:
    """Executor that echoes the expected output."""
    return ExecutionResult(
        task_id=task.id,
        output=task.expected,
        metrics={"token_count": 42},
        duration_ms=10.0,
        success=True,
    )


def _wrong_executor(task: TaskDefinition) -> ExecutionResult:
    """Executor that always returns wrong output."""
    return ExecutionResult(
        task_id=task.id,
        output="wrong answer",
        metrics={"token_count": 5},
        duration_ms=5.0,
        success=True,
    )


def _failing_executor(task: TaskDefinition) -> ExecutionResult:
    """Executor that reports failure."""
    return ExecutionResult(
        task_id=task.id,
        output=None,
        success=False,
    )


def _raising_executor(task: TaskDefinition) -> ExecutionResult:
    raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# TaskDefinition TOML round-trip
# ---------------------------------------------------------------------------


class TestTaskDefinitionToml:
    def test_round_trip_string_expected(self) -> None:
        task = _make_task(expected="hello world")
        toml_str = task.to_toml()
        restored = TaskDefinition.from_toml(toml_str)
        assert restored.id == task.id
        assert restored.name == task.name
        assert restored.description == task.description
        assert restored.dimension == task.dimension
        assert restored.expected == task.expected
        assert restored.metadata == task.metadata

    def test_round_trip_dict_expected(self) -> None:
        task = _make_task()
        task.expected = {"cyclomatic_complexity": 7, "num_branches": 6}
        toml_str = task.to_toml()
        restored = TaskDefinition.from_toml(toml_str)
        assert restored.expected == task.expected

    def test_round_trip_file(self, tmp_path: Path) -> None:
        task = _make_task()
        toml_file = tmp_path / "task.toml"
        toml_file.write_text(task.to_toml(), encoding="utf-8")
        restored = TaskDefinition.from_toml(toml_file)
        assert restored.id == task.id
        assert restored.name == task.name

    def test_round_trip_preserves_scoring_criteria(self) -> None:
        task = _make_task()
        task.scoring_criteria = [
            ScoringCriterion(name="exact", weight=0.6, scorer_type="exact"),
            ScoringCriterion(name="fuzzy", weight=0.4, scorer_type="fuzzy"),
        ]
        toml_str = task.to_toml()
        restored = TaskDefinition.from_toml(toml_str)
        assert len(restored.scoring_criteria) == 2
        assert restored.scoring_criteria[0].name == "exact"
        assert restored.scoring_criteria[1].weight == pytest.approx(0.4)

    def test_round_trip_none_expected(self) -> None:
        task = _make_task()
        task.expected = None
        toml_str = task.to_toml()
        restored = TaskDefinition.from_toml(toml_str)
        assert restored.expected is None

    def test_from_toml_invalid_path(self) -> None:
        with pytest.raises(Exception):
            TaskDefinition.from_toml(Path("/nonexistent/task.toml"))

    def test_to_core_task_and_back(self) -> None:
        task = _make_task()
        core = task.to_core_task()
        assert core.id == task.id
        assert core.name == task.name
        restored = TaskDefinition.from_core_task(core)
        assert restored.id == task.id


# ---------------------------------------------------------------------------
# ExactScorer
# ---------------------------------------------------------------------------


class TestExactScorer:
    def test_exact_match(self) -> None:
        scorer = ExactScorer()
        result = scorer.score("hello world", "hello world")
        assert result.value == 1.0
        assert result.scorer_name == "exact"

    def test_no_match(self) -> None:
        scorer = ExactScorer()
        result = scorer.score("hello", "world")
        assert result.value == 0.0

    def test_whitespace_stripping(self) -> None:
        scorer = ExactScorer()
        result = scorer.score("  hello  ", "hello")
        assert result.value == 1.0

    def test_none_expected(self) -> None:
        scorer = ExactScorer()
        result = scorer.score("hello", None)
        assert result.value == 0.0

    def test_name(self) -> None:
        assert ExactScorer().name() == "exact"


# ---------------------------------------------------------------------------
# FuzzyScorer
# ---------------------------------------------------------------------------


class TestFuzzyScorer:
    def test_identical_strings(self) -> None:
        scorer = FuzzyScorer()
        result = scorer.score("hello world", "hello world")
        assert result.value == pytest.approx(1.0)
        assert result.scorer_name == "fuzzy"

    def test_similar_strings(self) -> None:
        scorer = FuzzyScorer()
        result = scorer.score("hello world", "hello worl")
        assert 0.8 < result.value < 1.0

    def test_completely_different(self) -> None:
        scorer = FuzzyScorer()
        result = scorer.score("abc", "xyz")
        assert result.value < 0.5

    def test_none_expected(self) -> None:
        scorer = FuzzyScorer()
        result = scorer.score("hello", None)
        assert result.value == 0.0

    def test_name(self) -> None:
        assert FuzzyScorer().name() == "fuzzy"


# ---------------------------------------------------------------------------
# RubricScorer
# ---------------------------------------------------------------------------


class TestRubricScorer:
    def test_all_criteria_pass(self) -> None:
        criteria = [
            RubricItem(name="has_hello", weight=1.0, check_fn="contains", check_value="hello"),
            RubricItem(name="has_world", weight=1.0, check_fn="contains", check_value="world"),
        ]
        scorer = RubricScorer(criteria=criteria)
        result = scorer.score("hello world", None)
        assert result.value == pytest.approx(1.0)
        assert result.scorer_name == "rubric"

    def test_partial_criteria(self) -> None:
        criteria = [
            RubricItem(name="has_hello", weight=1.0, check_fn="contains", check_value="hello"),
            RubricItem(name="has_foo", weight=1.0, check_fn="contains", check_value="foo"),
        ]
        scorer = RubricScorer(criteria=criteria)
        result = scorer.score("hello world", None)
        assert result.value == pytest.approx(0.5)

    def test_no_criteria(self) -> None:
        scorer = RubricScorer(criteria=[])
        result = scorer.score("hello", None)
        assert result.value == 0.0

    def test_equals_check(self) -> None:
        criteria = [
            RubricItem(name="exact", weight=1.0, check_fn="equals", check_value="hello"),
        ]
        scorer = RubricScorer(criteria=criteria)
        assert scorer.score("hello", None).value == pytest.approx(1.0)
        assert scorer.score("hello world", None).value == pytest.approx(0.0)

    def test_starts_with_check(self) -> None:
        criteria = [
            RubricItem(name="prefix", weight=1.0, check_fn="starts_with", check_value="hel"),
        ]
        scorer = RubricScorer(criteria=criteria)
        assert scorer.score("hello", None).value == pytest.approx(1.0)

    def test_present_check(self) -> None:
        criteria = [
            RubricItem(name="non_empty", weight=1.0, check_fn="present", check_value=""),
        ]
        scorer = RubricScorer(criteria=criteria)
        assert scorer.score("something", None).value == pytest.approx(1.0)

    def test_weighted_criteria(self) -> None:
        criteria = [
            RubricItem(name="has_hello", weight=3.0, check_fn="contains", check_value="hello"),
            RubricItem(name="has_foo", weight=1.0, check_fn="contains", check_value="foo"),
        ]
        scorer = RubricScorer(criteria=criteria)
        result = scorer.score("hello world", None)
        assert result.value == pytest.approx(3.0 / 4.0)

    def test_name(self) -> None:
        assert RubricScorer().name() == "rubric"


# ---------------------------------------------------------------------------
# CompositeScorer
# ---------------------------------------------------------------------------


class TestCompositeScorer:
    def test_weighted_combination(self) -> None:
        exact = ExactScorer()
        fuzzy = FuzzyScorer()
        composite = CompositeScorer(scorers=[(exact, 0.6), (fuzzy, 0.4)])
        result = composite.score("hello world", "hello world")
        assert result.value == pytest.approx(1.0)
        assert result.scorer_name == "composite"

    def test_mixed_scores(self) -> None:
        exact = ExactScorer()
        fuzzy = FuzzyScorer()
        composite = CompositeScorer(scorers=[(exact, 0.5), (fuzzy, 0.5)])
        result = composite.score("hello worl", "hello world")
        assert result.value < 1.0
        assert result.value > 0.0
        exact_part = 0.0
        fuzzy_part = result.breakdown["fuzzy"]["value"]
        expected_composite = (exact_part * 0.5 + fuzzy_part * 0.5) / 1.0
        assert result.value == pytest.approx(expected_composite)

    def test_empty_scorers_raises(self) -> None:
        with pytest.raises(Exception):
            CompositeScorer(scorers=[])

    def test_breakdown_contains_sub_scores(self) -> None:
        exact = ExactScorer()
        fuzzy = FuzzyScorer()
        composite = CompositeScorer(scorers=[(exact, 0.5), (fuzzy, 0.5)])
        result = composite.score("hello", "hello")
        assert "exact" in result.breakdown
        assert "fuzzy" in result.breakdown

    def test_name(self) -> None:
        exact = ExactScorer()
        assert CompositeScorer(scorers=[(exact, 1.0)]).name() == "composite"


# ---------------------------------------------------------------------------
# ScorerRegistry
# ---------------------------------------------------------------------------


class TestScorerRegistry:
    def test_with_builtins(self) -> None:
        registry = ScorerRegistry.with_builtins()
        available = registry.list_available()
        assert "exact" in available
        assert "fuzzy" in available
        assert "rubric" in available
        assert "composite" in available

    def test_get_returns_instance(self) -> None:
        registry = ScorerRegistry.with_builtins()
        scorer = registry.get("exact")
        assert scorer.name() == "exact"

    def test_get_unknown_raises(self) -> None:
        registry = ScorerRegistry()
        with pytest.raises(Exception):
            registry.get("nonexistent")

    def test_duplicate_register_raises(self) -> None:
        registry = ScorerRegistry()
        registry.register("test", ExactScorer)
        with pytest.raises(Exception):
            registry.register("test", ExactScorer)


# ---------------------------------------------------------------------------
# EvalRunner — full pipeline
# ---------------------------------------------------------------------------


class TestEvalRunnerPipeline:
    def test_load_execute_score_pipeline(self, tmp_path: Path) -> None:
        task = _make_task()
        toml_file = tmp_path / "task.toml"
        toml_file.write_text(task.to_toml(), encoding="utf-8")

        runner = EvalRunner()
        loaded = runner.load_tasks(toml_file)
        assert len(loaded) == 1
        assert loaded[0].id == task.id

        results = runner.run(loaded, _echo_executor, [ExactScorer()])
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].composite_score == pytest.approx(1.0)

    def test_load_from_directory(self, tmp_path: Path) -> None:
        for i in range(3):
            task = _make_task(task_id=f"task-{i}", name=f"task-{i}")
            (tmp_path / f"task_{i}.toml").write_text(task.to_toml(), encoding="utf-8")

        runner = EvalRunner()
        loaded = runner.load_tasks(tmp_path)
        assert len(loaded) == 3

    def test_wrong_output_scores_zero(self) -> None:
        task = _make_task(expected="correct answer")
        runner = EvalRunner()
        results = runner.run([task], _wrong_executor, [ExactScorer()])
        assert results[0].success is True
        assert results[0].composite_score == pytest.approx(0.0)

    def test_failing_executor(self) -> None:
        task = _make_task()
        runner = EvalRunner()
        results = runner.run([task], _failing_executor, [ExactScorer()])
        assert results[0].success is False

    def test_raising_executor(self) -> None:
        task = _make_task()
        runner = EvalRunner()
        results = runner.run([task], _raising_executor, [ExactScorer()])
        assert results[0].success is False
        assert "boom" in (results[0].error or "")

    def test_validation_failure(self) -> None:
        task = TaskDefinition(id="", name="")
        runner = EvalRunner()
        results = runner.run([task], _echo_executor, [ExactScorer()])
        assert results[0].success is False
        assert "Validation failed" in (results[0].error or "")

    def test_run_single(self) -> None:
        task = _make_task()
        runner = EvalRunner()
        result = runner.run_single(task, _echo_executor, [ExactScorer()])
        assert result.success is True
        assert result.task_id == task.id

    def test_multiple_scorers(self) -> None:
        task = _make_task(expected="hello world")
        runner = EvalRunner()
        scorers = [ExactScorer(), FuzzyScorer()]
        results = runner.run([task], _echo_executor, scorers)
        assert len(results[0].scores) == 2
        assert results[0].scores[0].scorer_name == "exact"
        assert results[0].scores[1].scorer_name == "fuzzy"

    def test_load_nonexistent_path_raises(self) -> None:
        runner = EvalRunner()
        with pytest.raises(Exception):
            runner.load_tasks("/nonexistent/path")


# ---------------------------------------------------------------------------
# MetricCollector
# ---------------------------------------------------------------------------


class TestMetricCollector:
    def test_collect_and_retrieve(self) -> None:
        collector = MetricCollector()
        metrics = collector.collect(
            task_id="t1",
            duration_ms=100.0,
            token_count=50,
            scores=[Score(value=0.8, scorer_name="exact")],
        )
        assert metrics.task_id == "t1"
        assert metrics.duration_ms == 100.0
        assert metrics.token_count == 50
        assert metrics.score_values == [0.8]

    def test_get_returns_none_for_unknown(self) -> None:
        collector = MetricCollector()
        assert collector.get("unknown") is None

    def test_all_metrics(self) -> None:
        collector = MetricCollector()
        collector.collect(task_id="t1", duration_ms=100.0)
        collector.collect(task_id="t2", duration_ms=200.0)
        assert len(collector.all_metrics()) == 2

    def test_summary(self) -> None:
        collector = MetricCollector()
        collector.collect(task_id="t1", duration_ms=100.0, token_count=10)
        collector.collect(task_id="t2", duration_ms=200.0, token_count=20)
        summary = collector.summary()
        assert summary["task_count"] == 2
        assert summary["total_duration_ms"] == pytest.approx(300.0)
        assert summary["avg_duration_ms"] == pytest.approx(150.0)
        assert summary["total_tokens"] == 30

    def test_empty_summary(self) -> None:
        collector = MetricCollector()
        assert collector.summary() == {"task_count": 0}

    def test_runner_integration(self) -> None:
        collector = MetricCollector()
        runner = EvalRunner(metric_collector=collector)
        task = _make_task()
        runner.run([task], _echo_executor, [ExactScorer()])
        assert collector.get(task.id) is not None
        assert collector.get(task.id).token_count == 42

    def test_task_metrics_to_dict(self) -> None:
        m = TaskMetrics(task_id="t1", duration_ms=5.0, token_count=10)
        d = m.to_dict()
        assert d["task_id"] == "t1"
        assert d["duration_ms"] == 5.0


# ---------------------------------------------------------------------------
# ReliabilityCalculator
# ---------------------------------------------------------------------------


class TestReliabilityCalculator:
    def test_pass_at_k_all_correct(self) -> None:
        assert ReliabilityCalculator.pass_at_k(10, 10, 3) == pytest.approx(1.0)

    def test_pass_at_k_none_correct(self) -> None:
        assert ReliabilityCalculator.pass_at_k(10, 0, 3) == pytest.approx(0.0)

    def test_pass_at_k_partial(self) -> None:
        result = ReliabilityCalculator.pass_at_k(10, 5, 3)
        assert 0.0 < result < 1.0

    def test_pass_at_k_zero_n(self) -> None:
        assert ReliabilityCalculator.pass_at_k(0, 0, 1) == pytest.approx(0.0)

    def test_pass_at_k_zero_k(self) -> None:
        assert ReliabilityCalculator.pass_at_k(10, 5, 0) == pytest.approx(1.0)

    def test_pass_at_k_k_greater_than_n(self) -> None:
        assert math.isnan(ReliabilityCalculator.pass_at_k(3, 2, 5))

    def test_pass_power_k_all_correct(self) -> None:
        assert ReliabilityCalculator.pass_power_k(10, 10, 3) == pytest.approx(1.0)

    def test_pass_power_k_half_correct(self) -> None:
        assert ReliabilityCalculator.pass_power_k(10, 5, 3) == pytest.approx(0.125)

    def test_pass_power_k_zero_n(self) -> None:
        assert math.isnan(ReliabilityCalculator.pass_power_k(0, 0, 3))

    def test_consistency_identical_scores(self) -> None:
        assert ReliabilityCalculator.consistency_score([0.8, 0.8, 0.8]) == pytest.approx(1.0)

    def test_consistency_varied_scores(self) -> None:
        result = ReliabilityCalculator.consistency_score([0.5, 0.7, 0.9])
        assert 0.0 < result < 1.0

    def test_consistency_single_score(self) -> None:
        assert ReliabilityCalculator.consistency_score([0.5]) == pytest.approx(1.0)

    def test_consistency_empty(self) -> None:
        assert math.isnan(ReliabilityCalculator.consistency_score([]))


# ---------------------------------------------------------------------------
# EvalResult JSON serialization
# ---------------------------------------------------------------------------


class TestEvalResultSerialization:
    def test_to_dict(self) -> None:
        result = EvalResult(
            task_id="t1",
            task_name="test",
            output="hello",
            scores=[Score(value=1.0, scorer_name="exact")],
            composite_score=1.0,
            duration_ms=10.0,
            token_count=5,
            success=True,
        )
        d = result.to_dict()
        assert d["task_id"] == "t1"
        assert d["composite_score"] == 1.0
        assert len(d["scores"]) == 1

    def test_to_json(self) -> None:
        result = EvalResult(
            task_id="t1",
            task_name="test",
            output="hello",
            scores=[Score(value=1.0, scorer_name="exact")],
            composite_score=1.0,
        )
        j = result.to_json()
        parsed = json.loads(j)
        assert parsed["task_id"] == "t1"

    def test_from_dict(self) -> None:
        data = {
            "task_id": "t1",
            "task_name": "test",
            "output": "hello",
            "scores": [{"value": 1.0, "scorer_name": "exact"}],
            "composite_score": 1.0,
            "success": True,
        }
        result = EvalResult.from_dict(data)
        assert result.task_id == "t1"
        assert len(result.scores) == 1
        assert result.scores[0].value == 1.0

    def test_json_round_trip(self) -> None:
        original = EvalResult(
            task_id="t1",
            task_name="test",
            output={"key": "value"},
            scores=[
                Score(value=0.9, scorer_name="fuzzy"),
                Score(value=1.0, scorer_name="exact"),
            ],
            composite_score=0.95,
            duration_ms=42.0,
            token_count=100,
            success=True,
        )
        j = original.to_json()
        restored = EvalResult.from_dict(json.loads(j))
        assert restored.task_id == original.task_id
        assert restored.composite_score == pytest.approx(original.composite_score)
        assert len(restored.scores) == len(original.scores)


# ---------------------------------------------------------------------------
# Additional scorer edge-case tests
# ---------------------------------------------------------------------------


class TestScorerEdgeCases:
    def test_exact_scorer_numeric_types(self) -> None:
        scorer = ExactScorer()
        assert scorer.score(42, 42).value == 1.0
        assert scorer.score(42, "42").value == 1.0

    def test_fuzzy_scorer_empty_strings(self) -> None:
        scorer = FuzzyScorer()
        result = scorer.score("", "")
        assert result.value == pytest.approx(1.0)

    def test_fuzzy_scorer_with_threshold(self) -> None:
        scorer = FuzzyScorer(threshold=0.9)
        result = scorer.score("hello", "hello")
        assert result.breakdown["above_threshold"] is True

    def test_rubric_unknown_check_fn(self) -> None:
        criteria = [RubricItem(name="unknown", weight=1.0, check_fn="regex", check_value=".*")]
        scorer = RubricScorer(criteria=criteria)
        result = scorer.score("anything", None)
        assert result.value == 0.0

    def test_rubric_zero_weight_criteria(self) -> None:
        criteria = [RubricItem(name="zero", weight=0.0, check_fn="contains", check_value="x")]
        scorer = RubricScorer(criteria=criteria)
        result = scorer.score("x", None)
        assert result.value == 0.0

    def test_composite_single_scorer(self) -> None:
        exact = ExactScorer()
        comp = CompositeScorer(scorers=[(exact, 1.0)])
        result = comp.score("hello", "hello")
        assert result.value == pytest.approx(1.0)

    def test_composite_zero_weight(self) -> None:
        exact = ExactScorer()
        comp = CompositeScorer(scorers=[(exact, 0.0)])
        result = comp.score("hello", "hello")
        assert result.value == 0.0


class TestEvalRunnerEdgeCases:
    def test_run_empty_task_list(self) -> None:
        runner = EvalRunner()
        results = runner.run([], _echo_executor, [ExactScorer()])
        assert results == []

    def test_run_no_scorers(self) -> None:
        task = _make_task()
        runner = EvalRunner()
        results = runner.run([task], _echo_executor, [])
        assert results[0].success is True
        assert results[0].composite_score == 0.0
        assert results[0].scores == []

    def test_run_multiple_tasks_batch(self) -> None:
        tasks = [_make_task(task_id=f"t-{i}", name=f"task-{i}") for i in range(5)]
        runner = EvalRunner()
        results = runner.run(tasks, _echo_executor, [ExactScorer()])
        assert len(results) == 5
        assert all(r.success for r in results)

    def test_scorer_exception_handled(self) -> None:
        class FailingScorer:
            def name(self) -> str:
                return "failing"

            def score(self, output, expected) -> Score:
                raise ValueError("scorer crash")

        task = _make_task()
        runner = EvalRunner()
        results = runner.run([task], _echo_executor, [FailingScorer()])
        assert results[0].success is True
        assert results[0].scores[0].value == 0.0
        assert "error" in results[0].scores[0].breakdown

    def test_metric_collector_summary_with_scores(self) -> None:
        collector = MetricCollector()
        collector.collect(
            task_id="t1",
            duration_ms=50.0,
            token_count=10,
            scores=[Score(value=0.9), Score(value=0.8)],
        )
        m = collector.get("t1")
        assert m.score_values == [0.9, 0.8]


class TestTaskDefinitionEdgeCases:
    def test_scoring_criterion_round_trip(self) -> None:
        sc = ScoringCriterion(
            name="test", weight=0.5, description="A test", scorer_type="fuzzy",
            params={"threshold": 0.8},
        )
        restored = ScoringCriterion.from_dict(sc.to_dict())
        assert restored.name == "test"
        assert restored.params == {"threshold": 0.8}

    def test_task_definition_to_dict(self) -> None:
        task = _make_task()
        d = task.to_dict()
        assert d["id"] == "task-1"
        assert d["name"] == "test-task"
        assert "scoring_criteria" in d

    def test_task_definition_from_dict(self) -> None:
        data = {
            "id": "td-1",
            "name": "from-dict",
            "description": "test",
            "dimension": "quality",
            "input_config": {"prompt": "hi"},
            "expected": "hello",
            "metadata": {"v": 1},
        }
        td = TaskDefinition.from_dict(data)
        assert td.id == "td-1"
        assert td.scoring_criteria == []

    def test_task_definition_none_expected_toml(self) -> None:
        task = _make_task()
        task.expected = None
        d = task.to_dict()
        assert "expected" not in d

    def test_from_core_task_non_dict_input(self) -> None:
        core = EvalTask(id="t", input_data="string_input")
        td = TaskDefinition.from_core_task(core)
        assert td.input_config == {}
