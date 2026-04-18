"""CLI contract tests for ``nines analyze --format json``.

These tests pin the C02a invariant that the analyze JSON output
exposes a top-level ``report_metadata`` block with
``id_namespace_version=2`` so downstream parsers can detect the
namespaced finding-ID format and the C09 derived economics formula
without sniffing individual records.

Covers: C02a (report_metadata), C02 (namespaced finding-ID format).
"""

from __future__ import annotations

import json
import re
import textwrap
from typing import TYPE_CHECKING

from click.testing import CliRunner

from nines.cli.main import cli

if TYPE_CHECKING:
    from pathlib import Path

# Pattern documented in ``references/project-identity.md``: namespaced
# finding-ID format ``PREFIX-{8-hex-fp}-{>=4-digit idx}``.  The regex is
# anchored so any drift back to the legacy bare ``AI-NNNN`` form will
# fail loudly.
_NAMESPACED_ID_RE = re.compile(r"^[A-Z]+-[0-9a-f]{8}-[0-9]+$")


def _make_sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python project for analyze CLI tests.

    Mirrors the helper in ``tests/test_cli.py`` so the report_metadata
    contract is tested against the same minimal fixture shape.  We add
    an Agent-facing ``CLAUDE.md`` so ``AgentImpactAnalyzer`` is
    guaranteed to emit at least one ``AI-`` finding (otherwise the
    namespaced-ID assertion would degenerate into a vacuous truth).
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Root."""\n')
    (pkg / "app.py").write_text(
        textwrap.dedent(
            """\
            def hello():
                return "world"
            """,
        ),
    )
    # Agent-facing artifact — guarantees at least one AI-* finding.
    (tmp_path / "CLAUDE.md").write_text(
        "# Project guidance\n\nUse the helpers in pkg/app.py.\n",
    )
    return tmp_path


def test_analyze_json_includes_report_metadata(tmp_path: Path) -> None:
    """``analyze --format json`` exposes ``report_metadata`` at top level.

    Acceptance criteria:
      - ``report_metadata.id_namespace_version == 2`` (C02a contract).
      - ``report_metadata.nines_version`` is a non-empty string.
      - ``report_metadata.analyzer_schema_version`` is a positive int
        (currently ``1``, reserved for future bumps).
    """
    project = _make_sample_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "-f",
            "json",
            "analyze",
            "--target-path",
            str(project),
            "--agent-impact",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert "report_metadata" in payload, (
        f"analyze --format json must expose top-level report_metadata; got keys={sorted(payload)}"
    )
    metadata = payload["report_metadata"]
    assert metadata["id_namespace_version"] == 2, (
        "id_namespace_version must be 2 for the C02 namespaced format; "
        f"got {metadata.get('id_namespace_version')!r}"
    )
    nines_version = metadata.get("nines_version")
    assert isinstance(nines_version, str) and nines_version, (
        f"nines_version must be a non-empty string; got {nines_version!r}"
    )
    schema_version = metadata.get("analyzer_schema_version")
    assert isinstance(schema_version, int) and schema_version >= 1, (
        f"analyzer_schema_version must be a positive int; got {schema_version!r}"
    )


def test_analyze_json_includes_finding_namespace(tmp_path: Path) -> None:
    """At least one finding ID matches the C02 namespaced format.

    Pattern: ``PREFIX-{8-hex-fp}-NNNN`` (see
    ``references/project-identity.md`` §2).  The CLAUDE.md fixture
    ensures ``AgentImpactAnalyzer`` emits at least one ``AI-*``
    finding, so the assertion bites.
    """
    project = _make_sample_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "-f",
            "json",
            "analyze",
            "--target-path",
            str(project),
            "--agent-impact",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    findings = payload.get("findings", [])
    assert findings, "expected at least one finding from agent-impact run"

    namespaced = [
        f
        for f in findings
        if isinstance(f, dict) and isinstance(f.get("id"), str) and _NAMESPACED_ID_RE.match(f["id"])
    ]
    assert namespaced, (
        "expected at least one finding ID in the namespaced format "
        f"({_NAMESPACED_ID_RE.pattern!r}); finding IDs were: "
        f"{[f.get('id') for f in findings if isinstance(f, dict)]}"
    )


# ---------------------------------------------------------------------------
# C03 N3c — --strict-graph CLI flag
# ---------------------------------------------------------------------------


from unittest.mock import patch  # noqa: E402

from nines.core.models import AnalysisResult  # noqa: E402


def _make_failing_graph_result(target: str) -> AnalysisResult:
    """Return an :class:`AnalysisResult` that fails the strict-graph gate.

    Mirrors the JSON shape :class:`AnalysisPipeline._run_graph_pipeline`
    emits, but with ``verification.passed=False`` and a single
    ``severity="critical"`` issue so the CLI's ``--strict-graph`` gate
    will fire deterministically without exercising the real pipeline.
    """
    return AnalysisResult(
        target=target,
        findings=[],
        metrics={
            "files_analyzed": 1,
            "total_lines": 1,
            "knowledge_graph": {
                "scan": {"total_files": 1, "languages": ["python"], "frameworks": []},
                "import_graph": {"edges": 0, "unresolved": 0},
                "graph": {"nodes": [], "edges": [], "layers": []},
                "verification": {
                    "passed": False,
                    "issues": [
                        {
                            "severity": "critical",
                            "category": "referential_integrity",
                            "message": "synthetic critical for gate test",
                            "node_ids": ["file:missing.py"],
                        },
                    ],
                    "node_count": 0,
                    "edge_count": 0,
                    "layer_coverage_pct": 0.0,
                    "orphan_count": 0,
                },
                "summary": {},
            },
            "strategy": "graph",
            "depth": "shallow",
        },
    )


def test_strict_graph_default_aborts_on_critical(tmp_path: Path) -> None:
    """``--strict-graph`` is on by default for ``--strategy graph``: when
    the analyzer reports ``verification.passed=False`` with at least one
    critical issue, the CLI exits with code 2.

    The full report is still written to disk for forensic use; only the
    exit code communicates the gate.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "stub.py").write_text("x = 1\n")
    out_dir = tmp_path / "reports"

    failing_result = _make_failing_graph_result(str(project))

    with patch(
        "nines.cli.commands.analyze.AnalysisPipeline",
    ) as pipeline_cls:
        pipeline_cls.return_value.run.return_value = failing_result
        # build_report_metadata is a classmethod on the real pipeline;
        # the mock needs to expose it (not the instance) so the JSON
        # branch in analyze_cmd doesn't blow up — but since we don't
        # request --format json here, we keep the patch minimal.
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                "--target-path",
                str(project),
                "--strategy",
                "graph",
                "--no-agent-impact",
                "--output-dir",
                str(out_dir),
            ],
        )

    assert result.exit_code == 2, (
        f"expected exit code 2 (strict graph gate); got {result.exit_code}. "
        f"stdout={result.output!r} stderr={getattr(result, 'stderr', '')!r}"
    )
    # Forensic artifact must still be on disk so operators can debug.
    written = out_dir / "analysis_report.txt"
    assert written.exists(), (
        "strict-graph gate must not skip the report write; operators need the forensic file"
    )


def test_strict_graph_disabled_does_not_abort(tmp_path: Path) -> None:
    """Passing ``--no-strict-graph`` overrides the default-True gate so
    even a critical-issue verification result returns exit code 0.

    Ensures the gate is opt-out: operators who want a soft warning can
    still get the JSON / text report without CI failing the build.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "stub.py").write_text("x = 1\n")
    out_dir = tmp_path / "reports"

    failing_result = _make_failing_graph_result(str(project))

    with patch(
        "nines.cli.commands.analyze.AnalysisPipeline",
    ) as pipeline_cls:
        pipeline_cls.return_value.run.return_value = failing_result
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                "--target-path",
                str(project),
                "--strategy",
                "graph",
                "--no-strict-graph",
                "--no-agent-impact",
                "--output-dir",
                str(out_dir),
            ],
        )

    assert result.exit_code == 0, (
        f"--no-strict-graph must not abort even with critical issues; "
        f"got exit_code={result.exit_code}, output={result.output!r}"
    )
    # Sanity: the report still wrote to disk.
    assert (out_dir / "analysis_report.txt").exists()
