"""Tests for the rule-based mechanism detection registry (C11a — v3.2.3).

Covers:

- Per-rule predicate fires on positive evidence and skips on negative.
- Confidence scoring stays in ``[0.0, 1.0]`` and respects the ``min_confidence``
  emission gate.
- Counter-indicators drag the score down.
- :class:`MechanismDetector` defaults to the bundled
  ``DEFAULT_MECHANISM_RULES``, supports custom rule subsets, dedupes by rule
  name, returns ``[]`` on empty inputs, and emits sorted results.
- The legacy 5 mechanism rules are present (backward-compat sanity).
- The 6 new ContextOS rules are present and tagged ``source="contextos"``.
- Magnitude estimator returns the right sign for compression rules.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — used at runtime by helpers and fixtures

import pytest

from nines.analyzer.agent_impact import AgentMechanism, MechanismDetector
from nines.analyzer.mechanism_rules import (
    DEFAULT_MECHANISM_RULES,
    FileMatch,
    MechanismRule,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(target: Path, rel_path: str, content: str) -> str:
    """Write a file under ``target`` and return its repository-relative path."""
    fp = target / rel_path
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    return rel_path


# ---------------------------------------------------------------------------
# FileMatch
# ---------------------------------------------------------------------------


class TestFileMatch:
    """Tests for the FileMatch density helper."""

    def test_density_basic(self) -> None:
        match = FileMatch(path="x.md", indicator_hits=4, counter_hits=0, content_length=2000)
        # 4 hits per 2 000 chars = 2.0 hits per 1 000
        assert match.density == pytest.approx(2.0)

    def test_density_zero_content(self) -> None:
        match = FileMatch(path="x.md", indicator_hits=2, counter_hits=0, content_length=0)
        assert match.density == 0.0


# ---------------------------------------------------------------------------
# MechanismRule
# ---------------------------------------------------------------------------


class TestMechanismRulePredicate:
    """Tests that ``match_file`` / ``evidence_predicate`` honour thresholds."""

    def test_predicate_fires_on_positive_evidence(self) -> None:
        rule = MechanismRule(
            name="r1",
            category="cat",
            description="d",
            indicators=("alpha", "beta", "gamma"),
            min_indicator_hits_per_file=2,
        )
        m = rule.match_file("x.md", "alpha is followed by beta and friends")
        assert m is not None
        assert m.indicator_hits == 2
        assert rule.evidence_predicate([m]) is True

    def test_predicate_skips_below_threshold(self) -> None:
        """A single hit when min=2 must not fire."""
        rule = MechanismRule(
            name="r1",
            category="cat",
            description="d",
            indicators=("alpha", "beta"),
            min_indicator_hits_per_file=2,
        )
        # Only "alpha" present → 1 hit < 2 → no FileMatch
        assert rule.match_file("x.md", "alpha only") is None

    def test_predicate_skips_when_no_files_match(self) -> None:
        rule = MechanismRule(
            name="r1",
            category="cat",
            description="d",
            indicators=("alpha", "beta"),
        )
        assert rule.evidence_predicate([]) is False

    def test_path_hint_acts_as_synthetic_hit(self) -> None:
        """Path-hint adds 1 hit so a single-keyword match passes when in
        a recognised path."""
        rule = MechanismRule(
            name="r1",
            category="cat",
            description="d",
            indicators=("alpha",),
            path_hints=(".cursor/",),
            min_indicator_hits_per_file=2,
        )
        # "alpha" alone = 1 hit + .cursor/ path bonus = 2 → fires
        assert rule.match_file(".cursor/rules.md", "alpha rule") is not None
        # Without the path bonus → only 1 hit → does not fire
        assert rule.match_file("README.md", "alpha rule") is None

    def test_min_files_aggregate_threshold(self) -> None:
        rule = MechanismRule(
            name="r1",
            category="cat",
            description="d",
            indicators=("alpha", "beta"),
            min_indicator_hits_per_file=2,
            min_files=2,
        )
        m1 = rule.match_file("a.md", "alpha and beta")
        assert m1 is not None
        # Only 1 file matched but min_files=2 → predicate should be False
        assert rule.evidence_predicate([m1]) is False
        m2 = rule.match_file("b.md", "alpha then beta")
        assert m2 is not None
        assert rule.evidence_predicate([m1, m2]) is True


class TestMechanismRuleConfidence:
    """Tests for confidence scoring."""

    def test_confidence_no_matches_is_zero(self) -> None:
        rule = MechanismRule(
            name="r1", category="c", description="d", indicators=("x",),
        )
        assert rule.confidence_estimator([]) == 0.0

    def test_confidence_in_range(self) -> None:
        """Score must always land in [0.0, 1.0]."""
        rule = MechanismRule(
            name="r1",
            category="c",
            description="d",
            indicators=("a", "b", "c", "d", "e"),
        )
        match = FileMatch(path="x.md", indicator_hits=5, counter_hits=0, content_length=1000)
        score = rule.confidence_estimator([match])
        assert 0.0 <= score <= 1.0

    def test_confidence_above_min_for_predicate_passing(self) -> None:
        """Single predicate-passing match should clear the 0.30 emission gate."""
        rule = MechanismRule(
            name="r1",
            category="c",
            description="d",
            indicators=("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"),
            min_indicator_hits_per_file=2,
        )
        match = FileMatch(path="x.md", indicator_hits=2, counter_hits=0, content_length=1000)
        score = rule.confidence_estimator([match])
        assert score > rule.min_confidence

    def test_confidence_counter_indicator_penalty(self) -> None:
        """Counter-indicator hits must lower confidence below the no-counter case."""
        rule = MechanismRule(
            name="r1",
            category="c",
            description="d",
            indicators=("a", "b", "c"),
        )
        good = FileMatch(path="x.md", indicator_hits=2, counter_hits=0, content_length=1000)
        bad = FileMatch(path="x.md", indicator_hits=2, counter_hits=3, content_length=1000)
        assert rule.confidence_estimator([bad]) < rule.confidence_estimator([good])


class TestMagnitudeEstimator:
    """Tests for magnitude_estimator sign + magnitude."""

    def test_positive_sign_default(self) -> None:
        rule = MechanismRule(
            name="r1", category="c", description="d", indicators=("a",), token_impact_sign=1,
        )
        assert rule.magnitude_estimator(500) == 500

    def test_negative_sign_for_compression(self) -> None:
        rule = MechanismRule(
            name="r1", category="context_compression", description="d",
            indicators=("a",), token_impact_sign=-1,
        )
        assert rule.magnitude_estimator(500) == -500

    def test_returns_int(self) -> None:
        rule = MechanismRule(
            name="r1", category="c", description="d", indicators=("a",),
        )
        result = rule.magnitude_estimator(123)
        assert isinstance(result, int)

    def test_zero_tokens_yields_zero(self) -> None:
        rule = MechanismRule(
            name="r1", category="c", description="d", indicators=("a",),
        )
        assert rule.magnitude_estimator(0) == 0


# ---------------------------------------------------------------------------
# Default registry sanity
# ---------------------------------------------------------------------------


class TestDefaultRegistry:
    """The bundled rule set must keep its shape so reports stay stable."""

    def test_default_count(self) -> None:
        assert len(DEFAULT_MECHANISM_RULES) == 11

    def test_legacy_five_present(self) -> None:
        legacy_names = {
            "behavioral_rules",
            "token_compression",
            "safety_guardrails",
            "multi_platform_sync",
            "drift_prevention",
        }
        names = {r.name for r in DEFAULT_MECHANISM_RULES}
        assert legacy_names <= names

    def test_legacy_rules_tagged_legacy(self) -> None:
        legacy = {r.name for r in DEFAULT_MECHANISM_RULES if r.source == "legacy"}
        assert legacy == {
            "behavioral_rules",
            "token_compression",
            "safety_guardrails",
            "multi_platform_sync",
            "drift_prevention",
        }

    def test_six_new_contextos_rules_present(self) -> None:
        new_names = {
            "active_forgetting",
            "reasoning_depth_calibration",
            "productive_contradiction",
            "churn_aware_routing",
            "self_healing_index",
            "skillbook_evolution",
        }
        names = {r.name for r in DEFAULT_MECHANISM_RULES}
        assert new_names <= names

    def test_contextos_rules_tagged_source(self) -> None:
        contextos = {r.name for r in DEFAULT_MECHANISM_RULES if r.source == "contextos"}
        assert contextos == {
            "active_forgetting",
            "reasoning_depth_calibration",
            "productive_contradiction",
            "churn_aware_routing",
            "self_healing_index",
            "skillbook_evolution",
        }

    def test_token_compression_negative_sign(self) -> None:
        compression = next(
            r for r in DEFAULT_MECHANISM_RULES if r.name == "token_compression"
        )
        assert compression.token_impact_sign == -1

    def test_all_rules_have_indicators(self) -> None:
        for rule in DEFAULT_MECHANISM_RULES:
            assert rule.indicators, f"rule {rule.name} has no indicators"

    def test_all_rules_min_confidence_at_least_03(self) -> None:
        """Per design — min_confidence gate sits at 0.30."""
        for rule in DEFAULT_MECHANISM_RULES:
            assert rule.min_confidence >= 0.3, rule.name


# ---------------------------------------------------------------------------
# MechanismDetector
# ---------------------------------------------------------------------------


class TestMechanismDetectorBasics:
    """Detector construction + emission semantics."""

    def test_default_constructor_uses_default_rules(self) -> None:
        det = MechanismDetector()
        assert det.rules == DEFAULT_MECHANISM_RULES

    def test_custom_rules_subset(self) -> None:
        custom = [
            MechanismRule(
                name="only_one",
                category="custom",
                description="only one rule",
                indicators=("anything",),
            ),
        ]
        det = MechanismDetector(rules=custom)
        assert len(det.rules) == 1
        assert det.rules[0].name == "only_one"

    def test_empty_rules_emits_no_mechanisms(self, tmp_path: Path) -> None:
        det = MechanismDetector(rules=[])
        _write(tmp_path, "CLAUDE.md", "any content")
        result = det.detect(tmp_path, ["CLAUDE.md"])
        assert result == []

    def test_no_artifacts_returns_empty(self, tmp_path: Path) -> None:
        det = MechanismDetector()
        assert det.detect(tmp_path, []) == []

    def test_duplicate_rule_names_rejected(self) -> None:
        dup = [
            MechanismRule(name="x", category="c", description="d", indicators=("a",)),
            MechanismRule(name="x", category="c2", description="d2", indicators=("b",)),
        ]
        with pytest.raises(ValueError, match="duplicate"):
            MechanismDetector(rules=dup)


class TestMechanismDetectorEmission:
    """Detector produces expected AgentMechanism objects."""

    def test_emits_one_mechanism_per_passing_rule(self, tmp_path: Path) -> None:
        det = MechanismDetector(
            rules=[
                MechanismRule(
                    name="alpha_rule",
                    category="catA",
                    description="Alpha mechanism",
                    indicators=("alpha", "beta"),
                ),
            ],
        )
        _write(tmp_path, "AGENTS.md", "alpha and beta both appear here")
        result = det.detect(tmp_path, ["AGENTS.md"])
        assert len(result) == 1
        mech = result[0]
        assert isinstance(mech, AgentMechanism)
        assert mech.name == "alpha_rule"
        assert mech.category == "catA"
        assert mech.evidence_files == ["AGENTS.md"]
        assert mech.id.startswith("mech-")

    def test_skips_rule_with_no_evidence(self, tmp_path: Path) -> None:
        """If indicators are absent the rule must not appear in the output."""
        det = MechanismDetector(
            rules=[
                MechanismRule(
                    name="present_rule",
                    category="catP",
                    description="present",
                    indicators=("foo", "bar"),
                ),
                MechanismRule(
                    name="absent_rule",
                    category="catA",
                    description="absent",
                    indicators=("zzz_unrelated_word", "yyy_unrelated"),
                ),
            ],
        )
        _write(tmp_path, "doc.md", "foo plus bar yields a present mechanism")
        result = det.detect(tmp_path, ["doc.md"])
        names = {m.name for m in result}
        assert "present_rule" in names
        assert "absent_rule" not in names

    def test_emitted_confidence_above_min_gate(self, tmp_path: Path) -> None:
        det = MechanismDetector()
        _write(
            tmp_path,
            "CLAUDE.md",
            "You must always follow these rules and never skip the convention.",
        )
        result = det.detect(tmp_path, ["CLAUDE.md"])
        for mech in result:
            assert 0.30 < mech.confidence <= 1.0

    def test_results_sorted_by_category_name(self, tmp_path: Path) -> None:
        det = MechanismDetector(
            rules=[
                MechanismRule(
                    name="z_rule",
                    category="zoo",
                    description="d",
                    indicators=("foo",),
                    min_indicator_hits_per_file=1,
                ),
                MechanismRule(
                    name="a_rule",
                    category="ant",
                    description="d",
                    indicators=("foo",),
                    min_indicator_hits_per_file=1,
                ),
            ],
        )
        _write(tmp_path, "doc.md", "foo")
        result = det.detect(tmp_path, ["doc.md"])
        assert [m.category for m in result] == ["ant", "zoo"]

    def test_token_impact_sign_for_compression_negative(self, tmp_path: Path) -> None:
        det = MechanismDetector(
            rules=[
                MechanismRule(
                    name="comp_rule",
                    category="context_compression",
                    description="comp",
                    indicators=("compress", "token"),
                    token_impact_sign=-1,
                ),
            ],
        )
        _write(tmp_path, "doc.md", "compress every token aggressively when possible")
        result = det.detect(tmp_path, ["doc.md"])
        assert len(result) == 1
        assert result[0].estimated_token_impact <= 0

    def test_evidence_files_are_sorted_strings(self, tmp_path: Path) -> None:
        det = MechanismDetector(
            rules=[
                MechanismRule(
                    name="any_rule",
                    category="cat",
                    description="d",
                    indicators=("hit",),
                    min_indicator_hits_per_file=1,
                ),
            ],
        )
        _write(tmp_path, "z.md", "hit")
        _write(tmp_path, "a.md", "hit")
        _write(tmp_path, "m.md", "hit")
        result = det.detect(tmp_path, ["z.md", "a.md", "m.md"])
        assert result[0].evidence_files == ["a.md", "m.md", "z.md"]

    def test_dedup_by_rule_name(self, tmp_path: Path) -> None:
        """Even when multiple files match a rule, exactly one mechanism is emitted."""
        det = MechanismDetector(
            rules=[
                MechanismRule(
                    name="solo",
                    category="c",
                    description="d",
                    indicators=("hit",),
                    min_indicator_hits_per_file=1,
                ),
            ],
        )
        _write(tmp_path, "a.md", "hit me")
        _write(tmp_path, "b.md", "hit also")
        _write(tmp_path, "c.md", "hit too")
        result = det.detect(tmp_path, ["a.md", "b.md", "c.md"])
        assert len(result) == 1
        assert len(result[0].evidence_files) == 3
