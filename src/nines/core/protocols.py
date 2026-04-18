"""Protocol definitions for all NineS inter-module boundaries.

Every cross-module interface is defined here as a ``typing.Protocol``.
Implementations satisfy these contracts via structural subtyping — no
inheritance required.  All protocols are ``@runtime_checkable`` so that
``isinstance`` guards work at construction time (e.g. in PipelineBuilder).

Covers: CON-09, FR-204, NFR-13–16.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Forward-reference string literals keep this module free of circular imports.
# Concrete types live in ``nines.core.models``.
# ---------------------------------------------------------------------------


@runtime_checkable
class TaskLoader(Protocol):
    """Loads evaluation tasks from files, directories, or glob patterns.

    Implements FR-102.
    """

    def load(self, path: str) -> list[Any]:
        """Load evaluation tasks from *path*.

        Parameters
        ----------
        path:
            Filesystem path (file, directory, or glob) pointing to task
            definitions.

        Returns
        -------
        list[EvalTask]
            Parsed task objects ready for execution.
        """
        ...


@runtime_checkable
class Executor(Protocol):
    """Executes a single evaluation task inside an isolated environment.

    Subsumes EvoBench's Executor + DataCollector stages.
    Implements FR-114.
    """

    async def execute(self, task: Any) -> Any:
        """Execute *task* and return an ``ExecutionResult``.

        Parameters
        ----------
        task:
            An ``EvalTask`` instance describing what to run.

        Returns
        -------
        ExecutionResult
            Captured output, timing data, and success flag.
        """
        ...


@runtime_checkable
class Scorer(Protocol):
    """Scores an execution result against expected output.

    Base protocol for the scorer plugin system (ExactScorer,
    FuzzyScorer, RubricScorer, CompositeScorer, and custom plugins).
    Implements FR-103 through FR-106.
    """

    def score(self, result: Any, expected: Any) -> Any:
        """Produce a ``Score`` for a single task execution.

        Parameters
        ----------
        result:
            An ``ExecutionResult`` from the executor.
        expected:
            The ground-truth / expected output for comparison.

        Returns
        -------
        Score
            Normalized score with optional breakdown.
        """
        ...


@runtime_checkable
class SourceCollector(Protocol):
    """Discovers and fetches external information from a single source type.

    Each source (GitHub, arXiv, …) provides its own ``SourceCollector``
    implementation registered via ``CollectorRegistry``.
    Implements FR-201–FR-204.
    """

    async def search(self, query: str, **kwargs: Any) -> list[Any]:
        """Search the source for items matching *query*.

        Parameters
        ----------
        query:
            Free-text or structured search string.
        **kwargs:
            Source-specific options (``limit``, ``since``, etc.).

        Returns
        -------
        list[CollectionResult]
            Discovered items with metadata.
        """
        ...

    async def fetch(self, identifier: str) -> Any:
        """Fetch a single item by its unique *identifier*.

        Parameters
        ----------
        identifier:
            Source-specific unique key (URL, DOI, repo slug, …).

        Returns
        -------
        CollectionResult
            The fetched item with full metadata.
        """
        ...


@runtime_checkable
class Analyzer(Protocol):
    """Performs static analysis on a code target.

    Covers AST extraction, structural analysis, pattern detection,
    and knowledge decomposition.
    Implements FR-301–FR-311.
    """

    def analyze(self, target: str) -> Any:
        """Analyze the code at *target* path.

        Parameters
        ----------
        target:
            Filesystem path to a file or directory to analyze.

        Returns
        -------
        AnalysisResult
            Findings, metrics, and extracted knowledge.
        """
        ...


@runtime_checkable
class Reporter(Protocol):
    """Generates output reports from evaluation or analysis results.

    Supports multiple output formats (JSON, Markdown, etc.).
    Implements FR-112 (JSON) and FR-113 (Markdown).
    """

    def report(self, results: list[Any], output_path: str) -> None:
        """Write a formatted report to *output_path*.

        Parameters
        ----------
        results:
            Aggregated result objects to include in the report.
        output_path:
            Destination file path for the generated report.
        """
        ...


# ---------------------------------------------------------------------------
# C01 Phase 1 — project-aware DimensionEvaluator (Wave 2)
# ---------------------------------------------------------------------------

from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from nines.iteration.context import EvaluationContext


@runtime_checkable
class DimensionEvaluator(Protocol):
    """Project-aware self-eval dimension evaluator (C01 Phase 1).

    Implementations may declare a ``requires_context`` *class attribute*
    set to ``True`` to assert that a non-``None``
    :class:`~nines.iteration.context.EvaluationContext` must be supplied
    at evaluation time. Legacy evaluators that don't accept a ``ctx``
    keyword argument keep working through
    :class:`~nines.iteration.self_eval.LegacyEvaluatorAdapter`, which
    the runner attaches automatically at registration time.

    Notes
    -----
    The Protocol is :func:`typing.runtime_checkable` so the runner can
    quickly verify that registered evaluators expose an ``evaluate``
    method (signature is verified separately via
    :func:`inspect.signature`).  We deliberately do **not** declare
    ``requires_context`` on the Protocol itself, because
    runtime_checkable Protocols enforce member existence and forcing
    legacy evaluators to add the marker would be a breaking change;
    instead the runner uses ``getattr(ev, "requires_context", False)``.
    """

    def evaluate(self, *, ctx: EvaluationContext | None = None) -> Any:
        """Run evaluation for this dimension.

        Parameters
        ----------
        ctx:
            Optional :class:`EvaluationContext`. Modern evaluators that
            need project-aware paths (D11/D14/D15 today) require it;
            legacy ones ignore it via :class:`LegacyEvaluatorAdapter`.

        Returns
        -------
        DimensionScore
            The evaluator's score plus any per-dim metadata.
        """
        ...


__all__ = [
    "Analyzer",
    "DimensionEvaluator",
    "Executor",
    "Reporter",
    "Scorer",
    "SourceCollector",
    "TaskLoader",
]
