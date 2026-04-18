"""Self-evaluation runner and dimension evaluator protocol.

``SelfEvalRunner`` orchestrates evaluation across multiple dimensions
(code coverage, test count, module count, etc.) and produces a
``SelfEvalReport`` summarizing scores for each dimension.

Covers: FR-601, FR-602.
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from nines.core.budget import (
    EvaluatorBudgetExceeded,
    TimeBudget,
    evaluator_budget,
)


def _budgeted_subprocess_timeout(
    default_seconds: float,
    budget: TimeBudget | None,
    *,
    margin: float = 0.9,
) -> float:
    """Return the subprocess ``timeout=`` value to use under *budget*.

    Computes ``min(default_seconds, budget.hard_seconds * margin)`` so
    the subprocess always returns control to its caller before the
    daemon-thread budget kills the worker.  The 0.9 margin gives the
    evaluator ~10% of the wall budget to clean up after a
    ``subprocess.TimeoutExpired``.

    When ``budget`` is ``None`` (back-compat path used by direct
    instantiation in tests), returns ``default_seconds`` unchanged.

    Release follow-up N2.
    """
    if budget is None:
        return float(default_seconds)
    capped = budget.hard_seconds * margin
    return float(min(default_seconds, capped))

logger = logging.getLogger(__name__)


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension.

    Attributes
    ----------
    name:
        Dimension identifier (e.g. ``"code_coverage"``).
    value:
        Numeric score value.
    max_value:
        Upper bound of the score range.
    metadata:
        Additional context or breakdown.
    """

    name: str
    value: float
    max_value: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized(self) -> float:
        """Return the score normalized to [0, 1]."""
        if self.max_value == 0:
            return 0.0
        return self.value / self.max_value

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "max_value": self.max_value,
            "normalized": self.normalized,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DimensionScore:
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            max_value=data.get("max_value", 1.0),
            metadata=data.get("metadata", {}),
        )


@runtime_checkable
class DimensionEvaluator(Protocol):
    """Protocol for evaluating a single dimension."""

    def evaluate(self) -> DimensionScore:
        """Run evaluation and return a score for this dimension."""
        ...


