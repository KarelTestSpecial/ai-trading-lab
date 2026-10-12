"""Performance metrics with a hard honesty invariant.

`build_report` refuses to produce a performance report unless a benchmark series
AND a cost model are supplied. This is the credibility rule of PLAN.md §2
enforced in code: you cannot show "returns" without showing what you are
compared against and what it cost.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

TRADING_DAYS_PER_YEAR = 252


class IncompleteReportError(RuntimeError):
    """Raised when a performance report is requested without benchmark/costs."""


@dataclass(frozen=True)
class CostModel:
    """Trading costs. `fee_bps` and `slippage_bps` are *per side*.

    The backtest engine charges costs on portfolio turnover using
    `one_way_fraction`; `round_trip_fraction` is the cost of entering and
    exiting a position.
    """

    fee_bps: float = 0.0
    slippage_bps: float = 0.0

    @property
    def one_way_fraction(self) -> float:
        """Per-side cost as a return fraction (e.g. 5+5 bps -> 0.001)."""
        return (self.fee_bps + self.slippage_bps) / 10_000.0

    @property
    def round_trip_fraction(self) -> float:
        return 2.0 * self.one_way_fraction


def sharpe(returns: Sequence[float], risk_free: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    excess = [r - risk_free / TRADING_DAYS_PER_YEAR for r in returns]
    std = statistics.pstdev(excess)
    if std == 0:
        return None
    return statistics.fmean(excess) / std * TRADING_DAYS_PER_YEAR**0.5


def sortino(returns: Sequence[float], risk_free: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    excess = [r - risk_free / TRADING_DAYS_PER_YEAR for r in returns]
    downside = [min(0.0, r) for r in excess]
    dd = (sum(x * x for x in downside) / len(downside)) ** 0.5
    if dd == 0:
        return None
    return statistics.fmean(excess) / dd * TRADING_DAYS_PER_YEAR**0.5


def max_drawdown(returns: Sequence[float]) -> float:
    """Maximum drawdown as a negative fraction (e.g. -0.23 = -23%)."""
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for r in returns:
        equity *= 1.0 + r
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def hit_rate(returns: Sequence[float]) -> float | None:
    if not returns:
        return None
    wins = sum(1 for r in returns if r > 0)
    return wins / len(returns)


def cumulative_return(returns: Sequence[float]) -> float:
    """Total compounded return over the period (e.g. 0.25 = +25%)."""
    equity = 1.0
    for r in returns:
        equity *= 1.0 + r
    return equity - 1.0


def annualized_return(returns: Sequence[float]) -> float | None:
    """Geometric annualised return, using 252 trading days per year."""
    if len(returns) < 2:
        return None
    total = 1.0 + cumulative_return(returns)
    if total <= 0:
        return None
    return total ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1.0


def build_report(
    returns: Sequence[float],
    benchmark_returns: Sequence[float] | None,
    costs: CostModel | None,
) -> dict:
    """Build a performance report.

    Refuses to run without a benchmark series and a cost model — the honesty
    invariant. See PLAN.md §2.
    """
    if benchmark_returns is None:
        raise IncompleteReportError(
            "A benchmark series is required: no report without a SPY buy-and-hold baseline."
        )
    if costs is None:
        raise IncompleteReportError(
            "A cost model is required: no report without modelled fees and slippage."
        )

    strategy_cum = cumulative_return(returns)
    benchmark_cum = cumulative_return(benchmark_returns)
    return {
        "n_periods": len(returns),
        "cumulative_return": strategy_cum,
        "benchmark_cumulative_return": benchmark_cum,
        "excess_return": strategy_cum - benchmark_cum,
        "annualized_return": annualized_return(returns),
        "sharpe": sharpe(returns),
        "sortino": sortino(returns),
        "max_drawdown": max_drawdown(returns),
        "hit_rate": hit_rate(returns),
        "benchmark_sharpe": sharpe(benchmark_returns),
        "benchmark_max_drawdown": max_drawdown(benchmark_returns),
        "cost_model": {
            "fee_bps": costs.fee_bps,
            "slippage_bps": costs.slippage_bps,
        },
    }
