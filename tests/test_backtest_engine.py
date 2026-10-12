"""Backtest-engine tests: correctness, costs, no look-ahead, weight validation."""

from __future__ import annotations

from datetime import date

import pytest

from src.backtest.engine import run_backtest
from src.backtest.metrics import CostModel
from tests.helpers import make_bars


class BuyAndHold:
    def target_weights(self, day, history):
        return {symbol: 1.0 for symbol in history}


class LookaheadProbe:
    """Records the newest bar date it is shown; must never exceed the decision day."""

    def __init__(self):
        self.newest_seen: date | None = None

    def target_weights(self, day, history):
        for bars in history.values():
            for bar in bars:
                if bar.day > day:
                    raise AssertionError(f"look-ahead: saw {bar.day} while deciding on {day}")
                self.newest_seen = bar.day
        return {}


class OverLeveraged:
    def target_weights(self, day, history):
        return {symbol: 1.5 for symbol in history}


def _two_series(closes):
    return make_bars("AAPL", closes), make_bars("SPY", closes)


def test_buy_and_hold_no_costs():
    aapl, spy = _two_series([100.0, 110.0, 121.0])
    result = run_backtest({"AAPL": aapl}, spy, BuyAndHold(), CostModel())
    assert result.portfolio_returns == pytest.approx([0.10, 0.10])
    assert result.report["cumulative_return"] == pytest.approx(0.21)
    assert result.report["benchmark_cumulative_return"] == pytest.approx(0.21)
    assert result.report["excess_return"] == pytest.approx(0.0)


def test_costs_reduce_return():
    aapl, spy = _two_series([100.0, 110.0, 121.0])
    free = run_backtest({"AAPL": aapl}, spy, BuyAndHold(), CostModel())
    costly = run_backtest({"AAPL": aapl}, spy, BuyAndHold(), CostModel(fee_bps=5, slippage_bps=5))
    assert costly.report["cumulative_return"] < free.report["cumulative_return"]
    # first-day turnover is 1.0, so the first net return is gross minus 10 bps.
    assert costly.portfolio_returns[0] == pytest.approx(0.10 - 0.001)


def test_no_lookahead():
    aapl, spy = _two_series([100.0, 105.0, 110.0, 115.0])
    probe = LookaheadProbe()
    result = run_backtest({"AAPL": aapl}, spy, probe, CostModel())
    assert result.days[-1] == date(2024, 1, 4)
    assert probe.newest_seen is not None


def test_over_leverage_rejected():
    aapl, spy = _two_series([100.0, 110.0, 121.0])
    with pytest.raises(ValueError, match="leverage"):
        run_backtest({"AAPL": aapl}, spy, OverLeveraged(), CostModel())


def test_needs_two_aligned_days():
    aapl = make_bars("AAPL", [100.0])
    spy = make_bars("SPY", [100.0])
    with pytest.raises(ValueError):
        run_backtest({"AAPL": aapl}, spy, BuyAndHold(), CostModel())


def test_benchmark_is_required_in_report():
    aapl, spy = _two_series([100.0, 110.0, 121.0])
    result = run_backtest({"AAPL": aapl}, spy, BuyAndHold(), CostModel())
    assert "benchmark_sharpe" in result.report
    assert result.report["cost_model"] == {"fee_bps": 0.0, "slippage_bps": 0.0}
