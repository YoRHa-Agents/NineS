"""Tests for ``nines.eval.metrics_registry`` (C08 — Weighted MetricRegistry).

Covers
------

* :class:`MetricDefinition` field-level validation (positive weights,
  threshold ordering, default direction).
* :class:`MetricRegistry` register / get / metrics / groups.
* :meth:`MetricRegistry.weight_sum_for_group` over single + multi-group
  configurations.
* :meth:`MetricRegistry.normalized` for the no-threshold fallback,
  the MAXIMIZE band, the MINIMIZE band, the custom-normalizer override,
  and the unknown-name error path.
* :meth:`MetricRegistry.weighted_mean` for the basic case, the
  missing-score case (denominator excludes the missing weight), and
  the empty-group case.
* :meth:`MetricRegistry.validate` for the valid-config case, the
  weights-don't-sum case, and the negative-weight constructor guard.
* :meth:`MetricRegistry.from_toml` round-trip on the bundled
  ``data/self_eval_metrics.toml``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.eval.metrics_registry import (  # noqa: E402
    GROUPS_META_GROUP,
    Direction,
    MetricDefinition,
    MetricRegistry,
    default_registry_path,
    load_default_registry,
)

# ---------------------------------------------------------------------------
# MetricDefinition — field-level validation
# ---------------------------------------------------------------------------


def test_metric_definition_defaults() -> None:
    """Defaults match the spec: MAXIMIZE, group='default', no threshold."""
    defn = MetricDefinition(name="x", weight=0.5)
    assert defn.direction is Direction.MAXIMIZE
    assert defn.group == "default"
    assert defn.threshold is None
    assert defn.normalizer is None


def test_metric_definition_rejects_negative_weight() -> None:
    """Construction-time guard: weight < 0 raises ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        MetricDefinition(name="x", weight=-0.1)


def test_metric_definition_rejects_blank_name() -> None:
    """Construction-time guard: empty name raises ValueError."""
    with pytest.raises(ValueError, match="non-empty"):
        MetricDefinition(name="", weight=0.5)


def test_metric_definition_rejects_inverted_threshold() -> None:
    """Threshold (min, max) must satisfy min < max."""
    with pytest.raises(ValueError, match="min < max"):
        MetricDefinition(name="x", weight=0.5, threshold=(0.9, 0.5))


# ---------------------------------------------------------------------------
# MetricRegistry — register / lookup
# ---------------------------------------------------------------------------


def test_register_and_get() -> None:
    """register() inserts; get() returns the same definition; unknown → None."""
    r = MetricRegistry()
    defn = MetricDefinition(name="alpha", weight=0.5, group="g")
    r.register(defn)
    assert r.get("alpha") is defn
    assert r.get("missing") is None
    assert "alpha" in r.metrics()
    assert r.groups() == ["g"]


def test_register_overwrites_prior() -> None:
    """Re-registering the same name keeps the latest definition."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="alpha", weight=0.3))
    r.register(MetricDefinition(name="alpha", weight=0.7))
    assert r.get("alpha").weight == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# weight_sum_for_group
# ---------------------------------------------------------------------------


def test_weight_sum_for_group_single() -> None:
    """Single-group registry: sum equals the only weight."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=0.6, group="g"))
    assert r.weight_sum_for_group("g") == pytest.approx(0.6)


def test_weight_sum_for_group_multiple() -> None:
    """Multi-group registry: sum is per-group, not global."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=0.4, group="g1"))
    r.register(MetricDefinition(name="b", weight=0.2, group="g1"))
    r.register(MetricDefinition(name="c", weight=0.7, group="g2"))
    assert r.weight_sum_for_group("g1") == pytest.approx(0.6)
    assert r.weight_sum_for_group("g2") == pytest.approx(0.7)
    assert r.weight_sum_for_group("missing") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# normalized — fallback path (no threshold, no normalizer)
# ---------------------------------------------------------------------------


def test_normalized_no_threshold_passes_through_value_over_max() -> None:
    """Without threshold/normalizer, the registry returns value/max_value clamped."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=1.0))
    assert r.normalized("a", 0.5, max_value=1.0) == pytest.approx(0.5)
    assert r.normalized("a", 80.0, max_value=100.0) == pytest.approx(0.8)
    # Above max → clamped to 1.0
    assert r.normalized("a", 1.5, max_value=1.0) == pytest.approx(1.0)
    # Negative → clamped to 0.0
    assert r.normalized("a", -0.2, max_value=1.0) == pytest.approx(0.0)
    # max_value == 0 → 0
    assert r.normalized("a", 5.0, max_value=0.0) == pytest.approx(0.0)


