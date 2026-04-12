"""NineS core — zero-dependency foundation layer.

Re-exports all public protocols, data models, error types, and the
event system so that consumers can write::

    from nines.core import EvalTask, Scorer, NinesError, EventBus
"""

from nines.core.errors import (
    AnalyzerError,
    CollectorError,
    ConfigError,
    EvalError,
    NinesError,
    OrchestrationError,
    SandboxError,
    SkillError,
)
from nines.core.events import (
    ANALYSIS_COMPLETE,
    COLLECTION_COMPLETE,
    EVAL_COMPLETE,
    ITERATION_COMPLETE,
    Event,
    EventBus,
)
from nines.core.models import (
    AnalysisResult,
    CollectionResult,
    EvalTask,
    ExecutionResult,
    Finding,
    KnowledgeUnit,
    Score,
    ScoreCard,
)
from nines.core.protocols import (
    Analyzer,
    Executor,
    Reporter,
    Scorer,
    SourceCollector,
    TaskLoader,
)

__all__ = [
    # Protocols
    "Analyzer",
    "Executor",
    "Reporter",
    "Scorer",
    "SourceCollector",
    "TaskLoader",
    # Models
    "AnalysisResult",
    "CollectionResult",
    "EvalTask",
    "ExecutionResult",
    "Finding",
    "KnowledgeUnit",
    "Score",
    "ScoreCard",
    # Errors
    "AnalyzerError",
    "CollectorError",
    "ConfigError",
    "EvalError",
    "NinesError",
    "OrchestrationError",
    "SandboxError",
    "SkillError",
    # Events
    "ANALYSIS_COMPLETE",
    "COLLECTION_COMPLETE",
    "EVAL_COMPLETE",
    "ITERATION_COMPLETE",
    "Event",
    "EventBus",
]
