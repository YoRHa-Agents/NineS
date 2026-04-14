---
id: "nines/references/analysis-pipeline"
version: "1.0.0"
purpose: >
  Documents the full NineS analysis pipeline architecture including
  ingestion, code review, decomposition strategies, agent-impact
  analysis, key-point extraction, and the CLI interface.
triggers:
  - "analysis"
  - "pipeline"
  - "decompose"
  - "review"
tier: 2
token_estimate: 2000
dependencies:
  - "nines/SKILL.md"
last_updated: "2026-04-14"
---

# Analysis Pipeline Reference

## 1. Pipeline Architecture

```
 ┌─────────────┐
 │ CLI: analyze │  --target-path, --strategy, --depth
 └──────┬──────┘
        ▼
 ┌──────────────┐    ┌──────────────────┐
 │   ingest()   │───▶│ Python .py files  │
 │  ingest_all()│───▶│ All agent files   │
 └──────┬───────┘    └──────────────────┘
        ▼
 ┌──────────────┐    ┌──────────────────┐
 │  analyze()   │───▶│ FileReview[]     │
 │ (CodeReviewer│    │ (AST + metrics)  │
 └──────┬───────┘    └──────────────────┘
        ▼
 ┌──────────────┐    ┌──────────────────┐
 │ decompose()  │───▶│ KnowledgeUnit[] │
 │ (strategy)   │    │ (func/concern/   │
 └──────┬───────┘    │  layer groups)   │
        ▼            └──────────────────┘
 ┌──────────────┐    ┌──────────────────┐
 │AgentImpact   │───▶│ mechanisms,      │
 │Analyzer      │    │ economics,       │
 └──────┬───────┘    │ artifacts        │
        ▼            └──────────────────┘
 ┌──────────────┐    ┌──────────────────┐
 │KeyPoint      │───▶│ prioritized      │
 │Extractor     │    │ key points       │
 └──────┬───────┘    └──────────────────┘
        ▼
 ┌──────────────┐
 │AnalysisResult│  target, findings[], metrics{}
 └──────────────┘
```

The pipeline is orchestrated by `AnalysisPipeline` in `pipeline.py`.

## 2. Ingestion

Two ingestion modes, both skip directories in `_SKIP_DIRS` (`.git`, `node_modules`, `__pycache__`, `.venv`, etc.) and hidden directories.

| Method | Files Collected | Used By |
|--------|----------------|---------|
| `ingest(target)` | `*.py` files only | Code review + decomposition |
| `ingest_all(target)` | `.py`, `.yaml`, `.yml`, `.json`, `.toml`, `.md`, `.txt`, `.cfg`, `.ini`, `.rules` | Agent impact analysis |

Single-file targets are accepted: `ingest()` requires `.py`; `ingest_all()` accepts any agent-relevant extension.

## 3. Code Review

`CodeReviewer.review_file(path)` parses Python files via `ast.parse` and produces a `FileReview` containing:

| Metric | Source |
|--------|--------|
| `total_lines` | Line count of source |
| `function_count` | Top-level + method count |
| `class_count` | Class definitions |
| `import_count` | Import statements |
| `avg_complexity` | Mean cyclomatic complexity across functions |
| `max_complexity` | Highest single-function complexity |
| `functions[]` | `FunctionInfo` with name, args, decorators, complexity, docstring |
| `classes[]` | `ClassInfo` with name, bases, methods |
| `imports[]` | `ImportInfo` with module, names, is_relative |
| `findings[]` | Complexity warnings (>10), summaries, dependency listings |
| `ast_tree` | Parsed AST for downstream consumers |

Cyclomatic complexity counts: `If`, `For`, `While`, `ExceptHandler`, `With`, `Assert`, plus `BoolOp` values.

Finding IDs include a deterministic file-hash prefix (`CC-{hash}-{idx}`) to avoid collision across files.

## 4. Decomposition Strategies

The `Decomposer` class provides three strategies, selectable via `--strategy`:

### 4.1 Functional (default)

Each function → `function` KnowledgeUnit; each class → `class` unit with child method units linked via `parent` relationship. Tags inferred from name, docstring, and source path.

### 4.2 Concern

Builds on functional decomposition, then classifies each unit into cross-cutting concern groups by scanning against `CONCERN_PATTERNS` (18 patterns: error_handling, logging, validation, serialization, configuration, io_operations, testing, evaluation, analysis, collection, iteration, indexing, execution, initialization, parsing, reporting, sandbox, orchestration, skill). Unmatched units fall into `core_logic`.

