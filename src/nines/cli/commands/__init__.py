"""CLI subcommands for each NineS vertex."""

from nines.cli.commands.analyze import analyze_cmd
from nines.cli.commands.benchmark import benchmark_cmd
from nines.cli.commands.collect import collect_cmd
from nines.cli.commands.eval import eval_cmd
from nines.cli.commands.install import install_cmd
from nines.cli.commands.iterate import iterate_cmd
from nines.cli.commands.self_eval import self_eval_cmd
from nines.cli.commands.update import update_cmd

__all__ = [
    "analyze_cmd",
    "benchmark_cmd",
    "collect_cmd",
    "eval_cmd",
    "install_cmd",
    "iterate_cmd",
    "self_eval_cmd",
    "update_cmd",
]
