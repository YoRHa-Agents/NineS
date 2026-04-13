"""Core data models shared across all NineS modules.

All models are plain ``@dataclass`` instances with ``to_dict()`` /
``from_dict()`` round-trip serialization.  They carry no business logic
beyond construction validation and serialization so that ``core/``
remains a zero-dependency foundation layer.

Covers: FR-101, FR-305, FR-510.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class EvalTask:
    """Canonical in-memory representation of a single evaluation task.

    Attributes
    ----------
    id:
        Unique task identifier (UUID string recommended).
    name:
        Human-readable short name.
    description:
        Longer description of what the task evaluates.
    dimension:
        Evaluation dimension this task belongs to (e.g. ``"code_quality"``).
    input_data:
        Arbitrary input payload consumed by the executor.
    expected:
        Ground-truth / expected output for scoring.
    metadata:
        Free-form metadata (tags, difficulty, version, etc.).
    """

    id: str
    name: str = ""
    description: str = ""
    dimension: str = ""
    input_data: Any = None
    expected: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "dimension": self.dimension,
            "input_data": self.input_data,
            "expected": self.expected,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalTask:
        """Deserialize from a plain dictionary."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            dimension=data.get("dimension", ""),
            input_data=data.get("input_data"),
            expected=data.get("expected"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExecutionResult:
    """Output captured from executing a single evaluation task.

    Attributes
    ----------
    task_id:
        ID of the ``EvalTask`` that was executed.
    output:
        Raw output produced by the executor.
    metrics:
        Executor-reported metrics (resource usage, token counts, etc.).
    duration_ms:
        Wall-clock execution time in milliseconds.
    success:
        Whether the execution completed without fatal errors.
    """

    task_id: str
    output: Any = None
    metrics: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "task_id": self.task_id,
            "output": self.output,
            "metrics": dict(self.metrics),
            "duration_ms": self.duration_ms,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionResult:
        """Deserialize from a plain dictionary."""
        return cls(
            task_id=data["task_id"],
            output=data.get("output"),
            metrics=data.get("metrics", {}),
            duration_ms=data.get("duration_ms", 0.0),
            success=data.get("success", True),
        )


@dataclass
class Score:
    """A single scorer's evaluation of one task execution.

    Attributes
    ----------
    value:
        Numeric score in ``[0, max_value]``.
    max_value:
        Upper bound of the score range (default 1.0).
    breakdown:
        Per-criterion or per-metric breakdown.
    scorer_name:
        Identifier of the scorer that produced this score.
    """

    value: float
    max_value: float = 1.0
    breakdown: dict[str, Any] = field(default_factory=dict)
    scorer_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "value": self.value,
            "max_value": self.max_value,
            "breakdown": dict(self.breakdown),
            "scorer_name": self.scorer_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Score:
        """Deserialize from a plain dictionary."""
        return cls(
            value=data["value"],
            max_value=data.get("max_value", 1.0),
            breakdown=data.get("breakdown", {}),
            scorer_name=data.get("scorer_name", ""),
        )


@dataclass
class ScoreCard:
    """Aggregated scoring for a single task across one or more scorers.

    Attributes
    ----------
    task_id:
        ID of the evaluated ``EvalTask``.
    scores:
        Individual ``Score`` objects from each scorer.
    composite:
        Weighted composite score across all scorers.
    reliability:
        Statistical reliability metrics (pass@k, consistency, etc.).
    """

    task_id: str
    scores: list[Score] = field(default_factory=list)
    composite: float = 0.0
    reliability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "task_id": self.task_id,
            "scores": [s.to_dict() for s in self.scores],
            "composite": self.composite,
            "reliability": dict(self.reliability),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoreCard:
        """Deserialize from a plain dictionary."""
        return cls(
            task_id=data["task_id"],
            scores=[Score.from_dict(s) for s in data.get("scores", [])],
            composite=data.get("composite", 0.0),
            reliability=data.get("reliability", {}),
        )


@dataclass
class CollectionResult:
    """A single item returned by a ``SourceCollector``.

    Attributes
    ----------
    source:
        Name of the collection source (e.g. ``"github"``, ``"arxiv"``).
    identifier:
        Source-specific unique key (URL, DOI, repo slug, etc.).
    data:
        The collected payload.
    collected_at:
        ISO-8601 timestamp of when the item was collected.
    metadata:
        Additional source-specific metadata.
    """

    source: str
    identifier: str
    data: Any = None
    collected_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "source": self.source,
            "identifier": self.identifier,
            "data": self.data,
            "collected_at": self.collected_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollectionResult:
        """Deserialize from a plain dictionary."""
        return cls(
            source=data["source"],
            identifier=data["identifier"],
            data=data.get("data"),
            collected_at=data.get(
                "collected_at", datetime.now(UTC).isoformat()
            ),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AnalysisResult:
    """Output from an ``Analyzer`` run against a code target.

    Attributes
    ----------
    target:
        Filesystem path that was analyzed.
    findings:
        List of ``Finding`` objects discovered during analysis.
    metrics:
        Aggregate metrics (complexity, coupling, etc.).
    timestamp:
        ISO-8601 timestamp of when the analysis was performed.
    """

    target: str
    findings: list[Any] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "target": self.target,
            "findings": [
                f.to_dict() if hasattr(f, "to_dict") else f
                for f in self.findings
            ],
            "metrics": dict(self.metrics),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisResult:
        """Deserialize from a plain dictionary."""
        findings_raw = data.get("findings", [])
        findings = [
            Finding.from_dict(f) if isinstance(f, dict) else f
            for f in findings_raw
        ]
        return cls(
            target=data["target"],
            findings=findings,
            metrics=data.get("metrics", {}),
            timestamp=data.get(
                "timestamp", datetime.now(UTC).isoformat()
            ),
        )


@dataclass
class KnowledgeUnit:
    """An atomic piece of extracted knowledge from code analysis.

    Produced by the decomposer during analysis Stage 4.

    Attributes
    ----------
    id:
        Unique identifier for this knowledge unit.
    source:
        Filesystem path or URI the unit was extracted from.
    content:
        The extracted content (code snippet, docstring, pattern, etc.).
    unit_type:
        Classification (``"function"``, ``"class"``, ``"module"``,
        ``"concern"``, etc.).
    relationships:
        Links to other units (e.g. ``{"calls": [...], "imports": [...]}``).
    metadata:
        Additional context (complexity, layer assignment, tags, etc.).
    """

    id: str
    source: str = ""
    content: str = ""
    unit_type: str = ""
    relationships: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "source": self.source,
            "content": self.content,
            "unit_type": self.unit_type,
            "relationships": dict(self.relationships),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeUnit:
        """Deserialize from a plain dictionary."""
        return cls(
            id=data["id"],
            source=data.get("source", ""),
            content=data.get("content", ""),
            unit_type=data.get("unit_type", ""),
            relationships=data.get("relationships", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Finding:
    """A single issue or observation discovered during analysis.

    Attributes
    ----------
    id:
        Unique finding identifier.
    severity:
        Severity level (``"info"``, ``"warning"``, ``"error"``,
        ``"critical"``).
    category:
        Classification category (``"complexity"``, ``"coupling"``,
        ``"style"``, ``"architecture"``, etc.).
    message:
        Human-readable description of the finding.
    location:
        File path and/or line information where the finding applies.
    suggestion:
        Optional actionable suggestion for remediation.
    """

    id: str
    severity: str = "info"
    category: str = ""
    message: str = ""
    location: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        """Deserialize from a plain dictionary."""
        return cls(
            id=data["id"],
            severity=data.get("severity", "info"),
            category=data.get("category", ""),
            message=data.get("message", ""),
            location=data.get("location", ""),
            suggestion=data.get("suggestion", ""),
        )
