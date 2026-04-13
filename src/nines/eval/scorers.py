"""Scorer implementations and registry for the evaluation framework.

Provides four built-in scorers:

- **ExactScorer** — binary exact-match (1.0 or 0.0)
- **FuzzyScorer** — continuous similarity via ``difflib.SequenceMatcher``
- **RubricScorer** — checklist-based scoring against named criteria
- **CompositeScorer** — weighted combination of multiple scorers

Plus ``ScorerRegistry`` for registration and lookup.

Covers: FR-103, FR-104, FR-105, FR-106.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Protocol, runtime_checkable

from nines.core.errors import EvalError
from nines.core.models import Score

logger = logging.getLogger(__name__)


@runtime_checkable
class ScorerProtocol(Protocol):
    """Protocol that all scorers must satisfy."""

    def score(self, output: Any, expected: Any) -> Score:
        """Score output against expected value."""
        ...

    def name(self) -> str:
        """Return the scorer name."""
        ...


class ExactScorer:
    """Binary exact-match comparison. Returns 1.0 on match, 0.0 otherwise."""

    def name(self) -> str:
        """Name."""
        return "exact"

    def score(self, output: Any, expected: Any) -> Score:
        """Score output against expected using exact match."""
        if expected is None:
            return Score(value=0.0, scorer_name="exact", breakdown={"reason": "no expected output"})

        actual_str = str(output).strip()
        expected_str = str(expected).strip()
        match = actual_str == expected_str

        return Score(
            value=1.0 if match else 0.0,
            scorer_name="exact",
            breakdown={"match": match},
        )


class FuzzyScorer:
    """Continuous similarity scorer using ``difflib.SequenceMatcher``.

    Produces a score in [0.0, 1.0] representing the ratio of matching
    characters between the stringified output and expected values.
    """

    def __init__(self, threshold: float = 0.0) -> None:
        """Initialize fuzzy scorer."""
        self._threshold = threshold

    def name(self) -> str:
        """Name."""
        return "fuzzy"

    def score(self, output: Any, expected: Any) -> Score:
        """Score output against expected using fuzzy match."""
        if expected is None:
            return Score(value=0.0, scorer_name="fuzzy", breakdown={"reason": "no expected output"})

        actual_str = str(output).strip()
        expected_str = str(expected).strip()
        ratio = SequenceMatcher(None, actual_str, expected_str).ratio()

        return Score(
            value=ratio,
            scorer_name="fuzzy",
            breakdown={"ratio": ratio, "above_threshold": ratio >= self._threshold},
        )


@dataclass
class RubricItem:
    """A single criterion in a rubric checklist."""

    name: str
    description: str = ""
    weight: float = 1.0
    check_fn: str = "contains"
    check_value: str = ""


class RubricScorer:
    """Checklist-based scorer evaluating output against named criteria.

    Each ``RubricItem`` is checked against the output. The final score
    is the weighted sum of satisfied criteria, normalized to [0, 1].
    """

    def __init__(self, criteria: list[RubricItem] | None = None) -> None:
        """Initialize rubric scorer."""
        self._criteria = criteria or []

    def name(self) -> str:
        """Name."""
        return "rubric"

    def score(self, output: Any, expected: Any) -> Score:
        """Score output against the rubric criteria."""
        if not self._criteria:
            return Score(value=0.0, scorer_name="rubric", breakdown={"reason": "no criteria"})

        output_str = str(output).strip().lower()
        total_weight = sum(c.weight for c in self._criteria)
        if total_weight == 0:
            return Score(value=0.0, scorer_name="rubric", breakdown={"reason": "zero weight"})

        earned = 0.0
        breakdown: dict[str, Any] = {}

        for criterion in self._criteria:
            passed = self._check_criterion(criterion, output_str)
            breakdown[criterion.name] = {"passed": passed, "weight": criterion.weight}
            if passed:
                earned += criterion.weight

        value = earned / total_weight
        return Score(
            value=value,
            scorer_name="rubric",
            breakdown=breakdown,
        )

    @staticmethod
    def _check_criterion(criterion: RubricItem, output: str) -> bool:
        """Check criterion."""
        check_val = criterion.check_value.lower()
        if criterion.check_fn == "contains":
            return check_val in output
        if criterion.check_fn == "equals":
            return output == check_val
        if criterion.check_fn == "starts_with":
            return output.startswith(check_val)
        if criterion.check_fn == "present":
            return len(output) > 0
        return False


class CompositeScorer:
    """Weighted combination of multiple scorers.

    Each sub-scorer is paired with a weight. The composite score is
    the weighted average of all sub-scorer results.
    """

    def __init__(self, scorers: list[tuple[ScorerProtocol, float]]) -> None:
        """Initialize composite scorer."""
        if not scorers:
            raise EvalError("CompositeScorer requires at least one scorer")
        self._scorers = scorers

    def name(self) -> str:
        """Name."""
        return "composite"

    def score(self, output: Any, expected: Any) -> Score:
        """Score output using weighted sub-scorers."""
        total_weight = sum(w for _, w in self._scorers)
        if total_weight == 0:
            return Score(value=0.0, scorer_name="composite", breakdown={"reason": "zero weight"})

        weighted_sum = 0.0
        breakdown: dict[str, Any] = {}

        for scorer, weight in self._scorers:
            sub_score = scorer.score(output, expected)
            weighted_sum += sub_score.value * weight
            breakdown[scorer.name()] = {
                "value": sub_score.value,
                "weight": weight,
                "weighted": sub_score.value * weight,
            }

        composite = weighted_sum / total_weight
        return Score(
            value=composite,
            scorer_name="composite",
            breakdown=breakdown,
        )


class ScorerRegistry:
    """Central registry for scorer classes.

    Supports programmatic registration and instance creation by name.
    """

    def __init__(self) -> None:
        """Initialize scorer registry."""
        self._registry: dict[str, type] = {}

    def register(self, name: str, scorer_cls: type) -> None:
        """Register a scorer class by name."""
        if name in self._registry:
            raise EvalError(f"Scorer '{name}' already registered")
        self._registry[name] = scorer_cls
        logger.debug("Registered scorer: %s -> %s", name, scorer_cls.__name__)

    def get(self, name: str, **kwargs: Any) -> ScorerProtocol:
        """Return a scorer instance by name."""
        if name not in self._registry:
            raise EvalError(
                f"Unknown scorer: '{name}'. Available: {list(self._registry.keys())}"
            )
        instance = self._registry[name](**kwargs)
        return instance  # type: ignore[return-value]

    def list_available(self) -> list[str]:
        """List available."""
        return list(self._registry.keys())

    @classmethod
    def with_builtins(cls) -> ScorerRegistry:
        """Create a registry pre-loaded with the four built-in scorers."""
        registry = cls()
        registry.register("exact", ExactScorer)
        registry.register("fuzzy", FuzzyScorer)
        registry.register("rubric", RubricScorer)
        registry.register("composite", CompositeScorer)
        return registry
