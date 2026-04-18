"""Tests for the ``nines iterate`` CLI command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

from click.testing import CliRunner

from nines.cli.commands.iterate import _detect_src_dir, _detect_test_dir
from nines.cli.main import cli
from nines.iteration.self_eval import DimensionScore


def _make_fake_score(name: str, value: float = 0.8) -> DimensionScore:
    return DimensionScore(name=name, value=value, max_value=1.0)


class TestIterateHelp:
    def test_iterate_help(self) -> None:
        """Verify --project-root, --src-dir, --test-dir appear in help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["iterate", "--help"])
        assert result.exit_code == 0
        assert "--project-root" in result.output
        assert "--src-dir" in result.output
        assert "--test-dir" in result.output
        assert "--max-rounds" in result.output
        assert "--threshold" in result.output


class TestIterateDefaultConverges:
    def test_iterate_default_converges(self) -> None:
        """Run with defaults (stub evaluators), verify convergence message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["iterate"])
        assert result.exit_code == 0
        assert "Converged" in result.output or "Did not converge" in result.output


class TestIterateJsonOutput:
    def test_iterate_json_output(self) -> None:
        """Run with -f json, verify valid JSON with rounds/converged/history."""
        runner = CliRunner()
        result = runner.invoke(cli, ["-f", "json", "iterate"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                json_start = i
                break
        assert json_start is not None, f"No JSON found in output: {result.output}"
        json_text = "\n".join(lines[json_start:])
        data = json.loads(json_text)
        assert "rounds" in data
        assert "converged" in data
        assert "history" in data
        assert isinstance(data["history"], list)
        assert len(data["history"]) > 0


class TestIterateWithProjectRoot:
    def test_iterate_with_project_root(self, tmp_path: Path) -> None:
        """Mock live evaluators, verify they're used when --project-root is given."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text("def test_x(): pass\n")

        with (
            patch("nines.cli.commands.iterate.LiveCodeCoverageEvaluator") as mock_cov,
            patch("nines.cli.commands.iterate.LiveTestCountEvaluator") as mock_test,
            patch("nines.cli.commands.iterate.LiveModuleCountEvaluator") as mock_mod,
            patch("nines.cli.commands.iterate.DocstringCoverageEvaluator") as mock_doc,
            patch("nines.cli.commands.iterate.LintCleanlinessEvaluator") as mock_lint,
        ):
            mock_cov.return_value.evaluate.return_value = _make_fake_score("code_coverage")
            mock_test.return_value.evaluate.return_value = _make_fake_score("test_count")
            mock_mod.return_value.evaluate.return_value = _make_fake_score("module_count")
            mock_doc.return_value.evaluate.return_value = _make_fake_score("docstring_coverage")
            mock_lint.return_value.evaluate.return_value = _make_fake_score("lint_cleanliness")

            runner = CliRunner()
            result = runner.invoke(cli, ["iterate", "--project-root", str(tmp_path)])
            assert result.exit_code == 0
            mock_cov.assert_called_once()
            mock_test.assert_called_once()
            mock_mod.assert_called_once()
            mock_doc.assert_called_once()
            mock_lint.assert_called_once()

    def test_iterate_with_project_root_verbose(self, tmp_path: Path) -> None:
        """Verify verbose output includes live evaluator info."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        with (
            patch("nines.cli.commands.iterate.LiveCodeCoverageEvaluator") as mock_cov,
            patch("nines.cli.commands.iterate.LiveTestCountEvaluator") as mock_test,
            patch("nines.cli.commands.iterate.LiveModuleCountEvaluator") as mock_mod,
            patch("nines.cli.commands.iterate.DocstringCoverageEvaluator") as mock_doc,
            patch("nines.cli.commands.iterate.LintCleanlinessEvaluator") as mock_lint,
        ):
            mock_cov.return_value.evaluate.return_value = _make_fake_score("code_coverage")
            mock_test.return_value.evaluate.return_value = _make_fake_score("test_count")
            mock_mod.return_value.evaluate.return_value = _make_fake_score("module_count")
            mock_doc.return_value.evaluate.return_value = _make_fake_score("docstring_coverage")
            mock_lint.return_value.evaluate.return_value = _make_fake_score("lint_cleanliness")

            runner = CliRunner()
            result = runner.invoke(cli, ["-v", "iterate", "--project-root", str(tmp_path)])
            assert result.exit_code == 0
            assert "Using live evaluators" in result.output


class TestDetectSrcDir:
    def test_detect_src_dir_with_src(self, tmp_path: Path) -> None:
        """Prefer src/ if it exists and contains .py files."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("x = 1\n")
        assert _detect_src_dir(tmp_path) == str(src)

    def test_detect_src_dir_with_lib(self, tmp_path: Path) -> None:
        """Fall back to lib/ if src/ doesn't exist."""
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "mod.py").write_text("x = 1\n")
        assert _detect_src_dir(tmp_path) == str(lib)

    def test_detect_src_dir_fallback_to_root(self, tmp_path: Path) -> None:
        """Fall back to project root if it has .py files and no src/lib."""
        (tmp_path / "mod.py").write_text("x = 1\n")
        assert _detect_src_dir(tmp_path) == str(tmp_path)

    def test_detect_src_dir_empty_project(self, tmp_path: Path) -> None:
        """Return project root if no .py files found anywhere."""
        assert _detect_src_dir(tmp_path) == str(tmp_path)


class TestDetectTestDir:
    def test_detect_test_dir_with_tests(self, tmp_path: Path) -> None:
        """Prefer tests/ directory."""
        (tmp_path / "tests").mkdir()
        assert _detect_test_dir(tmp_path) == str(tmp_path / "tests")

    def test_detect_test_dir_with_test(self, tmp_path: Path) -> None:
        """Fall back to test/ directory."""
        (tmp_path / "test").mkdir()
        assert _detect_test_dir(tmp_path) == str(tmp_path / "test")

    def test_detect_test_dir_fallback(self, tmp_path: Path) -> None:
        """Return 'tests' string if no test directory found."""
        assert _detect_test_dir(tmp_path) == "tests"


class TestIterateWarnsNoContext:
    def test_iterate_warns_no_context(self) -> None:
        """Verify warning when using stub evaluators (no --project-root)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["iterate"])
        assert result.exit_code == 0
        combined = result.output
        assert "No project context provided" in combined or (
            hasattr(result, "stderr") and "No project context provided" in (result.stderr or "")
        ), f"Expected warning in output. Got stdout: {result.output!r}"

    def test_iterate_warns_with_logging(self) -> None:
        """Verify the logger warning fires when no project root is given."""
        with patch("nines.cli.commands.iterate.logger") as mock_logger:
            runner = CliRunner()
            result = runner.invoke(cli, ["iterate"])
            assert result.exit_code == 0
            mock_logger.warning.assert_called_once()
            warn_msg = mock_logger.warning.call_args[0][0]
            assert "No project context" in warn_msg
