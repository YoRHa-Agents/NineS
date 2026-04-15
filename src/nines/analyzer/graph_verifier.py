"""Knowledge graph verification.

Validates structural integrity, referential consistency, and coverage
of a :class:`KnowledgeGraph`.

Covers: FR-320.
"""

from __future__ import annotations

import logging

from nines.analyzer.graph_models import (
    VALID_EDGE_TYPES,
    VALID_NODE_TYPES,
    KnowledgeGraph,
    VerificationIssue,
    VerificationResult,
)

logger = logging.getLogger(__name__)


class GraphVerifier:
    """Validates a :class:`KnowledgeGraph` for structural correctness."""

    def verify(self, graph: KnowledgeGraph) -> VerificationResult:
        """Run all verification checks on *graph*.

        Parameters
        ----------
        graph:
            The knowledge graph to verify.

        Returns
        -------
        VerificationResult
            Aggregated result with issues and coverage metrics.
        """
        issues: list[VerificationIssue] = []
        issues.extend(self._check_referential_integrity(graph))
        issues.extend(self._check_duplicate_edges(graph))
        issues.extend(self._check_orphan_nodes(graph))
        issues.extend(self._check_layer_coverage(graph))
        issues.extend(self._check_node_types(graph))
        issues.extend(self._check_edge_types(graph))
        issues.extend(self._check_self_loops(graph))

        node_ids = {n.id for n in graph.nodes}
        layered_ids: set[str] = set()
        for layer in graph.layers:
            layered_ids.update(layer.node_ids)

        coverage_pct = (
            len(layered_ids & node_ids) / len(node_ids) * 100.0
            if node_ids else 0.0
        )

        edge_endpoints = set()
        for e in graph.edges:
            edge_endpoints.add(e.source)
            edge_endpoints.add(e.target)
        orphan_count = len(node_ids - edge_endpoints)

        has_critical = any(i.severity == "critical" for i in issues)

        result = VerificationResult(
            passed=not has_critical,
            issues=issues,
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            layer_coverage_pct=round(coverage_pct, 2),
            orphan_count=orphan_count,
        )

        logger.info(
            "Verification %s: %d issues (%d critical), "
            "%.1f%% layer coverage, %d orphans",
            "PASSED" if result.passed else "FAILED",
            len(issues),
            sum(1 for i in issues if i.severity == "critical"),
            coverage_pct,
            orphan_count,
        )

        return result

    @staticmethod
    def _check_referential_integrity(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Verify every edge references existing nodes."""
        node_ids = {n.id for n in graph.nodes}
        issues: list[VerificationIssue] = []
        for edge in graph.edges:
            missing: list[str] = []
            if edge.source not in node_ids:
                missing.append(edge.source)
            if edge.target not in node_ids:
                missing.append(edge.target)
            if missing:
                issues.append(VerificationIssue(
                    severity="critical",
                    category="referential_integrity",
                    message=(
                        f"Edge ({edge.source} -> {edge.target}) references "
                        f"non-existent node(s): {', '.join(missing)}"
                    ),
                    node_ids=missing,
                ))
        return issues

    @staticmethod
    def _check_duplicate_edges(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Detect duplicate edges (same source, target, and type)."""
        seen: dict[tuple[str, str, str], int] = {}
        for edge in graph.edges:
            key = (edge.source, edge.target, edge.edge_type)
            seen[key] = seen.get(key, 0) + 1

        issues: list[VerificationIssue] = []
        for (src, tgt, etype), count in seen.items():
            if count > 1:
                issues.append(VerificationIssue(
                    severity="warning",
                    category="duplicate_edge",
                    message=(
                        f"Duplicate edge ({src} -> {tgt}, type={etype}) "
                        f"appears {count} times"
                    ),
                    node_ids=[src, tgt],
                ))
        return issues

    @staticmethod
    def _check_orphan_nodes(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Find nodes with no edges."""
        connected: set[str] = set()
        for edge in graph.edges:
            connected.add(edge.source)
            connected.add(edge.target)

        orphans = [n.id for n in graph.nodes if n.id not in connected]
        issues: list[VerificationIssue] = []
        if orphans:
            issues.append(VerificationIssue(
                severity="info",
                category="orphan_node",
                message=f"{len(orphans)} node(s) have no edges",
                node_ids=orphans,
            ))
        return issues

    @staticmethod
    def _check_layer_coverage(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Check whether all nodes are assigned to a layer."""
        node_ids = {n.id for n in graph.nodes}
        layered: set[str] = set()
        for layer in graph.layers:
            layered.update(layer.node_ids)

        uncovered = node_ids - layered
        issues: list[VerificationIssue] = []

        if node_ids and len(uncovered) / len(node_ids) > 0.2:
            issues.append(VerificationIssue(
                severity="warning",
                category="missing_layer",
                message=(
                    f"{len(uncovered)} of {len(node_ids)} nodes "
                    f"({len(uncovered) / len(node_ids):.0%}) are not "
                    f"assigned to any layer"
                ),
                node_ids=sorted(uncovered)[:20],
            ))
        return issues

    @staticmethod
    def _check_node_types(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Flag nodes with invalid node_type."""
        bad = [n.id for n in graph.nodes if n.node_type not in VALID_NODE_TYPES]
        issues: list[VerificationIssue] = []
        if bad:
            issues.append(VerificationIssue(
                severity="warning",
                category="invalid_node_type",
                message=f"{len(bad)} node(s) have invalid node_type",
                node_ids=bad[:20],
            ))
        return issues

    @staticmethod
    def _check_edge_types(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Flag edges with invalid edge_type."""
        bad_pairs: list[str] = []
        for e in graph.edges:
            if e.edge_type not in VALID_EDGE_TYPES:
                bad_pairs.append(f"{e.source}->{e.target}")
        issues: list[VerificationIssue] = []
        if bad_pairs:
            issues.append(VerificationIssue(
                severity="warning",
                category="invalid_edge_type",
                message=f"{len(bad_pairs)} edge(s) have invalid edge_type",
                node_ids=[],
            ))
        return issues

    @staticmethod
    def _check_self_loops(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Detect edges where source == target."""
        loops = [e.source for e in graph.edges if e.source == e.target]
        issues: list[VerificationIssue] = []
        if loops:
            issues.append(VerificationIssue(
                severity="info",
                category="self_loop",
                message=f"{len(loops)} self-loop edge(s) detected",
                node_ids=list(set(loops)),
            ))
        return issues
