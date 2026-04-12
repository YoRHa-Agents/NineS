# NineS Code Quality Review

**Date:** 2026-04-12
**Scope:** `src/nines/{core,eval,collector,analyzer,iteration,orchestrator}/`
**Reviewer:** L3 Task Agent (T45)

---

## Summary

| Severity | Count | Fixed |
|----------|-------|-------|
| Blocker  | 0     | n/a   |
| Critical | 3     | 3     |
| Major    | 6     | 6     |
| Minor    | 5     | —     |

---

## Blocker

_None found._

---

## Critical

### C-01: `collector/scheduler.py` — Raises `KeyError`/`ValueError` instead of `NinesError`

**Category:** Error Handling
**Location:** `collector/scheduler.py:101-106`

`run_once()` raises bare `KeyError` and `ValueError`, breaking the error hierarchy
contract (NFR-20). All NineS errors must derive from `NinesError` to allow uniform
`except NinesError` handling.

**Fix:** Replace with `CollectorError`.

---

### C-02: `iteration/tracker.py` — Raises `RuntimeError` instead of `NinesError`

**Category:** Error Handling
**Location:** `iteration/tracker.py:135-136`

`complete_iteration()` raises `RuntimeError` when no iteration is in progress.
This bypasses the NineS error hierarchy and is uncatchable by a generic
`except NinesError` handler.

**Fix:** Replace with `OrchestrationError` (or a new `IterationError`).

---

### C-03: `collector/store.py` — Silent error swallowing in row converters

**Category:** Error Handling / No Silent Failures
**Location:** `collector/store.py:294-345`

`_row_to_repo`, `_row_to_paper`, and `_row_to_snapshot` catch
`json.JSONDecodeError` and `TypeError` but return empty lists without logging.
This violates the "No Silent Failures" workspace rule and NFR-21.

**Fix:** Add `logger.warning(...)` calls in each except block.

---

## Major

### M-01: `core/config.py` — Fragile string-based type dispatch in `_convert_env_value`

**Category:** Code Consistency / SOLID (OCP)
**Location:** `core/config.py:356-382`

Type dispatch uses `"bool" in str(type_hint)`, which is fragile and breaks if
the string representation changes or if custom types are used. This is not
extensible.

**Fix:** Use `dataclasses.fields()` to resolve actual types, or check against
known field names grouped by type.

---

### M-02: `analyzer/pipeline.py` — Incorrect return type on `_build_metrics`

**Category:** Type Hints
**Location:** `analyzer/pipeline.py:137-168`

`_build_metrics` is annotated as returning `dict[str, object]`. While technically
correct, `dict[str, Any]` is the convention used everywhere else in the codebase
and is more ergonomic for consumers.

**Fix:** Change return type to `dict[str, Any]`.

---

### M-03: `eval/analysis.py` — Accesses private `_dimension` attribute

**Category:** Code Consistency / Encapsulation
**Location:** `eval/analysis.py:57-59`

`group_by_dimension` checks `hasattr(r, '_dimension')` then accesses
`r._dimension` with a type-ignore comment. This is a code smell — if
a dimension is needed, it should be part of the public interface of
`EvalResult`.

**Fix:** Remove the private attribute access and rely only on the explicit
`dimension_map` parameter in `group_by()`.

---

### M-04: `collector/store.py` — Individual INSERTs for batch operations

**Category:** Performance
**Location:** `collector/store.py:110-146, 181-216`

`save_repos` and `save_papers` execute individual INSERT statements in a loop.
For large batches this is significantly slower than `executemany`.

**Fix:** Refactor to use `executemany` with parameter sequences.

---

### M-05: `analyzer/structure.py` — Double directory traversal

**Category:** Performance
**Location:** `analyzer/structure.py:179-198`

`_count_file_types` and `_collect_python_files` each call `root.rglob()`
independently, performing two full directory traversals. For large codebases
this doubles I/O.

**Fix:** Combine into a single traversal pass (minor impact at MVP scale,
flagged for awareness).

---

### M-06: `eval/analysis.py` — `group_by_dimension` has fragile dimension inference

**Category:** Code Consistency
**Location:** `eval/analysis.py:52-61`

The fallback dimension is extracted via `r.to_dict().get("task_id", "").rsplit("-", 1)[0]`,
which is fragile and depends on task ID naming conventions. Combined with the
private `_dimension` access in M-03, this method has two unreliable heuristics.

**Fix:** Remove the heuristic fallback; callers should use `group_by()` with
an explicit `dimension_map`.

---

## Minor

### m-01: `collector/scheduler.py` — `ScheduledJob` missing class docstring

**Category:** Docstrings
**Location:** `collector/scheduler.py:19-28`

The `ScheduledJob` dataclass has no class-level docstring explaining its purpose.

---

### m-02: `collector/tracker.py` — `Bookmark` missing class docstring

**Category:** Docstrings
**Location:** `collector/tracker.py:21-31`

The `Bookmark` dataclass has no class-level docstring.

---

### m-03: `eval/reporters.py` — Unused `asdict` import used only in one place

**Category:** Code Consistency
**Location:** `eval/reporters.py:15`

`asdict` from `dataclasses` is imported but used only once for `ReportSummary`.
The usage is fine but the import could be made local if the class gains a
custom `to_dict()` later.

---

### m-04: `core/config.py` — `_ALIASES` dict rebuilt on every `_try_extract_field` call

**Category:** Performance
**Location:** `core/config.py:424-439`

The `_ALIASES` dictionary is constructed inside `_try_extract_field`, meaning
it is rebuilt on every call. Should be a module-level constant.

---

### m-05: `eval/scorers.py` — `RubricScorer._check_criterion` uses if/elif chain

**Category:** SOLID (OCP)
**Location:** `eval/scorers.py:134-145`

Check function dispatch is a hardcoded if/elif chain. Adding new check types
requires modifying the method body.

---

_End of review._
