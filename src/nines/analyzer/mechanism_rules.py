"""Rule-based mechanism detection registry (C11a — NineS v3.2.3).

Each :class:`MechanismRule` is a self-contained declarative spec describing
one Agent-influence mechanism.  The legacy 5 mechanisms (``behavioral_rules``,
``token_compression``, ``safety_guardrails``, ``multi_platform_sync``,
``drift_prevention``) are preserved with **stricter evidence predicates** so
they only fire when substantive evidence is present, instead of always firing
on any Agent-facing file as in v3.2.2 and earlier (§4.3 baseline).

Six new ContextOS-derived mechanisms (``active_forgetting``,
``reasoning_depth_calibration``, ``productive_contradiction``,
``churn_aware_routing``, ``self_healing_index``, ``skillbook_evolution``)
extend the taxonomy so different repos can surface different mechanism subsets
— closing the §4.3 / §4.4 gap that "all 3 reference samples emit the same 5
mechanisms with confidence 1.0".

Confidence scoring
------------------
The :meth:`MechanismRule.confidence_estimator` returns a score in
``[0.0, 1.0]``; the analyzer emits a mechanism only when the score is
**strictly greater** than :attr:`MechanismRule.min_confidence` (default 0.3).
Score combines:

1. **Indicator density**: average fraction of distinct indicators hit per file.
2. **File coverage**: small bonus that saturates once enough files match.
3. **Counter-indicator penalty**: subtracts when the file contains explicit
   *negation* phrases for the rule.

This is rule-based ONLY; no LLM judge is called from this module.  C11b (LLM
fallback) is deferred to a separate release.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class FileMatch:
    """Per-file evidence for one :class:`MechanismRule`.

    Attributes
    ----------
    path:
        Repository-relative path of the matched file.
    indicator_hits:
        Number of distinct positive indicators (and path-hint bonus) found
        in the file content.
    counter_hits:
        Number of distinct counter-indicators found.
    content_length:
        Length (in characters) of the lowercased content scanned.
    """

    path: str
    indicator_hits: int
    counter_hits: int
    content_length: int

    @property
    def density(self) -> float:
        """Indicator hits per 1 000 characters of content."""
        if self.content_length <= 0:
            return 0.0
        return self.indicator_hits / max(1.0, self.content_length / 1000.0)


@dataclass(frozen=True)
class MechanismRule:
    """Declarative spec for one Agent-influence mechanism.

    Attributes
    ----------
    name:
        Mechanism slug (stable across reports).
    category:
        Taxonomy bucket — legacy 5 use the original v3.2.2 category names,
        new ContextOS rules introduce categories such as
        ``context_pruning`` / ``meta_reasoning`` / ``validation`` /
        ``context_routing`` / ``indexing`` / ``in_context_learning``.
    description:
        Human-readable description shown in reports.
    indicators:
        Tuple of lowercased substrings that count as positive evidence.
    counter_indicators:
        Tuple of lowercased substrings that count as negative evidence
        (penalize the confidence score).
    path_hints:
        Optional substrings of the relative path; matching adds one
        synthetic positive hit (useful for `.cursor/`, `.claude/`, etc.).
    min_indicator_hits_per_file:
        File-level predicate threshold — a file contributes evidence only
        when ``effective_hits >= this``.  Set to 1 for very specific
        phrase-only rules (e.g. ``self_healing_index``).
    min_files:
        Aggregate predicate threshold — emit a mechanism only when at
        least this many files match.
    min_confidence:
        Confidence gate — emit only when ``confidence > min_confidence``.
    token_impact_sign:
        ``+1`` for mechanisms that *add* to Agent context, ``-1`` for
        mechanisms that *save* tokens (currently only context-compression
        category).
    source:
        ``"legacy"`` for the original v3.2.2 five, ``"contextos"`` for the
        new ContextOS-derived rules.  Used for downstream filtering and
        backwards-compat shims.
    """

    name: str
    category: str
    description: str
    indicators: tuple[str, ...]
    counter_indicators: tuple[str, ...] = ()
    path_hints: tuple[str, ...] = ()
    min_indicator_hits_per_file: int = 2
    min_files: int = 1
    min_confidence: float = 0.3
    token_impact_sign: int = 1
    source: str = "default"

    def match_file(self, rel_path: str, content_lower: str) -> FileMatch | None:
        """Test whether one artifact provides evidence for this rule.

        Parameters
        ----------
        rel_path:
            Repository-relative path of the file (used for path hints).
        content_lower:
            Lowercased file content.

        Returns
        -------
        FileMatch | None
            A match descriptor when the file passes the per-file predicate,
            else ``None``.
        """
        if not content_lower:
            return None
        positive_hits = sum(1 for ind in self.indicators if ind in content_lower)
        path_lower = rel_path.lower()
        path_bonus = 1 if any(hint in path_lower for hint in self.path_hints) else 0
        effective_hits = positive_hits + path_bonus
        if effective_hits < self.min_indicator_hits_per_file:
            return None
        counter_hits = sum(1 for ind in self.counter_indicators if ind in content_lower)
        return FileMatch(
            path=rel_path,
            indicator_hits=effective_hits,
            counter_hits=counter_hits,
            content_length=len(content_lower),
        )

    def evidence_predicate(self, matches: list[FileMatch]) -> bool:
        """Return True iff there are enough matching files to emit.

        Parameters
        ----------
        matches:
            All :class:`FileMatch` objects collected for this rule.
        """
        return len(matches) >= self.min_files

    def confidence_estimator(self, matches: list[FileMatch]) -> float:
        """Score the rule's confidence in ``[0.0, 1.0]``.

        Anchored at ``0.40`` for any predicate-passing match so that the
        ``min_confidence > 0.3`` gate is comfortably crossed by typical
        evidence; counter-indicators can still drag the score below the
        gate when they dominate.

        Parameters
        ----------
        matches:
            All :class:`FileMatch` objects collected for this rule.
        """
        if not matches:
            return 0.0
        max_indicators = max(len(self.indicators), 1)
        avg_hit_fraction = sum(
            min(1.0, m.indicator_hits / max_indicators) for m in matches
        ) / len(matches)
        coverage_bonus = min(0.25, 0.05 * len(matches))
        avg_counter = sum(m.counter_hits for m in matches) / len(matches)
        counter_penalty = min(0.30, 0.10 * avg_counter)
        score = 0.40 + 0.50 * avg_hit_fraction + coverage_bonus - counter_penalty
        return round(max(0.0, min(1.0, score)), 2)

    def magnitude_estimator(self, total_content_tokens: int) -> int:
        """Signed token impact estimate.

        Parameters
        ----------
        total_content_tokens:
            Sum of estimated tokens across all evidence files (positive).
        """
        return self.token_impact_sign * abs(int(total_content_tokens))


# ---------------------------------------------------------------------------
# Default rule set — legacy 5 (with stricter predicates) + 6 ContextOS rules
# ---------------------------------------------------------------------------

_LEGACY_BEHAVIORAL = MechanismRule(
    name="behavioral_rules",
    category="behavioral_instruction",
    description=(
        "Provides behavioral rules and conventions that shape "
        "Agent output style and decision-making"
    ),
    indicators=(
        "instruction",
        "rule",
        "prompt",
        "convention",
        "guideline",
        "must",
        "always",
        "never",
        "should",
        "style",
    ),
    min_indicator_hits_per_file=2,
    source="legacy",
)

_LEGACY_COMPRESSION = MechanismRule(
    name="token_compression",
    category="context_compression",
    description=(
        "Reduces token usage through compression, abbreviation, "
        "or compact representation strategies"
    ),
    indicators=(
        "compress",
        "token",
        "compact",
        "terse",
        "concise",
        "abbreviat",
        "shorten",
        "minif",
        "strip",
        "reduc",
    ),
    counter_indicators=("verbose", "elaborate", "expand"),
    min_indicator_hits_per_file=2,
    token_impact_sign=-1,
    source="legacy",
)

_LEGACY_SAFETY = MechanismRule(
    name="safety_guardrails",
    category="safety",
    description=(
        "Implements safety guardrails such as confirmation prompts, "
        "auto-clarity checks, or irreversible-action protections"
    ),
    indicators=(
        "safety",
        "security",
        "irreversible",
        "danger",
        "warning",
        "fallback",
        "restore",
        "backup",
        "auto-clarity",
    ),
    min_indicator_hits_per_file=2,
    source="legacy",
)

_LEGACY_DISTRIBUTION = MechanismRule(
    name="multi_platform_sync",
    category="distribution",
    description=(
        "Distributes Agent configuration across multiple platforms "
        "or synchronizes rules between IDE integrations"
    ),
    indicators=(
        "sync",
        "deploy",
        "publish",
        "multi-agent",
        "distribute",
        "platform",
        "cross-ide",
        "workflow",
        "ci",
    ),
    path_hints=(
        ".cursor/",
        ".claude/",
        ".windsurf/",
        ".codex/",
        ".clinerules",
        "github/copilot",
    ),
    min_indicator_hits_per_file=2,
    source="legacy",
)

_LEGACY_PERSISTENCE = MechanismRule(
    name="drift_prevention",
    category="persistence",
    description=(
        "Enforces behavioral persistence through drift prevention, "
        "mode locking, or invariant enforcement"
    ),
    indicators=(
        "drift",
        "enforce",
        "persist",
        "mode lock",
        "invariant",
        "constraint",
        "assert",
        "guard",
    ),
    min_indicator_hits_per_file=2,
    source="legacy",
)

# ---------------------------------------------------------------------------
# ContextOS-derived rules (per `.local/v2.2.0/survey/02_reference_repo_catalog.md`
# entry P7).  Each captures a cognitive primitive that NineS could not
# previously distinguish from the legacy 5.
# ---------------------------------------------------------------------------

_CONTEXTOS_FORGETTING = MechanismRule(
    name="active_forgetting",
    category="context_pruning",
    description=(
        "Actively prunes or evicts stale context — TTL/eviction/LRU "
        "patterns and explicit forgetting policies"
    ),
    indicators=(
        "ttl",
        "evict",
        "lru",
        "forget",
        "prune",
        "expire",
        "garbage collect",
        "context window",
        "drop old",
    ),
    counter_indicators=("never expire", "infinite memory", "unlimited"),
    # Single-hit threshold: each indicator is a specific cognitive primitive
    # (per ContextOS taxonomy), so one hit per file is meaningful evidence.
    min_indicator_hits_per_file=1,
    source="contextos",
)

_CONTEXTOS_DEPTH = MechanismRule(
    name="reasoning_depth_calibration",
    category="meta_reasoning",
    description=(
        "Calibrates reasoning depth — multi-pass loops, "
        "step-by-step / chain-of-thought modulation, or depth flags"
    ),
    indicators=(
        "step-by-step",
        "multi-pass",
        "reasoning depth",
        "chain of thought",
        "deliberat",
        "depth flag",
        "deep think",
        "extended thinking",
        "thinking budget",
    ),
    # Single-hit threshold: each indicator is a domain-specific phrase from
    # the ContextOS meta-reasoning taxonomy.
    min_indicator_hits_per_file=1,
    source="contextos",
)

_CONTEXTOS_CONTRADICTION = MechanismRule(
    name="productive_contradiction",
    category="validation",
    description=(
        "Surfaces and resolves contradictions through cross-checking, "
        "auditing, or independent validation"
    ),
    indicators=(
        "contradict",
        "cross-check",
        "double-check",
        "self-check",
        "consistency check",
        "audit",
        "validate",
        "review",
        "discrepanc",
    ),
    min_indicator_hits_per_file=2,
    source="contextos",
)

_CONTEXTOS_CHURN = MechanismRule(
    name="churn_aware_routing",
    category="context_routing",
    description=(
        "Routes context based on staleness/freshness signals — "
        "churn-aware retrieval and cache invalidation"
    ),
    indicators=(
        "stale",
        "churn",
        "freshness",
        "rerank",
        "invalidat",
        "outdated",
        "drift detect",
        "freshness check",
        "cache invalidation",
        "cache miss",
    ),
    # Single-hit threshold: each indicator is a context-routing-specific term.
    min_indicator_hits_per_file=1,
    source="contextos",
)

_CONTEXTOS_HEALING = MechanismRule(
    name="self_healing_index",
    category="indexing",
    description=(
        "Maintains an index that detects and repairs its own "
        "corruption or drift (re-index, rebuild, heal)"
    ),
    indicators=(
        "re-index",
        "reindex",
        "rebuild index",
        "self-heal",
        "self heal",
        "auto-rebuild",
        "index repair",
        "heal index",
        "index drift",
        "index recovery",
    ),
    # Specific phrases — a single hit is enough to consider this evidence
    min_indicator_hits_per_file=1,
    source="contextos",
)

_CONTEXTOS_SKILLBOOK = MechanismRule(
    name="skillbook_evolution",
    category="in_context_learning",
    description=(
        "Maintains and evolves a learnable skill database — skillbook, "
        "in-context learned strategies, transparent skill accumulation"
    ),
    indicators=(
        "skillbook",
        "skill book",
        "skill database",
        "skill library",
        "in-context learn",
        "skill evolution",
        "learned strateg",
        "skill registry",
        "skill catalog",
    ),
    min_indicator_hits_per_file=1,
    source="contextos",
)


DEFAULT_MECHANISM_RULES: Final[tuple[MechanismRule, ...]] = (
    _LEGACY_BEHAVIORAL,
    _LEGACY_COMPRESSION,
    _LEGACY_SAFETY,
    _LEGACY_DISTRIBUTION,
    _LEGACY_PERSISTENCE,
    _CONTEXTOS_FORGETTING,
    _CONTEXTOS_DEPTH,
    _CONTEXTOS_CONTRADICTION,
    _CONTEXTOS_CHURN,
    _CONTEXTOS_HEALING,
    _CONTEXTOS_SKILLBOOK,
)
"""The default rule set: 5 legacy + 6 ContextOS = 11 mechanism rules."""


__all__ = [
    "DEFAULT_MECHANISM_RULES",
    "FileMatch",
    "MechanismRule",
]
