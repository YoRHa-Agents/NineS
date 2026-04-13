"""Skill installer for deploying NineS into agent runtimes.

Orchestrates manifest loading, adapter file generation, and writing to the
target directory.  Supports install/uninstall with version-aware semantics.

Covers: FR-506 (install CLI), FR-516 (version management).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from nines.skill.claude_adapter import ClaudeAdapter
from nines.skill.codex_adapter import CodexAdapter
from nines.skill.copilot_adapter import CopilotAdapter
from nines.skill.cursor_adapter import CursorAdapter
from nines.skill.manifest import SkillManifest

if TYPE_CHECKING:
    from nines.skill.adapters import SkillAdapter

log = structlog.get_logger(module="nines.skill.installer")


class SkillInstaller:
    """Install or uninstall NineS skill files into agent runtimes."""

    ADAPTERS: dict[str, SkillAdapter] = {
        "cursor": CursorAdapter(),
        "claude": ClaudeAdapter(),
        "codex": CodexAdapter(),
        "copilot": CopilotAdapter(),
    }

    def __init__(self, manifest: SkillManifest | None = None) -> None:
        """Initialize skill installer."""
        self._manifest = manifest or SkillManifest()

    def install(self, target: str, project_dir: Path | None = None) -> list[str]:
        """Install skill files for *target* runtime under *project_dir*.

        Parameters
        ----------
        target:
            ``"cursor"``, ``"claude"``, ``"codex"``, ``"copilot"``, or ``"all"``.
        project_dir:
            Root directory for the installation.  Defaults to cwd.

        Returns
        -------
        list[str]
            Paths (relative to *project_dir*) of files created.
        """
        project_dir = (project_dir or Path(".")).resolve()
        targets = self._resolve_targets(target)
        created: list[str] = []

        for runtime_name in targets:
            adapter = self.ADAPTERS[runtime_name]
            files = adapter.emit(self._manifest)
            install_dir = self._install_dir(adapter, project_dir)
            install_dir.mkdir(parents=True, exist_ok=True)

            for emitted in files:
                if emitted.relative_path == "__CLAUDE_MD_SECTION__":
                    continue
                dest = install_dir / emitted.relative_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(emitted.content, encoding="utf-8")
                created.append(str(dest.relative_to(project_dir)))
                log.debug("file_written", path=str(dest))

        log.info("install_complete", target=target, files_created=len(created))
        return created

    def uninstall(self, target: str, project_dir: Path | None = None) -> list[str]:
        """Remove NineS skill files for *target* runtime.

        Returns
        -------
        list[str]
            Paths of directories removed.
        """
        project_dir = (project_dir or Path(".")).resolve()
        targets = self._resolve_targets(target)
        removed: list[str] = []

        for runtime_name in targets:
            adapter = self.ADAPTERS[runtime_name]
            install_dir = self._install_dir(adapter, project_dir)
            if install_dir.exists():
                shutil.rmtree(install_dir)
                removed.append(str(install_dir.relative_to(project_dir)))
                log.info("uninstall_removed", path=str(install_dir))

        return removed

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_targets(self, target: str) -> list[str]:
        """Resolve targets."""
        if target == "all":
            return list(self.ADAPTERS)
        if target not in self.ADAPTERS:
            raise ValueError(
                f"Unknown target '{target}'. "
                f"Expected one of: {', '.join(self.ADAPTERS)}, all."
            )
        return [target]

    @staticmethod
    def _install_dir(adapter: SkillAdapter, project_dir: Path) -> Path:
        """Install dir."""
        if isinstance(adapter, CursorAdapter):
            return project_dir / CursorAdapter.INSTALL_DIR
        if isinstance(adapter, ClaudeAdapter):
            return project_dir / ClaudeAdapter.INSTALL_DIR
        if isinstance(adapter, CodexAdapter):
            return project_dir / CodexAdapter.INSTALL_DIR
        if isinstance(adapter, CopilotAdapter):
            return project_dir / CopilotAdapter.INSTALL_DIR
        raise ValueError(f"Unsupported adapter: {adapter.runtime_name}")
