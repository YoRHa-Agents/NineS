"""Analysis summary generator.

Produces structured summaries from knowledge graphs, including
fan-in/fan-out rankings, entry point detection, and agent impact
text.

Covers: FR-321.
"""

from __future__ import annotations

import logging
from pathlib import Path

from nines.analyzer.graph_models import (
    AnalysisSummary,
    KnowledgeGraph,
    VerificationResult,
)

logger = logging.getLogger(__name__)


class AnalysisSummarizer:
    """Generates an :class:`AnalysisSummary` from a :class:`KnowledgeGraph`."""

    def summarize(
        self,
        graph: KnowledgeGraph,
        verification: VerificationResult | None = None,
    ) -> AnalysisSummary:
        """Build a structured summary from *graph*.

        Parameters
        ----------
        graph:
            The knowledge graph to summarize.
        verification:
            Optional verification result to attach.

        Returns
        -------
        AnalysisSummary
        """
        file_nodes = [n for n in graph.nodes if n.node_type == "file"]

        lang_breakdown: dict[str, int] = {}
        cat_breakdown: dict[str, int] = {}
        for node in file_nodes:
            lang = node.metadata.get("language", "") or ""
            if lang:
                lang_breakdown[lang] = lang_breakdown.get(lang, 0) + 1
            cat = node.file_category or ""
            if cat:
                cat_breakdown[cat] = cat_breakdown.get(cat, 0) + 1

        top_fan_in, top_fan_out = self._compute_fan_rankings(graph)
        entry_points = self._detect_entry_points(graph)
        impact_text = self._build_agent_impact_text(graph)

        summary = AnalysisSummary(
            target=graph.project_name,
            total_files=len(file_nodes),
            total_nodes=len(graph.nodes),
            total_edges=len(graph.edges),
            layer_count=len(graph.layers),
            language_breakdown=lang_breakdown,
            category_breakdown=cat_breakdown,
            top_fan_in=top_fan_in,
            top_fan_out=top_fan_out,
            key_entry_points=entry_points,
            agent_impact_summary=impact_text,
            verification=verification,
        )

        logger.info(
            "Summary: %d files, %d nodes, %d edges, %d layers",
            summary.total_files,
            summary.total_nodes,
            summary.total_edges,
            summary.layer_count,
        )
        return summary

    @staticmethod
    def _compute_fan_rankings(
        graph: KnowledgeGraph,
    ) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
        """Return top-10 nodes by fan-in and fan-out."""
        fan_in: dict[str, int] = {}
        fan_out: dict[str, int] = {}
        for edge in graph.edges:
            fan_in[edge.target] = fan_in.get(edge.target, 0) + 1
            fan_out[edge.source] = fan_out.get(edge.source, 0) + 1

        top_in = sorted(fan_in.items(), key=lambda x: -x[1])[:10]
        top_out = sorted(fan_out.items(), key=lambda x: -x[1])[:10]
        return top_in, top_out

    @staticmethod
    def _detect_entry_points(graph: KnowledgeGraph) -> list[str]:
        """Detect likely entry point nodes.

        Heuristic: nodes named main/app/index/cli, or nodes with
        high fan-in and low fan-out.
        """
        entry_names = {"main", "app", "index", "cli", "__main__", "server"}
        candidates: list[str] = []

        for node in graph.nodes:
            if node.node_type != "file":
                continue
            stem = Path(node.file_path).stem.lower() if node.file_path else ""
            if stem in entry_names:
                candidates.append(node.id)

        fan_in: dict[str, int] = {}
        fan_out: dict[str, int] = {}
        for edge in graph.edges:
            fan_in[edge.target] = fan_in.get(edge.target, 0) + 1
            fan_out[edge.source] = fan_out.get(edge.source, 0) + 1

        for node in graph.nodes:
            if node.id in candidates:
                continue
            fi = fan_in.get(node.id, 0)
            fo = fan_out.get(node.id, 0)
            if fi >= 5 and fo <= 2 and node.node_type == "file":
                candidates.append(node.id)

        return candidates

    @staticmethod
    def _build_agent_impact_text(graph: KnowledgeGraph) -> str:
        """Build a human-readable agent impact summary."""
        parts: list[str] = []
        parts.append(
            f"Project '{graph.project_name}' contains "
            f"{len(graph.nodes)} nodes and {len(graph.edges)} edges"
        )

        if graph.languages:
            parts.append(f"Languages: {', '.join(graph.languages[:5])}")
        if graph.frameworks:
            parts.append(f"Frameworks: {', '.join(graph.frameworks[:5])}")
        if graph.layers:
            layer_names = [la.name for la in graph.layers]
            parts.append(f"Architecture layers: {', '.join(layer_names)}")

        cat_breakdown = graph.metadata.get("category_breakdown", {})
        if cat_breakdown:
            top_cats = sorted(cat_breakdown.items(), key=lambda x: -x[1])[:3]
            cat_str = ", ".join(f"{cat}: {count}" for cat, count in top_cats)
            parts.append(f"File categories: {cat_str}")

        return ". ".join(parts) + "."
