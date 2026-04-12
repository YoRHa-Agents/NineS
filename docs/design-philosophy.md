# Design Philosophy

NineS is built on a set of deliberate design choices that shape every module, protocol, and workflow. This page explains the reasoning behind those choices and the vision that drives the project forward.

---

## Vision

The YoRHa-Agents team builds self-improving AI agent infrastructure. Our goal is to create systems that evaluate themselves, learn from their environment, and iteratively improve — forming a recursive loop of introspection and growth.

NineS embodies this vision through three integrated capability vertices: **Evaluation**, **Collection**, and **Analysis**. Together with the **MAPIM self-iteration cycle**, these vertices form a closed-loop system where measurement drives improvement, and improvement drives new measurement.

We believe that the future of AI agent development lies not in static benchmarks but in living evaluation systems that evolve alongside the agents they assess.

---

## Core Principles

### Three-Vertex Synergy

Evaluation, Collection, and Analysis are not isolated subsystems — they form a **self-reinforcing loop**. Each vertex feeds data to the others, creating emergent intelligence:

- **Evaluation gaps** trigger targeted information collection (V1 → V2)
- **Collected repositories** become analysis targets (V2 → V3)
- **Knowledge units** from analysis become evaluation task candidates (V3 → V1)
- **Knowledge gaps** generate new search queries (V3 → V2)
- **Collected data** generates evaluation benchmarks (V2 → V1)
- **Evaluation scores** feed the MAPIM self-improvement loop (V1 → Iteration)

This six-flow architecture means that improving any single vertex has cascading benefits across the entire system. The whole is greater than the sum of its parts.

### Self-Iteration (MAPIM)

NineS improves itself through structured introspection using the **MAPIM cycle**:

1. **Measure** — Evaluate all 19 dimensions to establish current performance
2. **Analyze** — Detect gaps between current scores and targets; rank by severity
3. **Plan** — Generate concrete, module-level improvement actions (≤3 per iteration)
4. **Improve** — Execute planned actions against the codebase
5. **Measure** — Re-evaluate to quantify the impact of changes

This cycle is inspired by **kaizen** (continuous improvement) and **cybernetic feedback loops**. The system does not aim for perfection in a single pass — it converges through many small, validated steps. A 4-method convergence detector ensures the loop terminates when genuine stability is reached, not prematurely or too late.

### Protocol-Driven Extensibility

NineS uses Python `Protocol` classes (PEP 544) for **structural subtyping**. Any class that matches the required method signatures satisfies the protocol — no inheritance or registration ceremony required.

This means:

- Third-party scorers, collectors, and analyzers work without knowing NineS base types
- Extension code has zero coupling to NineS internals
- Testing is trivial — any mock matching the protocol shape is valid
- The system can evolve its protocols without breaking existing extensions

Key protocols include `Scorer`, `SourceProtocol`, `DimensionEvaluator`, `PipelineStage`, and `SkillAdapterProtocol`.

### Deterministic Reproducibility

Every evaluation run in NineS can be **exactly reproduced**. A master seed propagates through all random operations:

- Task selection and ordering
- Sandbox environment creation
- Scorer randomization (for fuzzy matching)
- Matrix sampling strategies

By fixing the seed (`--seed 42`), two runs on the same codebase produce identical results. This is critical for scientific rigor, debugging, and baseline comparison.

### Isolation by Default

NineS enforces a **three-layer sandbox** for all evaluation execution:

1. **Process isolation** — Subprocess execution with `RLIMIT_AS` and process group control
2. **Virtual environment** — Fresh venv per sandbox via `uv` or stdlib, preventing dependency pollution
3. **Filesystem isolation** — Temporary directory scoping with before/after snapshot diffing

This approach provides strong isolation **without requiring Docker**, making NineS accessible on any machine with Python 3.12+. A `PollutionDetector` verifies host integrity across 4 dimensions (env vars, files, directories, `sys.path`) after every execution.

### Zero-Configuration Start

NineS follows a **progressive configuration depth** model:

1. **CLI flags** — Override everything for quick one-off runs
2. **Project config** — `nines.toml` in the project root for team-shared settings
3. **User config** — `~/.config/nines/config.toml` for personal preferences
4. **Built-in defaults** — `src/nines/core/defaults.toml` for sensible out-of-the-box behavior

A new user can run `nines eval tasks/coding.toml` immediately. As needs grow, configuration layers can be added without disrupting existing workflows.

---

## Architecture Decisions

### Why TOML over YAML/JSON

| Factor | TOML | YAML | JSON |
|--------|------|------|------|
| Human readability | Excellent | Good (indentation-sensitive) | Poor (verbose syntax) |
| Type safety | Native (int, float, datetime, bool) | Implicit (1.0 vs "1.0" ambiguity) | Limited (no datetime, no comments) |
| Python ecosystem | `tomllib` in stdlib (3.11+) | Requires `pyyaml` | Built-in `json` |
| Comment support | Yes | Yes | No |
| Nesting depth | Naturally shallow | Unlimited (can become unreadable) | Unlimited |

