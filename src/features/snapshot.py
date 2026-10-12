"""Deterministic state-snapshot builder.

Turns a symbol's bar history into a compact, JSON-serialisable snapshot. This is
the ONLY view the AI judgment layer ever gets (PLAN.md §3): every number is
computed here in code, so the model reasons over figures it did not calculate and
cannot silently drift.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.data.base import Bar
from src.features.state_engine import distance_from_ma, returns, zscore


@dataclass(frozen=True)
class FeatureParams:
    return_windows: tuple[int, ...] = (1, 5, 20)
    ma_windows: tuple[int, ...] = (20, 50, 200)
    vol_window: int = 20
    zscore_window: int = 60


def realized_volatility(closes: Sequence[float], window: int) -> float | None:
    """Annualised realised volatility of daily returns over the trailing window."""
    if len(closes) < window + 1:
        return None
    rets = []
    for i in range(len(closes) - window, len(closes)):
        prev = closes[i - 1]
        if prev:
            rets.append(closes[i] / prev - 1.0)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return var**0.5 * 252**0.5


def _round(value, ndigits: int = 6):
    if isinstance(value, float):
        return round(value, ndigits)
    return value


def build_snapshot(
    symbol: str,
    bars: Sequence[Bar],
    params: FeatureParams | None = None,
    *,
    ndigits: int = 6,
) -> dict:
    """Build a compact snapshot for `symbol` from bars up to and including the last bar."""
    if not bars:
        raise ValueError("cannot build a snapshot from an empty bar series")
    params = params or FeatureParams()
    closes = [b.close for b in bars]
    snapshot = {
        "symbol": symbol,
        "day": bars[-1].day.isoformat(),
        "close": _round(closes[-1], ndigits),
        "returns": {str(w): _round(returns(closes, w), ndigits) for w in params.return_windows},
        "ma_distance": {
            str(w): _round(distance_from_ma(closes, w), ndigits) for w in params.ma_windows
        },
        "zscore": _round(zscore(closes, params.zscore_window), ndigits),
        "realized_vol": _round(realized_volatility(closes, params.vol_window), ndigits),
    }
    return snapshot