### 4.3 Layer

Classifies units into architectural layers using `LAYER_INDICATORS`: presentation, application, domain, infrastructure, testing. Unmatched → `unclassified`.

## 5. CLI Configuration

```
nines analyze --target-path PATH [OPTIONS]
```

| Flag | Type | Default | Effect |
|------|------|---------|--------|
| `--target-path` | PATH (required) | — | File or directory to analyze |
| `--strategy` | functional\|concern\|layer | functional | Decomposition strategy |
| `--depth` | shallow\|deep | shallow | Analysis depth (recorded in metrics) |
| `--agent-impact/--no-agent-impact` | bool | True | Run agent impact analysis |
| `--keypoints/--no-keypoints` | bool | True | Extract key points (implies agent-impact) |
| `--output-dir` | PATH | None | Write report to directory |

Output format is set on the root command: `nines -f json analyze ...` or `nines -f text analyze ...`.

## 6. Pipeline Flags

| Flag Combination | Behavior |
|------------------|----------|
| `agent_impact=True, keypoints=True` | Full analysis (default) |
| `agent_impact=True, keypoints=False` | Agent impact without key points |
| `agent_impact=False` | Code-structure-only (legacy); forces `keypoints=False` |
| `keypoints=True` | Forces `agent_impact=True` |

## 7. Metrics Aggregation

The `_build_metrics` static method aggregates review data into the
`AnalysisResult.metrics` dict:

| Key                  | Type    | Source                          |
|----------------------|---------|---------------------------------|
| `files_analyzed`     | int     | Count of reviewed files         |
| `total_lines`        | int     | Sum of lines across all files   |
| `total_functions`    | int     | Sum of function counts          |
| `total_classes`      | int     | Sum of class counts             |
| `total_imports`      | int     | Sum of import counts            |
| `avg_complexity`     | float   | Mean of per-file avg complexity |
| `knowledge_units`    | int     | Count of decomposed units       |
| `duration_ms`        | float   | Pipeline wall-clock time        |
| `strategy`           | str     | Decomposition strategy used     |
| `depth`              | str     | Analysis depth setting          |

When agent impact is enabled, additional keys are added:

| Key                  | Type    | Source                          |
|----------------------|---------|---------------------------------|
| `total_files_scanned`| int     | All agent-relevant files found  |
| `agent_impact`       | dict    | Serialized AgentImpactReport    |
| `key_points`         | dict    | Serialized KeyPointReport       |

When the target is a directory, structure analysis adds:

| Key                  | Type    | Source                          |
|----------------------|---------|---------------------------------|
| `packages`           | int     | Count of Python packages        |
| `python_modules`     | int     | Count of Python modules         |
| `file_type_counts`   | dict    | File extension distribution     |

## 8. Error Handling

Each pipeline stage isolates errors to prevent cascading failures:
- `ingest()` raises `AnalyzerError` for non-Python files or missing paths
- `analyze()` catches per-file `AnalyzerError` and logs warnings
- Structure analysis failure is caught and logged; pipeline continues
- Agent impact and keypoint extraction use their own error handling

## 9. KnowledgeUnit Output

Each decomposition strategy produces `KnowledgeUnit` instances with:

```python
@dataclass
class KnowledgeUnit:
    id: str              # "{filepath}::{qualified_name}" or group ID
    source: str          # source file path
    content: str         # function signature or group description
    unit_type: str       # "function", "class", "concern", "layer"
    relationships: dict  # parent, members, bases
    metadata: dict       # lineno, complexity, tags, docstring
```

Tags are inferred via `_infer_tags()` which checks name and docstring
against `CONCERN_PATTERNS`, plus module-based tags from the source path
(e.g., files under `eval/` get the `evaluation` tag).

## 10. Source Files

| File | Responsibility |
|------|---------------|
| `cli/commands/analyze.py` | CLI command definition, output formatting |
| `analyzer/pipeline.py` | Pipeline orchestration, metric aggregation |
| `analyzer/reviewer.py` | AST-based code review, complexity scoring |
| `analyzer/decomposer.py` | Three decomposition strategies |
| `analyzer/structure.py` | Directory structure analysis, coupling metrics |
| `analyzer/agent_impact.py` | Agent mechanism detection, context economics |
| `analyzer/keypoint.py` | Key-point extraction and prioritization |
