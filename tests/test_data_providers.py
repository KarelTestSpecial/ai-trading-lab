"""Data-provider tests (offline: parsing + fallback, no network)."""

from __future__ import annotations

from datetime import date

import pytest

from src.data.alpaca import AlpacaDataProvider, parse_alpaca_bars
from src.data.base import DataError
from src.data.csv_provider import CsvDataProvider
from src.data.registry import FallbackDataProvider
from src.data.stooq import parse_stooq_csv

START = date(2024, 1, 1)
END = date(2024, 12, 31)


def test_csv_provider_reads_and_filters(tmp_path):
    (tmp_path / "AAPL.csv").write_text(
        "date,open,high,low,close,volume\n"
        "2024-01-02,100,105,99,104,1000000\n"
        "2024-01-03,104,108,103,107,1200000\n"
        "2025-06-01,1,1,1,1,1\n"
    )
    bars = CsvDataProvider(tmp_path).daily_bars("AAPL", START, END)
    assert [b.day.isoformat() for b in bars] == ["2024-01-02", "2024-01-03"]
    assert bars[0].close == 104.0
    assert bars[0].symbol == "AAPL"


def test_csv_provider_missing_file(tmp_path):
    with pytest.raises(DataError):
        CsvDataProvider(tmp_path).daily_bars("MSFT", START, END)


def test_csv_provider_missing_column(tmp_path):
    (tmp_path / "AAPL.csv").write_text("date,close\n2024-01-02,104\n")
    with pytest.raises(DataError):
        CsvDataProvider(tmp_path).daily_bars("AAPL", START, END)


def test_parse_stooq_csv():
    text = "Date,Open,High,Low,Close,Volume\n2024-01-02,100,105,99,104,1000000\n"
    bars = parse_stooq_csv(text, "AAPL", START, END)
    assert len(bars) == 1
    assert bars[0].high == 105.0


def test_parse_stooq_rejects_garbage():
    with pytest.raises(DataError):
        parse_stooq_csv("No data", "AAPL", START, END)


def test_parse_alpaca_bars():
    payload = {
        "bars": [
            {"t": "2024-01-02T05:00:00Z", "o": 100, "h": 105, "l": 99, "c": 104, "v": 1000000}
        ],
        "next_page_token": None,
    }
    bars = parse_alpaca_bars(payload, "AAPL", START, END)
    assert len(bars) == 1
    assert bars[0].close == 104.0


def test_parse_alpaca_rejects_unexpected_payload():
    with pytest.raises(DataError):
        parse_alpaca_bars({"nope": 1}, "AAPL", START, END)


def test_alpaca_provider_requires_keys():
    with pytest.raises(DataError):
        AlpacaDataProvider(None, None)


class _FailingProvider:
    def daily_bars(self, symbol, start, end):
        raise DataError("boom")


class _WorkingProvider:
    def __init__(self):
        self.calls = 0

    def daily_bars(self, symbol, start, end):
        from tests.helpers import make_bars

        self.calls += 1
        return make_bars(symbol, [100.0, 101.0])


def test_fallback_provider_uses_next_source():
    working = _WorkingProvider()
    provider = FallbackDataProvider([_FailingProvider(), working])
    bars = provider.daily_bars("AAPL", START, END)
    assert len(bars) == 2
    assert provider.last_source == "_WorkingProvider"
    assert working.calls == 1


def test_fallback_provider_all_fail():
    provider = FallbackDataProvider([_FailingProvider(), _FailingProvider()])
    with pytest.raises(DataError):
        provider.daily_bars("AAPL", START, END)
