"""Skill adapters for emitting runtime-specific files.

Defines the :class:`SkillAdapter` protocol and four concrete implementations:
:class:`CursorAdapter` (Cursor SKILL.md + command workflows),
:class:`ClaudeAdapter` (Claude Code slash commands + CLAUDE.md section),
:class:`CodexAdapter` (Codex SKILL.md + command workflows), and
:class:`CopilotAdapter` (GitHub Copilot instructions).

Covers: FR-513 (Cursor adapter), FR-514 (Claude adapter), FR-517 (Codex adapter),
FR-518 (Copilot adapter), CON-09 (Protocol).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
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
        """Return the runtime name."""
        return self.RUNTIME_NAME

    def emit(self, manifest: SkillManifest) -> list[EmittedFile]:
        """Generate Cursor skill files from *manifest*."""
        files: list[EmittedFile] = [self._emit_skill_md(manifest)]
        for cmd in manifest.commands:
            files.append(self._emit_command(manifest, cmd.name))
        return files

    def _emit_skill_md(self, manifest: SkillManifest) -> EmittedFile:
        """Emit skill md."""
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
            "",
            "## Reference Navigation Guide",
            "",
            "NineS provides structured reference files in `references/` for domain",
            "knowledge that agents can selectively load. Each reference has YAML",
            "frontmatter with `triggers` — load a reference when the current task",
            "matches its trigger phrases.",
            "",
            "### Quick Reference Index",
            "",
            "| When working on...                     | Load this reference                      |",
            "|----------------------------------------|------------------------------------------|",
            "| Analysis pipeline, decomposition       | `references/analysis-pipeline.md`        |",
            "| Agent impact, mechanisms, artifacts    | `references/agent-impact-analysis.md`    |",
            "| Key points, priority, deduplication    | `references/key-point-extraction.md`     |",
            "| Eval tasks, scorers, benchmarks        | `references/evaluation-framework.md`     |",
            "| Iteration cycle, gaps, convergence     | `references/iteration-protocol.md`       |",
            "| Finding the right reference            | `references/index.md`                    |",
            "",
            "### Loading Strategy",
            "",
            "1. Read `references/index.md` first to identify which reference applies",
            "2. Load only the most specific reference for the current task",
            "3. Follow `dependencies` in the YAML frontmatter if upstream context is needed",
            "4. Each reference includes source file mappings and feature requirement IDs",
        ]
        return EmittedFile(
            relative_path="SKILL.md",
            content="\n".join(lines) + "\n",
            description="Main skill entry point",
        )

    def _emit_command(self, manifest: SkillManifest, command_name: str) -> EmittedFile:
        """Emit command."""
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
        """Return the runtime name."""
        return self.RUNTIME_NAME

    def emit(self, manifest: SkillManifest) -> list[EmittedFile]:
        """Generate Claude Code command files from *manifest*."""
        files: list[EmittedFile] = []
        for cmd in manifest.commands:
            files.append(self._emit_command(manifest, cmd))
        files.append(self._emit_claude_md_section(manifest))
        return files

    def _emit_command(self, manifest: SkillManifest, cmd: object) -> EmittedFile:
        """Emit command."""
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
        """Emit claude md section."""
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


class CodexAdapter:
    """Generates ``.codex/skills/nines/`` files including SKILL.md.

    Codex skills use a markdown-based SKILL.md with optional YAML frontmatter
    and per-command workflow files under ``commands/``.

    Covers: FR-517.
    """

    RUNTIME_NAME = "codex"
    INSTALL_DIR = ".codex/skills/nines"

    @property
    def runtime_name(self) -> str:
        """Return the runtime name."""
        return self.RUNTIME_NAME

    def emit(self, manifest: SkillManifest) -> list[EmittedFile]:
        """Generate Codex skill files from *manifest*."""
        files: list[EmittedFile] = [self._emit_skill_md(manifest)]
        for cmd in manifest.commands:
            files.append(self._emit_command(manifest, cmd))
        return files

    def _emit_skill_md(self, manifest: SkillManifest) -> EmittedFile:
        """Emit skill md."""
        lines = [
            "---",
            f"name: {manifest.name}",
            f"version: {manifest.version}",
            f"description: {manifest.description}",
            f"author: {manifest.author}",
            f"homepage: {manifest.homepage}",
            "---",
            "",
            f"# {manifest.name.upper()} — {manifest.description}",
            "",
            "## Available Commands",
            "",
            "| Command | Description | Capability |",
            "|---------|-------------|------------|",
        ]
        for cmd in manifest.commands:
            short = cmd.name.removeprefix("nines-")
            lines.append(f"| `{short}` | {cmd.description} | {cmd.capability} |")
        lines += [
            "",
            "## Prerequisites",
            "",
            f"- The `{manifest.cli_binary}` CLI binary must be on `$PATH`.",
            f"- Python {manifest.python_requires} is required.",
            "",
            "## Usage",
            "",
            f"All commands delegate to `{manifest.cli_binary} <subcommand>` via the Shell tool.",
            "",
            "```bash",
            f"{manifest.cli_binary} <command> [options]",
            "```",
        ]
        return EmittedFile(
            relative_path="SKILL.md",
            content="\n".join(lines) + "\n",
            description="Main skill entry point",
        )

    def _emit_command(self, manifest: SkillManifest, cmd: object) -> EmittedFile:
        """Emit command."""
        from nines.skill.manifest import CommandDef

        assert isinstance(cmd, CommandDef)
        short = cmd.name.removeprefix("nines-")
        lines = [
            f"# {cmd.name}",
            "",
            f"> {cmd.description}",
            "",
            "## Invocation",
            "",
            "```bash",
            f"{manifest.cli_binary} {short} {cmd.argument_hint}",
            "```",
            "",
            f"Capability: `{cmd.capability}`",
        ]
        return EmittedFile(
            relative_path=f"commands/{short}.md",
            content="\n".join(lines) + "\n",
            description=f"{cmd.name} command workflow",
        )


class CopilotAdapter:
    """Generates ``.github/copilot-instructions.md`` with NineS documentation.

    Covers: FR-518.
    """

    RUNTIME_NAME = "copilot"
    INSTALL_DIR = ".github"

    @property
    def runtime_name(self) -> str:
        """Return the runtime name."""
        return self.RUNTIME_NAME

    def emit(self, manifest: SkillManifest) -> list[EmittedFile]:
        """Generate Copilot instructions file from *manifest*."""
        lines = [
            f"# {manifest.name.upper()} — {manifest.description}",
            "",
            "## Available Commands",
            "",
            "| Command | Description |",
            "|---------|-------------|",
        ]
        for cmd in manifest.commands:
            short = cmd.name.removeprefix("nines-")
            lines.append(f"| `{short}` | {cmd.description} |")
        lines += [
            "",
            "## Prerequisites",
            "",
            f"- The `{manifest.cli_binary}` CLI binary must be on `$PATH`.",
            f"- Python {manifest.python_requires} is required.",
            "",
            "## Usage",
            "",
            f"All commands delegate to `{manifest.cli_binary} <subcommand>` via the Shell tool.",
        ]
        return [
            EmittedFile(
                relative_path="copilot-instructions.md",
                content="\n".join(lines) + "\n",
                description="Copilot instructions file",
            )
        ]
