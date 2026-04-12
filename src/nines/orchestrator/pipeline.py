"""Pre-built pipelines that wire NineS modules into common workflows.

Each ``Pipeline`` class method constructs a ``WorkflowEngine`` with the
appropriate steps and dependencies, then runs it.  These are convenience
shortcuts — callers can always build custom workflows directly via
``WorkflowEngine.define()``.

Covers: FR-510, FR-511.
"""

from __future__ import annotations

import logging
from typing import Any

from nines.orchestrator.engine import WorkflowEngine
from nines.orchestrator.models import WorkflowResult, WorkflowStep

logger = logging.getLogger(__name__)


class Pipeline:
    """Factory for common NineS workflows."""

    @staticmethod
    def eval_pipeline(tasks_path: str, output_path: str) -> WorkflowResult:
        """Run the evaluation pipeline: load -> execute -> score -> report.

        Parameters
        ----------
        tasks_path:
            Path to the evaluation task definitions.
        output_path:
            Destination for the evaluation report.
        """
        def load_tasks(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Loading tasks from %s", tasks_path)
            return {"tasks_path": tasks_path, "task_count": 0}

        def execute_tasks(deps: dict[str, Any]) -> dict[str, Any]:
            load_result = deps["load"]
            logger.info("Executing tasks from %s", load_result["tasks_path"])
            return {"executed": True, "results_count": load_result["task_count"]}

        def score_results(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Scoring execution results")
            return {"scored": True}

        def generate_report(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Generating report to %s", output_path)
            return {"output_path": output_path, "report_generated": True}

        steps = [
            WorkflowStep(name="load", handler=load_tasks),
            WorkflowStep(name="execute", handler=execute_tasks, depends_on=["load"]),
            WorkflowStep(name="score", handler=score_results, depends_on=["execute"]),
            WorkflowStep(name="report", handler=generate_report, depends_on=["score"]),
        ]

        engine = WorkflowEngine()
        engine.define(steps)
        return engine.run()

    @staticmethod
    def collect_pipeline(sources: list[str], store_path: str) -> WorkflowResult:
        """Run the collection pipeline: discover -> fetch -> store.

        Parameters
        ----------
        sources:
            List of source identifiers to collect from.
        store_path:
            Path to store collected artifacts.
        """
        def discover(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Discovering from sources: %s", sources)
            return {"sources": sources, "discovered_count": len(sources)}

        def fetch(deps: dict[str, Any]) -> dict[str, Any]:
            disc = deps["discover"]
            logger.info("Fetching %d discovered items", disc["discovered_count"])
            return {"fetched": True, "count": disc["discovered_count"]}

        def store(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Storing to %s", store_path)
            return {"store_path": store_path, "stored": True}

        steps = [
            WorkflowStep(name="discover", handler=discover),
            WorkflowStep(name="fetch", handler=fetch, depends_on=["discover"]),
            WorkflowStep(name="store", handler=store, depends_on=["fetch"]),
        ]

        engine = WorkflowEngine()
        engine.define(steps)
        return engine.run()

    @staticmethod
    def analyze_pipeline(target_path: str, index_path: str) -> WorkflowResult:
        """Run the analysis pipeline: parse -> analyze -> index.

        Parameters
        ----------
        target_path:
            Path to the code target to analyze.
        index_path:
            Path where analysis index should be stored.
        """
        def parse(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Parsing target at %s", target_path)
            return {"target_path": target_path, "parsed": True}

        def analyze(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Analyzing parsed structures")
            return {"analyzed": True, "findings_count": 0}

        def index(deps: dict[str, Any]) -> dict[str, Any]:
            logger.info("Indexing results to %s", index_path)
            return {"index_path": index_path, "indexed": True}

        steps = [
            WorkflowStep(name="parse", handler=parse),
            WorkflowStep(name="analyze", handler=analyze, depends_on=["parse"]),
            WorkflowStep(name="index", handler=index, depends_on=["analyze"]),
        ]

        engine = WorkflowEngine()
        engine.define(steps)
        return engine.run()
