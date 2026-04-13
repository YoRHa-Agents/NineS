"""Tests for live evaluators in nines.iteration.self_eval.

Covers:
  - LiveCodeCoverageEvaluator parsing and subprocess error handling
  - LiveTestCountEvaluator AST-based test counting
  - LiveModuleCountEvaluator file discovery
  - DocstringCoverageEvaluator docstring ratio computation
  - LintCleanlinessEvaluator ruff output parsing and scoring
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.iteration.self_eval import (
    CodeCoverageEvaluator,
    DimensionEvaluator,
    DocstringCoverageEvaluator,
    LintCleanlinessEvaluator,
    LiveCodeCoverageEvaluator,
    LiveModuleCountEvaluator,
    LiveTestCountEvaluator,
    ModuleCountEvaluator,
    TestCountEvaluator,
    UnitTestCountEvaluator,
)


# ---------------------------------------------------------------------------
# Backward-compatibility check
# ---------------------------------------------------------------------------


def test_original_evaluators_still_exist() -> None:
    """Original placeholder evaluators remain importable and functional."""
    cov = CodeCoverageEvaluator(coverage_pct=75.0)
    assert cov.evaluate().value == 75.0

    tc = UnitTestCountEvaluator(count=10)
    assert tc.evaluate().value == 10.0

    mc = ModuleCountEvaluator(count=5)
    assert mc.evaluate().value == 5.0

    assert TestCountEvaluator is UnitTestCountEvaluator


def test_live_evaluators_satisfy_protocol() -> None:
    """All live evaluators satisfy the DimensionEvaluator protocol."""
    assert isinstance(LiveCodeCoverageEvaluator(), DimensionEvaluator)
    assert isinstance(LiveTestCountEvaluator(), DimensionEvaluator)
    assert isinstance(LiveModuleCountEvaluator(), DimensionEvaluator)
    assert isinstance(DocstringCoverageEvaluator(), DimensionEvaluator)
    assert isinstance(LintCleanlinessEvaluator(), DimensionEvaluator)


# ---------------------------------------------------------------------------
# LiveCodeCoverageEvaluator
# ---------------------------------------------------------------------------


class TestLiveCodeCoverageEvaluator:
    """Tests for LiveCodeCoverageEvaluator."""

    def test_parse_coverage_typical(self) -> None:
        stdout = (
            "tests/test_foo.py ...\n"
            "Name          Stmts   Miss  Cover\n"
            "-------------------------------\n"
            "src/foo.py       50     10    80%\n"
            "TOTAL            50     10    80%\n"
        )
        assert LiveCodeCoverageEvaluator._parse_coverage(stdout) == 80.0

    def test_parse_coverage_no_percent_sign(self) -> None:
        stdout = "TOTAL            50     10    80\n"
        assert LiveCodeCoverageEvaluator._parse_coverage(stdout) == 80.0

    def test_parse_coverage_no_total_line(self) -> None:
        stdout = "some random output\nno total here\n"
        assert LiveCodeCoverageEvaluator._parse_coverage(stdout) == 0.0

    @patch("nines.iteration.self_eval.subprocess.run")
    def test_evaluate_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="TOTAL   100   20   80%\n",
            returncode=0,
        )
        ev = LiveCodeCoverageEvaluator(project_root="/fake")
        score = ev.evaluate()
        assert score.name == "code_coverage"
        assert score.value == 80.0
        assert score.max_value == 100.0

    @patch("nines.iteration.self_eval.subprocess.run")
    def test_evaluate_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)
        ev = LiveCodeCoverageEvaluator()
        score = ev.evaluate()
        assert score.value == 0.0

    @patch("nines.iteration.self_eval.subprocess.run")
    def test_evaluate_subprocess_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = OSError("command not found")
        ev = LiveCodeCoverageEvaluator()
        score = ev.evaluate()
        assert score.value == 0.0


# ---------------------------------------------------------------------------
# LiveTestCountEvaluator
# ---------------------------------------------------------------------------


class TestLiveTestCountEvaluator:
    """Tests for LiveTestCountEvaluator."""

    def test_counts_test_functions(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(
            "def test_alpha():\n    pass\n\n"
            "def test_beta():\n    pass\n\n"
            "def helper():\n    pass\n",
            encoding="utf-8",
        )
        ev = LiveTestCountEvaluator(test_dir=tmp_path)
        score = ev.evaluate()
        assert score.name == "test_count"
        assert score.value == 2.0
        assert score.metadata["files_scanned"] == 1

    def test_skips_non_test_files(self, tmp_path: Path) -> None:
        (tmp_path / "helper.py").write_text("def test_x(): pass\n", encoding="utf-8")
        ev = LiveTestCountEvaluator(test_dir=tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0

    def test_handles_nested_dirs(self, tmp_path: Path) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "test_nested.py").write_text("def test_one(): pass\n", encoding="utf-8")
        ev = LiveTestCountEvaluator(test_dir=tmp_path)
        score = ev.evaluate()
        assert score.value == 1.0

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        (tmp_path / "test_bad.py").write_text("def test_x(:\n", encoding="utf-8")
        ev = LiveTestCountEvaluator(test_dir=tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0

    def test_empty_dir(self, tmp_path: Path) -> None:
        ev = LiveTestCountEvaluator(test_dir=tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0
        assert score.max_value == 1.0

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        ev = LiveTestCountEvaluator(test_dir=tmp_path / "does_not_exist")
        score = ev.evaluate()
        assert score.value == 0.0


# ---------------------------------------------------------------------------
# LiveModuleCountEvaluator
# ---------------------------------------------------------------------------


class TestLiveModuleCountEvaluator:
    """Tests for LiveModuleCountEvaluator."""

    def test_counts_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "module_a.py").write_text("", encoding="utf-8")
        (tmp_path / "module_b.py").write_text("", encoding="utf-8")
        (tmp_path / "__init__.py").write_text("", encoding="utf-8")
        ev = LiveModuleCountEvaluator(src_dir=tmp_path)
        score = ev.evaluate()
        assert score.name == "module_count"
        assert score.value == 2.0

    def test_ignores_pycache(self, tmp_path: Path) -> None:
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-312.pyc.py").write_text("", encoding="utf-8")
        (tmp_path / "real.py").write_text("", encoding="utf-8")
        ev = LiveModuleCountEvaluator(src_dir=tmp_path)
        score = ev.evaluate()
        assert score.value == 1.0

    def test_empty_dir(self, tmp_path: Path) -> None:
        ev = LiveModuleCountEvaluator(src_dir=tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0
        assert score.max_value == 1.0


# ---------------------------------------------------------------------------
# DocstringCoverageEvaluator
# ---------------------------------------------------------------------------


class TestDocstringCoverageEvaluator:
    """Tests for DocstringCoverageEvaluator."""

    def test_full_coverage(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text(
            'class Foo:\n    """Foo class."""\n\n'
            'def bar():\n    """Bar func."""\n    pass\n',
            encoding="utf-8",
        )
        ev = DocstringCoverageEvaluator(src_dir=tmp_path)
        score = ev.evaluate()
        assert score.name == "docstring_coverage"
        assert score.value == 100.0

    def test_partial_coverage(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text(
            'def documented():\n    """Has docstring."""\n    pass\n\n'
            "def undocumented():\n    pass\n",
            encoding="utf-8",
        )
        ev = DocstringCoverageEvaluator(src_dir=tmp_path)
        score = ev.evaluate()
        assert score.value == 50.0
        assert score.metadata["total"] == 2
        assert score.metadata["documented"] == 1

    def test_skips_private(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text(
            "def _private():\n    pass\n\n"
            'def public():\n    """Has doc."""\n    pass\n',
            encoding="utf-8",
        )
        ev = DocstringCoverageEvaluator(src_dir=tmp_path)
        score = ev.evaluate()
        assert score.metadata["total"] == 1
        assert score.value == 100.0

    def test_empty_dir(self, tmp_path: Path) -> None:
        ev = DocstringCoverageEvaluator(src_dir=tmp_path)
        score = ev.evaluate()
        assert score.value == 0.0

    def test_ignores_pycache(self, tmp_path: Path) -> None:
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("def public(): pass\n", encoding="utf-8")
        ev = DocstringCoverageEvaluator(src_dir=tmp_path)
        score = ev.evaluate()
        assert score.metadata["total"] == 0


# ---------------------------------------------------------------------------
# LintCleanlinessEvaluator
# ---------------------------------------------------------------------------


class TestLintCleanlinessEvaluator:
    """Tests for LintCleanlinessEvaluator."""

    @patch("nines.iteration.self_eval.subprocess.run")
    def test_clean_code(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        ev = LintCleanlinessEvaluator(src_dir="/fake")
        score = ev.evaluate()
        assert score.name == "lint_cleanliness"
        assert score.value == 100.0
        assert score.metadata["violation_count"] == 0

    @patch("nines.iteration.self_eval.subprocess.run")
    def test_some_violations(self, mock_run: MagicMock) -> None:
        violations = [{"code": "E501"}, {"code": "F401"}, {"code": "W291"}]
        mock_run.return_value = MagicMock(stdout=json.dumps(violations), returncode=1)
        ev = LintCleanlinessEvaluator(src_dir="/fake")
        score = ev.evaluate()
        assert score.value == 94.0
        assert score.metadata["violation_count"] == 3

    @patch("nines.iteration.self_eval.subprocess.run")
    def test_many_violations_floor_zero(self, mock_run: MagicMock) -> None:
        violations = [{"code": f"E{i}"} for i in range(60)]
        mock_run.return_value = MagicMock(stdout=json.dumps(violations), returncode=1)
        ev = LintCleanlinessEvaluator(src_dir="/fake")
        score = ev.evaluate()
        assert score.value == 0.0

    @patch("nines.iteration.self_eval.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ruff", timeout=300)
        ev = LintCleanlinessEvaluator(src_dir="/fake")
        score = ev.evaluate()
        assert score.value == 100.0
        assert score.metadata["violation_count"] == 0

    @patch("nines.iteration.self_eval.subprocess.run")
    def test_subprocess_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = OSError("not found")
        ev = LintCleanlinessEvaluator(src_dir="/fake")
        score = ev.evaluate()
        assert score.value == 100.0
        assert score.metadata["violation_count"] == 0
