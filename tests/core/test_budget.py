"""Tests for ``nines.core.budget`` (C04 — TimeBudget + evaluator_budget)."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.core.budget import (  # noqa: E402
    EvaluatorBudgetExceeded,
    TimeBudget,
    evaluator_budget,
)


def test_no_timeout_returns_value() -> None:
    """Within-budget callable returns its value normally."""
    with evaluator_budget("ok", TimeBudget(0.5, 1.0)) as run:
        out = run(lambda: 42)
    assert out == 42


def test_soft_warning_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    """Crossing soft but not hard logs a warning; no exception."""
    caplog.set_level("INFO")
    def slow() -> str:
        time.sleep(0.15)
        return "ok"
    with evaluator_budget("slow", TimeBudget(soft_seconds=0.05, hard_seconds=2.0)) as run:
        out = run(slow)
    assert out == "ok"
    soft_warns = [r for r in caplog.records if "soft budget" in r.getMessage()]
    assert len(soft_warns) == 1


def test_hard_timeout_raises_and_sets_cancel_flag() -> None:
    """Crossing hard timeout raises EvaluatorBudgetExceeded and triggers cancel_flag."""
    cancel = threading.Event()
    def hangs() -> None:
        # Cooperative: check the flag, but mostly just sleep.
        for _ in range(100):
            if cancel.is_set():
                return None
            time.sleep(0.05)
        return None
    with evaluator_budget(
        "hang",
        TimeBudget(soft_seconds=0.05, hard_seconds=0.2),
        cancel_flag=cancel,
    ) as run:
        with pytest.raises(EvaluatorBudgetExceeded) as exc_info:
            run(hangs)
    assert exc_info.value.name == "hang"
    assert exc_info.value.elapsed_s >= 0.2
    assert cancel.is_set()


def test_exception_passthrough_inside_budget() -> None:
    """Exceptions from the wrapped callable propagate verbatim."""
    def boom() -> None:
        raise RuntimeError("boom")
    with evaluator_budget("err", TimeBudget(0.05, 1.0)) as run:
        with pytest.raises(RuntimeError, match="boom"):
            run(boom)


def test_time_budget_validates_bounds() -> None:
    """TimeBudget rejects nonsensical configurations at construction."""
    with pytest.raises(ValueError):
        TimeBudget(soft_seconds=0, hard_seconds=0)
    with pytest.raises(ValueError):
        TimeBudget(soft_seconds=-1, hard_seconds=10)
    with pytest.raises(ValueError):
        TimeBudget(soft_seconds=20, hard_seconds=10)
