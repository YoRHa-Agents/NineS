---
id: "nines/references/key-point-extraction"
version: "1.0.0"
purpose: >
  Documents the KeyPointExtractor: how it transforms agent impact reports and
  code analysis results into prioritized, deduplicated key points suitable
  for benchmark generation. Load this reference when working on key-point
  logic, priority tuning, or deduplication behavior.
triggers:
  - "key points"
  - "extraction"
  - "priority"
  - "dedup"
tier: 2
token_estimate: 2500
dependencies:
  - "nines/SKILL.md"
  - "nines/references/agent-impact-analysis"
last_updated: "2026-04-14"
---

# Key-Point Extraction Reference

## 1. Overview

The `KeyPointExtractor` (in `keypoint.py`, FR-314) transforms an
`AgentImpactReport` and an optional `AnalysisResult` into a ranked list of
actionable `KeyPoint` objects. These key points feed into the benchmark
generation system (`BenchmarkGenerator`) for automated test creation.

## 2. Extraction Flow

```
  AgentImpactReport              AnalysisResult (optional)
       |                               |
       +-- mechanisms --------+        |
       +-- economics ---------+        |
       +-- findings ----------+        |
                              v        v
                    +----------------------+
                    |  extract()           |
                    |  +- from_mechanisms  |
                    |  +- from_economics   |
                    |  +- from_findings    |
                    |  +- from_analysis    |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |  _deduplicate()      |
                    |  +- title-based      |
                    |  +- semantic overlap  |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |  _prioritize()       |
                    +----------+-----------+
                               |
                               v
                        KeyPointReport
```

## 3. KeyPoint Dataclass

```python
@dataclass
class KeyPoint:
    id: str                     # "kp-{source}-{uuid8}"
    category: str               # from VALID_CATEGORIES
    title: str                  # short human-readable title
    description: str            # detailed description
    mechanism_ids: list[str]    # supporting mechanism IDs
    expected_impact: str        # "positive"|"negative"|"neutral"|"uncertain"
    impact_magnitude: float     # [0.0, 1.0]
    validation_approach: str    # how to validate this key point
    evidence: list[str]         # file paths or descriptions
    priority: int               # 1 (highest) to 5 (lowest)
    metadata: dict[str, Any]    # free-form
```

## 4. Category Taxonomy

Six valid categories for key points:

| Category                | Description                                   |
|-------------------------|-----------------------------------------------|
| `compression`           | Token reduction and compact representation    |
| `context_management`    | Token budget overhead and savings             |
| `behavioral_shaping`    | Rules and conventions shaping agent output    |
| `cross_platform`        | Multi-IDE/platform consistency                |
| `semantic_preservation` | Meaning retention through transformations     |
| `engineering`           | Code quality and engineering practices        |

### Mechanism-to-Category Mapping

Agent mechanism categories map to key-point categories via
`_MECHANISM_CATEGORY_MAP`:

| Mechanism Category        | Key-Point Category       |
|---------------------------|--------------------------|
| `context_compression`     | `compression`            |
| `behavioral_instruction`  | `behavioral_shaping`     |
| `distribution`            | `cross_platform`         |
| `safety`                  | `semantic_preservation`  |
| `persistence`             | `semantic_preservation`  |
| (unmapped)                | `engineering`            |

### Finding-to-Category Mapping

Findings are mapped via `_finding_category_to_keypoint`:

| Finding Category     | Key-Point Category     |
|----------------------|------------------------|
| `agent_impact`       | `behavioral_shaping`   |
| `context_economics`  | `context_management`   |
| `coverage_gap`       | `context_management`   |
| `low_confidence`     | `behavioral_shaping`   |
| (unmapped)           | `engineering`          |

## 5. Extraction Sources

### 5.1 From Mechanisms (`_extract_from_mechanisms`)

One key point per `AgentMechanism`. Each point receives:

- **Category** from `_MECHANISM_CATEGORY_MAP`
- **Impact** inferred from token delta and category via
  `_infer_impact_from_token_delta`:
  - Token savings > 100 → `"positive"`
  - Beneficial categories (`behavioral_instruction`, `safety`, `persistence`)
    with positive tokens → `"positive"`
  - Token overhead > 500 → `"negative"`
  - Zero tokens → `"uncertain"`
  - Otherwise → `"neutral"`
- **Magnitude** computed as:
  ```
  magnitude = (log1p(|token_impact|) / log1p(50000)) * confidence
  ```
  Capped at 1.0. Approximate values at confidence=1.0:

  | Token Impact | Magnitude |
  |--------------|-----------|
  | 100          | 0.43      |
  | 1,000        | 0.64      |
  | 5,000        | 0.79      |
  | 10,000       | 0.85      |
  | 50,000       | 1.00      |

- **Validation approach** from `_CATEGORY_VALIDATION_TEMPLATES`

### 5.2 From Economics (`_extract_from_economics`)

Up to three key points from `ContextEconomics`:

