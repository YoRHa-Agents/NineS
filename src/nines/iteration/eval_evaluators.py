"""V1 Evaluation and System-wide dimension evaluators.

Implements four live evaluators for the self-eval framework:
- **EvalCoverageEvaluator** (D02) — validates sample eval task coverage
- **ReportQualityEvaluator** (D04) — checks report generation quality
- **PipelineLatencyEvaluator** (D16) — measures analysis pipeline latency
- **SandboxIsolationEvaluator** (D17) — verifies sandbox isolation

Each evaluator conforms to the ``DimensionEvaluator`` protocol defined in
:mod:`nines.iteration.self_eval` and returns a ``DimensionScore``.

Covers: FR-602, FR-603.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from nines.iteration.self_eval import DimensionScore

if TYPE_CHECKING:
    from nines.iteration.context import EvaluationContext

logger = logging.getLogger(__name__)

__all__ = [
    "EvalCoverageEvaluator",
    "ReportQualityEvaluator",
    "PipelineLatencyEvaluator",
    "SandboxIsolationEvaluator",
]


class EvalCoverageEvaluator:
    """Evaluate task-file coverage in the sample eval directory (D02).

    Loads every ``.toml`` file from the sample directory and checks
    that each one can be parsed into a valid ``TaskDefinition`` with
    the required fields (id, name, input, expected).

    Score = loadable_valid_tasks / total_toml_files  (max 1.0).

    C01 Phase 2: project-aware via ``ctx.samples_dir``. When the runner
    supplies a context with a non-None ``samples_dir``, that path
    overrides the constructor default — so foreign-repo runs no longer
    silently load NineS's own ``samples/eval`` (closes baseline §4.8
    silent-fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, sample_dir: str | Path = "samples/eval") -> None:
        """Initialize with the sample eval directory path."""
        self._sample_dir = Path(sample_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Load and validate TOML task files, returning coverage score.

        Parameters
        ----------
        ctx:
            Project context. When supplied with a non-None ``samples_dir``,
            that path overrides the constructor default so foreign-repo
            runs evaluate the project's own sample TOMLs (or report
            an empty fixture) instead of NineS's own.
        """
        from nines.eval.models import TaskDefinition

        sample_dir = (
            ctx.samples_dir if ctx is not None and ctx.samples_dir is not None
            else self._sample_dir
        )
        toml_files = sorted(sample_dir.glob("*.toml"))
        total = len(toml_files)

        if total == 0:
            return DimensionScore(
                name="eval_coverage",
                value=0.0,
                max_value=1.0,
                metadata={
                    "total_files": 0,
                    "error": "no TOML files found",
                    "sample_dir": str(sample_dir),
                },
            )

        valid = 0
        details: dict[str, Any] = {}

        for toml_path in toml_files:
            fname = toml_path.name
            try:
                task = TaskDefinition.from_toml(toml_path)
                missing: list[str] = []
                if not task.id:
                    missing.append("id")
                if not task.name:
                    missing.append("name")
                if not task.input_config:
                    missing.append("input")
                if task.expected is None:
                    missing.append("expected")

                if missing:
                    details[fname] = {"status": "invalid", "missing": missing}
                else:
                    details[fname] = {"status": "valid"}
                    valid += 1
            except Exception as exc:
                logger.warning("Failed to load %s: %s", toml_path, exc)
                details[fname] = {"status": "error", "error": str(exc)}

        score = valid / total
        return DimensionScore(
            name="eval_coverage",
            value=score,
            max_value=1.0,
            metadata={
                "total_files": total,
                "valid_tasks": valid,
                "details": details,
            },
        )


class ReportQualityEvaluator:
    """Evaluate quality of generated eval reports (D04).

    Creates a synthetic ``EvalResult``, passes it through
    ``MarkdownReporter`` and ``JSONReporter``, and checks that the
    generated output contains required sections/fields.

    Markdown checks: summary section, results table, score column.
    JSON checks: valid JSON, ``"summary"`` key, ``"results"`` key.

    Score = passed_checks / total_checks  (max 1.0).

    NineS-meta evaluator (C01 Phase 2 design note)
    ----------------------------------------------
    This evaluator validates NineS's own reporter implementations using
    a synthetic ``EvalResult`` fixture. It is intentionally project-
    independent — the same NineS reporters produce the same output
    regardless of which project the self-eval is targeting. Therefore
    it does **not** declare ``requires_context = True`` and does not
    accept a ``ctx`` keyword.
    """

    def evaluate(self) -> DimensionScore:
        """Generate reports from synthetic data and validate structure."""
        from nines.core.models import Score
        from nines.eval.models import EvalResult
        from nines.eval.reporters import JSONReporter, MarkdownReporter

        synthetic_result = EvalResult(
            task_id="synth-001",
            task_name="synthetic-task",
            output="Hello, World!",
            scores=[Score(value=0.9, scorer_name="exact", max_value=1.0)],
            composite_score=0.9,
            duration_ms=42.0,
            token_count=10,
            success=True,
        )
        results = [synthetic_result]

        checks: dict[str, bool] = {}
        total_checks = 6

        try:
            md_text = MarkdownReporter().generate(results)
            checks["md_generates"] = True
            checks["md_has_summary"] = "## Summary" in md_text
            checks["md_has_results"] = "## Results" in md_text
            checks["md_has_scores"] = "Score" in md_text
        except Exception as exc:
            logger.error("MarkdownReporter failed: %s", exc)
            checks["md_generates"] = False
            checks["md_has_summary"] = False
            checks["md_has_results"] = False
            checks["md_has_scores"] = False

        try:
            json_text = JSONReporter().generate(results)
            checks["json_valid"] = False
            try:
                parsed = json.loads(json_text)
                checks["json_valid"] = True
                checks["json_has_required_keys"] = "summary" in parsed and "results" in parsed
            except json.JSONDecodeError:
                checks["json_has_required_keys"] = False
        except Exception as exc:
            logger.error("JSONReporter failed: %s", exc)
            checks["json_valid"] = False
            checks["json_has_required_keys"] = False

        passed = sum(1 for v in checks.values() if v)
        score = passed / total_checks if total_checks > 0 else 0.0
        return DimensionScore(
            name="report_quality",
            value=score,
            max_value=1.0,
            metadata={"checks": checks, "passed": passed, "total": total_checks},
        )


class PipelineLatencyEvaluator:
    """Evaluate analysis pipeline latency on a small target (D16).

    Runs ``AnalysisPipeline.run`` on a single Python file and measures
    wall-clock time.  Faster execution yields a higher score.

    Score = 1.0 - min(elapsed_seconds, 30) / 30  (max 1.0).

    C01 Phase 2: project-aware. When the runner supplies an
    ``EvaluationContext``, the target file is derived from the
    project tree rather than the hard-coded ``src/nines/__init__.py``
    constructor default (closes baseline §4.8 silent-fallback bug —
    today every foreign-repo run silently times the NineS pipeline
    against NineS's own ``__init__.py``).

    Resolution order for the target file (when ``ctx`` is supplied):

    1. ``ctx.src_dir / "__init__.py"`` if it exists (typical Python pkg).
    2. The first ``*.py`` file under ``ctx.src_dir`` (rglob, sorted).
    3. Constructor-time ``target`` as a final fallback.
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, target: str | Path = "src/nines/__init__.py") -> None:
        """Initialize with the target file to analyze."""
        self._target = Path(target)

    def _resolve_target(self, ctx: EvaluationContext | None) -> Path:
        """Pick the most appropriate target file given the project ctx.

        See class docstring for the resolution order. When ``ctx`` is
        supplied but contains no ``*.py`` files, returns ``ctx.src_dir``
        itself (a directory) so the caller's ``target.exists()`` check
        passes and the metadata clearly identifies the empty project
        — never silently re-targets the constructor-time NineS default.
        """
        if ctx is None:
            return self._target

        src_dir = ctx.src_dir
        # Prefer the package's ``__init__.py`` for an apples-to-apples
        # latency comparison (small file, exercises the import path).
        init_candidate = src_dir / "__init__.py"
        if init_candidate.is_file():
            return init_candidate

        # Otherwise pick the first *.py under src_dir (deterministic via sort).
        for fpath in sorted(src_dir.rglob("*.py")):
            if "__pycache__" not in fpath.parts:
                return fpath

        # No *.py at all under ctx.src_dir — return src_dir itself so the
        # downstream metadata identifies this project (rather than silently
        # re-targeting the constructor's NineS default).  The pipeline
        # accepts a directory target and will report 0 files_analyzed,
        # which is the correct project-aware answer.
        return src_dir

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Run the pipeline and return a latency-based score.

        Parameters
        ----------
        ctx:
            Project context. When supplied, the target file is derived
            from ``ctx.src_dir`` (see :meth:`_resolve_target`). When
            ``None``, the constructor-time ``target`` is used (legacy
            path).
        """
        from nines.analyzer.pipeline import AnalysisPipeline

        target = self._resolve_target(ctx)
        if not target.exists():
            logger.error("Pipeline target does not exist: %s", target)
            return DimensionScore(
                name="pipeline_latency",
                value=0.0,
                max_value=1.0,
                metadata={
                    "error": f"target not found: {target}",
                    "target": str(target),
                },
            )

        try:
            pipeline = AnalysisPipeline()
            start = time.monotonic()
            result = pipeline.run(target)
            elapsed = time.monotonic() - start
        except Exception as exc:
            logger.error("Pipeline run failed: %s", exc)
            return DimensionScore(
                name="pipeline_latency",
                value=0.0,
                max_value=1.0,
                metadata={"error": str(exc), "target": str(target)},
            )

        clamped = min(elapsed, 30.0)
        score = 1.0 - clamped / 30.0

        return DimensionScore(
            name="pipeline_latency",
            value=round(score, 4),
            max_value=1.0,
            metadata={
                "elapsed_seconds": round(elapsed, 3),
                "files_analyzed": result.metrics.get("files_analyzed", 0),
                "finding_count": len(result.findings),
                "target": str(target),
            },
        )


class SandboxIsolationEvaluator:
    """Evaluate sandbox creation, execution, and cleanup (D17).

    Creates a sandbox via ``SandboxManager``, runs a trivial Python
    command, verifies the output, then tears down and checks that the
    sandbox workspace is cleaned up properly.

    Score = 1.0 if execution succeeds and cleanup is clean,
            0.5 if sandbox creation fails (e.g. venv issues),
            0.0 if execution or cleanup is polluted/broken.

    NineS-meta evaluator (C01 Phase 2 design note)
    ----------------------------------------------
    This evaluator validates NineS's own ``SandboxManager`` lifecycle.
    The exercised behaviour is independent of which project the
    self-eval targets, so it deliberately does **not** declare
    ``requires_context = True``.
    """

    def evaluate(self) -> DimensionScore:
        """Create, run, and tear down a sandbox; return isolation score."""
        from nines.sandbox.manager import SandboxConfig, SandboxManager

        manager: SandboxManager | None = None
        try:
            manager = SandboxManager()
        except Exception as exc:
            logger.error("SandboxManager creation failed: %s", exc)
            return DimensionScore(
                name="sandbox_isolation",
                value=0.5,
                max_value=1.0,
                metadata={"error": f"manager creation failed: {exc}"},
            )

        ctx = None
        try:
            ctx = manager.create(SandboxConfig(timeout_seconds=15))
        except Exception as exc:
            logger.error("Sandbox creation failed: %s", exc)
            return DimensionScore(
                name="sandbox_isolation",
                value=0.5,
                max_value=1.0,
                metadata={"error": f"sandbox creation failed: {exc}"},
            )

        checks: dict[str, bool] = {}
        try:
            run_result = manager.run_in_sandbox(
                ctx,
                [str(ctx.python_path), "-c", "print('hello')"],
            )
            checks["executed"] = run_result.exit_code == 0
            checks["correct_output"] = run_result.stdout.strip() == "hello"
            checks["no_timeout"] = not run_result.timed_out
        except Exception as exc:
            logger.error("Sandbox execution failed: %s", exc)
            checks["executed"] = False
            checks["correct_output"] = False
            checks["no_timeout"] = False

        work_dir = ctx.work_dir
        try:
            manager.destroy(ctx)
            checks["cleanup_ok"] = not work_dir.exists()
        except Exception as exc:
            logger.error("Sandbox cleanup failed: %s", exc)
            checks["cleanup_ok"] = False

        with contextlib.suppress(Exception):
            manager.destroy_all()

        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        score = passed / total if total > 0 else 0.0

        return DimensionScore(
            name="sandbox_isolation",
            value=round(score, 4),
            max_value=1.0,
            metadata={"checks": checks, "passed": passed, "total": total},
        )
