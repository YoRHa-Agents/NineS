"""Tests for nines.core.models — round-trip serialization and construction."""

from __future__ import annotations

import pytest

from nines.core.models import (
    AnalysisResult,
    CollectionResult,
    EvalTask,
    ExecutionResult,
    Finding,
    KnowledgeUnit,
    Score,
    ScoreCard,
)

# ---------------------------------------------------------------------------
# EvalTask
# ---------------------------------------------------------------------------


class TestEvalTask:
    def test_round_trip(self) -> None:
        task = EvalTask(
            id="task-1",
            name="hello",
            description="A test task",
            dimension="code_quality",
            input_data={"prompt": "write code"},
            expected="print('hi')",
            metadata={"difficulty": 3},
        )
        restored = EvalTask.from_dict(task.to_dict())
        assert restored.id == task.id
        assert restored.name == task.name
        assert restored.description == task.description
        assert restored.dimension == task.dimension
        assert restored.input_data == task.input_data
        assert restored.expected == task.expected
        assert restored.metadata == task.metadata

    def test_defaults(self) -> None:
        task = EvalTask(id="t")
        assert task.name == ""
        assert task.metadata == {}
        assert task.input_data is None

    def test_from_dict_minimal(self) -> None:
        task = EvalTask.from_dict({"id": "x"})
        assert task.id == "x"
        assert task.name == ""


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------


class TestExecutionResult:
    def test_round_trip(self) -> None:
        result = ExecutionResult(
            task_id="t1",
            output="hello",
            metrics={"tokens": 42},
            duration_ms=123.4,
            success=True,
        )
        restored = ExecutionResult.from_dict(result.to_dict())
        assert restored.task_id == result.task_id
        assert restored.output == result.output
        assert restored.metrics == result.metrics
        assert restored.duration_ms == pytest.approx(result.duration_ms)
        assert restored.success is True

    def test_defaults(self) -> None:
        result = ExecutionResult(task_id="t")
        assert result.success is True
        assert result.duration_ms == 0.0

    def test_failure(self) -> None:
        result = ExecutionResult(task_id="t", success=False)
        d = result.to_dict()
        assert d["success"] is False


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------


class TestScore:
    def test_round_trip(self) -> None:
        score = Score(
            value=0.85,
            max_value=1.0,
            breakdown={"accuracy": 0.9, "style": 0.8},
            scorer_name="composite",
        )
        restored = Score.from_dict(score.to_dict())
        assert restored.value == pytest.approx(0.85)
        assert restored.max_value == pytest.approx(1.0)
        assert restored.breakdown == score.breakdown
        assert restored.scorer_name == "composite"

    def test_defaults(self) -> None:
        score = Score(value=0.5)
        assert score.max_value == 1.0
        assert score.scorer_name == ""
        assert score.breakdown == {}


# ---------------------------------------------------------------------------
# ScoreCard
# ---------------------------------------------------------------------------


class TestScoreCard:
    def test_round_trip_with_nested_scores(self) -> None:
        card = ScoreCard(
            task_id="t1",
            scores=[
                Score(value=0.9, scorer_name="exact"),
                Score(value=0.7, scorer_name="fuzzy"),
            ],
            composite=0.8,
            reliability={"pass_at_1": 0.95},
        )
        restored = ScoreCard.from_dict(card.to_dict())
        assert restored.task_id == "t1"
        assert len(restored.scores) == 2
        assert restored.scores[0].scorer_name == "exact"
        assert restored.composite == pytest.approx(0.8)
        assert restored.reliability == {"pass_at_1": 0.95}

    def test_empty_scores(self) -> None:
        card = ScoreCard(task_id="t")
        assert card.scores == []
        assert card.composite == 0.0


# ---------------------------------------------------------------------------
# CollectionResult
# ---------------------------------------------------------------------------


class TestCollectionResult:
    def test_round_trip(self) -> None:
        cr = CollectionResult(
            source="github",
            identifier="owner/repo",
            data={"stars": 100},
            metadata={"api_version": "2022-11-28"},
        )
        restored = CollectionResult.from_dict(cr.to_dict())
        assert restored.source == "github"
        assert restored.identifier == "owner/repo"
        assert restored.data == {"stars": 100}
        assert restored.collected_at == cr.collected_at
        assert restored.metadata == cr.metadata

    def test_collected_at_auto_set(self) -> None:
        cr = CollectionResult(source="arxiv", identifier="1234.5678")
        assert cr.collected_at  # non-empty ISO timestamp


# ---------------------------------------------------------------------------
# AnalysisResult
# ---------------------------------------------------------------------------


