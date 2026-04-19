"""Weighted MetricRegistry for self-evaluation (C08).

Provides per-dimension weight + threshold-based normalization so the
self-eval runner can compute a *calibrated* ``weighted_overall`` score
instead of the legacy unweighted mean (see
``.local/v2.2.0/design/03_track_c_differentiation.md`` C08).

Public surface
--------------

* :class:`Direction` — score direction (``MAXIMIZE`` higher-is-better,
  ``MINIMIZE`` lower-is-better).
* :class:`MetricDefinition` — registry entry: name, weight, direction,
  optional ``threshold = (min_acceptable, max_excellent)`` band,
  optional custom ``normalizer``, and group bucket.
* :class:`MetricRegistry` — orchestrator: ``register``,
  ``weight_sum_for_group``, ``normalized``, ``weighted_mean``,
  ``validate``, plus TOML loader.

Validation contract
-------------------

``MetricRegistry.validate()`` returns the list of error messages
(empty when the registry is internally consistent).  A registry is
*valid* when every group's per-metric weights sum to ``1.0 ± 0.01``
and no weight is negative.  The ``capability``/``hygiene`` outer split
is itself a group (``"_groups"``) whose entries sum to ``1.0``.

Backward compatibility
----------------------

Built-in evaluators that already return ``DimensionScore.normalized``
in ``[0, 1]`` keep working: when no ``threshold`` is configured for a
metric, ``normalized()`` falls back to ``value / max_value``.  Existing
``SelfEvalReport.overall`` (unweighted mean) is preserved alongside the
new ``weighted_overall`` field for one minor deprecation window.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

#: Tolerance used by :meth:`MetricRegistry.validate` when checking that
#: the per-group weight sums equal ``1.0``.  Set to ``0.01`` per the C08
#: design.
WEIGHT_SUM_TOLERANCE: float = 0.01

#: Reserved group name used to hold the *outer* group weights (e.g.
#: ``capability=0.70`` / ``hygiene=0.30``) so the registry can validate
#: them with the same machinery.
GROUPS_META_GROUP: str = "_groups"


class Direction(StrEnum):
    """Score direction for normalization."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass(frozen=True)
class MetricDefinition:
    """Definition of a single weighted metric.

    Parameters
    ----------
    name:
        Unique metric identifier (matches the ``DimensionScore.name``
        emitted by the evaluator).
    weight:
        Non-negative weight for this metric within its group.  All
        weights inside a group must sum to ``1.0 ± WEIGHT_SUM_TOLERANCE``
        for the registry to validate.
    direction:
        :class:`Direction.MAXIMIZE` (default — higher is better) or
        :class:`Direction.MINIMIZE` (lower is better).  Affects
        :meth:`MetricRegistry.normalized` when ``threshold`` is set.
    normalizer:
        Optional ``(value, max_value) -> float`` callable used when the
        metric needs custom math beyond the threshold band.  Takes
        precedence over ``threshold`` when provided.
    threshold:
        Optional ``(min_acceptable, max_excellent)`` band.  When set,
        :meth:`MetricRegistry.normalized` maps:

        * ``MAXIMIZE``: value ≤ min → 0; value ≥ max → 1; linear in
          between.
        * ``MINIMIZE``: value ≤ min → 1; value ≥ max → 0; linear in
          between.

    group:
        Group bucket used by :meth:`MetricRegistry.weight_sum_for_group`
        and :meth:`MetricRegistry.weighted_mean`.  Defaults to
        ``"default"``.
    """

    name: str
    weight: float
    direction: Direction = Direction.MAXIMIZE
    normalizer: Callable[[float, float], float] | None = None
    threshold: tuple[float, float] | None = None
    group: str = "default"

    def __post_init__(self) -> None:
        """Validate field-level constraints at construction time."""
        if not self.name:
            msg = "MetricDefinition.name must be a non-empty string"
            raise ValueError(msg)
        if self.weight < 0:
            msg = (
                f"MetricDefinition({self.name!r}).weight must be non-negative; "
                f"got {self.weight!r}"
            )
            raise ValueError(msg)
        if self.threshold is not None:
            a, b = self.threshold
            if a >= b:
                msg = (
                    f"MetricDefinition({self.name!r}).threshold must satisfy "
                    f"min < max; got ({a!r}, {b!r})"
                )
                raise ValueError(msg)


