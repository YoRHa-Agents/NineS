"""``with_retry`` + ``RetryPolicy`` for transient-failure resilience.

Centralises retry semantics that previously lived ad-hoc inside
``collector/github.py`` and ``collector/arxiv.py``.  The eval runner
also gains a hook so the existing ``NinesConfig.eval_max_retries`` knob
(per the gap-analysis §1: "configured-but-unused") finally controls
behaviour.

Covers: C05 (with_retry helper).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TransientError(Exception):
    """Marker base class for retry-eligible exceptions.

    Callers typed this way (or registered via :class:`RetryPolicy`) will
    be retried by :func:`with_retry`; everything else is re-raised
    immediately.
    """


@dataclass
class RetryPolicy:
    """Policy controlling :func:`with_retry` behaviour.

    Attributes
    ----------
    attempts:
        Total number of attempts (must be ≥ 1).  ``attempts=3`` retries
        twice after the initial call.
    base_backoff_s:
        Initial sleep between retries; doubled each attempt up to
        :attr:`max_backoff_s`.
    max_backoff_s:
        Upper bound on the exponential back-off sleep.
    retry_on:
        Tuple of exception classes that trigger a retry.  Defaults to
        :class:`TransientError`.
    """

    attempts: int = 3
    base_backoff_s: float = 0.5
    max_backoff_s: float = 8.0
    retry_on: tuple[type[BaseException], ...] = field(
        default_factory=lambda: (TransientError,),
    )

    def __post_init__(self) -> None:
        if self.attempts < 1:
            msg = f"RetryPolicy.attempts must be >= 1, got {self.attempts}"
            raise ValueError(msg)
        if self.base_backoff_s < 0 or self.max_backoff_s < self.base_backoff_s:
            msg = (
                "RetryPolicy backoff bounds invalid: "
                f"base={self.base_backoff_s} max={self.max_backoff_s}"
            )
            raise ValueError(msg)

    def backoff_for(self, attempt_idx: int) -> float:
        """Return the back-off (seconds) to wait before *attempt_idx* (0-based).

        Exponential with cap: ``min(max_backoff_s, base_backoff_s * 2**i)``.
        """
        if attempt_idx <= 0:
            return 0.0
        return min(
            self.max_backoff_s,
            self.base_backoff_s * (2 ** (attempt_idx - 1)),
        )


def with_retry(
    fn: Callable[[], T],
    policy: RetryPolicy,
    *,
    on_retry: Callable[[int, BaseException], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run *fn* with retry semantics governed by *policy*.

    Parameters
    ----------
    fn:
        Zero-arg callable to invoke.
    policy:
        :class:`RetryPolicy` controlling attempts and back-off.
    on_retry:
        Optional observer invoked as ``on_retry(attempt_idx, exc)`` just
        before each retry sleep.  Useful for metrics / logging in tests.
    sleep:
        Sleep callable (test injection point).  Defaults to
        ``time.sleep``.

    Returns
    -------
    T
        Whatever *fn* returns on the first successful attempt.

    Raises
    ------
    BaseException
        Re-raises the final attempt's exception when all retries are
        exhausted, or any non-retry-eligible exception immediately.
    """
    last_exc: BaseException | None = None
    for attempt in range(policy.attempts):
        try:
            return fn()
        except policy.retry_on as exc:
            last_exc = exc
            remaining = policy.attempts - attempt - 1
            if remaining <= 0:
                logger.warning(
                    "with_retry: exhausted %d attempt(s); re-raising %s",
                    policy.attempts, type(exc).__name__,
                )
                raise
            backoff = policy.backoff_for(attempt + 1)
            logger.info(
                "with_retry: attempt %d/%d failed with %s; sleeping %.3fs",
                attempt + 1, policy.attempts, type(exc).__name__, backoff,
            )
            if on_retry is not None:
                # Observer must not swallow exceptions silently; let them
                # propagate so callers see misconfigurations.
                on_retry(attempt, exc)
            if backoff > 0:
                sleep(backoff)
        except BaseException:
            # Non-retry-eligible: re-raise immediately, never silently
            # swallow.
            raise
    # Defensive: shouldn't reach here because the loop either returns or
    # raises, but keeps mypy happy and makes intent explicit.
    if last_exc is not None:
        raise last_exc
    msg = "with_retry: zero attempts configured (RetryPolicy bug)"
    raise RuntimeError(msg)


__all__ = ["RetryPolicy", "TransientError", "with_retry"]
