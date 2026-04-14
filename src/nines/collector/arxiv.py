"""arXiv paper collector using the Atom XML API.

Implements the ``SourceCollector`` protocol for arXiv papers.
Uses ``httpx.Client`` for HTTP so callers can inject a mock transport.

Covers: FR-203.
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import httpx

from nines.collector.models import Paper
from nines.core.errors import CollectorError

logger = logging.getLogger(__name__)

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"
_DEFAULT_BASE_URL = "https://export.arxiv.org/api/query"
_REQUEST_DELAY = 3.0


@dataclass(frozen=True)
class ArxivConfig:
    """Configuration for the arXiv collector."""

    base_url: str = _DEFAULT_BASE_URL
    delay_seconds: float = _REQUEST_DELAY
    max_results: int = 50
    timeout_seconds: float = 30.0
    max_retries: int = 3
    default_categories: list[str] = field(
        default_factory=lambda: ["cs.AI", "cs.SE", "cs.CL", "cs.LG"]
    )


class ArxivCollector:
    """arXiv Atom XML API collector.

    Parameters
    ----------
    config:
        Collector configuration.
    client:
        Optional ``httpx.Client`` for dependency injection.
    """

    def __init__(
        self,
        config: ArxivConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """Initialize arxiv collector."""
        self._config = config or ArxivConfig()
        self._client = client or httpx.Client(timeout=self._config.timeout_seconds)
        self._last_request_time: float = 0.0

    def _rate_limit_wait(self) -> None:
        """Rate limit wait."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._config.delay_seconds:
            time.sleep(self._config.delay_seconds - elapsed)
        self._last_request_time = time.monotonic()

    def _get(self, params: dict[str, Any]) -> httpx.Response:
        """Send a GET request with rate limiting."""
        self._rate_limit_wait()
        last_exc: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                resp = self._client.get(self._config.base_url, params=params)
                if resp.status_code >= 500:
                    logger.warning(
                        "arXiv server error %d on attempt %d/%d",
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
                    f"arXiv API error: {exc.response.status_code}",
                    details={"status": exc.response.status_code},
                    cause=exc,
                ) from exc
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt == self._config.max_retries:
                    break
                logger.warning("HTTP error on attempt %d: %s", attempt, exc)
                time.sleep(2 ** attempt)
        raise CollectorError(
            f"arXiv request failed after {self._config.max_retries} attempts",
            cause=last_exc,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_papers(
        self,
        query: str,
        max_results: int | None = None,
        categories: list[str] | None = None,
    ) -> list[Paper]:
        """Search arXiv for papers matching *query*.

        If *categories* are provided the query is augmented with
        ``cat:`` qualifiers joined by OR.
        """
        search_query = query
        if categories:
            cat_clause = " OR ".join(f"cat:{c}" for c in categories)
            search_query = f"({query}) AND ({cat_clause})"

        params: dict[str, Any] = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results or self._config.max_results,
        }
        resp = self._get(params)
        return self._parse_feed(resp.text)

    def fetch_paper(self, arxiv_id: str) -> Paper:
        """Fetch a single paper by its arXiv ID."""
        params: dict[str, Any] = {"id_list": arxiv_id}
        resp = self._get(params)
        papers = self._parse_feed(resp.text)
        if not papers:
            raise CollectorError(
                f"Paper not found: {arxiv_id}",
                details={"arxiv_id": arxiv_id},
            )
        return papers[0]

    # ------------------------------------------------------------------
    # SourceCollector protocol (async facade)
    # ------------------------------------------------------------------

    async def search(self, query: str, **kwargs: Any) -> list[Any]:
        """Search for papers matching a query."""
        return self.search_papers(query, **kwargs)

    async def fetch(self, identifier: str) -> Any:
        """Fetch metadata for a single paper."""
        return self.fetch_paper(identifier)

    # ------------------------------------------------------------------
    # XML parsing
    # ------------------------------------------------------------------

    def _parse_feed(self, xml_text: str) -> list[Paper]:
        """Parse feed."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise CollectorError(
                "Failed to parse arXiv XML response",
                cause=exc,
            ) from exc

        papers: list[Paper] = []
        for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
            paper = self._parse_entry(entry)
            if paper is not None:
                papers.append(paper)
        return papers

    @staticmethod
    def _text(element: ET.Element | None) -> str:
        """Text."""
        if element is None:
            return ""
        return (element.text or "").strip()

    def _parse_entry(self, entry: ET.Element) -> Paper | None:
        """Parse entry."""
        raw_id = self._text(entry.find(f"{{{_ATOM_NS}}}id"))
        if not raw_id:
            return None

        arxiv_id = raw_id.rsplit("/abs/", 1)[-1]

        title = self._text(entry.find(f"{{{_ATOM_NS}}}title"))
        abstract = self._text(entry.find(f"{{{_ATOM_NS}}}summary"))
        published = self._text(entry.find(f"{{{_ATOM_NS}}}published"))
        updated = self._text(entry.find(f"{{{_ATOM_NS}}}updated"))

        authors: list[str] = []
        for author_el in entry.findall(f"{{{_ATOM_NS}}}author"):
            name = self._text(author_el.find(f"{{{_ATOM_NS}}}name"))
            if name:
                authors.append(name)

        categories: list[str] = []
        for cat_el in entry.findall(f"{{{_ARXIV_NS}}}primary_category"):
            term = cat_el.get("term", "")
            if term:
                categories.append(term)
        for cat_el in entry.findall(f"{{{_ATOM_NS}}}category"):
            term = cat_el.get("term", "")
            if term and term not in categories:
                categories.append(term)

        pdf_url = ""
        for link in entry.findall(f"{{{_ATOM_NS}}}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
                break

        return Paper(
            id=arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            categories=categories,
            published=published,
            updated=updated,
            pdf_url=pdf_url,
        )
