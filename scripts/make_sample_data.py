"""Generate deterministic synthetic daily bars for local backtests.

Writes `<SYMBOL>.csv` files (date,open,high,low,close,volume) into the output
directory for every symbol in config/universe.yaml plus the benchmark. The
series is a fixed-seed geometric random walk, so runs are reproducible.

Usage:
    uv run python scripts/make_sample_data.py --out var/sample_bars
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
import zlib
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import load_universe

END = date(2026, 10, 9)  # a Friday
N_DAYS = 500
DT = 1.0 / 252.0


def _business_days(end: date, count: int) -> list[date]:
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(days)


def _series(symbol: str, seed: int, drift: float, vol: float, start_price: float) -> list[dict]:
    rng = random.Random(seed)
    days = _business_days(END, N_DAYS)
    price = start_price
    rows: list[dict] = []
    for day in days:
        shock = rng.gauss(0.0, 1.0)
        price *= math.exp((drift - 0.5 * vol**2) * DT + vol * math.sqrt(DT) * shock)
        open_price = price * (1.0 + rng.gauss(0.0, 0.002))
        high = max(open_price, price) * (1.0 + abs(rng.gauss(0.0, 0.004)))
        low = min(open_price, price) * (1.0 - abs(rng.gauss(0.0, 0.004)))
        rows.append(
            {
                "date": day.isoformat(),
                "open": round(open_price, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(price, 4),
                "volume": int(rng.uniform(1e6, 8e6)),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="var/sample_bars")
    args = parser.parse_args()

    universe = load_universe()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    specs = [(universe.benchmark, 0.07, 0.14, 400.0)]
    for i, symbol in enumerate(universe.symbols):
        specs.append((symbol, 0.08 + 0.01 * (i % 3), 0.22 + 0.02 * (i % 4), 50.0 + 10 * i))

    for symbol, drift, vol, start_price in specs:
        seed = zlib.crc32(symbol.encode("utf-8"))
        rows = _series(symbol, seed=seed, drift=drift, vol=vol, start_price=start_price)
        path = out / f"{symbol}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["date", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {path} ({len(rows)} rows)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