def test_normalized_unknown_metric_raises_keyerror() -> None:
    """Misconfigured names surface immediately, no silent fallback."""
    r = MetricRegistry()
    with pytest.raises(KeyError):
        r.normalized("missing", 0.5)


# ---------------------------------------------------------------------------
# normalized — threshold path (MAXIMIZE)
# ---------------------------------------------------------------------------


def test_normalized_with_threshold_maximize() -> None:
    """MAXIMIZE band: value≤min → 0; value≥max → 1; linear in between."""
    r = MetricRegistry()
    r.register(
        MetricDefinition(
            name="cov",
            weight=1.0,
            threshold=(60.0, 95.0),
        ),
    )
    assert r.normalized("cov", 50.0) == pytest.approx(0.0)  # below min
    assert r.normalized("cov", 60.0) == pytest.approx(0.0)
    assert r.normalized("cov", 95.0) == pytest.approx(1.0)
    assert r.normalized("cov", 100.0) == pytest.approx(1.0)  # above max
    # Linear midpoint
    assert r.normalized("cov", 77.5) == pytest.approx(0.5)


def test_normalized_with_threshold_above_one_breaks_saturation() -> None:
    """Ceiling > 1.0 deliberately de-saturates a value=1.0 dim (C08 §4.10)."""
    r = MetricRegistry()
    r.register(
        MetricDefinition(
            name="dim",
            weight=1.0,
            threshold=(0.7, 1.05),
        ),
    )
    # value=1.0 falls in the linear region: (1.0-0.7)/(1.05-0.7) ≈ 0.857
    assert r.normalized("dim", 1.0) == pytest.approx(0.30 / 0.35)


# ---------------------------------------------------------------------------
# normalized — threshold path (MINIMIZE)
# ---------------------------------------------------------------------------


def test_normalized_with_threshold_minimize_direction() -> None:
    """MINIMIZE band: value≤min → 1 (best); value≥max → 0 (worst); linear in between."""
    r = MetricRegistry()
    r.register(
        MetricDefinition(
            name="latency_ms",
            weight=1.0,
            direction=Direction.MINIMIZE,
            threshold=(100.0, 1000.0),
        ),
    )
    assert r.normalized("latency_ms", 50.0) == pytest.approx(1.0)  # below min → best
    assert r.normalized("latency_ms", 100.0) == pytest.approx(1.0)
    assert r.normalized("latency_ms", 1000.0) == pytest.approx(0.0)
    assert r.normalized("latency_ms", 1500.0) == pytest.approx(0.0)
    # Midpoint
    assert r.normalized("latency_ms", 550.0) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# normalized — custom normalizer override
# ---------------------------------------------------------------------------


def test_normalized_with_custom_normalizer_wins_over_threshold() -> None:
    """Custom normalizer takes precedence even when a threshold is also set."""
    r = MetricRegistry()
    r.register(
        MetricDefinition(
            name="quirky",
            weight=1.0,
            threshold=(0.0, 1.0),
            normalizer=lambda v, m: 0.42,  # constant for predictability
        ),
    )
    # Always 0.42 regardless of the value or threshold band.
    assert r.normalized("quirky", 0.0) == pytest.approx(0.42)
    assert r.normalized("quirky", 99.0) == pytest.approx(0.42)


