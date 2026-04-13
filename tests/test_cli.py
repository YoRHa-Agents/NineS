"""Tests for the NineS CLI entry point."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from click.testing import CliRunner

from nines import __version__
from nines.cli.main import cli

EXPECTED_SUBCOMMANDS = [
    "eval",
    "collect",
    "analyze",
    "benchmark",
    "self-eval",
    "iterate",
    "install",
    "update",
]


class TestHelpOutput:
    def test_help_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "NineS" in result.output
        for cmd in EXPECTED_SUBCOMMANDS:
            assert cmd in result.output

    def test_help_shows_global_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "--config" in result.output
        assert "--verbose" in result.output
        assert "--output" in result.output
        assert "--format" in result.output
        assert "--no-color" in result.output
        assert "--version" in result.output


class TestVersion:
    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
        assert "nines" in result.output


class TestInstallCommand:
    def test_install_help_shows_global_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["install", "--help"])
        assert result.exit_code == 0
        assert "--global" in result.output

    def test_install_global_uses_home_dir(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        with patch("nines.cli.commands.install.Path.home", return_value=tmp_path):
            runner = CliRunner()
            result = runner.invoke(cli, ["install", "--target", "cursor", "--global"])
        assert result.exit_code == 0
        assert "global" in result.output
        assert (tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md").exists()

    def test_install_without_global_uses_cwd(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["install", "--target", "cursor"], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "global" not in result.output


class TestEvalCommand:
    def test_eval_requires_tasks_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["eval"])
        assert result.exit_code == 2
        assert "--tasks-path" in result.output


class TestCollectCommand:
    def test_collect_requires_source(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["collect"])
        assert result.exit_code == 2
        assert "--source" in result.output


class TestAllCommandsExist:
    def test_all_commands_have_help(self) -> None:
        runner = CliRunner()
        for cmd in EXPECTED_SUBCOMMANDS:
            result = runner.invoke(cli, [cmd, "--help"])
            assert result.exit_code == 0, f"'{cmd} --help' failed"
            assert len(result.output) > 0

    def test_each_subcommand_has_help(self) -> None:
        runner = CliRunner()
        for cmd in EXPECTED_SUBCOMMANDS:
            result = runner.invoke(cli, [cmd, "--help"])
            assert result.exit_code == 0, f"'{cmd} --help' failed"
            assert len(result.output) > 0


def _make_sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python project for CLI tests."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Root."""\n')
    (pkg / "app.py").write_text(
        textwrap.dedent("""\
            def hello():
                return "world"
        """),
    )
    return tmp_path


class TestAnalyzeCommand:
    """Tests for the 'analyze' command with new flags."""

    def test_analyze_help_shows_new_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--agent-impact" in result.output
        assert "--keypoints" in result.output
        assert "--depth" in result.output

    def test_analyze_basic_text(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", "--target-path", str(project)],
        )
        assert result.exit_code == 0
        assert "Agent Impact Analysis of" in result.output
        assert "Agent mechanisms:" in result.output
        assert "Key points:" in result.output

    def test_analyze_opt_out_text(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", "--target-path", str(project), "--no-agent-impact"],
        )
        assert result.exit_code == 0
        assert "Analysis of" in result.output
        assert "Agent mechanisms" not in result.output
        assert "Key points" not in result.output

    def test_analyze_agent_impact_text(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", "--target-path", str(project), "--agent-impact"],
        )
        assert result.exit_code == 0
        assert "Agent mechanisms:" in result.output
        assert "Agent artifacts:" in result.output

    def test_analyze_keypoints_text(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", "--target-path", str(project), "--keypoints"],
        )
        assert result.exit_code == 0
        assert "Agent mechanisms:" in result.output
        assert "Key points:" in result.output

    def test_analyze_agent_impact_json(self, tmp_path: Path) -> None:
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
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "agent_impact" in data["metrics"]

    def test_analyze_keypoints_json(self, tmp_path: Path) -> None:
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
                "--keypoints",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "agent_impact" in data["metrics"]
        assert "key_points" in data["metrics"]

    def test_analyze_depth_option(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        runner = CliRunner()
        for depth in ("shallow", "deep"):
            result = runner.invoke(
                cli,
                [
                    "analyze",
                    "--target-path",
                    str(project),
                    "--depth",
                    depth,
                ],
            )
            assert result.exit_code == 0

    def test_analyze_depth_invalid_rejected(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", "--target-path", ".", "--depth", "nope"],
        )
        assert result.exit_code != 0

    def test_analyze_verbose_includes_depth(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-v",
                "analyze",
                "--target-path",
                str(project),
                "--depth",
                "deep",
            ],
        )
        assert result.exit_code == 0
        assert "depth=deep" in result.output

    def test_analyze_output_dir_with_agent_impact(
        self,
        tmp_path: Path,
    ) -> None:
        project = _make_sample_project(tmp_path)
        out = tmp_path / "reports"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                "--target-path",
                str(project),
                "--agent-impact",
                "--output-dir",
                str(out),
            ],
        )
        assert result.exit_code == 0
        assert (out / "analysis_report.txt").exists()
        content = (out / "analysis_report.txt").read_text()
        assert "Agent mechanisms:" in content
