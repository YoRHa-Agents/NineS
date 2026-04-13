"""Tests for nines.iteration.capability_evaluators (D11-D15).

Verifies that all five capability evaluators:
  - Implement the DimensionEvaluator protocol
  - Return DimensionScore with correct names and valid ranges
  - Handle error conditions gracefully (non-existent path -> 0.0)
  - Produce meaningful results against real NineS source
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.capability_evaluators import (
    AbstractionQualityEvaluator,
    CodeReviewAccuracyEvaluator,
    DecompositionCoverageEvaluator,
    IndexRecallEvaluator,
    StructureRecognitionEvaluator,
    _collect_python_files,
    _count_ast_elements,
)
from nines.iteration.self_eval import DimensionEvaluator, DimensionScore

NINES_SRC = Path(__file__).resolve().parent.parent / "src" / "nines"


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [
        DecompositionCoverageEvaluator,
        AbstractionQualityEvaluator,
        CodeReviewAccuracyEvaluator,
        IndexRecallEvaluator,
        StructureRecognitionEvaluator,
    ],
)
def test_evaluator_satisfies_protocol(cls: type) -> None:
    """Each evaluator class satisfies the DimensionEvaluator protocol."""
    instance = cls(NINES_SRC)
    assert isinstance(instance, DimensionEvaluator)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_collect_python_files() -> None:
    """_collect_python_files discovers .py files, skipping __pycache__."""
    files = _collect_python_files(NINES_SRC)
    assert len(files) > 0
    for f in files:
        assert f.suffix == ".py"
        assert "__pycache__" not in f.parts


def test_count_ast_elements() -> None:
    """_count_ast_elements returns a positive count for real source."""
    files = _collect_python_files(NINES_SRC)
    total = _count_ast_elements(files)
    assert total > 0


# ---------------------------------------------------------------------------
# D11: DecompositionCoverageEvaluator
# ---------------------------------------------------------------------------


def test_decomposition_coverage_real_source() -> None:
    """D11 evaluator produces a score in (0, 1] against real NineS source."""
    ev = DecompositionCoverageEvaluator(NINES_SRC)
    score = ev.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "decomposition_coverage"
    assert score.max_value == 1.0
    assert 0.0 < score.value <= 1.0
    assert score.metadata["total_elements"] > 0
    assert score.metadata["captured_units"] > 0
    assert score.metadata["files_analyzed"] > 0


def test_decomposition_coverage_bad_path() -> None:
    """D11 evaluator returns 0.0 for a non-existent path."""
    ev = DecompositionCoverageEvaluator("/tmp/nonexistent_nines_dir")
    score = ev.evaluate()
    assert score.value == 0.0


# ---------------------------------------------------------------------------
# D12: AbstractionQualityEvaluator
# ---------------------------------------------------------------------------


def test_abstraction_quality_real_source() -> None:
    """D12 evaluator produces a score in [0, 1] against real NineS source."""
    ev = AbstractionQualityEvaluator(NINES_SRC)
    score = ev.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "abstraction_quality"
    assert score.max_value == 1.0
    assert 0.0 <= score.value <= 1.0
    assert score.metadata["total_units"] > 0
    assert score.metadata["files_analyzed"] > 0


def test_abstraction_quality_bad_path() -> None:
    """D12 evaluator returns 0.0 for a non-existent path."""
    ev = AbstractionQualityEvaluator("/tmp/nonexistent_nines_dir")
    score = ev.evaluate()
    assert score.value == 0.0


# ---------------------------------------------------------------------------
# D13: CodeReviewAccuracyEvaluator
# ---------------------------------------------------------------------------


def test_code_review_accuracy_real_source() -> None:
    """D13 evaluator produces a score in (0, 1] against real NineS source."""
    ev = CodeReviewAccuracyEvaluator(NINES_SRC)
    score = ev.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "code_review_accuracy"
    assert score.max_value == 1.0
    assert 0.0 < score.value <= 1.0
    assert score.metadata["total_findings"] > 0
    assert score.metadata["valid_findings"] > 0
    assert score.metadata["files_analyzed"] > 0
    assert 0.0 <= score.metadata["finding_quality_rate"] <= 1.0
    assert 0.0 <= score.metadata["complexity_reasonableness"] <= 1.0


def test_code_review_accuracy_bad_path() -> None:
    """D13 evaluator returns 0.0 for a non-existent path."""
    ev = CodeReviewAccuracyEvaluator("/tmp/nonexistent_nines_dir")
    score = ev.evaluate()
    assert score.value == 0.0


# ---------------------------------------------------------------------------
# D14: IndexRecallEvaluator
# ---------------------------------------------------------------------------


def test_index_recall_real_source() -> None:
    """D14 evaluator produces a score in (0, 1] against real NineS source."""
    ev = IndexRecallEvaluator(NINES_SRC)
    score = ev.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "index_recall"
    assert score.max_value == 1.0
    assert 0.0 < score.value <= 1.0
    assert score.metadata["indexed_units"] > 0
    assert score.metadata["queries_tested"] == 5
    assert score.metadata["queries_with_results"] > 0
    assert isinstance(score.metadata["query_details"], dict)


def test_index_recall_bad_path() -> None:
    """D14 evaluator returns 0.0 for a non-existent path."""
    ev = IndexRecallEvaluator("/tmp/nonexistent_nines_dir")
    score = ev.evaluate()
    assert score.value == 0.0


# ---------------------------------------------------------------------------
# D15: StructureRecognitionEvaluator
# ---------------------------------------------------------------------------


def test_structure_recognition_real_source() -> None:
    """D15 evaluator produces a score in (0, 1] against real NineS source."""
    ev = StructureRecognitionEvaluator(NINES_SRC)
    score = ev.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "structure_recognition"
    assert score.max_value == 1.0
    assert 0.0 < score.value <= 1.0
    assert score.metadata["checks_passed"] > 0
    assert score.metadata["total_checks"] >= 5
    assert score.metadata["detected_packages"] > 0
    assert score.metadata["detected_modules"] > 0
    assert isinstance(score.metadata["check_details"], dict)


def test_structure_recognition_bad_path() -> None:
    """D15 evaluator returns 0.0 for a non-existent path."""
    ev = StructureRecognitionEvaluator("/tmp/nonexistent_nines_dir")
    score = ev.evaluate()
    assert score.value == 0.0


# ---------------------------------------------------------------------------
# Integration: register all five with SelfEvalRunner
# ---------------------------------------------------------------------------


def test_all_evaluators_with_runner() -> None:
    """All five evaluators run through SelfEvalRunner without crashing."""
    from nines.iteration.self_eval import SelfEvalRunner

    runner = SelfEvalRunner()
    runner.register_dimension("d11", DecompositionCoverageEvaluator(NINES_SRC))
    runner.register_dimension("d12", AbstractionQualityEvaluator(NINES_SRC))
    runner.register_dimension("d13", CodeReviewAccuracyEvaluator(NINES_SRC))
    runner.register_dimension("d14", IndexRecallEvaluator(NINES_SRC))
    runner.register_dimension("d15", StructureRecognitionEvaluator(NINES_SRC))

    report = runner.run_all(version="test-cap-v3")

    assert len(report.scores) == 5
    assert report.overall > 0.0
    for score in report.scores:
        assert 0.0 <= score.value <= score.max_value
