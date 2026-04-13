"""Baseline management for self-evaluation reports.

``BaselineManager`` persists ``SelfEvalReport`` snapshots as JSON files
in a configurable directory (default ``data/baselines/``) so that
subsequent evaluations can be compared against known-good baselines.

Covers: FR-603, FR-604.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nines.iteration.self_eval import DimensionScore, SelfEvalReport

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of comparing a current report against a baseline.

    Attributes
    ----------
    improved:
        Dimensions that improved relative to baseline.
    regressed:
        Dimensions that regressed relative to baseline.
    unchanged:
        Dimensions that stayed the same.
    overall_delta:
        Change in overall score (current - baseline).
    details:
        Per-dimension comparison details.
    """

    improved: list[str] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    overall_delta: float = 0.0
    details: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "improved": list(self.improved),
            "regressed": list(self.regressed),
            "unchanged": list(self.unchanged),
            "overall_delta": self.overall_delta,
            "details": dict(self.details),
        }


class BaselineManager:
    """Manages persisted evaluation baselines for comparison.

    Baselines are stored as JSON files named ``{version}.json``
    inside the configured directory.

    Parameters
    ----------
    baselines_dir:
        Filesystem path where baseline JSON files are stored.
    """

    def __init__(self, baselines_dir: str | Path = "data/baselines") -> None:
        """Initialize baseline manager."""
        self._dir = Path(baselines_dir)

    def save_baseline(self, report: SelfEvalReport, version: str) -> Path:
        """Persist a report as a named baseline.

        Parameters
        ----------
        report:
            The evaluation report to save.
        version:
            Version label used as the filename stem.

        Returns
        -------
        Path
            Path to the written baseline file.
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{version}.json"
        data = report.to_dict()
        data["version"] = version
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Saved baseline '%s' to %s", version, path)
        return path

    def load_baseline(self, version: str) -> SelfEvalReport:
        """Load a previously saved baseline.

        Parameters
        ----------
        version:
            Version label of the baseline to load.

        Returns
        -------
        SelfEvalReport
            The deserialized report.

        Raises
        ------
        FileNotFoundError
            If no baseline with the given version exists.
        """
        path = self._dir / f"{version}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Baseline not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info("Loaded baseline '%s' from %s", version, path)
        return SelfEvalReport.from_dict(data)

    def list_baselines(self) -> list[str]:
        """Return version labels of all saved baselines."""
        if not self._dir.is_dir():
            return []
        return sorted(p.stem for p in self._dir.glob("*.json"))

    def compare(
        self,
        current: SelfEvalReport,
        baseline: SelfEvalReport,
        tolerance: float = 1e-6,
    ) -> ComparisonResult:
        """Compare a current report against a baseline report.

        Parameters
        ----------
        current:
            The fresh evaluation report.
        baseline:
            The reference baseline report.
        tolerance:
            Minimum absolute delta to consider a change significant.

        Returns
        -------
        ComparisonResult
            Categorized comparison of all dimensions.
        """
        result = ComparisonResult()
        result.overall_delta = current.overall - baseline.overall

        baseline_scores: dict[str, DimensionScore] = {}
        for s in baseline.scores:
            baseline_scores[s.name] = s

        for score in current.scores:
            base = baseline_scores.get(score.name)
            if base is None:
                result.improved.append(score.name)
                result.details[score.name] = {
                    "current": score.normalized,
                    "baseline": 0.0,
                    "delta": score.normalized,
                }
                continue

            delta = score.normalized - base.normalized
            result.details[score.name] = {
                "current": score.normalized,
                "baseline": base.normalized,
                "delta": delta,
            }

            if delta > tolerance:
                result.improved.append(score.name)
            elif delta < -tolerance:
                result.regressed.append(score.name)
            else:
                result.unchanged.append(score.name)

        return result
