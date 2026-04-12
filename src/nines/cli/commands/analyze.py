"""``nines analyze`` — analyze and decompose code into structured units."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from nines.analyzer.pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)

_VALID_STRATEGIES = ("functional", "concern", "layer")


@click.command("analyze")
@click.option(
    "--target-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to a Python file or directory to analyze.",
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
@click.pass_context
def analyze_cmd(
    ctx: click.Context,
    target_path: str,
    strategy: str,
    output_dir: str | None,
) -> None:
    """Analyze and decompose collected knowledge into structured units."""
    verbose = ctx.obj.get("verbose", False)
    output_format = ctx.obj.get("format", "text")

    if verbose:
        click.echo(f"Analyzing {target_path} with strategy={strategy}")

    pipeline = AnalysisPipeline()
    result = pipeline.run(target_path)

    metrics = result.metrics
    findings_count = len(result.findings)

    if output_format == "json":
        report = json.dumps(result.to_dict(), indent=2, default=str)
    else:
        lines = [
            f"Analysis of {result.target}",
            f"  Files analyzed: {metrics.get('files_analyzed', 0)}",
            f"  Total lines: {metrics.get('total_lines', 0)}",
            f"  Functions: {metrics.get('total_functions', 0)}",
            f"  Classes: {metrics.get('total_classes', 0)}",
            f"  Avg complexity: {metrics.get('avg_complexity', 0.0)}",
            f"  Knowledge units: {metrics.get('knowledge_units', 0)}",
            f"  Findings: {findings_count}",
            f"  Duration: {metrics.get('duration_ms', 0.0):.1f} ms",
        ]
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
