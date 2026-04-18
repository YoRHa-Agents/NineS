"""C05 polish — verify ``ArxivCollector`` delegates retries to ``with_retry``.

Mirror of :mod:`tests.collector.test_github`: pins the post-refactor
delegation contract for arXiv.  Existing happy-path coverage lives in
``tests/test_collector.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.collector import arxiv as arxiv_module  # noqa: E402
from nines.collector.arxiv import (  # noqa: E402
    _RETRYABLE_EXCEPTIONS,
    ArxivCollector,
    ArxivConfig,
)
from nines.core.errors import CollectorError  # noqa: E402
from nines.core.retry import RetryPolicy, TransientHTTPStatus  # noqa: E402

_EMPTY_FEED = (
    '<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
)


def _ok_handler(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=_EMPTY_FEED)


def test_get_invokes_with_retry_with_configured_policy() -> None:
    """``_get`` must call ``with_retry`` exactly once per request, with
    a ``RetryPolicy(attempts=cfg.max_retries, retry_on=_RETRYABLE_EXCEPTIONS)``.
    """
    transport = httpx.MockTransport(_ok_handler)
    client = httpx.Client(transport=transport)
    config = ArxivConfig(
        base_url="http://test.local/api/query",
        delay_seconds=0.0,
        max_retries=5,
    )
    collector = ArxivCollector(config=config, client=client)

    captured: dict[str, Any] = {}

    def fake_with_retry(fn: Any, policy: RetryPolicy, **_kw: Any) -> httpx.Response:
        captured["policy"] = policy
        captured["fn"] = fn
        return fn()

    with patch.object(arxiv_module, "with_retry", side_effect=fake_with_retry) as wr:
        resp = collector._get({"search_query": "all"})

    assert resp.status_code == 200
    assert wr.call_count == 1
    policy = captured["policy"]
    assert isinstance(policy, RetryPolicy)
    assert policy.attempts == 5
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
    until exhausted, then ``_get`` re-wraps as ``CollectorError``.
    """
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(502, text="bad gateway")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    config = ArxivConfig(
        base_url="http://test.local/api/query",
        delay_seconds=0.0,
        max_retries=2,
    )
    collector = ArxivCollector(config=config, client=client)

    with (
        patch("nines.core.retry.time.sleep", lambda _s: None),
        pytest.raises(CollectorError) as excinfo,
    ):
        collector._get({"search_query": "x"})

    assert calls["n"] == 2
    assert excinfo.value.details.get("status") == 502
    assert "after 2 attempts" in str(excinfo.value)


def test_4xx_response_is_not_retried() -> None:
    """4xx is a client error — ``_get`` must propagate ``CollectorError``
    without retrying.
    """
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, text="bad request")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    config = ArxivConfig(
        base_url="http://test.local/api/query",
        delay_seconds=0.0,
        max_retries=3,
    )
    collector = ArxivCollector(config=config, client=client)

    with pytest.raises(CollectorError) as excinfo:
        collector._get({"search_query": "x"})

    assert calls["n"] == 1
    assert excinfo.value.details.get("status") == 400
