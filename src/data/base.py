"""Data provider interface.

Fase 0 defines the contract only. Fase 1 adds the concrete providers:
Alpaca (IEX, primary), yfinance (fallback), Stooq (EOD CSV), plus EDGAR/RSS/FRED
for the context layer.

Reliability rules (PLAN.md §4): one primary source + cross-check, log the exact
snapshot used for each decision, use adjusted bars, avoid survivorship bias.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


class DataError(RuntimeError):
    """Raised when a data source cannot be reached or returns unusable data."""


@dataclass(frozen=True)
class Bar:
    symbol: str
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataProvider(ABC):
    """Contract for market-data sources."""

    @abstractmethod
    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        """Return adjusted daily OHLCV bars for a symbol over [start, end]."""
