"""Integration tests for enhanced analysis pipeline with agent impact + keypoints."""

from __future__ import annotations

from pathlib import Path

from nines.analyzer.pipeline import AnalysisPipeline


def _create_python_project(base: Path) -> None:
    """Create a minimal Python project."""
    src = base / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text(
        '"""Main module."""\n\n\ndef hello() -> str:\n    return "world"\n'
    )
    (src / "utils.py").write_text(
        '"""Utility functions."""\n\n\ndef add(a: int, b: int) -> int:\n    return a + b\n'
    )


def _create_agent_project(base: Path) -> None:
    """Create a Python project with agent-facing artifacts."""
    _create_python_project(base)
    (base / "CLAUDE.md").write_text(
        "# Rules\n\nAlways be concise.\nNever use filler words.\n"
        "Compress all output.\nUse token-efficient formatting.\n"
    )
    (base / ".cursorrules").write_text(
        "compress output\nuse short variable names\nsafety: never delete files\n"
    )


class TestEnhancedAnalysisPipeline:
    """Integration tests for AnalysisPipeline with agent_impact and keypoints flags."""

    def test_default_includes_agent_impact(self, tmp_path: Path) -> None:
        _create_python_project(tmp_path)
        pipeline = AnalysisPipeline()
        result = pipeline.run(tmp_path)

        assert "agent_impact" in result.metrics
        assert "key_points" in result.metrics
        assert result.metrics["files_analyzed"] >= 2
        assert "total_files_scanned" in result.metrics

    def test_opt_out_no_agent_impact(self, tmp_path: Path) -> None:
        _create_python_project(tmp_path)
        pipeline = AnalysisPipeline()
        result = pipeline.run(tmp_path, agent_impact=False)

        assert "agent_impact" not in result.metrics
        assert "key_points" not in result.metrics
        assert result.metrics["files_analyzed"] >= 2

    def test_agent_impact_flag(self, tmp_path: Path) -> None:
        _create_agent_project(tmp_path)
        pipeline = AnalysisPipeline()
        result = pipeline.run(tmp_path, agent_impact=True)

        assert "agent_impact" in result.metrics
        ai = result.metrics["agent_impact"]
        assert isinstance(ai, dict)
        assert "mechanisms" in ai
        assert "economics" in ai
        assert len(ai.get("agent_facing_artifacts", [])) >= 1

    def test_keypoints_flag(self, tmp_path: Path) -> None:
        _create_agent_project(tmp_path)
        pipeline = AnalysisPipeline()
        result = pipeline.run(tmp_path, keypoints=True)

        assert "key_points" in result.metrics
        kp_data = result.metrics["key_points"]
        assert isinstance(kp_data, dict)
        assert "key_points" in kp_data

    def test_keypoints_implies_agent_impact(self, tmp_path: Path) -> None:
        _create_agent_project(tmp_path)
        pipeline = AnalysisPipeline()
        result = pipeline.run(tmp_path, keypoints=True)

        assert "agent_impact" in result.metrics, "keypoints=True should enable agent_impact"
        assert "key_points" in result.metrics

    def test_no_agent_artifacts(self, tmp_path: Path) -> None:
        _create_python_project(tmp_path)
        pipeline = AnalysisPipeline()
        result = pipeline.run(tmp_path, agent_impact=True)

        ai = result.metrics.get("agent_impact", {})
        assert len(ai.get("mechanisms", [])) == 0
        assert len(ai.get("agent_facing_artifacts", [])) == 0

    def test_findings_merge(self, tmp_path: Path) -> None:
        _create_agent_project(tmp_path)
        pipeline = AnalysisPipeline()

        result_base = pipeline.run(tmp_path)
        base_count = len(result_base.findings)

        result_ai = pipeline.run(tmp_path, agent_impact=True)
        assert len(result_ai.findings) >= base_count

    def test_metrics_structure(self, tmp_path: Path) -> None:
        _create_agent_project(tmp_path)
        pipeline = AnalysisPipeline()
        result = pipeline.run(tmp_path, agent_impact=True, keypoints=True)

        assert "files_analyzed" in result.metrics
        assert "total_lines" in result.metrics
        assert "agent_impact" in result.metrics
        assert "key_points" in result.metrics
        assert isinstance(result.metrics["agent_impact"], dict)
        assert isinstance(result.metrics["key_points"], dict)

    def test_single_python_file(self, tmp_path: Path) -> None:
        py_file = tmp_path / "script.py"
        py_file.write_text('"""Script."""\n\nx = 1\n')
        pipeline = AnalysisPipeline()
        result = pipeline.run(py_file)

        assert result.metrics["files_analyzed"] == 1
        assert "agent_impact" in result.metrics

    def test_single_python_file_opt_out(self, tmp_path: Path) -> None:
        py_file = tmp_path / "script.py"
        py_file.write_text('"""Script."""\n\nx = 1\n')
        pipeline = AnalysisPipeline()
        result = pipeline.run(py_file, agent_impact=False)

        assert result.metrics["files_analyzed"] == 1
        assert "agent_impact" not in result.metrics
