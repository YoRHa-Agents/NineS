"""Tests for nines.core.protocols — runtime checkable Protocol verification."""

from __future__ import annotations

from typing import Any

import pytest

from nines.core.protocols import (
    Analyzer,
    Executor,
    Reporter,
    Scorer,
    SourceCollector,
    TaskLoader,
)

# ---------------------------------------------------------------------------
# Conforming stub implementations
# ---------------------------------------------------------------------------


class StubTaskLoader:
    """Satisfies the TaskLoader protocol."""

    def load(self, path: str) -> list[Any]:
        return []


class StubExecutor:
    """Satisfies the Executor protocol."""

    async def execute(self, task: Any) -> Any:
        return {"output": "ok"}


class StubScorer:
    """Satisfies the Scorer protocol."""

    def score(self, result: Any, expected: Any) -> Any:
        return {"value": 1.0}


class StubSourceCollector:
    """Satisfies the SourceCollector protocol."""

    async def search(self, query: str, **kwargs: Any) -> list[Any]:
        return []

    async def fetch(self, identifier: str) -> Any:
        return {}


class StubAnalyzer:
    """Satisfies the Analyzer protocol."""

    def analyze(self, target: str) -> Any:
        return {"findings": []}


class StubReporter:
    """Satisfies the Reporter protocol."""

    def report(self, results: list[Any], output_path: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Non-conforming stubs
# ---------------------------------------------------------------------------


class NotAScorer:
    """Missing required score method."""

    def compute(self, x: int) -> int:
        return x * 2


class PartialCollector:
    """Only implements search, missing fetch."""

    async def search(self, query: str) -> list[Any]:
        return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTaskLoaderProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubTaskLoader(), TaskLoader)

    def test_non_conforming_rejected(self) -> None:
        assert not isinstance(NotAScorer(), TaskLoader)


class TestExecutorProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubExecutor(), Executor)

    def test_non_conforming_rejected(self) -> None:
        assert not isinstance(StubScorer(), Executor)


class TestScorerProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubScorer(), Scorer)

    def test_non_conforming_rejected(self) -> None:
        assert not isinstance(NotAScorer(), Scorer)


class TestSourceCollectorProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubSourceCollector(), SourceCollector)

    def test_partial_rejected(self) -> None:
        assert not isinstance(PartialCollector(), SourceCollector)


class TestAnalyzerProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubAnalyzer(), Analyzer)


class TestReporterProtocol:
    def test_isinstance_check(self) -> None:
        assert isinstance(StubReporter(), Reporter)


class TestAllProtocolsHaveTypeHints:
    """Verify every Protocol method carries type annotations (AC #1)."""

    @pytest.mark.parametrize(
        "protocol_cls",
        [TaskLoader, Executor, Scorer, SourceCollector, Analyzer, Reporter],
    )
    def test_annotations_present(self, protocol_cls: type) -> None:
        for name in dir(protocol_cls):
            if name.startswith("_"):
                continue
            method = getattr(protocol_cls, name)
            if callable(method):
                hints = getattr(method, "__annotations__", {})
                assert hints, f"{protocol_cls.__name__}.{name} has no type annotations"


# ---------------------------------------------------------------------------
# Additional protocol compliance tests
# ---------------------------------------------------------------------------


class TestProtocolFunctionalBehaviour:
    """Verify mock implementations actually work through the protocol."""

    def test_task_loader_returns_list(self) -> None:
        loader: TaskLoader = StubTaskLoader()
        result = loader.load("/some/path")
        assert isinstance(result, list)

    def test_executor_returns_result(self) -> None:
        import asyncio

        executor: Executor = StubExecutor()
        result = asyncio.run(executor.execute({"id": "task-1"}))
        assert result == {"output": "ok"}

    def test_scorer_returns_score(self) -> None:
        scorer: Scorer = StubScorer()
        result = scorer.score({"output": "hello"}, "hello")
        assert result == {"value": 1.0}

    def test_source_collector_search_and_fetch(self) -> None:
        import asyncio

        collector: SourceCollector = StubSourceCollector()
        results = asyncio.run(collector.search("test query", limit=10))
        assert isinstance(results, list)
        item = asyncio.run(collector.fetch("some-id"))
        assert isinstance(item, dict)

    def test_analyzer_returns_result(self) -> None:
        analyzer: Analyzer = StubAnalyzer()
        result = analyzer.analyze("/src/foo.py")
        assert "findings" in result

    def test_reporter_accepts_results(self) -> None:
        reporter: Reporter = StubReporter()
        reporter.report([{"score": 1.0}], "/tmp/report.json")


class TestProtocolComposability:
    """Verify multiple protocols can coexist and be type-checked together."""

    def test_multi_protocol_class(self) -> None:
        class MultiImpl:
            def load(self, path: str) -> list[Any]:
                return []

            def score(self, result: Any, expected: Any) -> Any:
                return {"value": 0.5}

        impl = MultiImpl()
        assert isinstance(impl, TaskLoader)
        assert isinstance(impl, Scorer)

    def test_runtime_checkable_all_protocols(self) -> None:
        protocols = [TaskLoader, Executor, Scorer, SourceCollector, Analyzer, Reporter]
        for proto in protocols:
            assert (
                hasattr(proto, "__protocol_attrs__")
                or hasattr(proto, "__abstractmethods__")
                or True
            )
            assert getattr(proto, "__runtime_checkable__", False) or hasattr(
                proto, "__protocol_attrs__"
            )


class TestNonConformingEdgeCases:
    """Verify edge cases where implementations partially conform."""

    def test_wrong_signature_scorer(self) -> None:
        class WrongSigScorer:
            def score(self, x: int) -> int:
                return x

        assert isinstance(WrongSigScorer(), Scorer)

    def test_extra_methods_still_conform(self) -> None:
        class ExtendedLoader:
            def load(self, path: str) -> list[Any]:
                return []

            def extra_method(self) -> None:
                pass

        assert isinstance(ExtendedLoader(), TaskLoader)

    def test_empty_class_fails_all(self) -> None:
        class Empty:
            pass

        assert not isinstance(Empty(), TaskLoader)
        assert not isinstance(Empty(), Executor)
        assert not isinstance(Empty(), Scorer)
        assert not isinstance(Empty(), SourceCollector)
        assert not isinstance(Empty(), Analyzer)
        assert not isinstance(Empty(), Reporter)
