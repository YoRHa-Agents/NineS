"""Simple in-memory collection scheduler.

``CollectionScheduler`` manages scheduled collection jobs with configurable
intervals. Jobs are tracked in memory and can be queried for pending status.

Covers: FR-212.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from nines.core.errors import CollectorError

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """A scheduled collection job."""

    source: str
    interval_seconds: float
    last_run: float = 0.0
    run_count: int = 0
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def next_run(self) -> float:
        """Return the next run."""
        if self.last_run == 0.0:
            return 0.0
        return self.last_run + self.interval_seconds

    @property
    def is_due(self) -> bool:
        """Return the is due."""
        if self.last_run == 0.0:
            return True
        return time.monotonic() >= self.next_run

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source": self.source,
            "interval_seconds": self.interval_seconds,
            "last_run": self.last_run,
            "run_count": self.run_count,
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
        }


CollectorFn = Callable[[str], Any]


class CollectionScheduler:
    """In-memory scheduler for periodic collection jobs."""

    def __init__(self) -> None:
        """Initialize collection scheduler."""
        self._jobs: dict[str, ScheduledJob] = {}
        self._collectors: dict[str, CollectorFn] = {}

    def schedule(
        self,
        source: str,
        interval: float,
        collector: CollectorFn | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ScheduledJob:
        """Schedule a collection job for *source* at the given interval (seconds)."""
        job = ScheduledJob(
            source=source,
            interval_seconds=interval,
            metadata=metadata or {},
        )
        self._jobs[source] = job
        if collector is not None:
            self._collectors[source] = collector
        return job

    def unschedule(self, source: str) -> bool:
        """Remove a scheduled job by name."""
        if source in self._jobs:
            del self._jobs[source]
            self._collectors.pop(source, None)
            return True
        return False

    def get_job(self, source: str) -> ScheduledJob | None:
        """Return job."""
        return self._jobs.get(source)

    def list_jobs(self) -> list[ScheduledJob]:
        """List jobs."""
        return list(self._jobs.values())

    def get_pending(self) -> list[ScheduledJob]:
        """Return all jobs that are due for execution."""
        return [j for j in self._jobs.values() if j.enabled and j.is_due]

    def run_once(self, source: str) -> Any:
        """Execute a single collection run for *source*, updating job state."""
        job = self._jobs.get(source)
        if job is None:
            raise CollectorError(
                f"No scheduled job for source: {source}",
                details={"source": source},
            )

        collector = self._collectors.get(source)
        if collector is None:
            raise CollectorError(
                f"No collector registered for source: {source}",
                details={"source": source},
            )

        result = collector(source)
        job.last_run = time.monotonic()
        job.run_count += 1
        return result

    def run_pending(self) -> dict[str, Any]:
        """Execute all pending jobs, returning a map of source → result."""
        results: dict[str, Any] = {}
        for job in self.get_pending():
            try:
                results[job.source] = self.run_once(job.source)
            except Exception as exc:
                logger.error("Failed to run collector for %s: %s", job.source, exc)
                results[job.source] = {"error": str(exc)}
        return results
