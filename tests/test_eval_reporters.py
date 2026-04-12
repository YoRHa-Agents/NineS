"""Tests for eval reporters, analysis, and matrix evaluation."""

from __future__ import annotations

import json

import pytest

from nines.core.models import Score
from nines.eval.analysis import AxisAnalyzer, DimensionStats
from nines.eval.matrix import MatrixCell, MatrixEvaluator, MatrixResult
from nines.eval.models import EvalResult
from nines.eval.reporters import JSONReporter, MarkdownReporter, REPORT_JSON_SCHEMA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_results() -> list[EvalResult]:
    return [
        EvalResult(
            task_id="code-quality-1",
            task_name="Code Quality Test 1",
            output="result1",
            scores=[Score(value=0.9, scorer_name="exact")],
            composite_score=0.9,
            duration_ms=120.5,
            token_count=100,
            success=True,
        ),
        EvalResult(
            task_id="code-quality-2",
            task_name="Code Quality Test 2",
            output="result2",
            scores=[Score(value=0.7, scorer_name="fuzzy")],
            composite_score=0.7,
            duration_ms=80.0,
            token_count=50,
            success=True,
        ),
        EvalResult(
            task_id="reasoning-1",
            task_name="Reasoning Test 1",
            output=None,
            scores=[],
            composite_score=0.0,
            duration_ms=200.0,
            token_count=0,
            success=False,
            error="Execution timeout",
        ),
    ]


# ---------------------------------------------------------------------------
# MarkdownReporter
# ---------------------------------------------------------------------------

class TestMarkdownReporter:
    def test_generate_contains_title(self) -> None:
        reporter = MarkdownReporter(title="My Benchmark")
        md = reporter.generate(_make_results())
        assert "# My Benchmark" in md

    def test_generate_contains_summary_table(self) -> None:
        md = MarkdownReporter().generate(_make_results())
        assert "## Summary" in md
        assert "Total tasks" in md
        assert "| 3 |" in md

    def test_generate_contains_results_table(self) -> None:
        md = MarkdownReporter().generate(_make_results())
        assert "## Results" in md
        assert "code-quality-1" in md
        assert "PASS" in md
        assert "FAIL" in md

    def test_generate_contains_failures_section(self) -> None:
        md = MarkdownReporter().generate(_make_results())
        assert "## Failures" in md
        assert "Execution timeout" in md

    def test_generate_empty_results(self) -> None:
        md = MarkdownReporter().generate([])
        assert "# Benchmark Report" in md
        assert "| 0 |" in md

    def test_generate_all_passing(self) -> None:
        results = [r for r in _make_results() if r.success]
        md = MarkdownReporter().generate(results)
        assert "## Failures" not in md

    def test_pass_rate_format(self) -> None:
        md = MarkdownReporter().generate(_make_results())
        assert "66.7%" in md

    def test_avg_score_present(self) -> None:
        md = MarkdownReporter().generate(_make_results())
        assert "Avg score" in md


# ---------------------------------------------------------------------------
# JSONReporter
# ---------------------------------------------------------------------------

