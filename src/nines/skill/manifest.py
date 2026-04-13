"""Skill manifest definition and TOML generation.

The :class:`SkillManifest` is the single source of truth describing a NineS
skill installation.  The :meth:`generate` helper serialises the manifest to
TOML so that adapters and installers can emit it to disk.

Covers: FR-515 (skill manifest).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import tomli_w

from nines import __version__


@dataclass
class CommandDef:
    """A single command exposed by the skill."""

    name: str
    description: str
    argument_hint: str
    capability: str


def _default_commands() -> list[CommandDef]:
    """Built-in NineS command definitions."""
    return [
        CommandDef(
            name="nines-eval",
            description="Run evaluation benchmarks on agent capabilities.",
            argument_hint=(
                "<task-or-suite> [--scorer TYPE] [--format FORMAT] [--sandbox] [--seed N]"
            ),
            capability="eval",
        ),
        CommandDef(
            name="nines-collect",
            description="Search and collect information from configured sources.",
            argument_hint="<source> <query> [--incremental] [--store PATH] [--limit N]",
            capability="collect",
        ),
        CommandDef(
            name="nines-analyze",
            description="Analyze and decompose collected knowledge into structured units.",
            argument_hint="<target> [--depth LEVEL] [--decompose] [--index] [--output FORMAT]",
            capability="analyze",
        ),
        CommandDef(
            name="nines-self-eval",
            description="Run self-evaluation across all capability dimensions.",
            argument_hint="[--dimensions DIM,...] [--baseline VERSION] [--compare] [--report]",
            capability="self-eval",
        ),
        CommandDef(
            name="nines-iterate",
            description="Execute a self-improvement iteration cycle.",
            argument_hint="[--max-rounds N] [--convergence-threshold F] [--dry-run]",
            capability="iterate",
        ),
        CommandDef(
            name="nines-install",
            description="Install or uninstall NineS as an agent skill.",
            argument_hint="--target <cursor|claude|all> [--uninstall] [--global]",
            capability="install",
        ),
        CommandDef(
            name="nines-update",
            description="Check for and install NineS updates, refresh skill files.",
            argument_hint="[--check] [--skip-skills] [--target <cursor|claude|all>] [--global]",
            capability="update",
        ),
    ]


@dataclass
class SkillManifest:
    """Canonical skill definition used by all adapters.

    Attributes are intentionally kept simple so that tests and downstream
    code can construct instances trivially.
    """

    name: str = "nines"
    version: str = __version__
    description: str = (
        "Self-iterating agent toolflow for evaluation, "
        "information collection, and knowledge analysis."
    )
    author: str = "YoRHa-Agents"
    license: str = "MIT"
    homepage: str = "https://github.com/YoRHa-Agents/NineS"
    manifest_version: int = 1
    capabilities: list[str] = field(
        default_factory=lambda: [
            "eval",
            "collect",
            "analyze",
            "self-eval",
            "iterate",
            "install",
            "update",
        ]
    )
    commands: list[CommandDef] = field(default_factory=_default_commands)
    python_requires: str = ">=3.12"
    cli_binary: str = "nines"

    def to_dict(self) -> dict[str, Any]:
        """Return the manifest as a plain dict suitable for serialisation."""
        return {
            "manifest": {
                "name": self.name,
                "version": self.version,
                "description": self.description,
                "author": self.author,
                "license": self.license,
                "homepage": self.homepage,
                "manifest_version": self.manifest_version,
            },
            "capabilities": self.capabilities,
            "commands": {
                cmd.name: {
                    "description": cmd.description,
                    "argument_hint": cmd.argument_hint,
                    "capability": cmd.capability,
                }
                for cmd in self.commands
            },
            "dependencies": {
                "python": self.python_requires,
                "package": self.name,
                "cli_binary": self.cli_binary,
            },
        }

    def generate(self) -> str:
        """Serialise the manifest to a TOML string."""
        return tomli_w.dumps(self.to_dict())
