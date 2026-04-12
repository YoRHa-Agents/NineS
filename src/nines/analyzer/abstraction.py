"""Pattern detection and abstraction from knowledge units.

``AbstractionLayer`` identifies recurring patterns across ``KnowledgeUnit``
objects using naming conventions and structural similarity heuristics.

Covers: FR-312.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from nines.core.models import KnowledgeUnit

logger = logging.getLogger(__name__)

_NAMING_PATTERNS: dict[str, re.Pattern[str]] = {
    "factory": re.compile(r"(?:create|make|build|new)_\w+", re.IGNORECASE),
    "handler": re.compile(r"\w+_handler|handle_\w+|on_\w+", re.IGNORECASE),
    "validator": re.compile(r"validate_\w+|\w+_validator|check_\w+", re.IGNORECASE),
    "converter": re.compile(r"(?:to|from|convert|parse)_\w+", re.IGNORECASE),
    "singleton": re.compile(r"get_instance|_instance", re.IGNORECASE),
    "observer": re.compile(r"(?:subscribe|notify|emit|on_)\w+", re.IGNORECASE),
    "decorator": re.compile(r"(?:wrap|decorate|with_)\w+", re.IGNORECASE),
}


@dataclass
class Pattern:
    """A detected pattern across knowledge units."""

    name: str
    description: str = ""
    instances: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "instances": list(self.instances),
            "confidence": self.confidence,
        }


class AbstractionLayer:
    """Extracts patterns from knowledge units using naming and structural heuristics."""

    def __init__(self, min_instances: int = 2, min_confidence: float = 0.3) -> None:
        self._min_instances = min_instances
        self._min_confidence = min_confidence

    def extract_patterns(self, units: list[KnowledgeUnit]) -> list[Pattern]:
        """Analyze units and return detected patterns."""
        patterns: list[Pattern] = []
        patterns.extend(self._detect_naming_patterns(units))
        patterns.extend(self._detect_structural_patterns(units))
        patterns.extend(self._detect_type_clusters(units))
        return [p for p in patterns if p.confidence >= self._min_confidence]

    def _detect_naming_patterns(self, units: list[KnowledgeUnit]) -> list[Pattern]:
        """Detect patterns based on naming conventions in unit content/source."""
        pattern_hits: dict[str, list[str]] = defaultdict(list)

        for unit in units:
            text = f"{unit.content} {unit.source} {unit.id}"
            for pname, regex in _NAMING_PATTERNS.items():
                if regex.search(text):
                    pattern_hits[pname].append(unit.id)

        patterns: list[Pattern] = []
        for pname, instance_ids in pattern_hits.items():
            if len(instance_ids) < self._min_instances:
                continue
            confidence = min(1.0, len(instance_ids) / max(len(units), 1))
            patterns.append(Pattern(
                name=f"naming:{pname}",
                description=f"Units matching the '{pname}' naming convention",
                instances=instance_ids,
                confidence=confidence,
            ))
        return patterns

    def _detect_structural_patterns(self, units: list[KnowledgeUnit]) -> list[Pattern]:
        """Detect patterns based on structural similarity in relationships."""
        relationship_shapes: dict[str, list[str]] = defaultdict(list)

        for unit in units:
            if not unit.relationships:
                continue
            shape_key = ",".join(sorted(unit.relationships.keys()))
            relationship_shapes[shape_key].append(unit.id)

        patterns: list[Pattern] = []
        for shape, instance_ids in relationship_shapes.items():
            if len(instance_ids) < self._min_instances:
                continue
            confidence = min(1.0, len(instance_ids) / max(len(units), 1))
            patterns.append(Pattern(
                name=f"structural:{shape}",
                description=f"Units sharing relationship structure: {shape}",
                instances=instance_ids,
                confidence=confidence,
            ))
        return patterns

    def _detect_type_clusters(self, units: list[KnowledgeUnit]) -> list[Pattern]:
        """Detect clusters of units sharing the same unit_type."""
        type_groups: dict[str, list[str]] = defaultdict(list)
        for unit in units:
            if unit.unit_type:
                type_groups[unit.unit_type].append(unit.id)

        patterns: list[Pattern] = []
        total = max(len(units), 1)
        for utype, instance_ids in type_groups.items():
            if len(instance_ids) < self._min_instances:
                continue
            confidence = min(1.0, len(instance_ids) / total)
            patterns.append(Pattern(
                name=f"type_cluster:{utype}",
                description=f"Cluster of '{utype}' knowledge units",
                instances=instance_ids,
                confidence=confidence,
            ))
        return patterns
