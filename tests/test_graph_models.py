"""Tests for graph models (FR-315, FR-316)."""

from __future__ import annotations

import pytest

from nines.analyzer.graph_models import (
    AnalysisSummary,
    ArchitectureLayer,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    VerificationIssue,
    VerificationResult,
)


class TestGraphNode:
    def test_round_trip(self):
        node = GraphNode(
            id="file:src/main.py",
            node_type="file",
            name="main.py",
            file_path="src/main.py",
            file_category="code",
            summary="Entry point",
            tags=["python"],
            complexity=5,
            line_start=1,
            line_end=100,
            metadata={"language": "python"},
        )
        d = node.to_dict()
        restored = GraphNode.from_dict(d)
        assert restored.id == node.id
        assert restored.node_type == node.node_type
        assert restored.tags == ["python"]
        assert restored.complexity == 5
        assert restored.metadata == {"language": "python"}

    def test_defaults(self):
        node = GraphNode(id="test", node_type="file", name="test")
        assert node.file_path == ""
        assert node.tags == []
        assert node.complexity == 0

    def test_from_dict_minimal(self):
        node = GraphNode.from_dict({"id": "x", "node_type": "file", "name": "x"})
        assert node.id == "x"
        assert node.summary == ""


class TestGraphEdge:
    def test_round_trip(self):
        edge = GraphEdge(
            source="file:a.py",
            target="file:b.py",
            edge_type="imports",
            weight=0.8,
            metadata={"line": 5},
        )
        d = edge.to_dict()
        restored = GraphEdge.from_dict(d)
        assert restored.source == edge.source
        assert restored.target == edge.target
        assert restored.weight == 0.8

    def test_defaults(self):
        edge = GraphEdge(source="a", target="b", edge_type="calls")
        assert edge.weight == 1.0
        assert edge.metadata == {}


class TestArchitectureLayer:
    def test_round_trip(self):
        layer = ArchitectureLayer(
            id="domain",
            name="Domain",
            description="Core domain",
            node_ids=["file:a.py", "file:b.py"],
        )
        d = layer.to_dict()
        restored = ArchitectureLayer.from_dict(d)
        assert restored.id == "domain"
        assert len(restored.node_ids) == 2


class TestKnowledgeGraph:
    @pytest.fixture()
    def sample_graph(self):
        nodes = [
            GraphNode(id="file:a.py", node_type="file", name="a.py"),
            GraphNode(id="file:b.py", node_type="file", name="b.py"),
            GraphNode(id="file:c.py", node_type="file", name="c.py"),
        ]
        edges = [
            GraphEdge(source="file:a.py", target="file:b.py", edge_type="imports"),
            GraphEdge(source="file:a.py", target="file:c.py", edge_type="imports"),
            GraphEdge(source="file:b.py", target="file:c.py", edge_type="imports"),
        ]
        layers = [
            ArchitectureLayer(
                id="core",
                name="Core",
                node_ids=["file:a.py", "file:b.py"],
            ),
        ]
        return KnowledgeGraph(
            project_name="test",
            nodes=nodes,
            edges=edges,
            layers=layers,
        )

    def test_round_trip(self, sample_graph):
        d = sample_graph.to_dict()
        restored = KnowledgeGraph.from_dict(d)
        assert restored.project_name == "test"
        assert len(restored.nodes) == 3
        assert len(restored.edges) == 3
        assert len(restored.layers) == 1

    def test_get_node(self, sample_graph):
        assert sample_graph.get_node("file:a.py") is not None
        assert sample_graph.get_node("file:missing") is None

    def test_get_edges_from(self, sample_graph):
        edges = sample_graph.get_edges_from("file:a.py")
        assert len(edges) == 2

    def test_get_edges_to(self, sample_graph):
        edges = sample_graph.get_edges_to("file:c.py")
        assert len(edges) == 2

    def test_fan_in_out(self, sample_graph):
        assert sample_graph.fan_in("file:c.py") == 2
        assert sample_graph.fan_out("file:a.py") == 2
        assert sample_graph.fan_in("file:a.py") == 0

    def test_get_nodes_in_layer(self, sample_graph):
        nodes = sample_graph.get_nodes_in_layer("core")
        assert len(nodes) == 2
        assert sample_graph.get_nodes_in_layer("nonexistent") == []


class TestVerificationResult:
    def test_round_trip(self):
        issue = VerificationIssue(
            severity="critical",
            category="referential_integrity",
            message="Bad ref",
            node_ids=["file:x.py"],
        )
        result = VerificationResult(
            passed=False,
            issues=[issue],
            node_count=10,
            edge_count=5,
            layer_coverage_pct=80.0,
            orphan_count=2,
        )
        d = result.to_dict()
        restored = VerificationResult.from_dict(d)
        assert restored.passed is False
        assert len(restored.issues) == 1
        assert restored.issues[0].severity == "critical"
        assert restored.orphan_count == 2


class TestAnalysisSummary:
    def test_round_trip(self):
        summary = AnalysisSummary(
            target="test-project",
            total_files=10,
            total_nodes=50,
            total_edges=30,
            layer_count=4,
            language_breakdown={"python": 8, "yaml": 2},
            category_breakdown={"code": 8, "config": 2},
            top_fan_in=[("file:core.py", 10)],
            top_fan_out=[("file:main.py", 8)],
            key_entry_points=["file:main.py"],
            agent_impact_summary="Test summary",
        )
        d = summary.to_dict()
        restored = AnalysisSummary.from_dict(d)
        assert restored.target == "test-project"
        assert restored.total_files == 10
        assert restored.language_breakdown["python"] == 8

    def test_with_verification(self):
        ver = VerificationResult(passed=True, node_count=5, edge_count=3)
        summary = AnalysisSummary(target="t", verification=ver)
        d = summary.to_dict()
        restored = AnalysisSummary.from_dict(d)
        assert restored.verification is not None
        assert restored.verification.passed is True

    def test_without_verification(self):
        summary = AnalysisSummary(target="t")
        d = summary.to_dict()
        restored = AnalysisSummary.from_dict(d)
        assert restored.verification is None
