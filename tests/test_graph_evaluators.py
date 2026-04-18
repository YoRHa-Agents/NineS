"""Tests for graph-based self-eval dimensions (D21-D24)."""

from __future__ import annotations

import pytest

from nines.iteration.graph_evaluators import (
    GraphDecompositionCoverageEvaluator,
    GraphVerificationPassRateEvaluator,
    LayerAssignmentQualityEvaluator,
    SummaryCompletenessEvaluator,
)


@pytest.fixture()
def sample_project(tmp_path):
    """Create a minimal Python project for evaluation."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("def main():\n    pass\n")
    (src / "utils.py").write_text("def helper():\n    return 1\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("def test_main():\n    assert True\n")
    (tmp_path / "config.yaml").write_text("key: value\n")
    (tmp_path / "README.md").write_text("# Project\n")
    return tmp_path


class TestGraphDecompositionCoverageEvaluator:
    def test_evaluate_sample_project(self, sample_project):
        ev = GraphDecompositionCoverageEvaluator(sample_project)
        score = ev.evaluate()
        assert score.name == "graph_decomposition_coverage"
        assert 0.0 <= score.value <= 1.0
        assert score.value > 0.5

    def test_evaluate_empty_dir(self, tmp_path):
        ev = GraphDecompositionCoverageEvaluator(tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0

    def test_metadata_present(self, sample_project):
        ev = GraphDecompositionCoverageEvaluator(sample_project)
        score = ev.evaluate()
        assert "scanned_files" in score.metadata
        assert "graph_file_nodes" in score.metadata


class TestGraphVerificationPassRateEvaluator:
    def test_evaluate_sample_project(self, sample_project):
        ev = GraphVerificationPassRateEvaluator(sample_project)
        score = ev.evaluate()
        assert score.name == "graph_verification_pass_rate"
        assert 0.0 <= score.value <= 1.0

    def test_evaluate_empty_dir(self, tmp_path):
        ev = GraphVerificationPassRateEvaluator(tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0

    def test_metadata_present(self, sample_project):
        ev = GraphVerificationPassRateEvaluator(sample_project)
        score = ev.evaluate()
        assert "passed" in score.metadata
        assert "layer_coverage_pct" in score.metadata


class TestLayerAssignmentQualityEvaluator:
    def test_evaluate_sample_project(self, sample_project):
        ev = LayerAssignmentQualityEvaluator(sample_project)
        score = ev.evaluate()
        assert score.name == "layer_assignment_quality"
        assert 0.0 <= score.value <= 1.0

    def test_evaluate_empty_dir(self, tmp_path):
        ev = LayerAssignmentQualityEvaluator(tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0

    def test_metadata_present(self, sample_project):
        ev = LayerAssignmentQualityEvaluator(sample_project)
        score = ev.evaluate()
        assert "total_layers" in score.metadata


class TestSummaryCompletenessEvaluator:
    def test_evaluate_sample_project(self, sample_project):
        ev = SummaryCompletenessEvaluator(sample_project)
        score = ev.evaluate()
        assert score.name == "summary_completeness"
        assert 0.0 <= score.value <= 1.0
        assert score.value > 0.3

    def test_evaluate_empty_dir(self, tmp_path):
        ev = SummaryCompletenessEvaluator(tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0

    def test_metadata_checks(self, sample_project):
        ev = SummaryCompletenessEvaluator(sample_project)
        score = ev.evaluate()
        assert "checks" in score.metadata
        assert "passed" in score.metadata
