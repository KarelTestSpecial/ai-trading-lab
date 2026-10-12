"""Hybrid arm-D tests."""

from __future__ import annotations

from datetime import date

from src.judgment.rules import RuleBasedJudge
from src.policy.risk import RiskLimits
from src.strategy.hybrid import HybridStrategy
from tests.helpers import make_bars


def test_hybrid_gates_on_trend_then_judges():
    history = {
        "UP": make_bars("UP", [100.0 * 1.003**i for i in range(260)]),
        "DOWN": make_bars("DOWN", [100.0 * 0.997**i for i in range(260)]),
    }
    strategy = HybridStrategy(
        RuleBasedJudge(), RiskLimits(max_positions=10, max_position_pct=1.0), ma_window=50
    )
    weights = strategy.target_weights(date(2025, 12, 31), history)
    # DOWN is below its MA, so the rule gate excludes it before the judge runs.
    assert set(weights) == {"UP"}
    assert set(strategy.last_judgments) == {"UP"}
