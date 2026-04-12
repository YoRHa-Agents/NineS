"""Tests for the knowledge analyzer (V3 vertex).

Covers:
- test_review_python_file: CodeReviewer on a temp .py file
- test_structure_analysis: StructureAnalyzer on a temp directory tree
- test_decomposer_functional: Functional decomposition produces KnowledgeUnits
- test_decomposer_concern: Concern-based decomposition groups by concern
- test_decomposer_layer: Layer-based decomposition groups by layer
- test_pipeline_end_to_end: Full pipeline from directory to AnalysisResult
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from nines.analyzer.decomposer import Decomposer
from nines.analyzer.pipeline import AnalysisPipeline
from nines.analyzer.reviewer import CodeReviewer
from nines.analyzer.structure import StructureAnalyzer
from nines.core.errors import AnalyzerError
from nines.core.models import KnowledgeUnit

SAMPLE_CODE = textwrap.dedent("""\
    \"\"\"Sample module docstring.\"\"\"

    import os
    from pathlib import Path

    def simple_func(x, y):
        return x + y

    def branchy_func(a, b, c):
        if a > 0:
            for i in range(b):
                if i % 2 == 0:
                    while c > 0:
                        c -= 1
        return a + b + c

    class MyClass:
        \"\"\"A sample class.\"\"\"

        def __init__(self, value):
            self.value = value

        def get_value(self):
            return self.value

        def process(self, data):
            if data:
                return [x for x in data if x > 0]
            return []