class TestJSONReporter:
    def test_generate_valid_json(self) -> None:
        reporter = JSONReporter()
        output = reporter.generate(_make_results())
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_generate_schema_keys(self) -> None:
        data = JSONReporter().generate_dict(_make_results())
        for key in REPORT_JSON_SCHEMA["required"]:
            assert key in data, f"Missing key: {key}"

    def test_summary_fields(self) -> None:
        data = JSONReporter().generate_dict(_make_results())
        summary = data["summary"]
        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert 0.0 <= summary["pass_rate"] <= 1.0

    def test_results_list_length(self) -> None:
        data = JSONReporter().generate_dict(_make_results())
        assert len(data["results"]) == 3

    def test_version_present(self) -> None:
        data = JSONReporter().generate_dict(_make_results())
        assert data["version"] == "1.0"

    def test_validate_schema_valid(self) -> None:
        data = JSONReporter().generate_dict(_make_results())
        errors = JSONReporter.validate_schema(data)
        assert errors == []

    def test_validate_schema_missing_keys(self) -> None:
        errors = JSONReporter.validate_schema({})
        assert len(errors) > 0
        assert any("Missing required key" in e for e in errors)

    def test_generate_empty_results(self) -> None:
        data = JSONReporter().generate_dict([])
        assert data["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# AxisAnalyzer
# ---------------------------------------------------------------------------

class TestAxisAnalyzer:
    def test_group_by_dimension(self) -> None:
        results = _make_results()
        dim_map = {
            "code-quality-1": "code_quality",
            "code-quality-2": "code_quality",
            "reasoning-1": "reasoning",
        }
        analyzer = AxisAnalyzer()
        groups = analyzer.group_by(results, dim_map)
        assert "code_quality" in groups
        assert "reasoning" in groups
        assert len(groups["code_quality"]) == 2

    def test_compute_stats(self) -> None:
        results = [
            EvalResult(task_id="t1", composite_score=0.8, success=True),
            EvalResult(task_id="t2", composite_score=0.6, success=True),
            EvalResult(task_id="t3", composite_score=0.4, success=True),
        ]
        analyzer = AxisAnalyzer(pass_threshold=0.5)
        stats = analyzer.compute_stats(results)
        assert stats.count == 3
        assert abs(stats.mean - 0.6) < 1e-9
        assert stats.min == pytest.approx(0.4)
        assert stats.max == pytest.approx(0.8)
        assert stats.pass_rate == pytest.approx(2 / 3)

    def test_compute_stats_empty(self) -> None:
        stats = AxisAnalyzer().compute_stats([])
        assert stats.count == 0

    def test_analyze_full(self) -> None:
        results = _make_results()
        dim_map = {
            "code-quality-1": "cq",
            "code-quality-2": "cq",
            "reasoning-1": "reason",
        }
        analyzer = AxisAnalyzer()
        all_stats = analyzer.analyze(results, dim_map)
        assert "cq" in all_stats
        assert "reason" in all_stats
        assert all_stats["cq"].count == 2

    def test_dimension_stats_to_dict(self) -> None:
        ds = DimensionStats(dimension="test", count=5, mean=0.8)
        d = ds.to_dict()
        assert d["dimension"] == "test"
        assert d["count"] == 5


# ---------------------------------------------------------------------------
# MatrixEvaluator
# ---------------------------------------------------------------------------

class TestMatrixEvaluator:
    def test_generate_cells_cartesian(self) -> None:
        me = MatrixEvaluator()
        me.add_axis("model", ["gpt4", "claude"])
        me.add_axis("difficulty", ["easy", "hard"])
        cells = me.generate_cells()
        assert len(cells) == 4

    def test_generate_cells_empty_axes(self) -> None:
        me = MatrixEvaluator()
        assert me.generate_cells() == []

    def test_total_cells(self) -> None:
        me = MatrixEvaluator()
        me.add_axis("a", ["1", "2", "3"])
        me.add_axis("b", ["x", "y"])
        assert me.total_cells() == 6

    def test_exclusion_rules(self) -> None:
        me = MatrixEvaluator()
        me.add_axis("model", ["gpt4", "claude"])
        me.add_axis("difficulty", ["easy", "hard"])

        def no_claude_hard(coords: dict[str, str]) -> bool:
            return coords.get("model") == "claude" and coords.get("difficulty") == "hard"

        me.add_exclusion_rule(no_claude_hard)

        def evaluator(cell: MatrixCell) -> EvalResult:
            return EvalResult(task_id=cell.key, success=True, composite_score=1.0)

        results = me.run(evaluator)
        assert len(results) == 4
        skipped = [r for r in results if r.skipped]
        assert len(skipped) == 1
        assert "claude" in skipped[0].cell.key

    def test_run_all_evaluated(self) -> None:
        me = MatrixEvaluator()
        me.add_axis("x", ["a", "b"])
        call_count = 0

        def evaluator(cell: MatrixCell) -> EvalResult:
            nonlocal call_count
            call_count += 1
            return EvalResult(task_id=cell.key, success=True, composite_score=0.5)

        results = me.run(evaluator)
        assert call_count == 2
        assert all(not r.skipped for r in results)

    def test_run_handles_evaluator_exception(self) -> None:
        me = MatrixEvaluator()
        me.add_axis("x", ["a"])

        def bad_evaluator(cell: MatrixCell) -> EvalResult:
            raise RuntimeError("boom")

        results = me.run(bad_evaluator)
        assert len(results) == 1
        assert results[0].eval_result is not None
        assert not results[0].eval_result.success

    def test_cell_key(self) -> None:
        cell = MatrixCell(coordinates={"b": "2", "a": "1"})
        assert cell.key == "a=1|b=2"

    def test_three_axis_matrix(self) -> None:
        me = MatrixEvaluator()
        me.add_axis("a", ["1", "2"])
        me.add_axis("b", ["x"])
        me.add_axis("c", ["p", "q"])
        cells = me.generate_cells()
        assert len(cells) == 4
