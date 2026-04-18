"""Evaluation report generators.

``MarkdownReporter`` produces a human-readable ``benchmark_report.md`` from a
list of ``EvalResult`` objects.

``JSONReporter`` produces structured JSON output conforming to a fixed schema.

Covers: FR-115, FR-116.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.eval.models import EvalResult

logger = logging.getLogger(__name__)

REPORT_JSON_SCHEMA = {
    "type": "object",
    "required": ["version", "generated_at", "summary", "results"],
    "properties": {
        "version": {"type": "string"},
        "generated_at": {"type": "string"},
        "summary": {
            "type": "object",
            "required": ["total", "passed", "failed", "pass_rate", "avg_score"],
            "properties": {
                "total": {"type": "integer"},
                "passed": {"type": "integer"},
                "failed": {"type": "integer"},
                "pass_rate": {"type": "number"},
                "avg_score": {"type": "number"},
                "total_duration_ms": {"type": "number"},
            },
        },
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["task_id", "success", "composite_score"],
            },
        },
    },
}


@dataclass
class ReportSummary:
    """Report summary."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    avg_score: float = 0.0
    total_duration_ms: float = 0.0


def _compute_summary(results: list[EvalResult]) -> ReportSummary:
    """Compute summary."""
    total = len(results)
    if total == 0:
        return ReportSummary()

    passed = sum(1 for r in results if r.success)
    failed = total - passed
    avg_score = sum(r.composite_score for r in results) / total
    total_dur = sum(r.duration_ms for r in results)

    return ReportSummary(
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=passed / total,
        avg_score=avg_score,
        total_duration_ms=total_dur,
    )


class MarkdownReporter:
    """Generates a Markdown benchmark report from evaluation results."""

    def __init__(self, title: str = "Benchmark Report") -> None:
        """Initialize markdown reporter."""
        self._title = title

    def generate(self, results: list[EvalResult]) -> str:
        """Generate a formatted evaluation report."""
        summary = _compute_summary(results)
        lines: list[str] = []

        lines.append(f"# {self._title}")
        lines.append("")
        lines.append(f"*Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}*")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total tasks | {summary.total} |")
        lines.append(f"| Passed | {summary.passed} |")
        lines.append(f"| Failed | {summary.failed} |")
        lines.append(f"| Pass rate | {summary.pass_rate:.1%} |")
        lines.append(f"| Avg score | {summary.avg_score:.4f} |")
        lines.append(f"| Total duration | {summary.total_duration_ms:.1f} ms |")
        lines.append("")

        lines.append("## Results")
        lines.append("")
        lines.append("| Task ID | Name | Score | Duration (ms) | Status |")
        lines.append("|---------|------|-------|---------------|--------|")

        for r in results:
            status = "PASS" if r.success else "FAIL"
            name = r.task_name or r.task_id
            lines.append(
                f"| {r.task_id} | {name} | {r.composite_score:.4f} "
                f"| {r.duration_ms:.1f} | {status} |"
            )

        lines.append("")

        failed_results = [r for r in results if not r.success]
        if failed_results:
            lines.append("## Failures")
            lines.append("")
            for r in failed_results:
                lines.append(f"### {r.task_id}")
                lines.append("")
                lines.append(f"**Error:** {r.error or 'Unknown error'}")
                lines.append("")

        return "\n".join(lines)


class JSONReporter:
    """Generates structured JSON output from evaluation results.

    The output conforms to ``REPORT_JSON_SCHEMA``.
    """

    VERSION = "1.0"

    def generate(self, results: list[EvalResult]) -> str:
        """Generate the report as structured data."""
        data = self.generate_dict(results)
        return json.dumps(data, indent=2, default=str)

    def generate_dict(self, results: list[EvalResult]) -> dict[str, Any]:
        """Generate dict."""
        summary = _compute_summary(results)
        return {
            "version": self.VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": asdict(summary),
            "results": [r.to_dict() for r in results],
        }

    @staticmethod
    def validate_schema(data: dict[str, Any]) -> list[str]:
        """Basic schema validation — returns list of error strings (empty = valid)."""
        errors: list[str] = []
        for key in REPORT_JSON_SCHEMA["required"]:
            if key not in data:
                errors.append(f"Missing required key: {key}")
        if "summary" in data:
            for key in REPORT_JSON_SCHEMA["properties"]["summary"]["required"]:
                if key not in data["summary"]:
                    errors.append(f"Missing summary key: {key}")
        if "results" in data and not isinstance(data["results"], list):
            errors.append("'results' must be an array")
        return errors
