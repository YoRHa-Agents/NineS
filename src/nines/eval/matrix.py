"""Matrix-based evaluation across multiple dimensions.

``MatrixEvaluator`` defines axes (dimensions), generates all cell combinations
via ``itertools.product``, applies exclusion rules, and runs evaluations across
the resulting matrix.

Covers: FR-118.
"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from nines.eval.models import EvalResult

logger = logging.getLogger(__name__)


@dataclass
class MatrixAxis:
    """A single dimension in the evaluation matrix."""

    name: str
    values: list[str] = field(default_factory=list)


@dataclass
class MatrixCell:
    """A single combination of axis values to evaluate."""

    coordinates: dict[str, str] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Return a unique key for this cell's coordinates."""
        parts = [f"{k}={v}" for k, v in sorted(self.coordinates.items())]
        return "|".join(parts)


@dataclass
class MatrixResult:
    """Result of evaluating one cell in the matrix."""

    cell: MatrixCell
    eval_result: EvalResult | None = None
    skipped: bool = False
    skip_reason: str = ""


ExclusionRule = Callable[[dict[str, str]], bool]
CellEvaluator = Callable[[MatrixCell], EvalResult]


class MatrixEvaluator:
    """Defines an evaluation matrix and runs evaluations across all cells."""

    def __init__(self) -> None:
        """Initialize matrix evaluator."""
        self._axes: list[MatrixAxis] = []
        self._exclusion_rules: list[ExclusionRule] = []

    def add_axis(self, name: str, values: list[str]) -> None:
        """Add axis."""
        self._axes.append(MatrixAxis(name=name, values=values))

    def add_exclusion_rule(self, rule: ExclusionRule) -> None:
        """Add exclusion rule."""
        self._exclusion_rules.append(rule)

    def generate_cells(self) -> list[MatrixCell]:
        """Generate cells."""
        if not self._axes:
            return []

        axis_names = [a.name for a in self._axes]
        axis_values = [a.values for a in self._axes]

        cells: list[MatrixCell] = []
        for combo in itertools.product(*axis_values):
            coords = dict(zip(axis_names, combo, strict=True))
            cells.append(MatrixCell(coordinates=coords))
        return cells

    def _is_excluded(self, cell: MatrixCell) -> str | None:
        """Return the exclusion reason or None if the cell is allowed."""
        for rule in self._exclusion_rules:
            try:
                if rule(cell.coordinates):
                    return f"Excluded by rule: {rule.__name__}"
            except Exception as exc:
                logger.warning("Exclusion rule error for %s: %s", cell.key, exc)
                return f"Exclusion rule error: {exc}"
        return None

    def run(self, evaluator: CellEvaluator) -> list[MatrixResult]:
        """Generate all cells, apply exclusions, and evaluate remaining cells."""
        cells = self.generate_cells()
        results: list[MatrixResult] = []

        for cell in cells:
            exclusion_reason = self._is_excluded(cell)
            if exclusion_reason:
                results.append(MatrixResult(
                    cell=cell, skipped=True, skip_reason=exclusion_reason
                ))
                continue

            try:
                eval_result = evaluator(cell)
                results.append(MatrixResult(cell=cell, eval_result=eval_result))
            except Exception as exc:
                logger.error("Evaluation failed for cell %s: %s", cell.key, exc)
                results.append(MatrixResult(
                    cell=cell,
                    eval_result=EvalResult(
                        task_id=cell.key,
                        success=False,
                        error=str(exc),
                    ),
                ))

        return results

    @property
    def axes(self) -> list[MatrixAxis]:
        """Return the list of defined axes."""
        return list(self._axes)

    def total_cells(self) -> int:
        """Total cells."""
        if not self._axes:
            return 0
        count = 1
        for axis in self._axes:
            count *= len(axis.values)
        return count