def test_normalized_clamps_custom_normalizer_to_unit_interval() -> None:
    """Custom normalizer outputs are clamped to [0, 1]."""
    r = MetricRegistry()
    r.register(
        MetricDefinition(
            name="big",
            weight=1.0,
            normalizer=lambda v, m: 5.0,
        ),
    )
    r.register(
        MetricDefinition(
            name="small",
            weight=1.0,
            normalizer=lambda v, m: -3.0,
        ),
    )
    assert r.normalized("big", 0.0) == pytest.approx(1.0)
    assert r.normalized("small", 0.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# weighted_mean
# ---------------------------------------------------------------------------


def test_weighted_mean_basic() -> None:
    """Standard weighted average over a fully-populated group."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=0.4, group="g"))
    r.register(MetricDefinition(name="b", weight=0.6, group="g"))
    # 0.4 * 1.0 + 0.6 * 0.5 = 0.7
    assert r.weighted_mean("g", {"a": 1.0, "b": 0.5}) == pytest.approx(0.7)


def test_weighted_mean_excludes_missing_scores_from_denominator() -> None:
    """Missing scores are dropped from BOTH numerator and denominator."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=0.4, group="g"))
    r.register(MetricDefinition(name="b", weight=0.6, group="g"))
    # Only "a" supplied → denominator becomes 0.4, mean = 1.0
    assert r.weighted_mean("g", {"a": 1.0}) == pytest.approx(1.0)


def test_weighted_mean_empty_group_returns_zero() -> None:
    """Group with no matching scores → 0.0 (matches legacy run_all empty fallback)."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=1.0, group="g"))
    assert r.weighted_mean("g", {}) == pytest.approx(0.0)
    assert r.weighted_mean("missing-group", {}) == pytest.approx(0.0)


def test_weighted_mean_ignores_other_groups() -> None:
    """Scores for metrics in OTHER groups don't pollute the target group's mean."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=1.0, group="g1"))
    r.register(MetricDefinition(name="b", weight=1.0, group="g2"))
    # Only g1 should contribute even though we pass both scores.
    assert r.weighted_mean("g1", {"a": 0.4, "b": 0.9}) == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_passes_on_well_formed_registry() -> None:
    """Per-group sums == 1.0 (within tolerance) → no errors."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=0.5, group="g"))
    r.register(MetricDefinition(name="b", weight=0.5, group="g"))
    assert r.validate() == []


def test_validate_fails_when_group_weights_dont_sum_to_one() -> None:
    """Group whose weights sum to 0.85 produces a descriptive error."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=0.4, group="capability"))
    r.register(MetricDefinition(name="b", weight=0.45, group="capability"))
    errors = r.validate()
    assert len(errors) == 1
    assert "capability" in errors[0]
    assert "0.85" in errors[0]


def test_validate_tolerates_small_drift() -> None:
    """Drift inside ±0.01 is acceptable."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=0.501, group="g"))
    r.register(MetricDefinition(name="b", weight=0.495, group="g"))
    # Total = 0.996, within tolerance of 1.0
    assert r.validate() == []


# ---------------------------------------------------------------------------
# from_toml — bundled file
# ---------------------------------------------------------------------------


def test_load_default_registry_validates() -> None:
    """The bundled TOML must validate cleanly; capability + hygiene + _groups all sum to 1.0."""
    r = load_default_registry()
    assert r.validate() == []
    assert r.weight_sum_for_group("capability") == pytest.approx(1.0)
    assert r.weight_sum_for_group("hygiene") == pytest.approx(1.0)
    assert r.weight_sum_for_group(GROUPS_META_GROUP) == pytest.approx(1.0)


def test_load_default_registry_path_resolves() -> None:
    """default_registry_path() points at the in-tree TOML."""
    p = default_registry_path()
    assert p.exists(), f"missing bundled registry at {p}"
    assert p.suffix == ".toml"


def test_from_toml_round_trip_via_dict(tmp_path: Path) -> None:
    """A minimal TOML round-trips through MetricRegistry.from_toml correctly."""
    toml_path = tmp_path / "weights.toml"
    toml_path.write_text(
        """
[groups]
capability = 0.6
hygiene    = 0.4

[metrics.capability.scoring]
weight    = 1.0
direction = "maximize"
threshold = [0.5, 1.0]

[metrics.hygiene.lint]
weight = 1.0
""",
        encoding="utf-8",
    )
    r = MetricRegistry.from_toml(toml_path)
    assert r.validate() == []
    assert r.weight_sum_for_group("capability") == pytest.approx(1.0)
    assert r.weight_sum_for_group("hygiene") == pytest.approx(1.0)
    assert r.weight_sum_for_group(GROUPS_META_GROUP) == pytest.approx(1.0)
    defn = r.get("scoring")
    assert defn is not None
    assert defn.direction is Direction.MAXIMIZE
    assert defn.threshold == (0.5, 1.0)


def test_from_toml_rejects_invalid_direction(tmp_path: Path) -> None:
    """Unknown direction string surfaces as ValueError, not silent default."""
    toml_path = tmp_path / "bad.toml"
    toml_path.write_text(
        """
[metrics.capability.bad]
weight    = 1.0
direction = "sideways"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="direction"):
        MetricRegistry.from_toml(toml_path)


def test_from_toml_rejects_malformed_threshold(tmp_path: Path) -> None:
    """Threshold must be a 2-element list."""
    toml_path = tmp_path / "bad.toml"
    toml_path.write_text(
        """
[metrics.capability.bad]
weight    = 1.0
threshold = [0.5, 0.7, 0.9]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="threshold"):
        MetricRegistry.from_toml(toml_path)


# ---------------------------------------------------------------------------
# weights_dict + groups
# ---------------------------------------------------------------------------


def test_weights_dict_returns_name_weight_map() -> None:
    """weights_dict is a flat name→weight snapshot for report transparency."""
    r = MetricRegistry()
    r.register(MetricDefinition(name="a", weight=0.3, group="g1"))
    r.register(MetricDefinition(name="b", weight=0.7, group="g2"))
    weights = r.weights_dict()
    assert weights == {"a": 0.3, "b": 0.7}
