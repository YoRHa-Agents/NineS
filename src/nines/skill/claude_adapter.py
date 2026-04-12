"""Claude Code specific skill adapter with filesystem generation.

Provides :class:`ClaudeAdapter` with a high-level
:meth:`generate_commands` method that creates the
``.claude/commands/nines/`` directory containing slash command files.

Covers: FR-514.
"""

from __future__ import annotations

import logging
from pathlib import Path

from nines.skill.adapters import ClaudeAdapter as _BaseClaudeAdapter
from nines.skill.manifest import SkillManifest

logger = logging.getLogger(__name__)


class ClaudeAdapter(_BaseClaudeAdapter):
    """Extended Claude adapter that writes command files to disk.

    Inherits the ``emit()`` protocol from the base adapter and adds
    :meth:`generate_commands` for direct filesystem generation.
    """

    def generate_commands(
        self,
        output_path: str | Path,
        manifest: SkillManifest | None = None,
    ) -> list[Path]:
        """Create ``.claude/commands/nines/`` with slash command files.

        Parameters
        ----------
        output_path:
            Project root directory.  The ``.claude/commands/nines/``
            subtree is created under this path.
        manifest:
            Optional manifest override; defaults to a fresh
            :class:`SkillManifest`.

        Returns
        -------
        list[Path]
            Absolute paths of all command files written (excludes the
            ``__CLAUDE_MD_SECTION__`` virtual file).
        """
        manifest = manifest or SkillManifest()
        root = Path(output_path).resolve()
        install_dir = root / self.INSTALL_DIR
        install_dir.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        for emitted in self.emit(manifest):
            if emitted.relative_path == "__CLAUDE_MD_SECTION__":
                continue
            dest = install_dir / emitted.relative_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(emitted.content, encoding="utf-8")
            written.append(dest)
            logger.debug("Wrote %s", dest)

        logger.info(
            "Generated Claude commands directory at %s (%d files)",
            install_dir, len(written),
        )
        return written
