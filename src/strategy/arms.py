"""Experiment arms (PLAN.md §3).

The arms experiment compares, on identical data and costs:
  * A — deterministic baseline rules
  * B — LLM context + judgment (Fase 3)
  * C — calibrated decision model / Jev adapter (Fase 3)
  * D — hybrid (Fase 4)

`build_arm` is the single entry point so every arm is constructed the same way
and compared fairly. AI arms require an injected `judge`; that is deliberate, so
an arm can never silently run without the model it claims to use.
"""

from __future__ import annotations

from cadence_core.context.base import ContextProvider
from cadence_core.judgment.base import JudgmentModel

from src.backtest.engine import Strategy
from src.features.snapshot import FeatureParams
from src.policy.risk import RiskLimits
from src.strategy.hybrid import HybridStrategy
from src.strategy.judgment import JudgmentStrategy
from src.strategy.trend import TrendFollowingStrategy

ARMS = ("A", "B", "C", "D")

ARM_DESCRIPTIONS = {
    "A": "Deterministic trend baseline: equal-weight the symbols above their MA, capped by the hard position limit.",
    "B": "LLM context + judgment layer feeding the shared policy engine.",
    "C": "Calibrated decision model (Jev adapter) feeding the shared policy engine.",
    "D": "Hybrid: trend rule gates the universe, judgment sizes within it.",
}


def build_arm(
    name: str,
    *,
    judge: JudgmentModel | None = None,
    limits: RiskLimits | None = None,
    params: FeatureParams | None = None,
    context_provider: ContextProvider | None = None,
    ma_window: int = 50,
    max_positions: int = 10,
) -> Strategy:
    key = name.strip().upper()
    effective_limits = limits or RiskLimits()
    if key == "A":
        return TrendFollowingStrategy(
            ma_window=ma_window,
            max_positions=max_positions,
            max_position_pct=effective_limits.max_position_pct,
        )
    if key in {"B", "C"}:
        if judge is None:
            raise ValueError(f"arm {key} requires a judge model (pass judge=...)")
        return JudgmentStrategy(
            judge=judge,
            limits=effective_limits,
            params=params,
            context_provider=context_provider,
        )
    if key == "D":
        if judge is None:
            raise ValueError("arm D requires a judge model (pass judge=...)")
        return HybridStrategy(
            judge,
            effective_limits,
            params=params,
            context_provider=context_provider,
            ma_window=ma_window,
        )
    raise ValueError(f"unknown arm {name!r}; available: {', '.join(ARMS)}")