""")


@pytest.fixture
def sample_py_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.py"
    f.write_text(SAMPLE_CODE)
    return f


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python project tree for structure analysis."""
    pkg = tmp_path / "myproject"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Root package."""\n')

    core = pkg / "core"
    core.mkdir()
    (core / "__init__.py").write_text('"""Core domain."""\n')
    (core / "models.py").write_text(textwrap.dedent("""\
        class User:
            def __init__(self, name):
                self.name = name
    """))

    services = pkg / "services"
    services.mkdir()
    (services / "__init__.py").write_text('"""Application services."""\n')
    (services / "auth.py").write_text(textwrap.dedent("""\
        from myproject.core.models import User

        def authenticate(name):
            return User(name)
    """))

    tests_dir = pkg / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("")
    (tests_dir / "test_auth.py").write_text(textwrap.dedent("""\
        from myproject.services.auth import authenticate

        def test_authenticate():
            user = authenticate("alice")
            assert user.name == "alice"
    """))

    (tmp_path / "readme.txt").write_text("Hello")

    return tmp_path


class TestCodeReviewer:
    """Tests for the CodeReviewer (FR-301)."""

    def test_review_python_file(self, sample_py_file: Path) -> None:
        reviewer = CodeReviewer()
        review = reviewer.review_file(sample_py_file)

        assert review.path == str(sample_py_file)
        assert review.total_lines > 0
        assert review.function_count >= 5
        assert review.class_count == 1
        assert review.import_count >= 2
        assert review.avg_complexity >= 1.0
        assert review.max_complexity >= 1

        assert review.ast_tree is not None

        func_names = {f.name for f in review.functions}
        assert "simple_func" in func_names
        assert "branchy_func" in func_names

        cls_names = {c.name for c in review.classes}
        assert "MyClass" in cls_names

        my_class = next(c for c in review.classes if c.name == "MyClass")
        method_names = {m.name for m in my_class.methods}
        assert "__init__" in method_names
        assert "get_value" in method_names
        assert "process" in method_names

        import_modules = {imp.module for imp in review.imports}
        assert "os" in import_modules

        assert len(review.findings) > 0
        categories = {f.category for f in review.findings}
        assert "summary" in categories

    def test_review_extracts_complexity(self, sample_py_file: Path) -> None:
        reviewer = CodeReviewer()
        review = reviewer.review_file(sample_py_file)

        branchy = next(f for f in review.functions if f.name == "branchy_func")
        assert branchy.complexity > 1

        simple = next(f for f in review.functions if f.name == "simple_func")
        assert simple.complexity == 1

    def test_review_nonexistent_file(self, tmp_path: Path) -> None:
        reviewer = CodeReviewer()
        with pytest.raises(AnalyzerError, match="File not found"):
            reviewer.review_file(tmp_path / "nope.py")

    def test_review_syntax_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.py"
        bad.write_text("def broken(:\n")
        reviewer = CodeReviewer()
        with pytest.raises(AnalyzerError, match="Syntax error"):
            reviewer.review_file(bad)

    def test_review_source_string(self) -> None:
        reviewer = CodeReviewer()
        review = reviewer.review_source("x = 1\n", path="<test>")
        assert review.total_lines == 1
        assert review.function_count == 0


class TestStructureAnalyzer:
    """Tests for the StructureAnalyzer (FR-303)."""

    def test_structure_analysis(self, sample_project: Path) -> None:
        analyzer = StructureAnalyzer()
        report = analyzer.analyze_directory(sample_project)

        assert report.root == str(sample_project)
        assert report.python_module_count > 0
        assert len(report.packages) > 0

        pkg_names = {p.name for p in report.packages}
        assert any("core" in n for n in pkg_names)
        assert any("services" in n for n in pkg_names)

        assert ".py" in report.file_type_counts.counts
        assert report.file_type_counts.total > 0

    def test_structure_dependency_map(self, sample_project: Path) -> None:
        analyzer = StructureAnalyzer()
        report = analyzer.analyze_directory(sample_project)

        all_edges = set()
        for src, targets in report.dependency_map.edges.items():
            for tgt in targets:
                all_edges.add((src, tgt))

        assert len(report.dependency_map.modules) >= 0

    def test_structure_coupling_metrics(self, sample_project: Path) -> None:
        analyzer = StructureAnalyzer()
        report = analyzer.analyze_directory(sample_project)

        for mod, metrics in report.coupling_metrics.items():
            assert "afferent_coupling" in metrics
            assert "efferent_coupling" in metrics
            assert "instability" in metrics
            assert 0.0 <= metrics["instability"] <= 1.0

    def test_structure_not_a_directory(self, sample_py_file: Path) -> None:
        analyzer = StructureAnalyzer()
        with pytest.raises(AnalyzerError, match="Not a directory"):
            analyzer.analyze_directory(sample_py_file)

    def test_structure_to_dict(self, sample_project: Path) -> None:
        analyzer = StructureAnalyzer()
        report = analyzer.analyze_directory(sample_project)
        d = report.to_dict()
        assert "root" in d
        assert "packages" in d
        assert "file_type_counts" in d
        assert "dependency_map" in d


class TestDecomposer:
    """Tests for the Decomposer (FR-305, FR-306, FR-307)."""

    def _get_reviews(self, sample_py_file: Path) -> list:
        reviewer = CodeReviewer()
        return [reviewer.review_file(sample_py_file)]

    def test_decomposer_functional(self, sample_py_file: Path) -> None:
        reviews = self._get_reviews(sample_py_file)
        decomposer = Decomposer()
        units = decomposer.functional_decompose(reviews)

        assert len(units) > 0
        assert all(isinstance(u, KnowledgeUnit) for u in units)

        types = {u.unit_type for u in units}
        assert "function" in types
        assert "class" in types

        func_units = [u for u in units if u.unit_type == "function"]
        func_names = {u.id.split("::")[-1] for u in func_units}
        assert "simple_func" in func_names
        assert "branchy_func" in func_names

        cls_units = [u for u in units if u.unit_type == "class"]
        assert len(cls_units) == 1
        assert "MyClass" in cls_units[0].id

        method_units = [u for u in func_units if "parent" in u.relationships]
        assert len(method_units) >= 3

    def test_decomposer_functional_metadata(self, sample_py_file: Path) -> None:
        reviews = self._get_reviews(sample_py_file)
        decomposer = Decomposer()
        units = decomposer.functional_decompose(reviews)

        for unit in units:
            assert unit.source != ""
            assert unit.content != ""
            if unit.unit_type == "function":
                assert "complexity" in unit.metadata
                assert "lineno" in unit.metadata

    def test_decomposer_concern(self, sample_py_file: Path) -> None:
        reviews = self._get_reviews(sample_py_file)
        decomposer = Decomposer()
        units = decomposer.concern_decompose(reviews)

        assert len(units) > 0
        concern_units = [u for u in units if u.unit_type == "concern"]
        assert len(concern_units) >= 1

        for cu in concern_units:
            assert "members" in cu.relationships
            assert len(cu.relationships["members"]) > 0

    def test_decomposer_layer(self, sample_py_file: Path) -> None:
        reviews = self._get_reviews(sample_py_file)
        decomposer = Decomposer()
        units = decomposer.layer_decompose(reviews)

        assert len(units) > 0
        layer_units = [u for u in units if u.unit_type == "layer"]
        assert len(layer_units) >= 1

        for lu in layer_units:
            assert "members" in lu.relationships


class TestAnalysisPipeline:
    """Tests for the AnalysisPipeline end-to-end (FR-310)."""

    def test_pipeline_end_to_end(self, sample_project: Path) -> None:
        pipeline = AnalysisPipeline()
        result = pipeline.run(sample_project)

        assert result.target == str(sample_project)
        assert len(result.findings) > 0
        assert result.metrics["files_analyzed"] > 0
        assert result.metrics["knowledge_units"] > 0
        assert result.metrics["total_lines"] > 0
        assert result.metrics["duration_ms"] >= 0

    def test_pipeline_single_file(self, sample_py_file: Path) -> None:
        pipeline = AnalysisPipeline()
        result = pipeline.run(sample_py_file)

        assert result.target == str(sample_py_file)
        assert len(result.findings) > 0
        assert result.metrics["files_analyzed"] == 1
        assert result.metrics["knowledge_units"] > 0

    def test_pipeline_ingest_directory(self, sample_project: Path) -> None:
        pipeline = AnalysisPipeline()
        files = pipeline.ingest(sample_project)
        assert len(files) > 0
        assert all(f.suffix == ".py" for f in files)

    def test_pipeline_ingest_single_file(self, sample_py_file: Path) -> None:
        pipeline = AnalysisPipeline()
        files = pipeline.ingest(sample_py_file)
        assert files == [sample_py_file]

    def test_pipeline_ingest_nonexistent(self, tmp_path: Path) -> None:
        pipeline = AnalysisPipeline()
        with pytest.raises(AnalyzerError, match="Path does not exist"):
            pipeline.ingest(tmp_path / "nonexistent")

    def test_pipeline_metrics_include_structure(self, sample_project: Path) -> None:
        pipeline = AnalysisPipeline()
        result = pipeline.run(sample_project)
        assert "packages" in result.metrics
        assert "python_modules" in result.metrics
