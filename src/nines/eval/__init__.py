"""Evaluation & benchmarking (V1 vertex).

Re-exports the public API for the eval framework::

    from nines.eval import TaskDefinition, EvalRunner, ExactScorer
"""

from nines.eval.metrics import MetricCollector, ReliabilityCalculator, TaskMetrics
from nines.eval.mock_executor import DeterministicMockExecutor, MockEvaluator
from nines.eval.models import EvalResult, ScoringCriterion, TaskDefinition
from nines.eval.multi_round import MultiRoundReport, MultiRoundRunner, RoundResult
from nines.eval.runner import EvalRunner
from nines.eval.scorers import (
    CompositeScorer,
    ExactScorer,
    FuzzyScorer,
    RubricItem,
    RubricScorer,
    ScorerProtocol,
    ScorerRegistry,
)

__all__ = [
    # Models
    "EvalResult",
    "ScoringCriterion",
    "TaskDefinition",
    # Runner
    "EvalRunner",
    # Multi-round
    "MultiRoundReport",
    "MultiRoundRunner",
    "RoundResult",
    # Scorers
    "CompositeScorer",
    "ExactScorer",
    "FuzzyScorer",
    "RubricItem",
    "RubricScorer",
    "ScorerProtocol",
    "ScorerRegistry",
    # Metrics
    "MetricCollector",
    "ReliabilityCalculator",
    "TaskMetrics",
    # Mock primitives (C06 — golden test harness)
    "DeterministicMockExecutor",
    "MockEvaluator",
]
