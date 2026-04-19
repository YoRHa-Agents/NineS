"""Tests for the Agent impact analyzer (FR-313).

Covers:
- AgentMechanism / ContextEconomics / AgentImpactReport serialization
- _discover_agent_artifacts: finds Agent-facing files, skips .git etc.
- _estimate_context_economics: token estimation and break-even calculation
- _detect_mechanisms: classifies files into mechanism categories
- _generate_findings: produces findings about Agent impact profile
- _create_knowledge_units: creates KnowledgeUnits from mechanisms
- analyze: end-to-end on a synthetic repo
- edge cases: empty repo, single file, binary files, unreadable files
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from nines.analyzer.agent_impact import (
    AgentImpactAnalyzer,
    AgentImpactReport,
    AgentMechanism,
    ContextEconomics,
)
from nines.core.models import Finding, KnowledgeUnit


@pytest.fixture
def analyzer() -> AgentImpactAnalyzer:
    """Provide a fresh analyzer instance."""
    return AgentImpactAnalyzer()


@pytest.fixture
def agent_repo(tmp_path: Path) -> Path:
    """Create a synthetic AI-agent-oriented repository."""
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / ".cursor" / "rules" / "style.md").write_text(
        "# Style Rules\nAlways use concise variable names.\nNever skip safety checks.\n"
    )

    (tmp_path / "CLAUDE.md").write_text(
        "# Claude Instructions\nYou must follow these rules.\nAlways compress token usage.\n"
    )

    (tmp_path / "AGENTS.md").write_text(
        "# Agent Guidelines\nSync rules across platforms.\nDeploy to CI workflow.\n"
    )

    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# Skill Definition\nThis skill provides safety fallback.\nDrift prevention is enforced.\n"
    )

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")

    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n")

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.json").write_text("{}")

    return tmp_path


@pytest.fixture
def empty_repo(tmp_path: Path) -> Path:
    """Create a repo with no Agent-facing files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")
    (tmp_path / "README.md").write_text("# Project\n")
    return tmp_path


class TestAgentMechanism:
    """Tests for AgentMechanism dataclass serialization."""

    def test_to_dict(self) -> None:
        mech = AgentMechanism(
            id="m1",
            name="test_mech",
            category="safety",
            description="A safety mechanism",
            evidence_files=["a.md", "b.md"],
            estimated_token_impact=-100,
            confidence=0.8,
        )
        d = mech.to_dict()
        assert d["id"] == "m1"
        assert d["name"] == "test_mech"
        assert d["category"] == "safety"
        assert d["evidence_files"] == ["a.md", "b.md"]
        assert d["estimated_token_impact"] == -100
        assert d["confidence"] == 0.8

    def test_from_dict(self) -> None:
        data = {
            "id": "m2",
            "name": "compression",
            "category": "context_compression",
            "description": "Compresses tokens",
            "evidence_files": ["c.md"],
            "estimated_token_impact": -50,
            "confidence": 0.6,
        }
        mech = AgentMechanism.from_dict(data)
        assert mech.id == "m2"
        assert mech.category == "context_compression"
        assert mech.evidence_files == ["c.md"]

    def test_from_dict_defaults(self) -> None:
        mech = AgentMechanism.from_dict({"id": "m3"})
        assert mech.name == ""
        assert mech.evidence_files == []
        assert mech.estimated_token_impact == 0
        assert mech.confidence == 0.0

    def test_roundtrip(self) -> None:
        original = AgentMechanism(
            id="rt",
            name="roundtrip",
            category="distribution",
            description="Round trip test",
            evidence_files=["x.md"],
            estimated_token_impact=200,
            confidence=0.9,
        )
        restored = AgentMechanism.from_dict(original.to_dict())
        assert restored.to_dict() == original.to_dict()


