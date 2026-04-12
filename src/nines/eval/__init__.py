"""Evaluation & benchmarking (V1 vertex).

Re-exports the public API for the eval framework::

    from nines.eval import TaskDefinition, EvalRunner, ExactScorer
"""

from nines.eval.metrics import MetricCollector, ReliabilityCalculator, TaskMetrics
from nines.eval.models import EvalResult, ScoringCriterion, TaskDefinition
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
]
