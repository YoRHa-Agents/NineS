"""GitHub Copilot specific skill adapter with filesystem generation.

Provides :class:`CopilotAdapter` with a high-level
:meth:`generate_instructions` method that creates the
``.github/copilot-instructions.md`` file with NineS capability documentation.

Covers: FR-518.
"""

from __future__ import annotations

import logging
from pathlib import Path

from nines.skill.adapters import CopilotAdapter as _BaseCopilotAdapter
from nines.skill.manifest import SkillManifest

logger = logging.getLogger(__name__)


class CopilotAdapter(_BaseCopilotAdapter):
    """Extended Copilot adapter that writes instructions to disk.

    Inherits the ``emit()`` protocol from the base adapter and adds
    :meth:`generate_instructions` for direct filesystem generation.
    """

    def generate_instructions(
        self,
        output_path: str | Path,
        manifest: SkillManifest | None = None,
    ) -> Path:
        """Create ``.github/copilot-instructions.md`` with NineS content.

        Parameters
        ----------
        output_path:
            Project root directory.  The ``.github/`` directory is
            created under this path if it does not already exist.
        manifest:
            Optional manifest override; defaults to a fresh
            :class:`SkillManifest`.

        Returns
        -------
        Path
            Absolute path of the instructions file written.
        """
        manifest = manifest or SkillManifest()
        root = Path(output_path).resolve()
        install_dir = root / self.INSTALL_DIR
        install_dir.mkdir(parents=True, exist_ok=True)

        emitted_files = self.emit(manifest)
        emitted = emitted_files[0]
        dest = install_dir / emitted.relative_path
        dest.write_text(emitted.content, encoding="utf-8")
        logger.debug("Wrote %s", dest)

        logger.info(
            "Generated Copilot instructions at %s",
            dest,
        )
        return dest
