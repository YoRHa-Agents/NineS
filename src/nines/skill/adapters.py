"""Skill adapters for emitting runtime-specific files.

Defines the :class:`SkillAdapter` protocol and two concrete implementations:
:class:`CursorAdapter` (Cursor SKILL.md + command workflows) and
:class:`ClaudeAdapter` (Claude Code slash commands + CLAUDE.md section).

Covers: FR-513 (Cursor adapter), FR-514 (Claude adapter), CON-09 (Protocol).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from nines.skill.manifest import SkillManifest


@dataclass(frozen=True)
class EmittedFile:
    """A single file produced by an adapter."""

    relative_path: str
    content: str
    description: str


@runtime_checkable
class SkillAdapter(Protocol):
    """Protocol for runtime-specific skill file emitters."""

    @property
    def runtime_name(self) -> str:
        """Short identifier for the target runtime (e.g. ``'cursor'``)."""
        ...

    def emit(self, manifest: SkillManifest) -> list[EmittedFile]:
        """Generate all files needed by this runtime."""
        ...


class CursorAdapter:
    """Generates ``.cursor/skills/nines/`` files including SKILL.md.

    Covers: FR-513.
    """

    RUNTIME_NAME = "cursor"
    INSTALL_DIR = ".cursor/skills/nines"

    @property
    def runtime_name(self) -> str:
        return self.RUNTIME_NAME

    def emit(self, manifest: SkillManifest) -> list[EmittedFile]:
        """Generate Cursor skill files from *manifest*."""
        files: list[EmittedFile] = [self._emit_skill_md(manifest)]
        for cmd in manifest.commands:
            files.append(self._emit_command(manifest, cmd.name))
        return files

    def _emit_skill_md(self, manifest: SkillManifest) -> EmittedFile:
        lines = [
            f"# {manifest.name.upper()} — {manifest.description}",
            "",
            "## Available Commands",
            "",
            "| Command | Description |",
            "|---------|-------------|",
        ]
        for cmd in manifest.commands:
            lines.append(f"| `{cmd.name}` | {cmd.description} |")
        lines += [
            "",
            "## Prerequisites",
            "",
            f"The `{manifest.cli_binary}` CLI binary must be on `$PATH`.",
            f"All commands delegate to `{manifest.cli_binary} <subcommand>` via the Shell tool.",
        ]
        return EmittedFile(
            relative_path="SKILL.md",
            content="\n".join(lines) + "\n",
            description="Main skill entry point",
        )

    def _emit_command(self, manifest: SkillManifest, command_name: str) -> EmittedFile:
        short = command_name.removeprefix("nines-")
        content = (
            f"# {command_name}\n\n"
            f"Invoke via: `{manifest.cli_binary} {short} {{{{NINES_ARGS}}}}`\n"
        )
        return EmittedFile(
            relative_path=f"commands/{short}.md",
            content=content,
            description=f"{command_name} command workflow",
        )


class ClaudeAdapter:
    """Generates ``.claude/commands/nines/`` files and CLAUDE.md section.

    Covers: FR-514.
    """

    RUNTIME_NAME = "claude"
    INSTALL_DIR = ".claude/commands/nines"
    CLAUDE_MD_START = "<!-- nines:start -->"
    CLAUDE_MD_END = "<!-- nines:end -->"

    @property
    def runtime_name(self) -> str:
        return self.RUNTIME_NAME

    def emit(self, manifest: SkillManifest) -> list[EmittedFile]:
        """Generate Claude Code command files from *manifest*."""
        files: list[EmittedFile] = []
        for cmd in manifest.commands:
            files.append(self._emit_command(manifest, cmd))
        files.append(self._emit_claude_md_section(manifest))
        return files

    def _emit_command(self, manifest: SkillManifest, cmd: object) -> EmittedFile:
        from nines.skill.manifest import CommandDef

        assert isinstance(cmd, CommandDef)
        short = cmd.name.removeprefix("nines-")
        lines = [
            "---",
            f"name: nines:{short}",
            f"description: {cmd.description}",
            f'argument-hint: "{cmd.argument_hint}"',
            "allowed-tools:",
            "  - Bash",
            "  - Read",
            "  - Write",
            "  - Grep",
            "  - Glob",
            "  - Task",
            "---",
            "",
            f"Execute `{manifest.cli_binary} {short} $ARGUMENTS`.",
        ]
        return EmittedFile(
            relative_path=f"{short}.md",
            content="\n".join(lines) + "\n",
            description=f"nines:{short} slash command",
        )

    def _emit_claude_md_section(self, manifest: SkillManifest) -> EmittedFile:
        lines = [
            f"{self.CLAUDE_MD_START}",
            "## NineS Agent Toolflow",
            "",
            "### Available Commands",
        ]
        for cmd in manifest.commands:
            short = cmd.name.removeprefix("nines-")
            lines.append(f"- `/nines:{short}` — {cmd.description}")
        lines += [
            "",
            "### Configuration",
            "NineS configuration: `nines.toml` (project root) "
            "or `~/.config/nines/config.toml` (global).",
            f"{self.CLAUDE_MD_END}",
        ]
        return EmittedFile(
            relative_path="__CLAUDE_MD_SECTION__",
            content="\n".join(lines) + "\n",
            description="Content to append to CLAUDE.md",
        )
