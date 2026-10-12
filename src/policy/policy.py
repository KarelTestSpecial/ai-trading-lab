"""Policy engine: judgments -> target weights.

Weights are defined in code, never in the prompt (PLAN.md §3). A judgment maps to
a signed score (up -> +confidence, down -> -confidence, flat -> 0); the strongest
positive scores become equal-risk-ish long weights, capped by the hard limits.
The result is long-only and never levered (gross exposure <= 1.0), leaving the
remainder in cash.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.judgment.base import Judgment
from src.policy.risk import RiskLimits

DIRECTION = "direction"


def score(judgment: Judgment) -> float:
    if judgment.value == "up":
        return judgment.confidence
    if judgment.value == "down":
        return -judgment.confidence
    return 0.0


def judgment_weights(
    judgments_by_symbol: Mapping[str, Mapping[str, Judgment]],
    limits: RiskLimits,
    *,
    min_confidence: float = 0.0,
) -> dict[str, float]:
    scores = {
        symbol: score(judgments[DIRECTION])
        for symbol, judgments in judgments_by_symbol.items()
        if DIRECTION in judgments
    }
    picks = sorted(
        ((symbol, value) for symbol, value in scores.items() if value > min_confidence),
        key=lambda pair: (-pair[1], pair[0]),
    )[: limits.max_positions]
    total = sum(value for _, value in picks)
    if total <= 0.0:
        return {}
    return {
        symbol: min(value / total, limits.max_position_pct) for symbol, value in picks
    }
