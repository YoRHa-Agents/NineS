"""C05 polish — verify ``GitHubCollector`` delegates retries to ``with_retry``.

The pre-C05 collector hand-rolled a ``for attempt in range(...)`` loop
inside ``_request``.  After the refactor, every retry goes through
``nines.core.retry.with_retry`` with a ``RetryPolicy`` whose
``attempts`` matches ``GitHubConfig.max_retries``.

The existing happy-path coverage in ``tests/test_collector.py`` still
exercises the public API; this module pins the *delegation contract*
introduced by the refactor.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.collector import github as github_module  # noqa: E402
from nines.collector.github import (  # noqa: E402
    _RETRYABLE_EXCEPTIONS,
    GitHubCollector,
    GitHubConfig,
)
from nines.core.errors import CollectorError  # noqa: E402
from nines.core.retry import RetryPolicy, TransientHTTPStatus  # noqa: E402


def _ok_handler(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"items": []})


def test_request_invokes_with_retry_with_configured_policy() -> None:
    """``_request`` must call ``with_retry`` exactly once per request, with
    a ``RetryPolicy(attempts=cfg.max_retries, retry_on=_RETRYABLE_EXCEPTIONS)``.
    """
    transport = httpx.MockTransport(_ok_handler)
    client = httpx.Client(transport=transport, base_url="https://api.github.com")
    config = GitHubConfig(token="t", max_retries=4)
    collector = GitHubCollector(config=config, client=client)

    captured: dict[str, Any] = {}

    def fake_with_retry(fn: Any, policy: RetryPolicy, **_kw: Any) -> httpx.Response:
        captured["policy"] = policy
        captured["fn"] = fn
        return fn()

    with patch.object(github_module, "with_retry", side_effect=fake_with_retry) as wr:
        resp = collector._request("GET", "/search/repositories")

    assert resp.status_code == 200
    assert wr.call_count == 1
    policy = captured["policy"]
    assert isinstance(policy, RetryPolicy)
    assert policy.attempts == 4
    assert policy.retry_on == _RETRYABLE_EXCEPTIONS


def test_retryable_exceptions_tuple_includes_marker_and_transport() -> None:
    """Module-top tuple must list both the shared marker and the httpx transport
    error families that the legacy loop used to retry.
    """
    assert TransientHTTPStatus in _RETRYABLE_EXCEPTIONS
    for cls in (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.ReadError,
        httpx.NetworkError,
        httpx.RemoteProtocolError,
    ):
        assert cls in _RETRYABLE_EXCEPTIONS


def test_5xx_response_is_retried_then_wraps_collector_error() -> None:
    """5xx responses raise ``TransientHTTPStatus`` which ``with_retry`` retries
    until exhausted, then ``_request`` re-wraps as ``CollectorError``.
    """
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={"error": "service unavailable"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://api.github.com")
    config = GitHubConfig(max_retries=2)
    collector = GitHubCollector(config=config, client=client)

    # Patch the sleep used by with_retry so the test stays fast.
    with patch("nines.core.retry.time.sleep", lambda _s: None):
        with pytest.raises(CollectorError) as excinfo:
            collector._request("GET", "/repos/x/y")

    assert calls["n"] == 2
    assert excinfo.value.details.get("status") == 503
    assert "after 2 attempts" in str(excinfo.value)


def test_4xx_response_is_not_retried() -> None:
    """4xx (other than 429) is a client error — ``with_retry`` must see it
    only once and propagate the synchronous ``CollectorError``.
    """
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://api.github.com")
    config = GitHubConfig(max_retries=3)
    collector = GitHubCollector(config=config, client=client)

    with pytest.raises(CollectorError) as excinfo:
        collector._request("GET", "/repos/missing/repo")

    assert calls["n"] == 1
    assert excinfo.value.details.get("status") == 404