class MetricRegistry:
    """Registry of weighted, optionally-thresholded metric definitions.

    Usage
    -----
    ::

        registry = MetricRegistry()
        registry.register(MetricDefinition(
            name="code_coverage",
            weight=0.40,
            threshold=(70.0, 95.0),
            group="hygiene",
        ))
        ...
        errors = registry.validate()
        assert errors == []
        score = registry.weighted_mean("hygiene", {"code_coverage": 92.0, ...})
    """

    def __init__(self) -> None:
        """Initialise an empty registry."""
        self._metrics: dict[str, MetricDefinition] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, definition: MetricDefinition) -> None:
        """Register *definition* under its ``name`` key.

        Re-registering the same ``name`` overwrites the prior entry.  An
        INFO log is emitted on overwrite so misconfigurations surface
        without silent drops.
        """
        if definition.name in self._metrics:
            logger.info(
                "MetricRegistry: overwriting prior definition for %r",
                definition.name,
            )
        self._metrics[definition.name] = definition

    def get(self, name: str) -> MetricDefinition | None:
        """Return the registered definition for *name* (or ``None``)."""
        return self._metrics.get(name)

    def metrics(self) -> dict[str, MetricDefinition]:
        """Return a shallow copy of the internal name→definition map."""
        return dict(self._metrics)

    def groups(self) -> list[str]:
        """Return the sorted list of group identifiers known to the registry."""
        return sorted({d.group for d in self._metrics.values()})

    # ------------------------------------------------------------------
    # Aggregation primitives
    # ------------------------------------------------------------------

    def weight_sum_for_group(self, group: str) -> float:
        """Return the sum of weights for metrics in *group*."""
        return sum(d.weight for d in self._metrics.values() if d.group == group)

    def normalized(
        self,
        name: str,
        value: float,
        *,
        max_value: float = 1.0,
    ) -> float:
        """Return the calibrated ``[0, 1]`` score for ``name``.

        Resolution order:

        1. If ``definition.normalizer`` is set, call it as
           ``normalizer(value, max_value)`` and clamp to ``[0, 1]``.
        2. Else if ``definition.threshold`` is set, apply the band
           per :class:`Direction`.
        3. Else fall back to ``value / max_value`` (clamped).

        Unknown metric names raise :class:`KeyError` so silent
        misconfigurations cannot leak through.
        """
        if name not in self._metrics:
            msg = f"MetricRegistry has no definition for {name!r}"
            raise KeyError(msg)
        defn = self._metrics[name]

        if defn.normalizer is not None:
            raw = float(defn.normalizer(value, max_value))
            return max(0.0, min(1.0, raw))

        if defn.threshold is not None:
            min_v, max_v = defn.threshold
            if defn.direction is Direction.MINIMIZE:
                if value <= min_v:
                    return 1.0
                if value >= max_v:
                    return 0.0
                return 1.0 - (value - min_v) / (max_v - min_v)
            # MAXIMIZE
            if value <= min_v:
                return 0.0
            if value >= max_v:
                return 1.0
            return (value - min_v) / (max_v - min_v)

        # No threshold and no normalizer — value is already on the
        # ``[0, max_value]`` scale of the underlying evaluator.
        if max_value <= 0:
            return 0.0
        return max(0.0, min(1.0, value / max_value))

    def weighted_mean(
        self,
        group: str,
        scores: dict[str, float],
    ) -> float:
        """Return the weight-normalised mean of *scores* in *group*.

        ``scores`` maps metric name → already-normalised ``[0, 1]``
        score.  Missing metrics are skipped (their weight is excluded
        from the denominator) and an INFO log is emitted so callers
        notice partial coverage.  When *group* has zero matched weight
        the result is ``0.0`` (matches the legacy ``run_all`` semantics
        for an empty score list).
        """
        total_weight = 0.0
        weighted_sum = 0.0
        for defn in self._metrics.values():
            if defn.group != group:
                continue
            if defn.name not in scores:
                logger.info(
                    "weighted_mean(%r): no score supplied for metric %r; "
                    "excluding it from the denominator",
                    group,
                    defn.name,
                )
                continue
            total_weight += defn.weight
            weighted_sum += defn.weight * float(scores[defn.name])
        if total_weight <= 0:
            return 0.0
        return weighted_sum / total_weight

    # ------------------------------------------------------------------
    # Self-validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation error messages (empty == valid).

        Every non-empty group must have weights summing to
        ``1.0 ± WEIGHT_SUM_TOLERANCE``.  Negative weights are caught at
        :class:`MetricDefinition` construction time but re-checked here
        for completeness.
        """
        errors: list[str] = []
        per_group: dict[str, float] = {}
        for defn in self._metrics.values():
            if defn.weight < 0:
                errors.append(
                    f"metric {defn.name!r} in group {defn.group!r} has "
                    f"negative weight {defn.weight!r}"
                )
            per_group[defn.group] = per_group.get(defn.group, 0.0) + defn.weight

        for group, total in sorted(per_group.items()):
            if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
                errors.append(
                    f"group {group!r} weights sum to {total:.6f} "
                    f"(expected 1.0 ± {WEIGHT_SUM_TOLERANCE})"
                )
        return errors

    # ------------------------------------------------------------------
    # Convenience: serialisation + TOML loader
    # ------------------------------------------------------------------

    def weights_dict(self) -> dict[str, float]:
        """Return a plain ``{name: weight}`` map for report transparency."""
        return {name: defn.weight for name, defn in self._metrics.items()}

    @classmethod
    def from_toml(cls, path: str | Path) -> MetricRegistry:
        """Load a registry from a TOML file.

        Schema::

            [groups]
            capability = 0.70
            hygiene    = 0.30

            [metrics.capability.scoring_accuracy]
            weight     = 0.10
            direction  = "maximize"
            threshold  = [0.7, 1.05]

            [metrics.hygiene.code_coverage]
            weight    = 0.40
            threshold = [70.0, 95.0]

        The ``[groups]`` table populates the reserved
        :data:`GROUPS_META_GROUP` so :meth:`validate` will check that
        the outer split sums to ``1.0`` as well.
        """
        path = Path(path)
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricRegistry:
        """Build a registry from a parsed TOML/dict structure (see :meth:`from_toml`)."""
        registry = cls()
        groups = data.get("groups", {}) or {}
        for group_name, weight in groups.items():
            registry.register(
                MetricDefinition(
                    name=str(group_name),
                    weight=float(weight),
                    group=GROUPS_META_GROUP,
                ),
            )

        metrics_table = data.get("metrics", {}) or {}
        for group_name, group_metrics in metrics_table.items():
            if not isinstance(group_metrics, dict):
                continue
            for metric_name, raw in group_metrics.items():
                if not isinstance(raw, dict):
                    continue
                direction_str = str(raw.get("direction", "maximize")).lower()
                try:
                    direction = Direction(direction_str)
                except ValueError as exc:
                    msg = (
                        f"metric {metric_name!r} in group {group_name!r}: "
                        f"unknown direction {direction_str!r}"
                    )
                    raise ValueError(msg) from exc

                threshold_raw = raw.get("threshold")
                threshold: tuple[float, float] | None
                if threshold_raw is None:
                    threshold = None
                else:
                    if (
                        not isinstance(threshold_raw, (list, tuple))
                        or len(threshold_raw) != 2
                    ):
                        msg = (
                            f"metric {metric_name!r} in group {group_name!r}: "
                            f"threshold must be a 2-element list, got "
                            f"{threshold_raw!r}"
                        )
                        raise ValueError(msg)
                    threshold = (float(threshold_raw[0]), float(threshold_raw[1]))

                registry.register(
                    MetricDefinition(
                        name=str(metric_name),
                        weight=float(raw.get("weight", 0.0)),
                        direction=direction,
                        threshold=threshold,
                        group=str(group_name),
                    ),
                )
        return registry


@dataclass
class _RegistryDefaults:
    """Marker container for ``default_registry_path`` resolution."""

    package_data: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
        / "data"
        / "self_eval_metrics.toml"
    )


def default_registry_path() -> Path:
    """Return the absolute path to the bundled ``self_eval_metrics.toml``."""
    return _RegistryDefaults().package_data


def load_default_registry() -> MetricRegistry:
    """Convenience: load the bundled :data:`default_registry_path` TOML."""
    return MetricRegistry.from_toml(default_registry_path())
