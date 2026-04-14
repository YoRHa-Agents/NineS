"""Tests for the key-point extractor (FR-314).

Covers:
- KeyPoint / KeyPointReport serialization round-trip
- KeyPointReport convenience methods (get_by_category, get_by_priority, high_priority)
- KeyPointExtractor._extract_from_mechanisms: category mapping, priority, impact
- KeyPointExtractor._extract_from_economics: overhead, savings, break-even points
- KeyPointExtractor._extract_from_findings: severity-to-impact conversion
- KeyPointExtractor._extract_from_analysis: engineering observations + metrics
- KeyPointExtractor._deduplicate: removes overlapping points, keeps higher magnitude
- KeyPointExtractor._prioritize: correct priority assignment and sort order
- KeyPointExtractor.extract: end-to-end with and without AnalysisResult
- Edge cases: empty report, no mechanisms, no findings
"""

from __future__ import annotations

import pytest

from nines.analyzer.agent_impact import (
    AgentImpactReport,
    AgentMechanism,
    ContextEconomics,
)
from nines.analyzer.keypoint import (
    KeyPoint,
    KeyPointExtractor,
    KeyPointReport,
    _count_categories,
    _descriptions_overlap,
    _finding_category_to_keypoint,
    _infer_impact_from_token_delta,
    _mechanism_priority,
)
from nines.core.models import (
    AnalysisResult,
    Finding,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor() -> KeyPointExtractor:
    """Provide a fresh extractor instance."""
    return KeyPointExtractor()


@pytest.fixture
def sample_mechanisms() -> list[AgentMechanism]:
    """A small set of mechanisms covering multiple categories."""
    return [
        AgentMechanism(
            id="mech-001",
            name="token_compression",
            category="context_compression",
            description="Compresses token usage",
            evidence_files=["CLAUDE.md"],
            estimated_token_impact=-2000,
            confidence=0.8,
        ),
        AgentMechanism(
            id="mech-002",
            name="behavioral_rules",
            category="behavioral_instruction",
            description="Style rules for the agent",
            evidence_files=["rules/style.md"],
            estimated_token_impact=500,
            confidence=0.6,
        ),
        AgentMechanism(
            id="mech-003",
            name="multi_platform_sync",
            category="distribution",
            description="Syncs config across IDEs",
            evidence_files=["sync.yml"],
            estimated_token_impact=100,
            confidence=0.4,
        ),
        AgentMechanism(
            id="mech-004",
            name="safety_guardrails",
            category="safety",
            description="Safety rules",
            evidence_files=["safety.md"],
            estimated_token_impact=300,
            confidence=0.9,
        ),
        AgentMechanism(
            id="mech-005",
            name="drift_prevention",
            category="persistence",
            description="Drift prevention",
            evidence_files=["guard.md"],
            estimated_token_impact=200,
            confidence=0.3,
        ),
    ]


@pytest.fixture
def sample_economics() -> ContextEconomics:
    return ContextEconomics(
        overhead_tokens=6000,
        estimated_savings_ratio=0.25,
        mechanism_count=5,
        agent_facing_files=4,
        total_agent_context_tokens=6000,
        break_even_interactions=4,
    )


@pytest.fixture
def sample_findings() -> list[Finding]:
    return [
        Finding(
            id="AI-0000",
            severity="info",
            category="agent_impact",
            message="4 artifacts, 5 mechanisms",
            location="CLAUDE.md",
        ),
        Finding(
            id="AI-0001",
            severity="warning",
            category="context_economics",
            message="High overhead (6000 tokens)",
            location="",
        ),
        Finding(
            id="AI-0002",
            severity="info",
            category="coverage_gap",
            message="Missing tool_management",
            location="",
        ),
    ]


@pytest.fixture
def sample_report(
    sample_mechanisms: list[AgentMechanism],
    sample_economics: ContextEconomics,
    sample_findings: list[Finding],
) -> AgentImpactReport:
    return AgentImpactReport(
        target="/repo",
        mechanisms=sample_mechanisms,
        economics=sample_economics,
        agent_facing_artifacts=["CLAUDE.md", "rules/style.md", "sync.yml", "safety.md"],
        findings=sample_findings,
    )


# ---------------------------------------------------------------------------
# KeyPoint serialization
# ---------------------------------------------------------------------------


class TestKeyPoint:
    """Tests for KeyPoint dataclass serialization."""

    def test_to_dict(self) -> None:
        kp = KeyPoint(
            id="kp-1",
            category="compression",
            title="Test",
            description="desc",
            mechanism_ids=["m1"],
            expected_impact="positive",
            impact_magnitude=0.7,
            validation_approach="benchmark",
            evidence=["a.md"],
            priority=1,
            metadata={"k": "v"},
        )
        d = kp.to_dict()
        assert d["id"] == "kp-1"
        assert d["category"] == "compression"
        assert d["mechanism_ids"] == ["m1"]
        assert d["expected_impact"] == "positive"
        assert d["impact_magnitude"] == 0.7
        assert d["priority"] == 1
        assert d["metadata"] == {"k": "v"}

    def test_from_dict(self) -> None:
        data = {
            "id": "kp-2",
            "category": "engineering",
            "title": "T",
            "description": "D",
            "mechanism_ids": ["m2"],
            "expected_impact": "negative",
            "impact_magnitude": 0.3,
            "validation_approach": "review",
            "evidence": ["b.md"],
            "priority": 5,
            "metadata": {},
        }
        kp = KeyPoint.from_dict(data)
        assert kp.id == "kp-2"
        assert kp.category == "engineering"
        assert kp.expected_impact == "negative"

    def test_from_dict_defaults(self) -> None:
        kp = KeyPoint.from_dict({"id": "kp-3"})
        assert kp.category == ""
        assert kp.mechanism_ids == []
        assert kp.expected_impact == "uncertain"
        assert kp.impact_magnitude == 0.0
        assert kp.evidence == []
        assert kp.priority == 3
        assert kp.metadata == {}

    def test_roundtrip(self) -> None:
        original = KeyPoint(
            id="rt",
            category="compression",
            title="Round trip",
            description="Testing round trip",
            mechanism_ids=["m1", "m2"],
            expected_impact="positive",
            impact_magnitude=0.85,
            validation_approach="compare",
            evidence=["x.md", "y.md"],
            priority=2,
            metadata={"source": "test"},
        )
        restored = KeyPoint.from_dict(original.to_dict())
        assert restored.to_dict() == original.to_dict()


# ---------------------------------------------------------------------------
# KeyPointReport serialization & convenience methods
# ---------------------------------------------------------------------------


class TestKeyPointReport:
    """Tests for KeyPointReport dataclass serialization and helpers."""

    def _make_report(self) -> KeyPointReport:
        return KeyPointReport(
            target="/repo",
            key_points=[
                KeyPoint(
                    id="a",
                    category="compression",
                    title="A",
                    description="",
                    priority=1,
                    impact_magnitude=0.9,
                ),
                KeyPoint(
                    id="b",
                    category="context_management",
                    title="B",
                    description="",
                    priority=2,
                    impact_magnitude=0.5,
                ),
                KeyPoint(
                    id="c",
                    category="engineering",
                    title="C",
                    description="",
                    priority=5,
                    impact_magnitude=0.1,
                ),
                KeyPoint(
                    id="d",
                    category="compression",
                    title="D",
                    description="",
                    priority=3,
                    impact_magnitude=0.4,
                ),
            ],
            summary="4 key points",
            extraction_duration_ms=12.5,
            metadata={"version": 1},
        )

    def test_to_dict(self) -> None:
        report = self._make_report()
        d = report.to_dict()
        assert d["target"] == "/repo"
        assert len(d["key_points"]) == 4
        assert d["summary"] == "4 key points"
        assert d["extraction_duration_ms"] == 12.5

    def test_from_dict(self) -> None:
        report = self._make_report()
        restored = KeyPointReport.from_dict(report.to_dict())
        assert restored.target == "/repo"
        assert len(restored.key_points) == 4
        assert restored.extraction_duration_ms == 12.5

    def test_from_dict_minimal(self) -> None:
        report = KeyPointReport.from_dict({"target": "/x"})
        assert report.key_points == []
        assert report.summary == ""
        assert report.extraction_duration_ms == 0.0

    def test_roundtrip(self) -> None:
        original = self._make_report()
        restored = KeyPointReport.from_dict(original.to_dict())
        assert restored.to_dict() == original.to_dict()

    def test_get_by_category(self) -> None:
        report = self._make_report()
        compression = report.get_by_category("compression")
        assert len(compression) == 2
        assert all(kp.category == "compression" for kp in compression)

    def test_get_by_category_empty(self) -> None:
        report = self._make_report()
        assert report.get_by_category("nonexistent") == []

    def test_get_by_priority(self) -> None:
        report = self._make_report()
        p1 = report.get_by_priority(1)
        assert len(p1) == 1
        assert p1[0].id == "a"

    def test_high_priority(self) -> None:
        report = self._make_report()
        high = report.high_priority()
        assert len(high) == 2
        assert all(kp.priority <= 2 for kp in high)


# ---------------------------------------------------------------------------
# _extract_from_mechanisms
# ---------------------------------------------------------------------------


class TestExtractFromMechanisms:
    """Tests for KeyPointExtractor._extract_from_mechanisms."""

    def test_one_point_per_mechanism(
        self,
        extractor: KeyPointExtractor,
        sample_mechanisms: list[AgentMechanism],
    ) -> None:
        points = extractor._extract_from_mechanisms(sample_mechanisms)
        assert len(points) == len(sample_mechanisms)

    def test_category_mapping(
        self,
        extractor: KeyPointExtractor,
        sample_mechanisms: list[AgentMechanism],
    ) -> None:
        points = extractor._extract_from_mechanisms(sample_mechanisms)
        categories = {p.category for p in points}
        assert "compression" in categories
        assert "behavioral_shaping" in categories
        assert "cross_platform" in categories
        assert "semantic_preservation" in categories

    def test_mechanism_ids_linked(
        self,
        extractor: KeyPointExtractor,
        sample_mechanisms: list[AgentMechanism],
    ) -> None:
        points = extractor._extract_from_mechanisms(sample_mechanisms)
        for point, mech in zip(points, sample_mechanisms, strict=True):
            assert mech.id in point.mechanism_ids

    def test_impact_magnitude_bounded(
        self,
        extractor: KeyPointExtractor,
        sample_mechanisms: list[AgentMechanism],
    ) -> None:
        points = extractor._extract_from_mechanisms(sample_mechanisms)
        for p in points:
            assert 0.0 <= p.impact_magnitude <= 1.0

    def test_compression_gets_positive_impact(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        mechs = [
            AgentMechanism(
                id="c1",
                name="compress",
                category="context_compression",
                description="saves tokens",
                evidence_files=["a.md"],
                estimated_token_impact=-3000,
                confidence=0.9,
            )
        ]
        points = extractor._extract_from_mechanisms(mechs)
        assert points[0].expected_impact == "positive"

    def test_empty_mechanisms(self, extractor: KeyPointExtractor) -> None:
        assert extractor._extract_from_mechanisms([]) == []

    def test_evidence_propagated(
        self,
        extractor: KeyPointExtractor,
        sample_mechanisms: list[AgentMechanism],
    ) -> None:
        points = extractor._extract_from_mechanisms(sample_mechanisms)
        for p, m in zip(points, sample_mechanisms, strict=True):
            assert p.evidence == m.evidence_files


# ---------------------------------------------------------------------------
# _extract_from_economics
# ---------------------------------------------------------------------------


class TestExtractFromEconomics:
    """Tests for KeyPointExtractor._extract_from_economics."""

    def test_generates_overhead_point(
        self,
        extractor: KeyPointExtractor,
        sample_economics: ContextEconomics,
    ) -> None:
        points = extractor._extract_from_economics(sample_economics)
        overhead = [p for p in points if "overhead" in p.title.lower()]
        assert len(overhead) == 1
        assert overhead[0].category == "context_management"

    def test_generates_savings_point(
        self,
        extractor: KeyPointExtractor,
        sample_economics: ContextEconomics,
    ) -> None:
        points = extractor._extract_from_economics(sample_economics)
        savings = [p for p in points if "savings" in p.title.lower()]
        assert len(savings) == 1

    def test_generates_breakeven_point(
        self,
        extractor: KeyPointExtractor,
        sample_economics: ContextEconomics,
    ) -> None:
        points = extractor._extract_from_economics(sample_economics)
        be = [p for p in points if "break-even" in p.title.lower()]
        assert len(be) == 1

    def test_high_overhead_negative(self, extractor: KeyPointExtractor) -> None:
        econ = ContextEconomics(overhead_tokens=8000, agent_facing_files=2)
        points = extractor._extract_from_economics(econ)
        overhead = [p for p in points if "overhead" in p.title.lower()]
        assert overhead[0].expected_impact == "negative"

    def test_low_overhead_neutral(self, extractor: KeyPointExtractor) -> None:
        econ = ContextEconomics(overhead_tokens=100, agent_facing_files=1)
        points = extractor._extract_from_economics(econ)
        overhead = [p for p in points if "overhead" in p.title.lower()]
        assert overhead[0].expected_impact == "neutral"

    def test_zero_economics(self, extractor: KeyPointExtractor) -> None:
        econ = ContextEconomics()
        points = extractor._extract_from_economics(econ)
        assert points == []

    def test_low_savings_negative(self, extractor: KeyPointExtractor) -> None:
        econ = ContextEconomics(estimated_savings_ratio=0.05)
        points = extractor._extract_from_economics(econ)
        savings = [p for p in points if "savings" in p.title.lower()]
        assert savings[0].expected_impact == "negative"

    def test_all_points_context_management(
        self,
        extractor: KeyPointExtractor,
        sample_economics: ContextEconomics,
    ) -> None:
        points = extractor._extract_from_economics(sample_economics)
        assert all(p.category == "context_management" for p in points)


# ---------------------------------------------------------------------------
# _extract_from_findings
# ---------------------------------------------------------------------------


class TestExtractFromFindings:
    """Tests for KeyPointExtractor._extract_from_findings."""

    def test_one_point_per_finding(
        self,
        extractor: KeyPointExtractor,
        sample_findings: list[Finding],
    ) -> None:
        points = extractor._extract_from_findings(sample_findings)
        assert len(points) == len(sample_findings)

    def test_severity_to_impact(self, extractor: KeyPointExtractor) -> None:
        findings = [
            Finding(id="f1", severity="critical", message="crit"),
            Finding(id="f2", severity="warning", message="warn"),
            Finding(id="f3", severity="info", message="info"),
        ]
        points = extractor._extract_from_findings(findings)
        assert points[0].expected_impact == "negative"
        assert points[1].expected_impact == "negative"
        assert points[2].expected_impact == "neutral"

    def test_severity_to_magnitude(self, extractor: KeyPointExtractor) -> None:
        findings = [
            Finding(id="f1", severity="critical", message="c"),
            Finding(id="f2", severity="info", message="i"),
        ]
        points = extractor._extract_from_findings(findings)
        assert points[0].impact_magnitude > points[1].impact_magnitude

    def test_location_in_evidence(self, extractor: KeyPointExtractor) -> None:
        findings = [
            Finding(id="f1", severity="info", message="m", location="file.py"),
        ]
        points = extractor._extract_from_findings(findings)
        assert "file.py" in points[0].evidence

    def test_empty_location_no_evidence(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        findings = [Finding(id="f1", severity="info", message="m")]
        points = extractor._extract_from_findings(findings)
        assert points[0].evidence == []

    def test_empty_findings(self, extractor: KeyPointExtractor) -> None:
        assert extractor._extract_from_findings([]) == []


# ---------------------------------------------------------------------------
# _extract_from_analysis
# ---------------------------------------------------------------------------


class TestExtractFromAnalysis:
    """Tests for KeyPointExtractor._extract_from_analysis."""

    def test_findings_become_engineering(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        result = AnalysisResult(
            target="/repo",
            findings=[
                Finding(
                    id="af1", severity="error", message="critical function", location="main.py"
                ),
            ],
        )
        points = extractor._extract_from_analysis(result)
        assert len(points) == 1
        assert points[0].category == "engineering"
        assert points[0].priority == 5

    def test_metrics_produce_summary_only(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        result = AnalysisResult(
            target="/repo",
            metrics={
                "files_analyzed": 10,
                "total_lines": 500,
                "agent_impact": {"mechanisms": []},
                "total_files_scanned": 15,
            },
        )
        points = extractor._extract_from_analysis(result)
        assert len(points) == 1
        assert points[0].title == "Analysis coverage summary"
        assert points[0].metadata.get("source") == "analysis_summary"

    def test_empty_analysis(self, extractor: KeyPointExtractor) -> None:
        result = AnalysisResult(target="/repo")
        points = extractor._extract_from_analysis(result)
        assert points == []

    def test_finding_evidence_propagated(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        result = AnalysisResult(
            target="/repo",
            findings=[
                Finding(id="af1", severity="critical", message="security issue", location="src/foo.py"),
            ],
        )
        points = extractor._extract_from_analysis(result)
        assert len(points) >= 1
        assert "src/foo.py" in points[0].evidence


# ---------------------------------------------------------------------------
# _deduplicate
# ---------------------------------------------------------------------------


class TestDeduplicate:
    """Tests for KeyPointExtractor._deduplicate."""

    def test_removes_exact_duplicates(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(
                id="a",
                category="compression",
                title="Same Title",
                description="",
                impact_magnitude=0.5,
            ),
            KeyPoint(
                id="b",
                category="compression",
                title="Same Title",
                description="",
                impact_magnitude=0.3,
            ),
        ]
        result = extractor._deduplicate(points)
        assert len(result) == 1
        assert result[0].impact_magnitude == 0.5

    def test_keeps_different_categories(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(
                id="a",
                category="compression",
                title="Same Title",
                description="",
                impact_magnitude=0.5,
            ),
            KeyPoint(
                id="b",
                category="engineering",
                title="Same Title",
                description="",
                impact_magnitude=0.3,
            ),
        ]
        result = extractor._deduplicate(points)
        assert len(result) == 2

    def test_case_insensitive_title(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(
                id="a",
                category="compression",
                title="My Title",
                description="",
                impact_magnitude=0.3,
            ),
            KeyPoint(
                id="b",
                category="compression",
                title="my title",
                description="",
                impact_magnitude=0.7,
            ),
        ]
        result = extractor._deduplicate(points)
        assert len(result) == 1
        assert result[0].impact_magnitude == 0.7

    def test_empty_list(self, extractor: KeyPointExtractor) -> None:
        assert extractor._deduplicate([]) == []

    def test_no_duplicates_unchanged(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(id="a", category="compression", title="One", description=""),
            KeyPoint(id="b", category="engineering", title="Two", description=""),
        ]
        result = extractor._deduplicate(points)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _prioritize
# ---------------------------------------------------------------------------


class TestPrioritize:
    """Tests for KeyPointExtractor._prioritize."""

    def test_high_confidence_mechanism_gets_p1(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(
                id="x",
                category="compression",
                title="T",
                description="",
                impact_magnitude=0.8,
                metadata={"source": "mechanism", "confidence": 0.9},
            )
        ]
        result = extractor._prioritize(points)
        assert result[0].priority == 1

    def test_moderate_mechanism_gets_p2(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(
                id="x",
                category="compression",
                title="T",
                description="",
                impact_magnitude=0.5,
                metadata={"source": "mechanism", "confidence": 0.6},
            )
        ]
        result = extractor._prioritize(points)
        assert result[0].priority == 2

    def test_economics_gets_p3(self, extractor: KeyPointExtractor) -> None:
        points = [
            KeyPoint(
                id="x",
                category="context_management",
                title="T",
                description="",
                metadata={"source": "economics"},
            )
        ]
        result = extractor._prioritize(points)
        assert result[0].priority == 3

    def test_low_confidence_mechanism_gets_p4(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(
                id="x",
                category="compression",
                title="T",
                description="",
                impact_magnitude=0.1,
                metadata={"source": "mechanism", "confidence": 0.2},
            )
        ]
        result = extractor._prioritize(points)
        assert result[0].priority == 4

    def test_engineering_gets_p5(self, extractor: KeyPointExtractor) -> None:
        points = [
            KeyPoint(
                id="x",
                category="engineering",
                title="T",
                description="",
                metadata={"source": "analysis"},
            )
        ]
        result = extractor._prioritize(points)
        assert result[0].priority == 5

    def test_sorted_by_priority_then_magnitude(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(
                id="low",
                category="engineering",
                title="L",
                description="",
                impact_magnitude=0.1,
                metadata={"source": "analysis"},
            ),
            KeyPoint(
                id="high",
                category="compression",
                title="H",
                description="",
                impact_magnitude=0.9,
                metadata={"source": "mechanism", "confidence": 0.9},
            ),
            KeyPoint(
                id="mid",
                category="context_management",
                title="M",
                description="",
                impact_magnitude=0.5,
                metadata={"source": "economics"},
            ),
        ]
        result = extractor._prioritize(points)
        assert result[0].id == "high"
        assert result[1].id == "mid"
        assert result[2].id == "low"

    def test_finding_severity_priority(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        points = [
            KeyPoint(
                id="crit",
                category="behavioral_shaping",
                title="C",
                description="",
                metadata={"source": "finding", "severity": "critical"},
            ),
            KeyPoint(
                id="info",
                category="behavioral_shaping",
                title="I",
                description="",
                metadata={"source": "finding", "severity": "info"},
            ),
        ]
        result = extractor._prioritize(points)
        assert result[0].id == "crit"
        assert result[0].priority == 2
        assert result[1].priority == 4


# ---------------------------------------------------------------------------
# End-to-end extract
# ---------------------------------------------------------------------------


class TestExtractEndToEnd:
    """End-to-end tests for KeyPointExtractor.extract."""

    def test_extract_produces_report(
        self,
        extractor: KeyPointExtractor,
        sample_report: AgentImpactReport,
    ) -> None:
        report = extractor.extract(sample_report)
        assert isinstance(report, KeyPointReport)
        assert report.target == "/repo"
        assert len(report.key_points) > 0
        assert report.extraction_duration_ms >= 0
        assert report.summary != ""

    def test_all_categories_present(
        self,
        extractor: KeyPointExtractor,
        sample_report: AgentImpactReport,
    ) -> None:
        report = extractor.extract(sample_report)
        categories = {kp.category for kp in report.key_points}
        assert "compression" in categories
        assert "behavioral_shaping" in categories
        assert "context_management" in categories

    def test_sorted_by_priority(
        self,
        extractor: KeyPointExtractor,
        sample_report: AgentImpactReport,
    ) -> None:
        report = extractor.extract(sample_report)
        priorities = [kp.priority for kp in report.key_points]
        assert priorities == sorted(priorities)

    def test_with_analysis_result(
        self,
        extractor: KeyPointExtractor,
        sample_report: AgentImpactReport,
    ) -> None:
        analysis = AnalysisResult(
            target="/repo",
            findings=[Finding(id="af1", severity="error", message="critical issue", location="main.py")],
            metrics={"files_analyzed": 10, "agent_impact": {"mechanisms": []}},
        )
        report = extractor.extract(sample_report, analysis_result=analysis)
        eng = report.get_by_category("engineering")
        assert len(eng) >= 1

    def test_without_analysis_result(
        self,
        extractor: KeyPointExtractor,
        sample_report: AgentImpactReport,
    ) -> None:
        report = extractor.extract(sample_report, analysis_result=None)
        assert isinstance(report, KeyPointReport)
        assert len(report.key_points) > 0

    def test_report_serialization_roundtrip(
        self,
        extractor: KeyPointExtractor,
        sample_report: AgentImpactReport,
    ) -> None:
        report = extractor.extract(sample_report)
        data = report.to_dict()
        restored = KeyPointReport.from_dict(data)
        assert restored.target == report.target
        assert len(restored.key_points) == len(report.key_points)
        assert restored.extraction_duration_ms == report.extraction_duration_ms
        for orig, rest in zip(report.key_points, restored.key_points, strict=True):
            assert orig.to_dict() == rest.to_dict()

    def test_empty_report(self, extractor: KeyPointExtractor) -> None:
        empty = AgentImpactReport(target="/empty")
        report = extractor.extract(empty)
        assert report.target == "/empty"
        assert report.key_points == []
        assert "No key points" in report.summary

    def test_metadata_has_category_counts(
        self,
        extractor: KeyPointExtractor,
        sample_report: AgentImpactReport,
    ) -> None:
        report = extractor.extract(sample_report)
        assert "category_counts" in report.metadata
        counts = report.metadata["category_counts"]
        total = sum(counts.values())
        assert total == len(report.key_points)

    def test_high_priority_convenience(
        self,
        extractor: KeyPointExtractor,
        sample_report: AgentImpactReport,
    ) -> None:
        report = extractor.extract(sample_report)
        high = report.high_priority()
        assert all(kp.priority <= 2 for kp in high)

    def test_deduplication_happens(
        self,
        extractor: KeyPointExtractor,
    ) -> None:
        """Findings with identical category+title should be deduplicated."""
        findings = [
            Finding(id="f1", severity="info", category="agent_impact", message="duplicate msg"),
            Finding(id="f2", severity="info", category="agent_impact", message="duplicate msg"),
        ]
        report_input = AgentImpactReport(
            target="/dup",
            findings=findings,
        )
        report = extractor.extract(report_input)
        titles = [kp.title for kp in report.key_points]
        assert titles.count("Finding: agent_impact") == 1


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_infer_impact_positive(self) -> None:
        assert _infer_impact_from_token_delta(-500) == "positive"

    def test_infer_impact_negative(self) -> None:
        assert _infer_impact_from_token_delta(1000) == "negative"

    def test_infer_impact_neutral(self) -> None:
        assert _infer_impact_from_token_delta(100) == "neutral"

    def test_infer_impact_uncertain(self) -> None:
        assert _infer_impact_from_token_delta(0) == "uncertain"

    def test_mechanism_priority_high(self) -> None:
        mech = AgentMechanism(
            id="m",
            name="n",
            category="c",
            description="d",
            estimated_token_impact=1000,
            confidence=0.9,
        )
        assert _mechanism_priority(mech) == 1

    def test_mechanism_priority_moderate(self) -> None:
        mech = AgentMechanism(
            id="m",
            name="n",
            category="c",
            description="d",
            estimated_token_impact=100,
            confidence=0.6,
        )
        assert _mechanism_priority(mech) == 2

    def test_mechanism_priority_low(self) -> None:
        mech = AgentMechanism(
            id="m",
            name="n",
            category="c",
            description="d",
            estimated_token_impact=10,
            confidence=0.2,
        )
        assert _mechanism_priority(mech) == 4

    def test_finding_category_mapping(self) -> None:
        assert _finding_category_to_keypoint("agent_impact") == "behavioral_shaping"
        assert _finding_category_to_keypoint("context_economics") == "context_management"
        assert _finding_category_to_keypoint("coverage_gap") == "context_management"
        assert _finding_category_to_keypoint("unknown") == "engineering"

    def test_count_categories(self) -> None:
        points = [
            KeyPoint(id="a", category="compression", title="A", description=""),
            KeyPoint(id="b", category="compression", title="B", description=""),
            KeyPoint(id="c", category="engineering", title="C", description=""),
        ]
        counts = _count_categories(points)
        assert counts == {"compression": 2, "engineering": 1}

    def test_count_categories_empty(self) -> None:
        assert _count_categories([]) == {}


# ---------------------------------------------------------------------------
# Issue 1: Beneficial-category impact inference
# ---------------------------------------------------------------------------


class TestBeneficialCategoryImpact:
    """Behavioral_instruction, safety, and persistence mechanisms get positive impact."""

    def test_behavioral_instruction_positive(self) -> None:
        assert _infer_impact_from_token_delta(500, "behavioral_instruction") == "positive"

    def test_safety_positive(self) -> None:
        assert _infer_impact_from_token_delta(300, "safety") == "positive"

    def test_persistence_positive(self) -> None:
        assert _infer_impact_from_token_delta(200, "persistence") == "positive"

    def test_beneficial_zero_tokens_neutral(self) -> None:
        assert _infer_impact_from_token_delta(0, "safety") == "neutral"

    def test_beneficial_negative_tokens_still_positive(self) -> None:
        """Beneficial category saving tokens is still positive (saves tokens)."""
        assert _infer_impact_from_token_delta(-500, "safety") == "positive"

    def test_non_beneficial_high_tokens_negative(self) -> None:
        assert _infer_impact_from_token_delta(1000, "context_compression") == "negative"

    def test_no_category_preserves_old_behavior(self) -> None:
        assert _infer_impact_from_token_delta(1000) == "negative"
        assert _infer_impact_from_token_delta(-500) == "positive"
        assert _infer_impact_from_token_delta(100) == "neutral"
        assert _infer_impact_from_token_delta(0) == "uncertain"

    def test_mechanism_extraction_behavioral_gets_positive(
        self,
    ) -> None:
        """End-to-end: behavioral_instruction mechanism → positive impact key point."""
        extractor = KeyPointExtractor()
        mechs = [
            AgentMechanism(
                id="b1",
                name="behavioral_rules",
                category="behavioral_instruction",
                description="Style rules for the agent",
                evidence_files=["rules/style.md"],
                estimated_token_impact=500,
                confidence=0.6,
            ),
        ]
        points = extractor._extract_from_mechanisms(mechs)
        assert len(points) == 1
        assert points[0].expected_impact == "positive"

    def test_mechanism_extraction_safety_gets_positive(self) -> None:
        extractor = KeyPointExtractor()
        mechs = [
            AgentMechanism(
                id="s1",
                name="safety_guardrails",
                category="safety",
                description="Safety rules",
                evidence_files=["safety.md"],
                estimated_token_impact=300,
                confidence=0.9,
            ),
        ]
        points = extractor._extract_from_mechanisms(mechs)
        assert points[0].expected_impact == "positive"


# ---------------------------------------------------------------------------
# Issue 2: Logarithmic magnitude scale
# ---------------------------------------------------------------------------


class TestLogMagnitude:
    """Impact magnitude uses log scale to differentiate across the range."""

    def test_small_and_large_tokens_differ(self) -> None:
        """1K-token and 10K-token mechanisms must have different magnitudes."""
        extractor = KeyPointExtractor()
        small = AgentMechanism(
            id="s", name="s", category="context_compression",
            description="d", estimated_token_impact=-1000, confidence=1.0,
        )
        large = AgentMechanism(
            id="l", name="l", category="context_compression",
            description="d", estimated_token_impact=-10000, confidence=1.0,
        )
        pts_s = extractor._extract_from_mechanisms([small])
        pts_l = extractor._extract_from_mechanisms([large])
        assert pts_s[0].impact_magnitude < pts_l[0].impact_magnitude

    def test_5k_tokens_not_saturated(self) -> None:
        """5K tokens at confidence 1.0 must be well below 1.0."""
        extractor = KeyPointExtractor()
        mech = AgentMechanism(
            id="m", name="n", category="context_compression",
            description="d", estimated_token_impact=5000, confidence=1.0,
        )
        pts = extractor._extract_from_mechanisms([mech])
        assert pts[0].impact_magnitude < 0.85

    def test_50k_tokens_reaches_one(self) -> None:
        """50K tokens at confidence 1.0 should be at or near 1.0."""
        extractor = KeyPointExtractor()
        mech = AgentMechanism(
            id="m", name="n", category="context_compression",
            description="d", estimated_token_impact=50000, confidence=1.0,
        )
        pts = extractor._extract_from_mechanisms([mech])
        assert pts[0].impact_magnitude >= 0.99

    def test_magnitude_bounded(self) -> None:
        """Even with enormous token impact, magnitude must not exceed 1.0."""
        extractor = KeyPointExtractor()
        mech = AgentMechanism(
            id="m", name="n", category="context_compression",
            description="d", estimated_token_impact=999999, confidence=1.0,
        )
        pts = extractor._extract_from_mechanisms([mech])
        assert pts[0].impact_magnitude <= 1.0


# ---------------------------------------------------------------------------
# Issue 3: Semantic deduplication
# ---------------------------------------------------------------------------


class TestSemanticDeduplication:
    """Economics and finding key points describing the same concern are merged."""

    def test_overlapping_economics_finding_deduplicated(self) -> None:
        """Token overhead analysis (economics) + Finding: context_economics → 1 point."""
        extractor = KeyPointExtractor()
        points = [
            KeyPoint(
                id="econ-1",
                category="context_management",
                title="Token overhead analysis",
                description="Agent context overhead is 6000 tokens across 4 file(s). This is high and may degrade agent performance.",
                impact_magnitude=0.6,
                metadata={"source": "economics", "overhead_tokens": 6000},
            ),
            KeyPoint(
                id="find-1",
                category="context_management",
                title="Finding: context_economics",
                description="High overhead (6000 tokens)",
                impact_magnitude=0.5,
                metadata={"source": "finding", "severity": "warning"},
            ),
        ]
        result = extractor._deduplicate(points)
        assert len(result) == 1
        assert result[0].impact_magnitude == 0.6

    def test_non_overlapping_same_category_kept(self) -> None:
        """Same category but unrelated descriptions must survive."""
        extractor = KeyPointExtractor()
        points = [
            KeyPoint(
                id="a",
                category="context_management",
                title="Token overhead analysis",
                description="Agent context overhead is 6000 tokens.",
                impact_magnitude=0.6,
            ),
            KeyPoint(
                id="b",
                category="context_management",
                title="Break-even interaction threshold",
                description="Break-even at 4 interaction(s) — overhead is recovered quickly.",
                impact_magnitude=0.2,
            ),
        ]
        result = extractor._deduplicate(points)
        assert len(result) == 2

    def test_descriptions_overlap_substring(self) -> None:
        assert _descriptions_overlap(
            "High overhead (6000 tokens)",
            "Agent context overhead is 6000 tokens across 4 file(s). This is high.",
        )

    def test_descriptions_overlap_word_ratio(self) -> None:
        assert _descriptions_overlap(
            "Token overhead analysis shows 6000 tokens agent context",
            "Token overhead is 6000 tokens in the agent context window",
        )

    def test_descriptions_no_overlap(self) -> None:
        assert not _descriptions_overlap(
            "Break-even at 4 interactions",
            "Estimated savings ratio is 25.0%",
        )

    def test_empty_descriptions_no_overlap(self) -> None:
        assert not _descriptions_overlap("", "something")

    def test_different_categories_not_merged(self) -> None:
        """Semantic dedup only applies within the same category."""
        extractor = KeyPointExtractor()
        points = [
            KeyPoint(
                id="a",
                category="context_management",
                title="Overhead",
                description="High overhead 6000 tokens context",
                impact_magnitude=0.6,
            ),
            KeyPoint(
                id="b",
                category="engineering",
                title="Observation",
                description="High overhead 6000 tokens context",
                impact_magnitude=0.5,
            ),
        ]
        result = extractor._deduplicate(points)
        assert len(result) == 2
