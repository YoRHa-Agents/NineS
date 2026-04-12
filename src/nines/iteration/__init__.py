"""Self-evaluation and self-iteration (MAPIM loop)."""

from nines.iteration.baseline import BaselineManager, ComparisonResult
from nines.iteration.convergence import ConvergenceChecker, ConvergenceResult
from nines.iteration.gap_detector import Gap, GapAnalysis, GapDetector
from nines.iteration.history import ScoreHistory
from nines.iteration.planner import ImprovementPlan, ImprovementPlanner, Suggestion
from nines.iteration.self_eval import (
    CodeCoverageEvaluator,
    DimensionEvaluator,
    DimensionScore,
    ModuleCountEvaluator,
    SelfEvalReport,
    SelfEvalRunner,
    TestCountEvaluator,
    UnitTestCountEvaluator,
)
from nines.iteration.tracker import IterationTracker, ProgressReport

__all__ = [
    "BaselineManager",
    "CodeCoverageEvaluator",
    "ComparisonResult",
    "ConvergenceChecker",
    "ConvergenceResult",
    "DimensionEvaluator",
    "DimensionScore",
    "Gap",
    "GapAnalysis",
    "GapDetector",
    "ImprovementPlan",
    "ImprovementPlanner",
    "IterationTracker",
    "ModuleCountEvaluator",
    "ProgressReport",
    "ScoreHistory",
    "SelfEvalReport",
    "SelfEvalRunner",
    "Suggestion",
    "TestCountEvaluator",
    "UnitTestCountEvaluator",
]
