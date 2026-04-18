"""Tests for the ``nines benchmark`` CLI command."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import json
import textwrap
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nines.analyzer.keypoint import KeyPoint, KeyPointReport
from nines.cli.main import cli
from nines.core.models import AnalysisResult
from nines.eval.benchmark_gen import BenchmarkSuite
from nines.eval.mapping import KeyPointConclusion, MappingTable
from nines.eval.models import TaskDefinition
from nines.eval.multi_round import MultiRoundReport, RoundResult


def _make_sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python project for benchmark tests."""
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


def _make_key_points() -> list[KeyPoint]:
    return [
        KeyPoint(
            id="kp-test-001",
            category="compression",
            title="Test compression",
            description="Tests compression effectiveness",
            mechanism_ids=["mech-01"],
            expected_impact="positive",
            impact_magnitude=0.5,
            validation_approach="Run benchmark",
            evidence=["file.py"],
            priority=2,
        ),
        KeyPoint(
            id="kp-test-002",
            category="engineering",
            title="Code quality",
            description="Engineering observation",
            mechanism_ids=[],
            expected_impact="neutral",
            impact_magnitude=0.2,
            validation_approach="Review metrics",
            evidence=[],
            priority=4,
        ),
    ]


def _make_suite(key_points: list[KeyPoint]) -> BenchmarkSuite:
    tasks = [
        TaskDefinition(
            id=f"bench-suite1-{kp.id}-01",
            name=f"Task for {kp.title}",
            description=kp.description,
            dimension=kp.category,
            expected={"passes_threshold": True},
            metadata={"source_keypoint": kp.id, "category": kp.category},
        )
        for kp in key_points
    ]
    return BenchmarkSuite(
        id="suite1",
        name="Test Suite",
        description="Auto-generated test suite",
        tasks=tasks,
        source_keypoints=[kp.id for kp in key_points],
    )


def _make_report(suite: BenchmarkSuite) -> MultiRoundReport:
    from nines.core.models import Score
    from nines.eval.models import EvalResult

    results = [
        EvalResult(
            task_id=t.id,
            task_name=t.name,
            output=t.expected,
            scores=[Score(value=1.0, scorer_name="exact")],
            composite_score=1.0,
            success=True,
        )
        for t in suite.tasks
    ]
    rnd = RoundResult(
        round_number=1,
        results=results,
        composite_score=1.0,
        duration_ms=10.0,
    )
    return MultiRoundReport(
        suite_id=suite.id,
        rounds=[rnd, rnd, rnd],
        total_rounds=3,
        mean_composite=1.0,
        std_composite=0.0,
        min_composite=1.0,
        max_composite=1.0,
        reliability={"consistency": 1.0, "pass_at_1": 1.0},
        converged=True,
        convergence_round=3,
        total_duration_ms=30.0,
    )


def _make_mapping(
    key_points: list[KeyPoint],
    suite: BenchmarkSuite,
) -> MappingTable:
    conclusions = [
        KeyPointConclusion(
            keypoint_id=kp.id,
            keypoint_title=kp.title,
            category=kp.category,
            expected_impact=kp.expected_impact,
            observed_effectiveness="effective",
            confidence=0.9,
            mean_score=1.0,
            score_std=0.0,
            task_count=1,
            evidence_summary="Good",
            recommendation=f"Validated: adopt '{kp.title}'",
        )
        for kp in key_points
    ]
    return MappingTable(
        target=suite.name,
        conclusions=conclusions,
        effective_count=len(conclusions),
        ineffective_count=0,
        inconclusive_count=0,
        overall_effectiveness=1.0,
        lessons_learnt=["All techniques proved effective."],
    )


