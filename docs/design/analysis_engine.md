# Knowledge Analysis Engine Design

> **Task**: T14 — Knowledge Analysis Engine Design | **Team**: Design L3
> **Input**: `docs/research/domain_knowledge.md` (Area 2), `docs/design/requirements.md` (FR-301–FR-311)
> **Owned by**: T14
> **Last Modified**: 2026-04-11

---

## 1. Overview

The Knowledge Analysis Engine is NineS's V3 subsystem responsible for ingesting source code and repositories, parsing them into structured representations, analyzing their architecture and quality, decomposing them into atomic knowledge units, and indexing those units for retrieval. It closes the feedback triangle by producing knowledge units that feed V1 evaluation task generation (flow F5) and search queries for V2 information collection (flow F6).

### 1.1 Pipeline Summary

```
  ┌────────┐    ┌───────┐    ┌─────────┐    ┌───────────┐    ┌──────────┐    ┌───────┐
  │ Ingest │───►│ Parse │───►│ Analyze │───►│ Decompose │───►│ Abstract │───►│ Index │
  └────────┘    └───────┘    └─────────┘    └───────────┘    └──────────┘    └───────┘
       │             │             │               │                │             │
       ▼             ▼             ▼               ▼                ▼             ▼
   RawSource     ParsedFile   AnalysisReport  KnowledgeUnit   AbstractionReport KnowledgeIndex
```

Each stage is defined by a `Protocol` interface, enabling independent testing, replacement, and extension (CON-09). Stages communicate via typed intermediate artifacts stored in SQLite (CON-04).

### 1.2 Requirements Coverage

| Requirement | Pipeline Stage(s) | Section |
|-------------|-------------------|---------|
| FR-301 AST Analysis | Parse, Analyze | §3, §4 |
| FR-302 Multi-file Analysis | Analyze | §4 |
| FR-303 Structure Analysis | Analyze | §5 |
| FR-304 Architecture Detection | Analyze, Abstract | §5, §7 |
| FR-305 Functional Decomposition | Decompose | §6.1 |
| FR-306 Concern Decomposition | Decompose | §6.2 |
| FR-307 Layer Decomposition | Decompose | §6.3 |
| FR-308 Knowledge Indexing | Index | §8 |
| FR-309 Pattern Abstraction | Abstract | §7 |
| FR-310 Pipeline Orchestration | All (Orchestrator) | §2 |
| FR-311 Progress Reporting | All (Event hooks) | §2.3 |

---

## 2. Analysis Pipeline Protocol & Orchestration

### 2.1 Stage Protocol

Every pipeline stage conforms to a common protocol parameterized by input and output types. This enables the orchestrator to chain stages generically and allows any stage to be swapped without affecting others.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, TypeVar, runtime_checkable

T_In = TypeVar("T_In", contravariant=True)
T_Out = TypeVar("T_Out", covariant=True)


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class StageResult[T]:
    """Wrapper carrying a stage's output along with execution metadata."""
    status: StageStatus
    output: T | None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@runtime_checkable
class PipelineStage(Protocol[T_In, T_Out]):
    """Protocol that every analysis pipeline stage must satisfy."""

    @property
    def name(self) -> str:
        """Human-readable stage identifier (e.g. 'parse', 'analyze')."""
        ...

    def process(self, input_data: T_In) -> StageResult[T_Out]:
        """Execute the stage on a single input item."""
        ...

    def supports(self, input_data: T_In) -> bool:
        """Return True if this stage can handle the given input.

        Used by the orchestrator to skip inapplicable stages (e.g. a Python
        AST parser receiving a Rust file).
        """
        ...
```

### 2.2 Pipeline Orchestrator

The orchestrator chains stages, manages caching, isolates errors per-file (FR-310), and emits progress events (FR-311).

```python
@dataclass
class PipelineConfig:
    """Configuration for an analysis pipeline run."""
    enable_cache: bool = True
    stop_on_first_error: bool = False
    max_parallel_files: int = 4
    progress_callback: ProgressCallback | None = None


@dataclass
class PipelineProgress:
    """Payload emitted to progress_callback after each file-stage completion."""
    file: str
    stage: str
    status: StageStatus
    files_completed: int
    files_total: int
    units_extracted: int = 0
    patterns_found: int = 0


ProgressCallback = Callable[[PipelineProgress], None]


@runtime_checkable
class PipelineOrchestrator(Protocol):
    """Coordinates the end-to-end analysis flow."""

    def run(
        self,
        targets: list[Path],
        config: PipelineConfig | None = None,
    ) -> PipelineRunResult:
        """Analyze all target paths through the full pipeline.

        Single-file failures do not abort the pipeline (FR-310).
        Unchanged files are skipped when caching is enabled.
        """
        ...

    def run_incremental(
        self,
        targets: list[Path],
        since: datetime | None = None,
    ) -> PipelineRunResult:
        """Re-analyze only files modified since the given timestamp."""
        ...


@dataclass
class PipelineRunResult:
    """Aggregate result of a full pipeline execution."""
    files_processed: int
    files_skipped: int
    files_failed: int
    knowledge_units: list[KnowledgeUnit]
    analysis_reports: list[CodeReviewReport]
    structure_reports: list[StructureReport]
    abstraction_report: AbstractionReport | None
    errors: list[FileError]
    duration_ms: float


@dataclass
class FileError:
    """Structured error for a single file that failed during analysis."""
    file_path: str
    stage: str
    error_type: str
    message: str
    traceback: str | None = None
