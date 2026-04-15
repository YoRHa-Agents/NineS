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
from nines.analyzer.graph_decomposer import GraphDecomposer
from nines.analyzer.graph_models import (
    AnalysisSummary,
    ArchitectureLayer,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    VerificationIssue,
    VerificationResult,
)
from nines.analyzer.graph_verifier import GraphVerifier
from nines.analyzer.import_graph import ImportGraph, ImportGraphBuilder
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
from nines.analyzer.scanner import FileInfo, ProjectScanner, ScanResult
from nines.analyzer.structure import (
    DependencyMap,
    FileTypeCounts,
    PackageInfo,
    StructureAnalyzer,
    StructureReport,
)
from nines.analyzer.summarizer import AnalysisSummarizer

__all__ = [
    "AgentImpactAnalyzer",
    "AgentImpactReport",
    "AgentMechanism",
    "AnalysisPipeline",
    "AnalysisSummary",
    "AnalysisSummarizer",
    "ArchitectureLayer",
    "CONCERN_PATTERNS",
    "ClassInfo",
    "CodeReviewer",
    "ContextEconomics",
    "Decomposer",
    "DependencyMap",
    "FileInfo",
    "FileReview",
    "FileTypeCounts",
    "FunctionInfo",
    "GraphDecomposer",
    "GraphEdge",
    "GraphNode",
    "GraphVerifier",
    "ImportGraph",
    "ImportGraphBuilder",
    "ImportInfo",
    "KeyPoint",
    "KeyPointExtractor",
    "KeyPointReport",
    "KnowledgeGraph",
    "LAYER_INDICATORS",
    "PackageInfo",
    "ProjectScanner",
    "ScanResult",
    "StructureAnalyzer",
    "StructureReport",
    "VerificationIssue",
    "VerificationResult",
]
