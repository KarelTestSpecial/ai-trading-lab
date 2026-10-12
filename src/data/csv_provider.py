"""CSV market-data provider.

Reads adjusted daily bars from `<directory>/<SYMBOL>.csv` with a header of
`date,open,high,low,close,volume` (case-insensitive, any column order). This is
the offline provider used by tests and by local backtests on cached data.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from src.data.base import Bar, DataError, DataProvider

_REQUIRED = {"date", "open", "high", "low", "close", "volume"}


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    if "T" in raw:
        raw = raw.split("T", 1)[0]
    return date.fromisoformat(raw)


class CsvDataProvider(DataProvider):
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def path_for(self, symbol: str) -> Path:
        return self.directory / f"{symbol.upper()}.csv"

    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        path = self.path_for(symbol)
        if not path.exists():
            raise DataError(f"no CSV for {symbol!r} at {path}")
        bars: list[Bar] = []
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise DataError(f"{path} has no header")
            fields = {name.strip().lower(): name for name in reader.fieldnames}
            missing = _REQUIRED - set(fields)
            if missing:
                raise DataError(f"{path} is missing columns: {sorted(missing)}")
            for row in reader:
                day = _parse_date(row[fields["date"]])
                if not (start <= day <= end):
                    continue
                bars.append(
                    Bar(
                        symbol=symbol.upper(),
                        day=day,
                        open=float(row[fields["open"]]),
                        high=float(row[fields["high"]]),
                        low=float(row[fields["low"]]),
                        close=float(row[fields["close"]]),
                        volume=float(row[fields["volume"]]),
                    )
                )
        bars.sort(key=lambda b: b.day)
        return bars
