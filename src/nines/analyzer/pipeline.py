"""Analysis pipeline orchestrator.

Chains ingest → analyze → decompose into an end-to-end flow that
produces an :class:`~nines.core.models.AnalysisResult`.

Optionally integrates :class:`AgentImpactAnalyzer` and
:class:`KeyPointExtractor` when the corresponding flags are enabled.

Covers: FR-310, FR-311, FR-313, FR-314.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from nines.analyzer.agent_impact import AgentImpactAnalyzer
from nines.analyzer.decomposer import Decomposer
from nines.analyzer.keypoint import KeyPointExtractor
from nines.analyzer.reviewer import CodeReviewer, FileReview
from nines.analyzer.structure import StructureAnalyzer, StructureReport
from nines.core.errors import AnalyzerError
from nines.core.models import AnalysisResult, Finding, KnowledgeUnit

logger = logging.getLogger(__name__)

_AGENT_EXTENSIONS = frozenset(
    {
        ".py",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".md",
        ".txt",
        ".cfg",
        ".ini",
        ".rules",
    }
)

_SKIP_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        ".eggs",
    }
)


class AnalysisPipeline:
    """Orchestrates the analysis flow: ingest → analyze → decompose.

    Parameters
    ----------
    reviewer:
        Code reviewer instance (defaults to a new :class:`CodeReviewer`).
    structure_analyzer:
        Structure analyzer instance (defaults to a new :class:`StructureAnalyzer`).
    decomposer:
        Decomposer instance (defaults to a new :class:`Decomposer`).
    agent_impact_analyzer:
        Optional :class:`AgentImpactAnalyzer` for AI-agent impact analysis.
    keypoint_extractor:
        Optional :class:`KeyPointExtractor` for key-point extraction.
    """

    def __init__(
        self,
        reviewer: CodeReviewer | None = None,
        structure_analyzer: StructureAnalyzer | None = None,
        decomposer: Decomposer | None = None,
        agent_impact_analyzer: AgentImpactAnalyzer | None = None,
        keypoint_extractor: KeyPointExtractor | None = None,
    ) -> None:
        """Initialize analysis pipeline."""
        self._reviewer = reviewer or CodeReviewer()
        self._structure = structure_analyzer or StructureAnalyzer()
        self._decomposer = decomposer or Decomposer()
        self._agent_impact = agent_impact_analyzer
        self._keypoint = keypoint_extractor

    def run(
        self,
        path: str | Path,
        *,
        agent_impact: bool = True,
        keypoints: bool = True,
        strategy: str = "functional",
        depth: str = "shallow",
    ) -> AnalysisResult:
        """Execute the full pipeline on *path*.

        If *path* is a file, only that file is reviewed and decomposed.
        If *path* is a directory, all relevant files are ingested for
        agent-impact analysis and Python files are used for code review
        and decomposition.

        Agent-impact analysis is enabled by default since it is the core
        mission of NineS.  Pass ``agent_impact=False`` for a legacy
        code-structure-only run.

        Parameters
        ----------
        path:
            Target file or directory.
        agent_impact:
            When ``True`` (the default), run :class:`AgentImpactAnalyzer`
            and merge results into :attr:`AnalysisResult.metrics` under
            the ``"agent_impact"`` key.  Set to ``False`` for a fast,
            code-structure-only analysis.
        keypoints:
            When ``True`` (the default; implies *agent_impact*),
            additionally run :class:`KeyPointExtractor` and store results
            under the ``"key_points"`` metrics key.
        """
        if not agent_impact:
            keypoints = False
        if keypoints:
            agent_impact = True

        start = time.monotonic()
        target = Path(path)

        py_files = self.ingest(target)
        reviews = self.analyze(py_files)
        structure: StructureReport | None = None
        if target.is_dir():
            try:
                structure = self._structure.analyze_directory(target)
            except AnalyzerError:
                logger.warning(
                    "Structure analysis failed for %s",
                    target,
                    exc_info=True,
                )

        units = self.decompose(reviews, structure, strategy=strategy)

        all_findings: list[Finding] = []
        for review in reviews:
            all_findings.extend(review.findings)

        elapsed_ms = (time.monotonic() - start) * 1000

        metrics = self._build_metrics(reviews, units, structure, elapsed_ms)
        metrics["strategy"] = strategy
        metrics["depth"] = depth

        if agent_impact:
            all_files = self.ingest_all(target)
            metrics["total_files_scanned"] = len(all_files)

            analyzer = self._agent_impact or AgentImpactAnalyzer()
            impact_report = analyzer.analyze(target)
            metrics["agent_impact"] = impact_report.to_dict()
            all_findings.extend(impact_report.findings)

            if keypoints:
                result_so_far = AnalysisResult(
                    target=str(target),
                    findings=list(all_findings),
                    metrics=dict(metrics),
                )
                extractor = self._keypoint or KeyPointExtractor()
                kp_report = extractor.extract(impact_report, result_so_far)
                metrics["key_points"] = kp_report.to_dict()

        return AnalysisResult(
            target=str(target),
            findings=all_findings,
            metrics=metrics,
        )

    def ingest(self, target: Path) -> list[Path]:
        """Discover Python files at *target*.

        Skips hidden directories and common non-source directories.
        """
        if target.is_file():
            if target.suffix == ".py":
                return [target]
            raise AnalyzerError(
                f"Not a Python file: {target}",
                details={"path": str(target)},
            )

        if not target.is_dir():
            raise AnalyzerError(
                f"Path does not exist: {target}",
                details={"path": str(target)},
            )

        files: list[Path] = []
        for fpath in sorted(target.rglob("*.py")):
            if any(p in _SKIP_DIRS or p.startswith(".") for p in fpath.relative_to(target).parts):
                continue
            files.append(fpath)

        logger.info("Ingested %d Python files from %s", len(files), target)
        return files

    def ingest_all(self, target: Path) -> list[Path]:
        """Discover all agent-relevant files at *target* for impact analysis.

        Scans for files matching :data:`_AGENT_EXTENSIONS` while skipping
        the same directories as :meth:`ingest`.
        """
        if target.is_file():
            if target.suffix in _AGENT_EXTENSIONS:
                return [target]
            return []

        if not target.is_dir():
            return []

        files: list[Path] = []
        for fpath in sorted(target.rglob("*")):
            if not fpath.is_file():
                continue
            if fpath.suffix not in _AGENT_EXTENSIONS:
                continue
            if any(
                p in _SKIP_DIRS or p.startswith(".")
                for p in fpath.relative_to(target).parts
            ):
                continue
            files.append(fpath)

        logger.info("Ingested %d agent-relevant files from %s", len(files), target)
        return files

    def analyze(self, py_files: list[Path]) -> list[FileReview]:
        """Run the code reviewer on each file, isolating per-file errors."""
        reviews: list[FileReview] = []
        for fpath in py_files:
            try:
                review = self._reviewer.review_file(fpath)
                reviews.append(review)
            except AnalyzerError:
                logger.warning("Review failed for %s", fpath, exc_info=True)
        return reviews

    def decompose(
        self,
        reviews: list[FileReview],
        structure: StructureReport | None = None,
        *,
        strategy: str = "functional",
    ) -> list[KnowledgeUnit]:
        """Run decomposition on all reviews using the given *strategy*."""
        if strategy == "concern":
            return self._decomposer.concern_decompose(reviews)
        if strategy == "layer":
            return self._decomposer.layer_decompose(reviews, structure)
        return self._decomposer.functional_decompose(reviews)

    @staticmethod
    def _build_metrics(
        reviews: list[FileReview],
        units: list[KnowledgeUnit],
        structure: StructureReport | None,
        elapsed_ms: float,
    ) -> dict[str, Any]:
        """Build metrics."""
        total_lines = sum(r.total_lines for r in reviews)
        total_funcs = sum(r.function_count for r in reviews)
        total_classes = sum(r.class_count for r in reviews)
        total_imports = sum(r.import_count for r in reviews)
        complexities = [r.avg_complexity for r in reviews if r.function_count > 0]
        avg_complexity = round(sum(complexities) / len(complexities), 2) if complexities else 0.0

        metrics: dict[str, Any] = {
            "files_analyzed": len(reviews),
            "total_lines": total_lines,
            "total_functions": total_funcs,
            "total_classes": total_classes,
            "total_imports": total_imports,
            "avg_complexity": avg_complexity,
            "knowledge_units": len(units),
            "duration_ms": round(elapsed_ms, 2),
        }

        if structure is not None:
            metrics["packages"] = len(structure.packages)
            metrics["python_modules"] = structure.python_module_count
            metrics["file_type_counts"] = structure.file_type_counts.counts

        return metrics
