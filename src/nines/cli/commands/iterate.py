"""``nines iterate`` — execute a self-improvement iteration cycle."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from nines.iteration.capability_evaluators import (
    AbstractionQualityEvaluator,
    AgentAnalysisQualityEvaluator,
    CodeReviewAccuracyEvaluator,
    DecompositionCoverageEvaluator,
    IndexRecallEvaluator,
    StructureRecognitionEvaluator,
)
from nines.iteration.collection_evaluators import (
    ChangeDetectionEvaluator,
    CollectionThroughputEvaluator,
    DataCompletenessEvaluator,
    SourceCoverageEvaluator,
    SourceFreshnessEvaluator,
)
from nines.iteration.convergence import ConvergenceChecker
from nines.iteration.eval_evaluators import (
    EvalCoverageEvaluator,
    PipelineLatencyEvaluator,
    ReportQualityEvaluator,
    SandboxIsolationEvaluator,
)
from nines.iteration.gap_detector import GapDetector
from nines.iteration.graph_evaluators import (
    GraphDecompositionCoverageEvaluator,
    GraphVerificationPassRateEvaluator,
    LayerAssignmentQualityEvaluator,
    SummaryCompletenessEvaluator,
)
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
from nines.iteration.system_evaluators import (
    ConvergenceRateEvaluator,
    CrossVertexSynergyEvaluator,
)
from nines.iteration.v1_evaluators import (
    ReliabilityEvaluator,
    ScorerAgreementEvaluator,
    ScoringAccuracyEvaluator,
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


def _register_capability_dims(
    runner: SelfEvalRunner,
    src_dir: str,
    samples_dir: str,
    golden_dir: str,
    project_root: str = ".",
) -> None:
    """Register all D01-D24 capability dimensions."""
    runner.register_dimension("scoring_accuracy", ScoringAccuracyEvaluator(golden_dir))
    runner.register_dimension("eval_coverage", EvalCoverageEvaluator(samples_dir))
    runner.register_dimension("scoring_reliability", ReliabilityEvaluator(golden_dir))
    runner.register_dimension("report_quality", ReportQualityEvaluator())
    runner.register_dimension("scorer_agreement", ScorerAgreementEvaluator(golden_dir))
    runner.register_dimension("source_coverage", SourceCoverageEvaluator())
    runner.register_dimension("source_freshness", SourceFreshnessEvaluator())
    runner.register_dimension("change_detection", ChangeDetectionEvaluator())
    runner.register_dimension("data_completeness", DataCompletenessEvaluator())
    runner.register_dimension("collection_throughput", CollectionThroughputEvaluator())
    runner.register_dimension("decomposition_coverage", DecompositionCoverageEvaluator(src_dir))
    runner.register_dimension("abstraction_quality", AbstractionQualityEvaluator(src_dir))
    runner.register_dimension("code_review_accuracy", CodeReviewAccuracyEvaluator(src_dir))
    runner.register_dimension("index_recall", IndexRecallEvaluator(src_dir))
    runner.register_dimension("structure_recognition", StructureRecognitionEvaluator(src_dir))
    runner.register_dimension("pipeline_latency", PipelineLatencyEvaluator())
    runner.register_dimension("sandbox_isolation", SandboxIsolationEvaluator())
    runner.register_dimension("convergence_rate", ConvergenceRateEvaluator(src_dir))
    runner.register_dimension("cross_vertex_synergy", CrossVertexSynergyEvaluator())
    runner.register_dimension("agent_analysis_quality", AgentAnalysisQualityEvaluator(src_dir))
    runner.register_dimension(
        "graph_decomposition_coverage",
        GraphDecompositionCoverageEvaluator(project_root),
    )
    runner.register_dimension(
        "graph_verification_pass_rate",
        GraphVerificationPassRateEvaluator(project_root),
    )
    runner.register_dimension(
        "layer_assignment_quality",
        LayerAssignmentQualityEvaluator(project_root),
    )
    runner.register_dimension(
        "summary_completeness",
        SummaryCompletenessEvaluator(project_root),
    )


def _build_live_evaluators(
    project_root: Path,
    src_dir: str | None,
    test_dir: str | None,
    samples_dir: str = "samples/eval",
    golden_dir: str = "data/golden_test_set",
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

    _register_capability_dims(runner, resolved_src, samples_dir, golden_dir, str(project_root))

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
@click.option(
    "--samples-dir",
    type=click.Path(),
    default="samples/eval",
    help="Sample eval directory for EvalCoverageEvaluator.",
)
@click.option(
    "--golden-dir",
    type=click.Path(),
    default="data/golden_test_set",
    help="Golden test set directory for V1 scoring evaluators.",
)
@click.pass_context
def iterate_cmd(
    ctx: click.Context,
    max_rounds: int,
    threshold: float,
    project_root: str | None,
    src_dir: str | None,
    test_dir: str | None,
    samples_dir: str,
    golden_dir: str,
) -> None:
    """Execute a self-improvement iteration cycle."""
    verbose = ctx.obj.get("verbose", False)
    output_format = ctx.obj.get("format", "text")

    if project_root is not None:
        root = Path(project_root).resolve()
        runner = _build_live_evaluators(root, src_dir, test_dir, samples_dir, golden_dir)
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
