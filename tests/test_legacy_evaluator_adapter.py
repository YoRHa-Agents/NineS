"""Tests for ``LegacyEvaluatorAdapter`` and the runner's auto-wrapping (C01 Phase 1).

Covers:
- Pre-existing evaluators without a ``ctx`` arg are wrapped on register.
- INFO-level log emitted at registration time.
- Adapter discards the ``ctx`` kwarg before delegating.
- Runner refuses (ConfigError) when ``requires_context=True`` and ``ctx is None``
  in strict mode.
- Modern evaluators that accept ``ctx`` are NOT wrapped and DO receive ctx.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.core.errors import ConfigError  # noqa: E402
from nines.iteration.context import EvaluationContext  # noqa: E402
from nines.iteration.self_eval import (  # noqa: E402
    DimensionScore,
    LegacyEvaluatorAdapter,
    SelfEvalRunner,
)


class _LegacyEvaluator:
    """Pre-C01 evaluator: evaluate() takes no kwargs."""

    def evaluate(self) -> DimensionScore:
        return DimensionScore(name="legacy", value=0.5)


class _ModernEvaluator:
    """C01-aware evaluator: requires_context=True + accepts ctx kwarg."""

    requires_context = True

    def __init__(self) -> None:
        self.last_ctx: EvaluationContext | None = None

    def evaluate(self, *, ctx: EvaluationContext | None = None) -> DimensionScore:
        self.last_ctx = ctx
        return DimensionScore(
            name="modern",
            value=1.0 if ctx is not None else 0.0,
        )


def test_legacy_evaluator_wrapping_auto_detected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Registering a no-ctx evaluator produces a LegacyEvaluatorAdapter wrap +
    INFO log."""
    runner = SelfEvalRunner()
    with caplog.at_level(logging.INFO, logger="nines.iteration.self_eval"):
        runner.register_dimension("legacy_dim", _LegacyEvaluator())

    wrapped = runner._evaluators["legacy_dim"]
    assert isinstance(wrapped, LegacyEvaluatorAdapter), (
        f"expected LegacyEvaluatorAdapter wrap, got {type(wrapped).__name__}"
    )
    # The adapter retains a reference to the original evaluator.
    assert isinstance(wrapped.wrapped, _LegacyEvaluator)
    # INFO log mentions the dimension name + adapter.
    assert any(
        "Wrapping legacy_dim in LegacyEvaluatorAdapter" in rec.getMessage()
        and rec.levelno == logging.INFO
        for rec in caplog.records
    ), f"missing expected INFO log; got: {[r.getMessage() for r in caplog.records]}"


def test_legacy_evaluator_evaluate_discards_ctx() -> None:
    """LegacyEvaluatorAdapter.evaluate() ignores the ``ctx`` kwarg."""
    inner = _LegacyEvaluator()
    adapter = LegacyEvaluatorAdapter(inner)

    score = adapter.evaluate(
        ctx=EvaluationContext(
            project_root=Path("/tmp/no/such/path"),
            src_dir=Path("/tmp/no/such/path/src"),
        )
    )
    # Adapter must not propagate ctx; the inner evaluate(self) sees no kwargs.
    assert score.name == "legacy"
    assert score.value == 0.5
    # Calling without any kwargs also works (back-compat).
    assert adapter.evaluate().name == "legacy"


def test_requires_context_evaluator_refuses_none_ctx() -> None:
    """Strict-mode runner refuses to start with ctx=None when a registered
    evaluator declares requires_context=True."""
    runner = SelfEvalRunner(strict_ctx=True)
    runner.register_dimension("ctx_dim", _ModernEvaluator())

    with pytest.raises(ConfigError) as excinfo:
        runner.run_all()

    err = excinfo.value
    assert "EvaluationContext is required" in str(err)
    assert err.details.get("dimensions") == ["ctx_dim"]


def test_modern_evaluator_passthrough(tmp_path: Path) -> None:
    """A modern (ctx-aware) evaluator is NOT wrapped and DOES receive ctx."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("def main(): pass\n", encoding="utf-8")

    runner = SelfEvalRunner(strict_ctx=True)
    modern = _ModernEvaluator()
    runner.register_dimension("modern_dim", modern)

    # NOT wrapped — runner stores the original instance directly.
    stored = runner._evaluators["modern_dim"]
    assert stored is modern, (
        f"modern evaluator was wrapped unnecessarily: {type(stored).__name__}"
    )

    ctx = EvaluationContext.from_cli(project_root=str(tmp_path), src_dir="src")
    report = runner.run_all(ctx=ctx)

    # Modern evaluator received the ctx and was passed through correctly.
    assert modern.last_ctx is ctx
    assert report.context_fingerprint == ctx.fingerprint()
    score = report.get_score("modern")
    assert score is not None
    assert score.value == 1.0
