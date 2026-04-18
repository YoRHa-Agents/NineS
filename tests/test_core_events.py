"""Tests for nines.core.events — EventBus pub/sub and Event construction."""

from __future__ import annotations

from datetime import datetime

import pytest

from nines.core.errors import NinesError
from nines.core.events import (
    ANALYSIS_COMPLETE,
    COLLECTION_COMPLETE,
    EVAL_COMPLETE,
    ITERATION_COMPLETE,
    Event,
    EventBus,
)

# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------


class TestEvent:
    def test_construction(self) -> None:
        ev = Event(type="test", data={"key": "val"})
        assert ev.type == "test"
        assert ev.data == {"key": "val"}
        assert isinstance(ev.timestamp, datetime)

    def test_immutable(self) -> None:
        ev = Event(type="x")
        with pytest.raises(AttributeError):
            ev.type = "y"  # type: ignore[misc]

    def test_default_timestamp_is_utc(self) -> None:
        ev = Event(type="t")
        assert ev.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# Predefined event type constants
# ---------------------------------------------------------------------------


class TestEventTypeConstants:
    def test_constants_are_strings(self) -> None:
        for const in (
            COLLECTION_COMPLETE,
            ANALYSIS_COMPLETE,
            EVAL_COMPLETE,
            ITERATION_COMPLETE,
        ):
            assert isinstance(const, str)
            assert len(const) > 0


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class TestEventBus:
    @pytest.fixture(autouse=True)
    def _reset_singleton(self) -> None:
        EventBus.reset()

    def test_subscribe_and_publish(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe("test_evt", received.append)

        event = Event(type="test_evt", data={"x": 1})
        bus.publish(event)

        assert len(received) == 1
        assert received[0].data == {"x": 1}

    def test_multiple_handlers(self) -> None:
        bus = EventBus()
        calls: list[str] = []
        bus.subscribe("evt", lambda e: calls.append("a"))
        bus.subscribe("evt", lambda e: calls.append("b"))

        bus.publish(Event(type="evt"))
        assert calls == ["a", "b"]

    def test_no_cross_talk(self) -> None:
        bus = EventBus()
        received: list[str] = []
        bus.subscribe("alpha", lambda e: received.append("alpha"))
        bus.subscribe("beta", lambda e: received.append("beta"))

        bus.publish(Event(type="alpha"))
        assert received == ["alpha"]

    def test_handler_exception_is_logged_not_propagated(self) -> None:
        bus = EventBus()
        ok_results: list[Event] = []

        def bad_handler(e: Event) -> None:
            raise RuntimeError("handler crash")

        bus.subscribe("evt", bad_handler)
        bus.subscribe("evt", ok_results.append)

        bus.publish(Event(type="evt"))
        assert len(ok_results) == 1

    def test_clear_specific_type(self) -> None:
        bus = EventBus()
        calls: list[str] = []
        bus.subscribe("a", lambda e: calls.append("a"))
        bus.subscribe("b", lambda e: calls.append("b"))

        bus.clear("a")
        bus.publish(Event(type="a"))
        bus.publish(Event(type="b"))
        assert calls == ["b"]

    def test_clear_all(self) -> None:
        bus = EventBus()
        calls: list[str] = []
        bus.subscribe("a", lambda e: calls.append("a"))
        bus.subscribe("b", lambda e: calls.append("b"))

        bus.clear()
        bus.publish(Event(type="a"))
        bus.publish(Event(type="b"))
        assert calls == []

    def test_max_handlers_exceeded(self) -> None:
        bus = EventBus(max_handlers_per_event=2)
        bus.subscribe("evt", lambda e: None)
        bus.subscribe("evt", lambda e: None)
        with pytest.raises(NinesError, match="Max handlers"):
            bus.subscribe("evt", lambda e: None)

    def test_singleton_get(self) -> None:
        bus1 = EventBus.get()
        bus2 = EventBus.get()
        assert bus1 is bus2

    def test_singleton_reset(self) -> None:
        bus1 = EventBus.get()
        EventBus.reset()
        bus2 = EventBus.get()
        assert bus1 is not bus2

    def test_publish_to_no_subscribers(self) -> None:
        bus = EventBus()
        bus.publish(Event(type="ghost"))


# ---------------------------------------------------------------------------
# Integration: __init__ re-exports
# ---------------------------------------------------------------------------


class TestCoreReExports:
    def test_all_public_types_importable(self) -> None:
        from nines.core import (
            EvalTask,
        )

        assert EvalTask is not None
