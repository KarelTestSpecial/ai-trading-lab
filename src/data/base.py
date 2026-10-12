"""Stock market-data primitives.

`DataError` is owned by cadence-core (single source of truth for the data-layer
error type) and re-exported here so the venue providers import one local module.
The daily-bar `Bar` and the `DataProvider` contract are asset-specific — they key
on a calendar `day` rather than a timestamp, because equities trade one session
per day — and cadence-core defines no bar type on purpose.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from cadence_core.data.base import DataError

__all__ = ["Bar", "DataError", "DataProvider"]


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
