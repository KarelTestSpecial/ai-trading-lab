"""Guardrail tests: the safety invariants of PLAN.md must hold."""

from __future__ import annotations

import pytest

from src.backtest.metrics import CostModel, IncompleteReportError, build_report
from src.config import Settings, TradingMode, load_settings
from src.execution.broker import (
    LiveBroker,
    LiveTradingDisabledError,
    PaperBroker,
    get_broker,
)
from src.policy.risk import RiskLimits, RiskState, veto_reason


def _settings(**overrides) -> Settings:
    base = {
        "TRADING_MODE": "paper",
        "ALLOW_LIVE_TRADING": "false",
        "PUBLIC_DEMO": "true",
    }
    base.update(overrides)
    return load_settings(base)


# --- live-trading gate -------------------------------------------------------

def test_default_is_paper():
    broker = get_broker(_settings())
    assert isinstance(broker, PaperBroker)
    assert broker.mode is TradingMode.PAPER


def test_live_blocked_by_default():
    with pytest.raises(LiveTradingDisabledError):
        get_broker(_settings(TRADING_MODE="live"))


def test_live_blocked_without_allow_flag():
    with pytest.raises(LiveTradingDisabledError):
        get_broker(_settings(TRADING_MODE="live", PUBLIC_DEMO="false"), confirm_live=True)


def test_live_blocked_without_confirm():
    with pytest.raises(LiveTradingDisabledError):
        get_broker(
            _settings(TRADING_MODE="live", ALLOW_LIVE_TRADING="true", PUBLIC_DEMO="false"),
            confirm_live=False,
        )


def test_public_demo_never_goes_live_even_with_all_gates():
    with pytest.raises(LiveTradingDisabledError):
        get_broker(
            _settings(TRADING_MODE="live", ALLOW_LIVE_TRADING="true", PUBLIC_DEMO="true"),
            confirm_live=True,
        )


def test_live_requires_all_three_gates():
    broker = get_broker(
        _settings(TRADING_MODE="live", ALLOW_LIVE_TRADING="true", PUBLIC_DEMO="false"),
        confirm_live=True,
    )
    assert isinstance(broker, LiveBroker)


# --- honesty invariant -------------------------------------------------------

def test_report_requires_benchmark():
    with pytest.raises(IncompleteReportError):
        build_report([0.01, 0.02], benchmark_returns=None, costs=CostModel())


def test_report_requires_costs():
    with pytest.raises(IncompleteReportError):
        build_report([0.01, 0.02], benchmark_returns=[0.0, 0.01], costs=None)


def test_report_with_benchmark_and_costs():
    report = build_report(
        [0.01, -0.02, 0.03],
        benchmark_returns=[0.005, -0.01, 0.02],
        costs=CostModel(fee_bps=5, slippage_bps=5),
    )
    assert report["cost_model"] == {"fee_bps": 5, "slippage_bps": 5}
    assert "benchmark_sharpe" in report


# --- risk vetoes -------------------------------------------------------------

def test_risk_veto_drawdown():
    limits = RiskLimits(max_drawdown_pct=0.20)
    state = RiskState(100_000, 5_000, 0.0, 0.25, 1, None)
    assert "drawdown" in (veto_reason(state, limits) or "")


def test_risk_veto_earnings_blackout():
    limits = RiskLimits(earnings_blackout_days=3)
    state = RiskState(100_000, 5_000, 0.0, 0.0, 1, days_to_earnings=2)
    assert "earnings" in (veto_reason(state, limits) or "")


def test_no_veto_when_healthy():
    limits = RiskLimits()
    state = RiskState(100_000, 5_000, 0.01, 0.02, 3, days_to_earnings=30)
    assert veto_reason(state, limits) is None
