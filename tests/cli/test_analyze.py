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
        "analyze --format json must expose top-level report_metadata; "
        f"got keys={sorted(payload)}"
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
        f"analyzer_schema_version must be a positive int; "
        f"got {schema_version!r}"
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
        f for f in findings
        if isinstance(f, dict)
        and isinstance(f.get("id"), str)
        and _NAMESPACED_ID_RE.match(f["id"])
    ]
    assert namespaced, (
        "expected at least one finding ID in the namespaced format "
        f"({_NAMESPACED_ID_RE.pattern!r}); finding IDs were: "
        f"{[f.get('id') for f in findings if isinstance(f, dict)]}"
    )

