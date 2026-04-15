"""Self-evaluation dimensions for graph-based analysis (D21-D24).

Measures quality of the knowledge graph pipeline: graph decomposition
coverage, verification pass rate, layer assignment quality, and
summary completeness.

Covers: D21, D22, D23, D24.
"""

from __future__ import annotations

import logging
from pathlib import Path

from nines.analyzer.graph_decomposer import GraphDecomposer
from nines.analyzer.graph_verifier import GraphVerifier
from nines.analyzer.import_graph import ImportGraphBuilder
from nines.analyzer.scanner import ProjectScanner
from nines.analyzer.summarizer import AnalysisSummarizer
from nines.iteration.self_eval import DimensionScore

logger = logging.getLogger(__name__)


class GraphDecompositionCoverageEvaluator:
    """D21: Measures how completely the graph captures project files.

    Compares the number of file-level graph nodes against the total
    files discovered by the scanner.  A score of 1.0 means every
    scanned file has a corresponding graph node.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self._root = Path(project_root)

    def evaluate(self) -> DimensionScore:
        """Run graph decomposition and measure file coverage."""
        try:
            scanner = ProjectScanner()
            scan_result = scanner.scan(self._root)
            if scan_result.total_files == 0:
                return DimensionScore(
                    name="graph_decomposition_coverage",
                    value=0.0, max_value=1.0,
                    metadata={"reason": "no files found"},
                )

            builder = ImportGraphBuilder()
            import_graph = builder.build(self._root, scan_result.files)

            decomposer = GraphDecomposer()
            graph = decomposer.build_graph(scan_result, import_graph)

            file_nodes = sum(1 for n in graph.nodes if n.node_type == "file")
            coverage = file_nodes / scan_result.total_files

            return DimensionScore(
                name="graph_decomposition_coverage",
                value=min(1.0, coverage),
                max_value=1.0,
                metadata={
                    "scanned_files": scan_result.total_files,
                    "graph_file_nodes": file_nodes,
                    "total_graph_nodes": len(graph.nodes),
                    "total_graph_edges": len(graph.edges),
                },
            )
        except Exception as exc:
            logger.error("D21 graph decomposition coverage failed: %s", exc)
            return DimensionScore(
                name="graph_decomposition_coverage",
                value=0.0, max_value=1.0,
                metadata={"error": str(exc)},
            )


class GraphVerificationPassRateEvaluator:
    """D22: Measures graph structural integrity.

    Runs the :class:`GraphVerifier` and scores based on the ratio of
    non-critical issues.  A score of 1.0 means zero critical issues
    and full layer coverage.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self._root = Path(project_root)

    def evaluate(self) -> DimensionScore:
        """Build a graph and verify it."""
        try:
            scanner = ProjectScanner()
            scan_result = scanner.scan(self._root)
            if scan_result.total_files == 0:
                return DimensionScore(
                    name="graph_verification_pass_rate",
                    value=0.0, max_value=1.0,
                    metadata={"reason": "no files found"},
                )

            builder = ImportGraphBuilder()
            import_graph = builder.build(self._root, scan_result.files)

            decomposer = GraphDecomposer()
            graph = decomposer.build_graph(scan_result, import_graph)

            verifier = GraphVerifier()
            result = verifier.verify(graph)

            critical_count = sum(
                1 for i in result.issues if i.severity == "critical"
            )
            warning_count = sum(
                1 for i in result.issues if i.severity == "warning"
            )

            integrity_score = 1.0 if critical_count == 0 else 0.0
            coverage_score = result.layer_coverage_pct / 100.0
            penalty = min(0.3, warning_count * 0.05)

            value = max(0.0, (integrity_score * 0.5 + coverage_score * 0.5) - penalty)

            return DimensionScore(
                name="graph_verification_pass_rate",
                value=round(value, 3),
                max_value=1.0,
                metadata={
                    "passed": result.passed,
                    "critical_issues": critical_count,
                    "warning_issues": warning_count,
                    "layer_coverage_pct": result.layer_coverage_pct,
                    "orphan_count": result.orphan_count,
                },
            )
        except Exception as exc:
            logger.error("D22 graph verification failed: %s", exc)
            return DimensionScore(
                name="graph_verification_pass_rate",
                value=0.0, max_value=1.0,
                metadata={"error": str(exc)},
            )