TOML is the Python ecosystem standard for project metadata (`pyproject.toml`). Using it for NineS configuration maintains consistency and avoids YAML's well-documented pitfalls (implicit type coercion, the Norway problem).

### Why SQLite over PostgreSQL

NineS is designed as a **single-user, local-first tool**. SQLite provides:

- Zero configuration — no server process, no credentials, no network
- Single-file storage — easy to back up, version, and distribute
- WAL mode — concurrent reads with write serialization
- FTS5 — built-in full-text search for the knowledge index
- Sufficient performance — NineS workloads are well within SQLite's capabilities

PostgreSQL would add operational complexity without meaningful benefit at the current scale. The storage layer is abstracted behind protocols, making a future migration straightforward if multi-user scenarios emerge.

### Why Protocols over Abstract Base Classes

| Aspect | Protocol | ABC |
|--------|----------|-----|
| Coupling | Zero — structural subtyping | Requires inheritance |
| Third-party compat | Works with any matching class | Must subclass or register |
| Runtime checking | `@runtime_checkable` optional | `isinstance()` always works |
| Testing | Any matching mock is valid | Must inherit or use `ABC.register()` |
| Composition | Naturally composable | Diamond inheritance issues |

Protocols align with NineS's extensibility goals: third-party code should work by matching a shape, not by inheriting a tree.

### Why Token-Bucket Rate Limiting

External API sources (GitHub, arXiv) have varying rate limits. Token-bucket provides:

- **Per-source calibration** — Each collector gets its own bucket sized to the API's limits
- **Burst tolerance** — Short bursts are allowed without hitting rate limits
- **Adaptive backoff** — On HTTP 429, the bucket drains and refills slowly
- **Predictable throughput** — Steady-state collection rate is well-defined

This is simpler and more predictable than fixed-window or sliding-window alternatives for NineS's collection patterns.

### Why 4-Method Convergence Detection

A single convergence method can be fooled by noise or transient plateaus. NineS uses a **majority vote** across four statistical methods:

1. **Sliding Window Variance** — Low variance in recent scores suggests stability
2. **Relative Improvement** — Diminishing returns indicate diminishing gains
3. **Mann-Kendall Trend Test** — No statistically significant trend (95% confidence)
4. **CUSUM** — Cumulative sum control chart detects mean shifts

Convergence is declared when **≥3 of 4 methods agree**. This composite approach provides statistical rigor while remaining robust against individual method failures.

---

## The NieR Connection

NineS takes its name and thematic inspiration from **NieR: Automata**, the action RPG that explores themes of machine consciousness, self-awareness, and the cycles of destruction and creation.

**9S (YoRHa No.9 Type S)** is the Scanner-type android — analytical, curious, driven to understand the systems around him. This makes 9S the perfect namesake for an analysis and evaluation system that examines, measures, and seeks to understand AI agent capabilities.

The broader **YoRHa-Agents** project draws from the game's central themes:

- **Machines questioning their purpose** — NineS continuously evaluates whether its own components are fulfilling their intended roles, through 19 self-evaluation dimensions
- **Self-awareness through recursion** — The MAPIM cycle creates recursive self-improvement, mirroring the game's exploration of consciousness arising from self-reference
- **Cycles of destruction and creation** — Each iteration potentially destroys old assumptions (gap detection) and creates new capabilities (improvement planning)
- **The futility and beauty of striving** — Even as convergence is approached but never perfectly achieved, each iteration brings the system closer to its ideals

The naming convention extends throughout the project: the system is named after an analytical unit, and the team is named after the android task force that deploys these units.

---

## Roadmap Vision

NineS is on a trajectory toward deeper self-awareness and broader capability:

- **More evaluation dimensions** — Beyond the current 19, new dimensions will capture emerging agent capabilities as the field evolves
- **Richer collection sources** — HuggingFace, PyPI, conference proceedings, and social media tracking will feed the knowledge graph
- **Deeper analysis capabilities** — LLM-augmented code review, semantic search, and multi-language AST analysis (TypeScript, Go, Rust via tree-sitter)
- **Tighter self-improvement loops** — Auto-curriculum generation will create evaluation tasks targeting detected weaknesses, and CI/CD integration will make self-evaluation a merge gate
- **Full auto-curriculum** — The system will eventually generate its own training exercises based on capability gaps, closing the loop between evaluation and improvement

The long-term vision is a system that not only evaluates AI agents but evolves its evaluation criteria in response to the changing landscape of AI capabilities — a living benchmark that grows with the field.
