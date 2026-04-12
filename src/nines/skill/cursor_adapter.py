"""Cursor-specific skill adapter with filesystem generation.

Provides :class:`CursorAdapter` with a high-level
:meth:`generate_skill_dir` method that creates the
``.cursor/skills/nines/`` directory containing ``SKILL.md`` and
per-command workflow files.

Covers: FR-513.
"""

from __future__ import annotations

import logging
from pathlib import Path

from nines.skill.adapters import CursorAdapter as _BaseCursorAdapter
from nines.skill.manifest import SkillManifest

logger = logging.getLogger(__name__)


class CursorAdapter(_BaseCursorAdapter):
    """Extended Cursor adapter that writes skill files to disk.

    Inherits the ``emit()`` protocol from the base adapter and adds
    :meth:`generate_skill_dir` for direct filesystem generation.
    """

    def generate_skill_dir(
        self,
        output_path: str | Path,
        manifest: SkillManifest | None = None,
    ) -> list[Path]:
        """Create ``.cursor/skills/nines/`` with SKILL.md and commands.

        Parameters
        ----------
        output_path:
            Project root directory.  The ``.cursor/skills/nines/``
            subtree is created under this path.
        manifest:
            Optional manifest override; defaults to a fresh
            :class:`SkillManifest`.

        Returns
        -------
        list[Path]
            Absolute paths of all files written.
        """
        manifest = manifest or SkillManifest()
        root = Path(output_path).resolve()
        install_dir = root / self.INSTALL_DIR
        install_dir.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        for emitted in self.emit(manifest):
            dest = install_dir / emitted.relative_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(emitted.content, encoding="utf-8")
            written.append(dest)
            logger.debug("Wrote %s", dest)

        logger.info(
            "Generated Cursor skill directory at %s (%d files)",
            install_dir, len(written),
        )
        return written
