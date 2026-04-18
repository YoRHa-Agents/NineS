"""Tests for ``nines.core.cost_budget`` (C05 — CostBudget)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.core.cost_budget import (  # noqa: E402
    CostBudget,
    CostExceeded,
)


def test_within_limits_no_raise() -> None:
    """Charging within bounds updates counters and does not raise."""
    b = CostBudget(token_limit=1000, dollar_limit=10.0, time_limit_s=30.0)
    b.add(tokens=100, dollars=1.0, elapsed_s=5.0)
    b.add(tokens=200, dollars=2.0, elapsed_s=10.0)
    assert b.tokens_spent == 300
    assert b.dollars_spent == pytest.approx(3.0)
    assert b.elapsed_s == pytest.approx(15.0)
    assert b.remaining()["tokens"] == 700


def test_token_limit_exceeded_raises() -> None:
    """Crossing token_limit raises CostExceeded with informative message."""
    b = CostBudget(token_limit=100)
    b.add(tokens=80)
    with pytest.raises(CostExceeded) as exc_info:
        b.add(tokens=50)
    assert "tokens" in str(exc_info.value)


def test_negative_delta_rejected() -> None:
    """Negative deltas raise ValueError, never silently apply credit."""
    b = CostBudget(token_limit=100)
    with pytest.raises(ValueError):
        b.add(tokens=-1)
    with pytest.raises(ValueError):
        b.add(elapsed_s=-1.0)
