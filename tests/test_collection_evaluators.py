"""Tests for nines.iteration.collection_evaluators (D06, D09, D10).

Verifies that all three V2 Collection evaluators:
  - Implement the DimensionEvaluator protocol
  - Return DimensionScore with correct names and valid ranges
  - Handle error conditions gracefully
  - Produce meaningful results against the real NineS codebase
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.collection_evaluators import (
    CollectionThroughputEvaluator,
    DataCompletenessEvaluator,
    SourceCoverageEvaluator,
)
from nines.iteration.self_eval import DimensionEvaluator, DimensionScore


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [
        SourceCoverageEvaluator,
        DataCompletenessEvaluator,
        CollectionThroughputEvaluator,
    ],
)
def test_evaluator_satisfies_protocol(cls: type) -> None:
    """Each evaluator class satisfies the DimensionEvaluator protocol."""
    instance = cls()
    assert isinstance(instance, DimensionEvaluator)


# ---------------------------------------------------------------------------
# D06: SourceCoverageEvaluator
# ---------------------------------------------------------------------------


def test_source_coverage_returns_positive() -> None:
    """Both github and arxiv are importable, so score should be 1.0."""
    ev = SourceCoverageEvaluator()
    score = ev.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "source_coverage"
    assert score.max_value == 1.0
    assert score.value > 0.0
    assert score.metadata["configured_sources"] == 2
    assert score.metadata["active_sources"] >= 1


def test_source_coverage_full_when_both_active() -> None:
    """With real collectors available, all sources should be active."""
    ev = SourceCoverageEvaluator()
    score = ev.evaluate()

    assert score.value == 1.0
    assert score.metadata["active_sources"] == 2
    for source_name, detail in score.metadata["details"].items():
        assert detail["importable"] is True
        assert detail["has_search"] is True
        assert detail["has_fetch"] is True


def test_source_coverage_handles_import_failure() -> None:
    """Score degrades gracefully when a collector cannot be imported."""
    with patch("importlib.import_module", side_effect=ImportError("mocked")):
        ev = SourceCoverageEvaluator()
        score = ev.evaluate()

    assert score.value == 0.0
    assert score.metadata["active_sources"] == 0


# ---------------------------------------------------------------------------
# D09: DataCompletenessEvaluator
# ---------------------------------------------------------------------------


def test_data_completeness_returns_high_score() -> None:
    """With all fields populated, completeness should be > 0.8."""
    ev = DataCompletenessEvaluator()
    score = ev.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "data_completeness"
    assert score.max_value == 1.0
    assert score.value > 0.8
    assert score.metadata["valid_fields"] > 0
    assert score.metadata["total_fields"] > 0


def test_data_completeness_full_score() -> None:
    """All expected fields are present and populated in sample instances."""
    ev = DataCompletenessEvaluator()
    score = ev.evaluate()

    assert score.value == 1.0
    for field_key, ok in score.metadata["field_details"].items():
        assert ok, f"Field {field_key} not valid"


def test_data_completeness_handles_import_error() -> None:
    """Returns 0.0 when collector models cannot be imported."""
    with patch.dict("sys.modules", {"nines.collector.models": None}):
        ev = DataCompletenessEvaluator()
        score = ev.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


# ---------------------------------------------------------------------------
# D10: CollectionThroughputEvaluator
# ---------------------------------------------------------------------------


def test_collection_throughput_returns_positive() -> None:
    """Store operations complete and produce a positive score."""
    ev = CollectionThroughputEvaluator()
    score = ev.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "collection_throughput"
    assert score.max_value == 1.0
    assert score.value > 0.0
    assert score.metadata["elapsed_seconds"] >= 0
    assert score.metadata["inserted"] == 200
    assert score.metadata["retrieved"] == 200


def test_collection_throughput_fast_enough() -> None:
    """In-memory SQLite should complete well within the 5s budget."""
    ev = CollectionThroughputEvaluator()
    score = ev.evaluate()

    assert score.value > 0.5
    assert score.metadata["elapsed_seconds"] < 2.5


def test_collection_throughput_handles_store_error() -> None:
    """Returns 0.0 when DataStore cannot be imported."""
    with patch.dict("sys.modules", {"nines.collector.store": None}):
        ev = CollectionThroughputEvaluator()
        score = ev.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


# ---------------------------------------------------------------------------
# Integration: register all three with SelfEvalRunner
# ---------------------------------------------------------------------------


def test_all_evaluators_with_runner() -> None:
    """All three evaluators run through SelfEvalRunner without crashing."""
    from nines.iteration.self_eval import SelfEvalRunner

    runner = SelfEvalRunner()
    runner.register_dimension("source_coverage", SourceCoverageEvaluator())
    runner.register_dimension("data_completeness", DataCompletenessEvaluator())
    runner.register_dimension(
        "collection_throughput", CollectionThroughputEvaluator(),
    )

    report = runner.run_all(version="test-v2-collection")

    assert len(report.scores) == 3
    assert report.overall > 0.0
    for score in report.scores:
        assert 0.0 <= score.value <= score.max_value
        assert score.name in {
            "source_coverage",
            "data_completeness",
            "collection_throughput",
        }


# ---------------------------------------------------------------------------
# Error resilience: evaluators should never crash
# ---------------------------------------------------------------------------


def test_all_evaluators_return_dimension_score() -> None:
    """All evaluators return DimensionScore even with default arguments."""
    evaluators = [
        SourceCoverageEvaluator(),
        DataCompletenessEvaluator(),
        CollectionThroughputEvaluator(),
    ]
    for evaluator in evaluators:
        score = evaluator.evaluate()
        assert isinstance(score, DimensionScore)
        assert isinstance(score.value, float)
        assert isinstance(score.max_value, float)
        assert isinstance(score.metadata, dict)
        assert score.name != ""
