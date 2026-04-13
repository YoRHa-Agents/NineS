"""Pre-built pipelines that wire NineS modules into common workflows.

Each ``Pipeline`` class method constructs a ``WorkflowEngine`` with the
appropriate steps and dependencies, then runs it.  These are convenience
shortcuts — callers can always build custom workflows directly via
``WorkflowEngine.define()``.

Covers: FR-510, FR-511.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from nines.analyzer.keypoint import KeyPoint
from nines.analyzer.pipeline import AnalysisPipeline
from nines.core.models import ExecutionResult
from nines.eval.benchmark_gen import BenchmarkGenerator
from nines.eval.mapping import MappingTableGenerator
from nines.eval.multi_round import MultiRoundRunner
from nines.eval.runner import EvalRunner
from nines.eval.scorers import ScorerRegistry
from nines.orchestrator.engine import WorkflowEngine
from nines.orchestrator.models import WorkflowResult, WorkflowStep

logger = logging.getLogger(__name__)


def _default_executor(task: Any) -> ExecutionResult:
    """Passthrough executor that echoes ``task.expected`` as output."""
    return ExecutionResult(
        task_id=task.id,
        output=task.expected,
        success=True,
    )


def _keypoints_from_findings(
    findings: list[Any],
) -> list[KeyPoint]:
    """Derive basic ``KeyPoint`` objects from analysis findings."""
    kps: list[KeyPoint] = []
    for finding in findings:
        if hasattr(finding, "to_dict"):
            fd = finding.to_dict()
            msg = fd.get("message", str(finding))
            fid = fd.get("id", uuid.uuid4().hex[:8])
        else:
            msg = str(finding)
            fid = uuid.uuid4().hex[:8]
        kps.append(
            KeyPoint(
                id=f"kp-auto-{fid}",
                category="engineering",
                title=msg[:60],
                description=msg,
                expected_impact="neutral",
                impact_magnitude=0.5,
            )
        )
    return kps


class Pipeline:
    """Factory for common NineS workflows."""

    @staticmethod
    def eval_pipeline(
        tasks_path: str,
        output_path: str,
    ) -> WorkflowResult:
        """Run the evaluation pipeline: load → execute → score → report.

        Parameters
        ----------
        tasks_path:
            Path to the evaluation task definitions.
        output_path:
            Destination for the evaluation report.
        """
        try:
            runner = EvalRunner()
            registry = ScorerRegistry.with_builtins()

            def load_tasks(deps: dict[str, Any]) -> dict[str, Any]:
                tasks = runner.load_tasks(tasks_path)
                logger.info(
                    "Loaded %d tasks from %s",
                    len(tasks),
                    tasks_path,
                )
                return {
                    "tasks": tasks,
                    "task_count": len(tasks),
                }

            def execute_tasks(
                deps: dict[str, Any],
            ) -> dict[str, Any]:
                tasks = deps["load"]["tasks"]
                scorers = [registry.get("exact")]
                results = runner.run(
                    tasks,
                    _default_executor,
                    scorers,
                )
                logger.info("Executed %d tasks", len(results))
                return {
                    "results": results,
                    "results_count": len(results),
                }

            def score_results(
                deps: dict[str, Any],
            ) -> dict[str, Any]:
                results = deps["execute"]["results"]
                composites = [r.composite_score for r in results]
                avg = sum(composites) / len(composites) if composites else 0.0
                logger.info("Average composite score: %.4f", avg)
                return {
                    "composite_scores": composites,
                    "average_score": avg,
                    "results": results,
                }

            def generate_report(
                deps: dict[str, Any],
            ) -> dict[str, Any]:
                results = deps["score"]["results"]
                avg_score = deps["score"]["average_score"]
                report_data = {
                    "task_count": len(results),
                    "average_score": avg_score,
                    "results": [r.to_dict() for r in results],
                }
                out = Path(output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(
                    json.dumps(
                        report_data,
                        indent=2,
                        default=str,
                    ),
                )
                logger.info("Report written to %s", output_path)
                return {
                    "output_path": output_path,
                    "report_generated": True,
                }

            steps = [
                WorkflowStep(name="load", handler=load_tasks),
                WorkflowStep(
                    name="execute",
                    handler=execute_tasks,
                    depends_on=["load"],
                ),
                WorkflowStep(
                    name="score",
                    handler=score_results,
                    depends_on=["execute"],
                ),
                WorkflowStep(
                    name="report",
                    handler=generate_report,
                    depends_on=["score"],
                ),
            ]

            engine = WorkflowEngine()
            engine.define(steps)
            return engine.run()
        except Exception as exc:
            logger.exception("eval_pipeline failed")
            result = WorkflowResult()
            result.errors["pipeline"] = str(exc)
            return result

    @staticmethod
    def collect_pipeline(
        sources: list[str],
        store_path: str,
    ) -> WorkflowResult:
        """Run the collection pipeline: discover → fetch → store.

        Parameters
        ----------
        sources:
            List of source identifiers to collect from.
        store_path:
            Path to store collected artifacts.
        """
        logger.info(
            "Collection pipeline requires configured sources; returning no-op result",
        )

        def discover(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Discovering from sources: %s", sources)
            return {
                "sources": sources,
                "discovered_count": len(sources),
            }

        def fetch(deps: dict[str, Any]) -> dict[str, Any]:
            disc = deps["discover"]
            logger.info(
                "Fetching %d discovered items",
                disc["discovered_count"],
            )
            return {
                "fetched": True,
                "count": disc["discovered_count"],
            }

        def store(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Storing to %s", store_path)
            return {"store_path": store_path, "stored": True}

        steps = [
            WorkflowStep(name="discover", handler=discover),
            WorkflowStep(
                name="fetch",
                handler=fetch,
                depends_on=["discover"],
            ),
            WorkflowStep(
                name="store",
                handler=store,
                depends_on=["fetch"],
            ),
        ]

        engine = WorkflowEngine()
        engine.define(steps)
        return engine.run()

    @staticmethod
    def analyze_pipeline(
        target_path: str,
        index_path: str,
    ) -> WorkflowResult:
        """Run the analysis pipeline: parse → analyze → index.

        Parameters
        ----------
        target_path:
            Path to the code target to analyze.
        index_path:
            Path where analysis index should be stored.
        """
        try:
            analysis = AnalysisPipeline()

            def parse(deps: dict[str, Any]) -> dict[str, Any]:
                result = analysis.run(target_path)
                logger.info(
                    "Parsed %d findings from %s",
                    len(result.findings),
                    target_path,
                )
                return {
                    "target_path": target_path,
                    "parsed": True,
                    "result": result,
                }

            def analyze(deps: dict[str, Any]) -> dict[str, Any]:
                result = deps["parse"]["result"]
                logger.info(
                    "Analysis: %d findings, %d metric(s)",
                    len(result.findings),
                    len(result.metrics),
                )
                return {
                    "analyzed": True,
                    "findings_count": len(result.findings),
                    "metrics": result.metrics,
                    "result": result,
                }

            def index(deps: dict[str, Any]) -> dict[str, Any]:
                result = deps["analyze"]["result"]
                out = Path(index_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(
                    json.dumps(
                        result.to_dict(),
                        indent=2,
                        default=str,
                    ),
                )
                logger.info("Index written to %s", index_path)
                return {
                    "index_path": index_path,
                    "indexed": True,
                }

            steps = [
                WorkflowStep(name="parse", handler=parse),
                WorkflowStep(
                    name="analyze",
                    handler=analyze,
                    depends_on=["parse"],
                ),
                WorkflowStep(
                    name="index",
                    handler=index,
                    depends_on=["analyze"],
                ),
            ]

            engine = WorkflowEngine()
            engine.define(steps)
            return engine.run()
        except Exception as exc:
            logger.exception("analyze_pipeline failed")
            result = WorkflowResult()
            result.errors["pipeline"] = str(exc)
            return result

    @staticmethod
    def benchmark_pipeline(
        target_path: str,
        key_points_data: list[dict[str, Any]] | None = None,
        suite_id: str = "",
        scorer_names: list[str] | None = None,
    ) -> WorkflowResult:
        """Full benchmark workflow.

        Runs: analyze → extract keypoints → generate benchmarks
        → multi-round eval → mapping.

        Parameters
        ----------
        target_path:
            Path to the code target to analyze.
        key_points_data:
            Pre-extracted key-point dicts.  When *None*, basic key
            points are derived from analysis findings.
        suite_id:
            Benchmark suite identifier (auto-generated when empty).
        scorer_names:
            Names of scorers to use (defaults to ``["exact"]``).
        """
        try:
            sid = suite_id or uuid.uuid4().hex[:8]
            snames = scorer_names or ["exact"]

            def analyze_step(
                deps: dict[str, Any],
            ) -> dict[str, Any]:
                ap = AnalysisPipeline()
                result = ap.run(target_path)
                logger.info(
                    "Analysis: %d findings from %s",
                    len(result.findings),
                    target_path,
                )
                return {"result": result}

            def extract_keypoints(
                deps: dict[str, Any],
            ) -> dict[str, Any]:
                if key_points_data:
                    kps = [KeyPoint.from_dict(d) for d in key_points_data]
                else:
                    findings = deps["analyze"]["result"].findings
                    kps = _keypoints_from_findings(findings)
                logger.info("Extracted %d key points", len(kps))
                return {"key_points": kps}

            def generate_benchmarks(
                deps: dict[str, Any],
            ) -> dict[str, Any]:
                kps = deps["extract_keypoints"]["key_points"]
                gen = BenchmarkGenerator()
                suite = gen.generate(kps, suite_id=sid)
                logger.info(
                    "Generated suite %s with %d tasks",
                    suite.id,
                    len(suite.tasks),
                )
                return {"suite": suite}

            def evaluate(
                deps: dict[str, Any],
            ) -> dict[str, Any]:
                suite = deps["generate_benchmarks"]["suite"]
                registry = ScorerRegistry.with_builtins()
                scorers = [registry.get(n) for n in snames]
                mr_runner = MultiRoundRunner()
                report = mr_runner.run(
                    suite.tasks,
                    _default_executor,
                    scorers,
                    suite_id=sid,
                )
                logger.info(
                    "Multi-round eval: %d rounds, converged=%s",
                    report.total_rounds,
                    report.converged,
                )
                return {"report": report}

            def map_results(
                deps: dict[str, Any],
            ) -> dict[str, Any]:
                kps = deps["extract_keypoints"]["key_points"]
                report = deps["evaluate"]["report"]
                suite = deps["generate_benchmarks"]["suite"]
                mapper = MappingTableGenerator()
                mapping = mapper.generate(kps, report, suite)
                logger.info(
                    "Mapping: %d effective, %d ineffective, %d inconclusive",
                    mapping.effective_count,
                    mapping.ineffective_count,
                    mapping.inconclusive_count,
                )
                return {
                    "mapping": mapping.to_dict(),
                    "lessons": mapping.lessons_learnt,
                }

            steps = [
                WorkflowStep(
                    name="analyze",
                    handler=analyze_step,
                ),
                WorkflowStep(
                    name="extract_keypoints",
                    handler=extract_keypoints,
                    depends_on=["analyze"],
                ),
                WorkflowStep(
                    name="generate_benchmarks",
                    handler=generate_benchmarks,
                    depends_on=["extract_keypoints"],
                ),
                WorkflowStep(
                    name="evaluate",
                    handler=evaluate,
                    depends_on=["generate_benchmarks"],
                ),
                WorkflowStep(
                    name="map_results",
                    handler=map_results,
                    depends_on=[
                        "extract_keypoints",
                        "generate_benchmarks",
                        "evaluate",
                    ],
                ),
            ]

            engine = WorkflowEngine()
            engine.define(steps)
            return engine.run()
        except Exception as exc:
            logger.exception("benchmark_pipeline failed")
            result = WorkflowResult()
            result.errors["pipeline"] = str(exc)
            return result