```

### 2.3 Progress Event Contract (FR-311)

The pipeline fires at least one `PipelineProgress` event per file processed, satisfying FR-311. The `progress_callback` is invoked synchronously after each file-stage pair completes. Consumers (CLI progress bars, event bus subscribers) receive `{file, stage, status}` payloads with optional counters.

---

## 3. Ingestion & Parsing Stage

### 3.1 Raw Source Model

```python
@dataclass(frozen=True)
class RawSource:
    """A source file or directory discovered during ingestion."""
    path: Path
    language: str
    size_bytes: int
    last_modified: datetime
    content_hash: str  # SHA-256 of file contents for cache invalidation


@runtime_checkable
class Ingester(Protocol):
    """Discovers and reads source files from a target path."""

    @property
    def name(self) -> str: ...

    def ingest(self, target: Path, extensions: set[str] | None = None) -> list[RawSource]:
        """Walk target path and produce RawSource items.

        Skips hidden directories, __pycache__, node_modules, and .git.
        """
        ...
```

### 3.2 Parsed File Model

```python
@dataclass
class FunctionInfo:
    """Extracted metadata for a single function or method."""
    name: str
    qualified_name: str
    lineno: int
    end_lineno: int
    args: list[str]
    return_annotation: str | None
    decorators: list[str]
    docstring: str | None
    is_async: bool
    complexity: int


@dataclass
class ClassInfo:
    """Extracted metadata for a single class definition."""
    name: str
    qualified_name: str
    lineno: int
    end_lineno: int
    bases: list[str]
    methods: list[FunctionInfo]
    class_variables: list[str]
    docstring: str | None
    is_abstract: bool


@dataclass
class ImportInfo:
    """A single import statement."""
    module: str
    names: list[str]
    is_relative: bool
    lineno: int


@dataclass
class ParsedFile:
    """Complete parse result for a single source file."""
    source: RawSource
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    imports: list[ImportInfo]
    module_docstring: str | None
    total_lines: int
    blank_lines: int
    comment_lines: int
    parse_errors: list[str]


@runtime_checkable
class Parser(Protocol):
    """Parses raw source into structured representations."""

    @property
    def name(self) -> str: ...

    def process(self, input_data: RawSource) -> StageResult[ParsedFile]:
        """Parse a single source file using Python's ast module (FR-301)."""
        ...

    def supports(self, input_data: RawSource) -> bool:
        """True for Python files; extensible to other languages."""
        ...
```

### 3.3 Python Parser Implementation Notes

The parser uses Python's built-in `ast` module (CON-01, zero-dependency per domain knowledge §2.1):

- `ast.parse()` with `type_comments=True` for PEP 484 comment-style annotations
- `ast.NodeVisitor` subclass extracts functions, classes, and imports in a single pass
- Cyclomatic complexity computed via McCabe method: count `If`, `While`, `For`, `ExceptHandler`, `BoolOp`, `Assert`, `With` nodes + 1
- Syntax errors produce a `ParsedFile` with `parse_errors` populated (FR-310 error isolation)

---

## 4. Code Reviewer (FR-301, FR-302)

### 4.1 Code Review Report Model

```python
@dataclass
class ComplexityDistribution:
    """Histogram of function complexities across a codebase."""
    low: int       # complexity 1-5
    medium: int    # complexity 6-10
    high: int      # complexity 11-20
    very_high: int # complexity 21+


@dataclass
class DependencyEdge:
    """A single dependency relationship between two modules."""
    source_module: str
    target_module: str
    import_names: list[str]


@dataclass
class CouplingMetrics:
    """Coupling metrics for a single module."""
    module: str
    afferent_coupling: int   # Ca: number of modules that depend on this one
    efferent_coupling: int   # Ce: number of modules this one depends on
    instability: float       # I = Ce / (Ca + Ce); 0.0 = maximally stable


@dataclass
class PatternMatch:
    """A detected code pattern with confidence."""
    pattern_name: str
    location: str
    confidence: float     # [0.0, 1.0]
    evidence: list[str]


@dataclass
class CodeReviewReport:
    """Output of the code review stage for a single file or project."""
    target_path: str
    language: str
    total_files: int
    total_lines: int
    total_functions: int
    total_classes: int

    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    imports: list[ImportInfo]

    complexity_distribution: ComplexityDistribution
    avg_complexity: float
    max_complexity_function: FunctionInfo | None

    dependencies: list[DependencyEdge]
    coupling_metrics: list[CouplingMetrics]
    detected_patterns: list[PatternMatch]

    review_timestamp: datetime = field(default_factory=datetime.utcnow)
```

### 4.2 Code Reviewer Protocol

```python
@runtime_checkable
class CodeReviewer(Protocol):
    """AST-based code review producing quality and structure metrics."""

    @property
    def name(self) -> str: ...

    def review_file(self, parsed: ParsedFile) -> StageResult[CodeReviewReport]:
        """Review a single parsed file."""
        ...

    def review_project(
        self,
        parsed_files: list[ParsedFile],
        project_root: Path,
    ) -> StageResult[CodeReviewReport]:
        """Multi-file review with cross-file dependency analysis (FR-302).

        Resolves intra-project imports, constructs the dependency adjacency
        list, and computes coupling metrics: Ca, Ce, I = Ce/(Ca+Ce).
        """
        ...

    def process(self, input_data: list[ParsedFile]) -> StageResult[CodeReviewReport]:
        """PipelineStage-compatible entry point."""
        ...

    def supports(self, input_data: list[ParsedFile]) -> bool: ...
