"""Integration tests for the full benchmark workflow pipeline.

Tests the complete flow: KeyPoints → BenchmarkSuite → MultiRoundRunner → MappingTable.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from nines.analyzer.keypoint import KeyPoint
from nines.core.models import ExecutionResult
from nines.eval.benchmark_gen import BenchmarkGenerator
from nines.eval.mapping import MappingTableGenerator
from nines.eval.multi_round import MultiRoundRunner
from nines.eval.scorers import ExactScorer

if TYPE_CHECKING:
    from pathlib import Path

    from nines.eval.models import TaskDefinition


def _make_kp(
    kp_id: str,
    category: str = "compression",
    priority: int = 1,
    **kw: Any,
) -> KeyPoint:
    return KeyPoint(
        id=kp_id,
        category=category,
        title=kw.get("title", f"Test KP {kp_id}"),
        description=kw.get("description", f"Description for {kp_id}"),
        mechanism_ids=kw.get("mechanism_ids", []),
        expected_impact=kw.get("expected_impact", "positive"),
        impact_magnitude=kw.get("impact_magnitude", 0.7),
        validation_approach=kw.get("validation_approach", "benchmark test"),
        evidence=kw.get("evidence", []),
        priority=priority,
        metadata=kw.get("metadata", {}),
    )


def _passthrough_executor(task: TaskDefinition) -> ExecutionResult:
    return ExecutionResult(task_id=task.id, output=task.expected, success=True)


class TestBenchmarkWorkflowE2E:
    """End-to-end benchmark workflow integration tests."""

    def test_full_pipeline_keypoints_to_mapping(self, tmp_path: Path) -> None:
        kps = [
            _make_kp("kp-01", "compression", title="Token compression"),
            _make_kp("kp-02", "behavioral_shaping", title="Style enforcement"),
            _make_kp("kp-03", "context_management", title="Context overhead"),
        ]

        suite = BenchmarkGenerator().generate(kps, suite_id="full-e2e")
        assert len(suite.tasks) >= 3, "Should generate at least one task per key point"

        runner = MultiRoundRunner(min_rounds=3, max_rounds=5, convergence_threshold=0.05)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)
        assert report.total_rounds >= 3

        mapping = MappingTableGenerator().generate(kps, report, suite)
        assert len(mapping.conclusions) == 3, "One conclusion per key point"
        assert mapping.effective_count + mapping.ineffective_count + mapping.inconclusive_count == 3

    def test_benchmark_suite_toml_roundtrip(self, tmp_path: Path) -> None:
        kps = [_make_kp("kp-rt", "compression", title="Roundtrip test")]
        suite = BenchmarkGenerator().generate(kps, suite_id="rt-test")

        suite.to_toml_dir(tmp_path / "suite")
        toml_files = list((tmp_path / "suite").glob("*.toml"))
        assert len(toml_files) >= 1, "Should write at least one TOML file"

        for tf in toml_files:
            content = tf.read_text(encoding="utf-8")
            assert "[task]" in content or "[suite]" in content.lower() or "id" in content

    def test_multi_round_convergence_deterministic(self) -> None:
        kps = [_make_kp("kp-cv", "compression")]
        suite = BenchmarkGenerator().generate(kps, suite_id="cv-test")

        runner = MultiRoundRunner(min_rounds=3, max_rounds=10, convergence_threshold=0.05)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)

        assert report.converged, "Deterministic executor should converge"
        assert report.std_composite < 0.05

    def test_mapping_effectiveness_classification(self) -> None:
        kps = [
            _make_kp("kp-e1", "compression", expected_impact="positive"),
            _make_kp("kp-e2", "engineering", expected_impact="neutral", priority=4),
        ]
        suite = BenchmarkGenerator().generate(kps, suite_id="eff-test")
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)

        mapping = MappingTableGenerator(effectiveness_threshold=0.7).generate(kps, report, suite)
        for c in mapping.conclusions:
            assert c.observed_effectiveness in (
                "effective",
                "partially_effective",
                "ineffective",
                "inconclusive",
            )

    def test_mapping_lessons_extraction(self) -> None:
        kps = [
            _make_kp("kp-l1", "compression", title="Compression A"),
            _make_kp("kp-l2", "compression", title="Compression B"),
            _make_kp("kp-l3", "behavioral_shaping", title="Style rule"),
        ]
        suite = BenchmarkGenerator().generate(kps, suite_id="lesson-test")
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)

        mapping = MappingTableGenerator().generate(kps, report, suite)
        assert isinstance(mapping.lessons_learnt, list)

    def test_empty_keypoints_workflow(self) -> None:
        suite = BenchmarkGenerator().generate([], suite_id="empty")
        assert len(suite.tasks) == 0

        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)
        assert report.total_rounds >= 3

        mapping = MappingTableGenerator().generate([], report, suite)
        assert len(mapping.conclusions) == 0
        assert mapping.overall_effectiveness == 0.0

    def test_single_keypoint_full_cycle(self) -> None:
        kps = [_make_kp("kp-single", "semantic_preservation", title="Meaning retention")]
        suite = BenchmarkGenerator().generate(kps, suite_id="single")
        assert len(suite.tasks) >= 1

        runner = MultiRoundRunner(min_rounds=3, max_rounds=5)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)

        mapping = MappingTableGenerator().generate(kps, report, suite)
        assert len(mapping.conclusions) == 1
        assert mapping.conclusions[0].keypoint_id == "kp-single"

    def test_mixed_category_keypoints(self) -> None:
        kps = [
            _make_kp("kp-m1", "compression"),
            _make_kp("kp-m2", "behavioral_shaping"),
            _make_kp("kp-m3", "cross_platform"),
            _make_kp("kp-m4", "semantic_preservation"),
            _make_kp("kp-m5", "engineering", priority=5),
        ]
        suite = BenchmarkGenerator().generate(kps, suite_id="mixed")
        assert len(suite.source_keypoints) == 5

        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)
        mapping = MappingTableGenerator().generate(kps, report, suite)
        assert len(mapping.conclusions) == 5

    def test_mapping_table_markdown_output(self) -> None:
        kps = [_make_kp("kp-md", "compression", title="Markdown test")]
        suite = BenchmarkGenerator().generate(kps, suite_id="md")
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)

        mapping = MappingTableGenerator().generate(kps, report, suite)
        md = mapping.to_markdown()
        assert "| Key Point" in md or "| key" in md.lower() or "|" in md
        assert "Markdown test" in md or "kp-md" in md

    def test_mapping_table_json_serialization(self) -> None:
        kps = [
            _make_kp("kp-j1", "compression"),
            _make_kp("kp-j2", "behavioral_shaping"),
        ]
        suite = BenchmarkGenerator().generate(kps, suite_id="json-test")
        runner = MultiRoundRunner(min_rounds=3, max_rounds=3)
        report = runner.run(suite.tasks, _passthrough_executor, [ExactScorer()], suite.id)

        mapping = MappingTableGenerator().generate(kps, report, suite)
        data = mapping.to_dict()
        roundtripped = json.loads(json.dumps(data, default=str))
        assert len(roundtripped["conclusions"]) == 2
        assert "effective_count" in roundtripped
        assert "lessons_learnt" in roundtripped
