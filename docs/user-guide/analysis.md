# Analysis Guide (V3)

<!-- auto-updated: version from src/nines/__init__.py -->

NineS V3 ingests source code, parses it into ASTs, analyzes architecture and quality, decomposes into atomic knowledge units, and indexes them for search and retrieval.

---

## Analysis Pipeline Overview

The pipeline processes code through five sequential stages:

```mermaid
graph LR
    A[Ingest] --> B[Parse]
    B --> C[Analyze]
    C --> D[Decompose]
    D --> E[Index]
```

| Stage | Input | Output | Key Operations |
|-------|-------|--------|----------------|
| **Ingest** | Directory path | `RawSource` list | Walk directory, check cache, skip unchanged files |
| **Parse** | Source files | `ParsedFile` list | AST parsing, function/class/import extraction, complexity computation |
| **Analyze** | Parsed files | `StructureMap`, `CouplingMetrics` | Module boundaries, layer detection, pattern recognition, dependency graphs |
| **Decompose** | Analysis results | `KnowledgeUnit` list | Functional, concern-based, and layer-based decomposition |
| **Index** | Knowledge units | Searchable index | SQLite FTS5, keyword + faceted search |

---

## Running an Analysis

### Basic Analysis

```bash
nines analyze ./target-repo
```

### Deep Analysis with Decomposition and Indexing

```bash
nines analyze ./target-repo --depth deep --decompose --index
```

### Incremental Re-analysis

Only re-analyze files that changed since the last run:

```bash
nines analyze ./target-repo --incremental
```

### Output Formats

```bash
# Markdown report
nines analyze ./target-repo --output markdown -o analysis.md

# JSON output
nines analyze ./target-repo --output json -o analysis.json
```

---

## Code Review Capabilities

The `CodeReviewer` performs AST-based analysis on Python files:

- **Function extraction** — Name, arguments, return annotation, decorators, docstring, line range
- **Class extraction** — Name, bases, methods, class variables, abstract status
- **Import resolution** — Module-to-module dependency mapping across the project
- **Cyclomatic complexity** — McCabe method counting `If`, `While`, `For`, `ExceptHandler`, `BoolOp`, `Assert`, `With` nodes

### Complexity Distribution

Functions are classified by complexity:

| Tier | Complexity | Assessment |
|------|-----------|------------|
| Low | 1–5 | Simple, easily testable |
| Medium | 6–10 | Moderate, may benefit from refactoring |
| High | 11–20 | Complex, should be decomposed |
| Very High | 21+ | Requires immediate attention |

Configuration:

```toml
[analyze.reviewer]
complexity_threshold = 10
extract_docstrings = true
resolve_imports = true
```

---

## Structure Analysis

The `StructureAnalyzer` examines project layout and architecture:

### Module Boundary Detection

Identifies Python packages (directories with `__init__.py`) and their relationships.

### Architectural Layer Detection

Directories are classified into architectural layers using keyword matching:

| Layer | Indicator Keywords |
|-------|--------------------|
| Presentation | `cli`, `api`, `web`, `ui`, `views`, `routes`, `controllers` |
| Application | `services`, `usecases`, `commands`, `orchestrator`, `workflows` |
| Domain | `models`, `entities`, `domain`, `core`, `types`, `schemas` |
| Infrastructure | `db`, `database`, `repos`, `adapters`, `storage`, `external` |
| Testing | `tests`, `test`, `fixtures`, `conftest`, `mocks` |

### Architecture Pattern Detection

| Pattern | Detection Signals | Min Confidence |
|---------|-------------------|----------------|
| MVC | `models/`, `views/`, `controllers/` | 0.5 |
| Hexagonal | `ports/`, `adapters/`, `domain/`, `core/` | 0.5 |
| Layered | `presentation/`, `application/`, `domain/`, `infrastructure/` | 0.5 |
| Plugin/Extension | ≥3 Protocol-based classes | 0.5 |

### Coupling Metrics

For each module, NineS computes:

- **Ca** (Afferent Coupling) — Number of modules depending on this one
- **Ce** (Efferent Coupling) — Number of modules this one depends on
- **Instability** — I = Ce / (Ca + Ce); 0.0 = maximally stable

---

## Decomposition Strategies

NineS supports three decomposition strategies, all of which can run in a single pipeline pass:

### Functional Decomposition

Each function and class becomes a `KnowledgeUnit`. Methods are nested as children of their class.

```bash
nines analyze ./target-repo --decompose --strategies functional
```

### Concern-Based Decomposition

Groups code elements by cross-cutting concern:

| Concern | Detection Keywords |
|---------|--------------------|
| Error Handling | `except`, `raise`, `Error`, `Exception`, `try` |
| Logging | `logger`, `logging`, `log.` |
| Validation | `validate`, `assert`, `check`, `verify` |
| Serialization | `to_dict`, `from_dict`, `serialize`, `json` |
| Configuration | `config`, `settings`, `options`, `defaults` |
| I/O Operations | `read`, `write`, `open`, `save`, `fetch` |

```bash
nines analyze ./target-repo --decompose --strategies concern
```

### Layer-Based Decomposition

Assigns units to architectural layers identified during structure analysis. Units that don't match any layer are placed in "unclassified".

```bash
nines analyze ./target-repo --decompose --strategies layer
```

Configuration:

```toml
[analyze.decomposer]
strategies = ["functional", "concern", "layer"]
functional_granularity = "function"
```

---

## Knowledge Indexing and Search

The `KnowledgeIndex` stores decomposed units in SQLite with FTS5 for search:

```bash
# Index during analysis
nines analyze ./target-repo --index

# Search the index
nines analyze search "authentication middleware"
```

### Search Capabilities

- **Keyword search** — FTS5 full-text matching across name, description, signature, tags
- **Faceted filtering** — Filter by language, type (function/class/module), complexity tier, abstraction level
- **Ranked results** — BM25 relevance scoring

Configuration:

```toml
[analyze.index]
fts_enabled = true
facets = ["language", "type", "complexity_tier", "source"]
```

---

## Pattern Abstraction

The abstraction layer detects higher-level design patterns:

| Pattern | Structural Signals |
|---------|-------------------|
| Factory | Methods named `create`/`make`/`build` returning different types |
| Observer | `subscribe`/`register` + `notify`/`emit` methods |
| Strategy | Protocol/ABC base with ≥2 concrete implementations |
| Adapter | Class wrapping a foreign type with Protocol-conformant methods |
| Decorator | Function accepting and returning a callable with same signature |

!!! note "Error Isolation"
    Single-file parse errors don't abort the pipeline. Failed files are logged and skipped, with structured `FileError` entries in the result.