```

### 4.3 Dependency Resolution Algorithm

Cross-file import resolution (FR-302) builds an adjacency list `dict[str, set[str]]`:

1. Map each `.py` file to its module name by converting the relative path (e.g., `app/services/auth.py` → `app.services.auth`).
2. Walk `ast.Import` and `ast.ImportFrom` nodes in each file.
3. For each imported name, check if it matches or is a prefix of any project-internal module.
4. Record `DependencyEdge(source, target, names)` for each match.

Coupling metrics are derived from the adjacency list:
- **Ca** (afferent): count of other modules whose edge set contains this module
- **Ce** (efferent): count of this module's outgoing edges
- **Instability index**: `I = Ce / (Ca + Ce)`, with `I = 0.0` when both are zero

---

## 5. Structure Analyzer (FR-303, FR-304)

### 5.1 Structure Report Model

```python
@dataclass
class DirectoryNode:
    """A node in the project directory tree."""
    name: str
    path: Path
    is_package: bool          # __init__.py present
    children: list[DirectoryNode]
    py_file_count: int
    total_lines: int


class ArchitecturalLayer(Enum):
    PRESENTATION = "presentation"
    APPLICATION = "application"
    DOMAIN = "domain"
    INFRASTRUCTURE = "infrastructure"
    TESTING = "testing"
    UNCLASSIFIED = "unclassified"


@dataclass
class LayerAssignment:
    """Maps a directory to its detected architectural layer."""
    directory: Path
    layer: ArchitecturalLayer
    confidence: float          # [0.0, 1.0]
    matching_indicators: list[str]


@dataclass
class ArchitectureSignal:
    """A detected architectural pattern with supporting evidence."""
    pattern: str               # e.g. "MVC", "Hexagonal", "Layered"
    confidence: float
    evidence: list[str]


@dataclass
class CohesionMetrics:
    """Module-level cohesion measurement."""
    module: str
    internal_references: int   # symbols used within the same module
    total_symbols: int
    lcom: float                # Lack of Cohesion of Methods (lower is better)


@dataclass
class StructureReport:
    """Output of structure analysis for a project."""
    project_root: str
    directory_tree: DirectoryNode
    total_packages: int
    total_modules: int

    layer_assignments: list[LayerAssignment]
    architecture_signals: list[ArchitectureSignal]
    coupling_metrics: list[CouplingMetrics]
    cohesion_metrics: list[CohesionMetrics]

    dependency_graph: dict[str, set[str]]
    circular_dependencies: list[list[str]]

    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)
```

### 5.2 Structure Analyzer Protocol

```python
LAYER_INDICATORS: dict[ArchitecturalLayer, set[str]] = {
    ArchitecturalLayer.PRESENTATION: {
        "cli", "api", "web", "ui", "views", "routes",
        "endpoints", "handlers", "controllers",
    },
    ArchitecturalLayer.APPLICATION: {
        "services", "usecases", "commands", "orchestrator",
        "workflows", "application",
    },
    ArchitecturalLayer.DOMAIN: {
        "models", "entities", "domain", "core", "types", "schemas",
    },
    ArchitecturalLayer.INFRASTRUCTURE: {
        "db", "database", "repos", "repositories", "adapters",
        "clients", "storage", "external", "infrastructure",
    },
    ArchitecturalLayer.TESTING: {
        "tests", "test", "fixtures", "conftest", "mocks",
    },
}


@runtime_checkable
class StructureAnalyzer(Protocol):
    """Analyzes repository layout, detects layers and architecture patterns."""

    @property
    def name(self) -> str: ...

    def analyze(
        self,
        project_root: Path,
        dependency_graph: dict[str, set[str]],
    ) -> StageResult[StructureReport]:
        """Analyze project structure (FR-303, FR-304).

        1. Build directory tree with code distribution metrics.
        2. Classify directories into architectural layers using
           LAYER_INDICATORS name matching.
        3. Detect architecture patterns (MVC, Hexagonal, Layered,
           Microservices, Plugin/Extension) via multi-signal heuristics.
        4. Detect circular dependencies via Tarjan's SCC algorithm.
        5. Compute per-module cohesion metrics.
        """
        ...

    def process(self, input_data: tuple[Path, dict[str, set[str]]]) -> StageResult[StructureReport]:
        """PipelineStage-compatible entry point."""
        ...

    def supports(self, input_data: tuple[Path, dict[str, set[str]]]) -> bool: ...
```

### 5.3 Architecture Pattern Detection

Detection uses multi-signal heuristics with confidence scoring (FR-304). Each pattern detector returns an `ArchitectureSignal` only when confidence exceeds 0.5.

| Pattern | Detection Signals | Confidence Formula |
|---------|------------------|--------------------|
| MVC | Presence of `models/`, `views/`, `controllers/` directories | `overlap_count / 3` |
| Hexagonal | Presence of `ports/`, `adapters/`, `domain/`, `core/` | `overlap_count / 4` |
| Layered | Presence of `presentation/`, `application/`, `domain/`, `infrastructure/` | `overlap_count / 4` |
| Microservices | Multiple `*service*` directories + docker-compose | `min(1.0, svc_count × 0.3 + 0.3 if docker)` |
| Plugin/Extension | ≥3 `Protocol`-based classes in the codebase | `min(1.0, protocol_count × 0.15)` |

### 5.4 Circular Dependency Detection

Circular dependencies are detected using Tarjan's strongly-connected-components algorithm on the module dependency graph. Any SCC with more than one node is reported in `StructureReport.circular_dependencies`.

---

## 6. Decomposer (FR-305, FR-306, FR-307)

The decomposer transforms analyzed code into atomic `KnowledgeUnit` instances using one of three strategies. Each strategy produces a different view of the same codebase, and all three can run in a single pipeline pass.

### 6.1 Knowledge Unit Model

```python
class KnowledgeUnitType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    PATTERN = "pattern"
    CONCERN = "concern"
    LAYER = "layer"


