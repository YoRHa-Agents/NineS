"""Knowledge graph data models for rich repository decomposition.

Provides typed graph nodes, edges, architecture layers, verification
results, and analysis summaries.  Inspired by Understand-Anything's
schema-driven approach but tailored to NineS's Agent-impact focus.

Covers: FR-315, FR-316.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VALID_NODE_TYPES = frozenset(
    {
        "file",
        "function",
        "class",
        "module",
        "config",
        "document",
        "service",
        "endpoint",
        "schema",
        "resource",
        "concept",
    }
)

VALID_EDGE_TYPES = frozenset(
    {
        "imports",
        "contains",
        "calls",
        "configures",
        "deploys",
        "implements",
        "extends",
        "uses",
        "tests",
        "documents",
    }
)

VALID_FILE_CATEGORIES = frozenset(
    {
        "code",
        "config",
        "docs",
        "infra",
        "data",
        "script",
        "markup",
    }
)


@dataclass
class GraphNode:
    """A node in the knowledge graph representing a code entity."""

    id: str
    node_type: str
    name: str
    file_path: str = ""
    file_category: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    complexity: int = 0
    line_start: int = 0
    line_end: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "node_type": self.node_type,
            "name": self.name,
            "file_path": self.file_path,
            "file_category": self.file_category,
            "summary": self.summary,
            "tags": list(self.tags),
            "complexity": self.complexity,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphNode:
        """Deserialize from a plain dictionary."""
        return cls(
            id=data["id"],
            node_type=data.get("node_type", ""),
            name=data.get("name", ""),
            file_path=data.get("file_path", ""),
            file_category=data.get("file_category", ""),
            summary=data.get("summary", ""),
            tags=list(data.get("tags", [])),
            complexity=data.get("complexity", 0),
            line_start=data.get("line_start", 0),
            line_end=data.get("line_end", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class GraphEdge:
    """A directed edge between two graph nodes."""

    source: str
    target: str
    edge_type: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphEdge:
        """Deserialize from a plain dictionary."""
        return cls(
            source=data["source"],
            target=data["target"],
            edge_type=data.get("edge_type", ""),
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ArchitectureLayer:
    """A grouping of nodes into an architectural layer."""

    id: str
    name: str
    description: str = ""
    node_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "node_ids": list(self.node_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchitectureLayer:
        """Deserialize from a plain dictionary."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            node_ids=list(data.get("node_ids", [])),
            metadata=data.get("metadata", {}),
        )


@dataclass
class KnowledgeGraph:
    """Complete knowledge graph for a project."""

    project_name: str
    project_description: str = ""
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    layers: list[ArchitectureLayer] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "project_name": self.project_name,
            "project_description": self.project_description,
            "languages": list(self.languages),
            "frameworks": list(self.frameworks),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "layers": [la.to_dict() for la in self.layers],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraph:
        """Deserialize from a plain dictionary."""
        return cls(
            project_name=data.get("project_name", ""),
            project_description=data.get("project_description", ""),
            languages=list(data.get("languages", [])),
            frameworks=list(data.get("frameworks", [])),
            nodes=[GraphNode.from_dict(n) for n in data.get("nodes", [])],
            edges=[GraphEdge.from_dict(e) for e in data.get("edges", [])],
            layers=[ArchitectureLayer.from_dict(la) for la in data.get("layers", [])],
            metadata=data.get("metadata", {}),
        )

    def get_node(self, node_id: str) -> GraphNode | None:
        """Look up a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_edges_from(self, node_id: str) -> list[GraphEdge]:
        """Return all edges originating from *node_id*."""
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> list[GraphEdge]:
        """Return all edges targeting *node_id*."""
        return [e for e in self.edges if e.target == node_id]

    def get_nodes_in_layer(self, layer_id: str) -> list[GraphNode]:
        """Return nodes belonging to the given layer."""
        for layer in self.layers:
            if layer.id == layer_id:
                id_set = set(layer.node_ids)
                return [n for n in self.nodes if n.id in id_set]
        return []

    def fan_in(self, node_id: str) -> int:
        """Count distinct source nodes with edges targeting *node_id*."""
        return len({e.source for e in self.edges if e.target == node_id})

    def fan_out(self, node_id: str) -> int:
        """Count distinct target nodes with edges from *node_id*."""
        return len({e.target for e in self.edges if e.source == node_id})


@dataclass
class VerificationIssue:
    """A single issue found during graph verification."""

    severity: str
    category: str
    message: str
    node_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "node_ids": list(self.node_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationIssue:
        """Deserialize from a plain dictionary."""
        return cls(
            severity=data.get("severity", "info"),
            category=data.get("category", ""),
            message=data.get("message", ""),
            node_ids=list(data.get("node_ids", [])),
        )


@dataclass
class VerificationResult:
    """Result of knowledge graph verification."""

    passed: bool
    issues: list[VerificationIssue] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    layer_coverage_pct: float = 0.0
    orphan_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "layer_coverage_pct": self.layer_coverage_pct,
            "orphan_count": self.orphan_count,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationResult:
        """Deserialize from a plain dictionary."""
        return cls(
            passed=data.get("passed", False),
            issues=[VerificationIssue.from_dict(i) for i in data.get("issues", [])],
            node_count=data.get("node_count", 0),
            edge_count=data.get("edge_count", 0),
            layer_coverage_pct=data.get("layer_coverage_pct", 0.0),
            orphan_count=data.get("orphan_count", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AnalysisSummary:
    """Structured summary of the complete analysis."""

    target: str
    total_files: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    layer_count: int = 0
    language_breakdown: dict[str, int] = field(default_factory=dict)
    category_breakdown: dict[str, int] = field(default_factory=dict)
    top_fan_in: list[tuple[str, int]] = field(default_factory=list)
    top_fan_out: list[tuple[str, int]] = field(default_factory=list)
    key_entry_points: list[str] = field(default_factory=list)
    agent_impact_summary: str = ""
    verification: VerificationResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "target": self.target,
            "total_files": self.total_files,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "layer_count": self.layer_count,
            "language_breakdown": dict(self.language_breakdown),
            "category_breakdown": dict(self.category_breakdown),
            "top_fan_in": [[nid, count] for nid, count in self.top_fan_in],
            "top_fan_out": [[nid, count] for nid, count in self.top_fan_out],
            "key_entry_points": list(self.key_entry_points),
            "agent_impact_summary": self.agent_impact_summary,
            "verification": self.verification.to_dict() if self.verification else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisSummary:
        """Deserialize from a plain dictionary."""
        ver_data = data.get("verification")
        return cls(
            target=data["target"],
            total_files=data.get("total_files", 0),
            total_nodes=data.get("total_nodes", 0),
            total_edges=data.get("total_edges", 0),
            layer_count=data.get("layer_count", 0),
            language_breakdown=dict(data.get("language_breakdown", {})),
            category_breakdown=dict(data.get("category_breakdown", {})),
            top_fan_in=[tuple(pair) for pair in data.get("top_fan_in", [])],
            top_fan_out=[tuple(pair) for pair in data.get("top_fan_out", [])],
            key_entry_points=list(data.get("key_entry_points", [])),
            agent_impact_summary=data.get("agent_impact_summary", ""),
            verification=VerificationResult.from_dict(ver_data) if ver_data else None,
            metadata=data.get("metadata", {}),
        )
