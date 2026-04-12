"""Agent skill adapters for Cursor and Claude Code.

Public API
----------
- :class:`SkillManifest` — canonical skill definition with TOML generation
- :class:`SkillInstaller` — install / uninstall orchestrator
- :class:`CursorAdapter` — Cursor ``.cursor/skills/`` emitter
- :class:`ClaudeAdapter` — Claude Code ``.claude/commands/`` emitter
"""

from nines.skill.adapters import ClaudeAdapter, CursorAdapter, EmittedFile, SkillAdapter
from nines.skill.installer import SkillInstaller
from nines.skill.manifest import CommandDef, SkillManifest

__all__ = [
    "ClaudeAdapter",
    "CommandDef",
    "CursorAdapter",
    "EmittedFile",
    "SkillAdapter",
    "SkillInstaller",
    "SkillManifest",
]
