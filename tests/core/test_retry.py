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


# ======================================================================
# Async helper tests (with_retry_async)
# ======================================================================

import asyncio  # noqa: E402

from nines.core.retry import with_retry_async  # noqa: E402


def test_with_retry_async_success_no_retry() -> None:
    """An async fn that returns immediately is awaited exactly once."""
    calls = {"n": 0}

    async def fn() -> int:
        calls["n"] += 1
        return 7

    sleep_calls: list[float] = []

    async def fake_sleep(d: float) -> None:
        sleep_calls.append(d)

    out = asyncio.run(
        with_retry_async(
            fn,
            RetryPolicy(attempts=3),
            sleep=fake_sleep,
        )
    )
    assert out == 7
    assert calls["n"] == 1
    assert sleep_calls == []


def test_with_retry_async_success_after_retry() -> None:
    """async fn that fails 1× with TransientError then succeeds."""
    calls = {"n": 0}

    async def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TransientError(f"flake-{calls['n']}")
        return "ok"

    sleep_calls: list[float] = []

    async def fake_sleep(d: float) -> None:
        sleep_calls.append(d)

    out = asyncio.run(
        with_retry_async(
            fn,
            RetryPolicy(attempts=5, base_backoff_s=0.01),
            sleep=fake_sleep,
        )
    )
    assert out == "ok"
    assert calls["n"] == 2
    # One sleep between attempts 1 → 2.
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(0.01)


def test_with_retry_async_exhaustion() -> None:
    """async fn that always fails raises after exactly ``policy.attempts`` calls."""
    calls = {"n": 0}

    async def fn() -> None:
        calls["n"] += 1
        raise TransientError(f"persistent-{calls['n']}")

    async def fake_sleep(_d: float) -> None:
        return None

    with pytest.raises(TransientError):
        asyncio.run(
            with_retry_async(
                fn,
                RetryPolicy(attempts=3, base_backoff_s=0.0),
                sleep=fake_sleep,
            )
        )
    assert calls["n"] == 3


def test_with_retry_async_non_retryable() -> None:
    """async fn raising ValueError under retry_on=(TransientError,) propagates immediately."""
    calls = {"n": 0}

    async def fn() -> None:
        calls["n"] += 1
        raise ValueError("not transient")

    sleep_calls: list[float] = []

    async def fake_sleep(d: float) -> None:
        sleep_calls.append(d)

    with pytest.raises(ValueError, match="not transient"):
        asyncio.run(
            with_retry_async(
                fn,
                RetryPolicy(attempts=5, retry_on=(TransientError,)),
                sleep=fake_sleep,
            )
        )
    # Exactly one call, no retries, no sleeps.
    assert calls["n"] == 1
    assert sleep_calls == []
