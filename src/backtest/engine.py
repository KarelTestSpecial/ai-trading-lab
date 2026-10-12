"""Walk-forward backtest engine (no look-ahead, costs and benchmark mandatory).

Timing model (PLAN.md §2):
  * A decision is made at the close of day *t* using only bars dated <= *t*.
  * The resulting weights are held during day *t+1*, so the portfolio earns day
    *t+1*'s return. This is what makes the backtest look-ahead free.
  * Costs are charged on turnover when the target weights differ from the
    currently held weights.

`build_report` refuses to run without a benchmark and a cost model, so an
"honest" report is structurally guaranteed.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from src.backtest.metrics import CostModel, build_report
from src.data.base import Bar

_WEIGHT_EPS = 1e-9


class Strategy(Protocol):
    """A strategy maps the history available at close `day` to target weights."""

    def target_weights(
        self, day: date, history: Mapping[str, Sequence[Bar]]
    ) -> dict[str, float]:
        """Return target portfolio weights (sum of absolute values <= 1)."""


@dataclass(frozen=True)
class Trade:
    day: date
    symbol: str
    weight_delta: float


@dataclass(frozen=True)
class BacktestResult:
    days: list[date]
    equity_curve: list[float]
    portfolio_returns: list[float]
    benchmark_returns: list[float]
    trades: list[Trade]
    report: dict


def _close_map(bars: Sequence[Bar]) -> dict[date, float]:
    return {bar.day: bar.close for bar in bars}


def _aligned_days(
    price_maps: Mapping[str, Mapping[date, float]], benchmark: Mapping[date, float]
) -> list[date]:
    common: set[date] | None = None
    for mapping in price_maps.values():
        keys = set(mapping)
        common = keys if common is None else common & keys
    if common is None:
        return []
    return sorted(common & set(benchmark))


def aligned_days(
    bars_by_symbol: Mapping[str, Sequence[Bar]], benchmark_bars: Sequence[Bar]
) -> list[date]:
    """Trading days present for every symbol AND the benchmark (the common calendar)."""
    price_maps = {symbol: _close_map(bars) for symbol, bars in bars_by_symbol.items()}
    return _aligned_days(price_maps, _close_map(benchmark_bars))


def _validate_weights(weights: Mapping[str, float]) -> None:
    gross = 0.0
    for symbol, weight in weights.items():
        if math.isnan(weight):
            raise ValueError(f"weight for {symbol!r} is NaN")
        gross += abs(weight)
    if gross > 1.0 + _WEIGHT_EPS:
        raise ValueError(f"gross exposure {gross:.4f} exceeds 1.0 (leverage is not allowed)")


def run_backtest(
    bars_by_symbol: Mapping[str, Sequence[Bar]],
    benchmark_bars: Sequence[Bar],
    strategy: Strategy,
    costs: CostModel,
    *,
    initial_equity: float = 100_000.0,
    start_day: date | None = None,
    end_day: date | None = None,
    on_decision: Callable[[date, date, Strategy, Mapping[str, Mapping[date, float]]], None]
    | None = None,
) -> BacktestResult:
    if not bars_by_symbol:
        raise ValueError("no symbols to backtest")
    if initial_equity <= 0:
        raise ValueError("initial_equity must be positive")

    price = {symbol: _close_map(bars) for symbol, bars in bars_by_symbol.items()}
    benchmark = _close_map(benchmark_bars)
    days = _aligned_days(price, benchmark)
    # The evaluation window is restricted, but full history stays available to the
    # strategy (look-ahead safety comes from the `bar.day <= day` filter below).
    if start_day is not None:
        days = [d for d in days if d >= start_day]
    if end_day is not None:
        days = [d for d in days if d <= end_day]
    if len(days) < 2:
        raise ValueError("need at least two aligned trading days in the evaluation window")

    sorted_bars = {symbol: sorted(bars, key=lambda b: b.day) for symbol, bars in bars_by_symbol.items()}

    equity = initial_equity
    equity_curve: list[float] = [equity]
    portfolio_returns: list[float] = []
    benchmark_returns: list[float] = []
    trades: list[Trade] = []
    weights: dict[str, float] = {}

    for i in range(len(days) - 1):
        day = days[i]
        nxt = days[i + 1]

        history = {
            symbol: [bar for bar in bars if bar.day <= day]
            for symbol, bars in sorted_bars.items()
        }
        target = strategy.target_weights(day, history)
        _validate_weights(target)

        # Observers (e.g. calibration) read the strategy's decision here, while
        # the judgment behind it is still available.
        if on_decision is not None:
            on_decision(day, nxt, strategy, price)

        symbols = set(target) | set(weights)
        turnover = sum(abs(target.get(s, 0.0) - weights.get(s, 0.0)) for s in symbols)
        for symbol in symbols:
            delta = target.get(symbol, 0.0) - weights.get(symbol, 0.0)
            if abs(delta) > _WEIGHT_EPS:
                trades.append(Trade(day=day, symbol=symbol, weight_delta=delta))

        gross_return = 0.0
        for symbol, weight in target.items():
            series = price.get(symbol)
            if not series or series.get(day, 0.0) == 0.0 or nxt not in series:
                continue
            gross_return += weight * (series[nxt] / series[day] - 1.0)

        cost = turnover * costs.one_way_fraction
        net_return = gross_return - cost
        portfolio_returns.append(net_return)
        equity *= 1.0 + net_return
        equity_curve.append(equity)
        weights = dict(target)

        benchmark_returns.append(benchmark[nxt] / benchmark[day] - 1.0)

    report = build_report(portfolio_returns, benchmark_returns, costs)
    return BacktestResult(
        days=days,
        equity_curve=equity_curve,
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        trades=trades,
        report=report,
    )
