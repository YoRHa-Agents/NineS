"""Project-aware ``EvaluationContext`` for self-eval evaluators.

Today, self-eval evaluators silently fall back to NineS's own ``src/nines``
when no ``--src-dir`` is supplied (see baseline §4.8: caveman & UA both
report ``total_elements=837, files_analyzed=83`` — NineS's counts). The
:class:`EvaluationContext` here makes the project binding *explicit*: an
evaluator that declares ``requires_context = True`` will refuse to run
without a context object.

This implements C01 Phase 1 of the v3.2.0 design (Wave 2). The fingerprint
field is reused from :func:`nines.core.identity.project_fingerprint` so a
report's ``context_fingerprint`` is always derivable from its source paths.

Covers: C01 Phase 1 (project-aware EvaluationContext).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nines.core.errors import ConfigError
from nines.core.identity import project_fingerprint

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvaluationContext:
    """Immutable snapshot of *what project* a self-eval run targets.

    Attributes
    ----------
    project_root:
        Resolved absolute path to the repository root being evaluated.
    src_dir:
        Resolved absolute path to the source directory the evaluators
        should scan. Often a subdirectory of ``project_root``.
    test_dir:
        Optional resolved path to the test directory.
    samples_dir:
        Optional resolved path to a samples directory (e.g. for the
        EvalCoverageEvaluator).
    golden_dir:
        Optional resolved path to a golden-test-set directory.
    metadata:
        Free-form labels (git rev, repo hash, CI build id, …) the caller
        wants persisted into the report alongside the fingerprint.

    Notes
    -----
    The dataclass is frozen so contexts can be safely cached and shared
    between evaluators without anyone mutating them mid-run.
    """

    project_root: Path
    src_dir: Path
    test_dir: Path | None = None
    samples_dir: Path | None = None
    golden_dir: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_cli(
        cls,
        project_root: str | Path,
        src_dir: str | Path,
        test_dir: str | Path | None = None,
        samples_dir: str | Path | None = None,
        golden_dir: str | Path | None = None,
        metadata: dict[str, str] | None = None,
    ) -> EvaluationContext:
        """Build a context from raw CLI option values.

        Parameters
        ----------
        project_root:
            Required. Resolved & validated to exist as a directory.
        src_dir:
            Required. Relative paths are interpreted against
            ``project_root`` (so ``--project-root /x --src-dir foo``
            yields ``/x/foo``); absolute paths are used as-is. Must
            exist as a directory.
        test_dir, samples_dir, golden_dir:
            Optional. Same relative-path resolution as ``src_dir``.
            Existence is *not* required for these — many third-party
            projects don't have a test directory at all, and the
            evaluator is expected to handle the missing-dir case.
        metadata:
            Free-form key→value labels.

        Raises
        ------
        ConfigError
            If ``project_root`` or the resolved ``src_dir`` does not
            exist or is not a directory.
        """
        if project_root is None or str(project_root) == "":
            msg = "EvaluationContext.from_cli requires a non-empty project_root"
            raise ConfigError(msg)
        if src_dir is None or str(src_dir) == "":
            msg = "EvaluationContext.from_cli requires a non-empty src_dir"
            raise ConfigError(msg)

        root = Path(project_root).expanduser()
        try:
            root_resolved = root.resolve(strict=True)
        except FileNotFoundError as exc:
            msg = f"project_root does not exist: {root}"
            raise ConfigError(msg, cause=exc) from exc
        if not root_resolved.is_dir():
            msg = f"project_root is not a directory: {root_resolved}"
            raise ConfigError(msg)

        src_path = Path(src_dir).expanduser()
        src_resolved = (root_resolved / src_path) if not src_path.is_absolute() else src_path
        try:
            src_resolved = src_resolved.resolve(strict=True)
        except FileNotFoundError as exc:
            msg = f"src_dir does not exist: {src_resolved}"
            raise ConfigError(msg, cause=exc) from exc
        if not src_resolved.is_dir():
            msg = f"src_dir is not a directory: {src_resolved}"
            raise ConfigError(msg)

        test_resolved = cls._resolve_optional(test_dir, root_resolved)
        samples_resolved = cls._resolve_optional(samples_dir, root_resolved)
        golden_resolved = cls._resolve_optional(golden_dir, root_resolved)

        return cls(
            project_root=root_resolved,
            src_dir=src_resolved,
            test_dir=test_resolved,
            samples_dir=samples_resolved,
            golden_dir=golden_resolved,
            metadata=dict(metadata) if metadata else {},
        )

    @staticmethod
    def _resolve_optional(
        candidate: str | Path | None,
        root_resolved: Path,
    ) -> Path | None:
        """Resolve an optional path relative to *root_resolved*.

        Returns ``None`` for empty / ``None`` inputs. Returns an
        unresolved-but-absolute :class:`Path` when the candidate doesn't
        exist on disk (callers may legitimately point at a future
        output dir).
        """
        if candidate is None or str(candidate) == "":
            return None
        p = Path(candidate).expanduser()
        absolute = p if p.is_absolute() else (root_resolved / p)
        try:
            return absolute.resolve(strict=True)
        except FileNotFoundError:
            # The path doesn't exist yet — return absolute form, never
            # silently swallow the user's intent.
            logger.debug(
                "EvaluationContext optional path does not exist: %s",
                absolute,
            )
            return absolute.resolve(strict=False)

    def fingerprint(self) -> str:
        """Return a stable 8-char fingerprint of the project binding.

        Combines ``project_root`` and ``src_dir`` so two contexts that
        target the same repo but different source subdirectories get
        distinct fingerprints. Reuses
        :func:`nines.core.identity.project_fingerprint` to share the
        same blake2s/digest size that C02 finding-IDs already use, and
        layers in ``src_dir`` so different sub-trees of the same repo
        do not collide.
        """
        # Use the resolved tuple to avoid case/symlink drift; concatenate
        # with the unit separator so the components can never combine
        # ambiguously.
        marker = f"{self.project_root}\x1f{self.src_dir}"
        return project_fingerprint(marker)

    def requires_writable(self) -> bool:
        """Return True iff evaluators may write to the project tree.

        For the v3.2.0 baseline behaviour, evaluators are read-only;
        this method exists so future writable contexts (e.g. for
        auto-fix operators) can opt in without changing the dataclass
        fields.
        """
        return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dictionary.

        Round-trips through :meth:`from_dict` for empty dicts as well as
        full configurations. Paths are emitted as strings.
        """
        return {
            "project_root": str(self.project_root),
            "src_dir": str(self.src_dir),
            "test_dir": str(self.test_dir) if self.test_dir is not None else None,
            "samples_dir": (
                str(self.samples_dir) if self.samples_dir is not None else None
            ),
            "golden_dir": (
                str(self.golden_dir) if self.golden_dir is not None else None
            ),
            "metadata": dict(self.metadata),
            "fingerprint": self.fingerprint(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationContext:
        """Round-trip a dict produced by :meth:`to_dict`.

        Path validation is *not* re-applied: a context loaded from a
        historical report may legitimately point at directories that no
        longer exist on the local filesystem.
        """
        if "project_root" not in data or "src_dir" not in data:
            msg = "EvaluationContext.from_dict requires 'project_root' and 'src_dir'"
            raise ConfigError(msg)

        def _opt(key: str) -> Path | None:
            v = data.get(key)
            if v is None or v == "":
                return None
            return Path(v)

        return cls(
            project_root=Path(data["project_root"]),
            src_dir=Path(data["src_dir"]),
            test_dir=_opt("test_dir"),
            samples_dir=_opt("samples_dir"),
            golden_dir=_opt("golden_dir"),
            metadata=dict(data.get("metadata", {})),
        )


__all__ = ["EvaluationContext"]
