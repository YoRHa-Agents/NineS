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


def _count_ast_breakdown(py_files: list[Path]) -> tuple[int, int, int]:
    """Return ``(functions, classes, packages_with_init)`` from the AST.

    Used by C12 sub-skill extraction so D11 can report function /
    class capture rates separately rather than collapsing both into a
    single ratio.
    """
    functions = 0
    classes = 0
    for fpath in py_files:
        try:
            source = fpath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(fpath))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
    packages = sum(1 for fpath in py_files if fpath.name == "__init__.py")
    return functions, classes, packages


def _safe_ratio(num: float, denom: float) -> float:
    """Return ``num/denom`` clamped to ``[0, 1]`` with zero-denom = 0.

    Used by C12 sub-skill computations to avoid divide-by-zero on
    degenerate fixtures (e.g. empty source trees).
    """
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, num / denom))


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
                        # C12: emit zero sub-skills so the panel
                        # exists even on empty/non-Python repos.
                        "subskills": [
                            {"name": "file_coverage", "value": 0.0,
                             "max_value": 1.0, "weight": 0.20,
                             "metadata": {"reason": "empty_source"}},
                            {"name": "element_coverage", "value": 0.0,
                             "max_value": 1.0, "weight": 0.40,
                             "metadata": {"reason": "empty_source"}},
                            {"name": "function_capture", "value": 0.0,
                             "max_value": 1.0, "weight": 0.20,
                             "metadata": {"reason": "empty_source"}},
                            {"name": "class_capture", "value": 0.0,
                             "max_value": 1.0, "weight": 0.20,
                             "metadata": {"reason": "empty_source"}},
                        ],
                        "rollup_method": "weighted_mean",
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

            # C12: per-sub-skill breakdown.  Re-walk the AST to compute
            # function-vs-class capture rates and package coverage so
            # the D11 score is not just a single opaque ratio.
            functions, classes, packages = _count_ast_breakdown(py_files)
            captured_funcs = sum(
                1 for u in units if getattr(u, "unit_type", None) == "function"
            )
            captured_classes = sum(
                1 for u in units if getattr(u, "unit_type", None) == "class"
            )
            file_coverage = _safe_ratio(len(reviews), len(py_files))
            element_coverage = _safe_ratio(len(units), total_elements)
            function_capture = _safe_ratio(captured_funcs, functions)
            class_capture = _safe_ratio(captured_classes, classes) if classes else (
                1.0 if captured_classes == 0 else 0.0
            )
            # ``packages`` (count of __init__.py files) is recorded in
            # the metadata for downstream tooling but not used as a
            # standalone sub-skill — file_coverage already captures
            # whether the package layout was traversable.

            return DimensionScore(
                name="decomposition_coverage",
                value=round(ratio, 4),
                max_value=1.0,
                metadata={
                    "total_elements": total_elements,
                    "captured_units": len(units),
                    "files_analyzed": len(reviews),
                    "src_dir": str(src_dir),
                    # C12 sub-skill block
                    "subskills": [
                        {
                            "name": "file_coverage",
                            "value": round(file_coverage, 4),
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "files_reviewed": len(reviews),
                                "files_total": len(py_files),
                            },
                        },
                        {
                            "name": "element_coverage",
                            "value": round(element_coverage, 4),
                            "max_value": 1.0,
                            "weight": 0.40,
                            "metadata": {
                                "captured": len(units),
                                "total": total_elements,
                            },
                        },
                        {
                            "name": "function_capture",
                            "value": round(function_capture, 4),
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "captured_functions": captured_funcs,
                                "total_functions": functions,
                            },
                        },
                        {
                            "name": "class_capture",
                            "value": round(class_capture, 4),
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "captured_classes": captured_classes,
                                "total_classes": classes,
                            },
                        },
                    ],
                    "rollup_method": "weighted_mean",
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
                        "subskills": [
                            {"name": "tag_coverage", "value": 0.0,
                             "max_value": 1.0, "weight": 0.40,
                             "metadata": {"reason": "no_units"}},
                            {"name": "type_validity", "value": 0.0,
                             "max_value": 1.0, "weight": 0.40,
                             "metadata": {"reason": "no_units"}},
                            {"name": "unit_density", "value": 0.0,
                             "max_value": 1.0, "weight": 0.20,
                             "metadata": {"reason": "no_units"}},
                        ],
                        "rollup_method": "weighted_mean",
                    },
                )

            well_classified = sum(1 for u in units if self._is_well_classified(u))
            ratio = well_classified / len(units)

            # C12: split the single ``well_classified`` ratio into its
            # two ingredients (tag coverage + type validity) plus a
            # density sub-skill that rewards reaching at least one
            # unit per analysed file (saturates at 1.0/file).
            tagged = sum(
                1
                for u in units
                if (u.metadata.get("tags", "") or "").strip()
            )
            valid_typed = sum(1 for u in units if u.unit_type in _VALID_UNIT_TYPES)
            tag_coverage = _safe_ratio(tagged, len(units))
            type_validity = _safe_ratio(valid_typed, len(units))
            density_target = max(len(reviews), 1)
            unit_density = min(1.0, len(units) / density_target)

            return DimensionScore(
                name="abstraction_quality",
                value=round(ratio, 4),
                max_value=1.0,
                metadata={
                    "total_units": len(units),
                    "well_classified": well_classified,
                    "files_analyzed": len(reviews),
                    "src_dir": str(src_dir),
                    "tagged_units": tagged,
                    "valid_typed_units": valid_typed,
                    "subskills": [
                        {
                            "name": "tag_coverage",
                            "value": round(tag_coverage, 4),
                            "max_value": 1.0,
                            "weight": 0.40,
                            "metadata": {"tagged": tagged, "total": len(units)},
                        },
                        {
                            "name": "type_validity",
                            "value": round(type_validity, 4),
                            "max_value": 1.0,
                            "weight": 0.40,
                            "metadata": {"valid": valid_typed, "total": len(units)},
                        },
                        {
                            "name": "unit_density",
                            "value": round(unit_density, 4),
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "units": len(units),
                                "files": len(reviews),
                            },
                        },
                    ],
                    "rollup_method": "weighted_mean",
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
                        "subskills": [
                            {"name": "finding_quality_rate", "value": 0.0,
                             "max_value": 1.0, "weight": 0.40,
                             "metadata": {"reason": "no_findings"}},
                            {"name": "complexity_check_rate", "value": 0.0,
                             "max_value": 1.0, "weight": 0.20,
                             "metadata": {"reason": "no_findings"}},
                            {"name": "severity_balance", "value": 0.0,
                             "max_value": 1.0, "weight": 0.20,
                             "metadata": {"reason": "no_findings"}},
                            {"name": "false_positive_signal", "value": 0.0,
                             "max_value": 1.0, "weight": 0.20,
                             "metadata": {"reason": "no_findings"}},
                        ],
                        "rollup_method": "weighted_mean",
                    },
                )

            valid_count = sum(1 for f in all_findings if self._is_valid_finding(f))
            finding_ratio = valid_count / len(all_findings)

            complexity_checks, reasonable = self._check_complexities(reviews)
            complexity_ratio = reasonable / complexity_checks if complexity_checks else 1.0

            score = 0.7 * finding_ratio + 0.3 * complexity_ratio

            # C12: severity balance and false-positive rate.  Spread the
            # finding population across severity buckets so a reviewer
            # that only ever emits one severity is visibly imbalanced;
            # treat findings missing core attributes as
            # "false positives" so the false-positive sub-skill is the
            # complement of finding_quality_rate.
            severity_buckets: dict[str, int] = {}
            for finding in all_findings:
                key = (
                    finding.severity
                    if finding.severity in _VALID_SEVERITIES
                    else "unknown"
                )
                severity_buckets[key] = severity_buckets.get(key, 0) + 1
            distinct_sev = sum(1 for v in severity_buckets.values() if v > 0)
            severity_balance = _safe_ratio(distinct_sev, len(_VALID_SEVERITIES))
            false_positive_rate = _safe_ratio(
                len(all_findings) - valid_count, len(all_findings)
            )
            fp_signal = max(0.0, 1.0 - false_positive_rate)

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
                    "severity_buckets": dict(severity_buckets),
                    "false_positive_rate": round(false_positive_rate, 4),
                    # C12 sub-skill block
                    "subskills": [
                        {
                            "name": "finding_quality_rate",
                            "value": round(finding_ratio, 4),
                            "max_value": 1.0,
                            "weight": 0.40,
                            "metadata": {
                                "valid": valid_count,
                                "total": len(all_findings),
                            },
                        },
                        {
                            "name": "complexity_check_rate",
                            "value": round(complexity_ratio, 4),
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "reasonable": reasonable,
                                "checked": complexity_checks,
                            },
                        },
                        {
                            "name": "severity_balance",
                            "value": round(severity_balance, 4),
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "distinct_severities": distinct_sev,
                                "buckets": dict(severity_buckets),
                            },
                        },
                        {
                            "name": "false_positive_signal",
                            "value": round(fp_signal, 4),
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "false_positive_rate": round(false_positive_rate, 4),
                            },
                        },
                    ],
                    "rollup_method": "weighted_mean",
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
                        "subskills": [
                            {"name": "query_hit_rate", "value": 0.0,
                             "max_value": 1.0, "weight": 0.40,
                             "metadata": {"reason": "empty_index"}},
                            {"name": "exact_match_rate", "value": 0.0,
                             "max_value": 1.0, "weight": 0.25,
                             "metadata": {"reason": "empty_index"}},
                            {"name": "partial_match_rate", "value": 0.0,
                             "max_value": 1.0, "weight": 0.20,
                             "metadata": {"reason": "empty_index"}},
                            {"name": "latency_score", "value": 0.0,
                             "max_value": 1.0, "weight": 0.15,
                             "metadata": {"reason": "empty_index"}},
                        ],
                        "rollup_method": "weighted_mean",
                    },
                )

            index = KnowledgeIndex()
            for unit in units:
                index.add_unit(unit)
            index.build_index()

            hits = 0
            query_details: dict[str, bool] = {}
            exact_match_hits = 0
            partial_match_hits = 0
            non_empty_results = 0
            for query_text, keywords in _BENCHMARK_QUERIES.items():
                results = index.query(query_text, top_k=10)
                found = self._has_relevant_result(results, keywords, index)
                query_details[query_text] = found
                if results:
                    non_empty_results += 1
                if found:
                    hits += 1
                # C12: distinguish exact (top-1 hit) from partial (any of top-10) recall.
                top1_keywords_match = False
                if results:
                    first_id = results[0][0]
                    first_unit = index.get_unit(first_id)
                    if first_unit is not None:
                        searchable_first = (
                            f"{first_id} {first_unit.source} {first_unit.content}".lower()
                        )
                        top1_keywords_match = any(
                            kw.lower() in searchable_first for kw in keywords
                        )
                if top1_keywords_match:
                    exact_match_hits += 1
                if found and not top1_keywords_match:
                    partial_match_hits += 1

            total_queries = len(_BENCHMARK_QUERIES)
            ratio = hits / total_queries

            # C12 sub-skills.  Latency_score is a coarse signal — it
            # rewards the fact that index.query returned at all (i.e.
            # the index is queryable) without measuring wall-clock,
            # which would couple the sub-skill to noisy CI hardware.
            query_hit_rate = _safe_ratio(hits, total_queries)
            exact_match_rate = _safe_ratio(exact_match_hits, total_queries)
            partial_match_rate = _safe_ratio(partial_match_hits, total_queries)
            latency_score = _safe_ratio(non_empty_results, total_queries)

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
                    "exact_match_hits": exact_match_hits,
                    "partial_match_hits": partial_match_hits,
                    # C12 sub-skill block
                    "subskills": [
                        {
                            "name": "query_hit_rate",
                            "value": round(query_hit_rate, 4),
                            "max_value": 1.0,
                            "weight": 0.40,
                            "metadata": {"hits": hits, "queries": total_queries},
                        },
                        {
                            "name": "exact_match_rate",
                            "value": round(exact_match_rate, 4),
                            "max_value": 1.0,
                            "weight": 0.25,
                            "metadata": {
                                "exact_top1": exact_match_hits,
                                "queries": total_queries,
                            },
                        },
                        {
                            "name": "partial_match_rate",
                            "value": round(partial_match_rate, 4),
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "partial": partial_match_hits,
                                "queries": total_queries,
                            },
                        },
                        {
                            "name": "latency_score",
                            "value": round(latency_score, 4),
                            "max_value": 1.0,
                            "weight": 0.15,
                            "metadata": {
                                "non_empty": non_empty_results,
                                "queries": total_queries,
                            },
                        },
                    ],
                    "rollup_method": "weighted_mean",
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

            # C12 sub-skills.  Where possible we expose the *continuous*
            # ratio (detected/actual) instead of the binary check_passed
            # flag — that way "saturated" D15 dims still surface
            # non-saturated sub-skills (the AgentBoard headroom signal).
            actual_pkg_count = max(len(actual_pkgs), 1)
            detected_pkg_count = len(report.packages)
            package_ratio = (
                min(1.0, detected_pkg_count / actual_pkg_count)
                if actual_pkgs
                else 0.0
            )
            module_ratio = (
                1.0
                - min(
                    1.0,
                    abs(report.python_module_count - actual_py_count)
                    / max(actual_py_count, 1),
                )
                if actual_py_count
                else 0.0
            )
            framework_detection = float(
                check_details.get("py_file_type_detected", False)
            )
            # Layout inference scales with the proportion of files that
            # actually wired up at least one dependency edge — the
            # parser caps the contribution at 1.0 per file even on a
            # graph-rich repo so the score stays in [0, 1].
            edge_count = len(report.dependency_map.edges)
            layout_inference = (
                min(1.0, edge_count / max(actual_py_count, 1))
                if actual_py_count
                else 0.0
            )
            # Coupling inference scales with how many modules have
            # coupling metrics computed; saturates once every module
            # contributes at least one number.
            coupling_inference = (
                min(1.0, len(report.coupling_metrics) / max(actual_py_count, 1))
                if actual_py_count
                else 0.0
            )
            package_detection = round(package_ratio, 4)
            module_detection = round(module_ratio, 4)
            layout_inference = round(layout_inference, 4)
            coupling_inference = round(coupling_inference, 4)

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
                    # C12 sub-skill block
                    "subskills": [
                        {
                            "name": "package_detection",
                            "value": package_detection,
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "detected": len(report.packages),
                                "actual": len(actual_pkgs),
                            },
                        },
                        {
                            "name": "module_detection",
                            "value": module_detection,
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "detected": report.python_module_count,
                                "actual_files": actual_py_count,
                            },
                        },
                        {
                            "name": "framework_detection",
                            "value": framework_detection,
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {"py_type_seen": bool(framework_detection)},
                        },
                        {
                            "name": "layout_inference",
                            "value": layout_inference,
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "dependency_edges": len(report.dependency_map.edges),
                            },
                        },
                        {
                            "name": "coupling_inference",
                            "value": coupling_inference,
                            "max_value": 1.0,
                            "weight": 0.20,
                            "metadata": {
                                "coupling_metric_count": len(report.coupling_metrics),
                            },
                        },
                    ],
                    "rollup_method": "weighted_mean",
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

        # C12 sub-skills — one per check the evaluator runs, plus a
        # synthetic "key_points_quality" derived from the keypoints
        # check so reviewers see five distinct rows in the breakdown.
        artifacts_detected = float(details.get("artifacts_detected", False))
        mechanisms_identified = float(details.get("mechanisms_identified", False))
        economics_detected = float(details.get("economics_calculated", False))
        findings_quality = float(details.get("findings_produced", False))
        key_points_quality = float(details.get("keypoints_extracted", False))

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
                # C12 sub-skill block
                "subskills": [
                    {
                        "name": "artifacts_detected",
                        "value": artifacts_detected,
                        "max_value": 1.0,
                        "weight": 0.20,
                        "metadata": {"check": "artifacts_detected"},
                    },
                    {
                        "name": "mechanisms_identified",
                        "value": mechanisms_identified,
                        "max_value": 1.0,
                        "weight": 0.20,
                        "metadata": {"check": "mechanisms_identified"},
                    },
                    {
                        "name": "economics_detected",
                        "value": economics_detected,
                        "max_value": 1.0,
                        "weight": 0.20,
                        "metadata": {"check": "economics_calculated"},
                    },
                    {
                        "name": "findings_quality",
                        "value": findings_quality,
                        "max_value": 1.0,
                        "weight": 0.20,
                        "metadata": {"check": "findings_produced"},
                    },
                    {
                        "name": "key_points_quality",
                        "value": key_points_quality,
                        "max_value": 1.0,
                        "weight": 0.20,
                        "metadata": {"check": "keypoints_extracted"},
                    },
                ],
                "rollup_method": "weighted_mean",
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
