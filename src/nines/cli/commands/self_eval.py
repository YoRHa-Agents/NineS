"""``nines self-eval`` — run self-evaluation across all capability dimensions."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from nines.eval.metrics_registry import MetricRegistry, load_default_registry
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
from nines.iteration.context import EvaluationContext
from nines.iteration.eval_evaluators import (
    EvalCoverageEvaluator,
    PipelineLatencyEvaluator,
    ReportQualityEvaluator,
    SandboxIsolationEvaluator,
)
from nines.iteration.self_eval import (
    DimensionScore,
    DocstringCoverageEvaluator,
    LintCleanlinessEvaluator,
    LiveCodeCoverageEvaluator,
    LiveModuleCountEvaluator,
    LiveTestCountEvaluator,
    SelfEvalReport,
    SelfEvalRunner,
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

CAPABILITY_WEIGHT = 0.70
HYGIENE_WEIGHT = 0.30

_CAPABILITY_GROUPS: dict[str, list[str]] = {
    "V1 Evaluation": [
        "scoring_accuracy",
        "eval_coverage",
        "scoring_reliability",
        "report_quality",
        "scorer_agreement",
    ],
    "V2 Collection": [
        "source_coverage",
        "source_freshness",
        "change_detection",
        "data_completeness",
        "collection_throughput",
    ],
    "V3 Analysis": [
        "decomposition_coverage",
        "abstraction_quality",
        "code_review_accuracy",
        "index_recall",
        "structure_recognition",
    ],
    "System": [
        "pipeline_latency",
        "sandbox_isolation",
        "convergence_rate",
        "cross_vertex_synergy",
        "agent_analysis_quality",
    ],
}

_DIMENSION_LABELS: dict[str, str] = {
    "scoring_accuracy": "scoring_accuracy (D01)",
    "eval_coverage": "eval_coverage (D02)",
    "scoring_reliability": "scoring_reliability (D03)",
    "report_quality": "report_quality (D04)",
    "scorer_agreement": "scorer_agreement (D05)",
    "source_coverage": "source_coverage (D06)",
    "source_freshness": "source_freshness (D07)",
    "change_detection": "change_detection (D08)",
    "data_completeness": "data_completeness (D09)",
    "collection_throughput": "collection_throughput (D10)",
    "decomposition_coverage": "decomposition_coverage (D11)",
    "abstraction_quality": "abstraction_quality (D12)",
    "code_review_accuracy": "code_review_accuracy (D13)",
    "index_recall": "index_recall (D14)",
    "structure_recognition": "structure_recognition (D15)",
    "pipeline_latency": "pipeline_latency (D16)",
    "sandbox_isolation": "sandbox_isolation (D17)",
    "convergence_rate": "convergence_rate (D18)",
    "cross_vertex_synergy": "cross_vertex_synergy (D19)",
    "agent_analysis_quality": "agent_analysis_quality (D20)",
}

_ALL_CAPABILITY_DIMS = {name for names in _CAPABILITY_GROUPS.values() for name in names}

_HYGIENE_DIMS = [
    "code_coverage",
    "test_count",
    "module_count",
    "docstring_coverage",
    "lint_cleanliness",
]


def _mean_normalized(scores: list[DimensionScore]) -> float:
    if not scores:
        return 0.0
    return sum(s.normalized for s in scores) / len(scores)


def _format_text_report(
    report: SelfEvalReport,
    capability_scores: list[DimensionScore],
    hygiene_scores: list[DimensionScore],
) -> str:
    cap_mean = _mean_normalized(capability_scores)
    hyg_mean = _mean_normalized(hygiene_scores)
    overall = (
        CAPABILITY_WEIGHT * cap_mean + HYGIENE_WEIGHT * hyg_mean if hygiene_scores else cap_mean
    )

    lines = [
        f"Self-Evaluation Report (version={report.version or 'untagged'})",
        f"  Timestamp: {report.timestamp}",
    ]
    if hygiene_scores:
        lines.append(
            f"  Overall: {overall:.4f} "
            f"(capability: {cap_mean:.4f} \u00d7 {CAPABILITY_WEIGHT:.2f} "
            f"+ hygiene: {hyg_mean:.4f} \u00d7 {HYGIENE_WEIGHT:.2f})"
        )
    else:
        lines.append(f"  Overall: {overall:.4f} (capability only)")
    lines.append(f"  Duration: {report.duration:.3f}s")
    if report.timeouts:
        lines.append("  Timeouts (C04): " + ", ".join(report.timeouts))

    score_map = {s.name: s for s in capability_scores + hygiene_scores}

    pct_label = int(CAPABILITY_WEIGHT * 100)
    lines.append("")
    lines.append(f"  === Capability Dimensions ({pct_label}%) ===")
    for group_name, dim_names in _CAPABILITY_GROUPS.items():
        lines.append(f"  {group_name}:")
        for dim_name in dim_names:
            score = score_map.get(dim_name)
            if score is None:
                continue
            label = _DIMENSION_LABELS.get(dim_name, dim_name)
            lines.append(
                f"    {label}: {score.value:.3f} / {score.max_value:.3f} ({score.normalized:.1%})"
            )

    if hygiene_scores:
        hyg_pct = int(HYGIENE_WEIGHT * 100)
        lines.append("")
        lines.append(f"  === Code Hygiene ({hyg_pct}%) ===")
        for dim_name in _HYGIENE_DIMS:
            score = score_map.get(dim_name)
            if score is None:
                continue
            lines.append(
                f"    {dim_name}: {score.value:.3f} / {score.max_value:.3f} "
                f"({score.normalized:.1%})"
            )

    # C08: surface the weighted aggregate so operators can see the
    # registry-driven score alongside the legacy unweighted ``overall``.
    if report.weighted_overall or report.group_means:
        lines.append("")
        lines.append(
            f"  === Weighted (C08): {report.weighted_overall:.4f} ==="
        )
        for group, mean in sorted(report.group_means.items()):
            lines.append(f"    {group}: {mean:.4f}")

    return "\n".join(lines)


def _build_json_output(
    report: SelfEvalReport,
    capability_scores: list[DimensionScore],
    hygiene_scores: list[DimensionScore],
) -> str:
    """Emit JSON for ``nines self-eval --format json``.

    Forwards every field from :py:meth:`SelfEvalReport.to_dict` so any
    new attribute on the report (``timeouts`` from C04, future
    ``context_fingerprint`` from C01, ...) automatically propagates to
    operators without a per-field CLI patch (release follow-up N1).

    The CLI overlays its own weighted ``overall`` plus the capability/
    hygiene split since the runner emits an unweighted mean.
    """
    cap_mean = _mean_normalized(capability_scores)
    hyg_mean = _mean_normalized(hygiene_scores)
    overall = (
        CAPABILITY_WEIGHT * cap_mean + HYGIENE_WEIGHT * hyg_mean if hygiene_scores else cap_mean
    )

    # Forward every report field, then layer on CLI-specific computed
    # values.  ``report.to_dict()`` includes ``timeouts`` (C04) and any
    # future fields added to ``SelfEvalReport``.
    payload = report.to_dict()
    payload["overall"] = overall
    payload["capability_mean"] = cap_mean
    payload["hygiene_mean"] = hyg_mean
    payload["weights"] = {
        "capability": CAPABILITY_WEIGHT,
        "hygiene": HYGIENE_WEIGHT,
    }
    payload["capability_scores"] = [s.to_dict() for s in capability_scores]
    payload["hygiene_scores"] = [s.to_dict() for s in hygiene_scores]
    # Preserve the legacy flat ``scores`` list (existing callers may
    # depend on it); the report-derived payload already provides
    # ``scores`` but we re-set it to the cap+hyg ordering used above.
    payload["scores"] = [s.to_dict() for s in capability_scores + hygiene_scores]
    return json.dumps(payload, indent=2, default=str)


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
@click.option(
    "--project-root",
    type=click.Path(exists=True),
    default=".",
    help="Project root directory for coverage measurement.",
)
@click.option(
    "--src-dir",
    type=click.Path(exists=True),
    default="src/nines",
    help="Source directory for module/docstring/lint analysis.",
)
@click.option(
    "--test-dir",
    type=click.Path(exists=True),
    default="tests",
    help="Test directory for test discovery.",
)
@click.option(
    "--capability-only",
    is_flag=True,
    default=False,
    help="Run only capability evaluators, skip hygiene (faster iteration).",
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
    help="Golden test set directory for V1 scoring evaluators (D01/D03/D05).",
)
@click.option(
    "--metrics-config",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help=(
        "Path to a TOML file overriding the bundled C08 metric "
        "weights/thresholds (default: src/nines/data/self_eval_metrics.toml)."
    ),
)
@click.option(
    "--evaluator-timeout",
    type=float,
    default=60.0,
    show_default=True,
    help=(
        "Per-evaluator wall-clock budget in seconds (C04).  Evaluators "
        "that exceed this budget are recorded with status='timeout' "
        "in the report and the run continues."
    ),
)
@click.pass_context
def self_eval_cmd(
    ctx: click.Context,
    baseline_version: str,
    output_dir: str | None,
    project_root: str,
    src_dir: str,
    test_dir: str,
    capability_only: bool,
    samples_dir: str,
    golden_dir: str,
    metrics_config: str | None,
    evaluator_timeout: float,
) -> None:
    """Run self-evaluation across all capability dimensions."""
    verbose = ctx.obj.get("verbose", False)
    output_format = ctx.obj.get("format", "text")

    from nines.core.budget import TimeBudget

    # C04: bound every dimension to ``evaluator_timeout`` seconds so a
    # runaway evaluator can't hang the whole report.
    # C01 Phase 1: strict_ctx=True so the CLI refuses to silently fall
    # back to NineS's own src/nines for foreign-repo runs. Operators get
    # an immediate ConfigError if they forget to wire ``--src-dir``.
    # C08: build the MetricRegistry from --metrics-config (or the
    # bundled default) and validate up front so a misconfigured TOML
    # surfaces immediately rather than during run_all().  Validation
    # errors are reported via Click and abort the run with exit 2.
    if metrics_config:
        registry = MetricRegistry.from_toml(metrics_config)
    else:
        registry = load_default_registry()
    registry_errors = registry.validate()
    if registry_errors:
        for err in registry_errors:
            click.echo(f"metrics-config error: {err}", err=True)
        ctx.exit(2)

    runner = SelfEvalRunner(
        default_budget=TimeBudget(
            soft_seconds=min(20.0, max(1.0, evaluator_timeout / 2)),
            hard_seconds=max(1.0, float(evaluator_timeout)),
        ),
        strict_ctx=True,
        registry=registry,
    )

    # C01 Phase 1: build the EvaluationContext that gets threaded through
    # the runner so ctx-aware evaluators (D11/D14/D15) bind to *this*
    # project rather than NineS's own ``src/nines``.  Default ``src/nines``
    # is the NineS source — warn loudly so operators know foreign-repo
    # runs need an explicit ``--src-dir``.
    if src_dir == "src/nines":
        logger.warning("Using default NineS src_dir; ctx-aware dims will report NineS's own values")
    eval_ctx = EvaluationContext.from_cli(
        project_root=project_root,
        src_dir=src_dir,
        test_dir=test_dir,
        samples_dir=samples_dir,
        golden_dir=golden_dir,
    )

    runner.register_dimension(
        "scoring_accuracy",
        ScoringAccuracyEvaluator(golden_dir),
    )
    runner.register_dimension("eval_coverage", EvalCoverageEvaluator(samples_dir))
    runner.register_dimension(
        "scoring_reliability",
        ReliabilityEvaluator(golden_dir),
    )
    runner.register_dimension("report_quality", ReportQualityEvaluator())
    runner.register_dimension(
        "scorer_agreement",
        ScorerAgreementEvaluator(golden_dir),
    )

    runner.register_dimension("source_coverage", SourceCoverageEvaluator())
    runner.register_dimension("source_freshness", SourceFreshnessEvaluator())
    runner.register_dimension("change_detection", ChangeDetectionEvaluator())
    runner.register_dimension("data_completeness", DataCompletenessEvaluator())
    runner.register_dimension(
        "collection_throughput",
        CollectionThroughputEvaluator(),
    )

    runner.register_dimension(
        "decomposition_coverage",
        DecompositionCoverageEvaluator(src_dir),
    )
    runner.register_dimension(
        "abstraction_quality",
        AbstractionQualityEvaluator(src_dir),
    )
    runner.register_dimension(
        "code_review_accuracy",
        CodeReviewAccuracyEvaluator(src_dir),
    )
    runner.register_dimension("index_recall", IndexRecallEvaluator(src_dir))
    runner.register_dimension(
        "structure_recognition",
        StructureRecognitionEvaluator(src_dir),
    )
    runner.register_dimension("pipeline_latency", PipelineLatencyEvaluator())
    runner.register_dimension("sandbox_isolation", SandboxIsolationEvaluator())
    runner.register_dimension("convergence_rate", ConvergenceRateEvaluator(src_dir))
    runner.register_dimension("cross_vertex_synergy", CrossVertexSynergyEvaluator())
    runner.register_dimension("agent_analysis_quality", AgentAnalysisQualityEvaluator(src_dir))

    if not capability_only:
        runner.register_dimension(
            "code_coverage",
            LiveCodeCoverageEvaluator(project_root),
        )
        runner.register_dimension("test_count", LiveTestCountEvaluator(test_dir))
        runner.register_dimension("module_count", LiveModuleCountEvaluator(src_dir))
        runner.register_dimension(
            "docstring_coverage",
            DocstringCoverageEvaluator(src_dir),
        )
        runner.register_dimension(
            "lint_cleanliness",
            LintCleanlinessEvaluator(src_dir),
        )

    if verbose:
        click.echo("Running self-evaluation across all dimensions...")

    report = runner.run_all(version=baseline_version, ctx=eval_ctx)

    capability_scores = [s for s in report.scores if s.name in _ALL_CAPABILITY_DIMS]
    hygiene_scores = [s for s in report.scores if s.name in set(_HYGIENE_DIMS)]

    # Pass the SelfEvalReport object directly so renderers see every
    # field on it (notably ``timeouts`` from C04, plus any future
    # additions).  Release follow-up N1.
    if output_format == "json":
        output_text = _build_json_output(report, capability_scores, hygiene_scores)
    else:
        output_text = _format_text_report(
            report,
            capability_scores,
            hygiene_scores,
        )

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        ext = "json" if output_format == "json" else "txt"
        dest = out / f"self_eval_report.{ext}"
        dest.write_text(output_text, encoding="utf-8")
        click.echo(f"Report written to {dest}")
    else:
        click.echo(output_text)
