"""Policy-engine tests: judgments -> weights, deterministic and capped."""

from __future__ import annotations

import pytest
from cadence_core.judgment.base import Judgment

from src.policy.policy import judgment_weights
from src.policy.risk import RiskLimits


def _j(value: str, confidence: float) -> dict:
    return {"direction": Judgment("direction", value, confidence)}


def test_long_only_picks_positive_scores():
    weights = judgment_weights(
        {"AAPL": _j("up", 0.8), "MSFT": _j("down", 0.9)},
        RiskLimits(max_positions=10, max_position_pct=1.0),
    )
    assert weights == {"AAPL": pytest.approx(1.0)}


def test_proportional_to_confidence():
    weights = judgment_weights(
        {"AAPL": _j("up", 0.8), "MSFT": _j("up", 0.2)},
        RiskLimits(max_positions=10, max_position_pct=1.0),
    )
    assert weights["AAPL"] == pytest.approx(0.8)
    assert weights["MSFT"] == pytest.approx(0.2)


def test_position_cap_leaves_cash():
    weights = judgment_weights(
        {"AAPL": _j("up", 0.8), "MSFT": _j("up", 0.2)},
        RiskLimits(max_positions=10, max_position_pct=0.3),
    )
    assert weights["AAPL"] == pytest.approx(0.3)
    assert sum(weights.values()) <= 1.0


def test_max_positions_and_determinism():
    judgments = {f"S{i}": _j("up", 0.5) for i in range(5)}
    limits = RiskLimits(max_positions=2, max_position_pct=1.0)
    first = judgment_weights(judgments, limits)
    second = judgment_weights(judgments, limits)
    assert list(first) == ["S0", "S1"]  # tie broken by symbol, stable
    assert first == second


def test_no_longs_when_all_flat_or_down():
    assert judgment_weights({"AAPL": _j("down", 0.9), "MSFT": _j("flat", 0.5)}, RiskLimits()) == {}


def test_min_confidence_filters():
    weights = judgment_weights(
        {"AAPL": _j("up", 0.2), "MSFT": _j("up", 0.9)},
        RiskLimits(max_positions=10, max_position_pct=1.0),
        min_confidence=0.5,
    )
    assert weights == {"MSFT": pytest.approx(1.0)}