class AbstractionLevel(Enum):
    CONCRETE = "concrete"
    INTERFACE = "interface"
    CONCEPT = "concept"


@dataclass
class KnowledgeUnit:
    """Atomic unit of extracted knowledge. The fundamental output of decomposition."""
    id: str                          # e.g. "path/to/file.py::ClassName.method_name"
    name: str
    unit_type: KnowledgeUnitType
    abstraction_level: AbstractionLevel
    source_path: str
    line_range: tuple[int, int]
    language: str

    description: str                 # docstring or inferred summary
    signature: str                   # function signature or class declaration
    dependencies: list[str]          # IDs of units this one depends on
    tags: list[str]                  # inferred semantic tags

    complexity: int | None = None
    parent_id: str | None = None     # for tree structure (class → method)
    metadata: dict[str, str] = field(default_factory=dict)

    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DecompositionTree:
    """Hierarchical arrangement of knowledge units.

    Root nodes are modules, children are classes/functions, and
    leaf nodes are individual methods. This preserves the structural
    context lost in a flat unit list.
    """
    root_units: list[KnowledgeUnit]
    children: dict[str, list[KnowledgeUnit]]  # parent_id → child units
    total_units: int
    strategy: str

    def walk(self) -> Iterator[KnowledgeUnit]:
        """Depth-first traversal of the decomposition tree."""
        ...

    def leaves(self) -> list[KnowledgeUnit]:
        """Return all leaf-level knowledge units."""
        ...
```

### 6.2 Decomposition Strategies

#### Strategy 1: Functional Decomposition (FR-305)

Decomposes by function/class granularity. Each function and class becomes a `KnowledgeUnit`.

```python
class DecompositionStrategy(Enum):
    FUNCTIONAL = "functional"
    CONCERN = "concern"
    LAYER = "layer"


@runtime_checkable
class Decomposer(Protocol):
    """Decomposes analyzed code into knowledge units."""

    @property
    def name(self) -> str: ...

    @property
    def strategy(self) -> DecompositionStrategy: ...

    def decompose(
        self,
        parsed_files: list[ParsedFile],
        review: CodeReviewReport | None = None,
        structure: StructureReport | None = None,
    ) -> StageResult[DecompositionTree]:
        """Decompose parsed files into a tree of KnowledgeUnits."""
        ...

    def process(self, input_data: DecomposerInput) -> StageResult[DecompositionTree]:
        """PipelineStage-compatible entry point."""
        ...

    def supports(self, input_data: DecomposerInput) -> bool: ...


@dataclass
class DecomposerInput:
    """Bundled input for the decomposition stage."""
    parsed_files: list[ParsedFile]
    review: CodeReviewReport | None = None
    structure: StructureReport | None = None
```

**Functional decomposition** produces one `KnowledgeUnit` per function and one per class, with methods nested as children:

```python
class FunctionalDecomposer:
    """Decomposes code into units at function/class granularity (FR-305)."""

    @property
    def name(self) -> str:
        return "functional"

    @property
    def strategy(self) -> DecompositionStrategy:
        return DecompositionStrategy.FUNCTIONAL

    def decompose(
        self,
        parsed_files: list[ParsedFile],
        review: CodeReviewReport | None = None,
        structure: StructureReport | None = None,
    ) -> StageResult[DecompositionTree]:
        units: list[KnowledgeUnit] = []
        children: dict[str, list[KnowledgeUnit]] = {}

        for pf in parsed_files:
            filepath = str(pf.source.path)

            for func in pf.functions:
                units.append(KnowledgeUnit(
                    id=f"{filepath}::{func.name}",
                    name=func.name,
                    unit_type=KnowledgeUnitType.FUNCTION,
                    abstraction_level=AbstractionLevel.CONCRETE,
                    source_path=filepath,
                    line_range=(func.lineno, func.end_lineno),
                    language=pf.source.language,
                    description=func.docstring or "",
                    signature=self._build_signature(func),
                    dependencies=[],
                    tags=self._infer_tags(func.name, func.docstring),
                    complexity=func.complexity,
                ))

            for cls in pf.classes:
                cls_id = f"{filepath}::{cls.name}"
                cls_unit = KnowledgeUnit(
                    id=cls_id,
                    name=cls.name,
                    unit_type=KnowledgeUnitType.CLASS,
                    abstraction_level=(
                        AbstractionLevel.INTERFACE if cls.is_abstract
                        else AbstractionLevel.CONCRETE
                    ),
                    source_path=filepath,
                    line_range=(cls.lineno, cls.end_lineno),
                    language=pf.source.language,
                    description=cls.docstring or "",
                    signature=f"class {cls.name}({', '.join(cls.bases)})",
                    dependencies=cls.bases,
                    tags=self._infer_tags(cls.name, cls.docstring),
                )
                units.append(cls_unit)

                method_units = []
                for method in cls.methods:
                    m_unit = KnowledgeUnit(
                        id=f"{cls_id}.{method.name}",
                        name=f"{cls.name}.{method.name}",
                        unit_type=KnowledgeUnitType.FUNCTION,
                        abstraction_level=AbstractionLevel.CONCRETE,
                        source_path=filepath,
                        line_range=(method.lineno, method.end_lineno),
                        language=pf.source.language,
                        description=method.docstring or "",
                        signature=self._build_signature(method),
                        dependencies=[],
                        tags=self._infer_tags(method.name, method.docstring),
                        complexity=method.complexity,
                        parent_id=cls_id,
                    )
                    method_units.append(m_unit)
                children[cls_id] = method_units

        tree = DecompositionTree(
            root_units=units,
            children=children,
            total_units=len(units) + sum(len(v) for v in children.values()),
            strategy="functional",
        )
        return StageResult(status=StageStatus.COMPLETED, output=tree)
