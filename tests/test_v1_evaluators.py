"""Tests for nines.iteration.v1_evaluators — V1 scoring dimension evaluators.

Covers:
  - ScoringAccuracyEvaluator (D01) validates scoring against golden test set
  - ReliabilityEvaluator (D03) checks deterministic scoring consistency
  - ScorerAgreementEvaluator (D05) measures ExactScorer/FuzzyScorer agreement
  - All evaluators conform to the DimensionEvaluator protocol
  - Golden task loading works correctly
  - Error handling for missing/empty directories
  - Runner integration
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.self_eval import DimensionEvaluator, DimensionScore
from nines.iteration.v1_evaluators import (
    ReliabilityEvaluator,
    ScorerAgreementEvaluator,
    ScoringAccuracyEvaluator,
    load_golden_tasks,
)

GOLDEN_DIR = Path("data/golden_test_set")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls",
    [ScoringAccuracyEvaluator, ReliabilityEvaluator, ScorerAgreementEvaluator],
)
def test_protocol_conformance(cls: type) -> None:
    """Every evaluator satisfies the DimensionEvaluator protocol."""
    inst = cls()
    assert isinstance(inst, DimensionEvaluator)


# ---------------------------------------------------------------------------
# load_golden_tasks
# ---------------------------------------------------------------------------


def test_load_golden_tasks_from_real_dir() -> None:
    """Golden tasks load from the real data/golden_test_set directory."""
    tasks = load_golden_tasks(GOLDEN_DIR)
    assert len(tasks) >= 5
    for task in tasks:
        assert "id" in task
        assert "source" in task
        assert "expected" in task
        assert "expected_score" in task
        assert "scorer" in task


def test_load_golden_tasks_missing_dir(tmp_path: Path) -> None:
    """Returns empty list for a non-existent directory."""
    tasks = load_golden_tasks(tmp_path / "nonexistent")
    assert tasks == []


def test_load_golden_tasks_empty_dir(tmp_path: Path) -> None:
    """Returns empty list for a directory with no TOML files."""
    tasks = load_golden_tasks(tmp_path)
    assert tasks == []


def test_load_golden_tasks_skips_no_golden_section(tmp_path: Path) -> None:
    """Files without [task.golden] are silently skipped."""
    (tmp_path / "no_golden.toml").write_text(
        '[task]\nid = "t1"\n[task.input]\nsource = "x"\n[task.expected]\nvalue = "y"\n'
    )
    tasks = load_golden_tasks(tmp_path)
    assert tasks == []


def test_load_golden_tasks_skips_malformed(tmp_path: Path) -> None:
    """Malformed TOML files are skipped without crashing."""
    (tmp_path / "bad.toml").write_text("this is [[[ not valid toml")
    tasks = load_golden_tasks(tmp_path)
    assert tasks == []


def _write_golden_task(
    directory: Path,
    name: str,
    source: str,
    expected: str,
    expected_score: float,
    scorer: str = "exact",
) -> Path:
    """Helper to write a minimal golden task TOML file."""
    content = (
        f'[task]\nid = "{name}"\nname = "{name}"\n'
        f'dimension = "test"\ndifficulty = 1\n\n'
        f'[task.input]\ntype = "code"\nlanguage = "python"\n'
        f'source = "{source}"\n\n'
        f'[task.expected]\ntype = "text"\nvalue = "{expected}"\n\n'
        f"[task.golden]\nexpected_score = {expected_score}\n"
        f'scorer = "{scorer}"\n'
    )
    path = directory / f"{name}.toml"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# ScoringAccuracyEvaluator (D01)
# ---------------------------------------------------------------------------


def test_scoring_accuracy_with_real_golden_set() -> None:
    """ScoringAccuracyEvaluator loads real golden tasks and produces a score."""
    evaluator = ScoringAccuracyEvaluator(golden_dir=GOLDEN_DIR)
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "scoring_accuracy"
    assert score.max_value == 1.0
    assert 0.0 <= score.value <= 1.0
    assert score.metadata["total_tasks"] >= 5


def test_scoring_accuracy_all_match(tmp_path: Path) -> None:
    """Accuracy is 1.0 when all scores match golden expectations."""
    _write_golden_task(tmp_path, "t1", "hello", "hello", 1.0)
    _write_golden_task(tmp_path, "t2", "foo", "bar", 0.0)

    evaluator = ScoringAccuracyEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 1.0
    assert score.metadata["accurate_tasks"] == 2
    assert score.metadata["total_tasks"] == 2


def test_scoring_accuracy_partial_match(tmp_path: Path) -> None:
    """Accuracy reflects correct fraction when some scores mismatch."""
    _write_golden_task(tmp_path, "t1", "hello", "hello", 1.0)
    _write_golden_task(tmp_path, "t2", "foo", "bar", 1.0)

    evaluator = ScoringAccuracyEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 0.5
    assert score.metadata["accurate_tasks"] == 1


def test_scoring_accuracy_missing_dir(tmp_path: Path) -> None:
    """Score is 0.0 when golden directory doesn't exist."""
    evaluator = ScoringAccuracyEvaluator(golden_dir=tmp_path / "nope")
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


def test_scoring_accuracy_fuzzy_scorer(tmp_path: Path) -> None:
    """Fuzzy scorer golden tasks are handled correctly."""
    _write_golden_task(tmp_path, "t1", "hello world", "hello world", 1.0, scorer="fuzzy")

    evaluator = ScoringAccuracyEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 1.0


