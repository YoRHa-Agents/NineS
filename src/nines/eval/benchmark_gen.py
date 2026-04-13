"""Benchmark task generation from key-point analysis results.

Transforms ``KeyPoint`` observations into concrete ``TaskDefinition``
benchmark suites that can be evaluated by ``EvalRunner``.

Covers: FR-115.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomli_w

from nines.eval.models import ScoringCriterion, TaskDefinition

if TYPE_CHECKING:
    from nines.analyzer.keypoint import KeyPoint

logger = logging.getLogger(__name__)

_CATEGORY_GENERATORS: dict[str, str] = {
    "compression": "_compression_tasks",
    "context_management": "_context_management_tasks",
    "behavioral_shaping": "_behavioral_shaping_tasks",
    "cross_platform": "_cross_platform_tasks",
    "semantic_preservation": "_semantic_preservation_tasks",
    "engineering": "_engineering_tasks",
}


@dataclass
class BenchmarkSuite:
    """A collection of benchmark tasks generated from key points."""

    id: str
    name: str
    description: str
    tasks: list[TaskDefinition] = field(default_factory=list)
    source_keypoints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
            "source_keypoints": list(self.source_keypoints),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkSuite:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            tasks=[TaskDefinition.from_dict(t) for t in data.get("tasks", [])],
            source_keypoints=data.get("source_keypoints", []),
            metadata=data.get("metadata", {}),
        )

    def to_toml_dir(self, path: str | Path) -> Path:
        """Write each task as an individual TOML file under *path*.

        Creates the directory if it doesn't exist.  Also writes a
        ``suite.toml`` manifest describing the suite itself.

        Returns the resolved directory path.
        """
        out = Path(path)
        out.mkdir(parents=True, exist_ok=True)

        manifest: dict[str, Any] = {
            "suite": {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "source_keypoints": list(self.source_keypoints),
                "metadata": dict(self.metadata),
                "task_count": len(self.tasks),
            },
        }
        (out / "suite.toml").write_bytes(tomli_w.dumps(manifest).encode("utf-8"))
        logger.debug("Wrote suite manifest to %s/suite.toml", out)

        for task in self.tasks:
            fname = f"{task.id}.toml"
            (out / fname).write_bytes(task.to_toml().encode("utf-8"))

        logger.info("Wrote %d task files to %s", len(self.tasks), out)
        return out


class BenchmarkGenerator:
    """Generates ``TaskDefinition`` benchmark tasks from ``KeyPoint`` objects."""

    def generate(
        self,
        key_points: list[KeyPoint],
        suite_id: str = "",
    ) -> BenchmarkSuite:
        """Generate a full benchmark suite from a list of key points."""
        sid = suite_id or uuid.uuid4().hex[:8]
        all_tasks: list[TaskDefinition] = []
        kp_ids: list[str] = []

        for kp in key_points:
            tasks = self.generate_for_keypoint(kp, suite_id=sid)
            all_tasks.extend(tasks)
            kp_ids.append(kp.id)

        categories = sorted({kp.category for kp in key_points})
        suite = BenchmarkSuite(
            id=sid,
            name=f"Benchmark suite {sid}",
            description=f"Auto-generated from {len(key_points)} key points "
            f"(categories: {', '.join(categories)})",
            tasks=all_tasks,
            source_keypoints=kp_ids,
            metadata={
                "generator": "BenchmarkGenerator",
                "keypoint_count": len(key_points),
                "categories": categories,
            },
        )
        logger.info(
            "Generated suite %s with %d tasks from %d key points",
            sid,
            len(all_tasks),
            len(key_points),
        )
        return suite

    def generate_for_keypoint(
        self,
        kp: KeyPoint,
        suite_id: str = "",
    ) -> list[TaskDefinition]:
        """Generate one or more tasks for a single key point."""
        sid = suite_id or uuid.uuid4().hex[:8]
        method_name = _CATEGORY_GENERATORS.get(kp.category, "_engineering_tasks")
        method = getattr(self, method_name)
        tasks: list[TaskDefinition] = method(kp)

        for seq, task in enumerate(tasks, start=1):
            task.id = f"bench-{sid}-{kp.id}-{seq:02d}"
            task.metadata["source_keypoint"] = kp.id
            task.metadata["category"] = kp.category

        return tasks

    # ------------------------------------------------------------------
    # Per-category generators
    # ------------------------------------------------------------------

    def _compression_tasks(self, kp: KeyPoint) -> list[TaskDefinition]:
        """Generate tasks testing compression effectiveness."""
        return [
            TaskDefinition(
                id="",
                name="Measure output length with compression",
                description=(
                    f"Evaluate compression effectiveness for: {kp.title}. "
                    f"Verify that compressed output meets size reduction targets."
                ),
                dimension="compression",
                input_config={
                    "original_text": kp.description,
                    "mechanism_ids": list(kp.mechanism_ids),
                    "target_reduction": kp.impact_magnitude,
                },
                expected={
                    "max_ratio": max(1.0 - kp.impact_magnitude, 0.1),
                    "min_reduction_pct": kp.impact_magnitude * 100,
                },
                scoring_criteria=[
                    ScoringCriterion(
                        name="size_reduction",
                        weight=0.6,
                        description="Output size is within target ratio",
                        scorer_type="exact",
                        params={"threshold": max(1.0 - kp.impact_magnitude, 0.1)},
                    ),
                    ScoringCriterion(
                        name="content_preserved",
                        weight=0.4,
                        description="Key content preserved after compression",
                        scorer_type="fuzzy",
                        params={"min_similarity": 0.7},
                    ),
                ],
                metadata={"priority": kp.priority},
            ),
            TaskDefinition(
                id="",
                name="Compare semantic similarity before/after compression",
                description=(
                    f"Verify semantic preservation during compression for: {kp.title}. "
                    f"Compare meaning retention between original and compressed forms."
                ),
                dimension="compression",
                input_config={
                    "original_text": kp.description,
                    "mechanism_ids": list(kp.mechanism_ids),
                    "validation_approach": kp.validation_approach,
                },
                expected={"min_similarity": 0.8},
                scoring_criteria=[
                    ScoringCriterion(
                        name="semantic_similarity",
                        weight=1.0,
                        description="Semantic meaning preserved after compression",
                        scorer_type="fuzzy",
                        params={"min_similarity": 0.8},
                    ),
                ],
                metadata={"priority": kp.priority},
            ),
        ]

    def _context_management_tasks(self, kp: KeyPoint) -> list[TaskDefinition]:
        """Generate tasks testing context budget impact."""
        return [
            TaskDefinition(
                id="",
                name="Measure token overhead for N interactions",
                description=(
                    f"Measure context budget overhead for: {kp.title}. "
                    f"Verify token usage stays within acceptable thresholds."
                ),
                dimension="context_management",
                input_config={
                    "interaction_count": 10,
                    "mechanism_ids": list(kp.mechanism_ids),
                    "expected_impact": kp.expected_impact,
                },
                expected={
                    "max_overhead_tokens": 500,
                    "max_overhead_pct": kp.impact_magnitude * 100,
                },
                scoring_criteria=[
                    ScoringCriterion(
                        name="token_budget",
                        weight=0.7,
                        description="Token overhead within budget",
                        scorer_type="exact",
                        params={"max_tokens": 500},
                    ),
                    ScoringCriterion(
                        name="interaction_stability",
                        weight=0.3,
                        description="Overhead stable across interactions",
                        scorer_type="exact",
                        params={"max_variance_pct": 10.0},
                    ),
                ],
                metadata={"priority": kp.priority},
            ),
        ]

    def _behavioral_shaping_tasks(self, kp: KeyPoint) -> list[TaskDefinition]:
        """Generate tasks testing behavioral rule effectiveness."""
        return [
            TaskDefinition(
                id="",
                name="Verify behavioral rule compliance in agent output",
                description=(
                    f"Check behavioral rule compliance for: {kp.title}. "
                    f"Evaluate whether agent output conforms to specified rules."
                ),
                dimension="behavioral_shaping",
                input_config={
                    "rule_description": kp.description,
                    "mechanism_ids": list(kp.mechanism_ids),
                    "evidence": list(kp.evidence),
                },
                expected={"compliance": True},
                scoring_criteria=[
                    ScoringCriterion(
                        name="rule_compliance",
                        weight=0.5,
                        description="Output follows the behavioral rule",
                        scorer_type="rubric",
                        params={"check_fn": "contains", "check_value": "compliant"},
                    ),
                    ScoringCriterion(
                        name="consistency",
                        weight=0.3,
                        description="Behavior is consistent across invocations",
                        scorer_type="rubric",
                        params={"check_fn": "present"},
                    ),
                    ScoringCriterion(
                        name="no_regression",
                        weight=0.2,
                        description="No regression in other behaviors",
                        scorer_type="exact",
                        params={},
                    ),
                ],
                metadata={"priority": kp.priority},
            ),
        ]

    def _cross_platform_tasks(self, kp: KeyPoint) -> list[TaskDefinition]:
        """Generate tasks testing cross-platform consistency."""
        return [
            TaskDefinition(
                id="",
                name="Compare output consistency across platform configs",
                description=(
                    f"Evaluate cross-platform consistency for: {kp.title}. "
                    f"Verify output matches across different platform configurations."
                ),
                dimension="cross_platform",
                input_config={
                    "platforms": ["cursor", "windsurf", "cline"],
                    "mechanism_ids": list(kp.mechanism_ids),
                    "description": kp.description,
                },
                expected={"match": True},
                scoring_criteria=[
                    ScoringCriterion(
                        name="output_match",
                        weight=1.0,
                        description="Output identical across platforms",
                        scorer_type="exact",
                        params={},
                    ),
                ],
                metadata={"priority": kp.priority},
            ),
        ]

    def _semantic_preservation_tasks(self, kp: KeyPoint) -> list[TaskDefinition]:
        """Generate tasks testing semantic preservation."""
        return [
            TaskDefinition(
                id="",
                name="Verify semantic equivalence after transformation",
                description=(
                    f"Verify semantic preservation for: {kp.title}. "
                    f"Ensure transformations do not alter meaning."
                ),
                dimension="semantic_preservation",
                input_config={
                    "original": kp.description,
                    "mechanism_ids": list(kp.mechanism_ids),
                    "validation_approach": kp.validation_approach,
                },
                expected={"min_similarity": 0.85},
                scoring_criteria=[
                    ScoringCriterion(
                        name="semantic_equivalence",
                        weight=0.7,
                        description="Meaning preserved after transformation",
                        scorer_type="fuzzy",
                        params={"min_similarity": 0.85},
                    ),
                    ScoringCriterion(
                        name="structure_preserved",
                        weight=0.3,
                        description="Structural elements retained",
                        scorer_type="fuzzy",
                        params={"min_similarity": 0.7},
                    ),
                ],
                metadata={"priority": kp.priority},
            ),
        ]

    def _engineering_tasks(self, kp: KeyPoint) -> list[TaskDefinition]:
        """Generate tasks for engineering observations."""
        return [
            TaskDefinition(
                id="",
                name="Code quality metric check",
                description=(
                    f"Verify engineering quality for: {kp.title}. "
                    f"Check code quality metrics against defined thresholds."
                ),
                dimension="engineering",
                input_config={
                    "description": kp.description,
                    "mechanism_ids": list(kp.mechanism_ids),
                    "evidence": list(kp.evidence),
                },
                expected={"passes_threshold": True},
                scoring_criteria=[
                    ScoringCriterion(
                        name="quality_threshold",
                        weight=1.0,
                        description="Metric meets minimum quality threshold",
                        scorer_type="exact",
                        params={"threshold": 0.8},
                    ),
                ],
                metadata={"priority": kp.priority},
            ),
        ]
