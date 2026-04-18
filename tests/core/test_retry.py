"""Tests for ``nines.core.retry`` (C05 — with_retry helper)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.core.retry import (  # noqa: E402
    RetryPolicy,
    TransientError,
    with_retry,
)


def test_succeeds_on_first_attempt() -> None:
    """A function that succeeds immediately is called exactly once."""
    fn = Mock(return_value=42)
    sleep = Mock()
    out = with_retry(fn, RetryPolicy(attempts=3), sleep=sleep)
    assert out == 42
    assert fn.call_count == 1
    assert sleep.call_count == 0


def test_retries_then_succeeds() -> None:
    """Retries on TransientError and succeeds when it stops raising."""
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("transient")
        return "ok"

    sleep = Mock()
    out = with_retry(fn, RetryPolicy(attempts=5, base_backoff_s=0.01), sleep=sleep)
    assert out == "ok"
    assert calls["n"] == 3
    # Two sleeps: between attempts 1→2 and 2→3.
    assert sleep.call_count == 2


def test_exhausts_retries_re_raises_last() -> None:
    """When all attempts fail with TransientError, the last one re-raises."""
    fn = Mock(side_effect=TransientError("nope"))
    sleep = Mock()
    with pytest.raises(TransientError):
        with_retry(fn, RetryPolicy(attempts=2, base_backoff_s=0.5), sleep=sleep)
    assert fn.call_count == 2
    # 1 sleep (between attempts 1 and 2); none after the final failure.
    assert sleep.call_count == 1


def test_non_retry_eligible_raises_immediately() -> None:
    """An unrelated exception is re-raised immediately, no retries."""
    fn = Mock(side_effect=ValueError("nope"))
    sleep = Mock()
    with pytest.raises(ValueError):
        with_retry(fn, RetryPolicy(attempts=5), sleep=sleep)
    assert fn.call_count == 1
    assert sleep.call_count == 0


def test_observer_invoked_with_attempt_index() -> None:
    """on_retry observer sees (attempt_idx, exc) for every retry."""
    seen: list[tuple[int, str]] = []
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError(f"err{calls['n']}")
        return "done"

    def observer(idx: int, exc: BaseException) -> None:
        seen.append((idx, str(exc)))

    out = with_retry(
        fn,
        RetryPolicy(attempts=5, base_backoff_s=0.0),
        on_retry=observer,
        sleep=Mock(),
    )
    assert out == "done"
    assert seen == [(0, "err1"), (1, "err2")]


def test_retry_policy_rejects_zero_attempts() -> None:
    """RetryPolicy with attempts=0 raises at construction time."""
    with pytest.raises(ValueError):
        RetryPolicy(attempts=0)


def test_retry_policy_rejects_inverted_backoff() -> None:
    """RetryPolicy with max_backoff < base raises."""
    with pytest.raises(ValueError):
        RetryPolicy(base_backoff_s=2.0, max_backoff_s=1.0)
