"""Project identity utilities for namespacing finding IDs and reports.

This module provides stable, project-scoped identifiers so that downstream
artifacts emitted by the analyzer are globally unique across multiple
projects analyzed by the same NineS install.

Today, agent-impact / key-point / reviewer findings use bare
``f"AI-{idx:04d}"`` IDs which collide across reports for different repos
(see baseline §4.5).  The :func:`project_fingerprint` helper here computes
a short, stable hash derived from a repository's resolved absolute path
(plus its git remote when available), and :func:`parse_finding_id`
round-trips both legacy and namespaced finding IDs.

Hash collision risk for 32-bit blake2s: for ~1000 distinct projects in a
NineS install the expected collision count is < 10⁻³.

Covers: C02 (project-scoped finding-ID namespace).
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Length of the project-fingerprint prefix in hex characters (32 bits).
_FINGERPRINT_LEN = 8

# Pattern accepting either ``AI-NNNN`` (legacy) or ``AI-XXXXXXXX-NNNN``
# (namespaced).  The middle segment must be exactly _FINGERPRINT_LEN
# lowercase hex characters; the index must be at least 4 decimal digits.
_FINDING_ID_RE = re.compile(
    r"^(?P<prefix>[A-Z]{2,4})-"
    r"(?:(?P<project>[0-9a-f]{" + str(_FINGERPRINT_LEN) + r"})-)?"
    r"(?P<idx>\d{4,})$"
)


@dataclass(frozen=True)
class FindingIdParts:
    """Parsed components of a finding ID.

    Attributes
    ----------
    prefix:
        Short uppercase tag (e.g. ``"AI"``, ``"KP"``, ``"RV"``).
    project_id:
        8-character lowercase hex fingerprint, or ``None`` for legacy
        unscoped IDs.
    index:
        Zero-padded sequence number within the report.
    """

    prefix: str
    project_id: str | None
    index: int

    def render(self) -> str:
        """Render back to a finding-ID string preserving original format."""
        if self.project_id is None:
            return f"{self.prefix}-{self.index:04d}"
        return f"{self.prefix}-{self.project_id}-{self.index:04d}"


def project_fingerprint(path: str | Path) -> str:
    """Return a stable 8-char fingerprint for *path*.

    The fingerprint is derived from the resolved absolute path of the
    project root, optionally combined with the git remote URL when one
    is available, hashed with blake2s and truncated to 32 bits of
    entropy.

    Parameters
    ----------
    path:
        Project root directory (or any path inside the project).

    Returns
    -------
    str
        8-character lowercase hex fingerprint suitable for embedding in
        finding IDs.

    Raises
    ------
    ValueError
        If *path* is empty.
    """
    if not path:
        msg = "project_fingerprint() requires a non-empty path"
        raise ValueError(msg)

    p = Path(path).expanduser()
    try:
        resolved = p.resolve()
    except OSError as exc:
        # Path may not exist yet (e.g. computed before mkdir).  Fall back
        # to a best-effort absolute path; never silently swallow without
        # logging.
        logger.warning(
            "project_fingerprint: could not resolve %s (%s); using absolute fallback",
            p,
            exc,
        )
        resolved = p.absolute()

    components: list[str] = [str(resolved)]
    remote = _git_remote(resolved)
    if remote:
        components.append(remote)

    payload = "\x1f".join(components).encode("utf-8")
    digest = hashlib.blake2s(payload, digest_size=4).hexdigest()
    return digest


def parse_finding_id(s: str) -> FindingIdParts:
    """Parse a finding-ID string into its components.

    Accepts both legacy IDs (``AI-0000``) and namespaced IDs
    (``AI-deadbeef-0000``).

    Parameters
    ----------
    s:
        Finding-ID string.

    Returns
    -------
    FindingIdParts
        Parsed components.

    Raises
    ------
    ValueError
        If *s* doesn't match either supported format.
    """
    if not isinstance(s, str):
        msg = f"parse_finding_id requires a str, got {type(s).__name__}"
        raise TypeError(msg)
    m = _FINDING_ID_RE.match(s)
    if m is None:
        msg = f"Unrecognised finding-ID format: {s!r}"
        raise ValueError(msg)
    return FindingIdParts(
        prefix=m.group("prefix"),
        project_id=m.group("project"),
        index=int(m.group("idx")),
    )


def format_finding_id(prefix: str, index: int, project_id: str | None) -> str:
    """Render a finding-ID using the namespaced format when *project_id*
    is provided.

    Parameters
    ----------
    prefix:
        Short uppercase tag (e.g. ``"AI"``).
    index:
        Sequence number; will be zero-padded to 4 digits.
    project_id:
        Optional project fingerprint.  When ``None``, the legacy unscoped
        format is used (preserves backward compatibility).

    Returns
    -------
    str
        Finding-ID string.
    """
    if not prefix or not prefix.isupper() or not prefix.isalpha():
        msg = f"prefix must be an uppercase ASCII tag, got {prefix!r}"
        raise ValueError(msg)
    if index < 0:
        msg = f"index must be non-negative, got {index}"
        raise ValueError(msg)
    if project_id is None:
        return f"{prefix}-{index:04d}"
    if len(project_id) != _FINGERPRINT_LEN or not all(c in "0123456789abcdef" for c in project_id):
        msg = f"project_id must be {_FINGERPRINT_LEN} lowercase hex chars, got {project_id!r}"
        raise ValueError(msg)
    return f"{prefix}-{project_id}-{index:04d}"


def _git_remote(path: Path) -> str | None:
    """Return the project's primary git remote URL, or ``None``.

    Best-effort; failure is logged at debug level since many analyzed
    paths legitimately are not git repos.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("git remote lookup failed for %s: %s", path, exc)
        return None
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    return url or None


__all__ = [
    "FindingIdParts",
    "format_finding_id",
    "parse_finding_id",
    "project_fingerprint",
]
