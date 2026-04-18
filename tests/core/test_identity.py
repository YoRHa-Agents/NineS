"""Tests for ``nines.core.identity`` (C02 — project-scoped finding IDs).

Covers ``project_fingerprint``, ``parse_finding_id``, and
``format_finding_id`` round-trip semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.core.identity import (  # noqa: E402
    FindingIdParts,
    format_finding_id,
    parse_finding_id,
    project_fingerprint,
)

# ---------------------------------------------------------------------------
# project_fingerprint
# ---------------------------------------------------------------------------


def test_project_fingerprint_is_8_lowercase_hex(tmp_path: Path) -> None:
    """Fingerprints must be exactly 8 lowercase hex characters."""
    fp = project_fingerprint(tmp_path)
    assert len(fp) == 8
    assert fp == fp.lower()
    assert all(c in "0123456789abcdef" for c in fp)


def test_project_fingerprint_is_stable(tmp_path: Path) -> None:
    """Repeated calls on the same path return the same fingerprint."""
    fp1 = project_fingerprint(tmp_path)
    fp2 = project_fingerprint(tmp_path)
    assert fp1 == fp2


def test_project_fingerprint_distinct_for_distinct_paths(tmp_path: Path) -> None:
    """Two unrelated paths produce distinct fingerprints."""
    a = tmp_path / "alpha"
    b = tmp_path / "beta"
    a.mkdir()
    b.mkdir()
    assert project_fingerprint(a) != project_fingerprint(b)


def test_project_fingerprint_resolves_relative_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative paths are resolved before hashing — same project, same fp."""
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "proj"
    sub.mkdir()
    fp_abs = project_fingerprint(sub)
    fp_rel = project_fingerprint("proj")
    assert fp_abs == fp_rel


def test_project_fingerprint_handles_string_path(tmp_path: Path) -> None:
    """String input is accepted equivalently to Path input."""
    assert project_fingerprint(str(tmp_path)) == project_fingerprint(tmp_path)


def test_project_fingerprint_rejects_empty() -> None:
    """Empty path raises ValueError, not a silent fallback."""
    with pytest.raises(ValueError):
        project_fingerprint("")


def test_project_fingerprint_handles_nonexistent_path(tmp_path: Path) -> None:
    """Non-existent paths still produce a fingerprint via absolute() fallback."""
    fake = tmp_path / "does-not-exist-yet"
    fp = project_fingerprint(fake)
    assert len(fp) == 8


def test_project_fingerprint_collision_rate_low(tmp_path: Path) -> None:
    """Mass-generate 2000 paths and assert <2 collisions (32-bit blake2s)."""
    seen: set[str] = set()
    collisions = 0
    for i in range(2000):
        sub = tmp_path / f"p_{i:05d}"
        sub.mkdir()
        fp = project_fingerprint(sub)
        if fp in seen:
            collisions += 1
        else:
            seen.add(fp)
    # Birthday-bound expectation: ~10^-3 → typically zero across 2000 paths.
    assert collisions < 2, f"unexpectedly high collision rate: {collisions}"


# ---------------------------------------------------------------------------
# parse_finding_id
# ---------------------------------------------------------------------------


def test_parse_legacy_unscoped_id() -> None:
    """Legacy ``AI-0000`` parses with no project_id."""
    parts = parse_finding_id("AI-0000")
    assert parts == FindingIdParts(prefix="AI", project_id=None, index=0)


def test_parse_legacy_keypoint_id() -> None:
    """Other 2-char prefixes (KP, RV) work too."""
    parts = parse_finding_id("KP-0042")
    assert parts.prefix == "KP"
    assert parts.project_id is None
    assert parts.index == 42


def test_parse_namespaced_id() -> None:
    """Namespaced ``AI-deadbeef-0000`` parses with project_id populated."""
    parts = parse_finding_id("AI-deadbeef-0042")
    assert parts == FindingIdParts(
        prefix="AI",
        project_id="deadbeef",
        index=42,
    )


def test_parse_rejects_uppercase_project_id() -> None:
    """Project-id segment must be lowercase hex."""
    with pytest.raises(ValueError):
        parse_finding_id("AI-DEADBEEF-0000")


def test_parse_rejects_short_project_id() -> None:
    """Project-id segment must be exactly 8 hex chars."""
    with pytest.raises(ValueError):
        parse_finding_id("AI-deadb-0000")


def test_parse_rejects_unknown_prefix_format() -> None:
    """Garbage strings raise ValueError, not a silent default."""
    with pytest.raises(ValueError):
        parse_finding_id("not-a-finding-id")


def test_parse_round_trip_legacy() -> None:
    """``parse → render`` round-trips legacy IDs exactly."""
    s = "AI-0007"
    assert parse_finding_id(s).render() == s


def test_parse_round_trip_namespaced() -> None:
    """``parse → render`` round-trips namespaced IDs exactly."""
    s = "AI-12345678-0007"
    assert parse_finding_id(s).render() == s


def test_parse_rejects_non_string() -> None:
    """Type-confused inputs raise TypeError before regex matching."""
    with pytest.raises(TypeError):
        parse_finding_id(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# format_finding_id
# ---------------------------------------------------------------------------


def test_format_finding_id_legacy() -> None:
    """``project_id=None`` returns the legacy ``AI-NNNN`` form."""
    assert format_finding_id("AI", 7, None) == "AI-0007"


def test_format_finding_id_namespaced() -> None:
    """Valid project_id produces ``AI-XXXXXXXX-NNNN``."""
    assert format_finding_id("AI", 7, "deadbeef") == "AI-deadbeef-0007"


def test_format_finding_id_rejects_negative_index() -> None:
    """Negative indexes raise ValueError."""
    with pytest.raises(ValueError):
        format_finding_id("AI", -1, None)


def test_format_finding_id_rejects_bad_prefix() -> None:
    """Lowercase or empty prefixes raise ValueError."""
    with pytest.raises(ValueError):
        format_finding_id("ai", 0, None)
    with pytest.raises(ValueError):
        format_finding_id("", 0, None)


def test_format_finding_id_rejects_bad_project_id() -> None:
    """Non-hex / wrong-length project IDs are rejected."""
    with pytest.raises(ValueError):
        format_finding_id("AI", 0, "DEADBEEF")  # uppercase
    with pytest.raises(ValueError):
        format_finding_id("AI", 0, "tooshort")  # not hex


def test_format_finding_id_round_trip() -> None:
    """``format → parse`` round-trips."""
    rendered = format_finding_id("RV", 12, "abcdef01")
    parts = parse_finding_id(rendered)
    assert parts.prefix == "RV"
    assert parts.project_id == "abcdef01"
    assert parts.index == 12
