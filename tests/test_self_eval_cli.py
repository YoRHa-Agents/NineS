"""Tests for ``nines.cli.commands.self_eval`` — CLI rendering layer.

Covers release follow-up N1: ``_build_json_output`` must forward every
field of :class:`SelfEvalReport` so new fields (``timeouts`` from C04,
``context_fingerprint`` from C01, ...) automatically reach operators
without per-field CLI patches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.cli.commands.self_eval import (  # noqa: E402
    _build_json_output,
    _format_text_report,
)
from nines.iteration.self_eval import (  # noqa: E402
    DimensionScore,
    SelfEvalReport,
)

# ---------------------------------------------------------------------------
# N1 — CLI JSON exposes ``timeouts`` and other report-level fields
# ---------------------------------------------------------------------------


def _sample_report(
    *,
    timeouts: list[str],
    duration: float = 1.5,
) -> SelfEvalReport:
    """Build a minimal report fixture with a few scores + timeouts."""
    cap = DimensionScore(
        name="scoring_accuracy",
        value=0.8,
        max_value=1.0,
        metadata={"unit": "ratio"},
    )
    hyg = DimensionScore(
        name="lint_cleanliness",
        value=92.0,
        max_value=100.0,
        metadata={"unit": "score"},
    )
    return SelfEvalReport(
        scores=[cap, hyg],
        overall=0.86,
        version="v2.2.0-test",
        timestamp="2026-04-18T00:00:00+00:00",
        duration=duration,
        timeouts=list(timeouts),
    )


def test_build_json_output_includes_timeouts_when_present() -> None:
    """N1: when SelfEvalReport.timeouts is non-empty, the field must
    appear in the CLI JSON output as a list of dim names."""
    report = _sample_report(timeouts=["agent_analysis_quality"])

    cap_scores = [s for s in report.scores if s.name == "scoring_accuracy"]
    hyg_scores = [s for s in report.scores if s.name == "lint_cleanliness"]

    raw = _build_json_output(report, cap_scores, hyg_scores)
    payload = json.loads(raw)

    assert "timeouts" in payload, f"timeouts field missing — payload keys: {sorted(payload.keys())}"
    assert payload["timeouts"] == ["agent_analysis_quality"]


def test_build_json_output_includes_timeouts_as_empty_list_by_default() -> None:
    """N1: even when no evaluator timed out, the ``timeouts`` field
    must be present (empty list) so consumers can reliably access it
    without conditional defensive code."""
    report = _sample_report(timeouts=[])

    cap_scores = [s for s in report.scores if s.name == "scoring_accuracy"]
    hyg_scores = [s for s in report.scores if s.name == "lint_cleanliness"]

    raw = _build_json_output(report, cap_scores, hyg_scores)
    payload = json.loads(raw)

    assert "timeouts" in payload
    assert payload["timeouts"] == []


def test_build_json_output_preserves_legacy_top_level_fields() -> None:
    """The CLI-overlaid fields (``overall``, ``capability_mean``,
    ``hygiene_mean``, ``weights``, ``capability_scores``,
    ``hygiene_scores``, ``scores``) survive the report-forwarding
    refactor."""
    report = _sample_report(timeouts=["x"])

    cap_scores = [s for s in report.scores if s.name == "scoring_accuracy"]
    hyg_scores = [s for s in report.scores if s.name == "lint_cleanliness"]

    raw = _build_json_output(report, cap_scores, hyg_scores)
    payload = json.loads(raw)

    expected_keys = {
        "version",
        "timestamp",
        "duration",
        "overall",
        "capability_mean",
        "hygiene_mean",
        "weights",
        "capability_scores",
        "hygiene_scores",
        "scores",
        "timeouts",
    }
    assert expected_keys.issubset(payload.keys()), "missing keys: " + repr(
        expected_keys - set(payload.keys())
    )
    assert payload["weights"]["capability"] == 0.7
    assert payload["weights"]["hygiene"] == 0.3
    assert isinstance(payload["capability_scores"], list)
    assert isinstance(payload["hygiene_scores"], list)


def test_build_json_output_forwards_unknown_future_report_fields() -> None:
    """Forward-compat: any new key on ``SelfEvalReport.to_dict()`` must
    propagate to the JSON without a per-field CLI patch (the whole
    point of N1)."""
    report = _sample_report(timeouts=[])

    # Monkey-patch to_dict to simulate a future schema additions.
    original_to_dict = report.to_dict

    def _patched() -> dict:
        d = original_to_dict()
        d["context_fingerprint"] = "abc12345"  # imagined C01 field
        d["formula_version"] = 2  # already shipped by C09
        return d

    report.to_dict = _patched  # type: ignore[method-assign]

    raw = _build_json_output(report, [], [])
    payload = json.loads(raw)

    assert payload["context_fingerprint"] == "abc12345"
    assert payload["formula_version"] == 2


def test_build_json_output_overall_uses_cli_weighted_formula() -> None:
    """The CLI overlays its 0.7×cap + 0.3×hyg overall on top of the
    report's plain mean.  Verifying that overlay still happens after
    the refactor."""
    report = _sample_report(timeouts=[])

    cap_scores = [s for s in report.scores if s.name == "scoring_accuracy"]
    hyg_scores = [s for s in report.scores if s.name == "lint_cleanliness"]

    raw = _build_json_output(report, cap_scores, hyg_scores)
    payload = json.loads(raw)

    cap_mean = 0.8
    hyg_mean = 0.92
    expected = 0.7 * cap_mean + 0.3 * hyg_mean

    assert abs(payload["overall"] - expected) < 1e-6
    assert abs(payload["capability_mean"] - cap_mean) < 1e-6
    assert abs(payload["hygiene_mean"] - hyg_mean) < 1e-6


# ---------------------------------------------------------------------------
# N1 — text renderer surfaces the timeouts list too (operator-visible)
# ---------------------------------------------------------------------------


def test_format_text_report_surfaces_timeouts() -> None:
    """Text renderer mentions the timeouts when any dim breached."""
    report = _sample_report(timeouts=["agent_analysis_quality"])
    cap = [s for s in report.scores if s.name == "scoring_accuracy"]
    hyg = [s for s in report.scores if s.name == "lint_cleanliness"]
    text = _format_text_report(report, cap, hyg)
    assert "Timeouts (C04)" in text
    assert "agent_analysis_quality" in text


def test_format_text_report_omits_timeouts_line_when_empty() -> None:
    """No timeout mention when the report didn't record any."""
    report = _sample_report(timeouts=[])
    cap = [s for s in report.scores if s.name == "scoring_accuracy"]
    hyg = [s for s in report.scores if s.name == "lint_cleanliness"]
    text = _format_text_report(report, cap, hyg)
    assert "Timeouts" not in text


