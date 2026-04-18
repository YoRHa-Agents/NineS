"""Tests for graph verification (FR-320)."""

from __future__ import annotations

from nines.analyzer.graph_models import (
    ArchitectureLayer,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
)
from nines.analyzer.graph_verifier import GraphVerifier


def _make_graph(
    nodes: list[GraphNode] | None = None,
    edges: list[GraphEdge] | None = None,
    layers: list[ArchitectureLayer] | None = None,
) -> KnowledgeGraph:
    return KnowledgeGraph(
        project_name="test",
        nodes=nodes or [],
        edges=edges or [],
        layers=layers or [],
    )


class TestGraphVerifier:
    def test_valid_graph_passes(self):
        nodes = [
            GraphNode(id="a", node_type="file", name="a"),
            GraphNode(id="b", node_type="file", name="b"),
        ]
        edges = [GraphEdge(source="a", target="b", edge_type="imports")]
        layers = [ArchitectureLayer(id="core", name="Core", node_ids=["a", "b"])]

        result = GraphVerifier().verify(_make_graph(nodes, edges, layers))
        assert result.passed is True
        assert result.node_count == 2
        assert result.edge_count == 1
        assert result.layer_coverage_pct == 100.0
        assert result.orphan_count == 0

    def test_referential_integrity_failure(self):
        nodes = [GraphNode(id="a", node_type="file", name="a")]
        edges = [GraphEdge(source="a", target="missing", edge_type="imports")]

        result = GraphVerifier().verify(_make_graph(nodes, edges))
        assert result.passed is False
        critical = [i for i in result.issues if i.severity == "critical"]
        assert len(critical) >= 1
        assert "missing" in critical[0].node_ids

    def test_duplicate_edges(self):
        nodes = [
            GraphNode(id="a", node_type="file", name="a"),
            GraphNode(id="b", node_type="file", name="b"),
        ]
        edges = [
            GraphEdge(source="a", target="b", edge_type="imports"),
            GraphEdge(source="a", target="b", edge_type="imports"),
        ]

        result = GraphVerifier().verify(_make_graph(nodes, edges))
        dup_issues = [i for i in result.issues if i.category == "duplicate_edge"]
        assert len(dup_issues) >= 1

    def test_orphan_nodes(self):
        nodes = [
            GraphNode(id="a", node_type="file", name="a"),
            GraphNode(id="orphan", node_type="file", name="orphan"),
        ]
        edges = [GraphEdge(source="a", target="a", edge_type="uses")]

        result = GraphVerifier().verify(_make_graph(nodes, edges))
        assert result.orphan_count >= 1

    def test_low_layer_coverage(self):
        nodes = [GraphNode(id=f"n{i}", node_type="file", name=f"n{i}") for i in range(10)]
        layers = [ArchitectureLayer(id="core", name="Core", node_ids=["n0"])]

        result = GraphVerifier().verify(_make_graph(nodes, layers=layers))
        layer_issues = [i for i in result.issues if i.category == "missing_layer"]
        assert len(layer_issues) >= 1

    def test_invalid_node_types(self):
        nodes = [GraphNode(id="a", node_type="bogus_type", name="a")]
        result = GraphVerifier().verify(_make_graph(nodes))
        type_issues = [i for i in result.issues if i.category == "invalid_node_type"]
        assert len(type_issues) >= 1

    def test_invalid_edge_types(self):
        nodes = [
            GraphNode(id="a", node_type="file", name="a"),
            GraphNode(id="b", node_type="file", name="b"),
        ]
        edges = [GraphEdge(source="a", target="b", edge_type="bogus_edge")]
        result = GraphVerifier().verify(_make_graph(nodes, edges))
        edge_issues = [i for i in result.issues if i.category == "invalid_edge_type"]
        assert len(edge_issues) >= 1

    def test_self_loops(self):
        nodes = [GraphNode(id="a", node_type="file", name="a")]
        edges = [GraphEdge(source="a", target="a", edge_type="uses")]
        result = GraphVerifier().verify(_make_graph(nodes, edges))
        loop_issues = [i for i in result.issues if i.category == "self_loop"]
        assert len(loop_issues) >= 1

    def test_empty_graph(self):
        result = GraphVerifier().verify(_make_graph())
        assert result.passed is True
        assert result.node_count == 0
        assert result.edge_count == 0

    def test_full_layer_coverage(self):
        nodes = [
            GraphNode(id="a", node_type="file", name="a"),
            GraphNode(id="b", node_type="file", name="b"),
        ]
        layers = [ArchitectureLayer(id="all", name="All", node_ids=["a", "b"])]
        result = GraphVerifier().verify(_make_graph(nodes, layers=layers))
        assert result.layer_coverage_pct == 100.0
        layer_issues = [i for i in result.issues if i.category == "missing_layer"]
        assert len(layer_issues) == 0
