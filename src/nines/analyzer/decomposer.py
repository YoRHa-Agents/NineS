"""Knowledge decomposition with three strategies.

Transforms analyzed code into atomic :class:`~nines.core.models.KnowledgeUnit`
instances using functional, concern-based, or layer-based decomposition.

Covers: FR-305, FR-306, FR-307.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nines.core.models import KnowledgeUnit

if TYPE_CHECKING:
    from nines.analyzer.reviewer import FileReview, FunctionInfo
    from nines.analyzer.structure import StructureReport

logger = logging.getLogger(__name__)

CONCERN_PATTERNS: dict[str, list[str]] = {
    "error_handling": ["except", "raise", "Error", "Exception", "try"],
    "logging": ["logger", "logging", "log.", "LOG"],
    "validation": ["validate", "assert", "check", "verify", "is_valid"],
    "serialization": ["to_dict", "from_dict", "serialize", "deserialize", "json", "to_json"],
    "configuration": ["config", "settings", "options", "defaults", "Config"],
    "io_operations": ["read", "write", "open", "save", "load", "fetch", "request"],
    "testing": ["test_", "assert", "mock", "fixture", "pytest"],
    "evaluation": ["eval", "score", "scorer", "benchmark", "metric", "grade", "assess"],
    "analysis": ["analy", "review", "inspect", "decompos", "finding", "structure"],
    "collection": ["collect", "gather", "search", "crawl", "arxiv", "github", "source"],
    "iteration": ["iterate", "converge", "improve", "gap", "plan", "baseline", "mapim"],
    "indexing": ["index", "query", "search", "retrieve", "rank", "recall"],
    "execution": ["run", "execute", "invoke", "dispatch", "process", "pipeline"],
    "initialization": ["init", "setup", "create", "build", "register", "bootstrap"],
    "parsing": ["parse", "extract", "tokenize", "split", "decode", "transform"],
    "reporting": ["report", "format", "render", "display", "output", "emit", "generate"],
    "sandbox": ["sandbox", "isolat", "venv", "pollution", "clean"],
    "orchestration": ["orchestrat", "pipeline", "workflow", "stage", "wave", "dispatch"],
    "skill": ["skill", "adapter", "install", "cursor", "claude", "codex", "copilot"],
}

LAYER_INDICATORS: dict[str, set[str]] = {
    "presentation": {
        "cli", "api", "web", "ui", "views", "routes",
        "endpoints", "handlers", "controllers",
    },
    "application": {
        "services", "usecases", "commands", "orchestrator",
        "workflows", "application",
    },
    "domain": {
        "models", "entities", "domain", "core", "types", "schemas",
    },
    "infrastructure": {
        "db", "database", "repos", "repositories", "adapters",
        "clients", "storage", "external", "infrastructure",
    },
    "testing": {
        "tests", "test", "fixtures", "conftest", "mocks",
    },
}


def _func_signature(func: FunctionInfo) -> str:
    """Func signature."""
    args_str = ", ".join(func.args)
    prefix = "async def" if func.is_async else "def"
    return f"{prefix} {func.name}({args_str})"


def _infer_tags(name: str, docstring: str | None, source: str = "") -> list[str]:
    """Infer tags from name, docstring, and source path."""
    tags: list[str] = []
    text = (name + " " + (docstring or "")).lower()
    for concern, keywords in CONCERN_PATTERNS.items():
        if any(kw.lower() in text for kw in keywords):
            tags.append(concern)
    if source:
        module_tags: dict[str, str] = {
            "eval": "evaluation", "analyzer": "analysis", "collector": "collection",
            "iteration": "iteration", "sandbox": "sandbox", "skill": "skill",
            "orchestrator": "orchestration", "cli": "cli", "core": "core",
        }
        source_lower = source.lower()
        for module_part, tag in module_tags.items():
            if module_part in source_lower and tag not in tags:
                tags.append(tag)
    if not tags:
        tags.append("general")
    return tags


class Decomposer:
    """Decomposes code into :class:`KnowledgeUnit` instances using three strategies.

    - :meth:`functional_decompose`: by function / class (FR-305)
    - :meth:`concern_decompose`: by cross-cutting concern (FR-306)
    - :meth:`layer_decompose`: by architectural layer (FR-307)
    """

    def functional_decompose(
        self, reviews: list[FileReview]
    ) -> list[KnowledgeUnit]:
        """Decompose by function and class granularity (FR-305).

        Each top-level function becomes a ``function`` unit, each class
        becomes a ``class`` unit, and each method becomes a ``function``
        unit with the class as its parent via relationships.

        Parameters
        ----------
        reviews:
            Parsed file reviews, each optionally containing an AST tree.

        Returns
        -------
        list[KnowledgeUnit]
        """
        units: list[KnowledgeUnit] = []

        for review in reviews:
            filepath = review.path

            for func in review.functions:
                units.append(self._func_unit(filepath, func))

            for cls in review.classes:
                cls_id = f"{filepath}::{cls.name}"
                units.append(KnowledgeUnit(
                    id=cls_id,
                    source=filepath,
                    content=f"class {cls.name}({', '.join(cls.bases)})",
                    unit_type="class",
                    relationships={"bases": cls.bases},
                    metadata={
                        "lineno": str(cls.lineno),
                        "end_lineno": str(cls.end_lineno),
                        "method_count": str(len(cls.methods)),
                        "docstring": cls.docstring or "",
                        "tags": ",".join(_infer_tags(cls.name, cls.docstring, filepath)),
                    },
                ))
                for method in cls.methods:
                    m_unit = self._func_unit(filepath, method, parent_id=cls_id)
                    units.append(m_unit)

        return units

    def concern_decompose(
        self, reviews: list[FileReview]
    ) -> list[KnowledgeUnit]:
        """Group units by cross-cutting concern (FR-306).

        First performs functional decomposition, then classifies each unit
        into a concern group by scanning its content and name against
        :data:`CONCERN_PATTERNS`.  Units not matching any pattern fall
        into ``"core_logic"``.

        Returns
        -------
        list[KnowledgeUnit]
            Concern-group units (type ``"concern"``) whose relationships
            point to their member unit IDs.
        """
        func_units = self.functional_decompose(reviews)

        groups: dict[str, list[KnowledgeUnit]] = {}
        for unit in func_units:
            text = (unit.content + " " + unit.metadata.get("docstring", "")).lower()
            matched = False
            for concern, keywords in CONCERN_PATTERNS.items():
                if any(kw.lower() in text for kw in keywords):
                    groups.setdefault(concern, []).append(unit)
                    matched = True
                    break
            if not matched:
                groups.setdefault("core_logic", []).append(unit)

        result: list[KnowledgeUnit] = []
        for concern, members in sorted(groups.items()):
            result.append(KnowledgeUnit(
                id=f"concern::{concern}",
                source="",
                content=f"Concern group: {concern}",
                unit_type="concern",
                relationships={"members": [m.id for m in members]},
                metadata={"member_count": str(len(members))},
            ))
            result.extend(members)

        return result

    def layer_decompose(
        self,
        reviews: list[FileReview],
        structure: StructureReport | None = None,
    ) -> list[KnowledgeUnit]:
        """Assign units to architectural layers (FR-307).

        Uses :data:`LAYER_INDICATORS` to classify each unit's source
        path into a layer.  If a ``StructureReport`` is provided its
        package information enriches the classification.

        Returns
        -------
        list[KnowledgeUnit]
            Layer-group units (type ``"layer"``) containing member
            references.
        """
        func_units = self.functional_decompose(reviews)

        layer_map: dict[str, list[KnowledgeUnit]] = {}
        for unit in func_units:
            layer = self._classify_layer(unit.source)
            layer_map.setdefault(layer, []).append(unit)

        result: list[KnowledgeUnit] = []
        for layer, members in sorted(layer_map.items()):
            result.append(KnowledgeUnit(
                id=f"layer::{layer}",
                source="",
                content=f"Architectural layer: {layer}",
                unit_type="layer",
                relationships={"members": [m.id for m in members]},
                metadata={"member_count": str(len(members))},
            ))
            result.extend(members)

        return result

    def _classify_layer(self, source_path: str) -> str:
        """Classify layer."""
        parts = Path(source_path).parts
        lower_parts = {p.lower() for p in parts}
        for layer, indicators in LAYER_INDICATORS.items():
            if lower_parts & indicators:
                return layer
        return "unclassified"

    @staticmethod
    def _func_unit(
        filepath: str,
        func: FunctionInfo,
        parent_id: str | None = None,
    ) -> KnowledgeUnit:
        """Func unit."""
        unit_id = f"{filepath}::{func.qualified_name}"
        sig = _func_signature(func)
        rels: dict[str, Any] = {}
        if parent_id:
            rels["parent"] = parent_id

        return KnowledgeUnit(
            id=unit_id,
            source=filepath,
            content=sig,
            unit_type="function",
            relationships=rels,
            metadata={
                "lineno": str(func.lineno),
                "end_lineno": str(func.end_lineno),
                "complexity": str(func.complexity),
                "is_async": str(func.is_async),
                "docstring": func.docstring or "",
                "tags": ",".join(_infer_tags(func.name, func.docstring, filepath)),
            },
        )
