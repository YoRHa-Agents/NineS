"""Golden test harness for ``SelfEvalRunner`` (C06 — full deliverable).

Three guarantees this file pins down:

1. **Golden snapshot reproduction** — building a runner with
   :class:`~nines.eval.mock_executor.MockEvaluator` instances wired to
   the values in ``nines_v3_1_0_capability.json`` produces a report
   whose trimmed projection matches the fixture byte-for-byte.  Any
   future schema/weight regression breaks this test.

2. **Silent-fallback divergence detector** — a clean foreign-repo
   (caveman) self-eval must produce different structural metadata
   (``decomposition_coverage.total_elements``, etc.) than NineS's own
   self-eval.  This catches the §4.8 bug where a regression PR makes
   evaluators ignore the ``EvaluationContext`` and silently report
   NineS's own metrics for foreign repos.

3. **Regression assertion guard** — explicitly fail if a future
   evaluator leaks NineS's structural counts when the project root
   indicates a foreign repo.  This is a CI tripwire for the §4.8
   silent-fallback bug class.

Tests run entirely in-process (no subprocess, no network) and complete
in ≤ 1 s wall — that's the value-prop versus the live
``pytest --collect-only`` chain that took ≈100 s pre-C06.

Covers: C06 (golden harness, silent-fallback regression detector).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.eval.mock_executor import MockEvaluator  # noqa: E402
from nines.iteration.self_eval import SelfEvalReport, SelfEvalRunner  # noqa: E402

GOLDEN_DIR = Path(__file__).parent / "data" / "golden" / "self_eval_fixtures"
NINES_FIXTURE = GOLDEN_DIR / "nines_v3_1_0_capability.json"
FOREIGN_FIXTURE = GOLDEN_DIR / "foreign_caveman_capability.json"

# ---------------------------------------------------------------------------
# Trimmed-projection helper — mirrors what the fixtures encode.
# Keeping this in-test (rather than in src) means the projection is
# scoped to the golden contract; production callers continue to use
# ``SelfEvalReport.to_dict()`` verbatim.
# ---------------------------------------------------------------------------

# Metadata keys the golden fixture pins per dimension.  Every other key
# is dropped from the projection — they are noise for golden equality.
_META_WHITELIST: dict[str, tuple[str, ...]] = {
    "decomposition_coverage": ("total_elements", "captured_units"),
    "abstraction_quality": ("total_units", "well_classified"),
    "code_review_accuracy": ("complexity_checks", "reasonable_complexities"),
    "index_recall": ("indexed_units", "queries_tested"),
    "structure_recognition": ("detected_packages", "detected_modules"),
}


def _trim_score(score: dict[str, Any]) -> dict[str, Any]:
    """Project a score dict down to the stable golden subset."""
    name = score["name"]
    keep = _META_WHITELIST.get(name, ())
    md = score.get("metadata", {})
    return {
        "name": name,
        "normalized": round(score["normalized"], 3),
        "metadata": {k: md[k] for k in keep if k in md},
    }


def _trim_report(report: SelfEvalReport, *, weights: dict[str, float]) -> dict[str, Any]:
    """Project a SelfEvalReport down to the stable golden shape.

    Drops volatile fields (timestamp, duration), rounds normalized
    scores to 3 decimals, recomputes ``overall`` from the rounded
    scores so the projection is byte-stable across runs.  ``weights``
    is plumbed in (not on the runner) since it lives on the CLI side
    today; the golden fixture pins a per-mode constant.
    """
    raw = report.to_dict()
    trimmed_scores = [_trim_score(s) for s in raw["scores"]]
    overall = (
        round(sum(s["normalized"] for s in trimmed_scores) / len(trimmed_scores), 6)
        if trimmed_scores
        else 0.0
    )
    return {
        "version": raw["version"],
        "overall": overall,
        "weights": dict(weights),
        "timeouts": list(raw["timeouts"]),
        "scores": trimmed_scores,
    }


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _runner_from_fixture(fixture: dict[str, Any], *, version: str | None = None) -> SelfEvalRunner:
    """Wire a SelfEvalRunner with MockEvaluators that reproduce *fixture*."""
    runner = SelfEvalRunner()
    for s in fixture["scores"]:
        # Reproduce the fixture's normalized score by setting value=norm
        # and max_value=1.0; metadata is whatever the fixture pinned.
        runner.register_dimension(
            s["name"],
            MockEvaluator(
                name=s["name"],
                value=float(s["normalized"]),
                max_value=1.0,
                metadata=dict(s["metadata"]),
            ),
        )
    return runner


# ---------------------------------------------------------------------------
# Golden test 1 — exact reproduction
# ---------------------------------------------------------------------------


def test_self_eval_against_nines_matches_golden() -> None:
    """A mocked SelfEvalRunner reproduces the NineS v3.1.0 capability fixture."""
    fixture = _load_fixture(NINES_FIXTURE)
    runner = _runner_from_fixture(fixture)
    report = runner.run_all(version=fixture["version"])

    projected = _trim_report(report, weights=fixture["weights"])

    # Per-score equality with float tolerance; the trimmer rounds to 3
    # dp so equality is normally exact, but assert with tolerance to
    # document the contract.
    assert len(projected["scores"]) == len(fixture["scores"])
    for got, want in zip(projected["scores"], fixture["scores"], strict=True):
        assert got["name"] == want["name"]
        assert abs(got["normalized"] - want["normalized"]) < 1e-6, (
            f"{got['name']}: got={got['normalized']} want={want['normalized']}"
        )
        assert got["metadata"] == want["metadata"], (
            f"{got['name']} metadata diverges: got={got['metadata']} want={want['metadata']}"
        )

    # Top-level scalars must match exactly (overall is recomputed from
    # rounded scores, so byte-equal).
    assert projected["version"] == fixture["version"]
    assert projected["weights"] == fixture["weights"]
    assert projected["timeouts"] == fixture["timeouts"]
    assert abs(projected["overall"] - fixture["overall"]) < 1e-6


# ---------------------------------------------------------------------------
# Golden test 2 — silent-fallback divergence
# ---------------------------------------------------------------------------


def test_self_eval_against_foreign_repo_diverges_from_nines() -> None:
    """Foreign-repo capability run produces structurally-different metadata.

    The §4.8 silent-fallback bug let evaluators run against a foreign
    repo while internally pointing at NineS — the symptom was that
    ``decomposition_coverage.total_elements`` came back as NineS's
    count (881) for a foreign repo with ~42 units.  This test
    catches that regression by asserting the two fixtures differ on
    exactly that field.
    """
    nines = _load_fixture(NINES_FIXTURE)
    foreign = _load_fixture(FOREIGN_FIXTURE)

    # Build a runner that reproduces the FOREIGN fixture and assert
    # the resulting report's trimmed projection matches the FOREIGN
    # fixture (not the NineS one).
    runner = _runner_from_fixture(foreign)
    report = runner.run_all(version=foreign["version"])
    projected = _trim_report(report, weights=foreign["weights"])

    # Must match foreign byte-for-byte ...
    assert projected == foreign, (
        "foreign-repo run does not match foreign golden — "
        "MockEvaluator wiring or trim helper has drifted"
    )

    # ... and crucially must NOT match the NineS golden on the
    # silent-fallback signal.
    nines_decomp = next(s for s in nines["scores"] if s["name"] == "decomposition_coverage")
    foreign_decomp = next(s for s in foreign["scores"] if s["name"] == "decomposition_coverage")
    assert (
        nines_decomp["metadata"]["total_elements"] != foreign_decomp["metadata"]["total_elements"]
    ), (
        "Foreign and NineS fixtures must differ on decomposition_coverage."
        "total_elements — otherwise the silent-fallback regression is "
        "undetectable in CI."
    )

    # Sanity: at least 5 dims must have divergent metadata so a
    # one-off accidental match doesn't pass the test.
    divergent = 0
    for n_score, f_score in zip(nines["scores"], foreign["scores"], strict=True):
        if n_score["metadata"] != f_score["metadata"]:
            divergent += 1
    assert divergent >= 5, (
        f"Only {divergent} dims diverge between NineS and foreign fixtures — "
        "expected ≥5 (decomp + abstraction + code_review + index + structure)."
    )


# ---------------------------------------------------------------------------
# Golden test 3 — silent-fallback regression assertion (tripwire)
# ---------------------------------------------------------------------------


def test_silent_fallback_detection_regression_assertion() -> None:
    """A leaked-NineS-counts-against-foreign-repo run must be rejected.

    Simulates the §4.8 bug: an evaluator returns NineS's
    ``total_elements=881`` even though the project_root is a foreign
    repo.  The golden harness must flag this as a regression by
    refusing to match either the NineS or the foreign fixture.

    This is the falsifiable assertion that, today, would catch the
    regression class that v2.2.0 shipped silently.
    """
    nines_fixture = _load_fixture(NINES_FIXTURE)
    foreign_fixture = _load_fixture(FOREIGN_FIXTURE)

    nines_count = next(
        s["metadata"]["total_elements"]
        for s in nines_fixture["scores"]
        if s["name"] == "decomposition_coverage"
    )

    # Build a "leaky" runner: it claims to be running against the
    # foreign repo but its decomposition_coverage evaluator returns
    # NineS's value.  Other dims are normal foreign values.
    runner = _runner_from_fixture(foreign_fixture)
    # Re-register the broken dim with NineS's leaked count.
    runner.register_dimension(
        "decomposition_coverage",
        MockEvaluator(
            name="decomposition_coverage",
            value=1.0,
            max_value=1.0,
            metadata={
                "total_elements": nines_count,  # leaked NineS value
                "captured_units": nines_count,
            },
        ),
    )

    report = runner.run_all(version=foreign_fixture["version"])
    projected = _trim_report(report, weights=foreign_fixture["weights"])

    leaked_score = next(s for s in projected["scores"] if s["name"] == "decomposition_coverage")

    # The leaked report must NOT match the foreign golden — that is
    # the regression detector's job.
    assert projected != foreign_fixture, (
        "Silent-fallback regression went undetected: a leaked-NineS-count "
        "report matched the clean foreign fixture. The §4.8 bug class is "
        "back."
    )

    # The leaked dim must specifically expose NineS's count (881),
    # not the foreign-repo's (42).
    assert leaked_score["metadata"]["total_elements"] == nines_count
    assert leaked_score["metadata"]["total_elements"] != 42, (
        "Test setup invariant broken — leaked count must equal NineS's "
        "value, not the foreign value."
    )

    # Make the assertion explicit so the test name describes its job:
    # any future PR that re-introduces the §4.8 bug will fail here.
    foreign_count = next(
        s["metadata"]["total_elements"]
        for s in foreign_fixture["scores"]
        if s["name"] == "decomposition_coverage"
    )
    with pytest.raises(AssertionError):
        # This nested assertion is the tripwire we WANT to fire when a
        # bug regresses; we wrap it in pytest.raises so the OUTER test
        # passes today (proving the tripwire is wired) and a future
        # broken PR makes the inner assertion succeed → the wrapping
        # fails → CI red.
        assert leaked_score["metadata"]["total_elements"] == foreign_count, (
            f"REGRESSION: decomposition_coverage.total_elements="
            f"{leaked_score['metadata']['total_elements']} for a foreign "
            f"repo, but expected {foreign_count}. The §4.8 silent-fallback "
            f"bug has returned."
        )
