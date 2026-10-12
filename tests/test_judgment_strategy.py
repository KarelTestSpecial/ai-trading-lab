"""Judgment-strategy / arms tests: the pipeline end to end, offline."""

from __future__ import annotations

from datetime import date

import pytest

from src.context.base import ContextItem
from src.context.static import StaticContextProvider
from src.judgment.jev import JevAdapter
from src.judgment.rules import RuleBasedJudge
from src.policy.risk import RiskLimits
from src.strategy.arms import build_arm
from src.strategy.judgment import JudgmentStrategy
from tests.helpers import make_bars


def _history(closes_by_symbol):
    return {
        symbol: make_bars(symbol, closes) for symbol, closes in closes_by_symbol.items()
    }


def test_pipeline_produces_long_weights():
    history = _history(
        {
            "UP": [100.0 * (1.0 + 0.002) ** i for i in range(260)],
            "DOWN": [100.0 * (1.0 - 0.002) ** i for i in range(260)],
        }
    )
    strategy = JudgmentStrategy(RuleBasedJudge(), RiskLimits(max_positions=10, max_position_pct=1.0))
    day = date(2025, 12, 31)
    weights = strategy.target_weights(day, history)
    assert set(weights) == {"UP"}
    assert sum(weights.values()) <= 1.0
    assert strategy.last_snapshots and strategy.last_judgments


def test_context_is_passed_into_snapshot():
    history = _history({"AAPL": [100.0 + i for i in range(260)]})
    provider = StaticContextProvider(
        [ContextItem("feed", "AAPL headline", "some text", symbol="AAPL")]
    )
    strategy = JudgmentStrategy(RuleBasedJudge(), RiskLimits(), context_provider=provider)
    strategy.target_weights(date(2025, 12, 31), history)
    assert "context" in strategy.last_snapshots["AAPL"]
    assert "AAPL headline" in strategy.last_snapshots["AAPL"]["context"]


def test_build_arm_b_and_c():
    assert build_arm("A") is not None
    assert build_arm("B", judge=RuleBasedJudge()) is not None
    assert build_arm("C", judge=JevAdapter()) is not None


def test_build_arm_ai_requires_judge():
    with pytest.raises(ValueError, match="judge"):
        build_arm("B")


def test_build_arm_unknown():
    with pytest.raises(ValueError):
        build_arm("Z")
