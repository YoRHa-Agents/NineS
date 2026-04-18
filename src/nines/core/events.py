"""Lightweight synchronous event system for cross-module communication.

The ``EventBus`` decouples modules so that, for example, the collector
can notify the analyzer that new sources are available without a direct
import dependency.  Handler exceptions are caught and logged (not
silenced) to prevent one faulty subscriber from breaking the emitter.

Covers: FR-512 (EventBus), FR-311 (progress events), FR-114.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from nines.core.errors import NinesError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Predefined event type constants
# ---------------------------------------------------------------------------

COLLECTION_COMPLETE: str = "collection_complete"
"""Emitted when a collector finishes gathering items from a source."""

ANALYSIS_COMPLETE: str = "analysis_complete"
"""Emitted when the analysis pipeline finishes processing a target."""

EVAL_COMPLETE: str = "eval_complete"
"""Emitted when the evaluation pipeline finishes scoring all tasks."""

ITERATION_COMPLETE: str = "iteration_complete"
"""Emitted when a single MAPIM iteration round completes."""

# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------

EventHandler = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    """An immutable event carrying a type tag and arbitrary payload.

    Attributes
    ----------
    type:
        String identifier for the event kind (use the module-level
        constants for well-known types).
    data:
        Arbitrary payload dictionary.
    timestamp:
        UTC datetime when the event was created.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class EventBus:
    """Synchronous publish / subscribe event bus.

    Thread-safety is *not* required for the MVP (single-user,
    single-process).  Handler exceptions are caught and logged but
    never propagated to the emitter, preventing one faulty handler
    from breaking the pipeline.  This satisfies NFR-21 because the
    exception **is** logged, not silently swallowed.

    Parameters
    ----------
    max_handlers_per_event:
        Safety cap on the number of handlers that may be registered
        for a single event type.
    """

    _instance: EventBus | None = None

    def __init__(self, max_handlers_per_event: int = 50) -> None:
        """Initialize event bus."""
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._max_handlers = max_handlers_per_event

    # -- singleton helpers ---------------------------------------------------

    @classmethod
    def get(cls) -> EventBus:
        """Return the process-wide singleton ``EventBus``."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Discard the singleton (useful in tests)."""
        cls._instance = None

    # -- public API ----------------------------------------------------------

    def subscribe(self, event_type: str, callback: EventHandler) -> None:
        """Register *callback* to be invoked when *event_type* is published.

        Parameters
        ----------
        event_type:
            The event type string to listen for.
        callback:
            A callable accepting a single :class:`Event` argument.

        Raises
        ------
        NinesError
            If the per-event handler limit has been reached.
        """
        handlers = self._handlers[event_type]
        if len(handlers) >= self._max_handlers:
            raise NinesError(
                message=(
                    f"Max handlers ({self._max_handlers}) exceeded for event type '{event_type}'"
                ),
                details={"event_type": event_type, "limit": self._max_handlers},
            )
        handlers.append(callback)

    def publish(self, event: Event) -> None:
        """Dispatch *event* to all subscribers of its type.

        Handler exceptions are caught, logged at ERROR level, and
        swallowed so the emitter is never affected by handler bugs.

        Parameters
        ----------
        event:
            The event to dispatch.
        """
        for handler in self._handlers.get(event.type, []):
            try:
                handler(event)
            except Exception:
                logger.error(
                    "Event handler %s failed for event type '%s'",
                    getattr(handler, "__qualname__", repr(handler)),
                    event.type,
                    exc_info=True,
                )

    def clear(self, event_type: str | None = None) -> None:
        """Remove registered handlers.

        Parameters
        ----------
        event_type:
            If given, only handlers for this type are removed.
            If ``None``, **all** handlers are removed.
        """
        if event_type is None:
            self._handlers.clear()
        else:
            self._handlers.pop(event_type, None)
