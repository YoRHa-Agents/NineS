"""Evaluation task definition model with TOML round-trip serialization.

Provides ``TaskDefinition`` — the extended task format used by the eval
framework — bridging the lightweight ``nines.core.models.EvalTask`` with
the richer schema defined in ``docs/design/eval_framework.md`` §2.

Also provides ``EvalResult`` — the composite result of running and scoring
a single task through the eval pipeline.

Covers: FR-101, FR-102.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

from nines.core.errors import EvalError
from nines.core.models import EvalTask, Score


@dataclass
class ScoringCriterion:
    """A single criterion within a task's scoring rubric."""

    name: str
    weight: float
    description: str = ""
    scorer_type: str = "exact"
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "weight": self.weight,
            "description": self.description,
            "scorer_type": self.scorer_type,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoringCriterion:
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            weight=data["weight"],
            description=data.get("description", ""),
            scorer_type=data.get("scorer_type", "exact"),
            params=data.get("params", {}),
        )


@dataclass
class TaskDefinition:
    """Extended evaluation task with scoring criteria and TOML serialization.

    Bridges ``nines.core.models.EvalTask`` (lightweight transport model)
    with the full task definition format from the design doc §2.1.
    """

    id: str
    name: str = ""
    description: str = ""
    dimension: str = ""
    input_config: dict[str, Any] = field(default_factory=dict)
    expected: Any = None
    scoring_criteria: list[ScoringCriterion] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_core_task(self) -> EvalTask:
        """Convert to the lightweight core ``EvalTask``."""
        return EvalTask(
            id=self.id,
            name=self.name,
            description=self.description,
            dimension=self.dimension,
            input_data=self.input_config,
            expected=self.expected,
            metadata=self.metadata,
        )

    @classmethod
    def from_core_task(cls, task: EvalTask) -> TaskDefinition:
        """Construct from a core ``EvalTask``."""
        return cls(
            id=task.id,
            name=task.name,
            description=task.description,
            dimension=task.dimension,
            input_config=task.input_data if isinstance(task.input_data, dict) else {},
            expected=task.expected,
            metadata=task.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "dimension": self.dimension,
            "input_config": self.input_config,
            "metadata": dict(self.metadata),
        }
        if self.expected is not None:
            result["expected"] = self.expected
        if self.scoring_criteria:
            result["scoring_criteria"] = [c.to_dict() for c in self.scoring_criteria]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskDefinition:
        """Deserialize from dictionary."""
        criteria_raw = data.get("scoring_criteria", [])
        criteria = [ScoringCriterion.from_dict(c) for c in criteria_raw]
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            dimension=data.get("dimension", ""),
            input_config=data.get("input_config", {}),
            expected=data.get("expected"),
            scoring_criteria=criteria,
            metadata=data.get("metadata", {}),
        )

    def to_toml(self) -> str:
        """Serialize to a TOML string."""
        doc: dict[str, Any] = {"task": self._to_toml_dict()}
        return tomli_w.dumps(doc)

    def _to_toml_dict(self) -> dict[str, Any]:
        """To toml dict."""
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "dimension": self.dimension,
            "input_config": self.input_config,
            "metadata": self.metadata,
        }
        if self.expected is not None:
            if isinstance(self.expected, dict):
                data["expected"] = self.expected
            else:
                data["expected"] = {"value": self.expected}
        if self.scoring_criteria:
            data["scoring_criteria"] = [c.to_dict() for c in self.scoring_criteria]
        return data

    @classmethod
    def from_toml(cls, source: str | Path) -> TaskDefinition:
        """Deserialize from a TOML file path or TOML string."""
        if isinstance(source, Path) or (
            isinstance(source, str) and not source.strip().startswith("[")
        ):
            path = Path(source)
            if path.is_file():
                text = path.read_text(encoding="utf-8")
            else:
                raise EvalError(f"Task file not found: {path}")
        else:
            text = source

        try:
            raw = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise EvalError(f"Invalid TOML: {exc}") from exc

        task_data = raw.get("task", raw)
        input_config = task_data.get("input_config")
        if not input_config and "input" in task_data:
            input_config = task_data["input"]
        if not isinstance(input_config, dict):
            input_config = {}

        expected_raw = task_data.get("expected")
        if isinstance(expected_raw, dict):
            keys = set(expected_raw.keys())
            if keys == {"value"} or "value" in expected_raw and expected_raw.get("type") in (
                None,
                "text",
                "code",
                "pattern",
            ):
                expected_raw = expected_raw["value"]

        criteria = [
            ScoringCriterion.from_dict(c)
            for c in task_data.get("scoring_criteria", [])
        ]

        metadata = dict(task_data.get("metadata", {}))
        for meta_key in ("difficulty", "tags", "timeout_seconds", "version"):
            if meta_key in task_data and meta_key not in metadata:
                metadata[meta_key] = task_data[meta_key]

        return cls(
            id=task_data.get("id", ""),
            name=task_data.get("name", ""),
            description=task_data.get("description", ""),
            dimension=task_data.get("dimension", ""),
            input_config=input_config,
            expected=expected_raw,
            scoring_criteria=criteria,
            metadata=metadata,
        )


@dataclass
class EvalResult:
    """Composite result of running one task through the eval pipeline.

    Combines execution output with scoring results and metrics.
    """

    task_id: str
    task_name: str = ""
    output: Any = None
    scores: list[Score] = field(default_factory=list)
    composite_score: float = 0.0
    duration_ms: float = 0.0
    token_count: int = 0
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "output": self.output,
            "scores": [s.to_dict() for s in self.scores],
            "composite_score": self.composite_score,
            "duration_ms": self.duration_ms,
            "token_count": self.token_count,
            "success": self.success,
            "error": self.error,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalResult:
        """Deserialize from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_name=data.get("task_name", ""),
            output=data.get("output"),
            scores=[Score.from_dict(s) for s in data.get("scores", [])],
            composite_score=data.get("composite_score", 0.0),
            duration_ms=data.get("duration_ms", 0.0),
            token_count=data.get("token_count", 0),
            success=data.get("success", True),
            error=data.get("error"),
        )
