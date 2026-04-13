"""Key-point → evaluation-conclusion mapping.

Maps key points extracted from repository analysis to their evaluation
conclusions based on multi-round benchmark results.  Produces a
:class:`MappingTable` that summarises effectiveness, confidence, and
actionable recommendations for every key point.

Covers: FR-117.
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.analyzer.keypoint import KeyPoint
    from nines.eval.benchmark_gen import BenchmarkSuite
    from nines.eval.multi_round import MultiRoundReport

logger = logging.getLogger(__name__)

_NEGATIVE_INDICATORS = frozenset(
    {
        "negative",
        "degrad",
        "decrease",
        "worse",
        "harm",
        "reduce",
        "slow",
    }
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class KeyPointConclusion:
    """Conclusion for a single key point based on multi-round evaluation."""

    keypoint_id: str
    keypoint_title: str
    category: str
    expected_impact: str
    observed_effectiveness: str
    confidence: float
    mean_score: float
    score_std: float
    task_count: int
    evidence_summary: str
    recommendation: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keypoint_id": self.keypoint_id,
            "keypoint_title": self.keypoint_title,
            "category": self.category,
            "expected_impact": self.expected_impact,
            "observed_effectiveness": self.observed_effectiveness,
            "confidence": self.confidence,
            "mean_score": self.mean_score,
            "score_std": self.score_std,
            "task_count": self.task_count,
            "evidence_summary": self.evidence_summary,
            "recommendation": self.recommendation,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KeyPointConclusion:
        return cls(
            keypoint_id=data["keypoint_id"],
            keypoint_title=data["keypoint_title"],
            category=data["category"],
            expected_impact=data["expected_impact"],
            observed_effectiveness=data["observed_effectiveness"],
            confidence=data["confidence"],
            mean_score=data["mean_score"],
            score_std=data["score_std"],
            task_count=data["task_count"],
            evidence_summary=data["evidence_summary"],
            recommendation=data["recommendation"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class MappingTable:
    """Complete mapping from key points to evaluation conclusions."""

    target: str
    conclusions: list[KeyPointConclusion] = field(default_factory=list)
    effective_count: int = 0
    ineffective_count: int = 0
    inconclusive_count: int = 0
    overall_effectiveness: float = 0.0
    lessons_learnt: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "conclusions": [c.to_dict() for c in self.conclusions],
            "effective_count": self.effective_count,
            "ineffective_count": self.ineffective_count,
            "inconclusive_count": self.inconclusive_count,
            "overall_effectiveness": self.overall_effectiveness,
            "lessons_learnt": list(self.lessons_learnt),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MappingTable:
        return cls(
            target=data["target"],
            conclusions=[KeyPointConclusion.from_dict(c) for c in data.get("conclusions", [])],
            effective_count=data.get("effective_count", 0),
            ineffective_count=data.get("ineffective_count", 0),
            inconclusive_count=data.get("inconclusive_count", 0),
            overall_effectiveness=data.get("overall_effectiveness", 0.0),
            lessons_learnt=data.get("lessons_learnt", []),
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_markdown(self) -> str:
        """Render as a formatted markdown table."""
        header = (
            "| Key Point | Category | Expected | Observed | Score | Confidence | Recommendation |"
        )
        separator = (
            "|-----------|----------|----------|----------|-------|------------|----------------|"
        )
        lines: list[str] = [header, separator]
        for c in self.conclusions:
            lines.append(
                f"| {c.keypoint_title} "
                f"| {c.category} "
                f"| {c.expected_impact} "
                f"| {c.observed_effectiveness} "
                f"| {c.mean_score:.2f} "
                f"| {c.confidence:.2f} "
                f"| {c.recommendation} |"
            )
        return "\n".join(lines) + "\n"

    def get_effective(self) -> list[KeyPointConclusion]:
        """Return conclusions classified as effective."""
        return [c for c in self.conclusions if c.observed_effectiveness == "effective"]

    def get_by_category(self, cat: str) -> list[KeyPointConclusion]:
        """Return conclusions belonging to *cat*."""
        return [c for c in self.conclusions if c.category == cat]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _is_negative_expected(expected_impact: str) -> bool:
    """Heuristic: does *expected_impact* describe a negative outcome?"""
    lower = expected_impact.lower()
    return any(ind in lower for ind in _NEGATIVE_INDICATORS)


class MappingTableGenerator:
    """Generates a :class:`MappingTable` linking key points to conclusions."""

    def __init__(
        self,
        effectiveness_threshold: float = 0.7,
        confidence_threshold: float = 0.6,
    ) -> None:
        self._effectiveness_threshold = effectiveness_threshold
        self._confidence_threshold = confidence_threshold

    # -- public API ---------------------------------------------------------

    def generate(
        self,
        key_points: list[KeyPoint],
        report: MultiRoundReport,
        suite: BenchmarkSuite,
    ) -> MappingTable:
        """Generate mapping table from key points and evaluation results."""
        task_results = report.per_task_summary()
        conclusions: list[KeyPointConclusion] = []

        for kp in key_points:
            task_ids = self._find_tasks_for_keypoint(kp.id, suite)
            conclusion = self._map_keypoint(
                kp,
                task_results,
                task_ids,
                converged=report.converged,
            )
            conclusions.append(conclusion)

        effective = sum(1 for c in conclusions if c.observed_effectiveness == "effective")
        ineffective = sum(1 for c in conclusions if c.observed_effectiveness == "ineffective")
        inconclusive = sum(1 for c in conclusions if c.observed_effectiveness == "inconclusive")
        total = len(conclusions)

        return MappingTable(
            target=suite.name,
            conclusions=conclusions,
            effective_count=effective,
            ineffective_count=ineffective,
            inconclusive_count=inconclusive,
            overall_effectiveness=(effective / total if total else 0.0),
            lessons_learnt=self._extract_lessons(conclusions),
            metadata={
                "suite_id": suite.id,
                "converged": report.converged,
            },
        )

    # -- private helpers ----------------------------------------------------

    def _map_keypoint(
        self,
        kp: KeyPoint,
        task_results: dict[str, dict[str, Any]],
        task_ids: list[str],
        *,
        converged: bool,
    ) -> KeyPointConclusion:
        """Map a single key point to its conclusion."""
        relevant = {tid: task_results[tid] for tid in task_ids if tid in task_results}

        if not relevant:
            logger.warning(
                "No task results for key point %s",
                kp.id,
            )
            return KeyPointConclusion(
                keypoint_id=kp.id,
                keypoint_title=kp.title,
                category=kp.category,
                expected_impact=kp.expected_impact,
                observed_effectiveness="inconclusive",
                confidence=0.0,
                mean_score=0.0,
                score_std=0.0,
                task_count=0,
                evidence_summary="No matching task results found.",
                recommendation=("Requires more evaluation rounds or better test design"),
                metadata={},
            )

        means = [r["mean"] for r in relevant.values()]
        stds = [r["std"] for r in relevant.values()]
        task_count = len(relevant)

        mean_score = sum(means) / task_count
        score_std = math.sqrt(sum(s**2 for s in stds) / task_count) if stds else 0.0

        confidence = self._compute_confidence(
            score_std,
            task_count,
            converged,
        )
        effectiveness = self._determine_effectiveness(
            mean_score,
            confidence,
        )

        conclusion = KeyPointConclusion(
            keypoint_id=kp.id,
            keypoint_title=kp.title,
            category=kp.category,
            expected_impact=kp.expected_impact,
            observed_effectiveness=effectiveness,
            confidence=confidence,
            mean_score=mean_score,
            score_std=score_std,
            task_count=task_count,
            evidence_summary=(
                f"Evaluated across {task_count} task(s). "
                f"Mean score: {mean_score:.2f} "
                f"(±{score_std:.2f}). "
                f"Result: {effectiveness} "
                f"at {confidence:.0%} confidence."
            ),
            recommendation="",
            metadata={},
        )
        conclusion.recommendation = self._generate_recommendation(
            kp,
            conclusion,
        )
        return conclusion

    def _determine_effectiveness(
        self,
        mean_score: float,
        confidence: float,
    ) -> str:
        """Determine effectiveness based on score and confidence."""
        eff_t = self._effectiveness_threshold
        conf_t = self._confidence_threshold

        if confidence < conf_t * 0.5:
            return "inconclusive"
        if mean_score >= eff_t and confidence >= conf_t:
            return "effective"
        if mean_score >= eff_t * 0.6 and confidence >= conf_t:
            return "partially_effective"
        return "ineffective"

    def _compute_confidence(
        self,
        score_std: float,
        task_count: int,
        converged: bool,
    ) -> float:
        """Compute confidence from variance, sample size, convergence."""
        if task_count == 0:
            return 0.0
        sample_factor = min(1.0, task_count / 5.0)
        stability_factor = max(0.0, 1.0 - score_std)
        convergence_bonus = 0.1 if converged else 0.0
        raw = sample_factor * stability_factor + convergence_bonus
        return max(0.0, min(1.0, raw))

    def _generate_recommendation(
        self,
        kp: KeyPoint,
        conclusion: KeyPointConclusion,
    ) -> str:
        """Generate actionable recommendation based on conclusion."""
        eff = conclusion.observed_effectiveness

        if eff == "inconclusive":
            return "Requires more evaluation rounds or better test design"
        if eff == "ineffective":
            return "Not recommended: insufficient evidence of benefit"
        if eff == "partially_effective":
            return f"Needs refinement: consider optimizing '{kp.title}' for stronger results"
        if _is_negative_expected(kp.expected_impact):
            return f"Warning: '{kp.title}' degrades performance despite initial expectations"
        return f"Validated: adopt '{kp.title}' as a proven technique"

    def _extract_lessons(
        self,
        conclusions: list[KeyPointConclusion],
    ) -> list[str]:
        """Extract lessons learnt from all conclusions."""
        lessons: list[str] = []

        by_cat: dict[str, list[KeyPointConclusion]] = defaultdict(
            list,
        )
        for c in conclusions:
            by_cat[c.category].append(c)

        for cat, group in sorted(by_cat.items()):
            if len(group) < 2:
                continue
            eff = sum(1 for c in group if c.observed_effectiveness == "effective")
            total = len(group)
            if eff == total:
                lessons.append(f"All '{cat}' techniques proved effective ({eff}/{total}).")
            elif eff == 0:
                lessons.append(
                    f"No '{cat}' techniques showed sufficient effectiveness (0/{total})."
                )
            else:
                lessons.append(f"'{cat}' techniques had mixed results ({eff}/{total} effective).")

        for c in conclusions:
            neg = _is_negative_expected(c.expected_impact)
            if c.observed_effectiveness == "effective" and neg:
                lessons.append(
                    f"Unexpected positive: '{c.keypoint_title}' "
                    f"was expected to degrade performance "
                    f"but proved effective."
                )
            elif c.observed_effectiveness == "ineffective" and not neg:
                lessons.append(
                    f"Underperformed: '{c.keypoint_title}' was "
                    f"expected to help but showed no significant "
                    f"benefit."
                )

        return lessons

    def _find_tasks_for_keypoint(
        self,
        kp_id: str,
        suite: BenchmarkSuite,
    ) -> list[str]:
        """Find task IDs for a key point by parsing the ID format.

        Task IDs follow ``bench-{suite_id}-{kp.id}-{seq:02d}``.
        """
        needle = f"-{kp_id}-"
        return [t.id for t in suite.tasks if needle in t.id]
