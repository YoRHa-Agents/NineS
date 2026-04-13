"""Tests for benchmark_gen: suite generation, per-category tasks, serialization."""

from __future__ import annotations

import tempfile
import tomllib
from pathlib import Path

import pytest

from nines.analyzer.keypoint import KeyPoint
from nines.eval.benchmark_gen import BenchmarkGenerator, BenchmarkSuite
from nines.eval.models import ScoringCriterion, TaskDefinition

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _kp(
    kp_id: str = "kp-01",
    category: str = "compression",
    **overrides: object,
) -> KeyPoint:
    defaults: dict[str, object] = {
        "id": kp_id,
        "category": category,
        "title": "Test key point",
        "description": "A test description for benchmarking",
        "mechanism_ids": ["mech-1"],
        "expected_impact": "moderate",
        "impact_magnitude": 0.4,
        "validation_approach": "automated",
        "evidence": ["evidence-a"],
        "priority": 2,
        "metadata": {},
    }
    defaults.update(overrides)
    return KeyPoint(**defaults)  # type: ignore[arg-type]


_ALL_CATEGORIES = [
    "compression",
    "context_management",
    "behavioral_shaping",
    "cross_platform",
    "semantic_preservation",
    "engineering",
]


# ---------------------------------------------------------------------------
# BenchmarkSuite dataclass
# ---------------------------------------------------------------------------


class TestBenchmarkSuite:
    def test_to_dict_round_trip(self) -> None:
        task = TaskDefinition(
            id="t-1",
            name="task-1",
            description="desc",
            dimension="compression",
            input_config={"x": 1},
            expected={"value": 42},
            scoring_criteria=[
                ScoringCriterion(name="sc", weight=1.0, scorer_type="exact"),
            ],
            metadata={"k": "v"},
        )
        suite = BenchmarkSuite(
            id="s-1",
            name="suite",
            description="desc",
            tasks=[task],
            source_keypoints=["kp-01"],
            metadata={"gen": True},
        )
        data = suite.to_dict()
        restored = BenchmarkSuite.from_dict(data)

        assert restored.id == suite.id
        assert restored.name == suite.name
        assert restored.description == suite.description
        assert len(restored.tasks) == 1
        assert restored.tasks[0].id == "t-1"
        assert restored.source_keypoints == ["kp-01"]
        assert restored.metadata == {"gen": True}

    def test_from_dict_defaults(self) -> None:
        suite = BenchmarkSuite.from_dict({"id": "min"})
        assert suite.name == ""
        assert suite.tasks == []
        assert suite.source_keypoints == []

    def test_to_toml_dir_creates_files(self) -> None:
        gen = BenchmarkGenerator()
        suite = gen.generate([_kp()], suite_id="toml-test")

        with tempfile.TemporaryDirectory() as tmp:
            out = suite.to_toml_dir(tmp)
            manifest = out / "suite.toml"
            assert manifest.exists()

            raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
            assert raw["suite"]["id"] == "toml-test"
            assert raw["suite"]["task_count"] == len(suite.tasks)

            task_files = list(out.glob("bench-*.toml"))
            assert len(task_files) == len(suite.tasks)

            for tf in task_files:
                task_raw = tomllib.loads(tf.read_text(encoding="utf-8"))
                assert "task" in task_raw
                assert task_raw["task"]["id"] == tf.stem

    def test_to_toml_dir_creates_parent(self) -> None:
        gen = BenchmarkGenerator()
        suite = gen.generate([_kp()], suite_id="nested")

        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "deep" / "dir"
            suite.to_toml_dir(nested)
            assert nested.is_dir()
            assert (nested / "suite.toml").exists()


# ---------------------------------------------------------------------------
# BenchmarkGenerator.generate()
# ---------------------------------------------------------------------------


