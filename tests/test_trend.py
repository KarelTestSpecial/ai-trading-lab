"""Arm A (trend baseline) sizing: equal weight, capped by the hard position limit."""

from __future__ import annotations

from datetime import date

import pytest

from src.policy.risk import RiskLimits
from src.strategy.arms import build_arm
from src.strategy.trend import TrendFollowingStrategy
from tests.helpers import make_bars

DAY = date(2024, 3, 29)
RISERS = ["AAPL", "AMZN", "GOOGL", "JPM", "META", "MSFT", "NVDA", "UNH"]


def _rising(symbol: str):
    return make_bars(symbol, [100.0 + i for i in range(10)])


def test_equal_weight_below_cap():
    strategy = TrendFollowingStrategy(ma_window=2, max_position_pct=0.5)
    weights = strategy.target_weights(DAY, {s: _rising(s) for s in RISERS[:4]})
    assert weights == {s: 0.25 for s in RISERS[:4]}


def test_weights_capped_and_not_renormalised():
    """8 picks with a 10% cap is 80% invested, not 8 x 12.5% and not 8 x 12.5% renormalised."""
    strategy = TrendFollowingStrategy(ma_window=2, max_position_pct=0.10)
    weights = strategy.target_weights(DAY, {s: _rising(s) for s in RISERS})
    assert weights == {s: 0.10 for s in RISERS}
    assert sum(weights.values()) == pytest.approx(0.80)


def test_no_pick_below_ma_returns_empty():
    strategy = TrendFollowingStrategy(ma_window=2)
    falling = {s: make_bars(s, [100.0 - i for i in range(10)]) for s in RISERS}
    assert strategy.target_weights(DAY, falling) == {}


def test_max_positions_still_applies():
    strategy = TrendFollowingStrategy(ma_window=2, max_positions=3, max_position_pct=0.5)
    weights = strategy.target_weights(DAY, {s: _rising(s) for s in RISERS})
    assert list(weights) == ["AAPL", "AMZN", "GOOGL"]


def test_build_arm_applies_risk_limit_by_default():
    strategy = build_arm("A", ma_window=2)
    weights = strategy.target_weights(DAY, {s: _rising(s) for s in RISERS})
    assert max(weights.values()) <= RiskLimits().max_position_pct


def test_build_arm_honours_explicit_limits():
    strategy = build_arm("A", ma_window=2, limits=RiskLimits(max_position_pct=0.15))
    weights = strategy.target_weights(DAY, {s: _rising(s) for s in RISERS[:4]})
    assert weights == {s: 0.15 for s in RISERS[:4]}


def test_invalid_max_position_pct_raises():
    with pytest.raises(ValueError):
        TrendFollowingStrategy(max_position_pct=0.0)
    with pytest.raises(ValueError):
        TrendFollowingStrategy(max_position_pct=1.5)
