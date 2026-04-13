"""``nines eval`` — run evaluation benchmarks on agent capabilities."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from nines.core.models import ExecutionResult
from nines.eval.reporters import JSONReporter, MarkdownReporter
from nines.eval.runner import EvalRunner
from nines.eval.scorers import ScorerRegistry

if TYPE_CHECKING:
    from nines.eval.models import TaskDefinition

logger = logging.getLogger(__name__)


def _default_executor(task: TaskDefinition) -> ExecutionResult:
    """Default executor."""
    return ExecutionResult(
        task_id=task.id,
        output=task.expected,
        metrics={"token_count": 0},
        success=True,
    )


@click.command("eval")
@click.option(
    "--tasks-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to a TOML task file or directory of TOML task files.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Directory to write evaluation reports to.",
)
@click.option(
    "--scorers",
    multiple=True,
    default=("exact",),
    help="Scorer names to use (can be repeated). Default: exact.",
)
@click.option(
    "--parallel",
    is_flag=True,
    default=False,
    help="Enable parallel task execution (not yet supported).",
)
@click.pass_context
def eval_cmd(
    ctx: click.Context,
    tasks_path: str,
    output_dir: str | None,
    scorers: tuple[str, ...],
    parallel: bool,
) -> None:
    """Run evaluation benchmarks on agent capabilities."""
    verbose = ctx.obj.get("verbose", False)
    output_format = ctx.obj.get("format", "text")

    runner = EvalRunner()

    tasks = runner.load_tasks(tasks_path)
    if not tasks:
        click.echo("No tasks found.", err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"Loaded {len(tasks)} task(s) from {tasks_path}")

    registry = ScorerRegistry.with_builtins()
    scorer_instances = [registry.get(name) for name in scorers]

    if parallel:
        click.echo("Warning: parallel execution is not yet supported, running sequentially.")

    results = runner.run(tasks, _default_executor, scorer_instances)

    if output_format == "json":
        reporter = JSONReporter()
        report = reporter.generate(results)
    else:
        reporter_md = MarkdownReporter()
        report = reporter_md.generate(results)

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        ext = "json" if output_format == "json" else "md"
        dest = out / f"eval_report.{ext}"
        dest.write_text(report, encoding="utf-8")
        click.echo(f"Report written to {dest}")
    else:
        click.echo(report)

    passed = sum(1 for r in results if r.success)
    click.echo(f"\n{passed}/{len(results)} tasks passed.")