def _patch_benchmark_workflow(
    key_points: list[KeyPoint],
    suite: BenchmarkSuite,
    report: MultiRoundReport,
    mapping: MappingTable,
):
    """Return a context manager that patches the full benchmark workflow."""
    analysis_result = AnalysisResult(target="/tmp/test", metrics={"files_analyzed": 1})
    impact_report = MagicMock()
    kp_report = KeyPointReport(target="/tmp/test", key_points=key_points)

    pipeline_patch = patch(
        "nines.cli.commands.benchmark.AnalysisPipeline",
    )
    impact_patch = patch(
        "nines.cli.commands.benchmark.AgentImpactAnalyzer",
    )
    extractor_patch = patch(
        "nines.cli.commands.benchmark.KeyPointExtractor",
    )
    gen_patch = patch(
        "nines.cli.commands.benchmark.BenchmarkGenerator",
    )
    runner_patch = patch(
        "nines.cli.commands.benchmark.MultiRoundRunner",
    )
    mapping_patch = patch(
        "nines.cli.commands.benchmark.MappingTableGenerator",
    )

    class _PatchContext:
        def __enter__(self):
            self.p_pipeline = pipeline_patch.__enter__()
            self.p_impact = impact_patch.__enter__()
            self.p_extractor = extractor_patch.__enter__()
            self.p_gen = gen_patch.__enter__()
            self.p_runner = runner_patch.__enter__()
            self.p_mapping = mapping_patch.__enter__()

            self.p_pipeline.return_value.run.return_value = analysis_result
            self.p_impact.return_value.analyze.return_value = impact_report
            self.p_extractor.return_value.extract.return_value = kp_report
            self.p_gen.return_value.generate.return_value = suite
            self.p_runner.return_value.run.return_value = report
            self.p_mapping.return_value.generate.return_value = mapping
            return self

        def __exit__(self, *args):
            mapping_patch.__exit__(*args)
            runner_patch.__exit__(*args)
            gen_patch.__exit__(*args)
            extractor_patch.__exit__(*args)
            impact_patch.__exit__(*args)
            pipeline_patch.__exit__(*args)

    return _PatchContext()


class TestBenchmarkHelp:
    def test_benchmark_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["benchmark", "--help"])
        assert result.exit_code == 0
        assert "--target-path" in result.output
        assert "--rounds" in result.output
        assert "--convergence-threshold" in result.output
        assert "--output-dir" in result.output
        assert "--suite-id" in result.output

    def test_benchmark_requires_target_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["benchmark"])
        assert result.exit_code == 2
        assert "--target-path" in result.output


