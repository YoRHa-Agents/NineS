"""``nines analyze`` — analyze and decompose code into structured units."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from nines.analyzer.pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)

_VALID_STRATEGIES = ("functional", "concern", "layer", "graph")


@click.command("analyze")
@click.option(
    "--target-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to a repository or directory to analyze for Agent impact.",
)
@click.option(
    "--strategy",
    type=click.Choice(_VALID_STRATEGIES, case_sensitive=False),
    default="functional",
    show_default=True,
    help="Decomposition strategy.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Directory to write analysis results to.",
)
@click.option(
    "--agent-impact/--no-agent-impact",
    default=True,
    show_default=True,
    help="Run Agent impact analysis (default: enabled).",
)
@click.option(
    "--keypoints/--no-keypoints",
    default=True,
    show_default=True,
    help="Extract key points (default: enabled, implies --agent-impact).",
)
@click.option(
    "--depth",
    type=click.Choice(["shallow", "deep"], case_sensitive=False),
    default="shallow",
    show_default=True,
    help="Analysis depth.",
)
@click.pass_context
def analyze_cmd(
    ctx: click.Context,
    target_path: str,
    strategy: str,
    output_dir: str | None,
    agent_impact: bool,
    keypoints: bool,
    depth: str,
) -> None:
    """Analyze and decompose collected knowledge into structured units."""
    verbose = ctx.obj.get("verbose", False)
    output_format = ctx.obj.get("format", "text")

    if verbose:
        click.echo(f"Analyzing {target_path} with strategy={strategy} depth={depth}")

    pipeline = AnalysisPipeline()
    result = pipeline.run(
        target_path,
        agent_impact=agent_impact,
        keypoints=keypoints,
        strategy=strategy,
        depth=depth,
    )

    metrics = result.metrics
    findings_count = len(result.findings)

    if output_format == "json":
        report = json.dumps(result.to_dict(), indent=2, default=str)
    else:
        has_impact = "agent_impact" in metrics
        if has_impact:
            lines = [f"Agent Impact Analysis of {result.target}"]
        else:
            lines = [f"Analysis of {result.target}"]

        if has_impact:
            ai_data = metrics["agent_impact"]
            lines.append(
                f"  Total files scanned: {metrics.get('total_files_scanned', 0)}"
            )
            lines.append(
                f"  Agent mechanisms: {len(ai_data.get('mechanisms', []))}"
            )
            lines.append(
                f"  Agent artifacts: {len(ai_data.get('agent_facing_artifacts', []))}"
            )

            if "key_points" in metrics:
                kp_data = metrics["key_points"]
                kp_list = kp_data.get("key_points", [])
                lines.append(f"  Key points: {len(kp_list)}")
                for kp in kp_list[:5]:
                    lines.append(
                        f"    [{kp.get('priority', '?')}] "
                        f"{kp.get('title', 'untitled')}"
                    )

            lines.append("")
            lines.append("  Code structure:")

        lines.append(f"  Files analyzed: {metrics.get('files_analyzed', 0)}")
        lines.append(f"  Total lines: {metrics.get('total_lines', 0)}")
        lines.append(f"  Functions: {metrics.get('total_functions', 0)}")
        lines.append(f"  Classes: {metrics.get('total_classes', 0)}")
        lines.append(f"  Avg complexity: {metrics.get('avg_complexity', 0.0)}")
        lines.append(f"  Knowledge units: {metrics.get('knowledge_units', 0)}")
        lines.append(f"  Findings: {findings_count}")
        lines.append(f"  Duration: {metrics.get('duration_ms', 0.0):.1f} ms")

        if "knowledge_graph" in metrics:
            kg = metrics["knowledge_graph"]
            lines.append("")
            lines.append("  Knowledge graph:")
            scan_info = kg.get("scan", {})
            lines.append(f"    Scanned files: {scan_info.get('total_files', 0)}")
            lines.append(f"    Languages: {', '.join(scan_info.get('languages', []))}")
            lines.append(f"    Frameworks: {', '.join(scan_info.get('frameworks', []))}")
            ig = kg.get("import_graph", {})
            lines.append(f"    Import edges: {ig.get('edges', 0)}")
            lines.append(f"    Unresolved imports: {ig.get('unresolved', 0)}")
            graph_data = kg.get("graph", {})
            lines.append(f"    Graph nodes: {len(graph_data.get('nodes', []))}")
            lines.append(f"    Graph edges: {len(graph_data.get('edges', []))}")
            lines.append(f"    Layers: {len(graph_data.get('layers', []))}")
            ver = kg.get("verification", {})
            lines.append(
                f"    Verification: {'PASSED' if ver.get('passed') else 'FAILED'} "
                f"({len(ver.get('issues', []))} issues, "
                f"{ver.get('layer_coverage_pct', 0):.1f}% layer coverage)"
            )

        report = "\n".join(lines)

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        ext = "json" if output_format == "json" else "txt"
        dest = out / f"analysis_report.{ext}"
        dest.write_text(report, encoding="utf-8")
        click.echo(f"Report written to {dest}")
    else:
        click.echo(report)