@dataclass
class SelfEvalReport:
    """Aggregate report from running all dimension evaluators.

    Attributes
    ----------
    scores:
        Per-dimension scores.
    overall:
        Weighted average of normalized dimension scores.
    version:
        Optional version tag for baseline comparison.
    timestamp:
        ISO-8601 timestamp of when the report was generated.
    duration:
        Total evaluation time in seconds.
    timeouts:
        Names of dimensions whose evaluators exceeded the configured
        hard wall-clock budget (C04).  Empty when all evaluators
        completed within budget.
    """

    scores: list[DimensionScore] = field(default_factory=list)
    overall: float = 0.0
    version: str = ""
    timestamp: str = ""
    duration: float = 0.0
    timeouts: list[str] = field(default_factory=list)

    def get_score(self, dimension: str) -> DimensionScore | None:
        """Return score."""
        for s in self.scores:
            if s.name == dimension:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scores": [s.to_dict() for s in self.scores],
            "overall": self.overall,
            "version": self.version,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "timeouts": list(self.timeouts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelfEvalReport:
        """Deserialize from dictionary."""
        return cls(
            scores=[DimensionScore.from_dict(s) for s in data.get("scores", [])],
            overall=data.get("overall", 0.0),
            version=data.get("version", ""),
            timestamp=data.get("timestamp", ""),
            duration=data.get("duration", 0.0),
            timeouts=list(data.get("timeouts", [])),
        )


class SelfEvalRunner:
    """Orchestrates evaluation across multiple registered dimensions.

    Usage::

        runner = SelfEvalRunner()
        runner.register_dimension("test_count", TestCountEvaluator())
        runner.register_dimension("module_count", ModuleCountEvaluator())
        report = runner.run_all()
    """

    def __init__(
        self,
        default_budget: TimeBudget | None = None,
    ) -> None:
        """Initialize self eval runner.

        Parameters
        ----------
        default_budget:
            Per-evaluator wall-clock budget applied to every dimension
            unless overridden by ``register_dimension(..., budget=...)``.
            Defaults to ``TimeBudget(soft_seconds=20, hard_seconds=60)``
            per the C04 design.
        """
        self._evaluators: dict[str, DimensionEvaluator] = {}
        self._budgets: dict[str, TimeBudget] = {}
        self._default_budget = default_budget or TimeBudget(
            soft_seconds=20.0, hard_seconds=60.0,
        )

    def register_dimension(
        self,
        name: str,
        evaluator: DimensionEvaluator,
        *,
        budget: TimeBudget | None = None,
    ) -> None:
        """Register an evaluator for a named dimension.

        Parameters
        ----------
        name:
            Unique dimension identifier.
        evaluator:
            Object implementing the ``DimensionEvaluator`` protocol.
        budget:
            Optional per-dimension wall-clock budget overriding the
            runner-wide default.
        """
        self._evaluators[name] = evaluator
        if budget is not None:
            self._budgets[name] = budget
        logger.debug("Registered evaluator for dimension '%s'", name)

    @staticmethod
    def _make_invocation(
        evaluator: DimensionEvaluator,
        budget: TimeBudget,
    ) -> "Callable[[], DimensionScore]":
        """Bind ``budget`` to ``evaluator.evaluate`` if the method accepts it.

        Returns a zero-arg callable that invokes the evaluator with or
        without the ``budget`` kwarg, depending on its signature.
        Backward-compat: third-party evaluators that don't accept
        ``budget`` keep working (Approach A from the C04 follow-up).
        """
        try:
            sig = inspect.signature(evaluator.evaluate)
            accepts_budget = "budget" in sig.parameters
        except (TypeError, ValueError):
            # ``signature`` can fail on C-level callables — fall back to
            # the no-budget call shape.  We never silently swallow:
            # downstream evaluator errors still surface through the
            # ``except Exception`` branch in run_all.
            logger.debug(
                "inspect.signature failed for evaluator %r; "
                "calling without budget",
                evaluator,
            )
            accepts_budget = False

        if accepts_budget:
            return lambda: evaluator.evaluate(budget=budget)
        return evaluator.evaluate

    def run_all(self, version: str = "") -> SelfEvalReport:
        """Run all registered evaluators and produce a report.

        Parameters
        ----------
        version:
            Optional version tag for the report.

        Returns
        -------
        SelfEvalReport
            Aggregate scores from all dimensions.
        """
        from datetime import datetime

        start = time.monotonic()
        scores: list[DimensionScore] = []
        timeouts: list[str] = []

        for name, evaluator in self._evaluators.items():
            logger.info("Evaluating dimension '%s'", name)
            budget = self._budgets.get(name, self._default_budget)
            # N2: thread the budget into evaluators that accept it so
            # internal subprocess.run calls can derive their own
            # ``timeout=`` from the wall-clock budget.  Detection is
            # signature-based to keep third-party evaluators that don't
            # know about ``budget`` working unchanged.
            invoke = self._make_invocation(evaluator, budget)
            try:
                with evaluator_budget(name, budget) as run:
                    score = run(invoke)
                scores.append(score)
                logger.info(
                    "Dimension '%s': %.3f / %.3f (%.1f%%)",
                    name, score.value, score.max_value, score.normalized * 100,
                )
            except EvaluatorBudgetExceeded as exc:
                # C04: append a placeholder score with status='timeout'
                # so the report records exactly which dim breached.
                logger.warning(
                    "Evaluator '%s' timed out after %.1fs: %s",
                    name, exc.elapsed_s, exc,
                )
                scores.append(DimensionScore(
                    name=name,
                    value=0.0,
                    max_value=1.0,
                    metadata={
                        "status": "timeout",
                        "hard_seconds": exc.hard_seconds,
                        "elapsed_s": exc.elapsed_s,
                    },
                ))
                timeouts.append(name)
            except Exception as exc:
                logger.error("Evaluator for '%s' failed: %s", name, exc, exc_info=True)
                scores.append(DimensionScore(name=name, value=0.0, max_value=1.0))

        overall = 0.0
        if scores:
            overall = sum(s.normalized for s in scores) / len(scores)

        duration = time.monotonic() - start
        return SelfEvalReport(
            scores=scores,
            overall=overall,
            version=version,
            timestamp=datetime.now(UTC).isoformat(),
            duration=duration,
            timeouts=timeouts,
        )


# ---------------------------------------------------------------------------
# Built-in evaluators for simple dimensions
# ---------------------------------------------------------------------------


class CodeCoverageEvaluator:
    """Evaluator that reports a configured code coverage percentage."""

    def __init__(self, coverage_pct: float = 0.0) -> None:
        """Initialize code coverage evaluator."""
        self._coverage = coverage_pct

    def evaluate(self) -> DimensionScore:
        """Evaluate and return a code coverage score."""
        return DimensionScore(
            name="code_coverage",
            value=self._coverage,
            max_value=100.0,
            metadata={"unit": "percent"},
        )


class UnitTestCountEvaluator:
    """Evaluator that reports a count of tests."""

    def __init__(self, count: int = 0) -> None:
        """Initialize unit test count evaluator."""
        self._count = count

    def evaluate(self) -> DimensionScore:
        """Evaluate and return a test count score."""
        return DimensionScore(
            name="test_count",
            value=float(self._count),
            max_value=float(max(self._count, 1)),
            metadata={"unit": "tests"},
        )


TestCountEvaluator = UnitTestCountEvaluator


class ModuleCountEvaluator:
    """Evaluator that reports a count of modules."""

    def __init__(self, count: int = 0) -> None:
        """Initialize module count evaluator."""
        self._count = count

    def evaluate(self) -> DimensionScore:
        """Evaluate and return a module count score."""
        return DimensionScore(
            name="module_count",
            value=float(self._count),
            max_value=float(max(self._count, 1)),
            metadata={"unit": "modules"},
        )


# ---------------------------------------------------------------------------
# Live evaluators — auto-discover metrics from the project
# ---------------------------------------------------------------------------


class LiveCodeCoverageEvaluator:
    """Evaluator that runs pytest --cov and parses real coverage.

    Supports three coverage sources (checked in order):
    1. Pre-existing coverage file (coverage.xml or coverage.json)
    2. pytest ``--cov`` subprocess execution
    """

    def __init__(
        self,
        project_root: str | Path = ".",
        cov_package: str = "nines",
        coverage_file: str | Path | None = None,
    ) -> None:
        """Initialize live code coverage evaluator.

        Parameters
        ----------
        project_root:
            Working directory for running pytest.
        cov_package:
            Package name passed to ``--cov=<package>``.
        coverage_file:
            Optional path to a pre-existing coverage.xml (Cobertura) or
            coverage.json file.  When provided and the file exists, the
            evaluator parses coverage from it instead of running pytest.
        """
        self._project_root = Path(project_root)
        self._cov_package = cov_package
        self._coverage_file = Path(coverage_file) if coverage_file is not None else None

    def evaluate(self, *, budget: TimeBudget | None = None) -> DimensionScore:
        """Evaluate and return live code coverage.

        Parameters
        ----------
        budget:
            Optional :class:`TimeBudget` from the runner.  When set, the
            inner ``pytest --cov`` subprocess uses
            ``min(default_timeout, budget.hard_seconds * 0.9)`` so the
            child returns control before the daemon-thread budget fires
            (release follow-up N2).
        """
        coverage_pct = self._try_coverage_file()
        source = "file"

        if coverage_pct is None:
            source = "pytest"
            coverage_pct = self._run_pytest_cov(budget=budget)

        return DimensionScore(
            name="code_coverage",
            value=coverage_pct,
            max_value=100.0,
            metadata={"unit": "percent", "source": source},
        )

    # -- private helpers -----------------------------------------------------

    def _try_coverage_file(self) -> float | None:
        """Attempt to read coverage from a pre-existing file."""
        if self._coverage_file is None or not self._coverage_file.exists():
            return None

        suffix = self._coverage_file.suffix.lower()
        try:
            if suffix == ".xml":
                return self._parse_coverage_xml(self._coverage_file)
            if suffix == ".json":
                return self._parse_coverage_json(self._coverage_file)
            logger.warning(
                "Unsupported coverage file format '%s'; falling back to pytest",
                suffix,
            )
        except Exception as exc:
            logger.error(
                "Failed to parse coverage file %s: %s", self._coverage_file, exc,
            )
        return None

    def _run_pytest_cov(self, *, budget: TimeBudget | None = None) -> float:
        """Run pytest --cov and return the coverage percentage.

        N2: ``timeout`` defaults to 300s but is shrunk to
        ``budget.hard_seconds * 0.9`` whenever the runner passes a
        TimeBudget through, so the child subprocess returns before the
        daemon-thread guard kills it.
        """
        timeout_s = _budgeted_subprocess_timeout(300.0, budget)
        try:
            result = subprocess.run(
                [
                    "python", "-m", "pytest",
                    f"--cov={self._cov_package}",
                    "--cov-report=term-missing", "-q",
                ],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(self._project_root),
            )
            return self._parse_coverage(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error(
                "pytest --cov timed out after %.1fs (budget-derived)",
                timeout_s,
            )
            return 0.0
        except Exception as exc:
            logger.error("Failed to run pytest --cov: %s", exc)
            return 0.0

    @staticmethod
    def _parse_coverage(stdout: str) -> float:
        """Extract total coverage percentage from pytest-cov TOTAL line."""
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("TOTAL"):
                parts = stripped.split()
                for part in reversed(parts):
                    cleaned = part.rstrip("%")
                    try:
                        return float(cleaned)
                    except ValueError:
                        continue
        logger.warning("Could not parse coverage from pytest output")
        return 0.0

    @staticmethod
    def _parse_coverage_xml(path: Path) -> float:
        """Parse Cobertura coverage.xml and return coverage percentage."""
        tree = ET.parse(path)  # noqa: S314
        root = tree.getroot()
        line_rate = root.get("line-rate")
        if line_rate is None:
            msg = "coverage.xml missing 'line-rate' attribute on root element"
            raise ValueError(msg)
        return float(line_rate) * 100.0

    @staticmethod
    def _parse_coverage_json(path: Path) -> float:
        """Parse coverage.json and return coverage percentage."""
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            return float(data["totals"]["percent_covered"])
        except (KeyError, TypeError) as exc:
            msg = "coverage.json missing 'totals.percent_covered'"
            raise ValueError(msg) from exc


class LiveTestCountEvaluator:
    """Evaluator that counts test functions.

    Prefers ``pytest --collect-only -q`` for an accurate count (handles
    parameterized tests, fixture-generated tests, class-based methods,
    etc.).  Falls back to an AST walk when pytest collection is
    unavailable or fails.
    """

    def __init__(
        self,
        test_dir: str | Path = "tests",
        project_root: str | Path = ".",
    ) -> None:
        """Initialize live test count evaluator.

        Parameters
        ----------
        test_dir:
            Directory to scan when using the AST-walk fallback.
        project_root:
            Working directory for running ``pytest --collect-only``.
        """
        self._test_dir = Path(test_dir)
        self._project_root = Path(project_root)

    def evaluate(self, *, budget: TimeBudget | None = None) -> DimensionScore:
        """Evaluate and return live test count.

        Parameters
        ----------
        budget:
            Optional runner-supplied :class:`TimeBudget`.  When set, the
            inner ``pytest --collect-only`` subprocess uses
            ``min(120s, budget.hard_seconds * 0.9)`` (release follow-up
            N2).
        """
        count, method = self._try_pytest_collect(budget=budget)

        if count is None:
            count, method = self._ast_walk(), "ast-walk"

        return DimensionScore(
            name="test_count",
            value=float(count),
            max_value=float(max(count, 1)),
            metadata={"unit": "tests", "method": method},
        )

    # -- private helpers -----------------------------------------------------

    def _try_pytest_collect(
        self,
        *,
        budget: TimeBudget | None = None,
    ) -> tuple[int | None, str]:
        """Run ``pytest --collect-only -q`` and count collected items.

        N2: caps the subprocess timeout to
        ``budget.hard_seconds * 0.9`` when the runner forwards a
        TimeBudget; defaults to 120s otherwise.
        """
        timeout_s = _budgeted_subprocess_timeout(120.0, budget)
        try:
            result = subprocess.run(
                [
                    "python", "-m", "pytest", "--collect-only", "-q",
                    str(self._test_dir),
                ],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(self._project_root),
            )
            count = self._parse_collect_output(result.stdout)
            if count is not None:
                return count, "pytest-collect"
            logger.warning(
                "pytest --collect-only did not produce a parseable summary; "
                "falling back to AST walk"
            )
        except subprocess.TimeoutExpired:
            logger.error(
                "pytest --collect-only timed out after %.1fs (budget-derived)",
                timeout_s,
            )
        except Exception as exc:
            logger.error("pytest --collect-only failed: %s", exc)
        return None, ""

    @staticmethod
    def _parse_collect_output(stdout: str) -> int | None:
        """Parse the ``N tests collected`` summary line from pytest -q."""
        for line in reversed(stdout.splitlines()):
            match = re.search(r"(\d+)\s+tests?\s+collected", line)
            if match:
                return int(match.group(1))
        return None

    def _ast_walk(self) -> int:
        """Count test functions via AST analysis (fallback)."""
        count = 0
        files_scanned = 0
        try:
            for py_file in self._test_dir.rglob("test_*.py"):
                files_scanned += 1
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError) as exc:
                    logger.warning("Skipping %s: %s", py_file, exc)
                    continue
                for node in ast.walk(tree):
                    if (
                        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name.startswith("test_")
                    ):
                        count += 1
        except Exception as exc:
            logger.error("Failed to scan test directory %s: %s", self._test_dir, exc)
        logger.debug("AST walk: scanned %d files, found %d tests", files_scanned, count)
        return count


class LiveModuleCountEvaluator:
    """Evaluator that counts Python modules in src/nines/."""

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize live module count evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(self) -> DimensionScore:
        """Evaluate and return live module count."""
        count = 0
        try:
            for py_file in self._src_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                if "__pycache__" in py_file.parts:
                    continue
                count += 1
        except Exception as exc:
            logger.error("Failed to scan source directory %s: %s", self._src_dir, exc)

        return DimensionScore(
            name="module_count",
            value=float(count),
            max_value=float(max(count, 1)),
            metadata={"unit": "modules"},
        )


class DocstringCoverageEvaluator:
    """Evaluator that measures docstring coverage of public functions/classes."""

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize docstring coverage evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(self) -> DimensionScore:
        """Evaluate and return docstring coverage."""
        total = 0
        documented = 0
        try:
            for py_file in self._src_dir.rglob("*.py"):
                if "__pycache__" in py_file.parts:
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError) as exc:
                    logger.warning("Skipping %s: %s", py_file, exc)
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name.startswith("_"):
                            continue
                        total += 1
                        if ast.get_docstring(node):
                            documented += 1
        except Exception as exc:
            logger.error("Failed to scan source directory %s: %s", self._src_dir, exc)

        pct = (documented / total * 100.0) if total > 0 else 0.0
        return DimensionScore(
            name="docstring_coverage",
            value=pct,
            max_value=100.0,
            metadata={"unit": "percent", "total": total, "documented": documented},
        )


