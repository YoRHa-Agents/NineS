"""Tests for nines.core.errors — error hierarchy and construction."""

from __future__ import annotations

import pytest

from nines.core.errors import (
    AnalyzerError,
    CollectorError,
    ConfigError,
    EvalError,
    NinesError,
    OrchestrationError,
    SandboxError,
    SkillError,
)


class TestNinesErrorBase:
    def test_message_and_str(self) -> None:
        err = NinesError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"

    def test_details(self) -> None:
        err = NinesError("fail", details={"code": "E001", "field": "scorer"})
        assert err.details["code"] == "E001"

    def test_cause_chaining(self) -> None:
        root = ValueError("bad value")
        err = NinesError("wrapped", cause=root)
        assert err.cause is root
        assert err.__cause__ is root

    def test_defaults(self) -> None:
        err = NinesError()
        assert err.message == ""
        assert err.details == {}
        assert err.cause is None

    def test_is_exception(self) -> None:
        with pytest.raises(NinesError):
            raise NinesError("boom")


class TestSubclassHierarchy:
    """All subclasses inherit from NinesError and can be caught generically."""

    @pytest.mark.parametrize(
        "error_cls",
        [
            EvalError,
            CollectorError,
            AnalyzerError,
            SandboxError,
            ConfigError,
            SkillError,
            OrchestrationError,
        ],
    )
    def test_is_subclass(self, error_cls: type) -> None:
        assert issubclass(error_cls, NinesError)

    @pytest.mark.parametrize(
        "error_cls",
        [
            EvalError,
            CollectorError,
            AnalyzerError,
            SandboxError,
            ConfigError,
            SkillError,
            OrchestrationError,
        ],
    )
    def test_caught_by_base(self, error_cls: type) -> None:
        with pytest.raises(NinesError):
            raise error_cls("test")

    @pytest.mark.parametrize(
        "error_cls",
        [
            EvalError,
            CollectorError,
            AnalyzerError,
            SandboxError,
            ConfigError,
            SkillError,
            OrchestrationError,
        ],
    )
    def test_carries_details_and_cause(self, error_cls: type) -> None:
        cause = RuntimeError("root")
        err = error_cls("msg", details={"key": "val"}, cause=cause)
        assert err.message == "msg"
        assert err.details == {"key": "val"}
        assert err.cause is cause


class TestEvalErrorSpecific:
    def test_message_propagation(self) -> None:
        err = EvalError("task execution timed out")
        assert "timed out" in str(err)


class TestCollectorErrorSpecific:
    def test_message_propagation(self) -> None:
        err = CollectorError("rate limit exceeded", details={"source": "github"})
        assert err.details["source"] == "github"


class TestConfigErrorSpecific:
    def test_message_propagation(self) -> None:
        err = ConfigError("invalid scorer name")
        assert "scorer" in err.message
