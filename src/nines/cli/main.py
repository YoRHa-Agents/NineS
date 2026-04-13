"""Root CLI group for the nines command."""

import click

from nines import __version__
from nines.cli.commands import (
    analyze_cmd,
    benchmark_cmd,
    collect_cmd,
    eval_cmd,
    install_cmd,
    iterate_cmd,
    self_eval_cmd,
    update_cmd,
)


@click.group()
@click.version_option(version=__version__, prog_name="nines")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=False),
    default=None,
    help="Path to nines.toml config file.",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable verbose output.")
@click.option("-q", "--quiet", is_flag=True, default=False, help="Suppress non-error output.")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Write primary output to file instead of stdout.",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format.",
)
@click.option("--no-color", is_flag=True, default=False, help="Disable colored output.")
@click.pass_context
def cli(
    ctx: click.Context,
    config: str | None,
    verbose: bool,
    quiet: bool,
    output: str | None,
    output_format: str,
    no_color: bool,
) -> None:
    """NineS — Multi-vertex evaluation, collection, analysis, and self-iteration system."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["output"] = output
    ctx.obj["format"] = output_format
    ctx.obj["no_color"] = no_color


cli.add_command(eval_cmd, "eval")
cli.add_command(collect_cmd, "collect")
cli.add_command(analyze_cmd, "analyze")
cli.add_command(benchmark_cmd, "benchmark")
cli.add_command(self_eval_cmd, "self-eval")
cli.add_command(iterate_cmd, "iterate")
cli.add_command(install_cmd, "install")
cli.add_command(update_cmd, "update")