class LayerAssignmentQualityEvaluator:
    """D23: Measures quality of architecture layer assignments.

    Scores based on: all layers populated (not just 'unclassified'),
    reasonable distribution, and no overly dominant single layer.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self._root = Path(project_root)

    def evaluate(self) -> DimensionScore:
        """Build a graph and evaluate layer assignments."""
        try:
            scanner = ProjectScanner()
            scan_result = scanner.scan(self._root)
            if scan_result.total_files == 0:
                return DimensionScore(
                    name="layer_assignment_quality",
                    value=0.0, max_value=1.0,
                    metadata={"reason": "no files found"},
                )

            builder = ImportGraphBuilder()
            import_graph = builder.build(self._root, scan_result.files)

            decomposer = GraphDecomposer()
            graph = decomposer.build_graph(scan_result, import_graph)

            if not graph.layers:
                return DimensionScore(
                    name="layer_assignment_quality",
                    value=0.0, max_value=1.0,
                    metadata={"reason": "no layers detected"},
                )

            meaningful_layers = [
                la for la in graph.layers if la.id != "unclassified"
            ]
            layer_diversity = min(1.0, len(meaningful_layers) / 4.0)

            total_assigned = sum(len(la.node_ids) for la in graph.layers)
            unclassified_layer = next(
                (la for la in graph.layers if la.id == "unclassified"), None,
            )
            unclassified_count = len(unclassified_layer.node_ids) if unclassified_layer else 0

            classification_rate = (
                (total_assigned - unclassified_count) / total_assigned
                if total_assigned > 0 else 0.0
            )

            max_layer_size = max(
                (len(la.node_ids) for la in meaningful_layers), default=0,
            )
            balance = (
                1.0 - (max_layer_size / total_assigned)
                if total_assigned > 0 and meaningful_layers else 0.0
            )

            value = (layer_diversity * 0.3 + classification_rate * 0.5 + balance * 0.2)

            return DimensionScore(
                name="layer_assignment_quality",
                value=round(min(1.0, value), 3),
                max_value=1.0,
                metadata={
                    "total_layers": len(graph.layers),
                    "meaningful_layers": len(meaningful_layers),
                    "classification_rate": round(classification_rate, 3),
                    "balance_score": round(balance, 3),
                },
            )
        except Exception as exc:
            logger.error("D23 layer assignment quality failed: %s", exc)
            return DimensionScore(
                name="layer_assignment_quality",
                value=0.0, max_value=1.0,
                metadata={"error": str(exc)},
            )


class SummaryCompletenessEvaluator:
    """D24: Measures completeness of analysis summaries.

    Checks that the summarizer produces all expected fields with
    non-trivial content.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self._root = Path(project_root)

    def evaluate(self) -> DimensionScore:
        """Build a graph, summarize, and measure completeness."""
        try:
            scanner = ProjectScanner()
            scan_result = scanner.scan(self._root)
            if scan_result.total_files == 0:
                return DimensionScore(
                    name="summary_completeness",
                    value=0.0, max_value=1.0,
                    metadata={"reason": "no files found"},
                )

            builder = ImportGraphBuilder()
            import_graph = builder.build(self._root, scan_result.files)

            decomposer = GraphDecomposer()
            graph = decomposer.build_graph(scan_result, import_graph)

            verifier = GraphVerifier()
            verification = verifier.verify(graph)

            summarizer = AnalysisSummarizer()
            summary = summarizer.summarize(graph, verification)

            checks = {
                "has_target": bool(summary.target),
                "has_files": summary.total_files > 0,
                "has_nodes": summary.total_nodes > 0,
                "has_edges": summary.total_edges > 0,
                "has_layers": summary.layer_count > 0,
                "has_languages": bool(summary.language_breakdown),
                "has_categories": bool(summary.category_breakdown),
                "has_fan_in": bool(summary.top_fan_in),
                "has_impact_text": bool(summary.agent_impact_summary),
                "has_verification": summary.verification is not None,
            }

            passed = sum(1 for v in checks.values() if v)
            value = passed / len(checks)

            return DimensionScore(
                name="summary_completeness",
                value=round(value, 3),
                max_value=1.0,
                metadata={
                    "checks": checks,
                    "passed": passed,
                    "total_checks": len(checks),
                },
            )
        except Exception as exc:
            logger.error("D24 summary completeness failed: %s", exc)
            return DimensionScore(
                name="summary_completeness",
                value=0.0, max_value=1.0,
                metadata={"error": str(exc)},
            )
