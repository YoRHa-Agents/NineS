"""Key-point extraction from Agent impact reports.

Transforms an ``AgentImpactReport`` (and optionally an ``AnalysisResult``)
into a ranked list of actionable ``KeyPoint`` objects suitable for
downstream benchmark test generation.

Covers: FR-314.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.analyzer.agent_impact import (
        AgentImpactReport,
        AgentMechanism,
        ContextEconomics,
    )
    from nines.core.models import AnalysisResult, Finding

logger = logging.getLogger(__name__)

VALID_CATEGORIES = frozenset(
    {
        "compression",
        "context_management",
        "behavioral_shaping",
        "cross_platform",
        "semantic_preservation",
        "engineering",
    }
)

VALID_IMPACTS = frozenset({"positive", "negative", "neutral", "uncertain"})

_MECHANISM_CATEGORY_MAP: dict[str, str] = {
    "context_compression": "compression",
    "behavioral_instruction": "behavioral_shaping",
    "distribution": "cross_platform",
    "safety": "semantic_preservation",
    "persistence": "semantic_preservation",
}

_CATEGORY_VALIDATION_TEMPLATES: dict[str, str] = {
    "compression": ("Run compression benchmark: compare output length with/without this mechanism"),
    "behavioral_shaping": (
        "A/B test agent output quality with this behavioral rule enabled vs disabled"
    ),
    "cross_platform": (
        "Deploy to multiple platforms and verify consistent behavior across IDE integrations"
    ),
    "semantic_preservation": (
        "Run semantic equivalence checks before/after applying this preservation mechanism"
    ),
    "context_management": (
        "Measure token overhead across N interactions and compute break-even point"
    ),
    "engineering": (
        "Review code quality metrics and verify adherence to engineering best practices"
    ),
}


@dataclass
class KeyPoint:
    """A single actionable finding about how a repo affects agent effectiveness.

    Attributes
    ----------
    id:
        Unique identifier for this key point.
    category:
        One of ``"compression"``, ``"context_management"``,
        ``"behavioral_shaping"``, ``"cross_platform"``,
        ``"semantic_preservation"``, or ``"engineering"``.
    title:
        Short human-readable title.
    description:
        Detailed description of the key point.
    mechanism_ids:
        IDs of ``AgentMechanism`` instances that support this key point.
    expected_impact:
        One of ``"positive"``, ``"negative"``, ``"neutral"``,
        ``"uncertain"``.
    impact_magnitude:
        Magnitude in ``[0.0, 1.0]``.
    validation_approach:
        Human-readable description of how to validate this key point.
    evidence:
        File paths or textual descriptions supporting this key point.
    priority:
        Priority from 1 (highest) to 5 (lowest).
    metadata:
        Free-form metadata.
    """

    id: str
    category: str
    title: str
    description: str
    mechanism_ids: list[str] = field(default_factory=list)
    expected_impact: str = "uncertain"
    impact_magnitude: float = 0.0
    validation_approach: str = ""
    evidence: list[str] = field(default_factory=list)
    priority: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "mechanism_ids": list(self.mechanism_ids),
            "expected_impact": self.expected_impact,
            "impact_magnitude": self.impact_magnitude,
            "validation_approach": self.validation_approach,
            "evidence": list(self.evidence),
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KeyPoint:
        """Deserialize from a plain dictionary."""
        return cls(
            id=data["id"],
            category=data.get("category", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            mechanism_ids=list(data.get("mechanism_ids", [])),
            expected_impact=data.get("expected_impact", "uncertain"),
            impact_magnitude=data.get("impact_magnitude", 0.0),
            validation_approach=data.get("validation_approach", ""),
            evidence=list(data.get("evidence", [])),
            priority=data.get("priority", 3),
            metadata=data.get("metadata", {}),
        )


@dataclass
class KeyPointReport:
    """Aggregated report of all extracted key points.

    Attributes
    ----------
    target:
        Filesystem path that was analyzed.
    key_points:
        Extracted ``KeyPoint`` instances.
    summary:
        Human-readable summary of the extraction.
    extraction_duration_ms:
        Wall-clock time spent extracting, in milliseconds.
    metadata:
        Free-form metadata.
    """

    target: str
    key_points: list[KeyPoint] = field(default_factory=list)
    summary: str = ""
    extraction_duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "target": self.target,
            "key_points": [kp.to_dict() for kp in self.key_points],
            "summary": self.summary,
            "extraction_duration_ms": self.extraction_duration_ms,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KeyPointReport:
        """Deserialize from a plain dictionary."""
        return cls(
            target=data["target"],
            key_points=[KeyPoint.from_dict(kp) for kp in data.get("key_points", [])],
            summary=data.get("summary", ""),
            extraction_duration_ms=data.get("extraction_duration_ms", 0.0),
            metadata=data.get("metadata", {}),
        )

    def get_by_category(self, category: str) -> list[KeyPoint]:
        """Return key points matching the given category."""
        return [kp for kp in self.key_points if kp.category == category]

    def get_by_priority(self, priority: int) -> list[KeyPoint]:
        """Return key points matching the given priority level."""
        return [kp for kp in self.key_points if kp.priority == priority]

    def high_priority(self) -> list[KeyPoint]:
        """Return key points with priority 1 or 2."""
        return [kp for kp in self.key_points if kp.priority <= 2]


class KeyPointExtractor:
    """Extracts actionable key points from agent impact analysis results.

    Transforms mechanisms, economics, findings, and optional code analysis
    into a prioritized, deduplicated list of ``KeyPoint`` instances.
    """

    def extract(
        self,
        impact_report: AgentImpactReport,
        analysis_result: AnalysisResult | None = None,
    ) -> KeyPointReport:
        """Extract key points from agent impact analysis and optional code analysis.

        Parameters
        ----------
        impact_report:
            The ``AgentImpactReport`` to extract key points from.
        analysis_result:
            Optional ``AnalysisResult`` for supplementary engineering insights.

        Returns
        -------
        KeyPointReport
            Report containing all extracted, deduplicated, and prioritized
            key points.
        """
        start_ns = time.monotonic_ns()

        logger.info("Extracting key points from report for %s", impact_report.target)

        all_points: list[KeyPoint] = []

        try:
            all_points.extend(self._extract_from_mechanisms(impact_report.mechanisms))
        except Exception:
            logger.exception(
                "Error extracting key points from mechanisms for %s",
                impact_report.target,
            )

        try:
            all_points.extend(self._extract_from_economics(impact_report.economics))
        except Exception:
            logger.exception(
                "Error extracting key points from economics for %s",
                impact_report.target,
            )

        try:
            all_points.extend(self._extract_from_findings(impact_report.findings))
        except Exception:
            logger.exception(
                "Error extracting key points from findings for %s",
                impact_report.target,
            )

        if analysis_result is not None:
            try:
                all_points.extend(self._extract_from_analysis(analysis_result))
            except Exception:
                logger.exception(
                    "Error extracting key points from analysis for %s",
                    impact_report.target,
                )

        all_points = self._deduplicate(all_points)
        all_points = self._prioritize(all_points)

        elapsed_ms = (time.monotonic_ns() - start_ns) / 1_000_000

        category_counts = _count_categories(all_points)
        summary = self._build_summary(all_points, category_counts)

        logger.info(
            "Extracted %d key points in %.1fms for %s",
            len(all_points),
            elapsed_ms,
            impact_report.target,
        )

        return KeyPointReport(
            target=impact_report.target,
            key_points=all_points,
            summary=summary,
            extraction_duration_ms=round(elapsed_ms, 2),
            metadata={"category_counts": category_counts},
        )

    def _extract_from_mechanisms(
        self,
        mechanisms: list[AgentMechanism],
    ) -> list[KeyPoint]:
        """Create one key point per mechanism, categorized and prioritized.

        Parameters
        ----------
        mechanisms:
            Agent mechanisms from the impact report.

        Returns
        -------
        list[KeyPoint]
            One ``KeyPoint`` per mechanism.
        """
        points: list[KeyPoint] = []
        for mech in mechanisms:
            category = _MECHANISM_CATEGORY_MAP.get(mech.category, "engineering")
            impact = _infer_impact_from_token_delta(mech.estimated_token_impact)
            magnitude = min(1.0, abs(mech.estimated_token_impact) / 5000) * mech.confidence

            points.append(
                KeyPoint(
                    id=f"kp-mech-{uuid.uuid4().hex[:8]}",
                    category=category,
                    title=f"Mechanism: {mech.name}",
                    description=mech.description,
                    mechanism_ids=[mech.id],
                    expected_impact=impact,
                    impact_magnitude=round(min(1.0, magnitude), 3),
                    validation_approach=_CATEGORY_VALIDATION_TEMPLATES.get(
                        category, "Manual review of mechanism behavior"
                    ),
                    evidence=list(mech.evidence_files),
                    priority=_mechanism_priority(mech),
                    metadata={
                        "source": "mechanism",
                        "mechanism_category": mech.category,
                        "confidence": mech.confidence,
                    },
                )
            )
        return points

    def _extract_from_economics(
        self,
        economics: ContextEconomics,
    ) -> list[KeyPoint]:
        """Extract key points about token economics.

        Generates points for high overhead, low savings ratio, and
        break-even characteristics.

        Parameters
        ----------
        economics:
            Context economics from the impact report.

        Returns
        -------
        list[KeyPoint]
            Economics-derived key points (may be empty).
        """
        points: list[KeyPoint] = []

        if economics.overhead_tokens > 0:
            high_overhead = economics.overhead_tokens > 5000
            magnitude = min(1.0, economics.overhead_tokens / 10000)
            points.append(
                KeyPoint(
                    id=f"kp-econ-overhead-{uuid.uuid4().hex[:8]}",
                    category="context_management",
                    title="Token overhead analysis",
                    description=(
                        f"Agent context overhead is {economics.overhead_tokens} tokens "
                        f"across {economics.agent_facing_files} file(s). "
                        + (
                            "This is high and may degrade agent performance."
                            if high_overhead
                            else "This is within acceptable bounds."
                        )
                    ),
                    expected_impact="negative" if high_overhead else "neutral",
                    impact_magnitude=round(magnitude, 3),
                    validation_approach=(
                        "Measure token overhead across N interactions and compute break-even point"
                    ),
                    evidence=[],
                    priority=3,
                    metadata={
                        "source": "economics",
                        "overhead_tokens": economics.overhead_tokens,
                    },
                )
            )

        if economics.estimated_savings_ratio > 0:
            low_savings = economics.estimated_savings_ratio < 0.1
            points.append(
                KeyPoint(
                    id=f"kp-econ-savings-{uuid.uuid4().hex[:8]}",
                    category="context_management",
                    title="Token savings efficiency",
                    description=(
                        f"Estimated savings ratio is "
                        f"{economics.estimated_savings_ratio:.1%}"
                        + (
                            " — below typical thresholds for net-positive economics."
                            if low_savings
                            else " — indicates effective token reuse."
                        )
                    ),
                    expected_impact="negative" if low_savings else "positive",
                    impact_magnitude=round(
                        1.0 - economics.estimated_savings_ratio,
                        3,
                    ),
                    validation_approach=(
                        "Track actual token usage over multiple sessions "
                        "and compare against baseline"
                    ),
                    evidence=[],
                    priority=3,
                    metadata={
                        "source": "economics",
                        "savings_ratio": economics.estimated_savings_ratio,
                    },
                )
            )

        if economics.break_even_interactions > 0:
            late_break_even = economics.break_even_interactions > 10
            points.append(
                KeyPoint(
                    id=f"kp-econ-breakeven-{uuid.uuid4().hex[:8]}",
                    category="context_management",
                    title="Break-even interaction threshold",
                    description=(
                        f"Break-even at {economics.break_even_interactions} "
                        f"interaction(s)"
                        + (
                            " — users need many sessions to recoup overhead."
                            if late_break_even
                            else " — overhead is recovered quickly."
                        )
                    ),
                    expected_impact="negative" if late_break_even else "positive",
                    impact_magnitude=round(
                        min(1.0, economics.break_even_interactions / 20),
                        3,
                    ),
                    validation_approach=(
                        "Simulate N agent interactions and measure cumulative token cost vs savings"
                    ),
                    evidence=[],
                    priority=3,
                    metadata={
                        "source": "economics",
                        "break_even": economics.break_even_interactions,
                    },
                )
            )

        return points

    def _extract_from_findings(
        self,
        findings: list[Finding],
    ) -> list[KeyPoint]:
        """Convert severity-tagged findings into key points.

        Parameters
        ----------
        findings:
            Findings from the impact report.

        Returns
        -------
        list[KeyPoint]
            One ``KeyPoint`` per non-trivial finding.
        """
        severity_impact_map: dict[str, str] = {
            "critical": "negative",
            "error": "negative",
            "warning": "negative",
            "info": "neutral",
        }
        severity_magnitude_map: dict[str, float] = {
            "critical": 0.9,
            "error": 0.7,
            "warning": 0.5,
            "info": 0.2,
        }
        severity_priority_map: dict[str, int] = {
            "critical": 1,
            "error": 2,
            "warning": 3,
            "info": 4,
        }

        points: list[KeyPoint] = []
        for finding in findings:
            category = _finding_category_to_keypoint(finding.category)
            points.append(
                KeyPoint(
                    id=f"kp-find-{uuid.uuid4().hex[:8]}",
                    category=category,
                    title=f"Finding: {finding.category}",
                    description=finding.message,
                    expected_impact=severity_impact_map.get(
                        finding.severity,
                        "uncertain",
                    ),
                    impact_magnitude=severity_magnitude_map.get(
                        finding.severity,
                        0.2,
                    ),
                    validation_approach=_CATEGORY_VALIDATION_TEMPLATES.get(
                        category, "Manual review of finding details"
                    ),
                    evidence=[finding.location] if finding.location else [],
                    priority=severity_priority_map.get(finding.severity, 4),
                    metadata={
                        "source": "finding",
                        "finding_id": finding.id,
                        "severity": finding.severity,
                    },
                )
            )
        return points

    def _extract_from_analysis(
        self,
        result: AnalysisResult,
    ) -> list[KeyPoint]:
        """Extract engineering key points from code analysis results.

        These are lower-priority observations from static code analysis.

        Parameters
        ----------
        result:
            Code analysis result.

        Returns
        -------
        list[KeyPoint]
            Engineering-category key points.
        """
        points: list[KeyPoint] = []

        max_eng_findings = 5
        actionable_severities = {"critical", "error"}
        eng_count = 0

        for finding in result.findings:
            if eng_count >= max_eng_findings:
                break
            if hasattr(finding, "to_dict"):
                f_dict = finding.to_dict()
                msg = f_dict.get("message", str(finding))
                loc = f_dict.get("location", "")
                sev = f_dict.get("severity", "info")
            else:
                msg = str(finding)
                loc = ""
                sev = "info"

            if sev not in actionable_severities:
                continue

            magnitude_map: dict[str, float] = {
                "critical": 0.7,
                "error": 0.5,
            }

            points.append(
                KeyPoint(
                    id=f"kp-eng-{uuid.uuid4().hex[:8]}",
                    category="engineering",
                    title="Engineering observation",
                    description=msg,
                    expected_impact="neutral",
                    impact_magnitude=magnitude_map.get(sev, 0.5),
                    validation_approach=(
                        "Review code quality metrics and verify adherence to "
                        "engineering best practices"
                    ),
                    evidence=[loc] if loc else [],
                    priority=5,
                    metadata={
                        "source": "analysis",
                        "analysis_target": result.target,
                    },
                )
            )
            eng_count += 1

        agent_relevant = {
            k: v for k, v in result.metrics.items()
            if k in ("agent_impact", "key_points", "total_files_scanned")
        }
        if agent_relevant:
            points.append(
                KeyPoint(
                    id=f"kp-summary-{uuid.uuid4().hex[:8]}",
                    category="engineering",
                    title="Analysis coverage summary",
                    description=(
                        f"Analysis covered {result.metrics.get('files_analyzed', 0)} Python files "
                        f"and {result.metrics.get('total_files_scanned', 0)} total files. "
                        f"{result.metrics.get('knowledge_units', 0)} knowledge units extracted."
                    ),
                    expected_impact="neutral",
                    impact_magnitude=0.1,
                    validation_approach="Verify analysis coverage is comprehensive",
                    evidence=[],
                    priority=5,
                    metadata={
                        "source": "analysis_summary",
                        "files_analyzed": result.metrics.get("files_analyzed", 0),
                        "knowledge_units": result.metrics.get("knowledge_units", 0),
                    },
                )
            )

        return points

    def _deduplicate(self, points: list[KeyPoint]) -> list[KeyPoint]:
        """Remove duplicate or overlapping key points.

        Two points are considered duplicates if they share the same
        category and a sufficiently similar title (normalized).

        Parameters
        ----------
        points:
            Unsorted key points, possibly with duplicates.

        Returns
        -------
        list[KeyPoint]
            Deduplicated list; when duplicates exist the one with the
            higher impact magnitude is kept.
        """
        seen: dict[str, KeyPoint] = {}
        for point in points:
            key = f"{point.category}::{point.title.lower().strip()}"
            if key in seen:
                if point.impact_magnitude > seen[key].impact_magnitude:
                    seen[key] = point
            else:
                seen[key] = point
        return list(seen.values())

    def _prioritize(self, points: list[KeyPoint]) -> list[KeyPoint]:
        """Assign and sort by priority based on impact and category.

        Priority rules:
        - P1: impact_magnitude >= 0.7 and source is mechanism with
              high confidence
        - P2: impact_magnitude >= 0.4 and source is mechanism
        - P3: economics-based key points
        - P4: low-confidence mechanisms and coverage gaps
        - P5: engineering observations

        Parameters
        ----------
        points:
            Key points to re-prioritize.

        Returns
        -------
        list[KeyPoint]
            Sorted by priority (ascending), then impact_magnitude
            (descending).
        """
        for point in points:
            source = point.metadata.get("source", "")
            confidence = point.metadata.get("confidence", 0.0)

            if source == "mechanism":
                if point.impact_magnitude >= 0.7 and confidence >= 0.7:
                    point.priority = 1
                elif point.impact_magnitude >= 0.4 or confidence >= 0.5:
                    point.priority = 2
                else:
                    point.priority = 4
            elif source == "economics":
                point.priority = 3
            elif source in ("analysis", "analysis_metric"):
                point.priority = 5
            elif source == "finding":
                severity = point.metadata.get("severity", "info")
                if severity in ("critical", "error"):
                    point.priority = 2
                elif severity == "warning":
                    point.priority = 3
                else:
                    point.priority = 4

        return sorted(
            points,
            key=lambda kp: (kp.priority, -kp.impact_magnitude),
        )

    @staticmethod
    def _build_summary(
        points: list[KeyPoint],
        category_counts: dict[str, int],
    ) -> str:
        """Build a human-readable summary of extracted key points."""
        if not points:
            return "No key points extracted."

        parts = [f"Extracted {len(points)} key point(s)"]
        for cat, count in sorted(category_counts.items()):
            parts.append(f"{cat}: {count}")

        high = [kp for kp in points if kp.priority <= 2]
        if high:
            parts.append(f"{len(high)} high-priority item(s)")

        return ". ".join(parts) + "."


def _infer_impact_from_token_delta(token_impact: int) -> str:
    """Map a token delta to an expected impact label."""
    if token_impact < -100:
        return "positive"
    if token_impact > 500:
        return "negative"
    if token_impact == 0:
        return "uncertain"
    return "neutral"


def _mechanism_priority(mech: AgentMechanism) -> int:
    """Compute initial priority for a mechanism-derived key point."""
    if mech.confidence >= 0.7 and abs(mech.estimated_token_impact) > 500:
        return 1
    if mech.confidence >= 0.5:
        return 2
    return 4


def _finding_category_to_keypoint(finding_category: str) -> str:
    """Map a Finding.category to a KeyPoint category."""
    mapping: dict[str, str] = {
        "agent_impact": "behavioral_shaping",
        "context_economics": "context_management",
        "coverage_gap": "context_management",
        "low_confidence": "behavioral_shaping",
    }
    return mapping.get(finding_category, "engineering")


def _count_categories(points: list[KeyPoint]) -> dict[str, int]:
    """Count key points per category."""
    counts: dict[str, int] = {}
    for kp in points:
        counts[kp.category] = counts.get(kp.category, 0) + 1
    return counts