class LintCleanlinessEvaluator:
    """Evaluator that measures lint cleanliness via ruff."""

    def __init__(self, src_dir: str | Path = "src/nines") -> None:
        """Initialize lint cleanliness evaluator."""
        self._src_dir = Path(src_dir)

    def evaluate(self, *, budget: TimeBudget | None = None) -> DimensionScore:
        """Evaluate and return lint cleanliness score.

        Parameters
        ----------
        budget:
            Optional runner-supplied :class:`TimeBudget`.  When set, the
            inner ``ruff check`` subprocess uses
            ``min(300s, budget.hard_seconds * 0.9)`` (release follow-up
            N2).
        """
        timeout_s = _budgeted_subprocess_timeout(300.0, budget)
        violation_count = 0
        try:
            result = subprocess.run(
                ["python", "-m", "ruff", "check", str(self._src_dir), "--output-format=json", "-q"],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            if result.stdout.strip():
                violations = json.loads(result.stdout)
                violation_count = len(violations)
        except subprocess.TimeoutExpired:
            logger.error(
                "ruff check timed out after %.1fs (budget-derived)",
                timeout_s,
            )
        except Exception as exc:
            logger.error("Failed to run ruff check: %s", exc)

        raw_score = max(0.0, 100.0 - violation_count * 2.0)
        return DimensionScore(
            name="lint_cleanliness",
            value=raw_score,
            max_value=100.0,
            metadata={"unit": "score", "violation_count": violation_count},
        )
