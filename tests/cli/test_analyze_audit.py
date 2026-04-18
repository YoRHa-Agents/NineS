"""CLI contract tests for ``nines analyze --audit`` (C10).

Pins the C10 behaviour:

* ``--audit`` (default on) runs the consistency auditor in advisory
  mode — even a critical-finding report exits ``0``.
* ``--audit --strict-audit`` blocks: critical findings cause the CLI
  to exit with :data:`STRICT_AUDIT_EXIT_CODE` (3).
* ``--format json`` exposes a top-level ``audit_report`` block so
  machine consumers can read the verdict.

The fake ``AnalysisResult`` deliberately injects two §-style
regressions (duplicate finding IDs + the §4.6 ``break_even == 2``
constant) so the test cannot pass by accident if the auditor is
short-circuited.

Covers: C10 cross-artifact consistency auditor (advisory + strict).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

from click.testing import CliRunner

from nines.cli.commands.analyze import STRICT_AUDIT_EXIT_CODE
from nines.cli.main import cli
from nines.core.models import AnalysisResult, Finding

if TYPE_CHECKING:
    from pathlib import Path


_DUP_ID = "AI-deadbeef-0001"


def _make_regressed_result(target: str) -> AnalysisResult:
    """Return an ``AnalysisResult`` whose JSON shape triggers two critical
    auditor findings:

    1. Duplicate finding ID (``finding_id_uniqueness`` → critical).
    2. ``break_even_interactions == 2`` with overhead/savings that
       cannot algebraically derive ``2``
       (``economics_break_even_sanity`` → critical).
    """
    return AnalysisResult(
        target=target,
        findings=[
            Finding(id=_DUP_ID, severity="info", category="x", message="m1"),
            # Same id as above → forced collision.
            Finding(id=_DUP_ID, severity="info", category="y", message="m2"),
        ],
        metrics={
            "agent_impact": {
                "economics": {
                    "formula_version": 2,
                    "break_even_interactions": 2,
                    "overhead_tokens": 100000,
                    "per_interaction_savings_tokens": 5000,
                },
            },
            "files_analyzed": 1,
            "total_lines": 1,
            "strategy": "functional",
            "depth": "shallow",
        },
    )


def test_analyze_audit_advisory_mode_does_not_block(tmp_path: Path) -> None:
    """``--audit`` (default) is advisory: critical findings → exit 0.

    Mocks the pipeline so the regressed result is fed straight to the
    auditor, isolating the test from the real analyzer.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "stub.py").write_text("x = 1\n")
    out_dir = tmp_path / "reports"

    fake_result = _make_regressed_result(str(project))

    with patch(
        "nines.cli.commands.analyze.AnalysisPipeline",
    ) as pipeline_cls:
        pipeline_cls.return_value.run.return_value = fake_result
        # build_report_metadata is referenced; pass through to real impl.
        from nines.analyzer.pipeline import (
            AnalysisPipeline as RealAnalysisPipeline,
        )

        pipeline_cls.build_report_metadata = (
            RealAnalysisPipeline.build_report_metadata
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                "--target-path",
                str(project),
                "--no-agent-impact",
                "--no-strict-graph",
                # --audit is on by default; --strict-audit OFF
                "--output-dir",
                str(out_dir),
            ],
        )

    assert result.exit_code == 0, (
        "advisory --audit must NOT block even on critical findings; "
        f"got exit_code={result.exit_code}, output={result.output!r}"
    )
    # Forensic file still on disk.
    assert (out_dir / "analysis_report.txt").exists()
    # Sanity: the advisory text mentions Audit and at least one critical.
    written = (out_dir / "analysis_report.txt").read_text(encoding="utf-8")
    assert "Audit:" in written, f"audit summary missing from text: {written!r}"
    assert "critical=" in written


def test_analyze_strict_audit_blocks_on_critical(tmp_path: Path) -> None:
    """``--strict-audit`` causes a non-zero exit on critical findings.

    Same fake regressed result as the advisory test — only the flag
    differs, so the assertion isolates strict-audit gate behaviour.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "stub.py").write_text("x = 1\n")
    out_dir = tmp_path / "reports"

    fake_result = _make_regressed_result(str(project))

    with patch(
        "nines.cli.commands.analyze.AnalysisPipeline",
    ) as pipeline_cls:
        pipeline_cls.return_value.run.return_value = fake_result
        from nines.analyzer.pipeline import (
            AnalysisPipeline as RealAnalysisPipeline,
        )

        pipeline_cls.build_report_metadata = (
            RealAnalysisPipeline.build_report_metadata
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                "--target-path",
                str(project),
                "--no-agent-impact",
                "--no-strict-graph",
                "--strict-audit",
                "--output-dir",
                str(out_dir),
            ],
        )

    assert result.exit_code == STRICT_AUDIT_EXIT_CODE, (
        f"--strict-audit must exit {STRICT_AUDIT_EXIT_CODE} on critical "
        f"findings; got exit_code={result.exit_code}, "
        f"output={result.output!r}"
    )
    # Forensic file still written before the gate fires (same ordering
    # rationale as --strict-graph).
    assert (out_dir / "analysis_report.txt").exists()


def test_analyze_audit_emits_audit_report_in_json(tmp_path: Path) -> None:
    """``--format json`` payload exposes a top-level ``audit_report`` block.

    Verifies (a) the block exists, (b) ``checks_run`` lists all six
    built-in checks in registration order, (c) the summary reflects
    the seeded critical findings.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "stub.py").write_text("x = 1\n")

    fake_result = _make_regressed_result(str(project))

    with patch(
        "nines.cli.commands.analyze.AnalysisPipeline",
    ) as pipeline_cls:
        pipeline_cls.return_value.run.return_value = fake_result
        from nines.analyzer.pipeline import (
            AnalysisPipeline as RealAnalysisPipeline,
        )

        pipeline_cls.build_report_metadata = (
            RealAnalysisPipeline.build_report_metadata
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-f",
                "json",
                "analyze",
                "--target-path",
                str(project),
                "--no-agent-impact",
                "--no-strict-graph",
            ],
        )

    assert result.exit_code == 0, (
        f"advisory --audit + --format json must exit 0; "
        f"got exit_code={result.exit_code}, output={result.output!r}"
    )
    payload = json.loads(result.output)
    assert "audit_report" in payload, (
        f"top-level audit_report missing; payload keys={sorted(payload)}"
    )
    audit_report = payload["audit_report"]
    assert audit_report["checks_run"] == [
        "finding_id_uniqueness",
        "finding_id_namespace",
        "economics_formula_version",
        "economics_break_even_sanity",
        "graph_verification_passed",
        "report_metadata_presence",
    ]
    summary = audit_report["summary"]
    assert summary["critical"] >= 2, (
        f"expected >= 2 critical findings (duplicate id + break_even); "
        f"summary={summary}"
    )
    # Sanity: the per-finding dicts include the contract fields.
    crit_finding = next(
        f for f in audit_report["findings"] if f["severity"] == "critical"
    )
    assert {"check_name", "category", "severity", "message", "affected_keys", "evidence"} <= set(
        crit_finding,
    )