```

#### Strategy 2: Concern-Based Decomposition (FR-306)

Groups code elements by cross-cutting concern, scanning source snippets for concern-indicator keywords.

```python
CONCERN_PATTERNS: dict[str, list[str]] = {
    "error_handling": ["except", "raise", "Error", "Exception", "try"],
    "logging":        ["logger", "logging", "log.", "LOG"],
    "validation":     ["validate", "assert", "check", "verify", "is_valid"],
    "serialization":  ["to_dict", "from_dict", "serialize", "deserialize", "json", "to_json"],
    "configuration":  ["config", "settings", "options", "defaults", "Config"],
    "io_operations":  ["read", "write", "open", "save", "load", "fetch", "request"],
    "testing":        ["test_", "assert", "mock", "fixture", "pytest"],
}


class ConcernDecomposer:
    """Groups knowledge units by cross-cutting concern (FR-306)."""

    @property
    def name(self) -> str:
        return "concern"

    @property
    def strategy(self) -> DecompositionStrategy:
        return DecompositionStrategy.CONCERN

    def decompose(
        self,
        parsed_files: list[ParsedFile],
        review: CodeReviewReport | None = None,
        structure: StructureReport | None = None,
    ) -> StageResult[DecompositionTree]:
        """Classify each function/class into a concern group.

        1. Functional-decompose first to get atomic units.
        2. For each unit, read its source snippet.
        3. Match snippet against CONCERN_PATTERNS.
        4. Assign to first matching concern or 'core_logic'.
        5. Build tree with concern groups as roots.
        """
        ...
```

Concern groups become parent `KnowledgeUnit` instances of type `KnowledgeUnitType.CONCERN`, with the matched functions and classes as children. Units not matching any pattern fall into `"core_logic"`.

#### Strategy 3: Layer-Based Decomposition (FR-307)

Assigns units to architectural layers identified by the structure analyzer.

```python
class LayerDecomposer:
    """Assigns knowledge units to architectural layers (FR-307)."""

    @property
    def name(self) -> str:
        return "layer"

    @property
    def strategy(self) -> DecompositionStrategy:
        return DecompositionStrategy.LAYER

    def decompose(
        self,
        parsed_files: list[ParsedFile],
        review: CodeReviewReport | None = None,
        structure: StructureReport | None = None,
    ) -> StageResult[DecompositionTree]:
        """Assign each unit to a layer from StructureReport.layer_assignments.

        1. Use StructureReport.layer_assignments to build a path→layer map.
        2. For each KnowledgeUnit, look up its source_path in the map.
        3. Units whose path doesn't match any layer go to UNCLASSIFIED.
        4. Build tree with ArchitecturalLayer values as root nodes.
        """
        ...
```

Every `KnowledgeUnit` is assigned to exactly one layer. Units that cannot be mapped are placed in `ArchitecturalLayer.UNCLASSIFIED`.

### 6.3 Decomposition Strategy Summary

| Strategy | Granularity | Grouping Key | Root Node Type | Use Case |
|----------|-------------|-------------|----------------|----------|
| Functional | Function/Class | Identity (each entity) | Module | Code navigation, complexity profiling |
| Concern | Function/Class | Cross-cutting keyword match | Concern group | Understanding system-wide behaviors |
| Layer | Function/Class | Directory → layer mapping | Architectural layer | Architecture validation, layer conformance |

---

## 7. Abstraction Layer (FR-304, FR-309)

The abstraction layer extracts higher-level patterns from concrete knowledge units, recognizing both design patterns and architectural patterns.

### 7.1 Abstraction Report Model

```python
class PatternCategory(Enum):
    DESIGN_PATTERN = "design_pattern"
    ARCHITECTURAL_PATTERN = "architectural_pattern"
    CODE_IDIOM = "code_idiom"
    API_CONVENTION = "api_convention"


@dataclass
class DetectedPattern:
    """A recognized pattern with its instances across the codebase."""
    name: str
    category: PatternCategory
    confidence: float                   # [0.0, 1.0]
    frequency: int                      # number of instances found
    instances: list[PatternInstance]
    structural_description: str


@dataclass
class PatternInstance:
    """A single occurrence of a detected pattern."""
    knowledge_unit_ids: list[str]       # units that participate in this instance
    location: str
    evidence: list[str]


@dataclass
class AbstractionReport:
    """Output of the abstraction stage."""
    detected_patterns: list[DetectedPattern]
    pattern_summary: dict[PatternCategory, int]

    common_signatures: list[str]        # frequently repeated function signatures
    common_import_patterns: list[str]   # frequently repeated import groupings

    abstraction_timestamp: datetime = field(default_factory=datetime.utcnow)
