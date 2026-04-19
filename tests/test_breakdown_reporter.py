"""C12 — Tests for the AgentBoard-style sub-skill breakdown reporter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.breakdown_reporter import (  # noqa: E402
    BreakdownReport,
    BreakdownReporter,
    DimensionPanel,
    SubSkill,
)
from nines.iteration.self_eval import DimensionScore, SelfEvalReport  # noqa: E402

# ---------------------------------------------------------------------------
# SubSkill construction + normalized property
# ---------------------------------------------------------------------------


def test_subskill_defaults_carry_unit_max_and_full_weight() -> None:
    """Default ``max_value=1.0`` + ``weight=1.0`` so a ratio sub-skill
    reduces to its raw value with full vote in weighted rollups."""
    sub = SubSkill(name="x", parent_dim="dim", value=0.42)
    assert sub.max_value == 1.0
    assert sub.weight == 1.0
    assert sub.normalized == pytest.approx(0.42)
    assert sub.metadata == {}


def test_subskill_normalized_handles_non_unit_max() -> None:
    """Code-coverage style sub-skills (max=100) normalise to [0,1]."""
    sub = SubSkill(name="line_coverage", parent_dim="code_coverage",
                   value=86.0, max_value=100.0)
    assert sub.normalized == pytest.approx(0.86)


def test_subskill_normalized_zero_max_returns_zero() -> None:
    """Degenerate ``max_value=0`` must not raise — returns 0.0 instead
    of a ZeroDivisionError so rollups remain finite."""
    sub = SubSkill(name="bad", parent_dim="dim", value=5.0, max_value=0.0)
    assert sub.normalized == 0.0


def test_subskill_to_dict_preserves_all_fields() -> None:
    """JSON round-trip carries name / parent / value / max / weight /
    metadata; ``normalized`` is a derived convenience field."""
    sub = SubSkill(
        name="finding_quality",
        parent_dim="code_review_accuracy",
        value=0.9,
        weight=0.5,
        metadata={"valid": 9, "total": 10},
    )
    d = sub.to_dict()
    assert d["name"] == "finding_quality"
    assert d["parent_dim"] == "code_review_accuracy"
    assert d["value"] == 0.9
    assert d["weight"] == 0.5
    assert d["metadata"] == {"valid": 9, "total": 10}
    assert d["normalized"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# DimensionPanel rollup methods
# ---------------------------------------------------------------------------


def _make_subs(values: list[tuple[float, float]]) -> list[SubSkill]:
    """Build sub-skills from ``[(value, weight), ...]`` for rollup tests."""
    return [
        SubSkill(name=f"s{i}", parent_dim="dim", value=v, weight=w)
        for i, (v, w) in enumerate(values)
    ]


def test_panel_rollup_mean() -> None:
    """``mean`` ignores weights and averages normalized values."""
    panel = DimensionPanel(
        dim_name="dim",
        parent_dim_value=0.0,
        subskills=_make_subs([(0.4, 5.0), (0.6, 0.1), (1.0, 100.0)]),
        rollup_method="mean",
    )
    assert panel.rollup() == pytest.approx((0.4 + 0.6 + 1.0) / 3)


def test_panel_rollup_weighted_mean() -> None:
    """``weighted_mean`` weights each sub-skill by its ``weight``."""
    panel = DimensionPanel(
        dim_name="dim",
        parent_dim_value=0.0,
        subskills=_make_subs([(0.4, 1.0), (1.0, 3.0)]),
        rollup_method="weighted_mean",
    )
    expected = (0.4 * 1.0 + 1.0 * 3.0) / 4.0
    assert panel.rollup() == pytest.approx(expected)


def test_panel_rollup_min_and_max() -> None:
    """``min`` / ``max`` surface the worst/best sub-skill — useful for
    floor/ceiling reporting."""
    subs = _make_subs([(0.2, 1.0), (0.7, 1.0), (0.9, 1.0)])
    assert DimensionPanel("d", 0, subs, rollup_method="min").rollup() == pytest.approx(0.2)
    assert DimensionPanel("d", 0, subs, rollup_method="max").rollup() == pytest.approx(0.9)


def test_panel_rollup_empty_returns_zero() -> None:
    """Empty sub-skill lists collapse to 0.0 instead of raising."""
    for method in ("mean", "weighted_mean", "min", "max"):
        panel = DimensionPanel(dim_name="d", parent_dim_value=0.5, subskills=[],
                               rollup_method=method)
        assert panel.rollup() == 0.0


def test_panel_rollup_single_subskill_matches_value() -> None:
    """A single sub-skill's rollup reproduces its normalized value
    regardless of method."""
    sub = SubSkill(name="only", parent_dim="d", value=0.73, max_value=1.0)
    for method in ("mean", "weighted_mean", "min", "max"):
        panel = DimensionPanel(dim_name="d", parent_dim_value=0.0,
                               subskills=[sub], rollup_method=method)
        assert panel.rollup() == pytest.approx(0.73)


def test_panel_rollup_weighted_mean_zero_weight_falls_back_to_mean() -> None:
    """Weights that sum to zero degrade gracefully to the unweighted mean."""
    subs = [
        SubSkill(name="a", parent_dim="d", value=0.4, weight=0.0),
        SubSkill(name="b", parent_dim="d", value=0.8, weight=0.0),
    ]
    panel = DimensionPanel(dim_name="d", parent_dim_value=0.0,
                           subskills=subs, rollup_method="weighted_mean")
    assert panel.rollup() == pytest.approx(0.6)


def test_panel_coverage_count_and_has_breakdown() -> None:
    """``coverage_count`` reports the sub-skill count; ``has_breakdown``
    is True only when at least 2 sub-skills are present (mirror panels
    don't count as real granularity)."""
    one = DimensionPanel(dim_name="d", parent_dim_value=0.5,
                         subskills=_make_subs([(0.5, 1.0)]))
    two = DimensionPanel(dim_name="d", parent_dim_value=0.5,
                         subskills=_make_subs([(0.5, 1.0), (0.6, 1.0)]))
    assert one.coverage_count() == 1
    assert two.coverage_count() == 2
    assert one.has_breakdown() is False
    assert two.has_breakdown() is True


# ---------------------------------------------------------------------------
# BreakdownReporter.from_self_eval — extraction
# ---------------------------------------------------------------------------


def _score_with_subskills() -> DimensionScore:
    return DimensionScore(
        name="code_review_accuracy",
        value=0.9,
        max_value=1.0,
        metadata={
            "subskills": [
                {"name": "finding_quality_rate", "value": 0.95, "weight": 0.4},
                {"name": "complexity_check_rate", "value": 0.80, "weight": 0.2},
                {"name": "severity_balance", "value": 0.75, "weight": 0.2},
                {"name": "false_positive_signal", "value": 0.90, "weight": 0.2},
            ],
            "rollup_method": "weighted_mean",
        },
    )


def _score_without_subskills() -> DimensionScore:
    return DimensionScore(
        name="convergence_rate",
        value=1.0,
        max_value=1.0,
        metadata={"unit": "ratio"},
    )


def test_from_self_eval_extracts_annotated_subskills() -> None:
    """A score whose metadata carries a ``subskills`` block becomes a
    panel with one :class:`SubSkill` per entry."""
    report = SelfEvalReport(scores=[_score_with_subskills()], version="vT")
    bd = BreakdownReporter().from_self_eval(report)
    assert len(bd.panels) == 1
    panel = bd.panels[0]
    assert panel.dim_name == "code_review_accuracy"
    assert panel.coverage_count() == 4
    names = [s.name for s in panel.subskills]
    assert names == [
        "finding_quality_rate",
        "complexity_check_rate",
        "severity_balance",
        "false_positive_signal",
    ]
    assert panel.has_breakdown() is True


def test_from_self_eval_falls_back_to_mirror_subskill() -> None:
    """A score *without* a ``subskills`` metadata block produces a
    single mirror sub-skill — the panel is never empty."""
    report = SelfEvalReport(scores=[_score_without_subskills()])
    bd = BreakdownReporter().from_self_eval(report)
    panel = bd.panels[0]
    assert panel.coverage_count() == 1
    assert panel.subskills[0].name == "convergence_rate"
    assert panel.subskills[0].metadata == {"source": "mirror_fallback"}
    assert panel.has_breakdown() is False  # mirror panels don't count


def test_from_self_eval_handles_mixed_dims() -> None:
    """Mixed reports (some annotated, some not) preserve each dim's
    treatment in the same output report."""
    report = SelfEvalReport(
        scores=[_score_with_subskills(), _score_without_subskills()],
        version="vMix",
    )
    bd = BreakdownReporter().from_self_eval(report)
    assert len(bd.panels) == 2
    assert bd.dims_with_breakdown() == 1  # only the annotated one counts
    assert bd.total_subskills() == 5  # 4 + 1 mirror


def test_from_self_eval_skips_malformed_subskill_entries() -> None:
    """Entries lacking ``name`` or ``value`` are filtered silently so
    one bad row in metadata doesn't break the panel; if every entry is
    malformed the mirror fallback fires."""
    score = DimensionScore(
        name="d",
        value=0.5,
        metadata={
            "subskills": [
                {"name": "ok", "value": 0.7},
                {"value": 0.4},  # missing name
                "not a dict",  # type: ignore[list-item]
                {"name": "no_value"},  # missing value
            ]
        },
    )
    report = SelfEvalReport(scores=[score])
    bd = BreakdownReporter().from_self_eval(report)
    panel = bd.panels[0]
    assert panel.coverage_count() == 1
    assert panel.subskills[0].name == "ok"


def test_from_self_eval_summary_buckets_count_correctly() -> None:
    """The summary buckets count saturated / healthy / needs-work /
    broken sub-skills exactly per the documented thresholds."""
    scores = [
        DimensionScore(
            name="dim",
            value=0.5,
            metadata={
                "subskills": [
                    {"name": "saturated", "value": 0.99},
                    {"name": "saturated2", "value": 0.96},
                    {"name": "healthy", "value": 0.85},
                    {"name": "healthy2", "value": 0.75},
                    {"name": "needs_work", "value": 0.6},
                    {"name": "broken", "value": 0.2},
                ]
            },
        )
    ]
    bd = BreakdownReporter().from_self_eval(SelfEvalReport(scores=scores))
    s = bd.summary
    assert s["total_subskills"] == 6
    assert s["dims_with_breakdown"] == 1
    assert s["bucket_counts"]["saturated_>=0.95"] == 2
    assert s["bucket_counts"]["healthy_0.7_to_0.95"] == 2
    assert s["bucket_counts"]["needs_work_0.5_to_0.7"] == 1
    assert s["bucket_counts"]["broken_<0.5"] == 1
    assert s["subskills_in_0.7_to_0.95"] == 2
    assert s["subskills_in_0.5_to_0.95"] == 3  # 2 healthy + 1 needs-work


# ---------------------------------------------------------------------------
# BreakdownReporter.generate — rendering
# ---------------------------------------------------------------------------


def _sample_breakdown() -> BreakdownReport:
    report = SelfEvalReport(
        scores=[_score_with_subskills(), _score_without_subskills()],
        version="vRender",
    )
    return BreakdownReporter().from_self_eval(report)


def test_generate_text_contains_panel_header_and_bars() -> None:
    """Text format must list every panel name with at least one bar
    visualisation row per sub-skill."""
    bd = _sample_breakdown()
    out = BreakdownReporter().generate(bd, fmt="text")
    assert "code_review_accuracy" in out
    assert "convergence_rate" in out
    assert "finding_quality_rate" in out
    assert "[" in out and "]" in out  # ASCII bar
    assert "Sub-Skill Breakdown" in out


def test_generate_json_round_trips() -> None:
    """JSON format is parseable and carries the panel + summary fields."""
    bd = _sample_breakdown()
    out = BreakdownReporter().generate(bd, fmt="json")
    parsed = json.loads(out)
    assert parsed["panel_count"] == 2
    assert parsed["total_subskills"] == 5  # 4 annotated + 1 mirror
    assert parsed["dims_with_breakdown"] == 1
    assert parsed["summary"]["total_subskills"] == 5
    panel0 = parsed["panels"][0]
    assert panel0["dim_name"] == "code_review_accuracy"
    assert len(panel0["subskills"]) == 4


def test_generate_markdown_contains_table_and_anchors() -> None:
    """Markdown format produces level-3 headings and table rows for
    each sub-skill, plus a [broken-down]/[mirror] tag per panel."""
    bd = _sample_breakdown()
    out = BreakdownReporter().generate(bd, fmt="markdown")
    assert "## Sub-Skill Breakdown" in out
    assert "### code_review_accuracy" in out
    assert "**[broken-down]**" in out
    assert "*[mirror]*" in out
    assert "| sub-skill | normalized | value | max | weight |" in out


def test_generate_default_format_is_text() -> None:
    """Calling ``generate(bd)`` with no format argument matches the
    text output exactly."""
    bd = _sample_breakdown()
    reporter = BreakdownReporter()
    assert reporter.generate(bd) == reporter.generate(bd, fmt="text")


# ---------------------------------------------------------------------------
# Misc — total counts + JSON serialisation parity
# ---------------------------------------------------------------------------


def test_breakdown_report_to_dict_serialises_all_panels() -> None:
    """``BreakdownReport.to_dict`` returns a dict suitable for embedding
    under a top-level ``breakdown`` key in the CLI JSON output."""
    bd = _sample_breakdown()
    d = bd.to_dict()
    assert d["panel_count"] == 2
    assert d["total_subskills"] == 5
    assert d["dims_with_breakdown"] == 1
    assert isinstance(d["panels"], list)
    assert isinstance(d["summary"], dict)
    # Round-trip through JSON to catch any non-serialisable surprises.
    json.dumps(d, default=str)


def test_panel_rollup_method_extracted_from_metadata() -> None:
    """When metadata sets ``rollup_method``, the panel respects it
    instead of defaulting to weighted_mean."""
    score = DimensionScore(
        name="floor",
        value=0.4,
        metadata={
            "rollup_method": "min",
            "subskills": [
                {"name": "a", "value": 0.4},
                {"name": "b", "value": 0.9},
            ],
        },
    )
    bd = BreakdownReporter().from_self_eval(SelfEvalReport(scores=[score]))
    panel = bd.panels[0]
    assert panel.rollup_method == "min"
    assert panel.rollup() == pytest.approx(0.4)


def test_breakdown_report_total_helpers_match_summary() -> None:
    """``total_subskills``/``dims_with_breakdown`` agree with the
    summary block computed by the reporter."""
    bd = _sample_breakdown()
    assert bd.total_subskills() == bd.summary["total_subskills"]
    assert bd.dims_with_breakdown() == bd.summary["dims_with_breakdown"]