class TestContextEconomics:
    """Tests for ContextEconomics dataclass serialization."""

    def test_to_dict(self) -> None:
        econ = ContextEconomics(
            overhead_tokens=500,
            estimated_savings_ratio=0.15,
            mechanism_count=3,
            agent_facing_files=4,
            total_agent_context_tokens=500,
            break_even_interactions=7,
        )
        d = econ.to_dict()
        assert d["overhead_tokens"] == 500
        assert d["estimated_savings_ratio"] == 0.15
        assert d["break_even_interactions"] == 7

    def test_from_dict(self) -> None:
        econ = ContextEconomics.from_dict(
            {
                "overhead_tokens": 1000,
                "estimated_savings_ratio": 0.25,
            }
        )
        assert econ.overhead_tokens == 1000
        assert econ.mechanism_count == 0

    def test_from_dict_empty(self) -> None:
        econ = ContextEconomics.from_dict({})
        assert econ.overhead_tokens == 0
        assert econ.estimated_savings_ratio == 0.0

    def test_roundtrip(self) -> None:
        original = ContextEconomics(
            overhead_tokens=100,
            estimated_savings_ratio=0.5,
            mechanism_count=2,
            agent_facing_files=3,
            total_agent_context_tokens=100,
            break_even_interactions=2,
        )
        restored = ContextEconomics.from_dict(original.to_dict())
        assert restored.to_dict() == original.to_dict()


class TestAgentImpactReport:
    """Tests for AgentImpactReport dataclass serialization."""

    def test_to_dict(self) -> None:
        report = AgentImpactReport(
            target="/repo",
            mechanisms=[AgentMechanism(id="m1", name="x", category="safety", description="d")],
            economics=ContextEconomics(overhead_tokens=10),
            agent_facing_artifacts=["a.md"],
            findings=[Finding(id="f1", severity="info", message="test")],
            knowledge_units=[KnowledgeUnit(id="ku1")],
        )
        d = report.to_dict()
        assert d["target"] == "/repo"
        assert len(d["mechanisms"]) == 1
        assert d["economics"]["overhead_tokens"] == 10
        assert d["agent_facing_artifacts"] == ["a.md"]
        assert len(d["findings"]) == 1
        assert len(d["knowledge_units"]) == 1

    def test_from_dict(self) -> None:
        data = {
            "target": "/test",
            "mechanisms": [{"id": "m1", "name": "n", "category": "c", "description": "d"}],
            "economics": {"overhead_tokens": 50},
            "agent_facing_artifacts": ["b.md"],
            "findings": [{"id": "f1"}],
            "knowledge_units": [{"id": "ku1"}],
        }
        report = AgentImpactReport.from_dict(data)
        assert report.target == "/test"
        assert len(report.mechanisms) == 1
        assert report.economics.overhead_tokens == 50
        assert len(report.findings) == 1

    def test_from_dict_minimal(self) -> None:
        report = AgentImpactReport.from_dict({"target": "/x"})
        assert report.mechanisms == []
        assert report.economics.overhead_tokens == 0
        assert report.findings == []

    def test_roundtrip(self) -> None:
        original = AgentImpactReport(
            target="/repo",
            mechanisms=[AgentMechanism(id="m1", name="n", category="c", description="d")],
            agent_facing_artifacts=["a.md", "b.md"],
        )
        restored = AgentImpactReport.from_dict(original.to_dict())
        assert restored.to_dict() == original.to_dict()


