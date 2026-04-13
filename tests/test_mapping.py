"""Tests for nines.eval.mapping — key-point → conclusion mapping."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from nines.eval.mapping import (
    KeyPointConclusion,
    MappingTable,
    MappingTableGenerator,
    _is_negative_expected,
)

# ---------------------------------------------------------------------------
# Mock objects for parallel modules not yet available
# ---------------------------------------------------------------------------


@dataclass
class _MockKeyPoint:
    id: str
    category: str
    title: str
    description: str = ""
    expected_impact: str = "positive improvement"
    impact_magnitude: str = "medium"
    priority: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    mechanism_ids: list[str] = field(default_factory=list)
    validation_approach: str = ""
    evidence: str = ""


@dataclass
class _MockTask:
    id: str
    name: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _MockBenchmarkSuite:
    id: str
    name: str
    tasks: list[_MockTask] = field(default_factory=list)
    source_keypoints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _MockMultiRoundReport:
    suite_id: str
    converged: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    _task_summary: dict[str, dict[str, float]] = field(
        default_factory=dict,
    )

    def per_task_summary(self) -> dict[str, dict[str, float]]:
        return dict(self._task_summary)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_conclusion(**overrides: Any) -> KeyPointConclusion:
    defaults: dict[str, Any] = {
        "keypoint_id": "kp-1",
        "keypoint_title": "Caching",
        "category": "performance",
        "expected_impact": "positive improvement",
        "observed_effectiveness": "effective",
        "confidence": 0.9,
        "mean_score": 0.85,
        "score_std": 0.05,
        "task_count": 3,
        "evidence_summary": "Evaluated across 3 task(s).",
        "recommendation": "Validated: adopt 'Caching'",
        "metadata": {},
    }
    defaults.update(overrides)
    return KeyPointConclusion(**defaults)


def _make_suite_and_report(
    suite_id: str = "s1",
    kp_ids: list[str] | None = None,
    converged: bool = True,
) -> tuple[_MockBenchmarkSuite, _MockMultiRoundReport]:
    """Build a suite + report with tasks for each key-point ID."""
    kp_ids = kp_ids or ["kp-1"]
    tasks: list[_MockTask] = []
    task_summary: dict[str, dict[str, float]] = {}

    for kp_id in kp_ids:
        for seq in range(1, 4):
            tid = f"bench-{suite_id}-{kp_id}-{seq:02d}"
            tasks.append(_MockTask(id=tid, name=f"task-{seq}"))
            task_summary[tid] = {
                "mean": 0.80 + seq * 0.02,
                "std": 0.05,
                "min": 0.70,
                "max": 0.95,
            }

    suite = _MockBenchmarkSuite(
        id=suite_id,
        name="Test Suite",
        tasks=tasks,
        source_keypoints=kp_ids,
    )
    report = _MockMultiRoundReport(
        suite_id=suite_id,
        converged=converged,
        _task_summary=task_summary,
    )
    return suite, report


# ---------------------------------------------------------------------------
# KeyPointConclusion tests
# ---------------------------------------------------------------------------


class TestKeyPointConclusion:
    def test_to_dict_roundtrip(self) -> None:
        original = _make_conclusion()
        data = original.to_dict()
        restored = KeyPointConclusion.from_dict(data)

        assert restored.keypoint_id == original.keypoint_id
        assert restored.keypoint_title == original.keypoint_title
        assert restored.category == original.category
        assert restored.observed_effectiveness == "effective"
        assert restored.confidence == pytest.approx(0.9)
        assert restored.mean_score == pytest.approx(0.85)
        assert restored.metadata == original.metadata

    def test_from_dict_missing_metadata_defaults(self) -> None:
        data = _make_conclusion().to_dict()
        del data["metadata"]
        restored = KeyPointConclusion.from_dict(data)
        assert restored.metadata == {}

    def test_to_dict_contains_all_fields(self) -> None:
        c = _make_conclusion()
        d = c.to_dict()
        expected_keys = {
            "keypoint_id",
            "keypoint_title",
            "category",
            "expected_impact",
            "observed_effectiveness",
            "confidence",
            "mean_score",
            "score_std",
            "task_count",
            "evidence_summary",
            "recommendation",
            "metadata",
        }
        assert set(d.keys()) == expected_keys


# ---------------------------------------------------------------------------
# MappingTable tests
# ---------------------------------------------------------------------------


class TestMappingTable:
    def test_to_dict_roundtrip(self) -> None:
        table = MappingTable(
            target="repo-x",
            conclusions=[_make_conclusion()],
            effective_count=1,
            ineffective_count=0,
            inconclusive_count=0,
            overall_effectiveness=1.0,
            lessons_learnt=["lesson-1"],
            metadata={"suite_id": "s1"},
        )
        data = table.to_dict()
        restored = MappingTable.from_dict(data)

        assert restored.target == "repo-x"
        assert len(restored.conclusions) == 1
        assert restored.effective_count == 1
        assert restored.overall_effectiveness == pytest.approx(1.0)
        assert restored.lessons_learnt == ["lesson-1"]

    def test_to_json_valid(self) -> None:
        table = MappingTable(
            target="repo-x",
            conclusions=[_make_conclusion()],
        )
        raw = table.to_json()
        parsed = json.loads(raw)
        assert parsed["target"] == "repo-x"
        assert len(parsed["conclusions"]) == 1

    def test_to_markdown_header(self) -> None:
        table = MappingTable(
            target="repo-x",
            conclusions=[_make_conclusion()],
        )
        md = table.to_markdown()
        lines = md.strip().split("\n")
        assert lines[0].startswith("| Key Point")
        assert lines[1].startswith("|---")
        assert len(lines) == 3
        assert "Caching" in lines[2]
        assert "0.85" in lines[2]

    def test_to_markdown_empty(self) -> None:
        table = MappingTable(target="repo-x")
        md = table.to_markdown()
        lines = md.strip().split("\n")
        assert len(lines) == 2

    def test_get_effective(self) -> None:
        c1 = _make_conclusion(
            keypoint_id="kp-1",
            observed_effectiveness="effective",
        )
        c2 = _make_conclusion(
            keypoint_id="kp-2",
            observed_effectiveness="ineffective",
        )
        c3 = _make_conclusion(
            keypoint_id="kp-3",
            observed_effectiveness="effective",
        )
        table = MappingTable(
            target="t",
            conclusions=[c1, c2, c3],
        )
        eff = table.get_effective()
        assert len(eff) == 2
        assert {c.keypoint_id for c in eff} == {"kp-1", "kp-3"}

    def test_get_by_category(self) -> None:
        c1 = _make_conclusion(
            keypoint_id="kp-1",
            category="perf",
        )
        c2 = _make_conclusion(
            keypoint_id="kp-2",
            category="security",
        )
        c3 = _make_conclusion(
            keypoint_id="kp-3",
            category="perf",
        )
        table = MappingTable(
            target="t",
            conclusions=[c1, c2, c3],
        )
        perf = table.get_by_category("perf")
        assert len(perf) == 2
        sec = table.get_by_category("security")
        assert len(sec) == 1
        assert table.get_by_category("missing") == []


# ---------------------------------------------------------------------------
# _is_negative_expected helper
# ---------------------------------------------------------------------------


class TestIsNegativeExpected:
    @pytest.mark.parametrize(
        "text",
        [
            "negative impact on latency",
            "degrades throughput",
            "may decrease reliability",
            "makes it worse",
            "could harm stability",
            "will reduce performance",
            "slows down processing",
        ],
    )
    def test_negative_indicators(self, text: str) -> None:
        assert _is_negative_expected(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "positive improvement",
            "enhances throughput",
            "increases reliability",
            "better performance",
            "",
        ],
    )
    def test_non_negative(self, text: str) -> None:
        assert _is_negative_expected(text) is False


# ---------------------------------------------------------------------------
# MappingTableGenerator — unit tests for private helpers
# ---------------------------------------------------------------------------


class TestDetermineEffectiveness:
    def setup_method(self) -> None:
        self.gen = MappingTableGenerator(
            effectiveness_threshold=0.7,
            confidence_threshold=0.6,
        )

    def test_effective(self) -> None:
        assert self.gen._determine_effectiveness(0.8, 0.7) == ("effective")

    def test_effective_at_boundary(self) -> None:
        assert self.gen._determine_effectiveness(0.7, 0.6) == ("effective")

    def test_partially_effective(self) -> None:
        result = self.gen._determine_effectiveness(0.5, 0.7)
        assert result == "partially_effective"

    def test_partially_at_lower_boundary(self) -> None:
        result = self.gen._determine_effectiveness(0.42, 0.6)
        assert result == "partially_effective"

    def test_ineffective_low_score(self) -> None:
        result = self.gen._determine_effectiveness(0.3, 0.7)
        assert result == "ineffective"

    def test_ineffective_medium_confidence(self) -> None:
        result = self.gen._determine_effectiveness(0.8, 0.4)
        assert result == "ineffective"

    def test_inconclusive_very_low_confidence(self) -> None:
        result = self.gen._determine_effectiveness(0.9, 0.2)
        assert result == "inconclusive"

    def test_inconclusive_zero_confidence(self) -> None:
        result = self.gen._determine_effectiveness(1.0, 0.0)
        assert result == "inconclusive"


class TestComputeConfidence:
    def setup_method(self) -> None:
        self.gen = MappingTableGenerator()

    def test_zero_tasks(self) -> None:
        assert self.gen._compute_confidence(0.0, 0, True) == 0.0

    def test_high_confidence(self) -> None:
        conf = self.gen._compute_confidence(0.0, 5, True)
        assert conf == pytest.approx(1.0)

    def test_convergence_bonus(self) -> None:
        with_conv = self.gen._compute_confidence(0.1, 3, True)
        without_conv = self.gen._compute_confidence(0.1, 3, False)
        assert with_conv > without_conv
        assert with_conv - without_conv == pytest.approx(0.1)

    def test_high_variance_lowers_confidence(self) -> None:
        low_var = self.gen._compute_confidence(0.1, 5, False)
        high_var = self.gen._compute_confidence(0.8, 5, False)
        assert low_var > high_var

    def test_more_tasks_increase_confidence(self) -> None:
        few = self.gen._compute_confidence(0.1, 1, False)
        many = self.gen._compute_confidence(0.1, 5, False)
        assert many > few

    def test_clamped_to_unit_range(self) -> None:
        conf = self.gen._compute_confidence(0.0, 10, True)
        assert 0.0 <= conf <= 1.0


class TestFindTasksForKeypoint:
    def setup_method(self) -> None:
        self.gen = MappingTableGenerator()

    def test_finds_matching_tasks(self) -> None:
        suite = _MockBenchmarkSuite(
            id="s1",
            name="Suite",
            tasks=[
                _MockTask(id="bench-s1-kp-1-01"),
                _MockTask(id="bench-s1-kp-1-02"),
                _MockTask(id="bench-s1-kp-2-01"),
            ],
        )
        result = self.gen._find_tasks_for_keypoint("kp-1", suite)
        assert result == [
            "bench-s1-kp-1-01",
            "bench-s1-kp-1-02",
        ]

    def test_no_matching_tasks(self) -> None:
        suite = _MockBenchmarkSuite(
            id="s1",
            name="Suite",
            tasks=[_MockTask(id="bench-s1-kp-99-01")],
        )
        result = self.gen._find_tasks_for_keypoint("kp-1", suite)
        assert result == []

    def test_empty_suite(self) -> None:
        suite = _MockBenchmarkSuite(
            id="s1",
            name="Suite",
            tasks=[],
        )
        result = self.gen._find_tasks_for_keypoint("kp-1", suite)
        assert result == []


class TestGenerateRecommendation:
    def setup_method(self) -> None:
        self.gen = MappingTableGenerator()

    def _make_kp(
        self,
        expected_impact: str = "positive improvement",
    ) -> _MockKeyPoint:
        return _MockKeyPoint(
            id="kp-1",
            category="perf",
            title="Caching",
            expected_impact=expected_impact,
        )

    def test_effective_positive(self) -> None:
        kp = self._make_kp("positive improvement")
        c = _make_conclusion(observed_effectiveness="effective")
        rec = self.gen._generate_recommendation(kp, c)
        assert "Validated" in rec
        assert "Caching" in rec

    def test_effective_negative(self) -> None:
        kp = self._make_kp("degrades latency")
        c = _make_conclusion(observed_effectiveness="effective")
        rec = self.gen._generate_recommendation(kp, c)
        assert "Warning" in rec

    def test_partially_effective(self) -> None:
        kp = self._make_kp()
        c = _make_conclusion(
            observed_effectiveness="partially_effective",
        )
        rec = self.gen._generate_recommendation(kp, c)
        assert "refinement" in rec.lower()

    def test_ineffective(self) -> None:
        kp = self._make_kp()
        c = _make_conclusion(
            observed_effectiveness="ineffective",
        )
        rec = self.gen._generate_recommendation(kp, c)
        assert "Not recommended" in rec

    def test_inconclusive(self) -> None:
        kp = self._make_kp()
        c = _make_conclusion(
            observed_effectiveness="inconclusive",
        )
        rec = self.gen._generate_recommendation(kp, c)
        assert "more evaluation" in rec.lower()


class TestExtractLessons:
    def setup_method(self) -> None:
        self.gen = MappingTableGenerator()

    def test_category_with_mixed_results(self) -> None:
        conclusions = [
            _make_conclusion(
                keypoint_id="kp-1",
                category="perf",
                observed_effectiveness="effective",
            ),
            _make_conclusion(
                keypoint_id="kp-2",
                category="perf",
                observed_effectiveness="ineffective",
            ),
        ]
        lessons = self.gen._extract_lessons(conclusions)
        cat_lessons = [ln for ln in lessons if "'perf'" in ln]
        assert len(cat_lessons) >= 1
        assert "mixed" in cat_lessons[0].lower()

    def test_all_effective_in_category(self) -> None:
        conclusions = [
            _make_conclusion(
                keypoint_id="kp-1",
                category="security",
                observed_effectiveness="effective",
            ),
            _make_conclusion(
                keypoint_id="kp-2",
                category="security",
                observed_effectiveness="effective",
            ),
        ]
        lessons = self.gen._extract_lessons(conclusions)
        cat_lessons = [ln for ln in lessons if "'security'" in ln]
        assert len(cat_lessons) >= 1
        assert "proved effective" in cat_lessons[0]

    def test_none_effective_in_category(self) -> None:
        conclusions = [
            _make_conclusion(
                keypoint_id="kp-1",
                category="ux",
                observed_effectiveness="ineffective",
            ),
            _make_conclusion(
                keypoint_id="kp-2",
                category="ux",
                observed_effectiveness="inconclusive",
            ),
        ]
        lessons = self.gen._extract_lessons(conclusions)
        cat_lessons = [ln for ln in lessons if "'ux'" in ln]
        assert len(cat_lessons) >= 1
        assert "No" in cat_lessons[0]

    def test_single_item_category_skipped(self) -> None:
        conclusions = [
            _make_conclusion(
                keypoint_id="kp-1",
                category="solo",
                observed_effectiveness="effective",
            ),
        ]
        lessons = self.gen._extract_lessons(conclusions)
        assert all("'solo'" not in ln for ln in lessons)

    def test_unexpected_positive_lesson(self) -> None:
        conclusions = [
            _make_conclusion(
                keypoint_id="kp-1",
                keypoint_title="Risky Change",
                expected_impact="degrades stability",
                observed_effectiveness="effective",
            ),
        ]
        lessons = self.gen._extract_lessons(conclusions)
        assert any("Unexpected positive" in ln for ln in lessons)

    def test_underperformed_lesson(self) -> None:
        conclusions = [
            _make_conclusion(
                keypoint_id="kp-1",
                keypoint_title="Promised Feature",
                expected_impact="positive improvement",
                observed_effectiveness="ineffective",
            ),
        ]
        lessons = self.gen._extract_lessons(conclusions)
        assert any("Underperformed" in ln for ln in lessons)


# ---------------------------------------------------------------------------
# MappingTableGenerator.generate — integration tests
# ---------------------------------------------------------------------------


class TestGenerateIntegration:
    def test_basic_generation(self) -> None:
        gen = MappingTableGenerator(
            effectiveness_threshold=0.7,
            confidence_threshold=0.6,
        )
        kp = _MockKeyPoint(
            id="kp-1",
            category="perf",
            title="Caching",
            expected_impact="positive improvement",
        )
        suite, report = _make_suite_and_report(
            suite_id="s1",
            kp_ids=["kp-1"],
        )

        table = gen.generate([kp], report, suite)

        assert table.target == "Test Suite"
        assert len(table.conclusions) == 1

        c = table.conclusions[0]
        assert c.keypoint_id == "kp-1"
        assert c.task_count == 3
        assert c.mean_score > 0
        assert c.confidence > 0
        assert c.observed_effectiveness in {
            "effective",
            "partially_effective",
            "ineffective",
            "inconclusive",
        }
        assert c.recommendation != ""
        assert c.evidence_summary != ""

    def test_multiple_keypoints(self) -> None:
        gen = MappingTableGenerator()
        kps = [
            _MockKeyPoint(
                id="kp-1",
                category="perf",
                title="Caching",
            ),
            _MockKeyPoint(
                id="kp-2",
                category="security",
                title="Auth",
            ),
        ]
        suite, report = _make_suite_and_report(
            kp_ids=["kp-1", "kp-2"],
        )

        table = gen.generate(kps, report, suite)

        assert len(table.conclusions) == 2
        ids = {c.keypoint_id for c in table.conclusions}
        assert ids == {"kp-1", "kp-2"}
        total = table.effective_count + table.ineffective_count + table.inconclusive_count
        assert total <= len(table.conclusions)

    def test_no_matching_tasks_gives_inconclusive(self) -> None:
        gen = MappingTableGenerator()
        kp = _MockKeyPoint(
            id="kp-missing",
            category="perf",
            title="Ghost",
        )
        suite, report = _make_suite_and_report(
            kp_ids=["kp-other"],
        )

        table = gen.generate([kp], report, suite)

        assert len(table.conclusions) == 1
        c = table.conclusions[0]
        assert c.observed_effectiveness == "inconclusive"
        assert c.task_count == 0
        assert c.confidence == 0.0

    def test_unconverged_report(self) -> None:
        gen = MappingTableGenerator()
        kp = _MockKeyPoint(
            id="kp-1",
            category="perf",
            title="Caching",
        )
        suite, report = _make_suite_and_report(
            kp_ids=["kp-1"],
            converged=False,
        )

        table = gen.generate([kp], report, suite)

        c = table.conclusions[0]
        assert table.metadata["converged"] is False
        suite_conv, report_conv = _make_suite_and_report(
            kp_ids=["kp-1"],
            converged=True,
        )
        table_conv = gen.generate(
            [kp],
            report_conv,
            suite_conv,
        )
        c_conv = table_conv.conclusions[0]
        assert c_conv.confidence >= c.confidence

    def test_empty_keypoints(self) -> None:
        gen = MappingTableGenerator()
        suite, report = _make_suite_and_report()

        table = gen.generate([], report, suite)

        assert table.conclusions == []
        assert table.effective_count == 0
        assert table.overall_effectiveness == 0.0
        assert table.lessons_learnt == []

    def test_overall_effectiveness_ratio(self) -> None:
        gen = MappingTableGenerator(
            effectiveness_threshold=0.5,
            confidence_threshold=0.3,
        )
        kps = [
            _MockKeyPoint(
                id=f"kp-{i}",
                category="perf",
                title=f"KP-{i}",
            )
            for i in range(1, 5)
        ]
        suite, report = _make_suite_and_report(
            kp_ids=[f"kp-{i}" for i in range(1, 5)],
        )

        table = gen.generate(kps, report, suite)

        total = len(table.conclusions)
        assert total == 4
        expected_ratio = table.effective_count / total
        assert table.overall_effectiveness == pytest.approx(
            expected_ratio,
        )

    def test_full_roundtrip_serialization(self) -> None:
        gen = MappingTableGenerator()
        kp = _MockKeyPoint(
            id="kp-1",
            category="perf",
            title="Caching",
        )
        suite, report = _make_suite_and_report(
            kp_ids=["kp-1"],
        )
        table = gen.generate([kp], report, suite)

        data = table.to_dict()
        restored = MappingTable.from_dict(data)

        assert restored.target == table.target
        assert len(restored.conclusions) == len(table.conclusions)
        assert restored.overall_effectiveness == pytest.approx(table.overall_effectiveness)
        assert restored.lessons_learnt == table.lessons_learnt

        json_str = table.to_json()
        parsed = json.loads(json_str)
        assert parsed["target"] == table.target

    def test_markdown_output_all_rows(self) -> None:
        gen = MappingTableGenerator()
        kps = [
            _MockKeyPoint(
                id="kp-1",
                category="perf",
                title="Caching",
            ),
            _MockKeyPoint(
                id="kp-2",
                category="security",
                title="Auth",
            ),
        ]
        suite, report = _make_suite_and_report(
            kp_ids=["kp-1", "kp-2"],
        )
        table = gen.generate(kps, report, suite)

        md = table.to_markdown()
        lines = md.strip().split("\n")
        assert len(lines) == 4
        assert "Caching" in lines[2]
        assert "Auth" in lines[3]
