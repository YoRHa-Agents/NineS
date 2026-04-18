"""Tests for the C09 derived ``ContextEconomics`` formula.

Covers the new ``per_interaction_savings_tokens`` /
``expected_retention_rate`` / ``mechanism_diversity_factor`` /
``economics_score`` fields and asserts that ``break_even_interactions``
is now a real function of overhead vs savings, no longer the constant
``2`` reported in baseline §4.6.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.analyzer.agent_impact import (  # noqa: E402
    AgentImpactAnalyzer,
    AgentMechanism,
    ContextEconomics,
)


def _mech(name: str, category: str, tokens: int, *, confidence: float = 1.0) -> AgentMechanism:
    """Build a minimal AgentMechanism for tests."""
    return AgentMechanism(
        id=f"mech-{name}",
        name=name,
        category=category,
        description="",
        evidence_files=["fake.md"],
        estimated_token_impact=tokens,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Happy paths — derivation works
# ---------------------------------------------------------------------------


def test_no_artifacts_no_mechanisms_yields_zero_break_even(tmp_path: Path) -> None:
    """An empty repo produces zero overhead, zero savings, zero break-even."""
    eco = AgentImpactAnalyzer()._estimate_context_economics(tmp_path, [])
    assert eco.overhead_tokens == 0
    assert eco.break_even_interactions == 0
    assert eco.economics_score == 0.0
    assert eco.formula_version == 2


def test_break_even_uses_real_savings(tmp_path: Path) -> None:
    """When mechanisms supply 6919-token savings on 41343 overhead, break_even
    must equal ceil(41343/6919) = 6 (not the legacy constant 2)."""
    artifact = tmp_path / "BIG.md"
    # ~41343-token target; 1.3 tok/word → ~31800 words; use a stable
    # lorem-ipsum repetition.
    artifact.write_text("lorem ipsum dolor sit amet " * 6360)
    mechs = [
        _mech("token_compression", "context_compression", -6919),
        _mech("behavioral_rules", "behavioral_instruction", 1000),
    ]
    eco = AgentImpactAnalyzer()._estimate_context_economics(
        tmp_path,
        ["BIG.md"],
        mechs,
    )
    assert eco.per_interaction_savings_tokens == 6919
    assert eco.break_even_interactions == math.ceil(eco.overhead_tokens / 6919)
    # Crucially: NOT the legacy constant 2.
    assert eco.break_even_interactions != 2


def test_break_even_distinct_per_overhead_savings(tmp_path: Path) -> None:
    """Same savings, different overhead → different break_even values."""
    a = tmp_path / "small.md"
    a.write_text("foo " * 10_000)
    b = tmp_path / "large.md"
    b.write_text("foo " * 100_000)
    mechs = [_mech("compress", "context_compression", -1000)]
    eco_a = AgentImpactAnalyzer()._estimate_context_economics(
        tmp_path,
        ["small.md"],
        mechs,
    )
    eco_b = AgentImpactAnalyzer()._estimate_context_economics(
        tmp_path,
        ["large.md"],
        mechs,
    )
    assert eco_a.break_even_interactions != eco_b.break_even_interactions
    assert eco_b.break_even_interactions > eco_a.break_even_interactions


def test_economics_score_reflects_mechanism_diversity(tmp_path: Path) -> None:
    """Diverse mechanism categories raise the score for the same savings."""
    (tmp_path / "f.md").write_text("hello " * 5000)
    base = [_mech("compress", "context_compression", -1000)]
    diverse = base + [
        _mech("rules", "behavioral_instruction", 500),
        _mech("safety", "safety", 300),
    ]
    eco_base = AgentImpactAnalyzer()._estimate_context_economics(
        tmp_path,
        ["f.md"],
        base,
    )
    eco_div = AgentImpactAnalyzer()._estimate_context_economics(
        tmp_path,
        ["f.md"],
        diverse,
    )
    assert eco_div.mechanism_diversity_factor > eco_base.mechanism_diversity_factor
    # economics_score scales with diversity_factor (within clamp range).
    assert eco_div.economics_score >= eco_base.economics_score


def test_economics_score_clamped_to_unit_interval(tmp_path: Path) -> None:
    """When savings dwarf overhead, economics_score is clamped to 1.0."""
    (tmp_path / "tiny.md").write_text("a")
    mechs = [_mech("compress", "context_compression", -10_000_000)]
    eco = AgentImpactAnalyzer()._estimate_context_economics(
        tmp_path,
        ["tiny.md"],
        mechs,
    )
    assert 0.0 <= eco.economics_score <= 1.0


def test_legacy_call_signature_no_mechanisms_uses_fallback(tmp_path: Path) -> None:
    """When called without mechanisms (legacy path), the v1-compatible
    ratio fallback fires so existing callers don't break."""
    (tmp_path / "AGENTS.md").write_text("ai " * 1000)
    eco = AgentImpactAnalyzer()._estimate_context_economics(
        tmp_path,
        ["AGENTS.md"],
    )
    # Fallback ratio: min(0.95, 1*0.05)=0.05 → savings ≈ 5% of overhead.
    assert eco.per_interaction_savings_tokens > 0
    assert eco.formula_version == 2  # always v2 for new analyses


def test_zero_savings_yields_overhead_sized_break_even(tmp_path: Path) -> None:
    """No compression mechanism + no fallback → break_even = overhead/1."""
    (tmp_path / "x.md").write_text("hi " * 100)
    mechs = [_mech("rules", "behavioral_instruction", 200)]  # no compression
    eco = AgentImpactAnalyzer()._estimate_context_economics(
        tmp_path,
        ["x.md"],
        mechs,
    )
    assert eco.per_interaction_savings_tokens == 0
    # break_even = ceil(overhead / max(0, 1)) = overhead
    assert eco.break_even_interactions == eco.overhead_tokens


# ---------------------------------------------------------------------------
# Schema round-trip
# ---------------------------------------------------------------------------


def test_to_dict_includes_c09_fields() -> None:
    """``ContextEconomics.to_dict`` exposes all C09 fields."""
    eco = ContextEconomics(
        overhead_tokens=1000,
        per_interaction_savings_tokens=200,
        expected_retention_rate=0.85,
        mechanism_diversity_factor=1.2,
        economics_score=0.42,
        formula_version=2,
    )
    d = eco.to_dict()
    assert d["per_interaction_savings_tokens"] == 200
    assert d["expected_retention_rate"] == 0.85
    assert d["mechanism_diversity_factor"] == 1.2
    assert d["economics_score"] == 0.42
    assert d["formula_version"] == 2


def test_from_dict_legacy_v1_report_defaults_filled() -> None:
    """A formula_version=1 report parses without error and gets defaults."""
    legacy = {
        "overhead_tokens": 1000,
        "estimated_savings_ratio": 0.6,
        "mechanism_count": 5,
        "agent_facing_files": 12,
        "total_agent_context_tokens": 1000,
        "break_even_interactions": 2,
    }
    eco = ContextEconomics.from_dict(legacy)
    assert eco.formula_version == 1  # preserved
    assert eco.expected_retention_rate == 0.85  # default filled
    assert eco.per_interaction_savings_tokens == 0  # default