class TestDiscoverAgentArtifacts:
    """Tests for _discover_agent_artifacts."""

    def test_finds_agent_files(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        assert len(artifacts) >= 3
        artifact_set = set(artifacts)
        assert "CLAUDE.md" in artifact_set
        assert "AGENTS.md" in artifact_set
        assert any("SKILL.md" in a for a in artifacts)
        assert any(".cursor/rules/" in a for a in artifacts)

    def test_skips_git_directory(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        assert not any(".git" in a for a in artifacts)

    def test_skips_node_modules(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        assert not any("node_modules" in a for a in artifacts)

    def test_empty_repo(self, analyzer: AgentImpactAnalyzer, empty_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(empty_repo)
        assert artifacts == []

    def test_single_file_match(self, analyzer: AgentImpactAnalyzer, tmp_path: Path) -> None:
        f = tmp_path / "CLAUDE.md"
        f.write_text("instructions")
        artifacts = analyzer._discover_agent_artifacts(f)
        assert len(artifacts) == 1

    def test_single_file_no_match(self, analyzer: AgentImpactAnalyzer, tmp_path: Path) -> None:
        f = tmp_path / "README.md"
        f.write_text("hello")
        artifacts = analyzer._discover_agent_artifacts(f)
        assert artifacts == []

    def test_results_are_sorted(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        assert artifacts == sorted(artifacts)


class TestEstimateContextEconomics:
    """Tests for _estimate_context_economics."""

    def test_economics_with_artifacts(
        self,
        analyzer: AgentImpactAnalyzer,
        agent_repo: Path,
    ) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        econ = analyzer._estimate_context_economics(agent_repo, artifacts)
        assert econ.agent_facing_files == len(artifacts)
        assert econ.total_agent_context_tokens > 0
        assert econ.overhead_tokens > 0
        assert econ.estimated_savings_ratio > 0

    def test_economics_empty_artifacts(self, analyzer: AgentImpactAnalyzer, tmp_path: Path) -> None:
        econ = analyzer._estimate_context_economics(tmp_path, [])
        assert econ.agent_facing_files == 0
        assert econ.total_agent_context_tokens == 0
        assert econ.overhead_tokens == 0
        assert econ.estimated_savings_ratio == 0.0
        assert econ.break_even_interactions == 0

    def test_savings_ratio_capped(self, analyzer: AgentImpactAnalyzer, tmp_path: Path) -> None:
        many_artifacts = []
        for i in range(30):
            f = tmp_path / f"CLAUDE_{i}.md"
            f.write_text("instructions " * 50)
            many_artifacts.append(f"CLAUDE_{i}.md")
        econ = analyzer._estimate_context_economics(tmp_path, many_artifacts)
        assert econ.estimated_savings_ratio <= 0.95


class TestDetectMechanisms:
    """Tests for _detect_mechanisms."""

    def test_detects_behavioral(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        mechanisms = analyzer._detect_mechanisms(agent_repo, artifacts)
        categories = {m.category for m in mechanisms}
        assert "behavioral_instruction" in categories

    def test_detects_safety(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        mechanisms = analyzer._detect_mechanisms(agent_repo, artifacts)
        categories = {m.category for m in mechanisms}
        assert "safety" in categories

    def test_mechanisms_have_evidence(
        self,
        analyzer: AgentImpactAnalyzer,
        agent_repo: Path,
    ) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        mechanisms = analyzer._detect_mechanisms(agent_repo, artifacts)
        for mech in mechanisms:
            assert len(mech.evidence_files) > 0
            assert mech.confidence > 0
            assert mech.description != ""
            assert mech.id.startswith("mech-")

    def test_no_mechanisms_empty(self, analyzer: AgentImpactAnalyzer, tmp_path: Path) -> None:
        mechanisms = analyzer._detect_mechanisms(tmp_path, [])
        assert mechanisms == []


class TestGenerateFindings:
    """Tests for _generate_findings."""

    def test_findings_for_agent_repo(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        econ = analyzer._estimate_context_economics(agent_repo, artifacts)
        mechanisms = analyzer._detect_mechanisms(agent_repo, artifacts)
        findings = analyzer._generate_findings(mechanisms, econ, artifacts)
        assert len(findings) > 0
        assert all(isinstance(f, Finding) for f in findings)
        categories = {f.category for f in findings}
        assert "agent_impact" in categories

    def test_findings_for_empty_repo(self, analyzer: AgentImpactAnalyzer) -> None:
        findings = analyzer._generate_findings([], ContextEconomics(), [])
        assert any("No Agent-facing artifacts" in f.message for f in findings)

    def test_findings_ids_unique(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        artifacts = analyzer._discover_agent_artifacts(agent_repo)
        econ = analyzer._estimate_context_economics(agent_repo, artifacts)
        mechanisms = analyzer._detect_mechanisms(agent_repo, artifacts)
        findings = analyzer._generate_findings(mechanisms, econ, artifacts)
        ids = [f.id for f in findings]
        assert len(ids) == len(set(ids))

    def test_high_overhead_warning(self, analyzer: AgentImpactAnalyzer) -> None:
        econ = ContextEconomics(
            overhead_tokens=10000,
            total_agent_context_tokens=10000,
            agent_facing_files=1,
        )
        findings = analyzer._generate_findings([], econ, ["big.md"])
        severities = {f.severity for f in findings}
        assert "warning" in severities


class TestCreateKnowledgeUnits:
    """Tests for _create_knowledge_units."""

    def test_units_from_mechanisms(self, analyzer: AgentImpactAnalyzer) -> None:
        mechs = [
            AgentMechanism(
                id="m1",
                name="rules",
                category="behavioral_instruction",
                description="desc",
                evidence_files=["a.md"],
                confidence=0.8,
            ),
        ]
        units = analyzer._create_knowledge_units(mechs, ["a.md"])
        assert len(units) == 2
        mech_units = [u for u in units if u.unit_type == "agent_mechanism"]
        summary_units = [u for u in units if u.unit_type == "agent_impact_summary"]
        assert len(mech_units) == 1
        assert len(summary_units) == 1

    def test_units_empty(self, analyzer: AgentImpactAnalyzer) -> None:
        units = analyzer._create_knowledge_units([], [])
        assert units == []

    def test_summary_references_mechanisms(self, analyzer: AgentImpactAnalyzer) -> None:
        mechs = [
            AgentMechanism(id="m1", name="a", category="safety", description="d"),
            AgentMechanism(id="m2", name="b", category="distribution", description="d"),
        ]
        units = analyzer._create_knowledge_units(mechs, ["x.md"])
        summary = next(u for u in units if u.unit_type == "agent_impact_summary")
        assert len(summary.relationships["mechanisms"]) == 2


class TestEstimateTokens:
    """Tests for the static _estimate_tokens method."""

    def test_empty_string(self) -> None:
        assert AgentImpactAnalyzer._estimate_tokens("") == 0

    def test_single_word(self) -> None:
        assert AgentImpactAnalyzer._estimate_tokens("hello") == 1

    def test_multiple_words(self) -> None:
        result = AgentImpactAnalyzer._estimate_tokens("one two three four five")
        assert result == int(5 * 1.3)

    def test_whitespace_only(self) -> None:
        assert AgentImpactAnalyzer._estimate_tokens("   ") == 0


class TestReadFileSafe:
    """Tests for the static _read_file_safe method."""

    def test_reads_normal_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        assert AgentImpactAnalyzer._read_file_safe(f) == "hello world"

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        result = AgentImpactAnalyzer._read_file_safe(tmp_path / "nope.txt")
        assert result == ""

    def test_directory_path(self, tmp_path: Path) -> None:
        result = AgentImpactAnalyzer._read_file_safe(tmp_path)
        assert result == ""


class TestAnalyzeEndToEnd:
    """End-to-end tests for the analyze method."""

    def test_analyze_agent_repo(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        report = analyzer.analyze(agent_repo)
        assert report.target == str(agent_repo)
        assert len(report.agent_facing_artifacts) >= 3
        assert len(report.mechanisms) > 0
        assert report.economics.agent_facing_files > 0
        assert report.economics.total_agent_context_tokens > 0
        assert report.economics.mechanism_count == len(report.mechanisms)
        assert report.economics.overhead_tokens > 0
        assert len(report.findings) > 0
        assert len(report.knowledge_units) > 0

    def test_analyze_empty_repo(self, analyzer: AgentImpactAnalyzer, empty_repo: Path) -> None:
        report = analyzer.analyze(empty_repo)
        assert report.target == str(empty_repo)
        assert report.agent_facing_artifacts == []
        assert report.mechanisms == []
        assert report.economics.agent_facing_files == 0
        assert any("No Agent-facing" in f.message for f in report.findings)

    def test_report_serialization(self, analyzer: AgentImpactAnalyzer, agent_repo: Path) -> None:
        report = analyzer.analyze(agent_repo)
        data = report.to_dict()
        restored = AgentImpactReport.from_dict(data)
        assert restored.target == report.target
        assert len(restored.mechanisms) == len(report.mechanisms)
        assert len(restored.findings) == len(report.findings)
        assert restored.economics.overhead_tokens == report.economics.overhead_tokens

    def test_analyze_single_agent_file(self, analyzer: AgentImpactAnalyzer, tmp_path: Path) -> None:
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Instructions\nAlways follow safety rules.\n")
        report = analyzer.analyze(f)
        assert len(report.agent_facing_artifacts) == 1

    def test_economics_enriched_with_mechanisms(
        self,
        analyzer: AgentImpactAnalyzer,
        agent_repo: Path,
    ) -> None:
        report = analyzer.analyze(agent_repo)
        assert report.economics.mechanism_count > 0
        assert report.economics.mechanism_count == len(report.mechanisms)
        total_mech_tokens = sum(abs(m.estimated_token_impact) for m in report.mechanisms)
        assert report.economics.total_agent_context_tokens >= total_mech_tokens

    def test_economics_minimum_estimate_fallback(
        self,
        analyzer: AgentImpactAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Empty agent files still get a minimum token estimate."""
        f = tmp_path / "AGENTS.md"
        f.write_text("")
        report = analyzer.analyze(tmp_path)
        assert len(report.agent_facing_artifacts) >= 1
        assert report.economics.overhead_tokens > 0
        assert report.economics.total_agent_context_tokens > 0

    def test_economics_to_dict_always_populated(
        self,
        analyzer: AgentImpactAnalyzer,
        agent_repo: Path,
    ) -> None:
        report = analyzer.analyze(agent_repo)
        d = report.economics.to_dict()
        assert isinstance(d, dict)
        assert len(d) > 0
        assert "overhead_tokens" in d
        assert "mechanism_count" in d
        assert d["mechanism_count"] > 0

    def test_pyproject_toml_detected(
        self,
        analyzer: AgentImpactAnalyzer,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.nines]\nrules = true\n")
        artifacts = analyzer._discover_agent_artifacts(tmp_path)
        assert any("pyproject.toml" in a for a in artifacts)

    def test_analyze_nonexistent_path(self, analyzer: AgentImpactAnalyzer, tmp_path: Path) -> None:
        report = analyzer.analyze(tmp_path / "nonexistent")
        assert report.agent_facing_artifacts == []
        assert report.mechanisms == []


class TestC11aDiversification:
    """C11a (v3.2.3) tests — rule-based MechanismDetector replaces v3.2.2's
    hard-coded ``always-fire`` 5-mechanism path.

    These pin the contract that:

    1. Different evidence inputs → different mechanism subsets (the §4.3 fix).
    2. The legacy 5 mechanism names remain available (backward compat for
       downstream consumers that filter by name).
    3. Rules whose confidence falls at or below ``min_confidence`` are not
       emitted.
    """

    def test_three_evidence_inputs_yield_three_subsets(
        self,
        analyzer: AgentImpactAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Three distinct repos must produce three distinct mechanism
        subsets — the central regression guard for the §4.3 ``every repo
        emits the same 5 mechanisms with confidence 1.0`` baseline."""
        # Repo 1 — pure compression skill (caveman-style).
        repo1 = tmp_path / "repo1"
        repo1.mkdir()
        (repo1 / "SKILL.md").write_text(
            "# Caveman compression skill\n"
            "Always compress every token. Never use verbose phrasing.\n"
            "Style: terse, concise, abbreviate aggressively.\n"
            "Safety fallback: restore on warning. Backup the original.\n"
        )

        # Repo 2 — workflow with explicit churn-aware routing + active
        # forgetting + cross-checking.
        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        (repo2 / "AGENTS.md").write_text(
            "# Workflow framework\n"
            "Always sync rules across platforms. Deploy via CI workflow.\n"
            "Drift prevention enforces invariants and constraints.\n"
            "Prune stale memory entries; expire context older than the TTL.\n"
            "Cache invalidation triggers a freshness check on outdated docs.\n"
            "Run a consistency check; cross-check the audit findings.\n"
        )

        # Repo 3 — RAG plugin with reasoning-depth flag + skillbook.
        repo3 = tmp_path / "repo3"
        repo3.mkdir()
        (repo3 / "CLAUDE.md").write_text(
            "# RAG plugin\n"
            "Provides multi-pass step-by-step retrieval with extended thinking.\n"
            "Maintains a skillbook of learned strategies, evolving via in-context learn.\n"
        )

        rep1 = analyzer.analyze(repo1)
        rep2 = analyzer.analyze(repo2)
        rep3 = analyzer.analyze(repo3)

        names1 = {m.name for m in rep1.mechanisms}
        names2 = {m.name for m in rep2.mechanisms}
        names3 = {m.name for m in rep3.mechanisms}

        # Each repo emits a different mechanism subset (no two are equal).
        assert names1 != names2
        assert names2 != names3
        assert names1 != names3

        # Repo 2 is the only one with churn-aware routing (the central
        # ContextOS-derived mechanism the v3.2.2 detector cannot see).
        assert "churn_aware_routing" in names2
        assert "churn_aware_routing" not in names1
        assert "churn_aware_routing" not in names3

        # Repo 3 is the only one with skillbook_evolution.
        assert "skillbook_evolution" in names3
        assert "skillbook_evolution" not in names1
        assert "skillbook_evolution" not in names2

    def test_legacy_five_names_remain_available(self) -> None:
        """The original 5 mechanism names from v3.2.2 must remain emittable
        so downstream consumers that filter by name see no breaking change."""
        from nines.analyzer.agent_impact import MechanismDetector

        det = MechanismDetector()
        names = {r.name for r in det.rules}
        legacy = {
            "behavioral_rules",
            "token_compression",
            "safety_guardrails",
            "multi_platform_sync",
            "drift_prevention",
        }
        assert legacy <= names

    def test_low_confidence_mechanism_filtered_out(self, tmp_path: Path) -> None:
        """A rule whose confidence falls at/under ``min_confidence`` (e.g.
        because counter-indicators dominate) must NOT appear in the
        analyzer's output."""
        from nines.analyzer.agent_impact import (
            AgentImpactAnalyzer,
            MechanismDetector,
        )
        from nines.analyzer.mechanism_rules import MechanismRule

        # A rule that demands ``a, b`` indicators and is heavily penalised by
        # the ``X``-style counter-indicators that dominate the file.  Even
        # when the predicate fires, the score should drop below the gate.
        custom_rule = MechanismRule(
            name="sensitive_rule",
            category="custom",
            description="d",
            indicators=("a", "b"),
            counter_indicators=("nope1", "nope2", "nope3", "nope4"),
            min_indicator_hits_per_file=2,
            min_confidence=0.99,  # impossibly high gate
        )
        det = MechanismDetector(rules=[custom_rule])
        analyzer = AgentImpactAnalyzer(mechanism_detector=det)

        (tmp_path / "AGENTS.md").write_text(
            "a and b appear here together with nope1 nope2 nope3 nope4 nope1"
        )
        report = analyzer.analyze(tmp_path)
        names = {m.name for m in report.mechanisms}
        # Gated out → not emitted.
        assert "sensitive_rule" not in names
