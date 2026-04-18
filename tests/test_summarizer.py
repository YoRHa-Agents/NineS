"""Tests for analysis summarizer (FR-321)."""

from __future__ import annotations

from nines.analyzer.graph_models import (
    ArchitectureLayer,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    VerificationResult,
)
from nines.analyzer.summarizer import AnalysisSummarizer


def _make_graph() -> KnowledgeGraph:
    nodes = [
        GraphNode(
            id="file:src/main.py",
            node_type="file",
            name="main.py",
            file_path="src/main.py",
            file_category="code",
            metadata={"language": "python"},
        ),
        GraphNode(
            id="file:src/utils.py",
            node_type="file",
            name="utils.py",
            file_path="src/utils.py",
            file_category="code",
            metadata={"language": "python"},
        ),
        GraphNode(
            id="file:config.yaml",
            node_type="file",
            name="config.yaml",
            file_path="config.yaml",
            file_category="config",
            metadata={"language": "yaml"},
        ),
        GraphNode(
            id="function:src/main.py::run",
            node_type="function",
            name="run",
            file_path="src/main.py",
            file_category="code",
        ),
    ]
    edges = [
        GraphEdge(source="file:src/main.py", target="file:src/utils.py", edge_type="imports"),
        GraphEdge(
            source="file:src/main.py", target="function:src/main.py::run", edge_type="contains"
        ),
    ]
    layers = [
        ArchitectureLayer(
            id="domain", name="Domain", node_ids=["file:src/main.py", "file:src/utils.py"]
        ),
        ArchitectureLayer(id="configuration", name="Configuration", node_ids=["file:config.yaml"]),
    ]
    return KnowledgeGraph(
        project_name="test-project",
        languages=["python", "yaml"],
        frameworks=["click"],
        nodes=nodes,
        edges=edges,
        layers=layers,
        metadata={"category_breakdown": {"code": 2, "config": 1}},
    )


class TestAnalysisSummarizer:
    def test_summarize_basic(self):
        graph = _make_graph()
        summarizer = AnalysisSummarizer()
        summary = summarizer.summarize(graph)

        assert summary.target == "test-project"
        assert summary.total_files == 3
        assert summary.total_nodes == 4
        assert summary.total_edges == 2
        assert summary.layer_count == 2
        assert "python" in summary.language_breakdown
        assert summary.language_breakdown["python"] == 2
        assert "code" in summary.category_breakdown

    def test_summarize_with_verification(self):
        graph = _make_graph()
        ver = VerificationResult(passed=True, node_count=4, edge_count=2)
        summary = AnalysisSummarizer().summarize(graph, ver)
        assert summary.verification is not None
        assert summary.verification.passed is True

    def test_fan_rankings(self):
        graph = _make_graph()
        summary = AnalysisSummarizer().summarize(graph)
        assert len(summary.top_fan_in) > 0
        assert len(summary.top_fan_out) > 0

    def test_entry_points(self):
        graph = _make_graph()
        summary = AnalysisSummarizer().summarize(graph)
        assert any("main" in ep for ep in summary.key_entry_points)

    def test_agent_impact_text(self):
        graph = _make_graph()
        summary = AnalysisSummarizer().summarize(graph)
        assert "test-project" in summary.agent_impact_summary
        assert (
            "python" in summary.agent_impact_summary.lower()
            or "Languages" in summary.agent_impact_summary
        )

    def test_empty_graph(self):
        graph = KnowledgeGraph(project_name="empty")
        summary = AnalysisSummarizer().summarize(graph)
        assert summary.total_files == 0
        assert summary.total_nodes == 0
        assert summary.total_edges == 0

    def test_round_trip(self):
        graph = _make_graph()
        summary = AnalysisSummarizer().summarize(graph)
        d = summary.to_dict()
        from nines.analyzer.graph_models import AnalysisSummary

        restored = AnalysisSummary.from_dict(d)
        assert restored.target == summary.target
        assert restored.total_files == summary.total_files
