"""V1 Evaluation dimension evaluators with golden test set validation.

Implements three evaluators for the self-eval framework:
- **ScoringAccuracyEvaluator** (D01) — validates NineS scoring against golden expected scores
- **ReliabilityEvaluator** (D03) — measures deterministic scoring consistency across runs
- **ScorerAgreementEvaluator** (D05) — measures pass/fail agreement between scorers

Each evaluator conforms to the ``DimensionEvaluator`` protocol defined in
:mod:`nines.iteration.self_eval` and returns a ``DimensionScore``.

Covers: FR-602, FR-603.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

from nines.eval.scorers import ExactScorer, FuzzyScorer
from nines.iteration.self_eval import DimensionScore

logger = logging.getLogger(__name__)

__all__ = [
    "ScoringAccuracyEvaluator",
    "ReliabilityEvaluator",
    "ScorerAgreementEvaluator",
    "load_golden_tasks",
]

PASS_THRESHOLD = 0.5
TOLERANCE = 0.1


def load_golden_tasks(golden_dir: str | Path) -> list[dict[str, Any]]:
    """Load golden task definitions from TOML files in the given directory.

    Each file must contain a ``[task]`` table with at least ``id``,
    ``[task.input]`` (with ``source``), ``[task.expected]`` (with ``value``),
    and ``[task.golden]`` (with ``expected_score`` and ``scorer``).

    Returns a list of parsed task dicts or an empty list on failure.
    """
    golden_path = Path(golden_dir)
    if not golden_path.is_dir():
        logger.warning("Golden test set directory not found: %s", golden_path)
        return []

    tasks: list[dict[str, Any]] = []
    for toml_file in sorted(golden_path.glob("*.toml")):
        try:
            raw = tomllib.loads(toml_file.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError) as exc:
            logger.warning("Skipping malformed golden file %s: %s", toml_file.name, exc)
            continue

        task_data = raw.get("task", {})
        golden = task_data.get("golden")
        if not golden:
            logger.warning("Skipping %s: no [task.golden] section", toml_file.name)
            continue

        input_section = task_data.get("input", task_data.get("input_config", {}))
        expected_section = task_data.get("expected", {})
        expected_value = expected_section
        if isinstance(expected_section, dict) and "value" in expected_section:
            expected_value = expected_section["value"]

        tasks.append({
            "id": task_data.get("id", toml_file.stem),
            "source": input_section.get("source", "") if isinstance(input_section, dict) else "",
            "expected": expected_value,
            "expected_score": float(golden.get("expected_score", 0.0)),
            "scorer": golden.get("scorer", "exact"),
            "file": toml_file.name,
        })

    return tasks


def _get_scorer(scorer_name: str) -> ExactScorer | FuzzyScorer:
    """Return a scorer instance by name, defaulting to ExactScorer."""
    if scorer_name == "fuzzy":
        return FuzzyScorer()
    return ExactScorer()


class ScoringAccuracyEvaluator:
    """Evaluate NineS scoring accuracy against a golden test set (D01).

    For each golden task the evaluator treats ``input.source`` as the agent
    output, scores it against ``expected.value`` using the specified scorer,
    then compares the NineS score to the golden ``expected_score``.

    Accuracy = count(|nines_score - golden_score| <= tolerance) / total_tasks.
    """

    def __init__(
        self,
        golden_dir: str | Path = "data/golden_test_set",
        tolerance: float = TOLERANCE,
    ) -> None:
        """Initialize with the golden test set directory."""
        self._golden_dir = Path(golden_dir)
        self._tolerance = tolerance

    def evaluate(self) -> DimensionScore:
        """Load golden tasks, score each, and return accuracy."""
        tasks = load_golden_tasks(self._golden_dir)
        if not tasks:
            return DimensionScore(
                name="scoring_accuracy",
                value=0.0,
                max_value=1.0,
                metadata={"error": f"no golden tasks found in {self._golden_dir}"},
            )

        accurate = 0
        details: dict[str, Any] = {}

        for task in tasks:
            scorer = _get_scorer(task["scorer"])
            score_result = scorer.score(task["source"], task["expected"])
            nines_score = score_result.value
            golden_score = task["expected_score"]
            is_accurate = abs(nines_score - golden_score) <= self._tolerance

            if is_accurate:
                accurate += 1

            details[task["id"]] = {
                "nines_score": nines_score,
                "golden_score": golden_score,
                "delta": round(abs(nines_score - golden_score), 4),
                "accurate": is_accurate,
                "scorer": task["scorer"],
            }

        total = len(tasks)
        accuracy = accurate / total

        return DimensionScore(
            name="scoring_accuracy",
            value=round(accuracy, 4),
            max_value=1.0,
            metadata={
                "total_tasks": total,
                "accurate_tasks": accurate,
                "tolerance": self._tolerance,
                "details": details,
            },
        )


class ReliabilityEvaluator:
    """Evaluate scoring reliability / determinism (D03).

    Loads a subset of golden tasks and runs each through ExactScorer
    multiple times.  Consistency = count(all runs agree on pass/fail)
    / total_tasks, where pass = score > 0.5.
    """

    def __init__(
        self,
        golden_dir: str | Path = "data/golden_test_set",
        runs: int = 3,
        max_tasks: int = 5,
    ) -> None:
        """Initialize with golden dir, run count, and task limit."""
        self._golden_dir = Path(golden_dir)
        self._runs = max(runs, 2)
        self._max_tasks = max_tasks

    def evaluate(self) -> DimensionScore:
        """Run each golden task multiple times and check consistency."""
        tasks = load_golden_tasks(self._golden_dir)
        if not tasks:
            return DimensionScore(
                name="scoring_reliability",
                value=0.0,
                max_value=1.0,
                metadata={"error": f"no golden tasks found in {self._golden_dir}"},
            )

        subset = [t for t in tasks if t["scorer"] == "exact"][:self._max_tasks]
        if not subset:
            subset = tasks[:self._max_tasks]

        scorer = ExactScorer()
        consistent_count = 0
        details: dict[str, Any] = {}

        for task in subset:
            run_scores: list[float] = []
            for _ in range(self._runs):
                result = scorer.score(task["source"], task["expected"])
                run_scores.append(result.value)

            pass_results = [s > PASS_THRESHOLD for s in run_scores]
            all_agree = len(set(pass_results)) == 1

            if all_agree:
                consistent_count += 1

            details[task["id"]] = {
                "scores": run_scores,
                "pass_results": pass_results,
                "consistent": all_agree,
            }

        total = len(subset)
        consistency = consistent_count / total

        return DimensionScore(
            name="scoring_reliability",
            value=round(consistency, 4),
            max_value=1.0,
            metadata={
                "total_tasks": total,
                "consistent_tasks": consistent_count,
                "runs_per_task": self._runs,
                "details": details,
            },
        )


class ScorerAgreementEvaluator:
    """Evaluate pass/fail agreement between ExactScorer and FuzzyScorer (D05).

    For each golden task, both scorers produce a score. A task "passes"
    if score > 0.5.  Agreement = count(both agree on pass/fail) / total.
    """

    def __init__(self, golden_dir: str | Path = "data/golden_test_set") -> None:
        """Initialize with the golden test set directory."""
        self._golden_dir = Path(golden_dir)

    def evaluate(self) -> DimensionScore:
        """Score all golden tasks with both scorers and measure agreement."""
        tasks = load_golden_tasks(self._golden_dir)
        if not tasks:
            return DimensionScore(
                name="scorer_agreement",
                value=0.0,
                max_value=1.0,
                metadata={"error": f"no golden tasks found in {self._golden_dir}"},
            )

        exact_scorer = ExactScorer()
        fuzzy_scorer = FuzzyScorer()
        agree_count = 0
        details: dict[str, Any] = {}

        for task in tasks:
            exact_result = exact_scorer.score(task["source"], task["expected"])
            fuzzy_result = fuzzy_scorer.score(task["source"], task["expected"])

            exact_pass = exact_result.value > PASS_THRESHOLD
            fuzzy_pass = fuzzy_result.value > PASS_THRESHOLD
            agreed = exact_pass == fuzzy_pass

            if agreed:
                agree_count += 1

            details[task["id"]] = {
                "exact_score": exact_result.value,
                "fuzzy_score": round(fuzzy_result.value, 4),
                "exact_pass": exact_pass,
                "fuzzy_pass": fuzzy_pass,
                "agreed": agreed,
            }

        total = len(tasks)
        agreement = agree_count / total

        return DimensionScore(
            name="scorer_agreement",
            value=round(agreement, 4),
            max_value=1.0,
            metadata={
                "total_tasks": total,
                "agreed_tasks": agree_count,
                "pass_threshold": PASS_THRESHOLD,
                "details": details,
            },
        )
