"""``nines self-eval`` — run self-evaluation across all capability dimensions."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from nines.iteration.self_eval import (
    CodeCoverageEvaluator,
    ModuleCountEvaluator,
    SelfEvalRunner,
    TestCountEvaluator,
)

logger = logging.getLogger(__name__)


@click.command("self-eval")
@click.option(
    "--baseline-version",
    type=str,
    default="",
    help="Version tag for this evaluation (used for baseline comparison).",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Directory to write the self-evaluation report to.",
)
@click.pass_context
def self_eval_cmd(
    ctx: click.Context,
    baseline_version: str,
    output_dir: str | None,
) -> None:
    """Run self-evaluation across all capability dimensions."""
    verbose = ctx.obj.get("verbose", False)
    output_format = ctx.obj.get("format", "text")

    runner = SelfEvalRunner()
    runner.register_dimension("code_coverage", CodeCoverageEvaluator(coverage_pct=0.0))
    runner.register_dimension("test_count", TestCountEvaluator(count=0))
    runner.register_dimension("module_count", ModuleCountEvaluator(count=0))

    if verbose:
        click.echo("Running self-evaluation across all dimensions...")

    report = runner.run_all(version=baseline_version)

    if output_format == "json":
        output_text = json.dumps(report.to_dict(), indent=2, default=str)
    else:
        lines = [
            f"Self-Evaluation Report (version={report.version or 'untagged'})",
            f"  Timestamp: {report.timestamp}",
            f"  Overall: {report.overall:.4f}",
            f"  Duration: {report.duration:.3f}s",
            "",
            "  Dimensions:",
        ]
        for score in report.scores:
            lines.append(
                f"    {score.name}: {score.value:.3f} / {score.max_value:.3f} "
                f"({score.normalized:.1%})"
            )
        output_text = "\n".join(lines)

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        ext = "json" if output_format == "json" else "txt"
        dest = out / f"self_eval_report.{ext}"
        dest.write_text(output_text, encoding="utf-8")
        click.echo(f"Report written to {dest}")
    else:
        click.echo(output_text)
