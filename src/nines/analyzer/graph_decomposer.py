"""Graph-based knowledge decomposition.

Builds a typed :class:`KnowledgeGraph` from scan results, import graphs,
and optional AST-based code reviews.  Assigns nodes to architecture
layers using path heuristics and fan-in/fan-out analysis.

Covers: FR-319.

C03 N3 (builder-side canonicalisation): every node ID and every edge
endpoint emitted by the builder is funnelled through
:func:`canonicalize_id` exactly once at construction time.  This makes
the verifier's referential-integrity check deterministic at the source
rather than relying on the consumer-side patch shipped with the C03 POC.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from nines.analyzer.graph_canonicalizer import canonicalize_id
from nines.analyzer.graph_models import (
    ArchitectureLayer,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
)

if TYPE_CHECKING:
    from nines.analyzer.import_graph import ImportGraph
    from nines.analyzer.reviewer import FileReview
    from nines.analyzer.scanner import ScanResult

logger = logging.getLogger(__name__)

_LAYER_PATH_PATTERNS: dict[str, set[str]] = {
    "presentation": {
        "cli",
        "api",
        "web",
        "ui",
        "views",
        "routes",
        "endpoints",
        "handlers",
        "controllers",
    },
    "application": {
        "services",
        "usecases",
        "commands",
        "orchestrator",
        "workflows",
        "application",
    },
    "domain": {
        "models",
        "entities",
        "domain",
        "core",
        "types",
        "schemas",
    },
    "infrastructure": {
        "db",
        "database",
        "repos",
        "repositories",
        "adapters",
        "clients",
        "storage",
        "external",
        "infrastructure",
    },
    "testing": {
        "tests",
        "test",
        "fixtures",
        "conftest",
        "mocks",
    },
    "documentation": {
        "docs",
        "doc",
        "documentation",
        "guides",
        "references",
    },
    "configuration": {
        "config",
        "configs",
        "settings",
    },
}


class GraphDecomposer:
    """Builds a :class:`KnowledgeGraph` from scan, import, and review data.

    Parameters
    ----------
    project_root:
        Optional explicit anchor used by :func:`canonicalize_id` for
        every node and edge ID minted by the builder.  When ``None``,
        the builder derives the root from ``scan_result.project_root``
        (which the :class:`ProjectScanner` already resolves to an
        absolute path).  Passing an explicit root is preferred whenever
        the caller already knows the analyse target — it avoids any
        ambiguity if a downstream consumer ever stops resolving paths
        the same way.
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        """Initialise the builder with an optional canonicalisation anchor."""
        self._project_root = project_root

    def build_graph(
        self,
        scan_result: ScanResult,
        import_graph: ImportGraph,
        reviews: list[FileReview] | None = None,
    ) -> KnowledgeGraph:
        """Build a knowledge graph from analysis artifacts.

        Parameters
        ----------
        scan_result:
            File inventory from :class:`ProjectScanner`.
        import_graph:
            Cross-language import dependency graph.
        reviews:
            Optional AST-based code reviews (Python files).

        Returns
        -------
        KnowledgeGraph
        """
        # Resolve the canonicalisation anchor once per build.  Prefer the
        # explicit constructor argument; fall back to scan_result so the
        # legacy call sites (no project_root) still produce canonical
        # output.
        if self._project_root is not None:
            effective_root: str | Path = self._project_root
        else:
            effective_root = scan_result.project_root

        file_nodes = self._create_file_nodes(scan_result, effective_root)
        code_nodes: list[GraphNode] = []
        containment_edges: list[GraphEdge] = []

        if reviews:
            code_nodes, containment_edges = self._create_code_nodes(
                reviews,
                effective_root,
            )

        all_nodes = file_nodes + code_nodes
        import_edges = self._create_import_edges(import_graph, effective_root)
        all_edges = containment_edges + import_edges

        layers = self._detect_layers(all_nodes, all_edges)

        logger.info(
            "Built knowledge graph: %d nodes, %d edges, %d layers",
            len(all_nodes),
            len(all_edges),
            len(layers),
        )

        return KnowledgeGraph(
            project_name=scan_result.project_name,
            project_description=scan_result.description,
            languages=list(scan_result.languages),
            frameworks=list(scan_result.frameworks),
            nodes=all_nodes,
            edges=all_edges,
            layers=layers,
            metadata={
                "total_files": scan_result.total_files,
                "total_lines": scan_result.total_lines,
                "language_breakdown": dict(scan_result.language_breakdown),
                "category_breakdown": dict(scan_result.category_breakdown),
            },
        )

    @staticmethod
    def _canonical(raw_id: str, root: str | Path) -> str:
        """Funnel every minted ID through :func:`canonicalize_id`.

        Centralised so any future ID-emitting site automatically picks
        up canonicalisation.
        """
        return canonicalize_id(raw_id, project_root=root)

    def _create_file_nodes(
        self,
        scan_result: ScanResult,
        project_root: str | Path,
    ) -> list[GraphNode]:
        """Create one :class:`GraphNode` per discovered file."""
        root = Path(scan_result.project_root)
        nodes: list[GraphNode] = []
        for fi in scan_result.files:
            try:
                rel = Path(fi.path).relative_to(root).as_posix()
            except ValueError:
                rel = fi.path

            raw_id = f"file:{rel}"
            nodes.append(
                GraphNode(
                    id=self._canonical(raw_id, project_root),
                    node_type="file",
                    name=Path(rel).name,
                    file_path=rel,
                    file_category=fi.category,
                    tags=[fi.language] if fi.language else [],
                    metadata={
                        "language": fi.language,
                        "line_count": fi.line_count,
                        "size_bytes": fi.size_bytes,
                    },
                )
            )
        return nodes

    def _create_code_nodes(
        self,
        reviews: list[FileReview],
        project_root: str | Path,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Create function and class nodes from AST reviews.

        Returns
        -------
        tuple
            (nodes, containment_edges)
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        for review in reviews:
            file_id = self._canonical(f"file:{review.path}", project_root)

            for func in review.functions:
                func_id = self._canonical(
                    f"function:{review.path}::{func.qualified_name}",
                    project_root,
                )
                nodes.append(
                    GraphNode(
                        id=func_id,
                        node_type="function",
                        name=func.name,
                        file_path=review.path,
                        file_category="code",
                        summary=func.docstring or "",
                        complexity=func.complexity,
                        line_start=func.lineno,
                        line_end=func.end_lineno,
                        tags=["async"] if func.is_async else [],
                        metadata={
                            "args": func.args,
                            "decorators": func.decorators,
                        },
                    )
                )
                edges.append(
                    GraphEdge(
                        source=file_id,
                        target=func_id,
                        edge_type="contains",
                    )
                )

            for cls in review.classes:
                cls_id = self._canonical(
                    f"class:{review.path}::{cls.name}",
                    project_root,
                )
                nodes.append(
                    GraphNode(
                        id=cls_id,
                        node_type="class",
                        name=cls.name,
                        file_path=review.path,
                        file_category="code",
                        summary=cls.docstring or "",
                        line_start=cls.lineno,
                        line_end=cls.end_lineno,
                        tags=[],
                        metadata={
                            "bases": cls.bases,
                            "method_count": len(cls.methods),
                        },
                    )
                )
                edges.append(
                    GraphEdge(
                        source=file_id,
                        target=cls_id,
                        edge_type="contains",
                    )
                )

                for method in cls.methods:
                    method_id = self._canonical(
                        f"function:{review.path}::{cls.name}.{method.name}",
                        project_root,
                    )
                    nodes.append(
                        GraphNode(
                            id=method_id,
                            node_type="function",
                            name=method.name,
                            file_path=review.path,
                            file_category="code",
                            summary=method.docstring or "",
                            complexity=method.complexity,
                            line_start=method.lineno,
                            line_end=method.end_lineno,
                            tags=["method"] + (["async"] if method.is_async else []),
                        )
                    )
                    edges.append(
                        GraphEdge(
                            source=cls_id,
                            target=method_id,
                            edge_type="contains",
                        )
                    )

        return nodes, edges

    def _create_import_edges(
        self,
        import_graph: ImportGraph,
        project_root: str | Path,
    ) -> list[GraphEdge]:
        """Convert :class:`ImportEdge` instances to :class:`GraphEdge`."""
        edges: list[GraphEdge] = []
        for ie in import_graph.edges:
            edges.append(
                GraphEdge(
                    source=self._canonical(f"file:{ie.source_file}", project_root),
                    target=self._canonical(f"file:{ie.target_file}", project_root),
                    edge_type="imports",
                    metadata={"import_name": ie.import_name, "line_number": ie.line_number},
                )
            )
        return edges

    def _detect_layers(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> list[ArchitectureLayer]:
        """Assign nodes to architecture layers.

        Uses path-based classification with fan-in promotion: nodes
        in the top 10 percent by fan-in are promoted to the ``"core"``
        layer if they would otherwise be ``"unclassified"``.
        """
        fan_in_counts: dict[str, int] = {}
        for edge in edges:
            fan_in_counts[edge.target] = fan_in_counts.get(edge.target, 0) + 1

        threshold = 0
        if fan_in_counts:
            sorted_counts = sorted(fan_in_counts.values(), reverse=True)
            idx = max(1, len(sorted_counts) // 10)
            threshold = sorted_counts[min(idx, len(sorted_counts) - 1)]

        layer_buckets: dict[str, list[str]] = {}
        for node in nodes:
            layer = self._classify_node_layer(node)
            if layer == "unclassified" and fan_in_counts.get(node.id, 0) >= threshold > 0:
                layer = "domain"
            layer_buckets.setdefault(layer, []).append(node.id)

        layers: list[ArchitectureLayer] = []
        for layer_id, node_ids in sorted(layer_buckets.items()):
            if layer_id == "unclassified":
                continue
            layers.append(
                ArchitectureLayer(
                    id=layer_id,
                    name=layer_id.replace("_", " ").title(),
                    description=f"Nodes classified as {layer_id}",
                    node_ids=sorted(node_ids),
                )
            )

        unclassified = layer_buckets.get("unclassified", [])
        if unclassified:
            layers.append(
                ArchitectureLayer(
                    id="unclassified",
                    name="Unclassified",
                    description="Nodes not matching any layer pattern",
                    node_ids=sorted(unclassified),
                )
            )

        return layers

    def _classify_node_layer(self, node: GraphNode) -> str:
        """Classify a node into an architecture layer using path heuristics."""
        if not node.file_path:
            return "unclassified"

        parts = {p.lower() for p in Path(node.file_path).parts}
        for layer, indicators in _LAYER_PATH_PATTERNS.items():
            if parts & indicators:
                return layer
        return "unclassified"

    def identify_entry_points(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> list[str]:
        """Identify likely project entry points.

        Heuristic: files named ``main``, ``app``, ``index``, ``cli``,
        or nodes with high fan-in and low fan-out.
        """
        entry_names = {"main", "app", "index", "cli", "__main__"}
        entry_ids: list[str] = []

        for node in nodes:
            stem = Path(node.file_path).stem.lower() if node.file_path else ""
            if stem in entry_names:
                entry_ids.append(node.id)

        fan_in_map: dict[str, int] = {}
        fan_out_map: dict[str, int] = {}
        for edge in edges:
            fan_in_map[edge.target] = fan_in_map.get(edge.target, 0) + 1
            fan_out_map[edge.source] = fan_out_map.get(edge.source, 0) + 1

        for node in nodes:
            if node.id in entry_ids:
                continue
            fi = fan_in_map.get(node.id, 0)
            fo = fan_out_map.get(node.id, 0)
            if fi >= 5 and fo <= 2:
                entry_ids.append(node.id)

        return entry_ids
