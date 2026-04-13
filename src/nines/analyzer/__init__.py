"""Knowledge analysis & decomposition (V3 vertex).

Re-exports the public API so that consumers can write::

    from nines.analyzer import AnalysisPipeline, CodeReviewer, StructureAnalyzer, Decomposer
"""

from nines.analyzer.agent_impact import (
    AgentImpactAnalyzer,
    AgentImpactReport,
    AgentMechanism,
    ContextEconomics,
)
from nines.analyzer.decomposer import (
    CONCERN_PATTERNS,
    LAYER_INDICATORS,
    Decomposer,
)
from nines.analyzer.keypoint import (
    KeyPoint,
    KeyPointExtractor,
    KeyPointReport,
)
from nines.analyzer.pipeline import AnalysisPipeline
from nines.analyzer.reviewer import (
    ClassInfo,
    CodeReviewer,
    FileReview,
    FunctionInfo,
    ImportInfo,
)
from nines.analyzer.structure import (
    DependencyMap,
    FileTypeCounts,
    PackageInfo,
    StructureAnalyzer,
    StructureReport,
)

__all__ = [
    "AgentImpactAnalyzer",
    "AgentImpactReport",
    "AgentMechanism",
    "AnalysisPipeline",
    "CONCERN_PATTERNS",
    "ClassInfo",
    "CodeReviewer",
    "ContextEconomics",
    "Decomposer",
    "KeyPoint",
    "KeyPointExtractor",
    "KeyPointReport",
    "DependencyMap",
    "FileReview",
    "FileTypeCounts",
    "FunctionInfo",
    "ImportInfo",
    "LAYER_INDICATORS",
    "PackageInfo",
    "StructureAnalyzer",
    "StructureReport",
]
