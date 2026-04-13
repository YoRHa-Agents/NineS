"""Agent skill adapters for Cursor, Claude Code, Codex, and GitHub Copilot.

Public API
----------
- :class:`SkillManifest` — canonical skill definition with TOML generation
- :class:`SkillInstaller` — install / uninstall orchestrator
- :class:`CursorAdapter` — Cursor ``.cursor/skills/`` emitter
- :class:`ClaudeAdapter` — Claude Code ``.claude/commands/`` emitter
- :class:`CodexAdapter` — Codex ``.codex/skills/`` emitter
- :class:`CopilotAdapter` — GitHub Copilot ``.github/`` emitter
"""

from nines.skill.adapters import (
    ClaudeAdapter,
    CodexAdapter,
    CopilotAdapter,
    CursorAdapter,
    EmittedFile,
    SkillAdapter,
)
from nines.skill.installer import SkillInstaller
from nines.skill.manifest import CommandDef, SkillManifest

__all__ = [
    "ClaudeAdapter",
    "CodexAdapter",
    "CommandDef",
    "CopilotAdapter",
    "CursorAdapter",
    "EmittedFile",
    "SkillAdapter",
    "SkillInstaller",
    "SkillManifest",
]