class TestAnalysisResult:
    def test_round_trip_with_findings(self) -> None:
        finding = Finding(id="f1", severity="warning", message="high complexity")
        ar = AnalysisResult(
            target="/src/foo.py",
            findings=[finding],
            metrics={"cyclomatic_complexity": 12},
        )
        d = ar.to_dict()
        assert d["findings"][0]["id"] == "f1"

        restored = AnalysisResult.from_dict(d)
        assert restored.target == "/src/foo.py"
        assert len(restored.findings) == 1
        assert restored.findings[0].severity == "warning"
        assert restored.metrics == {"cyclomatic_complexity": 12}

    def test_empty(self) -> None:
        ar = AnalysisResult(target="/tmp")
        assert ar.findings == []
        assert ar.metrics == {}


# ---------------------------------------------------------------------------
# KnowledgeUnit
# ---------------------------------------------------------------------------


class TestKnowledgeUnit:
    def test_round_trip(self) -> None:
        ku = KnowledgeUnit(
            id="ku-1",
            source="src/nines/core/models.py",
            content="class EvalTask: ...",
            unit_type="class",
            relationships={"imports": ["typing"]},
            metadata={"complexity": 3},
        )
        restored = KnowledgeUnit.from_dict(ku.to_dict())
        assert restored.id == "ku-1"
        assert restored.unit_type == "class"
        assert restored.relationships == {"imports": ["typing"]}

    def test_defaults(self) -> None:
        ku = KnowledgeUnit(id="k")
        assert ku.content == ""
        assert ku.relationships == {}


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


class TestFinding:
    def test_round_trip(self) -> None:
        f = Finding(
            id="f-1",
            severity="error",
            category="complexity",
            message="Function too complex",
            location="src/foo.py:42",
            suggestion="Extract helper functions",
        )
        restored = Finding.from_dict(f.to_dict())
        assert restored.id == "f-1"
        assert restored.severity == "error"
        assert restored.category == "complexity"
        assert restored.location == "src/foo.py:42"
        assert restored.suggestion == "Extract helper functions"

    def test_defaults(self) -> None:
        f = Finding(id="f")
        assert f.severity == "info"
        assert f.suggestion == ""


# ---------------------------------------------------------------------------
# Edge case / boundary tests for all models
# ---------------------------------------------------------------------------


class TestEvalTaskEdgeCases:
    def test_complex_nested_input_data(self) -> None:
        task = EvalTask(
            id="nested",
            input_data={"list": [1, 2, {"deep": True}], "none_val": None},
            expected={"nested": {"a": [1, 2]}},
        )
        restored = EvalTask.from_dict(task.to_dict())
        assert restored.input_data["list"][2]["deep"] is True
        assert restored.expected["nested"]["a"] == [1, 2]

    def test_empty_string_fields(self) -> None:
        task = EvalTask(id="", name="", description="", dimension="")
        d = task.to_dict()
        assert d["id"] == ""
        restored = EvalTask.from_dict(d)
        assert restored.id == ""

    def test_metadata_isolation(self) -> None:
        meta = {"key": "value"}
        task = EvalTask(id="t", metadata=meta)
        meta["key"] = "changed"
        assert task.metadata["key"] == "changed"
        d = task.to_dict()
        d["metadata"]["key"] = "mutated"
        assert task.metadata["key"] == "changed"

    def test_from_dict_extra_keys_ignored(self) -> None:
        data = {"id": "t1", "unknown_field": "ignored", "name": "test"}
        task = EvalTask.from_dict(data)
        assert task.id == "t1"
        assert task.name == "test"

    def test_unicode_content(self) -> None:
        task = EvalTask(id="unicode", name="任务", description="描述", expected="结果")
        restored = EvalTask.from_dict(task.to_dict())
        assert restored.name == "任务"
        assert restored.expected == "结果"


class TestExecutionResultEdgeCases:
    def test_large_metrics(self) -> None:
        big_metrics = {f"metric_{i}": float(i) for i in range(100)}
        result = ExecutionResult(task_id="big", metrics=big_metrics)
        restored = ExecutionResult.from_dict(result.to_dict())
        assert len(restored.metrics) == 100

    def test_none_output_round_trip(self) -> None:
        result = ExecutionResult(task_id="t", output=None)
        restored = ExecutionResult.from_dict(result.to_dict())
        assert restored.output is None

    def test_complex_output(self) -> None:
        result = ExecutionResult(task_id="t", output={"code": "def f(): pass", "lines": 1})
        restored = ExecutionResult.from_dict(result.to_dict())
        assert restored.output["code"] == "def f(): pass"

    def test_from_dict_missing_optional_fields(self) -> None:
        result = ExecutionResult.from_dict({"task_id": "minimal"})
        assert result.output is None
        assert result.metrics == {}
        assert result.duration_ms == 0.0
        assert result.success is True