```

### 7.2 Abstractor Protocol

```python
@runtime_checkable
class Abstractor(Protocol):
    """Extracts higher-level patterns from knowledge units (FR-309)."""

    @property
    def name(self) -> str: ...

    def abstract(
        self,
        units: list[KnowledgeUnit],
        review: CodeReviewReport | None = None,
        structure: StructureReport | None = None,
    ) -> StageResult[AbstractionReport]:
        """Analyze knowledge units for recurring patterns.

        Design pattern detection:
        - Factory: classes with 'create'/'make'/'build' methods returning
          instances of other classes
        - Observer: classes maintaining subscriber/listener lists with
          notify/emit methods
        - Strategy: Protocol/ABC with multiple implementations selected at
          runtime
        - Adapter: classes wrapping external interfaces to conform to
          internal protocols
        - Decorator: classes/functions that wrap another callable, preserving
          its interface

        Architectural patterns: delegated to StructureAnalyzer signals.
        """
        ...

    def process(self, input_data: AbstractorInput) -> StageResult[AbstractionReport]:
        """PipelineStage-compatible entry point."""
        ...

    def supports(self, input_data: AbstractorInput) -> bool: ...


@dataclass
class AbstractorInput:
    units: list[KnowledgeUnit]
    review: CodeReviewReport | None = None
    structure: StructureReport | None = None
```

### 7.3 Pattern Detection Heuristics

| Pattern | Structural Signals | Min Confidence |
|---------|-------------------|----------------|
| Factory | Method named `create`/`make`/`build` returning a different type; OR classmethod constructors | 0.6 |
| Observer | Class with `subscribe`/`register` + `notify`/`emit` methods; list/set attribute for listeners | 0.7 |
| Strategy | Protocol/ABC base with ≥2 concrete implementations; runtime selection via constructor injection | 0.7 |
| Adapter | Class wrapping a foreign type, exposing Protocol-conformant methods | 0.6 |
| Decorator | Function/class accepting a callable and returning a callable with same signature | 0.5 |

---

## 8. Knowledge Indexer (FR-308)

### 8.1 Index Data Model

```python
@dataclass
class SearchResult:
    """A single search hit with relevance metadata."""
    unit: KnowledgeUnit
    relevance_score: float            # [0.0, 1.0]
    match_type: str                   # "keyword", "semantic", "facet"
    matched_fields: list[str]         # e.g. ["name", "description", "tags"]
    snippet: str                      # relevant excerpt from the unit


@dataclass
class SearchQuery:
    """Structured search query for the knowledge index."""
    text: str | None = None           # free-text keyword search
    tags: list[str] | None = None     # filter by tags
    unit_type: KnowledgeUnitType | None = None
    language: str | None = None
    complexity_min: int | None = None
    complexity_max: int | None = None
    abstraction_level: AbstractionLevel | None = None
    limit: int = 20
    offset: int = 0


@dataclass
class IndexStats:
    """Summary statistics for the knowledge index."""
    total_units: int
    units_by_type: dict[str, int]
    units_by_language: dict[str, int]
    units_by_abstraction: dict[str, int]
    last_updated: datetime
```

### 8.2 Knowledge Index Protocol

```python
@runtime_checkable
class KnowledgeIndex(Protocol):
    """Indexes knowledge units for search and retrieval (FR-308)."""

    def insert(self, unit: KnowledgeUnit) -> None:
        """Add or update a knowledge unit in the index.

        Upserts based on unit.id. Updates the keyword index and
        any configured semantic embeddings.
        """
        ...

    def insert_batch(self, units: list[KnowledgeUnit]) -> int:
        """Bulk insert/update. Returns count of units indexed."""
        ...

    def query(self, search: SearchQuery) -> list[SearchResult]:
        """Search the index.

        Combines keyword matching (SQLite FTS5) with faceted filtering.
        Results are ranked by relevance_score descending.

        Keyword search matches against: name, description, signature, tags.
        Faceted filters apply as AND conditions on metadata columns.
        """
        ...

    def get(self, unit_id: str) -> KnowledgeUnit | None:
        """Retrieve a single unit by its ID."""
        ...

    def update(self, unit: KnowledgeUnit) -> bool:
        """Update an existing unit. Returns False if not found."""
        ...

    def delete(self, unit_id: str) -> bool:
        """Remove a unit from the index. Returns False if not found."""
        ...

    def stats(self) -> IndexStats:
        """Return summary statistics about the index contents."""
        ...
```

### 8.3 SQLite FTS5 Implementation Design

The indexer uses SQLite (CON-04) with FTS5 for full-text keyword search:

```sql
-- Core knowledge unit storage
CREATE TABLE IF NOT EXISTS knowledge_units (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    unit_type     TEXT NOT NULL,
    abstraction   TEXT NOT NULL,
    source_path   TEXT NOT NULL,
    line_start    INTEGER NOT NULL,
    line_end      INTEGER NOT NULL,
    language      TEXT NOT NULL,
    description   TEXT,
    signature     TEXT,
    complexity    INTEGER,
    parent_id     TEXT,
    tags          TEXT,  -- JSON array
    dependencies  TEXT,  -- JSON array
    metadata      TEXT,  -- JSON object
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- Full-text search index over searchable fields
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    name,
    description,
    signature,
    tags,
    content='knowledge_units',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER knowledge_fts_insert AFTER INSERT ON knowledge_units BEGIN
    INSERT INTO knowledge_fts(rowid, name, description, signature, tags)
    VALUES (new.rowid, new.name, new.description, new.signature, new.tags);
END;

CREATE TRIGGER knowledge_fts_delete AFTER DELETE ON knowledge_units BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, name, description, signature, tags)
    VALUES ('delete', old.rowid, old.name, old.description, old.signature, old.tags);