# ---------------------------------------------------------------------------
# ReliabilityEvaluator (D03)
# ---------------------------------------------------------------------------


def test_reliability_with_real_golden_set() -> None:
    """ReliabilityEvaluator loads real golden tasks and checks consistency."""
    evaluator = ReliabilityEvaluator(golden_dir=GOLDEN_DIR)
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "scoring_reliability"
    assert score.max_value == 1.0
    assert score.value == 1.0, "ExactScorer should be perfectly deterministic"
    assert score.metadata["runs_per_task"] == 3


def test_reliability_all_consistent(tmp_path: Path) -> None:
    """Consistency is 1.0 when all repeat runs agree."""
    _write_golden_task(tmp_path, "t1", "ok", "ok", 1.0)
    _write_golden_task(tmp_path, "t2", "x", "y", 0.0)

    evaluator = ReliabilityEvaluator(golden_dir=tmp_path, runs=3)
    score = evaluator.evaluate()

    assert score.value == 1.0
    assert score.metadata["consistent_tasks"] == 2


def test_reliability_missing_dir(tmp_path: Path) -> None:
    """Score is 0.0 when golden directory doesn't exist."""
    evaluator = ReliabilityEvaluator(golden_dir=tmp_path / "nope")
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


def test_reliability_respects_max_tasks(tmp_path: Path) -> None:
    """Only processes up to max_tasks."""
    for i in range(10):
        _write_golden_task(tmp_path, f"t{i}", "a", "a", 1.0)

    evaluator = ReliabilityEvaluator(golden_dir=tmp_path, max_tasks=3)
    score = evaluator.evaluate()

    assert score.metadata["total_tasks"] == 3


# ---------------------------------------------------------------------------
# ScorerAgreementEvaluator (D05)
# ---------------------------------------------------------------------------


def test_scorer_agreement_with_real_golden_set() -> None:
    """ScorerAgreementEvaluator loads real golden tasks and computes agreement."""
    evaluator = ScorerAgreementEvaluator(golden_dir=GOLDEN_DIR)
    score = evaluator.evaluate()

    assert isinstance(score, DimensionScore)
    assert score.name == "scorer_agreement"
    assert score.max_value == 1.0
    assert 0.0 <= score.value <= 1.0
    assert score.metadata["total_tasks"] >= 5


def test_scorer_agreement_perfect_match(tmp_path: Path) -> None:
    """Agreement is 1.0 when both scorers agree on all tasks."""
    _write_golden_task(tmp_path, "t1", "same", "same", 1.0)
    _write_golden_task(tmp_path, "t2", "x", "y", 0.0)

    evaluator = ScorerAgreementEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    assert score.value == 1.0
    assert score.metadata["agreed_tasks"] == 2


def test_scorer_agreement_partial(tmp_path: Path) -> None:
    """Agreement reflects the fraction of tasks where scorers agree."""
    _write_golden_task(tmp_path, "t1", "same", "same", 1.0)
    _write_golden_task(tmp_path, "t2", "abc", "abd", 0.0)

    evaluator = ScorerAgreementEvaluator(golden_dir=tmp_path)
    score = evaluator.evaluate()

    details = score.metadata["details"]
    t2 = details["t2"]
    assert t2["exact_pass"] is False
    assert t2["fuzzy_pass"] is True
    assert t2["agreed"] is False
    assert score.value == 0.5


def test_scorer_agreement_missing_dir(tmp_path: Path) -> None:
    """Score is 0.0 when golden directory doesn't exist."""
    evaluator = ScorerAgreementEvaluator(golden_dir=tmp_path / "nope")
    score = evaluator.evaluate()

    assert score.value == 0.0
    assert "error" in score.metadata


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


def test_all_evaluators_return_dimension_score() -> None:
    """All evaluators return DimensionScore even with default arguments."""
    evaluators = [
        ScoringAccuracyEvaluator(),
        ReliabilityEvaluator(),
        ScorerAgreementEvaluator(),
    ]
    for evaluator in evaluators:
        score = evaluator.evaluate()
        assert isinstance(score, DimensionScore)
        assert isinstance(score.value, float)
        assert isinstance(score.max_value, float)
        assert isinstance(score.metadata, dict)
        assert score.name != ""


# ---------------------------------------------------------------------------
# Integration: register in SelfEvalRunner
# ---------------------------------------------------------------------------


def test_register_with_self_eval_runner() -> None:
    """All three evaluators can be registered and run via SelfEvalRunner."""
    from nines.iteration.self_eval import SelfEvalRunner

    runner = SelfEvalRunner()
    runner.register_dimension(
        "scoring_accuracy", ScoringAccuracyEvaluator(golden_dir=GOLDEN_DIR),
    )
    runner.register_dimension(
        "scoring_reliability", ReliabilityEvaluator(golden_dir=GOLDEN_DIR),
    )
    runner.register_dimension(
        "scorer_agreement", ScorerAgreementEvaluator(golden_dir=GOLDEN_DIR),
    )

    report = runner.run_all(version="test-v1-scoring")

    assert len(report.scores) == 3
    assert report.version == "test-v1-scoring"
    assert 0.0 <= report.overall <= 1.0

    names = {s.name for s in report.scores}
    assert names == {"scoring_accuracy", "scoring_reliability", "scorer_agreement"}
