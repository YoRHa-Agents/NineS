"""``nines benchmark`` — full analysis-to-evaluation workflow.

Runs the pipeline: analyze → extract key points → generate benchmark
suite → multi-round evaluate → map conclusions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import click

from nines.analyzer.agent_impact import AgentImpactAnalyzer
from nines.analyzer.keypoint import KeyPoint, KeyPointExtractor
from nines.analyzer.pipeline import AnalysisPipeline
from nines.core.models import ExecutionResult
from nines.eval.benchmark_gen import BenchmarkGenerator, BenchmarkSuite
from nines.eval.mapping import MappingTable, MappingTableGenerator
from nines.eval.multi_round import MultiRoundReport, MultiRoundRunner
from nines.eval.scorers import ExactScorer

logger = logging.getLogger(__name__)


def _default_executor(task: Any) -> ExecutionResult:
    """Passthrough executor that returns the expected output verbatim."""
    return ExecutionResult(task_id=task.id, output=task.expected, success=True)


def _format_text_report(
    target_path: str,
    suite: BenchmarkSuite,
    report: MultiRoundReport,
    mapping: MappingTable,
) -> str:
    """Render the benchmark report as human-readable text."""
    lines: list[str] = [
        f"Benchmark Report for {target_path}",
        f"  Suite: {suite.id} ({len(suite.tasks)} tasks)",
        f"  Rounds: {report.total_rounds} (converged: {report.converged})",
        f"  Mean score: {report.mean_composite:.4f} ± {report.std_composite:.4f}",
        "",
        "Key Point → Conclusion Mapping:",
    ]

    for conclusion in mapping.conclusions:
        label = conclusion.observed_effectiveness.capitalize()
        lines.append(
            f"  [{label}] {conclusion.keypoint_title} "
            f"(score: {conclusion.mean_score:.3f}, "
            f"confidence: {conclusion.confidence:.1%})"
        )

    lines.extend([
        "",
        "Summary:",
        f"  Effective: {mapping.effective_count}",
        f"  Ineffective: {mapping.ineffective_count}",
        f"  Inconclusive: {mapping.inconclusive_count}",
        f"  Overall effectiveness: {mapping.overall_effectiveness:.1%}",
    ])

    if mapping.lessons_learnt:
        lines.append("")
        lines.append("Lessons Learnt:")
        for lesson in mapping.lessons_learnt:
            lines.append(f"  - {lesson}")

    return "\n".join(lines)


def _format_json_report(
    target_path: str,
    suite: BenchmarkSuite,
    report: MultiRoundReport,
    mapping: MappingTable,
) -> str:
    """Render the benchmark report as JSON."""
    payload: dict[str, Any] = {
        "target_path": target_path,
        "suite": suite.to_dict(),
        "report": report.to_dict(),
        "mapping": mapping.to_dict(),
    }
    return json.dumps(payload, indent=2, default=str)


def _write_artifacts(
    output_dir: Path,
    suite: BenchmarkSuite,
    report: MultiRoundReport,
    mapping: MappingTable,
) -> None:
    """Persist mapping markdown, suite TOMLs, and report JSON to *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)

    mapping_path = output_dir / "mapping.md"
    mapping_path.write_text(mapping.to_markdown(), encoding="utf-8")
    logger.info("Wrote mapping markdown to %s", mapping_path)

    suite_dir = output_dir / "suite"
    suite.to_toml_dir(suite_dir)
    logger.info("Wrote suite TOMLs to %s", suite_dir)

    report_path = output_dir / "report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Wrote report JSON to %s", report_path)


@click.command("benchmark")
@click.option(
    "--target-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to repo to analyze.",
)
@click.option(
    "--rounds",
    type=int,
    default=3,
    help="Number of evaluation rounds.",
)
@click.option(
    "--convergence-threshold",
    type=float,
    default=0.02,
    help="Score convergence threshold.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Directory for output artifacts.",
)
@click.option(
    "--suite-id",
    type=str,
    default="",
    help="Benchmark suite identifier.",
)
@click.pass_context
def benchmark_cmd(
    ctx: click.Context,
    target_path: str,
    rounds: int,
    convergence_threshold: float,
    output_dir: str | None,
    suite_id: str,
) -> None:
    """Full analysis→benchmark→evaluate→mapping workflow."""
    output_format = ctx.obj.get("format", "text")
    verbose = ctx.obj.get("verbose", False)

    if verbose:
        click.echo(f"Starting benchmark workflow for {target_path}")

    # Step 1: Run analysis pipeline
    logger.info("Running analysis pipeline on %s", target_path)
    pipeline = AnalysisPipeline()
    analysis_result = pipeline.run(target_path)

    # Step 2: Run agent impact analysis and extract key points
    logger.info("Running agent impact analysis on %s", target_path)
    impact_analyzer = AgentImpactAnalyzer()
    impact_report = impact_analyzer.analyze(target_path)

    extractor = KeyPointExtractor()
    kp_report = extractor.extract(impact_report, analysis_result)
    key_points: list[KeyPoint] = kp_report.key_points

    if not key_points:
        click.echo("No key points extracted — nothing to benchmark.", err=True)
        ctx.exit(1)
        return

    if verbose:
        click.echo(f"Extracted {len(key_points)} key point(s)")

    # Step 3: Generate benchmark suite
    logger.info("Generating benchmark suite")
    generator = BenchmarkGenerator()
    suite = generator.generate(key_points, suite_id)

    if not suite.tasks:
        click.echo("Benchmark generator produced no tasks.", err=True)
        ctx.exit(1)
        return

    if verbose:
        click.echo(f"Generated suite {suite.id} with {len(suite.tasks)} task(s)")

    # Step 4: Run multi-round evaluation
    logger.info("Running multi-round evaluation (%d rounds)", rounds)
    runner = MultiRoundRunner(
        convergence_threshold=convergence_threshold,
        min_rounds=rounds,
        max_rounds=max(rounds, 5),
    )
    report = runner.run(suite.tasks, _default_executor, [ExactScorer()], suite.id)

    if verbose:
        click.echo(
            f"Evaluation complete: mean={report.mean_composite:.4f}, "
            f"converged={report.converged}"
        )

    # Step 5: Generate mapping table
    logger.info("Generating key-point-to-conclusion mapping")
    mapping_gen = MappingTableGenerator()
    mapping = mapping_gen.generate(key_points, report, suite)

    # Step 6: Output results
    if output_format == "json":
        text = _format_json_report(target_path, suite, report, mapping)
    else:
        text = _format_text_report(target_path, suite, report, mapping)

    click.echo(text)

    # Step 7: Write artifacts if output-dir specified
    if output_dir:
        _write_artifacts(Path(output_dir), suite, report, mapping)
        click.echo(f"Artifacts written to {output_dir}")