END;

CREATE TRIGGER knowledge_fts_update AFTER UPDATE ON knowledge_units BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, name, description, signature, tags)
    VALUES ('delete', old.rowid, old.name, old.description, old.signature, old.tags);
    INSERT INTO knowledge_fts(rowid, name, description, signature, tags)
    VALUES (new.rowid, new.name, new.description, new.signature, new.tags);
END;

-- Faceted filtering indexes
CREATE INDEX IF NOT EXISTS idx_units_type ON knowledge_units(unit_type);
CREATE INDEX IF NOT EXISTS idx_units_language ON knowledge_units(language);
CREATE INDEX IF NOT EXISTS idx_units_complexity ON knowledge_units(complexity);
CREATE INDEX IF NOT EXISTS idx_units_abstraction ON knowledge_units(abstraction);
CREATE INDEX IF NOT EXISTS idx_units_parent ON knowledge_units(parent_id);
```

### 8.4 Query Execution

Keyword search uses FTS5's `MATCH` with BM25 ranking. Faceted filters are applied as WHERE conditions on the join:

```python
def _build_query(self, search: SearchQuery) -> tuple[str, list[Any]]:
    """Build SQL query combining FTS5 keyword search with faceted filters."""
    params: list[Any] = []

    if search.text:
        sql = """
            SELECT ku.*, fts.rank AS relevance
            FROM knowledge_fts fts
            JOIN knowledge_units ku ON ku.rowid = fts.rowid
            WHERE knowledge_fts MATCH ?
        """
        params.append(search.text)
    else:
        sql = """
            SELECT ku.*, 1.0 AS relevance
            FROM knowledge_units ku
            WHERE 1=1
        """

    if search.unit_type is not None:
        sql += " AND ku.unit_type = ?"
        params.append(search.unit_type.value)

    if search.language is not None:
        sql += " AND ku.language = ?"
        params.append(search.language)

    if search.complexity_min is not None:
        sql += " AND ku.complexity >= ?"
        params.append(search.complexity_min)

    if search.complexity_max is not None:
        sql += " AND ku.complexity <= ?"
        params.append(search.complexity_max)

    if search.abstraction_level is not None:
        sql += " AND ku.abstraction = ?"
        params.append(search.abstraction_level.value)

    if search.tags:
        for tag in search.tags:
            sql += " AND ku.tags LIKE ?"
            params.append(f"%{tag}%")

    if search.text:
        sql += " ORDER BY fts.rank"
    else:
        sql += " ORDER BY ku.name"

    sql += " LIMIT ? OFFSET ?"
    params.extend([search.limit, search.offset])

    return sql, params
```

### 8.5 Optional Semantic Search Extension

For richer similarity queries beyond keyword matching, an optional semantic layer can be added without changing the `KnowledgeIndex` protocol:

```python
@runtime_checkable
class SemanticSearchProvider(Protocol):
    """Optional semantic embedding-based search."""

    def embed(self, text: str) -> list[float]:
        """Produce a dense vector embedding for the given text."""
        ...

    def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Return (unit_id, cosine_similarity) pairs."""
        ...

    def index_unit(self, unit_id: str, text: str) -> None:
        """Add a unit's text to the semantic index."""
        ...
```

This is deferred to post-MVP as an optional enhancement. The keyword + faceted approach satisfies FR-308 for MVP.

---

## 9. Knowledge Graph (Relationship Model)

### 9.1 Graph Model

The knowledge graph captures relationships between knowledge units that go beyond the decomposition tree hierarchy.

```python
class RelationshipType(Enum):
    DEPENDS_ON = "depends_on"       # A imports/uses B
    CONTAINS = "contains"           # A is parent of B (module→class, class→method)
    SIMILAR_TO = "similar_to"       # A and B have similar structure/purpose
    EVOLVED_FROM = "evolved_from"   # A is a newer version of B (cross-analysis)
    IMPLEMENTS = "implements"       # A implements protocol/interface B
    TESTED_BY = "tested_by"         # A is tested by test unit B


@dataclass(frozen=True)
class KnowledgeEdge:
    """A directed relationship between two knowledge units."""
    source_id: str
    target_id: str
    relationship: RelationshipType
    weight: float = 1.0             # relationship strength [0.0, 1.0]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class GraphQueryResult:
    """Result of a graph traversal query."""
    nodes: list[KnowledgeUnit]
    edges: list[KnowledgeEdge]
    depth: int
```

### 9.2 Knowledge Graph Protocol

```python
@runtime_checkable
class KnowledgeGraph(Protocol):
    """Graph of relationships between knowledge units, stored in SQLite."""

    def add_edge(self, edge: KnowledgeEdge) -> None:
        """Add a relationship. Upserts on (source, target, relationship)."""
        ...

    def add_edges_batch(self, edges: list[KnowledgeEdge]) -> int:
        """Bulk edge insertion. Returns count added."""
        ...

    def get_neighbors(
        self,
        unit_id: str,
        relationship: RelationshipType | None = None,
        direction: str = "outgoing",  # "outgoing", "incoming", "both"
    ) -> list[KnowledgeEdge]:
        """Find direct neighbors of a unit, optionally filtered by type."""
        ...

    def get_subgraph(
        self,
        root_id: str,
        max_depth: int = 3,
        relationship_types: set[RelationshipType] | None = None,
    ) -> GraphQueryResult:
        """BFS traversal from root up to max_depth hops."""
        ...

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[KnowledgeEdge] | None:
        """Find shortest path between two units. Returns None if unreachable."""
        ...

    def get_clusters(
        self,
        relationship_type: RelationshipType = RelationshipType.DEPENDS_ON,
        min_cluster_size: int = 3,
    ) -> list[list[str]]:
        """Identify clusters of tightly connected units (connected components)."""
        ...

    def remove_edge(self, source_id: str, target_id: str, relationship: RelationshipType) -> bool:
        """Remove a specific edge. Returns False if not found."""
        ...

    def stats(self) -> GraphStats:
        """Return summary statistics about the graph."""
        ...


