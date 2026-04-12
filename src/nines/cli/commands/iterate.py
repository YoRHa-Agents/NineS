"""``nines iterate`` — execute a self-improvement iteration cycle."""

from __future__ import annotations

import json
import logging

import click

from nines.iteration.convergence import ConvergenceChecker
from nines.iteration.gap_detector import GapDetector
from nines.iteration.planner import ImprovementPlanner
from nines.iteration.self_eval import (
    CodeCoverageEvaluator,
    ModuleCountEvaluator,
    SelfEvalRunner,
    TestCountEvaluator,
)

logger = logging.getLogger(__name__)


@click.command("iterate")
@click.option(
    "--max-rounds",
    type=int,
    default=5,
    show_default=True,
    help="Maximum number of iteration rounds.",
)
@click.option(
    "--threshold",
    type=float,
    default=0.05,
    show_default=True,
    help="Convergence variance threshold.",
)
@click.pass_context
def iterate_cmd(
    ctx: click.Context,
    max_rounds: int,
    threshold: float,
) -> None:
    """Execute a self-improvement iteration cycle."""
    verbose = ctx.obj.get("verbose", False)
    output_format = ctx.obj.get("format", "text")

    runner = SelfEvalRunner()
    runner.register_dimension("code_coverage", CodeCoverageEvaluator(coverage_pct=0.0))
    runner.register_dimension("test_count", TestCountEvaluator(count=0))
    runner.register_dimension("module_count", ModuleCountEvaluator(count=0))

    detector = GapDetector()
    planner = ImprovementPlanner()
    convergence = ConvergenceChecker(min_rounds=2)
    history: list[float] = []

    if verbose:
        click.echo(f"Starting iteration (max_rounds={max_rounds}, threshold={threshold})")

    baseline_report = runner.run_all(version="baseline")
    history.append(baseline_report.overall)

    for round_num in range(1, max_rounds + 1):
        current_report = runner.run_all(version=f"round-{round_num}")
        history.append(current_report.overall)

        gap_analysis = detector.detect(current_report, baseline_report)
        plan = planner.plan(gap_analysis)

        if verbose:
            click.echo(
                f"  Round {round_num}: overall={current_report.overall:.4f}, "
                f"gaps={plan.total_gaps}, suggestions={len(plan.suggestions)}"
            )

        conv_result = convergence.check(history, threshold=threshold)
        if conv_result.converged:
            click.echo(f"Converged after {round_num} round(s) (variance={conv_result.variance:.6f})")
            break

        baseline_report = current_report
    else:
        click.echo(f"Did not converge after {max_rounds} round(s).")

    final = history[-1] if history else 0.0
    if output_format == "json":
        summary = {
            "rounds": len(history) - 1,
            "converged": conv_result.converged if history else False,
            "final_score": final,
            "history": history,
        }
        click.echo(json.dumps(summary, indent=2))
    else:
        click.echo(f"Final score: {final:.4f} after {len(history) - 1} round(s).")
