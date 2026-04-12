"""Tests for the NineS CLI entry point."""

from click.testing import CliRunner

from nines import __version__
from nines.cli.main import cli

EXPECTED_SUBCOMMANDS = ["eval", "collect", "analyze", "self-eval", "iterate", "install"]


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