class TestBenchmarkGenerate:
    def test_generate_returns_suite(self) -> None:
        gen = BenchmarkGenerator()
        suite = gen.generate([_kp()], suite_id="g1")

        assert isinstance(suite, BenchmarkSuite)
        assert suite.id == "g1"
        assert len(suite.tasks) > 0
        assert suite.source_keypoints == ["kp-01"]

    def test_generate_auto_id(self) -> None:
        gen = BenchmarkGenerator()
        suite = gen.generate([_kp()])
        assert suite.id  # non-empty auto-generated ID

    def test_generate_multiple_keypoints(self) -> None:
        gen = BenchmarkGenerator()
        kps = [
            _kp("kp-a", "compression"),
            _kp("kp-b", "engineering"),
        ]
        suite = gen.generate(kps, suite_id="multi")

        assert suite.source_keypoints == ["kp-a", "kp-b"]
        assert len(suite.tasks) >= 2
        ids = [t.id for t in suite.tasks]
        assert any("kp-a" in tid for tid in ids)
        assert any("kp-b" in tid for tid in ids)

    def test_generate_empty_keypoints(self) -> None:
        gen = BenchmarkGenerator()
        suite = gen.generate([], suite_id="empty")

        assert suite.tasks == []
        assert suite.source_keypoints == []

    def test_task_id_format(self) -> None:
        gen = BenchmarkGenerator()
        suite = gen.generate([_kp("kp-x")], suite_id="fmt")

        for task in suite.tasks:
            assert task.id.startswith("bench-fmt-kp-x-")
            seq_part = task.id.split("-")[-1]
            assert len(seq_part) == 2
            assert seq_part.isdigit()


# ---------------------------------------------------------------------------
# generate_for_keypoint
# ---------------------------------------------------------------------------


