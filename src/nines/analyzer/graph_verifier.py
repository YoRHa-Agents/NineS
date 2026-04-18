"""Knowledge graph verification.

Validates structural integrity, referential consistency, and coverage
of a :class:`KnowledgeGraph`.

C03 N3 (regression detector): the new
:meth:`GraphVerifier._check_id_canonicalisation` walks every node and
every edge endpoint and verifies that each ID is *already* canonical
under :func:`canonicalize_id`.  Any divergence is reported as a
``severity="warning"`` issue (category ``id_canonicalisation``) so a
future code path that bypasses the builder-side canonicalisation in
:class:`~nines.analyzer.graph_decomposer.GraphDecomposer` is caught by
the verifier without breaking existing referential checks.

Covers: FR-320.
"""

from __future__ import annotations

import logging

from nines.analyzer.graph_canonicalizer import (
    canonicalize_id,
    common_project_root,
)
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

    def verify(
        self,
        graph: KnowledgeGraph,
        *,
        project_root: str | None = None,
    ) -> VerificationResult:
        """Run all verification checks on *graph*.

        Parameters
        ----------
        graph:
            The knowledge graph to verify.
        project_root:
            Optional explicit project root.  When provided, used by
            referential-integrity canonicalisation to align node IDs and
            edge endpoints regardless of the encoding each producer
            chose.  When omitted, the verifier falls back to deriving a
            root from absolute paths found in the graph (less precise).

        Returns
        -------
        VerificationResult
            Aggregated result with issues and coverage metrics.
        """
        # Resolve the canonicalisation root once so every check sees
        # the same anchor.  Reused by both the referential-integrity
        # check and the new id-canonicalisation regression detector.
        effective_root = self._resolve_root(graph, project_root)

        issues: list[VerificationIssue] = []
        issues.extend(
            self._check_referential_integrity(graph, project_root=effective_root),
        )
        issues.extend(self._check_duplicate_edges(graph))
        issues.extend(self._check_orphan_nodes(graph))
        issues.extend(self._check_layer_coverage(graph))
        issues.extend(self._check_node_types(graph))
        issues.extend(self._check_edge_types(graph))
        issues.extend(self._check_self_loops(graph))
        issues.extend(
            self._check_id_canonicalisation(graph, project_root=effective_root),
        )

        node_ids = {n.id for n in graph.nodes}
        layered_ids: set[str] = set()
        for layer in graph.layers:
            layered_ids.update(layer.node_ids)

        # C03: when no layers are declared the coverage *must* be 0.0,
        # not 100.0 — the prior behaviour reported full coverage even on
        # empty layers because the intersection of two empty sets is
        # empty (and the divisor is non-zero).  Downstream consumers
        # treat ``layer_coverage_pct`` as a real coverage signal, so
        # an empty-layers graph reports 0% coverage explicitly.
        if not graph.layers:
            coverage_pct = 0.0
        else:
            coverage_pct = len(layered_ids & node_ids) / len(node_ids) * 100.0 if node_ids else 0.0

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
            "Verification %s: %d issues (%d critical), %.1f%% layer coverage, %d orphans",
            "PASSED" if result.passed else "FAILED",
            len(issues),
            sum(1 for i in issues if i.severity == "critical"),
            coverage_pct,
            orphan_count,
        )

        return result

    @staticmethod
    def _resolve_root(
        graph: KnowledgeGraph,
        project_root: str | None,
    ) -> str:
        """Return the canonicalisation anchor for *graph*.

        Prefers the explicit *project_root* when supplied; otherwise
        derives a best-effort common prefix from absolute paths found
        on nodes and edge endpoints (the same heuristic used by the
        legacy referential-integrity check).
        """
        if project_root:
            return project_root

        candidate_paths: list[str] = []
        for n in graph.nodes:
            if n.file_path and n.file_path.startswith("/"):
                candidate_paths.append(n.file_path)
        for e in graph.edges:
            for endpoint in (e.source, e.target):
                if not endpoint or ":" not in endpoint:
                    continue
                _, _, remainder = endpoint.partition(":")
                path_part = remainder.split("::", 1)[0]
                if path_part.startswith("/"):
                    candidate_paths.append(path_part)
        if candidate_paths:
            return common_project_root(candidate_paths)
        return "."

    @staticmethod
    def _check_referential_integrity(
        graph: KnowledgeGraph,
        *,
        project_root: str | None = None,
    ) -> list[VerificationIssue]:
        """Verify every edge references existing nodes.

        Both node IDs and edge endpoints are canonicalised before the
        set-membership comparison so that producers using different path
        encodings (relative vs absolute) don't trigger false positives.
        See C03 baseline §4.1 for the empirical motivation.

        Parameters
        ----------
        graph:
            Graph under verification.
        project_root:
            Explicit anchor used by the canonicalizer.  Resolved by
            :meth:`_resolve_root` when called from :meth:`verify`.
        """
        # Always work with a non-empty root; ``"."`` is the safe default
        # so canonicalize_id never raises.
        root = project_root or "."

        canonical_node_ids = {canonicalize_id(n.id, project_root=root) for n in graph.nodes}
        issues: list[VerificationIssue] = []
        for edge in graph.edges:
            canon_source = canonicalize_id(edge.source, project_root=root)
            canon_target = canonicalize_id(edge.target, project_root=root)
            missing: list[str] = []
            if canon_source not in canonical_node_ids:
                missing.append(edge.source)
            if canon_target not in canonical_node_ids:
                missing.append(edge.target)
            if missing:
                issues.append(
                    VerificationIssue(
                        severity="critical",
                        category="referential_integrity",
                        message=(
                            f"Edge ({edge.source} -> {edge.target}) references "
                            f"non-existent node(s): {', '.join(missing)}"
                        ),
                        node_ids=missing,
                    )
                )
        return issues

    @staticmethod
    def _check_id_canonicalisation(
        graph: KnowledgeGraph,
        *,
        project_root: str | None = None,
    ) -> list[VerificationIssue]:
        """Flag any node or edge ID that is not already canonical.

        This is C03 N3's regression detector: the builder-side fix in
        :class:`~nines.analyzer.graph_decomposer.GraphDecomposer` should
        canonicalise every ID at construction time.  If a future code
        path bypasses that funnel (e.g. a new graph-emitting analyzer
        that mints raw absolute paths), this check surfaces the mismatch
        as a ``severity="warning"`` issue with category
        ``id_canonicalisation``.

        Severity is intentionally ``warning`` rather than ``critical``:
        the consumer-side patch in :meth:`_check_referential_integrity`
        still resolves the verifier's headline ``passed`` status, but a
        warning is enough to catch the regression in code review.

        Parameters
        ----------
        graph:
            Graph under verification.
        project_root:
            Explicit anchor used by the canonicalizer.  Resolved by
            :meth:`_resolve_root` when called from :meth:`verify`.
        """
        root = project_root or "."

        offending_node_ids: list[str] = []
        for node in graph.nodes:
            if not node.id:
                # Empty IDs are a separate failure mode; surface them
                # explicitly so the next checks can see them.
                offending_node_ids.append(node.id)
                continue
            canonical = canonicalize_id(node.id, project_root=root)
            if canonical != node.id:
                offending_node_ids.append(node.id)

        offending_endpoints: list[str] = []
        for edge in graph.edges:
            for endpoint in (edge.source, edge.target):
                if not endpoint:
                    continue
                canonical = canonicalize_id(endpoint, project_root=root)
                if canonical != endpoint:
                    offending_endpoints.append(endpoint)

        issues: list[VerificationIssue] = []
        if offending_node_ids:
            # Cap the surfaced sample so a 1000-node regression doesn't
            # produce an unreadable issue payload.
            sample = offending_node_ids[:20]
            issues.append(
                VerificationIssue(
                    severity="warning",
                    category="id_canonicalisation",
                    message=(
                        f"{len(offending_node_ids)} node ID(s) are not in "
                        "canonical form; the builder should normalise them "
                        "via canonicalize_id() at construction time."
                    ),
                    node_ids=sample,
                )
            )

        if offending_endpoints:
            sample = offending_endpoints[:20]
            issues.append(
                VerificationIssue(
                    severity="warning",
                    category="id_canonicalisation",
                    message=(
                        f"{len(offending_endpoints)} edge endpoint(s) are "
                        "not in canonical form; the builder should normalise "
                        "them via canonicalize_id() at construction time."
                    ),
                    node_ids=sample,
                )
            )

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
                issues.append(
                    VerificationIssue(
                        severity="warning",
                        category="duplicate_edge",
                        message=(
                            f"Duplicate edge ({src} -> {tgt}, type={etype}) appears {count} times"
                        ),
                        node_ids=[src, tgt],
                    )
                )
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
            issues.append(
                VerificationIssue(
                    severity="info",
                    category="orphan_node",
                    message=f"{len(orphans)} node(s) have no edges",
                    node_ids=orphans,
                )
            )
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
            issues.append(
                VerificationIssue(
                    severity="warning",
                    category="missing_layer",
                    message=(
                        f"{len(uncovered)} of {len(node_ids)} nodes "
                        f"({len(uncovered) / len(node_ids):.0%}) are not "
                        f"assigned to any layer"
                    ),
                    node_ids=sorted(uncovered)[:20],
                )
            )
        return issues

    @staticmethod
    def _check_node_types(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Flag nodes with invalid node_type."""
        bad = [n.id for n in graph.nodes if n.node_type not in VALID_NODE_TYPES]
        issues: list[VerificationIssue] = []
        if bad:
            issues.append(
                VerificationIssue(
                    severity="warning",
                    category="invalid_node_type",
                    message=f"{len(bad)} node(s) have invalid node_type",
                    node_ids=bad[:20],
                )
            )
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
            issues.append(
                VerificationIssue(
                    severity="warning",
                    category="invalid_edge_type",
                    message=f"{len(bad_pairs)} edge(s) have invalid edge_type",
                    node_ids=[],
                )
            )
        return issues

    @staticmethod
    def _check_self_loops(
        graph: KnowledgeGraph,
    ) -> list[VerificationIssue]:
        """Detect edges where source == target."""
        loops = [e.source for e in graph.edges if e.source == e.target]
        issues: list[VerificationIssue] = []
        if loops:
            issues.append(
                VerificationIssue(
                    severity="info",
                    category="self_loop",
                    message=f"{len(loops)} self-loop edge(s) detected",
                    node_ids=list(set(loops)),
                )
            )
        return issues