@dataclass
class GraphStats:
    total_nodes: int
    total_edges: int
    edges_by_type: dict[str, int]
    avg_out_degree: float
    max_out_degree: int
    connected_components: int
```

### 9.3 SQLite Storage Schema

```sql
CREATE TABLE IF NOT EXISTS knowledge_edges (
    source_id     TEXT NOT NULL,
    target_id     TEXT NOT NULL,
    relationship  TEXT NOT NULL,
    weight        REAL NOT NULL DEFAULT 1.0,
    metadata      TEXT,  -- JSON object
    created_at    TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, relationship),
    FOREIGN KEY (source_id) REFERENCES knowledge_units(id),
    FOREIGN KEY (target_id) REFERENCES knowledge_units(id)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON knowledge_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON knowledge_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON knowledge_edges(relationship);
```

### 9.4 Edge Population

Edges are populated automatically from analysis results:

| Relationship | Source | Population Rule |
|-------------|--------|-----------------|
| `DEPENDS_ON` | Dependency graph | One edge per resolved import between internal modules |
| `CONTAINS` | Decomposition tree | One edge per parent→child relationship |
| `SIMILAR_TO` | Abstraction layer | Units sharing the same detected pattern |
| `EVOLVED_FROM` | Re-analysis | When a unit's content_hash changes between analysis runs |
| `IMPLEMENTS` | Class bases | When a class lists a Protocol/ABC in its bases |
| `TESTED_BY` | Naming convention | When a test function name matches `test_<function_name>` |

---

## 10. Error Handling

All analysis engine errors derive from `NinesError` → `AnalysisError` (NFR-20):

```python
class AnalysisError(NinesError):
    """Base for all analysis engine errors."""
    pass

class ParseError(AnalysisError):
    """Source file could not be parsed (syntax error, encoding error)."""
    def __init__(self, file_path: str, message: str, lineno: int | None = None):
        self.file_path = file_path
        self.lineno = lineno
        super().__init__(f"Parse error in {file_path}:{lineno}: {message}")

class AnalysisPipelineError(AnalysisError):
    """A pipeline stage failed fatally."""
    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(f"Pipeline stage '{stage}' failed: {message}")

class IndexError(AnalysisError):
    """Knowledge index operation failed."""
    pass

class GraphError(AnalysisError):
    """Knowledge graph operation failed."""
    pass
```

Per NFR-21, no exceptions are silently swallowed. Every `except` block either logs and re-raises, or populates `FileError` / `StageResult.error` with structured information.

---

## 11. Data Flow Integration

### 11.1 Pipeline Stage Data Flow

```
 Ingester                  Parser                CodeReviewer
 ────────                  ──────                ────────────
 Path → list[RawSource]    RawSource → ParsedFile    list[ParsedFile] → CodeReviewReport
                                                          │
                                                          ▼
                    StructureAnalyzer                 Decomposer (×3 strategies)
                    ─────────────────                 ──────────
                    (Path, dep_graph) → StructureReport    (ParsedFiles, Review, Structure)
                                                          → DecompositionTree
                                                          │
                                                          ▼
                    Abstractor                        KnowledgeIndex
                    ──────────                        ──────────────
                    (Units, Review, Structure)         Units → insert_batch()
                    → AbstractionReport               SearchQuery → list[SearchResult]
                                                          │
                                                          ▼
                                                    KnowledgeGraph
                                                    ──────────────
                                                    Edges from deps, tree, patterns
```

### 11.2 Cross-Vertex Integration Points

| Flow | Producer | Consumer | Artifact |
|------|----------|----------|----------|
| F5: V3 → V1 | KnowledgeIndex | Evaluation task generator | `KnowledgeUnit` instances as task candidates |
| F6: V3 → V2 | Abstractor | Search query generator | Knowledge gaps → search queries |
| F3: V2 → V3 | Collection store | PipelineOrchestrator | Collected repo paths as analysis targets |

---

## 12. Acceptance Criteria Verification

| Criterion | Satisfied | Evidence |
|-----------|-----------|----------|
| Pipeline stages have Protocol interfaces | Yes | §2.1 `PipelineStage`, §3.2 `Parser`, §4.2 `CodeReviewer`, §5.2 `StructureAnalyzer`, §6.2 `Decomposer`, §7.2 `Abstractor`, §8.2 `KnowledgeIndex` |
| At least 3 decomposition strategies defined | Yes | §6.2: Functional (FR-305), Concern-based (FR-306), Layer-based (FR-307) |
| Knowledge indexer has query interface design | Yes | §8.2 `KnowledgeIndex.query()`, §8.4 query execution with FTS5 + faceted filtering |

---

*Last modified: 2026-04-11T00:00:00Z*
