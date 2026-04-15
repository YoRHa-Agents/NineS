"""Tests for the cross-language import graph builder (FR-318).

Covers:
- ImportEdge / ImportGraph serialization (to_dict / from_dict round-trip)
- ImportGraph query methods: files_importing, files_imported_by, fan_in, fan_out
- Python import extraction (ast-based): absolute and relative imports
- JS/TS import extraction (regex): import from, require, dynamic import
- Go import extraction (regex): single and block imports
- Rust import extraction (regex): use crate/super/self, mod declarations
- File index construction per language
- Import resolution: absolute, relative (Python dot-prefix, JS/TS ./ ../)
- End-to-end build on a synthetic multi-language repo
- Edge cases: empty files, syntax errors, unreadable files
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from nines.analyzer.import_graph import (
    ImportEdge,
    ImportGraph,
    ImportGraphBuilder,
)

if TYPE_CHECKING:
    pass


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def builder() -> ImportGraphBuilder:
    """Provide a fresh builder instance."""
    return ImportGraphBuilder()


class _FakeFileInfo:
    """Minimal duck-typed stand-in for FileInfo."""

    def __init__(self, path: str, language: str) -> None:
        self.path = path
        self.language = language


# ------------------------------------------------------------------ #
# ImportEdge serialization                                            #
# ------------------------------------------------------------------ #

class TestImportEdge:
    """ImportEdge to_dict / from_dict round-trip."""

    def test_round_trip(self) -> None:
        edge = ImportEdge(
            source_file="pkg/main.py",
            target_file="pkg/utils.py",
            import_name="pkg.utils",
            is_relative=False,
            line_number=3,
        )
        data = edge.to_dict()
        restored = ImportEdge.from_dict(data)
        assert restored == edge

    def test_from_dict_defaults(self) -> None:
        minimal: dict[str, Any] = {
            "source_file": "a.py",
            "target_file": "b.py",
            "import_name": "b",
        }
        edge = ImportEdge.from_dict(minimal)
        assert edge.is_relative is False
        assert edge.line_number == 0


# ------------------------------------------------------------------ #
# ImportGraph serialization & query methods                           #
# ------------------------------------------------------------------ #

class TestImportGraph:
    """ImportGraph serialization and query helpers."""

    @staticmethod
    def _sample_graph() -> ImportGraph:
        return ImportGraph(
            edges=[
                ImportEdge("a.py", "b.py", "b", False, 1),
                ImportEdge("a.py", "c.py", "c", False, 2),
                ImportEdge("d.py", "b.py", "b", False, 1),
            ],
            unresolved=[("a.py", "external_lib")],
        )

    def test_round_trip(self) -> None:
        graph = self._sample_graph()
        data = graph.to_dict()
        restored = ImportGraph.from_dict(data)
        assert len(restored.edges) == 3
        assert len(restored.unresolved) == 1
        assert restored.unresolved[0] == ("a.py", "external_lib")

    def test_files_importing(self) -> None:
        graph = self._sample_graph()
        assert graph.files_importing("b.py") == ["a.py", "d.py"]
        assert graph.files_importing("c.py") == ["a.py"]
        assert graph.files_importing("nonexistent.py") == []

    def test_files_imported_by(self) -> None:
        graph = self._sample_graph()
        assert graph.files_imported_by("a.py") == ["b.py", "c.py"]
        assert graph.files_imported_by("d.py") == ["b.py"]
        assert graph.files_imported_by("nonexistent.py") == []

    def test_fan_in(self) -> None:
        graph = self._sample_graph()
        assert graph.fan_in("b.py") == 2
        assert graph.fan_in("c.py") == 1
        assert graph.fan_in("nonexistent.py") == 0

    def test_fan_out(self) -> None:
        graph = self._sample_graph()
        assert graph.fan_out("a.py") == 2
        assert graph.fan_out("d.py") == 1
        assert graph.fan_out("nonexistent.py") == 0


# ------------------------------------------------------------------ #
# Python import extraction                                            #
# ------------------------------------------------------------------ #

class TestPythonImports:
    """AST-based Python import extraction."""

    def test_absolute_import(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        py = tmp_path / "example.py"
        py.write_text("import os\nimport pkg.utils\n")
        results = builder._extract_python_imports(py)
        names = [r[0] for r in results]
        assert "os" in names
        assert "pkg.utils" in names
        assert all(r[1] is False for r in results)

    def test_from_import(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        py = tmp_path / "example.py"
        py.write_text("from pkg.utils import helper\n")
        results = builder._extract_python_imports(py)
        assert results[0][0] == "pkg.utils"
        assert results[0][1] is False

    def test_relative_import(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        py = tmp_path / "example.py"
        py.write_text("from . import sibling\nfrom ..parent import thing\n")
        results = builder._extract_python_imports(py)
        assert len(results) == 2
        assert results[0][1] is True
        assert results[1][1] is True

    def test_syntax_error_returns_empty(
        self, tmp_path: Path, builder: ImportGraphBuilder,
    ) -> None:
        py = tmp_path / "bad.py"
        py.write_text("def broken(\n")
        results = builder._extract_python_imports(py)
        assert results == []


# ------------------------------------------------------------------ #
# JS / TS import extraction                                           #
# ------------------------------------------------------------------ #

class TestJsTsImports:
    """Regex-based JS/TS import extraction."""

    def test_import_from(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        js = tmp_path / "app.js"
        js.write_text("import { foo } from './utils';\n")
        results = builder._extract_js_ts_imports(js)
        assert len(results) == 1
        assert results[0][0] == "./utils"
        assert results[0][1] is True

    def test_require(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        js = tmp_path / "app.js"
        js.write_text("const fs = require('fs');\nconst u = require('./util');\n")
        results = builder._extract_js_ts_imports(js)
        names = [r[0] for r in results]
        assert "fs" in names
        assert "./util" in names

    def test_dynamic_import(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        ts = tmp_path / "lazy.ts"
        ts.write_text("const mod = import('./heavy-module');\n")
        results = builder._extract_js_ts_imports(ts)
        assert results[0][0] == "./heavy-module"
        assert results[0][1] is True

    def test_absolute_import_not_relative(
        self, tmp_path: Path, builder: ImportGraphBuilder,
    ) -> None:
        ts = tmp_path / "app.ts"
        ts.write_text("import React from 'react';\n")
        results = builder._extract_js_ts_imports(ts)
        assert results[0][0] == "react"
        assert results[0][1] is False


# ------------------------------------------------------------------ #
# Go import extraction                                                #
# ------------------------------------------------------------------ #

class TestGoImports:
    """Regex-based Go import extraction."""

    def test_single_import(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        go = tmp_path / "main.go"
        go.write_text('package main\n\nimport "fmt"\n')
        results = builder._extract_go_imports(go)
        assert results[0][0] == "fmt"
        assert results[0][1] is False

    def test_block_import(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        go = tmp_path / "main.go"
        go.write_text('package main\n\nimport (\n\t"fmt"\n\t"os"\n)\n')
        results = builder._extract_go_imports(go)
        names = [r[0] for r in results]
        assert "fmt" in names
        assert "os" in names


# ------------------------------------------------------------------ #
# Rust import extraction                                              #
# ------------------------------------------------------------------ #

class TestRustImports:
    """Regex-based Rust import extraction."""

    def test_use_crate(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        rs = tmp_path / "main.rs"
        rs.write_text("use crate::config::Settings;\n")
        results = builder._extract_rust_imports(rs)
        assert len(results) == 1
        assert "crate::" in results[0][0]
        assert results[0][1] is False

    def test_use_super(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        rs = tmp_path / "sub.rs"
        rs.write_text("use super::parent_mod;\n")
        results = builder._extract_rust_imports(rs)
        assert results[0][1] is True

    def test_mod_declaration(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        rs = tmp_path / "lib.rs"
        rs.write_text("mod config;\nmod utils;\n")
        results = builder._extract_rust_imports(rs)
        names = [r[0] for r in results]
        assert "config" in names
        assert "utils" in names


# ------------------------------------------------------------------ #
# File index construction                                             #
# ------------------------------------------------------------------ #

class TestBuildFileIndex:
    """File index maps importable names to relative paths."""

    def test_python_index(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "utils.py").write_text("")

        files = [
            _FakeFileInfo(str(tmp_path / "pkg" / "__init__.py"), "python"),
            _FakeFileInfo(str(tmp_path / "pkg" / "utils.py"), "python"),
        ]
        index = builder._build_file_index(tmp_path, files)
        assert "pkg" in index
        assert "pkg.utils" in index

    def test_js_ts_index(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("")
        (tmp_path / "src" / "utils.ts").write_text("")

        files = [
            _FakeFileInfo(str(tmp_path / "src" / "index.ts"), "typescript"),
            _FakeFileInfo(str(tmp_path / "src" / "utils.ts"), "typescript"),
        ]
        index = builder._build_file_index(tmp_path, files)
        assert "src/index.ts" in index
        assert "src" in index  # index.ts → directory name
        assert "src/utils" in index  # without extension

    def test_go_index(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        (tmp_path / "cmd").mkdir()
        (tmp_path / "cmd" / "main.go").write_text("")

        files = [_FakeFileInfo(str(tmp_path / "cmd" / "main.go"), "go")]
        index = builder._build_file_index(tmp_path, files)
        assert "cmd" in index

    def test_rust_index(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "config.rs").write_text("")

        files = [_FakeFileInfo(str(tmp_path / "src" / "config.rs"), "rust")]
        index = builder._build_file_index(tmp_path, files)
        assert "crate::src::config" in index
        assert "config" in index


# ------------------------------------------------------------------ #
# End-to-end build                                                    #
# ------------------------------------------------------------------ #

class TestBuildEndToEnd:
    """End-to-end graph build on a synthetic Python project."""

    def test_python_project(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "core.py").write_text("import mypkg.helpers\n")
        (pkg / "helpers.py").write_text("")

        files = [
            _FakeFileInfo(str(pkg / "__init__.py"), "python"),
            _FakeFileInfo(str(pkg / "core.py"), "python"),
            _FakeFileInfo(str(pkg / "helpers.py"), "python"),
        ]
        graph = builder.build(tmp_path, files)
        assert len(graph.edges) == 1
        edge = graph.edges[0]
        assert edge.source_file == "mypkg/core.py"
        assert edge.target_file == "mypkg/helpers.py"
        assert edge.import_name == "mypkg.helpers"

    def test_unresolved_external(
        self, tmp_path: Path, builder: ImportGraphBuilder,
    ) -> None:
        (tmp_path / "app.py").write_text("import requests\n")
        files = [_FakeFileInfo(str(tmp_path / "app.py"), "python")]
        graph = builder.build(tmp_path, files)
        assert len(graph.edges) == 0
        assert ("app.py", "requests") in graph.unresolved

    def test_empty_file(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        (tmp_path / "empty.py").write_text("")
        files = [_FakeFileInfo(str(tmp_path / "empty.py"), "python")]
        graph = builder.build(tmp_path, files)
        assert len(graph.edges) == 0
        assert len(graph.unresolved) == 0

    def test_js_project(self, tmp_path: Path, builder: ImportGraphBuilder) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "index.ts").write_text("import { helper } from './utils';\n")
        (src / "utils.ts").write_text("export const helper = 1;\n")

        files = [
            _FakeFileInfo(str(src / "index.ts"), "typescript"),
            _FakeFileInfo(str(src / "utils.ts"), "typescript"),
        ]
        graph = builder.build(tmp_path, files)
        assert len(graph.edges) == 1
        assert graph.edges[0].target_file == "src/utils.ts"

    def test_unsupported_language_skipped(
        self, tmp_path: Path, builder: ImportGraphBuilder,
    ) -> None:
        (tmp_path / "data.csv").write_text("a,b,c\n")
        files = [_FakeFileInfo(str(tmp_path / "data.csv"), "csv")]
        graph = builder.build(tmp_path, files)
        assert len(graph.edges) == 0
        assert len(graph.unresolved) == 0
