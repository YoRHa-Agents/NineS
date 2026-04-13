"""Multi-round evaluation runner with convergence detection and reliability metrics.

Runs evaluations multiple times (rounds), collecting per-round results and
computing reliability/convergence metrics across rounds.  Optionally isolates
each round inside a ``SandboxManager`` sandbox.

Covers: FR-116.
"""

from __future__ import annotations

import logging
import statistics
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nines.eval.metrics import ReliabilityCalculator
from nines.eval.models import EvalResult, TaskDefinition
from nines.eval.runner import EvalRunner, ExecutorFn

if TYPE_CHECKING:
    from nines.eval.scorers import ScorerProtocol
    from nines.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

_CONVERGENCE_WINDOW = 3


@dataclass
class RoundResult:
    """Result of a single evaluation round."""

    round_number: int
    results: list[EvalResult]
    composite_score: float
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "round_number": self.round_number,
            "results": [r.to_dict() for r in self.results],
            "composite_score": self.composite_score,
            "duration_ms": self.duration_ms,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoundResult:
        """Deserialize from dictionary."""
        return cls(
            round_number=data["round_number"],
            results=[EvalResult.from_dict(r) for r in data.get("results", [])],
            composite_score=data.get("composite_score", 0.0),
            duration_ms=data.get("duration_ms", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class MultiRoundReport:
    """Aggregated report across multiple evaluation rounds."""

    suite_id: str
    rounds: list[RoundResult]
    total_rounds: int
    mean_composite: float
    std_composite: float
    min_composite: float
    max_composite: float
    reliability: dict[str, float]
    converged: bool
    convergence_round: int | None
    total_duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "suite_id": self.suite_id,
            "rounds": [r.to_dict() for r in self.rounds],
            "total_rounds": self.total_rounds,
            "mean_composite": self.mean_composite,
            "std_composite": self.std_composite,
            "min_composite": self.min_composite,
            "max_composite": self.max_composite,
            "reliability": dict(self.reliability),
            "converged": self.converged,
            "convergence_round": self.convergence_round,
            "total_duration_ms": self.total_duration_ms,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MultiRoundReport:
        """Deserialize from dictionary."""
        return cls(
            suite_id=data["suite_id"],
            rounds=[RoundResult.from_dict(r) for r in data.get("rounds", [])],
            total_rounds=data.get("total_rounds", 0),
            mean_composite=data.get("mean_composite", 0.0),
            std_composite=data.get("std_composite", 0.0),
            min_composite=data.get("min_composite", 0.0),
            max_composite=data.get("max_composite", 0.0),
            reliability=data.get("reliability", {}),
            converged=data.get("converged", False),
            convergence_round=data.get("convergence_round"),
            total_duration_ms=data.get("total_duration_ms", 0.0),
            metadata=data.get("metadata", {}),
        )

    def per_task_summary(self) -> dict[str, dict[str, Any]]:
        """Per-task statistics (mean/std/min/max composite) across all rounds."""
        task_scores: dict[str, list[float]] = {}
        for rnd in self.rounds:
            for result in rnd.results:
                task_scores.setdefault(result.task_id, []).append(result.composite_score)

        summary: dict[str, dict[str, Any]] = {}
        for task_id, scores in task_scores.items():
            std = statistics.pstdev(scores) if len(scores) > 1 else 0.0
            summary[task_id] = {
                "mean": statistics.mean(scores),
                "std": std,
                "min": min(scores),
                "max": max(scores),
                "count": len(scores),
            }
        return summary


class MultiRoundRunner:
    """Runs evaluations over multiple rounds, tracking convergence and reliability."""

    def __init__(
        self,
        eval_runner: EvalRunner | None = None,
        sandbox_manager: SandboxManager | None = None,
        convergence_threshold: float = 0.02,
        min_rounds: int = 3,
        max_rounds: int = 10,
    ) -> None:
        """Initialize multi round runner."""
        if min_rounds < 1:
            raise ValueError("min_rounds must be >= 1")
        if max_rounds < min_rounds:
            raise ValueError("max_rounds must be >= min_rounds")
        if convergence_threshold < 0:
            raise ValueError("convergence_threshold must be >= 0")

        self._eval_runner = eval_runner or EvalRunner()
        self._sandbox_manager = sandbox_manager
        self._convergence_threshold = convergence_threshold
        self._min_rounds = min_rounds
        self._max_rounds = max_rounds

    def run(
        self,
        tasks: list[TaskDefinition],
        executor: ExecutorFn,
        scorers: list[ScorerProtocol],
        suite_id: str = "",
    ) -> MultiRoundReport:
        """Run multi-round evaluation."""
        if not suite_id:
            suite_id = uuid.uuid4().hex[:12]

        rounds: list[RoundResult] = []
        converged = False
        convergence_round: int | None = None
        total_start = time.monotonic()

        for round_num in range(1, self._max_rounds + 1):
            logger.info("Suite %s: starting round %d", suite_id, round_num)
            rnd = self._run_single_round(round_num, tasks, executor, scorers)
            rounds.append(rnd)
            logger.info(
                "Suite %s: round %d composite=%.4f duration=%.1fms",
                suite_id,
                round_num,
                rnd.composite_score,
                rnd.duration_ms,
            )

            if round_num >= self._min_rounds:
                converged, convergence_round = self._check_convergence(rounds)
                if converged:
                    logger.info("Suite %s: converged at round %d", suite_id, round_num)
                    break

        total_duration_ms = (time.monotonic() - total_start) * 1000
        composites = [r.composite_score for r in rounds]
        std = statistics.pstdev(composites) if len(composites) > 1 else 0.0
        reliability = self._compute_reliability(rounds)

        return MultiRoundReport(
            suite_id=suite_id,
            rounds=rounds,
            total_rounds=len(rounds),
            mean_composite=statistics.mean(composites),
            std_composite=std,
            min_composite=min(composites),
            max_composite=max(composites),
            reliability=reliability,
            converged=converged,
            convergence_round=convergence_round,
            total_duration_ms=total_duration_ms,
            metadata={
                "min_rounds": self._min_rounds,
                "max_rounds": self._max_rounds,
                "convergence_threshold": self._convergence_threshold,
                "sandboxed": self._sandbox_manager is not None,
            },
        )

    def _run_single_round(
        self,
        round_num: int,
        tasks: list[TaskDefinition],
        executor: ExecutorFn,
        scorers: list[ScorerProtocol],
    ) -> RoundResult:
        """Execute one round of evaluation."""
        if self._sandbox_manager is not None:
            return self._run_round_sandboxed(round_num, tasks, executor, scorers)
        return self._run_round_direct(round_num, tasks, executor, scorers)

    def _run_round_direct(
        self,
        round_num: int,
        tasks: list[TaskDefinition],
        executor: ExecutorFn,
        scorers: list[ScorerProtocol],
    ) -> RoundResult:
        """Run round direct."""
        start = time.monotonic()
        results = self._eval_runner.run(tasks, executor, scorers)
        duration_ms = (time.monotonic() - start) * 1000
        composite = self._aggregate_composite(results)
        return RoundResult(
            round_number=round_num,
            results=results,
            composite_score=composite,
            duration_ms=duration_ms,
            metadata={"sandboxed": False},
        )

    def _run_round_sandboxed(
        self,
        round_num: int,
        tasks: list[TaskDefinition],
        executor: ExecutorFn,
        scorers: list[ScorerProtocol],
    ) -> RoundResult:
        """Run round sandboxed."""
        assert self._sandbox_manager is not None
        ctx = self._sandbox_manager.create()
        try:
            start = time.monotonic()
            results = self._eval_runner.run(tasks, executor, scorers)
            duration_ms = (time.monotonic() - start) * 1000
            composite = self._aggregate_composite(results)
            return RoundResult(
                round_number=round_num,
                results=results,
                composite_score=composite,
                duration_ms=duration_ms,
                metadata={
                    "sandboxed": True,
                    "sandbox_id": ctx.sandbox_id,
                },
            )
        finally:
            self._sandbox_manager.destroy(ctx)

    def _check_convergence(self, rounds: list[RoundResult]) -> tuple[bool, int | None]:
        """Check if scores have converged using sliding window variance.

        Convergence is met when the population standard deviation of the
        last ``_CONVERGENCE_WINDOW`` rounds' composite scores falls below
        ``convergence_threshold``.
        """
        if len(rounds) < _CONVERGENCE_WINDOW:
            return False, None

        window = rounds[-_CONVERGENCE_WINDOW:]
        window_scores = [r.composite_score for r in window]
        std = statistics.pstdev(window_scores)

        if std < self._convergence_threshold:
            return True, rounds[-1].round_number
        return False, None

    def _compute_reliability(self, rounds: list[RoundResult]) -> dict[str, float]:
        """Compute reliability metrics across rounds using ReliabilityCalculator."""
        composites = [r.composite_score for r in rounds]
        n = len(composites)

        passing_threshold = 0.5
        c = sum(1 for s in composites if s >= passing_threshold)

        reliability: dict[str, float] = {
            "consistency": ReliabilityCalculator.consistency_score(composites),
        }

        for k in (1, 3, 5):
            if k <= n:
                reliability[f"pass_at_{k}"] = ReliabilityCalculator.pass_at_k(n, c, k)
                reliability[f"pass_power_{k}"] = ReliabilityCalculator.pass_power_k(n, c, k)

        return reliability

    def _compute_per_task_stats(self, rounds: list[RoundResult]) -> dict[str, dict[str, Any]]:
        """Compute per-task statistics across all rounds."""
        task_scores: dict[str, list[float]] = {}
        for rnd in rounds:
            for result in rnd.results:
                task_scores.setdefault(result.task_id, []).append(result.composite_score)

        summary: dict[str, dict[str, Any]] = {}
        for task_id, scores in task_scores.items():
            std = statistics.pstdev(scores) if len(scores) > 1 else 0.0
            summary[task_id] = {
                "mean": statistics.mean(scores),
                "std": std,
                "min": min(scores),
                "max": max(scores),
                "count": len(scores),
            }
        return summary

    @staticmethod
    def _aggregate_composite(results: list[EvalResult]) -> float:
        """Aggregate composite."""
        if not results:
            return 0.0
        return statistics.mean(r.composite_score for r in results)
