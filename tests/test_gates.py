"""Tests for ``nines.iteration.gates`` — C07 quality-gate state machine.

Covers the four built-in gates (graph verification, economics score,
self-eval coverage, regression), the :class:`GateRunner` advisory /
strict mode policy, the :meth:`GateRunner.summary` aggregator, and
the :class:`GateRegistry` default factory.
"""

from __future__ import annotations

from typing import Any

from nines.iteration.gates import (
    EconomicsScoreGate,
    GateRegistry,
    GateResult,
    GateRunner,
    GateStatus,
    GraphVerificationGate,
    QualityGate,
    RegressionGate,
    SelfEvalCoverageGate,
    Snapshot,
)
from nines.iteration.self_eval import DimensionScore, SelfEvalReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_self_eval_report(
    overall: float,
    *,
    version: str = "v3.2.0",
) -> SelfEvalReport:
    """Build a minimal :class:`SelfEvalReport` for gate tests."""
    return SelfEvalReport(
        version=version,
        timestamp="2026-04-18T16:00:00Z",
        duration=10.0,
        scores=[
            DimensionScore(
                name="dim1",
                value=overall,
                max_value=1.0,
                metadata={},
            ),
        ],
        overall=overall,
        timeouts=[],
    )


class _FakeAnalysisReport:
    """Object with a ``.metrics`` dict mimicking ``AnalysisResult``."""

    def __init__(self, metrics: dict[str, Any]) -> None:
        self.metrics = metrics


def _make_graph_metrics(
    *,
    passed: bool,
    critical_issues: int = 0,
) -> dict[str, Any]:
    issues = [
        {
            "severity": "critical",
            "category": "referential_integrity",
            "message": f"synthetic crit #{i}",
            "node_ids": [],
        }
        for i in range(critical_issues)
    ]
    return {
        "knowledge_graph": {
            "verification": {
                "passed": passed,
                "issues": issues,
                "node_count": 10,
                "edge_count": 9,
                "layer_coverage_pct": 100.0,
                "orphan_count": 0,
                "metadata": {},
            }
        }
    }


def _make_economics_metrics(score: float) -> dict[str, Any]:
    return {
        "agent_impact": {
            "economics": {
                "economics_score": score,
                "formula_version": 2,
                "overhead_tokens": 100,
                "estimated_savings_ratio": 0.6,
                "mechanism_count": 4,
                "agent_facing_files": 3,
                "total_agent_context_tokens": 5000,
                "break_even_interactions": 6,
                "per_interaction_savings_tokens": 50,
                "expected_retention_rate": 0.85,
                "mechanism_diversity_factor": 1.2,
            }
        }
    }


# ---------------------------------------------------------------------------
# GraphVerificationGate
# ---------------------------------------------------------------------------


def test_graph_verification_gate_passes_on_clean_report() -> None:
    """Clean verification (passed=True, 0 critical issues) → PASSED."""
    report = _FakeAnalysisReport(
        metrics=_make_graph_metrics(passed=True, critical_issues=0),
    )
    gate = GraphVerificationGate(threshold_critical_issues=0)
    result = gate.evaluate(report)

    assert isinstance(result, GateResult)
    assert result.gate_name == "graph_verification"
    assert result.status == GateStatus.PASSED
    assert result.metric_value == 0.0
    assert result.threshold == 0.0
    assert result.metadata["verification_passed"] is True


def test_graph_verification_gate_fails_on_critical_issues() -> None:
    """Critical issues exceeding the threshold → FAILED."""
    report = _FakeAnalysisReport(
        metrics=_make_graph_metrics(passed=False, critical_issues=3),
    )
    gate = GraphVerificationGate(threshold_critical_issues=0)
    result = gate.evaluate(report)

    assert result.status == GateStatus.FAILED
    assert result.metric_value == 3.0
    assert result.metadata["verification_passed"] is False
    assert result.metadata["critical_count"] == 3
    assert "critical_issues=3" in result.verdict


# ---------------------------------------------------------------------------
# EconomicsScoreGate
# ---------------------------------------------------------------------------


def test_economics_score_gate_passes_above_threshold() -> None:
    """economics_score above the floor → PASSED."""
    report = _FakeAnalysisReport(metrics=_make_economics_metrics(score=0.42))
    gate = EconomicsScoreGate(min_score=0.10)
    result = gate.evaluate(report)

    assert result.status == GateStatus.PASSED
    assert result.metric_value == 0.42
    assert result.threshold == 0.10
    assert result.metadata["formula_version"] == 2


def test_economics_score_gate_fails_below_threshold() -> None:
    """economics_score below the floor → FAILED."""
    report = _FakeAnalysisReport(metrics=_make_economics_metrics(score=0.05))
    gate = EconomicsScoreGate(min_score=0.10)
    result = gate.evaluate(report)

    assert result.status == GateStatus.FAILED
    assert result.metric_value == 0.05
    assert "0.0500" in result.verdict
    assert "0.1000" in result.verdict


# ---------------------------------------------------------------------------
# SelfEvalCoverageGate
# ---------------------------------------------------------------------------


def test_self_eval_coverage_gate_passes_at_threshold() -> None:
    """overall == threshold → PASSED (>=, not >)."""
    report = _make_self_eval_report(overall=0.85)
    gate = SelfEvalCoverageGate(min_overall=0.85)
    result = gate.evaluate(report)

    assert result.status == GateStatus.PASSED
    assert result.metric_value == 0.85


