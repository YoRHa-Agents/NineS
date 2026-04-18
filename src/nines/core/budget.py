"""Per-evaluator wall-clock budget for the self-eval runner.

The §4.7 baseline shows a single bad evaluator can hang for >5 minutes
silently when ``--src-dir`` is unfriendly to ``pytest --collect-only``.
This module provides a :class:`TimeBudget` dataclass and an
``evaluator_budget(name, budget)`` context manager that runs the wrapped
work on a *daemon* :class:`threading.Thread`, enforcing
``hard_seconds`` via :py:meth:`threading.Thread.join`.

Daemon threads do not keep the interpreter alive, so a hung worker
stuck on a blocking syscall will not prevent the process from
terminating after the runner finishes the rest of the dimensions.
Cooperative cancellation is supported via the optional ``cancel_flag``
argument: long-running evaluators that periodically check the flag can
exit cleanly, but pure-Python CPU-bound infinite loops are *not*
cancellable in this POC (a child-process executor is deferred to v2.3
per the C04 design notes).

Covers: C04 (per-evaluator wall-clock budget).
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EvaluatorBudgetExceeded(Exception):  # noqa: N818 — public API; renaming would break collector imports
    """Raised by :func:`evaluator_budget` when ``hard_seconds`` elapses.

    Carries the evaluator name and elapsed wall time so reports can
    record exactly which dimension breached.
    """

    def __init__(self, name: str, elapsed_s: float, hard_seconds: float) -> None:
        self.name = name
        self.elapsed_s = elapsed_s
        self.hard_seconds = hard_seconds
        super().__init__(
            f"evaluator '{name}' exceeded hard budget "
            f"{hard_seconds:.1f}s (elapsed {elapsed_s:.1f}s)"
        )


@dataclass
class TimeBudget:
    """Soft / hard wall-clock budget.

    Attributes
    ----------
    soft_seconds:
        Threshold at which a warning is logged but execution continues.
    hard_seconds:
        Wall budget after which :class:`EvaluatorBudgetExceeded` is
        raised by :func:`evaluator_budget`.
    """

    soft_seconds: float
    hard_seconds: float

    def __post_init__(self) -> None:
        if self.hard_seconds <= 0:
            msg = f"hard_seconds must be > 0, got {self.hard_seconds}"
            raise ValueError(msg)
        if self.soft_seconds < 0:
            msg = f"soft_seconds must be >= 0, got {self.soft_seconds}"
            raise ValueError(msg)
        if self.soft_seconds > self.hard_seconds:
            msg = (
                "soft_seconds must not exceed hard_seconds "
                f"(soft={self.soft_seconds}, hard={self.hard_seconds})"
            )
            raise ValueError(msg)


@contextmanager
def evaluator_budget(
    name: str,
    budget: TimeBudget,
    *,
    cancel_flag: threading.Event | None = None,
) -> Iterator[Callable[[Callable[[], T]], T]]:
    """Run a callable within *budget* wall time.

    The yielded value is a single-shot ``run()`` callable that the
    caller invokes with the work to execute.  Each invocation spawns a
    fresh daemon thread, joins it with ``timeout=hard_seconds``, and
    raises :class:`EvaluatorBudgetExceeded` if it doesn't finish in
    time.  The thread is left to expire on its own (daemon=True
    guarantees it doesn't block process exit).

    Examples
    --------
    >>> with evaluator_budget("my_dim", TimeBudget(5.0, 30.0)) as run:
    ...     result = run(lambda: do_work())

    Parameters
    ----------
    name:
        Evaluator name (for log + exception messages).
    budget:
        :class:`TimeBudget` to enforce.
    cancel_flag:
        Optional :class:`threading.Event` set right before raising
        :class:`EvaluatorBudgetExceeded`.  Cooperative evaluators that
        check the flag can exit cleanly when it fires.

    Raises
    ------
    EvaluatorBudgetExceeded
        On hard-timeout breach.  Exceptions raised inside the wrapped
        callable propagate verbatim through the ``run()`` invocation.
    """

    def run(fn: Callable[[], T]) -> T:
        # Holders for the worker thread's result / exception so the
        # caller can see them after join.
        result_box: list[T] = []
        exc_box: list[BaseException] = []

        def target() -> None:
            try:
                result_box.append(fn())
            except BaseException as exc:  # noqa: BLE001
                # Capture so the caller can re-raise.  We never log
                # silently — see the post-join branch below.
                exc_box.append(exc)

        worker = threading.Thread(
            target=target,
            name=f"budget-{name}",
            daemon=True,
        )
        start = time.monotonic()
        worker.start()
        worker.join(timeout=budget.hard_seconds)
        elapsed = time.monotonic() - start

        if worker.is_alive():
            # Hard-timeout breach: signal cooperative cancellation and
            # raise.  The daemon worker keeps running but won't block
            # process exit.
            if cancel_flag is not None:
                cancel_flag.set()
            logger.warning(
                "Evaluator %s exceeded hard budget %.1fs (elapsed %.1fs)",
                name,
                budget.hard_seconds,
                elapsed,
            )
            raise EvaluatorBudgetExceeded(
                name=name,
                elapsed_s=elapsed,
                hard_seconds=budget.hard_seconds,
            )

        if exc_box:
            # Re-raise the worker's exception verbatim — never silently
            # swallow.
            raise exc_box[0]

        if elapsed > budget.soft_seconds:
            logger.info(
                "Evaluator %s exceeded soft budget %.1fs (elapsed %.1fs)",
                name,
                budget.soft_seconds,
                elapsed,
            )

        if not result_box:
            # Worker completed without raising and without setting a
            # result — only possible when fn() returned None.
            return None  # type: ignore[return-value]
        return result_box[0]

    yield run


__all__ = ["EvaluatorBudgetExceeded", "TimeBudget", "evaluator_budget"]
