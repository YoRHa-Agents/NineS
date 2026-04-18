"""Knowledge-graph ID canonicalizer.

The graph builder writes node IDs and edge endpoints from different
producers (file-scanner vs import-graph builder vs ad-hoc decomposers).
Today the same logical artifact can appear as:

* ``file:CONTRIBUTING.md``                     (relative to project root)
* ``file:/home/agent/reference/caveman/CONTRIBUTING.md``  (absolute)
* ``function:/home/agent/reference/caveman/scripts/run.py::main``

The verifier's referential-integrity check compares these via plain
set-membership and reports thousands of false-positive ``critical``
issues (baseline §4.1: 49 / 803 / 40 across the three samples).

This module provides :func:`canonicalize_id`, which reduces every
recognised ID into a stable form keyed on a path *relative* to the
project root.  The verifier (and any other consumer) can then compare
canonical IDs without worrying about which producer wrote them.

Covers: C03 (graph canonicalizer + verifier-as-gate).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ID type-prefixes recognised by the canonicalizer.  Anything else is
# returned verbatim so concept-only IDs (e.g. ``concept:knowledge``) are
# unaffected.
_PATH_PREFIXES = frozenset({"file", "function", "class", "module"})

# ``function`` and ``class`` prefixes embed a Python-style ``::member``
# qualifier on the path component.  The split below preserves it.
_MEMBER_SEP = "::"


def canonicalize_id(raw: str, *, project_root: str | Path) -> str:
    """Return *raw* with its path component normalised relative to *project_root*.

    Parameters
    ----------
    raw:
        Raw ID such as ``file:foo/bar.py`` or
        ``function:/home/repo/foo.py::main``.
    project_root:
        Directory the canonical form should be expressed relative to.

    Returns
    -------
    str
        Canonical ID.  IDs whose prefix is not in :data:`_PATH_PREFIXES`
        are returned unchanged; malformed IDs (no ``:`` separator) are
        also returned unchanged with a debug log.

    Raises
    ------
    ValueError
        If *raw* is empty or *project_root* is empty.
    """
    if not raw:
        msg = "canonicalize_id requires a non-empty id"
        raise ValueError(msg)
    if not project_root:
        msg = "canonicalize_id requires a non-empty project_root"
        raise ValueError(msg)

    if ":" not in raw:
        # Not a typed ID — leave unchanged so concept-only IDs survive.
        logger.debug("canonicalize_id: no type-prefix in %r; passthrough", raw)
        return raw

    prefix, _, remainder = raw.partition(":")
    if prefix not in _PATH_PREFIXES:
        return raw
    if not remainder:
        # ``file:`` with nothing after — pathological, return as-is.
        return raw

    # function/class IDs may carry a ``::member`` suffix on the *path*
    # component.  Split it off, canonicalize the path, then recombine.
    path_part, sep, member = remainder.partition(_MEMBER_SEP)
    canonical_path = _normalise_path(path_part, project_root)
    if sep:
        return f"{prefix}:{canonical_path}{_MEMBER_SEP}{member}"
    return f"{prefix}:{canonical_path}"


def _normalise_path(raw_path: str, project_root: str | Path) -> str:
    """Return *raw_path* expressed as a project-relative POSIX path.

    Falls back to a resolved absolute POSIX path when *raw_path* lies
    outside *project_root* (e.g. site-packages references).
    """
    root = Path(project_root)
    try:
        root_resolved = root.resolve()
    except OSError as exc:
        logger.warning(
            "canonicalize_id: could not resolve project_root %s (%s); "
            "using absolute fallback",
            root, exc,
        )
        root_resolved = root.absolute()

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root_resolved / candidate

    try:
        resolved = candidate.resolve()
    except OSError as exc:
        # Path may not exist on disk — best-effort absolute form so we
        # still produce a stable canonical result.
        logger.debug(
            "canonicalize_id: could not resolve %s under %s (%s); "
            "using best-effort normalisation",
            candidate, root_resolved, exc,
        )
        resolved = candidate.absolute()

    try:
        rel = resolved.relative_to(root_resolved)
    except ValueError:
        # Outside the project root: keep an absolute POSIX path so
        # equality still holds across producers.
        return resolved.as_posix()

    posix = rel.as_posix()
    # Path("") and Path(".") yield "" and "." respectively; normalise the
    # root-of-project case to "." so consumers see a stable token.
    return posix or "."


def canonicalize_pair(
    source: str,
    target: str,
    *,
    project_root: str | Path,
) -> tuple[str, str]:
    """Return ``(canonical_source, canonical_target)`` for an edge.

    Convenience wrapper used by :class:`GraphVerifier` to apply the same
    transformation to both endpoints.
    """
    return (
        canonicalize_id(source, project_root=project_root),
        canonicalize_id(target, project_root=target_anchor(project_root)),
    )


def target_anchor(project_root: str | Path) -> Path:
    """Return *project_root* as a Path; helper for :func:`canonicalize_pair`."""
    return Path(project_root)


def common_project_root(paths: list[str]) -> str:
    """Best-effort common-prefix root for a batch of absolute paths.

    Used by the verifier when no explicit ``project_root`` was supplied.
    Returns ``"."`` when no paths are provided or when no common prefix
    can be established.
    """
    abs_paths: list[str] = []
    for p in paths:
        try:
            abs_paths.append(str(Path(p).expanduser().resolve()))
        except OSError as exc:
            logger.debug("common_project_root: skipping %r (%s)", p, exc)
            continue
    if not abs_paths:
        return "."
    common = os.path.commonpath(abs_paths)
    return common or "."


__all__ = [
    "canonicalize_id",
    "canonicalize_pair",
    "common_project_root",
]
