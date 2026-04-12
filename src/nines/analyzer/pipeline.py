"""Analysis pipeline orchestrator.

Chains ingest → analyze → decompose into an end-to-end flow that
produces an :class:`~nines.core.models.AnalysisResult`.

Covers: FR-310, FR-311.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from nines.core.errors import AnalyzerError
from nines.core.models import AnalysisResult, Finding, KnowledgeUnit

from nines.analyzer.decomposer import Decomposer
from nines.analyzer.reviewer import CodeReviewer, FileReview
from nines.analyzer.structure import StructureAnalyzer, StructureReport

logger = logging.getLogger(__name__)

_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".hg", ".svn", "node_modules",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".venv", "venv", ".eggs",
})


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
    """

    def __init__(
        self,
        reviewer: CodeReviewer | None = None,
        structure_analyzer: StructureAnalyzer | None = None,
        decomposer: Decomposer | None = None,
    ) -> None:
        self._reviewer = reviewer or CodeReviewer()
        self._structure = structure_analyzer or StructureAnalyzer()
        self._decomposer = decomposer or Decomposer()

    def run(self, path: str | Path) -> AnalysisResult:
        """Execute the full pipeline on *path*.

        If *path* is a file, only that file is reviewed and decomposed.
        If *path* is a directory, all Python files are ingested and both
        structure analysis and decomposition are performed.
        """
        start = time.monotonic()
        target = Path(path)

        py_files = self.ingest(target)
        reviews = self.analyze(py_files)
        structure: StructureReport | None = None
        if target.is_dir():
            try:
                structure = self._structure.analyze_directory(target)
            except AnalyzerError:
                logger.warning("Structure analysis failed for %s", target, exc_info=True)

        units = self.decompose(reviews, structure)

        all_findings: list[Finding] = []
        for review in reviews:
            all_findings.extend(review.findings)

        elapsed_ms = (time.monotonic() - start) * 1000

        metrics = self._build_metrics(reviews, units, structure, elapsed_ms)

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
    ) -> list[KnowledgeUnit]:
        """Run functional decomposition on all reviews."""
        return self._decomposer.functional_decompose(reviews)

    @staticmethod
    def _build_metrics(
        reviews: list[FileReview],
        units: list[KnowledgeUnit],
        structure: StructureReport | None,
        elapsed_ms: float,
    ) -> dict[str, Any]:
        total_lines = sum(r.total_lines for r in reviews)
        total_funcs = sum(r.function_count for r in reviews)
        total_classes = sum(r.class_count for r in reviews)
        total_imports = sum(r.import_count for r in reviews)
        complexities = [r.avg_complexity for r in reviews if r.function_count > 0]
        avg_complexity = (
            round(sum(complexities) / len(complexities), 2) if complexities else 0.0
        )

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
