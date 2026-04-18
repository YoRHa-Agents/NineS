"""Tests for C01 Phase 2+3 — full evaluator migration to ``EvaluationContext``.

Each test asserts:
1. The evaluator declares ``requires_context = True`` (where applicable).
2. ``evaluate(ctx=ctx)`` honours ``ctx`` paths (golden_dir / samples_dir /
   src_dir / project_root) instead of falling back to the constructor default.
3. Two contexts targeting different projects produce different metadata
   (proves the silent-fallback bug is fixed).

Covers C01 Phase 2 (V1 + capability) and Phase 3 (hygiene).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.capability_evaluators import (  # noqa: E402
    AbstractionQualityEvaluator,
    AgentAnalysisQualityEvaluator,
    CodeReviewAccuracyEvaluator,
)
from nines.iteration.context import EvaluationContext  # noqa: E402
from nines.iteration.eval_evaluators import (  # noqa: E402
    EvalCoverageEvaluator,
    PipelineLatencyEvaluator,
)
from nines.iteration.self_eval import (  # noqa: E402
    DocstringCoverageEvaluator,
    LintCleanlinessEvaluator,
    LiveModuleCountEvaluator,
)
from nines.iteration.v1_evaluators import (  # noqa: E402
    ReliabilityEvaluator,
    ScorerAgreementEvaluator,
    ScoringAccuracyEvaluator,
)


def _make_project(root: Path, with_py: bool = True) -> EvaluationContext:
    """Build a tiny project layout under *root* and return its EvaluationContext."""
    src = root / "src"
    src.mkdir(parents=True)
    if with_py:
        (src / "app.py").write_text(
            "def public_func():\n    \"\"\"docstring.\"\"\"\n    return 1\n",
            encoding="utf-8",
        )
        (src / "__init__.py").write_text("", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_x(): pass\n", encoding="utf-8")
    samples = root / "samples"
    samples.mkdir()
    golden = root / "golden"
    golden.mkdir()
    return EvaluationContext.from_cli(
        project_root=str(root),
        src_dir="src",
        test_dir="tests",
        samples_dir="samples",
        golden_dir="golden",
    )


# ---------------------------------------------------------------------------
# Phase 2 — V1 evaluators (D01/D03/D05)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evaluator_cls",
    [ScoringAccuracyEvaluator, ReliabilityEvaluator, ScorerAgreementEvaluator],
)
def test_v1_evaluator_declares_requires_context(evaluator_cls) -> None:
    """V1 evaluators (D01/D03/D05) must opt in to ctx-aware via the marker."""
    assert evaluator_cls.requires_context is True


@pytest.mark.parametrize(
    "evaluator_cls,dim_name",
    [
        (ScoringAccuracyEvaluator, "scoring_accuracy"),
        (ReliabilityEvaluator, "scoring_reliability"),
        (ScorerAgreementEvaluator, "scorer_agreement"),
    ],
)
def test_v1_evaluator_uses_ctx_golden_dir(
    evaluator_cls,
    dim_name: str,
    tmp_path: Path,
) -> None:
    """When ctx.golden_dir is supplied, the evaluator scans *that* dir.

    The empty foreign golden_dir produces an error metadata field that
    points at ctx.golden_dir, proving we did NOT silently fall back to
    the constructor default.
    """
    ctx = _make_project(tmp_path)
    # Foreign project's golden dir is empty → expect 0.0 with error metadata
    evaluator = evaluator_cls()  # Constructor has NineS-default golden_dir
    score = evaluator.evaluate(ctx=ctx)
    assert score.name == dim_name
    assert score.value == 0.0
    assert "error" in score.metadata
    assert str(ctx.golden_dir) in str(score.metadata.get("golden_dir", ""))


# ---------------------------------------------------------------------------
# Phase 2 — D02 EvalCoverageEvaluator + D16 PipelineLatencyEvaluator
# ---------------------------------------------------------------------------


def test_d02_eval_coverage_uses_ctx_samples_dir(tmp_path: Path) -> None:
    """D02 EvalCoverageEvaluator honours ctx.samples_dir."""
    ctx = _make_project(tmp_path)
    assert EvalCoverageEvaluator.requires_context is True
    evaluator = EvalCoverageEvaluator()
    score = evaluator.evaluate(ctx=ctx)
    assert score.name == "eval_coverage"
    # Empty samples dir → 0 files
    assert score.metadata["total_files"] == 0
    assert str(ctx.samples_dir) in str(score.metadata.get("sample_dir", ""))


def test_d16_pipeline_latency_resolves_target_from_ctx(tmp_path: Path) -> None:
    """D16 PipelineLatencyEvaluator picks ctx.src_dir / __init__.py first."""
    ctx = _make_project(tmp_path, with_py=True)
    assert PipelineLatencyEvaluator.requires_context is True
    evaluator = PipelineLatencyEvaluator()
    score = evaluator.evaluate(ctx=ctx)
    assert score.name == "pipeline_latency"
    # When ctx is provided, target metadata must point at ctx.src_dir
    target = score.metadata.get("target", "")
    assert str(ctx.src_dir) in target, (
        f"target {target!r} did not resolve under ctx.src_dir {ctx.src_dir!r}"
    )


def test_d16_pipeline_latency_fallback_first_py_file(tmp_path: Path) -> None:
    """D16 falls back to the first *.py when no __init__.py exists."""
    src_root = tmp_path
    src = src_root / "src"
    src.mkdir()
    (src / "module.py").write_text("def f(): pass\n", encoding="utf-8")
    # No __init__.py at all
    (src_root / "samples").mkdir()
    ctx = EvaluationContext.from_cli(
        project_root=str(src_root),
        src_dir="src",
        samples_dir="samples",
    )
    score = PipelineLatencyEvaluator().evaluate(ctx=ctx)
    target = score.metadata.get("target", "")
    assert "module.py" in target


# ---------------------------------------------------------------------------
# Phase 2 — Capability D12/D13/D20
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evaluator_cls,dim_name",
    [
        (AbstractionQualityEvaluator, "abstraction_quality"),
        (CodeReviewAccuracyEvaluator, "code_review_accuracy"),
    ],
)
def test_d12_d13_use_ctx_src_dir(
    evaluator_cls,
    dim_name: str,
    tmp_path: Path,
) -> None:
    """D12 / D13 must scan ctx.src_dir, not the constructor default."""
    ctx = _make_project(tmp_path, with_py=True)
    assert evaluator_cls.requires_context is True
    score = evaluator_cls().evaluate(ctx=ctx)
    assert score.name == dim_name
    assert str(ctx.src_dir) == score.metadata.get("src_dir")


def test_d20_agent_analysis_uses_ctx_project_root(tmp_path: Path) -> None:
    """D20 AgentAnalysisQualityEvaluator binds project_root from ctx."""
    ctx = _make_project(tmp_path, with_py=True)
    assert AgentAnalysisQualityEvaluator.requires_context is True
    score = AgentAnalysisQualityEvaluator().evaluate(ctx=ctx)
    # Even if 0/5 checks pass for an empty project, metadata must
    # reflect that ctx.project_root was honoured.
    assert score.metadata.get("project_root") == str(ctx.project_root)
    assert score.metadata.get("src_dir") == str(ctx.src_dir)


# ---------------------------------------------------------------------------
# Phase 3 — Hygiene (D-h: module_count, docstring_coverage, lint_cleanliness)
# ---------------------------------------------------------------------------


def test_module_count_uses_ctx_src_dir(tmp_path: Path) -> None:
    """LiveModuleCountEvaluator must honour ctx.src_dir."""
    ctx = _make_project(tmp_path, with_py=True)
    assert LiveModuleCountEvaluator.requires_context is True
    score = LiveModuleCountEvaluator().evaluate(ctx=ctx)
    # 1 *.py file (app.py) — __init__.py is excluded
    assert score.value == 1.0
    assert score.metadata.get("src_dir") == str(ctx.src_dir)


def test_docstring_coverage_uses_ctx_src_dir(tmp_path: Path) -> None:
    """DocstringCoverageEvaluator must honour ctx.src_dir."""
    ctx = _make_project(tmp_path, with_py=True)
    assert DocstringCoverageEvaluator.requires_context is True
    score = DocstringCoverageEvaluator().evaluate(ctx=ctx)
    assert score.metadata.get("src_dir") == str(ctx.src_dir)
    # public_func has a docstring → 100%
    assert score.value == 100.0


def test_lint_cleanliness_uses_ctx_src_dir(tmp_path: Path) -> None:
    """LintCleanlinessEvaluator must honour ctx.src_dir."""
    ctx = _make_project(tmp_path, with_py=True)
    assert LintCleanlinessEvaluator.requires_context is True
    score = LintCleanlinessEvaluator().evaluate(ctx=ctx)
    assert score.metadata.get("src_dir") == str(ctx.src_dir)


# ---------------------------------------------------------------------------
# Cross-cutting: two contexts → distinct metadata
# ---------------------------------------------------------------------------


def test_two_contexts_yield_distinct_module_counts(tmp_path: Path) -> None:
    """Two projects with different src trees produce different module counts.

    This is the core anti-silent-fallback assertion: before C01, both
    contexts would have hit the constructor's ``src/nines`` default and
    returned 72. After the migration, each ctx returns its own count.
    """
    ctx_a = _make_project(tmp_path / "a", with_py=True)
    ctx_b = _make_project(tmp_path / "b", with_py=True)
    # Add a second module to project b so they differ
    (ctx_b.src_dir / "extra.py").write_text("def g(): pass\n", encoding="utf-8")

    ev = LiveModuleCountEvaluator()
    a = ev.evaluate(ctx=ctx_a)
    b = ev.evaluate(ctx=ctx_b)

    assert a.value == 1.0
    assert b.value == 2.0
    assert a.metadata["src_dir"] != b.metadata["src_dir"]


def test_two_contexts_yield_distinct_pipeline_targets(tmp_path: Path) -> None:
    """Two projects produce distinct pipeline_latency targets."""
    ctx_a = _make_project(tmp_path / "a", with_py=True)
    ctx_b = _make_project(tmp_path / "b", with_py=True)
    ev = PipelineLatencyEvaluator()
    a = ev.evaluate(ctx=ctx_a)
    b = ev.evaluate(ctx=ctx_b)
    assert a.metadata["target"] != b.metadata["target"]


# ---------------------------------------------------------------------------
# Backward-compat: ctx=None still works (legacy fallback path)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evaluator_cls",
    [
        LiveModuleCountEvaluator,
        DocstringCoverageEvaluator,
    ],
)
def test_legacy_ctx_none_still_works(evaluator_cls, tmp_path: Path) -> None:
    """ctx=None must fall back to constructor src_dir without raising."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("def f(): pass\n", encoding="utf-8")
    score = evaluator_cls(src_dir=str(src)).evaluate(ctx=None)
    # Just assert it produced a score without crashing.
    assert score.name in ("module_count", "docstring_coverage")


def test_d16_pipeline_latency_no_py_files_does_not_fall_back_to_nines(
    tmp_path: Path,
) -> None:
    """When ctx.src_dir has no *.py, target must be ctx.src_dir itself —
    never silently re-targeting the constructor's NineS default.

    This is the hardest anti-silent-fallback assertion: a foreign repo
    with no Python files (like caveman, which is a Markdown skill) must
    NOT cause the evaluator to fall back to ``src/nines/__init__.py``.
    """
    src = tmp_path / "src"
    src.mkdir()
    # No .py files at all
    (src / "README.md").write_text("# foreign", encoding="utf-8")
    (tmp_path / "samples").mkdir()
    ctx = EvaluationContext.from_cli(
        project_root=str(tmp_path),
        src_dir="src",
        samples_dir="samples",
    )
    score = PipelineLatencyEvaluator().evaluate(ctx=ctx)
    target = score.metadata.get("target", "")
    # target must point at ctx.src_dir, not the NineS constructor default
    assert "src/nines" not in target, (
        f"Silent fallback to NineS detected! target={target!r}"
    )
    assert str(ctx.src_dir) in target
