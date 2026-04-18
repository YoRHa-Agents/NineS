"""Tests for graph-based decomposition (FR-319)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


from nines.analyzer.graph_decomposer import GraphDecomposer
from nines.analyzer.graph_models import KnowledgeGraph
from nines.analyzer.import_graph import ImportEdge, ImportGraph
from nines.analyzer.scanner import FileInfo, ScanResult


def _make_scan_result(tmp_path: Path) -> ScanResult:
    """Create a minimal scan result for testing."""
    root = str(tmp_path)
    files = [
        FileInfo(
            path=str(tmp_path / "src" / "main.py"),
            language="python",
            category="code",
            line_count=50,
        ),
        FileInfo(
            path=str(tmp_path / "src" / "utils.py"),
            language="python",
            category="code",
            line_count=30,
        ),
        FileInfo(
            path=str(tmp_path / "tests" / "test_main.py"),
            language="python",
            category="code",
            line_count=40,
        ),
        FileInfo(
            path=str(tmp_path / "config.yaml"), language="yaml", category="config", line_count=10
        ),
        FileInfo(
            path=str(tmp_path / "README.md"), language="markdown", category="docs", line_count=20
        ),
    ]
    return ScanResult(
        project_root=root,
        project_name="test-project",
        files=files,
        languages=["python", "yaml", "markdown"],
        total_files=5,
        total_lines=150,
        language_breakdown={"python": 3, "yaml": 1, "markdown": 1},
        category_breakdown={"code": 3, "config": 1, "docs": 1},
    )


class TestGraphDecomposer:
    def test_build_graph_basic(self, tmp_path):
        for d in ["src", "tests"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        for f in ["src/main.py", "src/utils.py", "tests/test_main.py", "config.yaml", "README.md"]:
            (tmp_path / f).touch()

        scan = _make_scan_result(tmp_path)
        import_graph = ImportGraph()
        decomposer = GraphDecomposer()

        graph = decomposer.build_graph(scan, import_graph)

        assert isinstance(graph, KnowledgeGraph)
        assert graph.project_name == "test-project"
        assert len(graph.nodes) == 5
        assert graph.languages == ["python", "yaml", "markdown"]

    def test_file_node_ids(self, tmp_path):
        for d in ["src", "tests"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        for f in ["src/main.py", "src/utils.py", "tests/test_main.py", "config.yaml", "README.md"]:
            (tmp_path / f).touch()

        scan = _make_scan_result(tmp_path)
        graph = GraphDecomposer().build_graph(scan, ImportGraph())

        node_ids = {n.id for n in graph.nodes}
        assert any(nid.startswith("file:") for nid in node_ids)

    def test_import_edges_converted(self, tmp_path):
        for d in ["src", "tests"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        for f in ["src/main.py", "src/utils.py", "tests/test_main.py", "config.yaml", "README.md"]:
            (tmp_path / f).touch()

        scan = _make_scan_result(tmp_path)
        ig = ImportGraph(
            edges=[
                ImportEdge(
                    source_file="src/main.py",
                    target_file="src/utils.py",
                    import_name="utils",
                    is_relative=False,
                    line_number=1,
                ),
            ]
        )

        graph = GraphDecomposer().build_graph(scan, ig)

        import_edges = [e for e in graph.edges if e.edge_type == "imports"]
        assert len(import_edges) == 1
        assert import_edges[0].source == "file:src/main.py"
        assert import_edges[0].target == "file:src/utils.py"

    def test_layer_detection(self, tmp_path):
        for d in ["src", "tests"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        for f in ["src/main.py", "src/utils.py", "tests/test_main.py", "config.yaml", "README.md"]:
            (tmp_path / f).touch()

        scan = _make_scan_result(tmp_path)
        graph = GraphDecomposer().build_graph(scan, ImportGraph())

        layer_ids = {la.id for la in graph.layers}
        assert "testing" in layer_ids

    def test_graph_round_trip(self, tmp_path):
        for d in ["src", "tests"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        for f in ["src/main.py", "src/utils.py", "tests/test_main.py", "config.yaml", "README.md"]:
            (tmp_path / f).touch()

        scan = _make_scan_result(tmp_path)
        graph = GraphDecomposer().build_graph(scan, ImportGraph())

        d = graph.to_dict()
        restored = KnowledgeGraph.from_dict(d)
        assert len(restored.nodes) == len(graph.nodes)
        assert len(restored.edges) == len(graph.edges)

    def test_identify_entry_points(self, tmp_path):
        for d in ["src", "tests"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        for f in ["src/main.py", "src/utils.py", "tests/test_main.py", "config.yaml", "README.md"]:
            (tmp_path / f).touch()

        scan = _make_scan_result(tmp_path)
        graph = GraphDecomposer().build_graph(scan, ImportGraph())

        entry_points = GraphDecomposer().identify_entry_points(
            graph.nodes,
            graph.edges,
        )
        entry_paths = []
        for eid in entry_points:
            node = graph.get_node(eid)
            if node:
                entry_paths.append(node.file_path)
        assert any("main" in p for p in entry_paths)

    def test_empty_scan(self, tmp_path):
        scan = ScanResult(
            project_root=str(tmp_path),
            project_name="empty",
            files=[],
            total_files=0,
        )
        graph = GraphDecomposer().build_graph(scan, ImportGraph())
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