| Key Point                | Condition             | Impact when bad     |
|--------------------------|-----------------------|---------------------|
| Token overhead analysis  | `overhead_tokens > 0` | negative if > 5000  |
| Token savings efficiency | `savings_ratio > 0`   | negative if < 10%   |
| Break-even threshold     | `break_even > 0`      | negative if > 10    |

All economics-derived points start at priority 3.

Magnitude calculations:
- Overhead: `min(1.0, overhead_tokens / 10000)`
- Savings: `1.0 - savings_ratio`
- Break-even: `min(1.0, break_even_interactions / 20)`

### 5.3 From Findings (`_extract_from_findings`)

One key point per finding. Severity maps to impact and magnitude:

| Severity   | Expected Impact | Magnitude | Priority |
|------------|-----------------|-----------|----------|
| `critical` | negative        | 0.9       | 1        |
| `error`    | negative        | 0.7       | 2        |
| `warning`  | negative        | 0.5       | 3        |
| `info`     | neutral         | 0.2       | 4        |

### 5.4 From Analysis (`_extract_from_analysis`)

Engineering observations from the `AnalysisResult`. Limited to a maximum
of 5 findings with severity `critical` or `error`:

- All receive `category="engineering"` and `priority=5`
- Magnitude: critical → 0.7, error → 0.5

Additionally, an analysis coverage summary point is created when
agent-relevant metrics are present (`agent_impact`, `key_points`, or
`total_files_scanned`), reporting Python files analyzed, total files scanned,
and knowledge units extracted.

## 6. Deduplication Logic

Deduplication runs in two passes after all extraction sources complete.

### Pass 1: Title-Based

Groups points by `"{category}::{title.lower().strip()}"`. When duplicates
share the same key, the one with higher `impact_magnitude` is kept.

### Pass 2: Semantic Overlap

Within each category, points are sorted by descending magnitude. For each
pair (i, j) where i < j:

1. **Substring check**: if one description (lowered) contains the other,
   overlap is detected
2. **Word overlap check**: extract non-trivial words (>2 chars, stripped of
   punctuation). If `intersection / min(len_a, len_b) > 0.6`, overlap is
   detected

When overlap is detected, the lower-magnitude point (j) is dropped. This
catches economics-derived vs. finding-derived points that describe the same
concern with different titles.

## 7. Priority System (P1–P5)

The `_prioritize` method reassigns priorities based on source and metrics:

| Priority | Assignment Rule                                            |
|----------|------------------------------------------------------------|
| P1       | Source=mechanism, magnitude >= 0.7, confidence >= 0.7      |
| P2       | Source=mechanism, magnitude >= 0.4 or confidence >= 0.5    |
| P2       | Source=finding, severity critical or error                  |
| P3       | Source=economics                                           |
| P3       | Source=finding, severity warning                           |
| P4       | Source=mechanism, low confidence (< 0.5 and magnitude < 0.4) |
| P4       | Source=finding, severity info                              |
| P5       | Source=analysis or analysis_metric                         |

After assignment, points are sorted by `(priority ASC, impact_magnitude DESC)`.

### Initial Mechanism Priority

Before the `_prioritize` pass, mechanisms receive an initial priority from
`_mechanism_priority`:

| Condition                                  | Initial Priority |
|--------------------------------------------|------------------|
| `confidence >= 0.7` and `|tokens| > 500`  | 1                |
| `confidence >= 0.5`                        | 2                |
| Otherwise                                  | 4                |

## 8. Impact Classification

`_infer_impact_from_token_delta(token_impact, category)`:

| Condition                                  | Result      |
|--------------------------------------------|-------------|
| `token_impact < -100`                      | `positive`  |
| Beneficial category + positive tokens      | `positive`  |
| `token_impact > 500`                       | `negative`  |
| `token_impact == 0`                        | `uncertain` |
| Otherwise                                  | `neutral`   |

Beneficial categories: `behavioral_instruction`, `safety`, `persistence`.
These are considered positive even when adding tokens because the overhead
delivers real value.

## 9. Validation Approach Templates

Each category has a default validation approach text:

| Category                | Template                                          |
|-------------------------|---------------------------------------------------|
| `compression`           | Run compression benchmark: compare output length  |
| `behavioral_shaping`    | A/B test agent output with rule enabled/disabled  |
| `cross_platform`        | Deploy to platforms, verify consistent behavior   |
| `semantic_preservation` | Run semantic equivalence checks before/after      |
| `context_management`    | Measure token overhead across N interactions      |
| `engineering`           | Review code quality metrics and verify practices  |

## 10. KeyPointReport

```python
@dataclass
class KeyPointReport:
    target: str
    key_points: list[KeyPoint]
    summary: str                    # human-readable summary
    extraction_duration_ms: float
    metadata: dict[str, Any]        # includes category_counts
```

Convenience methods:
- `get_by_category(category)` → filter by category
- `get_by_priority(priority)` → filter by exact priority level
- `high_priority()` → all points with priority <= 2

The summary is built as: `"Extracted N key point(s). {category}: {count}. ...
{M} high-priority item(s)."`

## 11. Source File

| File          | Role                        | FR     |
|---------------|-----------------------------|--------|
| `keypoint.py` | Key-point extraction engine | FR-314 |
