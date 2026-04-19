"""C12 — AgentBoard-style sub-skill breakdown reporter.

Decomposes the flat 25-dimension self-evaluation report into per-dimension
panels of 2-4 sub-skills each, so reviewers can see *which* sub-component
caused a regression (the §4.10 saturation problem AgentBoard solves).

Public API
----------
:class:`SubSkill`
    Leaf measurement attached to a parent dim; carries a value, optional
    max, and a weight used by weighted rollups.
:class:`DimensionPanel`
    A parent dim plus its sub-skills.  Provides ``rollup()`` to recompute
    the parent value from sub-skills (sanity check vs the evaluator's own
    aggregation) and ``coverage_count()`` for spread analysis.
:class:`BreakdownReport`
    Container of panels + summary stats (total sub-skills, dims with
    breakdown, sub-skill range distribution).
:class:`BreakdownReporter`
    Extracts panels from a :class:`SelfEvalReport` (reading
    ``DimensionScore.metadata["subskills"]`` when present, otherwise
    falling back to a single mirror sub-skill) and renders text /
    JSON / Markdown.

Sub-skill metadata schema (evaluators populate
``score.metadata["subskills"]`` as a list of dicts)::

    [
        {"name": "finding_quality_rate", "value": 0.95,
         "max_value": 1.0, "weight": 0.5,
         "metadata": {"unit": "ratio"}},
        ...
    ]

Backward compat: dimensions with no ``subskills`` block still appear in
the report — they get a single mirror sub-skill named after the parent
dim, so consumers always see one row per parent dim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from nines.iteration.self_eval import DimensionScore, SelfEvalReport


RollupMethod = Literal["mean", "weighted_mean", "min", "max"]


# ---------------------------------------------------------------------------
# Sub-skill leaf
# ---------------------------------------------------------------------------


@dataclass
class SubSkill:
    """Leaf sub-component of a parent dim.

    Attributes
    ----------
    name:
        Sub-skill identifier (e.g. ``"finding_quality_rate"``).
    parent_dim:
        Name of the parent :class:`DimensionScore` this sub-skill rolls
        up into.
    value:
        Measured value.
    max_value:
        Upper bound; ``normalized`` divides ``value`` by this.  Defaults
        to ``1.0`` for ratio-typed sub-skills.
    weight:
        Used by ``rollup_method="weighted_mean"``.  Defaults to ``1.0``
        so an unweighted population reduces to the mean.
    metadata:
        Optional opaque context (units, raw counts, etc.).
    """

    name: str
    parent_dim: str
    value: float
    max_value: float = 1.0
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized(self) -> float:
        """Return ``value / max_value`` clamped to a safe value.

        Returns ``0.0`` when ``max_value == 0`` (rather than dividing by
        zero) so rollups remain finite even on degenerate inputs.
        """
        if self.max_value == 0:
            return 0.0
        return self.value / self.max_value

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dictionary."""
        return {
            "name": self.name,
            "parent_dim": self.parent_dim,
            "value": self.value,
            "max_value": self.max_value,
            "normalized": self.normalized,
            "weight": self.weight,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Dimension panel
# ---------------------------------------------------------------------------


@dataclass
class DimensionPanel:
    """A parent dim plus its sub-skills.

    Attributes
    ----------
    dim_name:
        Name of the parent dim (matches ``DimensionScore.name``).
    parent_dim_value:
        The normalized value reported by the evaluator (the
        authoritative number).
    subskills:
        Leaf sub-components.
    rollup_method:
        How :meth:`rollup` recomputes the parent number from sub-skills.
        Defaults to ``"weighted_mean"`` (matches AgentBoard's analytical
        breakdown convention).
    """

    dim_name: str
    parent_dim_value: float
    subskills: list[SubSkill] = field(default_factory=list)
    rollup_method: RollupMethod = "weighted_mean"

    def coverage_count(self) -> int:
        """Number of sub-skills in this panel."""
        return len(self.subskills)

    def has_breakdown(self) -> bool:
        """True when the panel contains genuine sub-skill granularity.

        A panel is "broken down" when it carries 2+ sub-skills.  Mirror
        panels (single fallback sub-skill matching the parent) return
        ``False`` so summary counts only reflect real decomposition.
        """
        return len(self.subskills) >= 2

    def rollup(self) -> float:
        """Recompute the parent value from sub-skills.

        Used as a sanity check — comparing :meth:`rollup` against
        :attr:`parent_dim_value` shows how much the evaluator's own
        aggregation differs from the mechanical sub-skill mean (helpful
        when an evaluator weights one sub-skill more than the others).

        Returns ``0.0`` for empty sub-skill lists.
        """
        if not self.subskills:
            return 0.0
        if self.rollup_method == "mean":
            return sum(s.normalized for s in self.subskills) / len(self.subskills)
        if self.rollup_method == "min":
            return min(s.normalized for s in self.subskills)
        if self.rollup_method == "max":
            return max(s.normalized for s in self.subskills)
        # weighted_mean (default)
        weight_sum = sum(s.weight for s in self.subskills)
        if weight_sum == 0:
            return sum(s.normalized for s in self.subskills) / len(self.subskills)
        return sum(s.normalized * s.weight for s in self.subskills) / weight_sum

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dictionary."""
        return {
            "dim_name": self.dim_name,
            "parent_dim_value": self.parent_dim_value,
            "rollup_method": self.rollup_method,
            "rollup_value": self.rollup(),
            "subskill_count": self.coverage_count(),
            "has_breakdown": self.has_breakdown(),
            "subskills": [s.to_dict() for s in self.subskills],
        }


# ---------------------------------------------------------------------------
# Breakdown report
# ---------------------------------------------------------------------------


def _bucket_key(normalized: float) -> str:
    """Map a normalized score to a coarse bucket for summary stats.

    Buckets used in the report summary so reviewers can see at a glance
    how many sub-skills sit in saturated, healthy, or broken zones.
    """
    if normalized >= 0.95:
        return "saturated_>=0.95"
    if normalized >= 0.7:
        return "healthy_0.7_to_0.95"
    if normalized >= 0.5:
        return "needs_work_0.5_to_0.7"
    return "broken_<0.5"


@dataclass
class BreakdownReport:
    """Aggregate of dimension panels + spread summary.

    Attributes
    ----------
    version:
        Optional version tag mirroring :attr:`SelfEvalReport.version`.
    timestamp:
        ISO-8601 generation time.
    panels:
        One :class:`DimensionPanel` per parent dim from the source
        report (mirror panels included for dims without sub-skill
        metadata, so the panel count equals the input dim count).
    summary:
        Distribution stats — see :meth:`_compute_summary`.
    """

    version: str = ""
    timestamp: str = ""
    panels: list[DimensionPanel] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def all_subskills(self) -> list[SubSkill]:
        """Flatten panels into a single sub-skill list."""
        out: list[SubSkill] = []
        for panel in self.panels:
            out.extend(panel.subskills)
        return out

    def total_subskills(self) -> int:
        """Total number of sub-skill measurements across all panels."""
        return sum(p.coverage_count() for p in self.panels)

    def dims_with_breakdown(self) -> int:
        """Number of panels carrying ≥ 2 sub-skills (real granularity)."""
        return sum(1 for p in self.panels if p.has_breakdown())

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "panel_count": len(self.panels),
            "total_subskills": self.total_subskills(),
            "dims_with_breakdown": self.dims_with_breakdown(),
            "summary": dict(self.summary),
            "panels": [p.to_dict() for p in self.panels],
        }


# ---------------------------------------------------------------------------
# Reporter — extraction + rendering
# ---------------------------------------------------------------------------


class BreakdownReporter:
    """Extract sub-skill panels from a :class:`SelfEvalReport` and render.

    Extraction reads ``DimensionScore.metadata["subskills"]`` when
    present (a list of dicts following the schema in the module
    docstring) and falls back to a single mirror sub-skill when the
    metadata block is missing or empty — that way every dim in the
    input report contributes exactly one panel to the output.
    """

    def from_self_eval(self, report: SelfEvalReport) -> BreakdownReport:
        """Build a :class:`BreakdownReport` from a :class:`SelfEvalReport`.

        Each ``score`` becomes a panel.  Sub-skills come from
        ``score.metadata["subskills"]`` when that list-typed key exists;
        otherwise a single mirror sub-skill named after the parent dim
        is emitted so the panel is never empty (consumers always see at
        least one row per dim).
        """
        panels: list[DimensionPanel] = []
        for score in report.scores:
            panel = self._panel_from_score(score)
            panels.append(panel)

        breakdown = BreakdownReport(
            version=report.version,
            timestamp=datetime.now(UTC).isoformat(),
            panels=panels,
        )
        breakdown.summary = self._compute_summary(breakdown)
        return breakdown

    @staticmethod
    def _panel_from_score(score: DimensionScore) -> DimensionPanel:
        """Build a single :class:`DimensionPanel` from one score."""
        raw_subskills = score.metadata.get("subskills") if isinstance(
            score.metadata, dict
        ) else None
        rollup_method: RollupMethod = "weighted_mean"
        if isinstance(score.metadata, dict):
            method = score.metadata.get("rollup_method")
            if method in ("mean", "weighted_mean", "min", "max"):
                rollup_method = method  # type: ignore[assignment]

        subskills: list[SubSkill] = []
        if isinstance(raw_subskills, list) and raw_subskills:
            for entry in raw_subskills:
                if not isinstance(entry, dict):
                    continue
                if "name" not in entry or "value" not in entry:
                    continue
                subskills.append(
                    SubSkill(
                        name=str(entry["name"]),
                        parent_dim=score.name,
                        value=float(entry["value"]),
                        max_value=float(entry.get("max_value", 1.0)),
                        weight=float(entry.get("weight", 1.0)),
                        metadata=dict(entry.get("metadata", {})),
                    )
                )

        if not subskills:
            # Mirror fallback so every panel has at least one row.
            subskills = [
                SubSkill(
                    name=score.name,
                    parent_dim=score.name,
                    value=score.value,
                    max_value=score.max_value,
                    weight=1.0,
                    metadata={"source": "mirror_fallback"},
                )
            ]

        return DimensionPanel(
            dim_name=score.name,
            parent_dim_value=score.normalized,
            subskills=subskills,
            rollup_method=rollup_method,
        )

    @staticmethod
    def _compute_summary(breakdown: BreakdownReport) -> dict[str, Any]:
        """Compute distribution stats over all sub-skills.

        The bucket counts let reviewers see at a glance how many
        sub-skills are saturated (≥0.95), healthy ([0.7, 0.95)),
        needing work ([0.5, 0.7)), or broken (<0.5) — the equivalent of
        AgentBoard's per-dim heatmap rolled up into a single summary.
        """
        all_subs = breakdown.all_subskills()
        bucket_counts: dict[str, int] = {
            "saturated_>=0.95": 0,
            "healthy_0.7_to_0.95": 0,
            "needs_work_0.5_to_0.7": 0,
            "broken_<0.5": 0,
        }
        for sub in all_subs:
            bucket_counts[_bucket_key(sub.normalized)] += 1

        # The 0.7-0.95 band is the AgentBoard "headroom signal" zone —
        # surfaces sub-skills that aren't saturated but aren't broken
        # either.  Reported separately as the canonical task-spec metric.
        in_healthy = bucket_counts["healthy_0.7_to_0.95"]
        in_mid = bucket_counts["healthy_0.7_to_0.95"] + bucket_counts["needs_work_0.5_to_0.7"]

        return {
            "total_subskills": breakdown.total_subskills(),
            "dims_with_breakdown": breakdown.dims_with_breakdown(),
            "panel_count": len(breakdown.panels),
            "subskills_in_0.7_to_0.95": in_healthy,
            "subskills_in_0.5_to_0.95": in_mid,
            "bucket_counts": bucket_counts,
        }

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def generate(
        self,
        breakdown: BreakdownReport,
        fmt: Literal["text", "json", "markdown"] = "text",
    ) -> str:
        """Render a :class:`BreakdownReport` in the requested *fmt*.

        ``fmt`` accepts ``"text"``, ``"json"`` or ``"markdown"``
        (named ``fmt`` rather than ``format`` to avoid shadowing the
        Python builtin).
        """
        if fmt == "json":
            return json.dumps(breakdown.to_dict(), indent=2, default=str)
        if fmt == "markdown":
            return self._render_markdown(breakdown)
        return self._render_text(breakdown)

    @staticmethod
    def _bar(normalized: float, width: int = 20) -> str:
        """ASCII bar visualization of a [0, 1] value."""
        clamped = max(0.0, min(1.0, normalized))
        filled = int(round(clamped * width))
        return "[" + ("=" * filled).ljust(width, "·") + "]"

    def _render_text(self, breakdown: BreakdownReport) -> str:
        lines = [
            "=== Sub-Skill Breakdown (C12) ===",
            f"  Version: {breakdown.version or 'untagged'}",
            f"  Timestamp: {breakdown.timestamp}",
            f"  Panels: {len(breakdown.panels)}  "
            f"Total sub-skills: {breakdown.total_subskills()}  "
            f"Dims with breakdown: {breakdown.dims_with_breakdown()}",
        ]
        s = breakdown.summary
        if s:
            lines.append(
                f"  Sub-skills in [0.7, 0.95): {s.get('subskills_in_0.7_to_0.95', 0)}  "
                f"in [0.5, 0.95): {s.get('subskills_in_0.5_to_0.95', 0)}"
            )
            buckets = s.get("bucket_counts", {})
            if buckets:
                bucket_line = "  Buckets: " + ", ".join(
                    f"{k}={v}" for k, v in buckets.items()
                )
                lines.append(bucket_line)
        lines.append("")

        for panel in breakdown.panels:
            marker = "*" if panel.has_breakdown() else " "
            lines.append(
                f"  {marker} {panel.dim_name}  "
                f"parent={panel.parent_dim_value:.3f}  "
                f"rollup={panel.rollup():.3f}  "
                f"({panel.coverage_count()} sub)"
            )
            for sub in panel.subskills:
                lines.append(
                    f"      - {sub.name:<32} {self._bar(sub.normalized)} "
                    f"{sub.normalized:.3f}  (w={sub.weight:.2f})"
                )

        return "\n".join(lines)

    def _render_markdown(self, breakdown: BreakdownReport) -> str:
        lines = [
            "## Sub-Skill Breakdown (C12)",
            "",
            f"- **Version:** {breakdown.version or 'untagged'}",
            f"- **Timestamp:** {breakdown.timestamp}",
            f"- **Panels:** {len(breakdown.panels)}",
            f"- **Total sub-skills:** {breakdown.total_subskills()}",
            f"- **Dims with breakdown (≥2 sub-skills):** {breakdown.dims_with_breakdown()}",
        ]
        s = breakdown.summary
        if s:
            lines.append(
                f"- **Sub-skills in [0.7, 0.95):** {s.get('subskills_in_0.7_to_0.95', 0)}"
            )
            lines.append(
                f"- **Sub-skills in [0.5, 0.95):** {s.get('subskills_in_0.5_to_0.95', 0)}"
            )
        lines.append("")

        for panel in breakdown.panels:
            broken_marker = "**[broken-down]**" if panel.has_breakdown() else "*[mirror]*"
            lines.append(
                f"### {panel.dim_name} {broken_marker}  parent={panel.parent_dim_value:.3f}"
            )
            lines.append("")
            lines.append("| sub-skill | normalized | value | max | weight |")
            lines.append("|---|---|---|---|---|")
            for sub in panel.subskills:
                lines.append(
                    f"| `{sub.name}` | {sub.normalized:.3f} {self._bar(sub.normalized, 12)} "
                    f"| {sub.value:.3f} | {sub.max_value:.3f} | {sub.weight:.2f} |"
                )
            lines.append("")

        return "\n".join(lines)
