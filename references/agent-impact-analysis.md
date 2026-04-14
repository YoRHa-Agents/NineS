---
id: "nines/references/agent-impact-analysis"
version: "1.0.0"
purpose: >
  Documents the AgentImpactAnalyzer: how it detects mechanisms that influence
  AI agent behavior, discovers agent-facing artifacts, estimates context
  economics, and generates findings. Load this reference when working on
  agent impact features or debugging mechanism detection.
triggers:
  - "agent impact"
  - "mechanisms"
  - "economics"
  - "artifacts"
tier: 2
token_estimate: 2500
dependencies:
  - "nines/SKILL.md"
  - "nines/references/analysis-pipeline"
last_updated: "2026-04-14"
---

# Agent Impact Analysis Reference

## 1. Overview

The `AgentImpactAnalyzer` (in `agent_impact.py`, FR-313) analyzes repositories
for their influence on AI agent effectiveness. Unlike traditional static
analysis that focuses on complexity and coupling, this analyzer identifies:

1. **Agent-facing artifacts** — files designed for agent consumption
2. **Mechanisms** — discrete patterns that shape agent behavior
3. **Context economics** — token overhead vs. savings tradeoffs
4. **Distribution patterns** — how configuration reaches multiple platforms

The analyzer produces an `AgentImpactReport` containing mechanisms, economics,
artifacts, findings, and knowledge units.

## 2. Analysis Flow

```
  target path
      |
      v
  +--------------------------+
  | _discover_agent_         |
  |     artifacts()          |--------> list[str]  (relative paths)
  +------------+-------------+
               |
               v
  +--------------------------+
  | _estimate_context_       |
  |     economics()          |--------> ContextEconomics
  +------------+-------------+
               |
               v
  +--------------------------+
  | _detect_mechanisms()     |--------> list[AgentMechanism]
  +------------+-------------+
               |
               +---> economics.mechanism_count updated
               +---> economics.overhead_tokens adjusted
               |
               v
  +--------------------------+
  | _generate_findings()     |--------> list[Finding]
  +------------+-------------+
               |
               v
  +--------------------------+
  | _create_knowledge_       |
  |     units()              |--------> list[KnowledgeUnit]
  +------------+-------------+
               |
               v
         AgentImpactReport
```

## 3. Agent Artifact Discovery

The analyzer recursively walks the target directory and tests each file's
relative path against a set of regex patterns defined in
`AGENT_ARTIFACT_PATTERNS`:

| Pattern                         | What it matches                      |
|---------------------------------|--------------------------------------|
| `CLAUDE\.md$`                   | Claude instruction files             |
| `\.claude/`                     | Claude configuration directories     |
| `SKILL\.md$`                    | Agent skill definitions              |
| `\.cursor/rules/`              | Cursor IDE rule files                |
| `\.cursorrules$`               | Cursor rules file                    |
| `\.windsurf/rules/`            | Windsurf IDE rules                   |
| `\.clinerules/`                | Cline rules                          |
| `copilot-instructions\.md$`    | GitHub Copilot instructions          |
| `AGENTS\.md$`                   | Multi-agent configuration            |
| `\.codex/`, `codex-plugin/`    | OpenAI Codex configuration           |
| `CONTEXT\.md$`                  | Context documents                    |
| `SYSTEM_PROMPT`                 | System prompt files                  |
| `pyproject\.toml$`             | Project metadata (agent-parseable)   |
| `\.github/copilot/`            | GitHub Copilot directory config      |
| `\.aider`                       | Aider configuration                  |
| `RULES\.md$`                    | Rules documents                      |

Directories matching `_SKIP_DIRS` are excluded: `.git`, `node_modules`,
`__pycache__`, `.venv`, `venv`, `.tox`, `.mypy_cache`, `.pytest_cache`,
`.ruff_cache`, `dist`, `build`, `.eggs`, `*.egg-info`.

For single-file targets, the file's POSIX path is tested against all
patterns. For directories, traversal uses `rglob("*")` with `_should_skip`
filtering any path whose components match the skip set.

## 4. Five Mechanism Categories

Mechanisms are detected by scanning the lowercased content of each
agent-facing artifact against indicator keyword lists. The five categories
and their indicators are:

### 4.1 Behavioral Instruction

Shapes agent output style and decision-making through rules and conventions.

**Indicators:** `instruction`, `rule`, `prompt`, `convention`, `must`,
`always`, `never`, `should`, `style`, `guideline`

**Mechanism name:** `behavioral_rules`

### 4.2 Context Compression

Reduces token usage through compression, abbreviation, or compact formats.

**Indicators:** `compress`, `token`, `shorten`, `strip`, `minif`, `compact`,
`terse`, `concise`, `abbreviat`, `reduc`

**Mechanism name:** `token_compression`

Token impact is **negated** for this category (saves tokens rather than adding).

### 4.3 Safety

Implements guardrails like confirmation prompts and irreversible-action
protection.

**Indicators:** `safety`, `security`, `irreversible`, `danger`, `warning`,
`auto-clarity`, `fallback`, `restore`, `backup`

**Mechanism name:** `safety_guardrails`

### 4.4 Distribution

Distributes agent configuration across multiple platforms or synchronizes
rules between IDE integrations.

**Indicators:** `sync`, `deploy`, `publish`, `ci`, `workflow`,
`multi-agent`, `distribute`, `platform`, `cross-ide`

**Mechanism name:** `multi_platform_sync`

### 4.5 Persistence

Enforces behavioral persistence through drift prevention or invariant
enforcement.

**Indicators:** `drift`, `enforce`, `persist`, `mode`, `lock`, `guard`,
`invariant`, `constraint`, `assert`

