"""Live capability evaluators for NineS V3 Analysis dimensions (D11-D15).

These evaluators measure real functional capabilities of NineS's analysis
pipeline: decomposition coverage, abstraction quality, code review
accuracy, index recall, and structure recognition. They exercise the
actual V3 analyzer components against the NineS source tree.

Covers: D11, D12, D13, D14, D15.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from nines.analyzer.decomposer import Decomposer
from nines.analyzer.indexer import KnowledgeIndex
from nines.analyzer.pipeline import AnalysisPipeline
from nines.analyzer.reviewer import CodeReviewer
from nines.analyzer.structure import StructureAnalyzer
from nines.iteration.self_eval import DimensionScore

if TYPE_CHECKING:
    from nines.iteration.context import EvaluationContext

logger = logging.getLogger(__name__)

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

_VALID_SEVERITIES = frozenset({"info", "warning", "error", "critical"})
_VALID_UNIT_TYPES = frozenset({"function", "class", "module", "concern", "layer"})

_BENCHMARK_QUERIES: dict[str, list[str]] = {
    "evaluation runner": ["eval", "runner", "run"],
    "code review": ["review", "reviewer"],
    "sandbox isolation": ["sandbox", "isolation"],
    "self improvement": ["iteration", "self_eval", "improvement"],
    "knowledge decomposition": ["decompos", "knowledge", "unit"],
}


def _collect_python_files(src_dir: Path) -> list[Path]:
    """Collect Python files from *src_dir*, skipping non-source directories."""
    files: list[Path] = []
    for fpath in sorted(src_dir.rglob("*.py")):
        rel_parts = fpath.relative_to(src_dir).parts
        if any(p in _SKIP_DIRS or p.startswith(".") for p in rel_parts):
            continue
        files.append(fpath)
    return files


def _count_ast_elements(py_files: list[Path]) -> int:
    """Count total functions + classes across *py_files* using the AST."""
    total = 0
    for fpath in py_files:
        try:
            source = fpath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(fpath))
        except (SyntaxError, UnicodeDecodeError) as exc:
            logger.warning("Skipping %s for AST count: %s", fpath, exc)
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                total += 1
    return total


# ---------------------------------------------------------------------------
# D11: Decomposition Coverage
# ---------------------------------------------------------------------------


class DecompositionCoverageEvaluator:
    """D11: Measures how completely the Decomposer captures code elements.

    Counts total analyzable elements (functions + classes) via AST, then
    runs CodeReviewer followed by Decomposer and computes the ratio
    ``captured_units / total_elements``.

    C01 Phase 1: project-aware. Reads ``ctx.src_dir`` at evaluation
    time so foreign repos no longer collapse to NineS's own counts
    (closes baseline §4.8 silent-fallback bug). The constructor still
    accepts a ``src_dir`` for backward compatibility; the supplied
    value is used only when ``ctx`` is omitted (legacy path).
    """

    #: C01 Phase 1: declares this evaluator wants a ctx-aware project
    #: binding. The runner enforces this in strict mode.
    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize decomposition coverage evaluator.

        Parameters
        ----------
        src_dir:
            Legacy default used only when ``ctx`` is omitted. The
            modern code path supplies a ctx and overrides this value.
        """
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Run decomposition against ``ctx.src_dir`` and return coverage ratio.

        Parameters
        ----------
        ctx:
            Project context.  Required for project-aware behaviour
            (the runner enforces this when ``strict_ctx=True``).
            When ``None`` (legacy / inner-runner path) the evaluator
            falls back to the constructor-time ``src_dir`` so existing
            callers keep working unchanged for one minor version.
        """
        src_dir = ctx.src_dir if ctx is not None else self._src_dir
        try:
            py_files = _collect_python_files(src_dir)
            total_elements = _count_ast_elements(py_files)

            if total_elements == 0:
                return DimensionScore(
                    name="decomposition_coverage",
                    value=0.0,
                    max_value=1.0,
                    metadata={
                        "total_elements": 0,
                        "captured_units": 0,
                        "files_analyzed": 0,
                        "src_dir": str(src_dir),
                    },
                )

            reviewer = CodeReviewer()
            reviews = []
            for fpath in py_files:
                try:
                    reviews.append(reviewer.review_file(fpath))
                except Exception as exc:
                    logger.warning("Review failed for %s: %s", fpath, exc)

            units = Decomposer().functional_decompose(reviews)
            ratio = min(len(units) / total_elements, 1.0)

            return DimensionScore(
                name="decomposition_coverage",
                value=round(ratio, 4),
                max_value=1.0,
                metadata={
                    "total_elements": total_elements,
                    "captured_units": len(units),
                    "files_analyzed": len(reviews),
                    "src_dir": str(src_dir),
                },
            )
        except Exception as exc:
            logger.error(
                "DecompositionCoverageEvaluator failed for %s: %s",
                src_dir,
                exc,
                exc_info=True,
            )
            return DimensionScore(
                name="decomposition_coverage",
                value=0.0,
                max_value=1.0,
                metadata={"src_dir": str(src_dir), "error": str(exc)},
            )


# ---------------------------------------------------------------------------
# D12: Abstraction Quality
# ---------------------------------------------------------------------------


class AbstractionQualityEvaluator:
    """D12: Measures pattern classification quality in knowledge units.

    Runs the AnalysisPipeline, then checks how many resulting
    KnowledgeUnit instances have non-empty ``tags`` and a valid
    ``unit_type`` category.

    C01 Phase 2: project-aware. Reads ``ctx.src_dir`` at evaluation
    time so foreign repos report classification quality on their own
    sources rather than silently re-evaluating NineS itself when the
    constructor argument is omitted (closes baseline §4.8 silent-
    fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize abstraction quality evaluator.

        Parameters
        ----------
        src_dir:
            Legacy default used only when ``ctx`` is omitted. The
            modern code path supplies a ctx and overrides this value.
        """
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Run the analysis pipeline and score classification quality.

        Parameters
        ----------
        ctx:
            Project context. See
            :meth:`DecompositionCoverageEvaluator.evaluate` for the
            ``ctx=None`` legacy fallback contract.
        """
        src_dir = ctx.src_dir if ctx is not None else self._src_dir
        try:
            pipeline = AnalysisPipeline()
            py_files = pipeline.ingest(src_dir)
            reviews = pipeline.analyze(py_files)

            structure = None
            try:
                structure = StructureAnalyzer().analyze_directory(src_dir)
            except Exception as exc:
                logger.warning("Structure analysis skipped: %s", exc)

            units = pipeline.decompose(reviews, structure)

            if not units:
                return DimensionScore(
                    name="abstraction_quality",
                    value=0.0,
                    max_value=1.0,
                    metadata={
                        "total_units": 0,
                        "well_classified": 0,
                        "src_dir": str(src_dir),
                    },
                )

            well_classified = sum(1 for u in units if self._is_well_classified(u))
            ratio = well_classified / len(units)

            return DimensionScore(
                name="abstraction_quality",
                value=round(ratio, 4),
                max_value=1.0,
                metadata={
                    "total_units": len(units),
                    "well_classified": well_classified,
                    "files_analyzed": len(reviews),
                    "src_dir": str(src_dir),
                },
            )
        except Exception as exc:
            logger.error(
                "AbstractionQualityEvaluator failed for %s: %s",
                src_dir,
                exc,
                exc_info=True,
            )
            return DimensionScore(
                name="abstraction_quality",
                value=0.0,
                max_value=1.0,
                metadata={"src_dir": str(src_dir), "error": str(exc)},
            )

    @staticmethod
    def _is_well_classified(unit: Any) -> bool:
        """Return True if the unit has non-empty tags and a valid type."""
        tags_str = unit.metadata.get("tags", "")
        has_tags = bool(tags_str and tags_str.strip())
        has_valid_type = unit.unit_type in _VALID_UNIT_TYPES
        return has_tags and has_valid_type


# ---------------------------------------------------------------------------
# D13: Code Review Accuracy
# ---------------------------------------------------------------------------


class CodeReviewAccuracyEvaluator:
    """D13: Measures finding quality produced by CodeReviewer.

    Validates that each Finding has a valid severity, non-empty file path,
    category, and message.  Also verifies that complexity values fall within
    the 1-50 range.  Composite score: 70% finding quality, 30% complexity
    reasonableness.

    C01 Phase 2: project-aware. Reads ``ctx.src_dir`` so the reviewed
    corpus follows the supplied project rather than silently
    defaulting to NineS's own ``src/nines`` (closes baseline §4.8
    silent-fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize code review accuracy evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Review all source files and score finding quality.

        Parameters
        ----------
        ctx:
            Project context. See
            :meth:`DecompositionCoverageEvaluator.evaluate` for the
            ``ctx=None`` legacy fallback contract.
        """
        src_dir = ctx.src_dir if ctx is not None else self._src_dir
        try:
            reviewer = CodeReviewer()
            py_files = _collect_python_files(src_dir)

            reviews = []
            for fpath in py_files:
                try:
                    reviews.append(reviewer.review_file(fpath))
                except Exception as exc:
                    logger.warning("Review failed for %s: %s", fpath, exc)

            all_findings: list[Any] = []
            for review in reviews:
                all_findings.extend(review.findings)

            if not all_findings:
                return DimensionScore(
                    name="code_review_accuracy",
                    value=0.0,
                    max_value=1.0,
                    metadata={
                        "total_findings": 0,
                        "valid_findings": 0,
                        "src_dir": str(src_dir),
                    },
                )

            valid_count = sum(1 for f in all_findings if self._is_valid_finding(f))
            finding_ratio = valid_count / len(all_findings)

            complexity_checks, reasonable = self._check_complexities(reviews)
            complexity_ratio = reasonable / complexity_checks if complexity_checks else 1.0

            score = 0.7 * finding_ratio + 0.3 * complexity_ratio

            return DimensionScore(
                name="code_review_accuracy",
                value=round(score, 4),
                max_value=1.0,
                metadata={
                    "total_findings": len(all_findings),
                    "valid_findings": valid_count,
                    "finding_quality_rate": round(finding_ratio, 4),
                    "complexity_checks": complexity_checks,
                    "reasonable_complexities": reasonable,
                    "complexity_reasonableness": round(complexity_ratio, 4),
                    "files_analyzed": len(reviews),
                    "src_dir": str(src_dir),
                },
            )
        except Exception as exc:
            logger.error(
                "CodeReviewAccuracyEvaluator failed for %s: %s",
                src_dir,
                exc,
                exc_info=True,
            )
            return DimensionScore(
                name="code_review_accuracy",
                value=0.0,
                max_value=1.0,
                metadata={"src_dir": str(src_dir), "error": str(exc)},
            )

    @staticmethod
    def _is_valid_finding(finding: Any) -> bool:
        """Return True when the finding has all required quality attributes."""
        has_severity = finding.severity in _VALID_SEVERITIES
        has_location = bool(finding.location and finding.location.strip())
        has_category = bool(finding.category and finding.category.strip())
        has_message = bool(finding.message and finding.message.strip())
        return has_severity and has_location and has_category and has_message

    @staticmethod
    def _check_complexities(reviews: list[Any]) -> tuple[int, int]:
        """Count total and reasonable (1-50) complexity values."""
        total = 0
        reasonable = 0
        for review in reviews:
            for func in review.functions:
                total += 1
                if 1 <= func.complexity <= 50:
                    reasonable += 1
            for cls in review.classes:
                for method in cls.methods:
                    total += 1
                    if 1 <= method.complexity <= 50:
                        reasonable += 1
        return total, reasonable


# ---------------------------------------------------------------------------
# D14: Index Recall
# ---------------------------------------------------------------------------


class IndexRecallEvaluator:
    """D14: Measures search recall of KnowledgeIndex.

    Builds an index from decomposed knowledge units, runs a set of
    benchmark queries, and checks whether relevant results appear in
    the top 10 for each query.

    C01 Phase 1: project-aware. Reads ``ctx.src_dir`` at evaluation
    time so the indexed corpus follows the supplied project rather
    than defaulting to NineS's own ``src/nines`` (closes baseline
    §4.8 silent-fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize index recall evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Build index, run benchmark queries, and return recall ratio.

        Parameters
        ----------
        ctx:
            Project context. See
            :meth:`DecompositionCoverageEvaluator.evaluate` for the
            ``ctx=None`` legacy fallback contract.
        """
        src_dir = ctx.src_dir if ctx is not None else self._src_dir
        try:
            pipeline = AnalysisPipeline()
            py_files = pipeline.ingest(src_dir)
            reviews = pipeline.analyze(py_files)
            units = Decomposer().functional_decompose(reviews)

            if not units:
                return DimensionScore(
                    name="index_recall",
                    value=0.0,
                    max_value=1.0,
                    metadata={
                        "indexed_units": 0,
                        "queries_tested": 0,
                        "src_dir": str(src_dir),
                    },
                )

            index = KnowledgeIndex()
            for unit in units:
                index.add_unit(unit)
            index.build_index()

            hits = 0
            query_details: dict[str, bool] = {}
            for query_text, keywords in _BENCHMARK_QUERIES.items():
                results = index.query(query_text, top_k=10)
                found = self._has_relevant_result(results, keywords, index)
                query_details[query_text] = found
                if found:
                    hits += 1

            total_queries = len(_BENCHMARK_QUERIES)
            ratio = hits / total_queries

            return DimensionScore(
                name="index_recall",
                value=round(ratio, 4),
                max_value=1.0,
                metadata={
                    "indexed_units": len(units),
                    "queries_tested": total_queries,
                    "queries_with_results": hits,
                    "query_details": query_details,
                    "src_dir": str(src_dir),
                },
            )
        except Exception as exc:
            logger.error(
                "IndexRecallEvaluator failed for %s: %s",
                src_dir,
                exc,
                exc_info=True,
            )
            return DimensionScore(
                name="index_recall",
                value=0.0,
                max_value=1.0,
                metadata={"src_dir": str(src_dir), "error": str(exc)},
            )

    @staticmethod
    def _has_relevant_result(
        results: list[tuple[str, float]],
        keywords: list[str],
        index: KnowledgeIndex,
    ) -> bool:
        """Return True if any result matches the relevance keywords."""
        for unit_id, _score in results:
            unit = index.get_unit(unit_id)
            if unit is None:
                continue
            searchable = f"{unit_id} {unit.source} {unit.content}".lower()
            if any(kw.lower() in searchable for kw in keywords):
                return True
        return False


# ---------------------------------------------------------------------------
# D15: Structure Recognition
# ---------------------------------------------------------------------------


class StructureRecognitionEvaluator:
    """D15: Measures how accurately StructureAnalyzer maps the codebase.

    Runs the analyzer on the target source and verifies: package
    detection, module count accuracy, file-type identification,
    dependency edges, and coupling metric computation.

    C01 Phase 1: project-aware. Reads ``ctx.src_dir`` at evaluation
    time so foreign repos report their own package/module counts
    instead of NineS's own (closes baseline §4.8 silent-fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize structure recognition evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Analyze directory structure and score recognition accuracy.

        Parameters
        ----------
        ctx:
            Project context. See
            :meth:`DecompositionCoverageEvaluator.evaluate` for the
            ``ctx=None`` legacy fallback contract.
        """
        src_dir = ctx.src_dir if ctx is not None else self._src_dir
        try:
            report = StructureAnalyzer().analyze_directory(src_dir)

            checks_passed = 0
            total_checks = 0
            check_details: dict[str, bool] = {}

            actual_pkgs = self._find_actual_packages(src_dir)
            if actual_pkgs:
                total_checks += 1
                detected_paths = {p.path for p in report.packages}
                matches = sum(1 for d in actual_pkgs if str(d) in detected_paths)
                ok = matches / len(actual_pkgs) >= 0.5
                check_details["package_detection"] = ok
                if ok:
                    checks_passed += 1

            actual_py_count = len(_collect_python_files(src_dir))

            total_checks += 1
            module_ok = (
                report.python_module_count > 0
                and abs(report.python_module_count - actual_py_count) / max(actual_py_count, 1)
                < 0.3
            )
            check_details["module_count_accuracy"] = module_ok
            if module_ok:
                checks_passed += 1

            total_checks += 1
            has_py = ".py" in report.file_type_counts.counts
            check_details["py_file_type_detected"] = has_py
            if has_py:
                checks_passed += 1

            total_checks += 1
            has_deps = len(report.dependency_map.edges) > 0
            check_details["dependencies_detected"] = has_deps
            if has_deps:
                checks_passed += 1

            total_checks += 1
            has_coupling = len(report.coupling_metrics) > 0
            check_details["coupling_computed"] = has_coupling
            if has_coupling:
                checks_passed += 1

            ratio = checks_passed / total_checks if total_checks > 0 else 0.0

            return DimensionScore(
                name="structure_recognition",
                value=round(ratio, 4),
                max_value=1.0,
                metadata={
                    "checks_passed": checks_passed,
                    "total_checks": total_checks,
                    "detected_packages": len(report.packages),
                    "actual_packages": len(actual_pkgs),
                    "detected_modules": report.python_module_count,
                    "actual_py_files": actual_py_count,
                    "dependency_edges": len(report.dependency_map.edges),
                    "check_details": check_details,
                    "src_dir": str(src_dir),
                },
            )
        except Exception as exc:
            logger.error(
                "StructureRecognitionEvaluator failed for %s: %s",
                src_dir,
                exc,
                exc_info=True,
            )
            return DimensionScore(
                name="structure_recognition",
                value=0.0,
                max_value=1.0,
                metadata={"src_dir": str(src_dir), "error": str(exc)},
            )

    @staticmethod
    def _find_actual_packages(src_dir: Path) -> list[Path]:
        """Discover actual Python packages (directories with ``__init__.py``).

        Pulled out of ``self._src_dir`` and made static so the caller
        can pass the C01 ``ctx.src_dir`` directly without first
        mutating the instance.
        """
        packages: list[Path] = []
        for dirpath in sorted(src_dir.rglob("*")):
            if not dirpath.is_dir():
                continue
            rel_parts = dirpath.relative_to(src_dir).parts
            if any(p in _SKIP_DIRS or p.startswith(".") for p in rel_parts):
                continue
            if (dirpath / "__init__.py").is_file():
                packages.append(dirpath)
        if (src_dir / "__init__.py").is_file():
            packages.insert(0, src_dir)
        return packages


# ---------------------------------------------------------------------------
# D16: Agent Analysis Quality
# ---------------------------------------------------------------------------


class AgentAnalysisQualityEvaluator:
    """D20: Measures NineS's ability to correctly analyze agent-impact on a known repo.

    Runs AgentImpactAnalyzer on the configured project tree and checks:
    1. Agent-facing artifacts are detected (SKILL.md templates exist)
    2. At least 1 mechanism is identified
    3. Context economics produces non-empty results
    4. Findings are produced
    5. Pipeline with agent_impact + keypoints runs without error

    Score = checks_passed / total_checks.

    C01 Phase 2: project-aware. Reads ``ctx.project_root`` and
    ``ctx.src_dir`` so foreign-repo runs analyze the *target* project's
    agent-facing artifacts rather than silently re-analyzing NineS
    itself when the constructor argument is omitted (closes baseline
    §4.8 silent-fallback bug).
    """

    requires_context: ClassVar[bool] = True

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize agent analysis quality evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(
        self,
        *,
        ctx: EvaluationContext | None = None,
    ) -> DimensionScore:
        """Run agent-impact analysis on the project tree and score quality.

        Parameters
        ----------
        ctx:
            Project context. When supplied, uses ``ctx.project_root``
            (the target repo to analyze) and ``ctx.src_dir`` (the
            source tree). When ``None``, falls back to the
            constructor-time ``src_dir`` and the legacy
            walk-up-to-find-``src`` heuristic.
        """
        from nines.analyzer.agent_impact import AgentImpactAnalyzer

        if ctx is not None:
            src_dir = ctx.src_dir
            project_root = ctx.project_root
        else:
            src_dir = self._src_dir
            project_root = self._resolve_project_root_from(src_dir)

        checks_passed = 0
        total_checks = 5
        details: dict[str, Any] = {}

        try:
            if not src_dir.is_dir():
                raise FileNotFoundError(f"Source directory does not exist: {src_dir}")

            analyzer = AgentImpactAnalyzer()

            report = analyzer.analyze(project_root)

            has_artifacts = len(report.agent_facing_artifacts) > 0
            details["artifacts_detected"] = has_artifacts
            if has_artifacts:
                checks_passed += 1

            has_mechanisms = len(report.mechanisms) > 0
            details["mechanisms_identified"] = has_mechanisms
            if has_mechanisms:
                checks_passed += 1

            has_economics = report.economics.overhead_tokens > 0
            details["economics_calculated"] = has_economics
            if has_economics:
                checks_passed += 1

            has_findings = len(report.findings) > 0
            details["findings_produced"] = has_findings
            if has_findings:
                checks_passed += 1

            pipeline = AnalysisPipeline()
            result = pipeline.run(project_root, agent_impact=True, keypoints=True)
            has_keypoints = "key_points" in result.metrics
            details["keypoints_extracted"] = has_keypoints
            if has_keypoints:
                checks_passed += 1

        except Exception as exc:
            logger.error("AgentAnalysisQualityEvaluator failed for %s: %s", project_root, exc)
            details["error"] = str(exc)

        score = checks_passed / total_checks if total_checks > 0 else 0.0

        return DimensionScore(
            name="agent_analysis_quality",
            value=round(score, 4),
            max_value=1.0,
            metadata={
                "checks_passed": checks_passed,
                "total_checks": total_checks,
                "details": details,
                "src_dir": str(src_dir),
                "project_root": str(project_root),
            },
        )

    @staticmethod
    def _resolve_project_root_from(src_dir: Path) -> Path:
        """Walk up from *src_dir* to find the project root (parent of 'src').

        Static so the legacy ``ctx=None`` path can use it without
        relying on ``self._src_dir`` mutation.
        """
        project_root = src_dir
        while project_root.name != "src" and project_root != project_root.parent:
            project_root = project_root.parent
        if project_root.name == "src":
            project_root = project_root.parent
        return project_root
