"""Tests for the multi-language project scanner (FR-317)."""

from __future__ import annotations

from nines.analyzer.scanner import (
    FileInfo,
    ProjectScanner,
    ScanResult,
)


class TestFileInfo:
    def test_round_trip(self):
        fi = FileInfo(
            path="/tmp/a.py",
            language="python",
            category="code",
            line_count=50,
            size_bytes=1200,
        )
        d = fi.to_dict()
        restored = FileInfo.from_dict(d)
        assert restored.path == fi.path
        assert restored.language == "python"
        assert restored.category == "code"

    def test_defaults(self):
        fi = FileInfo(path="x", language="", category="config")
        assert fi.line_count == 0
        assert fi.size_bytes == 0


class TestScanResult:
    def test_round_trip(self):
        result = ScanResult(
            project_root="/tmp/proj",
            project_name="proj",
            description="A test project",
            files=[FileInfo(path="/tmp/proj/a.py", language="python", category="code")],
            languages=["python"],
            total_files=1,
            total_lines=50,
            language_breakdown={"python": 1},
            category_breakdown={"code": 1},
        )
        d = result.to_dict()
        restored = ScanResult.from_dict(d)
        assert restored.project_name == "proj"
        assert len(restored.files) == 1
        assert restored.languages == ["python"]


class TestProjectScanner:
    def test_scan_simple_project(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "config.yaml").write_text("key: value\n")
        (tmp_path / "README.md").write_text("# Project\n")

        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)

        assert result.total_files == 3
        assert "python" in result.languages
        assert "yaml" in result.languages
        assert result.category_breakdown.get("code", 0) >= 1
        assert result.category_breakdown.get("config", 0) >= 1
        assert result.category_breakdown.get("docs", 0) >= 1

    def test_scan_skips_hidden_dirs(self, tmp_path):
        hidden = tmp_path / ".git"
        hidden.mkdir()
        (hidden / "config").write_text("git stuff\n")
        (tmp_path / "main.py").write_text("x = 1\n")

        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)

        assert result.total_files == 1
        assert all(".git" not in fi.path for fi in result.files)

    def test_scan_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}\n")
        (tmp_path / "app.ts").write_text("const x = 1;\n")

        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)

        assert result.total_files == 1

    def test_language_detection(self, tmp_path):
        (tmp_path / "app.ts").write_text("const x = 1;\n")
        (tmp_path / "lib.rs").write_text("fn main() {}\n")
        (tmp_path / "main.go").write_text("package main\n")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")

        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)

        langs = {fi.language for fi in result.files}
        assert "typescript" in langs
        assert "rust" in langs
        assert "go" in langs
        assert "dockerfile" in langs

    def test_category_detection(self, tmp_path):
        (tmp_path / "main.py").write_text("x=1\n")
        (tmp_path / "config.toml").write_text("[tool]\n")
        (tmp_path / "README.md").write_text("# Hi\n")
        (tmp_path / "schema.sql").write_text("CREATE TABLE t(id INT);\n")
        (tmp_path / "deploy.sh").write_text("#!/bin/bash\n")
        (tmp_path / "index.html").write_text("<html></html>\n")

        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)

        categories = {fi.category for fi in result.files}
        assert "code" in categories
        assert "config" in categories
        assert "docs" in categories
        assert "data" in categories
        assert "script" in categories
        assert "markup" in categories

    def test_framework_detection(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "myapp"\ndescription = "test"\n'
            '[project.dependencies]\nfastapi = "*"\npydantic = "*"\n'
        )
        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)
        assert "fastapi" in result.frameworks
        assert "pydantic" in result.frameworks

    def test_project_info_extraction(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "cool-project"\ndescription = "A cool project"\n'
        )
        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)
        assert result.project_name == "cool-project"
        assert result.description == "A cool project"

    def test_scan_empty_dir(self, tmp_path):
        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)
        assert result.total_files == 0
        assert result.languages == []

    def test_scan_nonexistent(self, tmp_path):
        scanner = ProjectScanner()
        result = scanner.scan(tmp_path / "nonexistent")
        assert result.total_files == 0

    def test_line_count(self, tmp_path):
        (tmp_path / "multi.py").write_text("a\nb\nc\nd\ne\n")
        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)
        assert result.total_lines == 5

    def test_custom_skip_dirs(self, tmp_path):
        custom = tmp_path / "vendor"
        custom.mkdir()
        (custom / "dep.py").write_text("x=1\n")
        (tmp_path / "main.py").write_text("y=2\n")

        scanner = ProjectScanner(skip_dirs=frozenset({"vendor"}))
        result = scanner.scan(tmp_path)
        assert result.total_files == 1

    def test_package_json_detection(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"name": "my-app", "description": "Web app", "dependencies": {"react": "^18.0.0"}}'
        )
        scanner = ProjectScanner()
        result = scanner.scan(tmp_path)
        assert result.project_name == "my-app"
        assert "react" in result.frameworks