# ---------------------------------------------------------------------------
# C08 — --metrics-config option + weighted aggregate JSON output
# ---------------------------------------------------------------------------


def test_cli_metrics_config_loads_alternate_weights(tmp_path: Path) -> None:
    """--metrics-config PATH builds the registry from the supplied TOML."""
    from click.testing import CliRunner

    from nines.cli.main import cli

    custom = tmp_path / "weights.toml"
    custom.write_text(
        """
[groups]
hygiene = 1.0

[metrics.hygiene.code_coverage]
weight    = 0.50
threshold = [50.0, 95.0]

[metrics.hygiene.lint_cleanliness]
weight = 0.50
""",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "-f",
            "json",
            "self-eval",
            "--project-root",
            ".",
            "--src-dir",
            "src/nines",
            "--test-dir",
            "tests",
            "--capability-only",  # skip live hygiene evaluators (faster)
            "--metrics-config",
            str(custom),
            "--evaluator-timeout",
            "30",
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output

    payload = json.loads((out_dir / "self_eval_report.json").read_text())
    # The alternate registry has only hygiene metrics; capability run with
    # --capability-only never matches → group_means is empty (fall-through
    # to legacy ``overall`` for the headline number). weighted_overall is
    # 0.0 because no capability dim mapped to the custom registry's metrics
    # and we registered no hygiene evaluators.
    assert payload["weighted_overall"] == 0.0
    # metric_weights still snapshots the registry that was loaded.
    assert payload["metric_weights"] == {
        "code_coverage": 0.5,
        "lint_cleanliness": 0.5,
        "hygiene": 1.0,
    }


def test_cli_default_metrics_config_populates_weighted_overall(
    tmp_path: Path,
) -> None:
    """No --metrics-config → bundled TOML loads → weighted_overall populated."""
    from click.testing import CliRunner

    from nines.cli.main import cli

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "-f",
            "json",
            "self-eval",
            "--project-root",
            ".",
            "--src-dir",
            "src/nines",
            "--test-dir",
            "tests",
            "--capability-only",  # skip live hygiene for speed
            "--evaluator-timeout",
            "30",
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output

    payload = json.loads((out_dir / "self_eval_report.json").read_text())
    # capability dims registered → weighted_overall reflects capability mean
    # (the bundled meta-group has both capability=0.7 and hygiene=0.3, but
    # outer aggregation skips empty groups).
    assert payload["weighted_overall"] > 0.0
    assert "capability" in payload["group_means"]
    assert len(payload["metric_weights"]) >= 25
