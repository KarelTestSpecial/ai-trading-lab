"""Deterministic feature/state engine.

Everything computable stays in code (PLAN.md §3): indicators are pure functions.
The AI judgment layer only ever sees the compact snapshot produced here.
"""

from __future__ import annotations

from collections.abc import Sequence


def returns(closes: Sequence[float], periods: int = 1) -> float | None:
    """Simple return over `periods` bars, or None if there is not enough data."""
    if len(closes) <= periods:
        return None
    prev = closes[-1 - periods]
    if prev == 0:
        return None
    return (closes[-1] - prev) / prev


def simple_moving_average(values: Sequence[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def distance_from_ma(closes: Sequence[float], window: int) -> float | None:
    """Relative distance of the latest close from its moving average."""
    ma = simple_moving_average(closes, window)
    if ma in (None, 0):
        return None
    return (closes[-1] - ma) / ma


def zscore(values: Sequence[float], window: int) -> float | None:
    """Z-score of the latest value vs the trailing window."""
    if len(values) < window:
        return None
    window_vals = list(values[-window:])
    mean = sum(window_vals) / window
    var = sum((v - mean) ** 2 for v in window_vals) / window
    std = var**0.5
    if std == 0:
        return None
    return (window_vals[-1] - mean) / std
