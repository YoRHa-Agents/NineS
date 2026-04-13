"""Self-evaluation runner and dimension evaluator protocol.

``SelfEvalRunner`` orchestrates evaluation across multiple dimensions
(code coverage, test count, module count, etc.) and produces a
``SelfEvalReport`` summarizing scores for each dimension.

Covers: FR-601, FR-602.
"""

from __future__ import annotations

import ast
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

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
    """

    scores: list[DimensionScore] = field(default_factory=list)
    overall: float = 0.0
    version: str = ""
    timestamp: str = ""
    duration: float = 0.0

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
        )


class SelfEvalRunner:
    """Orchestrates evaluation across multiple registered dimensions.

    Usage::

        runner = SelfEvalRunner()
        runner.register_dimension("test_count", TestCountEvaluator())
        runner.register_dimension("module_count", ModuleCountEvaluator())
        report = runner.run_all()
    """

    def __init__(self) -> None:
        """Initialize self eval runner."""
        self._evaluators: dict[str, DimensionEvaluator] = {}

    def register_dimension(self, name: str, evaluator: DimensionEvaluator) -> None:
        """Register an evaluator for a named dimension.

        Parameters
        ----------
        name:
            Unique dimension identifier.
        evaluator:
            Object implementing the ``DimensionEvaluator`` protocol.
        """
        self._evaluators[name] = evaluator
        logger.debug("Registered evaluator for dimension '%s'", name)

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

        for name, evaluator in self._evaluators.items():
            logger.info("Evaluating dimension '%s'", name)
            try:
                score = evaluator.evaluate()
                scores.append(score)
                logger.info(
                    "Dimension '%s': %.3f / %.3f (%.1f%%)",
                    name, score.value, score.max_value, score.normalized * 100,
                )
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
    """Evaluator that runs pytest --cov and parses real coverage."""

    def __init__(self, project_root: str | Path = ".") -> None:
        """Initialize live code coverage evaluator."""
        self._project_root = Path(project_root)

    def evaluate(self) -> DimensionScore:
        """Evaluate and return live code coverage."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--cov=nines", "--cov-report=term-missing", "-q"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self._project_root),
            )
            coverage_pct = self._parse_coverage(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error("pytest --cov timed out after 300s")
            coverage_pct = 0.0
        except Exception as exc:
            logger.error("Failed to run pytest --cov: %s", exc)
            coverage_pct = 0.0

        return DimensionScore(
            name="code_coverage",
            value=coverage_pct,
            max_value=100.0,
            metadata={"unit": "percent"},
        )

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


class LiveTestCountEvaluator:
    """Evaluator that counts test functions from test files."""

    def __init__(self, test_dir: str | Path = "tests") -> None:
        """Initialize live test count evaluator."""
        self._test_dir = Path(test_dir)

    def evaluate(self) -> DimensionScore:
        """Evaluate and return live test count."""
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

        return DimensionScore(
            name="test_count",
            value=float(count),
            max_value=float(max(count, 1)),
            metadata={"unit": "tests", "files_scanned": files_scanned},
        )


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

    def evaluate(self) -> DimensionScore:
        """Evaluate and return lint cleanliness score."""
        violation_count = 0
        try:
            result = subprocess.run(
                ["python", "-m", "ruff", "check", str(self._src_dir), "--output-format=json", "-q"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.stdout.strip():
                violations = json.loads(result.stdout)
                violation_count = len(violations)
        except subprocess.TimeoutExpired:
            logger.error("ruff check timed out after 300s")
        except Exception as exc:
            logger.error("Failed to run ruff check: %s", exc)

        raw_score = max(0.0, 100.0 - violation_count * 2.0)
        return DimensionScore(
            name="lint_cleanliness",
            value=raw_score,
            max_value=100.0,
            metadata={"unit": "score", "violation_count": violation_count},
        )