class TestScoreEdgeCases:
    def test_zero_score(self) -> None:
        s = Score(value=0.0)
        restored = Score.from_dict(s.to_dict())
        assert restored.value == 0.0

    def test_large_max_value(self) -> None:
        s = Score(value=50.0, max_value=100.0)
        restored = Score.from_dict(s.to_dict())
        assert restored.max_value == 100.0

    def test_breakdown_with_nested_data(self) -> None:
        s = Score(value=0.8, breakdown={"criteria": {"a": 0.9, "b": 0.7}})
        restored = Score.from_dict(s.to_dict())
        assert restored.breakdown["criteria"]["a"] == 0.9


class TestScoreCardEdgeCases:
    def test_many_scores(self) -> None:
        scores = [Score(value=i * 0.1, scorer_name=f"scorer_{i}") for i in range(10)]
        card = ScoreCard(task_id="multi", scores=scores, composite=0.45)
        restored = ScoreCard.from_dict(card.to_dict())
        assert len(restored.scores) == 10
        assert restored.scores[5].scorer_name == "scorer_5"

    def test_from_dict_missing_scores(self) -> None:
        card = ScoreCard.from_dict({"task_id": "t"})
        assert card.scores == []
        assert card.composite == 0.0

    def test_reliability_data(self) -> None:
        card = ScoreCard(
            task_id="t",
            reliability={"pass_at_1": 0.95, "pass_at_5": 0.99, "consistency": 0.92},
        )
        d = card.to_dict()
        assert d["reliability"]["pass_at_5"] == 0.99


class TestCollectionResultEdgeCases:
    def test_none_data(self) -> None:
        cr = CollectionResult(source="test", identifier="id-1", data=None)
        restored = CollectionResult.from_dict(cr.to_dict())
        assert restored.data is None

    def test_explicit_collected_at(self) -> None:
        cr = CollectionResult(
            source="test",
            identifier="id-1",
            collected_at="2024-01-01T00:00:00Z",
        )
        restored = CollectionResult.from_dict(cr.to_dict())
        assert restored.collected_at == "2024-01-01T00:00:00Z"

    def test_large_data_payload(self) -> None:
        big_data = {"items": [{"id": i, "val": f"item_{i}"} for i in range(50)]}
        cr = CollectionResult(source="github", identifier="repo/x", data=big_data)
        restored = CollectionResult.from_dict(cr.to_dict())
        assert len(restored.data["items"]) == 50


class TestAnalysisResultEdgeCases:
    def test_mixed_findings_types(self) -> None:
        findings = [
            Finding(id="f1", severity="warning"),
            Finding(id="f2", severity="error", message="critical issue"),
        ]
        ar = AnalysisResult(target="/src", findings=findings)
        d = ar.to_dict()
        assert len(d["findings"]) == 2
        restored = AnalysisResult.from_dict(d)
        assert restored.findings[1].message == "critical issue"

    def test_non_dict_findings_passthrough(self) -> None:
        ar = AnalysisResult(target="/src", findings=["raw_finding_string"])
        d = ar.to_dict()
        assert d["findings"] == ["raw_finding_string"]
        restored = AnalysisResult.from_dict(d)
        assert restored.findings == ["raw_finding_string"]

    def test_explicit_timestamp(self) -> None:
        ar = AnalysisResult(target="/src", timestamp="2024-06-15T12:00:00Z")
        d = ar.to_dict()
        assert d["timestamp"] == "2024-06-15T12:00:00Z"


class TestKnowledgeUnitEdgeCases:
    def test_complex_relationships(self) -> None:
        ku = KnowledgeUnit(
            id="ku",
            relationships={
                "calls": ["fn_a", "fn_b"],
                "imports": ["os", "sys"],
                "depends_on": ["ku-2"],
            },
        )
        restored = KnowledgeUnit.from_dict(ku.to_dict())
        assert "calls" in restored.relationships
        assert len(restored.relationships["imports"]) == 2

    def test_all_fields_populated(self) -> None:
        ku = KnowledgeUnit(
            id="ku-full",
            source="src/core/models.py",
            content="class Foo:\n    pass",
            unit_type="class",
            relationships={"parent": "module"},
            metadata={"lines": 2, "complexity": 1},
        )
        d = ku.to_dict()
        restored = KnowledgeUnit.from_dict(d)
        assert restored.content == "class Foo:\n    pass"
        assert restored.metadata["complexity"] == 1


class TestFindingEdgeCases:
    def test_all_severity_levels(self) -> None:
        for severity in ("info", "warning", "error", "critical"):
            f = Finding(id=f"f-{severity}", severity=severity)
            restored = Finding.from_dict(f.to_dict())
            assert restored.severity == severity

    def test_from_dict_minimal(self) -> None:
        f = Finding.from_dict({"id": "minimal"})
        assert f.severity == "info"
        assert f.category == ""
        assert f.message == ""
        assert f.location == ""
        assert f.suggestion == ""