**Mechanism name:** `drift_prevention`

### Mechanism Detection Logic

For each artifact file, the content is lowercased and checked against all
five category indicator lists. When any indicator keyword is found, the
file is recorded as evidence for that category/mechanism pair.

After scanning all files, mechanisms are created from the accumulated
evidence:

```
for each (category, mechanism_name) with evidence:
    read all evidence files
    token_impact = estimate_tokens(combined_content)
    if category == "context_compression":
        token_impact = -token_impact
    confidence = min(1.0, num_evidence_files * 0.3 + 0.1)
    create AgentMechanism(id="mech-{uuid8}", ...)
```

## 5. AgentMechanism Dataclass

```python
@dataclass
class AgentMechanism:
    id: str                        # "mech-{uuid8}"
    name: str                      # e.g. "behavioral_rules"
    category: str                  # one of the five categories
    description: str               # human-readable explanation
    evidence_files: list[str]      # paths supporting this mechanism
    estimated_token_impact: int    # positive = adds, negative = saves
    confidence: float              # [0.0, 1.0]
```

## 6. Context Economics Model

`ContextEconomics` quantifies the token budget impact of agent-facing content.

### Fields

| Field                      | Type  | Description                        |
|----------------------------|-------|------------------------------------|
| `overhead_tokens`          | int   | Tokens added to every interaction  |
| `estimated_savings_ratio`  | float | Ratio of output tokens saved       |
| `mechanism_count`          | int   | Distinct mechanisms detected       |
| `agent_facing_files`       | int   | Count of agent-facing files        |
| `total_agent_context_tokens`| int  | Aggregate tokens across all files  |
| `break_even_interactions`  | int   | Interactions needed for net-positive|

### Token Estimation

Uses a word-based approximation without external tokenizer dependencies:

```
tokens = word_count * 1.3   (_TOKENS_PER_WORD = 1.3)
```

### Savings Ratio Calculation

```python
savings_ratio = min(0.95, num_artifacts * 0.05) if artifacts else 0.0
```

Each artifact contributes 5% savings, capped at 95%.

### Break-Even Calculation

When both overhead and savings are positive:

```python
saved_per_interaction = overhead * savings_ratio
break_even = ceil(overhead / saved_per_interaction)
```

This tells users how many interactions are needed before the token overhead
of agent-facing files pays for itself through improved output efficiency.

### Post-Mechanism Adjustments

After mechanism detection, the economics are updated:
- `mechanism_count` is set to the number of detected mechanisms
- Total absolute token impact from mechanisms is added to
  `total_agent_context_tokens` and `overhead_tokens`
- If no overhead was computed but artifacts exist, a minimum estimate of
  `num_artifacts * 50` tokens is applied

## 7. Confidence Scoring

Mechanism confidence is computed as:

```python
confidence = min(1.0, num_evidence_files * 0.3 + 0.1)
```

| Evidence Files | Confidence |
|----------------|------------|
| 1              | 0.4        |
| 2              | 0.7        |
| 3              | 1.0        |
| 4+             | 1.0 (cap)  |

Low-confidence mechanisms (< 0.3) generate an additional finding to flag
that evidence may be circumstantial.

## 8. Findings Generation

The `_generate_findings` method produces actionable findings:

| Finding Category     | Severity | Condition                           |
|----------------------|----------|-------------------------------------|
| `agent_impact`       | info     | Always (artifact + mechanism count) |
| `context_economics`  | info     | When total tokens > 0               |
| `context_economics`  | warning  | When overhead > 5000 tokens         |
| `coverage_gap`       | info     | When mechanism categories are missing|
| `agent_impact`       | info     | When no artifacts detected           |
| `low_confidence`     | info     | Per-mechanism when confidence < 0.3 |

The high-overhead warning suggests splitting large instruction files into
role-specific segments or applying token-compression techniques.

Coverage gap detection compares detected categories against the full set
(`behavioral_instruction`, `context_compression`, `safety`, `distribution`,
`persistence`) and reports any missing.

## 9. Knowledge Unit Creation

One `KnowledgeUnit` per mechanism plus one summary unit:

| Unit Type               | ID Pattern                  | Content                |
|-------------------------|-----------------------------|------------------------|
| `agent_mechanism`       | `agent_mech::{mech.id}`     | Mechanism name + description |
| `agent_impact_summary`  | `agent_impact::summary`     | Aggregate profile      |

The summary unit's relationships reference all mechanism unit IDs and all
artifact paths, enabling downstream pattern detection.

## 10. Integration with Pipeline

The `AgentImpactAnalyzer` is invoked by `AnalysisPipeline.run()` when the
`agent_impact` flag is `True` (the default). The pipeline:

1. Calls `ingest_all()` to discover all agent-relevant files
2. Instantiates `AgentImpactAnalyzer` (or uses the injected instance)
3. Calls `analyzer.analyze(target)` to produce the `AgentImpactReport`
4. Stores the report dict under `metrics["agent_impact"]`
5. Merges `impact_report.findings` into the global findings list
6. Passes the report to `KeyPointExtractor` if keypoints are enabled

## 11. Token Impact Semantics

The `estimated_token_impact` field on `AgentMechanism` follows a sign
convention:

- **Positive values** mean the mechanism **adds** tokens to agent context
  (e.g., behavioral rules that must be loaded)
- **Negative values** mean the mechanism **saves** tokens (e.g., compression
  strategies that reduce output size)

Only the `context_compression` category negates its token impact. All other
categories use the raw (positive) estimate based on evidence file sizes.

## 12. Source File

| File              | Role                          | FR     |
|-------------------|-------------------------------|--------|
| `agent_impact.py` | Full agent impact analysis    | FR-313 |
