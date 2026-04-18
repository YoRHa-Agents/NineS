"""``CostBudget`` for bounded execution of evaluation runs.

Tracks token / dollar / wall-clock spend across a sequence of evaluator
calls and raises :class:`CostExceeded` once any limit is breached.  The
``EvalRunner`` consumes this so a runaway batch can be aborted before
burning the entire CI budget.

Covers: C05 (cost-budget guard).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CostExceeded(Exception):
    """Raised by :meth:`CostBudget.add` when a configured limit is breached."""


@dataclass
class CostBudget:
    """Cumulative budget across an evaluation run.

    All limits are optional; ``None`` means "unbounded" for that
    dimension.  Pass ``token_limit=0`` (etc.) to forbid all spend.

    Attributes
    ----------
    token_limit:
        Maximum cumulative tokens spent.
    dollar_limit:
        Maximum cumulative dollar spend.
    time_limit_s:
        Maximum cumulative wall-clock seconds.
    """

    token_limit: int | None = None
    dollar_limit: float | None = None
    time_limit_s: float | None = None

    tokens_spent: int = 0
    dollars_spent: float = 0.0
    elapsed_s: float = 0.0

    def add(
        self,
        *,
        tokens: int = 0,
        dollars: float = 0.0,
        elapsed_s: float = 0.0,
    ) -> None:
        """Charge *tokens* / *dollars* / *elapsed_s* against the budget.

        Raises
        ------
        CostExceeded
            If any non-``None`` limit would be breached after the charge.
            The internal counters are updated *before* the raise so the
            caller can inspect the totals; downstream consumers must
            treat the raise as a request to abort the outer loop.
        """
        if tokens < 0 or dollars < 0 or elapsed_s < 0:
            msg = (
                "CostBudget.add cannot accept negative deltas "
                f"(tokens={tokens} dollars={dollars} elapsed_s={elapsed_s})"
            )
            raise ValueError(msg)

        self.tokens_spent += tokens
        self.dollars_spent += dollars
        self.elapsed_s += elapsed_s

        breaches: list[str] = []
        if self.token_limit is not None and self.tokens_spent > self.token_limit:
            breaches.append(
                f"tokens={self.tokens_spent} > limit={self.token_limit}"
            )
        if self.dollar_limit is not None and self.dollars_spent > self.dollar_limit:
            breaches.append(
                f"dollars={self.dollars_spent} > limit={self.dollar_limit}"
            )
        if self.time_limit_s is not None and self.elapsed_s > self.time_limit_s:
            breaches.append(
                f"elapsed_s={self.elapsed_s} > limit={self.time_limit_s}"
            )

        if breaches:
            msg = "CostBudget exceeded: " + ", ".join(breaches)
            logger.warning(msg)
            raise CostExceeded(msg)

    def remaining(self) -> dict[str, float | int | None]:
        """Return a snapshot of remaining budget across each dimension."""
        return {
            "tokens": (
                None
                if self.token_limit is None
                else max(0, self.token_limit - self.tokens_spent)
            ),
            "dollars": (
                None
                if self.dollar_limit is None
                else max(0.0, self.dollar_limit - self.dollars_spent)
            ),
            "elapsed_s": (
                None
                if self.time_limit_s is None
                else max(0.0, self.time_limit_s - self.elapsed_s)
            ),
        }


__all__ = ["CostBudget", "CostExceeded"]