class TestBenchmarkTextOutput:
    def test_text_output_contains_report(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["benchmark", "--target-path", str(project)],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0
            assert "Benchmark Report for" in result.output
            assert f"Suite: {suite.id}" in result.output
            assert "Mean score:" in result.output

    def test_text_output_contains_mapping(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["benchmark", "--target-path", str(project)],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0
            assert "Key Point → Conclusion Mapping:" in result.output
            assert "[Effective]" in result.output
            assert "Test compression" in result.output

    def test_text_output_contains_summary(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["benchmark", "--target-path", str(project)],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0
            assert "Effective:" in result.output
            assert "Ineffective:" in result.output
            assert "Inconclusive:" in result.output
            assert "Overall effectiveness:" in result.output

    def test_text_output_contains_lessons(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["benchmark", "--target-path", str(project)],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0
            assert "Lessons Learnt:" in result.output


class TestBenchmarkJsonOutput:
    def test_json_output_is_valid(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["-f", "json", "benchmark", "--target-path", str(project)],
                obj={"verbose": False, "format": "json"},
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "suite" in data
            assert "report" in data
            assert "mapping" in data

    def test_json_contains_full_mapping_table(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["-f", "json", "benchmark", "--target-path", str(project)],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["mapping"]["effective_count"] == 2
            assert data["mapping"]["overall_effectiveness"] == 1.0
            assert len(data["mapping"]["conclusions"]) == 2
            assert len(data["mapping"]["lessons_learnt"]) > 0


class TestBenchmarkOutputDir:
    def test_writes_artifacts_to_dir(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)
        out_dir = tmp_path / "bench_output"

        with _patch_benchmark_workflow(key_points, suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "benchmark",
                    "--target-path",
                    str(project),
                    "--output-dir",
                    str(out_dir),
                ],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0

            assert (out_dir / "mapping.md").exists()
            md_content = (out_dir / "mapping.md").read_text()
            assert "Key Point" in md_content

            assert (out_dir / "suite" / "suite.toml").exists()

            assert (out_dir / "report.json").exists()
            report_data = json.loads((out_dir / "report.json").read_text())
            assert report_data["suite_id"] == suite.id
            assert report_data["total_rounds"] == 3


class TestBenchmarkOptions:
    def test_custom_rounds(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping) as ctx:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "benchmark",
                    "--target-path",
                    str(project),
                    "--rounds",
                    "5",
                ],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0
            call_kwargs = ctx.p_runner.call_args
            assert call_kwargs.kwargs.get("min_rounds") == 5

    def test_custom_suite_id(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping) as ctx:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "benchmark",
                    "--target-path",
                    str(project),
                    "--suite-id",
                    "my-suite",
                ],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0
            gen_call = ctx.p_gen.return_value.generate.call_args
            assert gen_call[0][1] == "my-suite"

    def test_verbose_mode(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)
        project = _make_sample_project(tmp_path)

        with _patch_benchmark_workflow(key_points, suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["-v", "benchmark", "--target-path", str(project)],
            )
            assert result.exit_code == 0
            assert "Starting benchmark workflow" in result.output
            assert "Extracted" in result.output


class TestBenchmarkEdgeCases:
    def test_no_key_points_exits(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        suite = _make_suite([])
        report = _make_report(suite)
        mapping = _make_mapping([], suite)

        with _patch_benchmark_workflow([], suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["benchmark", "--target-path", str(project)],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 1
            assert "No key points extracted" in result.output

    def test_no_tasks_exits(self, tmp_path: Path) -> None:
        key_points = _make_key_points()
        empty_suite = BenchmarkSuite(
            id="empty",
            name="Empty",
            description="No tasks",
            tasks=[],
            source_keypoints=[],
        )
        report = _make_report(empty_suite)
        mapping = _make_mapping(key_points, empty_suite)

        with _patch_benchmark_workflow(key_points, empty_suite, report, mapping):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["benchmark", "--target-path", str(tmp_path)],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 1
            assert "no tasks" in result.output.lower()

    def test_invalid_target_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["benchmark", "--target-path", "/nonexistent/path"],
            obj={"verbose": False, "format": "text"},
        )
        assert result.exit_code == 2


class TestBenchmarkTasksPath:
    def test_tasks_path_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["benchmark", "--help"])
        assert result.exit_code == 0
        assert "--tasks-path" in result.output

    def test_tasks_path_loads_custom_tasks(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        tasks_dir = tmp_path / "custom_tasks"
        tasks_dir.mkdir()
        (tasks_dir / "task1.toml").write_text(
            textwrap.dedent("""\
                [task]
                id = "custom-001"
                name = "Custom test"
                description = "Tests specific functionality"
                dimension = "engineering"

                [task.expected]
                passes_threshold = true

                [task.metadata]
                category = "engineering"
                priority = 1
            """),
        )
        (tasks_dir / "task2.toml").write_text(
            textwrap.dedent("""\
                [task]
                id = "custom-002"
                name = "Another test"
                description = "Tests another feature"
                dimension = "compression"

                [task.expected]
                passes_threshold = true

                [task.metadata]
                category = "compression"
                priority = 2
            """),
        )

        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)

        with (
            patch(
                "nines.cli.commands.benchmark.MultiRoundRunner",
            ) as mock_runner,
            patch(
                "nines.cli.commands.benchmark.MappingTableGenerator",
            ) as mock_mapping,
        ):
            mock_runner.return_value.run.return_value = report
            mock_mapping.return_value.generate.return_value = mapping

            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "benchmark",
                    "--target-path",
                    str(project),
                    "--tasks-path",
                    str(tasks_dir),
                ],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0, result.output
            assert "Benchmark Report for" in result.output
            mock_runner.return_value.run.assert_called_once()
            call_args = mock_runner.return_value.run.call_args
            tasks_arg = call_args[0][0]
            assert len(tasks_arg) == 2
            assert tasks_arg[0].id == "custom-001"
            assert tasks_arg[1].id == "custom-002"

    def test_tasks_path_skips_analysis(self, tmp_path: Path) -> None:
        project = _make_sample_project(tmp_path)
        tasks_dir = tmp_path / "custom_tasks"
        tasks_dir.mkdir()
        (tasks_dir / "task1.toml").write_text(
            textwrap.dedent("""\
                [task]
                id = "custom-001"
                name = "Custom test"
                description = "Tests specific functionality"
                dimension = "engineering"

                [task.expected]
                passes_threshold = true

                [task.metadata]
                category = "engineering"
                priority = 1
            """),
        )

        key_points = _make_key_points()
        suite = _make_suite(key_points)
        report = _make_report(suite)
        mapping = _make_mapping(key_points, suite)

        with (
            patch(
                "nines.cli.commands.benchmark.AnalysisPipeline",
            ) as mock_pipeline,
            patch(
                "nines.cli.commands.benchmark.AgentImpactAnalyzer",
            ) as mock_impact,
            patch(
                "nines.cli.commands.benchmark.KeyPointExtractor",
            ) as mock_extractor,
            patch(
                "nines.cli.commands.benchmark.BenchmarkGenerator",
            ) as mock_gen,
            patch(
                "nines.cli.commands.benchmark.MultiRoundRunner",
            ) as mock_runner,
            patch(
                "nines.cli.commands.benchmark.MappingTableGenerator",
            ) as mock_mapping,
        ):
            mock_runner.return_value.run.return_value = report
            mock_mapping.return_value.generate.return_value = mapping

            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "benchmark",
                    "--target-path",
                    str(project),
                    "--tasks-path",
                    str(tasks_dir),
                ],
                obj={"verbose": False, "format": "text"},
            )
            assert result.exit_code == 0, result.output
            mock_pipeline.assert_not_called()
            mock_pipeline.return_value.run.assert_not_called()
            mock_impact.assert_not_called()
            mock_extractor.assert_not_called()
            mock_gen.assert_not_called()

    def test_tasks_path_invalid_dir(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "benchmark",
                "--target-path",
                ".",
                "--tasks-path",
                "/nonexistent/custom_tasks",
            ],
            obj={"verbose": False, "format": "text"},
        )
        assert result.exit_code == 2