class TestGenerateForKeypoint:
    def test_returns_list_of_task_definitions(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen.generate_for_keypoint(_kp(), suite_id="kpg")

        assert isinstance(tasks, list)
        assert all(isinstance(t, TaskDefinition) for t in tasks)

    def test_unknown_category_falls_back_to_engineering(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen.generate_for_keypoint(
            _kp(category="unknown_category"),
            suite_id="fb",
        )
        assert len(tasks) >= 1
        assert tasks[0].dimension == "engineering"

    def test_metadata_contains_source_info(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen.generate_for_keypoint(_kp("src-kp", "compression"), suite_id="m")

        for task in tasks:
            assert task.metadata["source_keypoint"] == "src-kp"
            assert task.metadata["category"] == "compression"


# ---------------------------------------------------------------------------
# Per-category task generators
# ---------------------------------------------------------------------------


class TestCompressionTasks:
    def test_produces_two_tasks(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._compression_tasks(_kp())
        assert len(tasks) == 2

    def test_first_task_shape(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._compression_tasks(_kp())
        t = tasks[0]

        assert "compression" in t.name.lower() or "length" in t.name.lower()
        assert t.dimension == "compression"
        assert "original_text" in t.input_config
        assert "max_ratio" in t.expected
        assert len(t.scoring_criteria) >= 1

    def test_second_task_uses_fuzzy(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._compression_tasks(_kp())
        t = tasks[1]

        assert "semantic" in t.name.lower() or "similarity" in t.name.lower()
        scorer_types = {c.scorer_type for c in t.scoring_criteria}
        assert "fuzzy" in scorer_types


class TestContextManagementTasks:
    def test_produces_one_task(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._context_management_tasks(_kp(category="context_management"))
        assert len(tasks) == 1

    def test_task_shape(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._context_management_tasks(_kp(category="context_management"))
        t = tasks[0]

        assert t.dimension == "context_management"
        assert "interaction_count" in t.input_config
        assert "max_overhead_tokens" in t.expected
        scorer_types = {c.scorer_type for c in t.scoring_criteria}
        assert "exact" in scorer_types


class TestBehavioralShapingTasks:
    def test_produces_one_task(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._behavioral_shaping_tasks(_kp(category="behavioral_shaping"))
        assert len(tasks) == 1

    def test_task_has_rubric_scorer(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._behavioral_shaping_tasks(_kp(category="behavioral_shaping"))
        t = tasks[0]

        assert t.dimension == "behavioral_shaping"
        scorer_types = {c.scorer_type for c in t.scoring_criteria}
        assert "rubric" in scorer_types


class TestCrossPlatformTasks:
    def test_produces_one_task(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._cross_platform_tasks(_kp(category="cross_platform"))
        assert len(tasks) == 1

    def test_task_uses_exact_scorer(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._cross_platform_tasks(_kp(category="cross_platform"))
        t = tasks[0]

        assert t.dimension == "cross_platform"
        scorer_types = {c.scorer_type for c in t.scoring_criteria}
        assert "exact" in scorer_types
        assert "platforms" in t.input_config


class TestSemanticPreservationTasks:
    def test_produces_one_task(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._semantic_preservation_tasks(
            _kp(category="semantic_preservation"),
        )
        assert len(tasks) == 1

    def test_task_uses_fuzzy_scorer(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._semantic_preservation_tasks(
            _kp(category="semantic_preservation"),
        )
        t = tasks[0]

        assert t.dimension == "semantic_preservation"
        scorer_types = {c.scorer_type for c in t.scoring_criteria}
        assert "fuzzy" in scorer_types


class TestEngineeringTasks:
    def test_produces_one_task(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._engineering_tasks(_kp(category="engineering"))
        assert len(tasks) == 1

    def test_task_uses_exact_scorer(self) -> None:
        gen = BenchmarkGenerator()
        tasks = gen._engineering_tasks(_kp(category="engineering"))
        t = tasks[0]

        assert t.dimension == "engineering"
        scorer_types = {c.scorer_type for c in t.scoring_criteria}
        assert "exact" in scorer_types
        assert "threshold" in t.scoring_criteria[0].params


# ---------------------------------------------------------------------------
# Scoring criteria validation
# ---------------------------------------------------------------------------


class TestScoringCriteria:
    @pytest.mark.parametrize("category", _ALL_CATEGORIES)
    def test_all_criteria_have_valid_scorer_type(self, category: str) -> None:
        gen = BenchmarkGenerator()
        tasks = gen.generate_for_keypoint(_kp(category=category), suite_id="sc")

        for task in tasks:
            for criterion in task.scoring_criteria:
                assert criterion.scorer_type in {"exact", "fuzzy", "rubric"}

    @pytest.mark.parametrize("category", _ALL_CATEGORIES)
    def test_all_criteria_have_positive_weight(self, category: str) -> None:
        gen = BenchmarkGenerator()
        tasks = gen.generate_for_keypoint(_kp(category=category), suite_id="w")

        for task in tasks:
            for criterion in task.scoring_criteria:
                assert criterion.weight > 0

    @pytest.mark.parametrize("category", _ALL_CATEGORIES)
    def test_all_tasks_have_at_least_one_criterion(self, category: str) -> None:
        gen = BenchmarkGenerator()
        tasks = gen.generate_for_keypoint(_kp(category=category), suite_id="c")

        for task in tasks:
            assert len(task.scoring_criteria) >= 1


# ---------------------------------------------------------------------------
# Integration: round-trip through TOML
# ---------------------------------------------------------------------------


class TestTomlRoundTrip:
    @pytest.mark.parametrize("category", _ALL_CATEGORIES)
    def test_generated_tasks_survive_toml_round_trip(self, category: str) -> None:
        gen = BenchmarkGenerator()
        suite = gen.generate([_kp(category=category)], suite_id="rt")

        with tempfile.TemporaryDirectory() as tmp:
            suite.to_toml_dir(tmp)
            for task in suite.tasks:
                path = Path(tmp) / f"{task.id}.toml"
                assert path.exists(), f"Missing TOML for {task.id}"

                restored = TaskDefinition.from_toml(path)
                assert restored.id == task.id
                assert restored.name == task.name
                assert restored.dimension == task.dimension