def test_self_eval_coverage_gate_fails_below() -> None:
    """overall below threshold → FAILED."""
    report = _make_self_eval_report(overall=0.30)
    gate = SelfEvalCoverageGate(min_overall=0.85)
    result = gate.evaluate(report)

    assert result.status == GateStatus.FAILED
    assert result.metric_value == 0.30
    assert "0.3000" in result.verdict


# ---------------------------------------------------------------------------
# RegressionGate
# ---------------------------------------------------------------------------


def test_regression_gate_passes_on_stable_history() -> None:
    """Stable history → current within tolerance → PASSED."""
    history = [
        Snapshot(version="v1", overall=0.90),
        Snapshot(version="v2", overall=0.91),
        Snapshot(version="v3", overall=0.92),
    ]
    gate = RegressionGate(history=history, regression_threshold=0.05)
    report = _make_self_eval_report(overall=0.90)
    result = gate.evaluate(report)

    assert result.status == GateStatus.PASSED
    assert result.metadata["history_size"] == 3


def test_regression_gate_fails_on_drop_beyond_threshold() -> None:
    """Current score dropping more than threshold below mean → FAILED."""
    history = [
        Snapshot(version="v1", overall=0.90),
        Snapshot(version="v2", overall=0.92),
        Snapshot(version="v3", overall=0.94),
    ]
    gate = RegressionGate(history=history, regression_threshold=0.05)
    report = _make_self_eval_report(overall=0.60)
    result = gate.evaluate(report)

    assert result.status == GateStatus.FAILED
    assert result.metric_value > 0.05
    assert "dropped" in result.verdict


# ---------------------------------------------------------------------------
# GateRunner advisory / strict / summary
# ---------------------------------------------------------------------------


def test_gate_runner_advisory_mode_does_not_block() -> None:
    """A failed gate in advisory mode → severity warn; should_abort False."""
    report = _make_self_eval_report(overall=0.20)
    runner = GateRunner(
        gates=[SelfEvalCoverageGate(min_overall=0.85)],
        advisory_mode=True,
    )
    results = runner.evaluate_all(report)

    assert len(results) == 1
    assert results[0].status == GateStatus.FAILED
    assert results[0].severity == "warn"
    assert runner.should_abort(results) is False
    summary = runner.summary(results)
    assert summary["warned"] == 1
    assert summary["blocked"] == 0
    assert summary["advisory_mode"] is True


def test_gate_runner_strict_mode_blocks_on_failed() -> None:
    """A failed gate in strict mode → severity block; should_abort True."""
    report = _make_self_eval_report(overall=0.20)
    runner = GateRunner(
        gates=[SelfEvalCoverageGate(min_overall=0.85)],
        advisory_mode=False,
    )
    results = runner.evaluate_all(report)

    assert len(results) == 1
    assert results[0].status == GateStatus.FAILED
    assert results[0].severity == "block"
    assert runner.should_abort(results) is True
    summary = runner.summary(results)
    assert summary["blocked"] == 1
    assert summary["advisory_mode"] is False


def test_gate_runner_summary_aggregates_correctly() -> None:
    """Summary tallies passed/failed/bypassed correctly across mixed gates."""
    history = [
        Snapshot(version="v1", overall=0.90),
        Snapshot(version="v2", overall=0.92),
        Snapshot(version="v3", overall=0.94),
    ]
    runner = GateRunner(
        gates=[
            SelfEvalCoverageGate(min_overall=0.85),  # pass on 0.90
            SelfEvalCoverageGate(min_overall=0.99),  # fail on 0.90
            RegressionGate(  # bypass: insufficient history
                history=[Snapshot(version="x", overall=0.9)],
                regression_threshold=0.05,
            ),
            RegressionGate(  # pass: stable history
                history=history,
                regression_threshold=0.05,
            ),
        ],
        advisory_mode=True,
    )

    report = _make_self_eval_report(overall=0.90)
    results = runner.evaluate_all(report)
    summary = runner.summary(results)

    assert summary["total"] == 4
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["bypassed"] == 1
    assert summary["warned"] == 1
    assert summary["blocked"] == 0
    assert len(summary["results"]) == 4


# ---------------------------------------------------------------------------
# GateRegistry
# ---------------------------------------------------------------------------


def test_gate_registry_default_factory_returns_4_gates() -> None:
    """Default registry factory ships exactly the 4 built-in gates."""
    runner = GateRegistry.default_runner()
    assert isinstance(runner, GateRunner)
    assert len(runner.gates) == 4

    names = {gate.name for gate in runner.gates}
    assert names == {
        "graph_verification",
        "economics_score",
        "self_eval_coverage",
        "regression",
    }
    # advisory_mode default is True per acceptance criteria
    assert runner.advisory_mode is True

    # And custom gates can still be registered without affecting
    # default_runner's contents.
    registry = GateRegistry()

    class _MyGate(QualityGate):
        name = "custom"

        def evaluate(self, report: Any) -> GateResult:  # pragma: no cover
            raise AssertionError("not invoked")

    registry.register("custom", _MyGate)
    assert "custom" in registry.names()
    assert isinstance(registry.create("custom"), _MyGate)