class TestBenchmarkDefaultExecutor:
    def test_passthrough_executor_returns_expected(self) -> None:
        from nines.cli.commands.benchmark import _passthrough_executor

        task = TaskDefinition(
            id="test-01",
            name="Test",
            expected={"key": "value"},
        )
        result = _passthrough_executor(task)
        assert result.task_id == "test-01"
        assert result.output == {"key": "value"}
        assert result.success is True


class TestAnalysisExecutor:
    def test_analysis_executor_compression(self) -> None:
        from nines.cli.commands.benchmark import _analysis_executor

        task = TaskDefinition(
            id="test-01",
            name="Test",
            dimension="compression",
            input_config={"target_reduction": 0.3},
            expected={"max_ratio": 0.7, "min_reduction_pct": 30},
        )
        result = _analysis_executor(task)
        assert result.task_id == "test-01"
        assert result.success is True
        assert "max_ratio" in result.output

    def test_analysis_executor_engineering(self) -> None:
        from nines.cli.commands.benchmark import _analysis_executor

        task = TaskDefinition(
            id="test-02",
            name="Test",
            dimension="engineering",
            expected={"passes_threshold": True},
        )
        result = _analysis_executor(task)
        assert result.output == {"passes_threshold": True}

    def test_analysis_executor_context_management(self) -> None:
        from nines.cli.commands.benchmark import _analysis_executor

        task = TaskDefinition(
            id="test-03",
            name="Test",
            dimension="context_management",
            input_config={"interaction_count": 5},
            expected={"max_overhead_tokens": 500, "max_overhead_pct": 50},
        )
        result = _analysis_executor(task)
        assert result.task_id == "test-03"
        assert result.success is True
        assert "max_overhead_tokens" in result.output
        assert "max_overhead_pct" in result.output

    def test_analysis_executor_behavioral_shaping(self) -> None:
        from nines.cli.commands.benchmark import _analysis_executor

        task = TaskDefinition(
            id="test-04",
            name="Test",
            dimension="behavioral_shaping",
            expected={},
        )
        result = _analysis_executor(task)
        assert result.output == {"compliance": True}
        assert result.success is True

    def test_analysis_executor_semantic_preservation(self) -> None:
        from nines.cli.commands.benchmark import _analysis_executor

        task = TaskDefinition(
            id="test-05",
            name="Test",
            dimension="semantic_preservation",
            expected={"min_similarity": 0.85},
        )
        result = _analysis_executor(task)
        assert result.output == {"min_similarity": 0.75}
        assert result.success is False

    def test_analysis_executor_cross_platform(self) -> None:
        from nines.cli.commands.benchmark import _analysis_executor

        task = TaskDefinition(
            id="test-06",
            name="Test",
            dimension="cross_platform",
            expected={},
        )
        result = _analysis_executor(task)
        assert result.output == {"match": True}
        assert result.success is True


class TestFormatHelpers:
    def test_format_text_report(self) -> None:
        from nines.cli.commands.benchmark import _format_text_report

        kps = _make_key_points()
        suite = _make_suite(kps)
        report = _make_report(suite)
        mapping = _make_mapping(kps, suite)

        text = _format_text_report("/tmp/repo", suite, report, mapping)
        assert "Benchmark Report for /tmp/repo" in text
        assert "Suite: suite1" in text
        assert "Rounds: 3" in text
        assert "converged: True" in text
        assert "Mean score:" in text
        assert "Effective:" in text
        assert "Lessons Learnt:" in text

    def test_format_json_report(self) -> None:
        from nines.cli.commands.benchmark import _format_json_report

        kps = _make_key_points()
        suite = _make_suite(kps)
        report = _make_report(suite)
        mapping = _make_mapping(kps, suite)

        raw = _format_json_report("/tmp/repo", suite, report, mapping)
        data = json.loads(raw)
        assert data["target_path"] == "/tmp/repo"
        assert "suite" in data
        assert "report" in data
        assert "mapping" in data
