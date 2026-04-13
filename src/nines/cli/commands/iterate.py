"""``nines iterate`` — execute a self-improvement iteration cycle."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from nines.iteration.convergence import ConvergenceChecker
from nines.iteration.gap_detector import GapDetector
from nines.iteration.planner import ImprovementPlanner
from nines.iteration.self_eval import (
    CodeCoverageEvaluator,
    DocstringCoverageEvaluator,
    LintCleanlinessEvaluator,
    LiveCodeCoverageEvaluator,
    LiveModuleCountEvaluator,
    LiveTestCountEvaluator,
    ModuleCountEvaluator,
    SelfEvalRunner,
    TestCountEvaluator,
)

logger = logging.getLogger(__name__)


def _detect_src_dir(project_root: Path) -> str:
    """Auto-detect the source directory within a project root."""
    for candidate in ["src", "lib", "."]:
        p = project_root / candidate
        if p.is_dir() and any(p.rglob("*.py")):
            return str(p)
    return str(project_root)


def _detect_test_dir(project_root: Path) -> str:
    """Auto-detect the test directory within a project root."""
    for candidate in ["tests", "test"]:
        p = project_root / candidate
        if p.is_dir():
            return str(p)
    return "tests"


def _build_live_evaluators(
    project_root: Path,
    src_dir: str | None,
    test_dir: str | None,
) -> SelfEvalRunner:
    """Build a SelfEvalRunner with live evaluators for the given project."""
    resolved_src = src_dir if src_dir else _detect_src_dir(project_root)
    resolved_test = test_dir if test_dir else _detect_test_dir(project_root)

    runner = SelfEvalRunner()
    runner.register_dimension(
        "code_coverage",
        LiveCodeCoverageEvaluator(project_root=str(project_root)),
    )
    runner.register_dimension(
        "test_count",
        LiveTestCountEvaluator(test_dir=resolved_test),
    )
    runner.register_dimension(
        "module_count",
        LiveModuleCountEvaluator(src_dir=resolved_src),
    )
    runner.register_dimension(
        "docstring_coverage",
        DocstringCoverageEvaluator(src_dir=resolved_src),
    )
    runner.register_dimension(
        "lint_cleanliness",
        LintCleanlinessEvaluator(src_dir=resolved_src),
    )
    return runner


def _build_stub_evaluators() -> SelfEvalRunner:
    """Build a SelfEvalRunner with stub evaluators (non-zero initial values)."""
    runner = SelfEvalRunner()
    runner.register_dimension("code_coverage", CodeCoverageEvaluator(coverage_pct=50.0))
    runner.register_dimension("test_count", TestCountEvaluator(count=1))
    runner.register_dimension("module_count", ModuleCountEvaluator(count=1))
    return runner


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
@click.option(
    "--project-root",
    type=click.Path(exists=True),
    default=None,
    help="Project root directory.",
)
@click.option(
    "--src-dir",
    type=click.Path(),
    default=None,
    help="Source directory for analysis. Auto-detected if not set.",
)
@click.option(
    "--test-dir",
    type=click.Path(),
    default=None,
    help="Test directory. Auto-detected if not set.",
)
@click.pass_context
def iterate_cmd(
    ctx: click.Context,
    max_rounds: int,
    threshold: float,
    project_root: str | None,
    src_dir: str | None,
    test_dir: str | None,
) -> None:
    """Execute a self-improvement iteration cycle."""
    verbose = ctx.obj.get("verbose", False)
    output_format = ctx.obj.get("format", "text")

    if project_root is not None:
        root = Path(project_root).resolve()
        runner = _build_live_evaluators(root, src_dir, test_dir)
        if verbose:
            click.echo(f"Using live evaluators for project: {root}")
    else:
        logger.warning(
            "No project context provided. Use --project-root for meaningful iteration."
        )
        click.echo(
            "Warning: No project context provided. "
            "Use --project-root for meaningful iteration.",
            err=True,
        )
        runner = _build_stub_evaluators()

    detector = GapDetector()
    planner = ImprovementPlanner()
    convergence = ConvergenceChecker(min_rounds=2)
    history: list[float] = []

    if verbose:
        click.echo(f"Starting iteration (max_rounds={max_rounds}, threshold={threshold})")

    baseline_report = runner.run_all(version="baseline")
    history.append(baseline_report.overall)

    conv_result = None
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
            msg = (
                f"Converged after {round_num} round(s) "
                f"(variance={conv_result.variance:.6f})"
            )
            click.echo(msg)
            break

        baseline_report = current_report
    else:
        click.echo(f"Did not converge after {max_rounds} round(s).")

    final = history[-1] if history else 0.0
    if output_format == "json":
        summary = {
            "rounds": len(history) - 1,
            "converged": conv_result.converged if conv_result else False,
            "final_score": final,
            "history": history,
        }
        click.echo(json.dumps(summary, indent=2))
    else:
        click.echo(f"Final score: {final:.4f} after {len(history) - 1} round(s).")
