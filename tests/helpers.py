"""Shared test helpers."""

from __future__ import annotations

from datetime import date, timedelta

from src.data.base import Bar


def make_bars(
    symbol: str, closes: list[float], start: date = date(2024, 1, 1)
) -> list[Bar]:
    """Build daily bars on consecutive weekdays from a list of closes."""
    bars: list[Bar] = []
    day = start
    for close in closes:
        while day.weekday() >= 5:  # skip weekends
            day += timedelta(days=1)
        bars.append(Bar(symbol, day, close, close, close, close, 1_000_000.0))
        day += timedelta(days=1)
    return bars
