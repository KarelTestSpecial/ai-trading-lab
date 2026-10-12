"""Stooq end-of-day provider (free, no API key).

Stooq serves a daily OHLCV CSV per symbol:
    https://stooq.com/q/d/l/?s=aapl.us&i=d

Used as the keyless fallback behind Alpaca in the provider chain.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from src.data.base import Bar, DataError, DataProvider
from src.data.http import http_get_text

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"


def parse_stooq_csv(text: str, symbol: str, start: date, end: date) -> list[Bar]:
    """Parse a Stooq daily CSV into bars within [start, end]."""
    reader = csv.DictReader(io.StringIO(text.strip()))
    if reader.fieldnames is None or "Date" not in reader.fieldnames:
        raise DataError(f"unexpected Stooq response for {symbol!r}")
    bars: list[Bar] = []
    for row in reader:
        try:
            day = date.fromisoformat(row["Date"].strip())
            if not (start <= day <= end):
                continue
            bars.append(
                Bar(
                    symbol=symbol.upper(),
                    day=day,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume") or 0.0),
                )
            )
        except (KeyError, ValueError) as exc:
            raise DataError(f"malformed Stooq row for {symbol!r}: {row}") from exc
    bars.sort(key=lambda b: b.day)
    return bars


class StooqDataProvider(DataProvider):
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        text = http_get_text(STOOQ_URL.format(symbol=symbol.lower()), timeout=self.timeout)
        return parse_stooq_csv(text, symbol, start, end)
