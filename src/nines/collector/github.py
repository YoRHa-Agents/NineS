"""GitHub data collector using the REST API v3.

Implements the ``SourceCollector`` protocol for GitHub repositories.
Uses ``httpx.Client`` for HTTP so callers can inject a mock transport
for testing.

Covers: FR-201, FR-202, FR-206.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from nines.collector.models import Repository
from nines.core.errors import CollectorError

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.github.com"
_RATE_LIMIT_SLEEP = 1.0


@dataclass(frozen=True)
class GitHubConfig:
    """Configuration for the GitHub collector."""

    token: str = ""
    base_url: str = _DEFAULT_BASE_URL
    timeout_seconds: float = 30.0
    max_retries: int = 3
    per_page: int = 30


class GitHubCollector:
    """GitHub REST API collector.

    All HTTP requests are routed through the injected ``httpx.Client``,
    making the collector fully mock-friendly for tests.

    Parameters
    ----------
    config:
        Collector configuration (token, base URL, etc.).
    client:
        Optional ``httpx.Client`` instance.  When *None* a default
        client is created with the configured timeout and auth headers.
    """

    def __init__(
        self,
        config: GitHubConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """Initialize git hub collector."""
        self._config = config or GitHubConfig()
        self._client = client or self._build_client()
        self._last_request_time: float = 0.0

    def _build_client(self) -> httpx.Client:
        """Build client."""
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._config.token:
            headers["Authorization"] = f"Bearer {self._config.token}"
        return httpx.Client(
            base_url=self._config.base_url,
            headers=headers,
            timeout=self._config.timeout_seconds,
        )

    def _rate_limit_wait(self) -> None:
        """Rate limit wait."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < _RATE_LIMIT_SLEEP:
            time.sleep(_RATE_LIMIT_SLEEP - elapsed)
        self._last_request_time = time.monotonic()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Request."""
        self._rate_limit_wait()
        last_exc: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                resp = self._client.request(method, url, **kwargs)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("retry-after", 2 ** attempt))
                    logger.warning("Rate limited (429), sleeping %.1fs", retry_after)
                    time.sleep(retry_after)
                    continue
                if resp.status_code >= 500:
                    logger.warning(
                        "Server error %d on attempt %d/%d",
                        resp.status_code,
                        attempt,
                        self._config.max_retries,
                    )
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                raise CollectorError(
                    f"GitHub API error: {exc.response.status_code}",
                    details={"url": url, "status": exc.response.status_code},
                    cause=exc,
                ) from exc
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt == self._config.max_retries:
                    break
                logger.warning("HTTP error on attempt %d: %s", attempt, exc)
                time.sleep(2 ** attempt)
        raise CollectorError(
            f"GitHub request failed after {self._config.max_retries} attempts",
            details={"url": url},
            cause=last_exc,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_repos(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc",
        per_page: int | None = None,
    ) -> list[Repository]:
        """Search GitHub repositories.

        Returns a list of ``Repository`` objects parsed from the
        ``/search/repositories`` endpoint.
        """
        params: dict[str, Any] = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page or self._config.per_page,
        }
        resp = self._request("GET", "/search/repositories", params=params)
        data = resp.json()
        items = data.get("items", [])
        return [self._parse_repo(item) for item in items]

    def fetch_repo(self, owner: str, name: str) -> Repository:
        """Fetch a single repository by owner/name."""
        resp = self._request("GET", f"/repos/{owner}/{name}")
        return self._parse_repo(resp.json())

    def get_commits(
        self, owner: str, name: str, since: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch recent commits for a repository.

        Parameters
        ----------
        since:
            ISO-8601 timestamp.  Only commits after this date are returned.
        """
        params: dict[str, Any] = {"per_page": 30}
        if since:
            params["since"] = since
        resp = self._request("GET", f"/repos/{owner}/{name}/commits", params=params)
        return resp.json()

    def get_releases(self, owner: str, name: str) -> list[dict[str, Any]]:
        """Fetch releases for a repository."""
        resp = self._request(
            "GET", f"/repos/{owner}/{name}/releases", params={"per_page": 10}
        )
        return resp.json()

    # ------------------------------------------------------------------
    # SourceCollector protocol (async facade)
    # ------------------------------------------------------------------

    async def search(self, query: str, **kwargs: Any) -> list[Any]:
        """Satisfy ``SourceCollector.search``."""
        return self.search_repos(query, **kwargs)

    async def fetch(self, identifier: str) -> Any:
        """Satisfy ``SourceCollector.fetch``.

        *identifier* is expected as ``"owner/repo"``.
        """
        parts = identifier.split("/", 1)
        if len(parts) != 2:
            raise CollectorError(
                f"Invalid GitHub identifier '{identifier}', expected 'owner/repo'",
                details={"identifier": identifier},
            )
        return self.fetch_repo(parts[0], parts[1])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_repo(data: dict[str, Any]) -> Repository:
        """Parse repo."""
        return Repository(
            id=data.get("id"),
            name=data.get("name", ""),
            owner=(data.get("owner") or {}).get("login", ""),
            url=data.get("html_url", ""),
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            description=data.get("description") or "",
            language=data.get("language") or "",
            topics=data.get("topics", []),
            last_updated=data.get("updated_at", ""),
        )
