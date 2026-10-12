"""Data-provider registry and fallback chain.

PLAN.md §4: one primary source plus a fallback. `FallbackDataProvider` tries each
provider in order and only accepts a non-empty result, logging which provider
answered so the snapshot's provenance is always known.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.config import Settings
from src.data.alpaca import AlpacaDataProvider
from src.data.base import Bar, DataError, DataProvider
from src.data.csv_provider import CsvDataProvider
from src.data.stooq import StooqDataProvider


class FallbackDataProvider(DataProvider):
    def __init__(self, providers: list[DataProvider]) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self.providers = providers
        self.last_source: str | None = None

    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        problems: list[str] = []
        for provider in self.providers:
            try:
                bars = provider.daily_bars(symbol, start, end)
            except DataError as exc:
                problems.append(f"{type(provider).__name__}: {exc}")
                continue
            if bars:
                self.last_source = type(provider).__name__
                return bars
            problems.append(f"{type(provider).__name__}: empty result")
        raise DataError(f"all providers failed for {symbol!r}: {'; '.join(problems)}")


def build_data_provider(
    settings: Settings,
    *,
    name: str = "auto",
    csv_dir: str | Path | None = None,
) -> DataProvider:
    """Construct a data provider.

    name: "auto" (Alpaca if keys present, then Stooq), "alpaca", "stooq", "csv".
    """
    if name == "csv":
        if csv_dir is None:
            raise DataError("csv provider requires a directory")
        return CsvDataProvider(csv_dir)
    if name == "alpaca":
        return AlpacaDataProvider(settings.alpaca_api_key, settings.alpaca_secret_key)
    if name == "stooq":
        return StooqDataProvider()

    providers: list[DataProvider] = []
    if settings.alpaca_api_key and settings.alpaca_secret_key:
        providers.append(AlpacaDataProvider(settings.alpaca_api_key, settings.alpaca_secret_key))
    providers.append(StooqDataProvider())
    return FallbackDataProvider(providers)
