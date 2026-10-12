"""Alpaca market-data provider (primary source; free IEX feed).

Fetches adjusted daily bars from the Alpaca data API. Requires an API key pair
(free paper account). Uses the IEX feed by default, which is free without a paid
subscription.

Docs: https://docs.alpaca.markets/reference/stockbars
"""

from __future__ import annotations

from datetime import date

from src.data.base import Bar, DataError, DataProvider
from src.data.http import http_get_json

ALPACA_DATA_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"


def parse_alpaca_bars(payload: dict, symbol: str, start: date, end: date) -> list[Bar]:
    """Parse an Alpaca bars page into bars within [start, end]."""
    if "bars" not in payload:
        raise DataError(f"unexpected Alpaca response for {symbol!r}: {payload!r}")
    raw_bars = payload.get("bars") or []
    bars: list[Bar] = []
    for item in raw_bars:
        try:
            day = date.fromisoformat(str(item["t"])[:10])
            if not (start <= day <= end):
                continue
            bars.append(
                Bar(
                    symbol=symbol.upper(),
                    day=day,
                    open=float(item["o"]),
                    high=float(item["h"]),
                    low=float(item["l"]),
                    close=float(item["c"]),
                    volume=float(item["v"]),
                )
            )
        except (KeyError, ValueError) as exc:
            raise DataError(f"malformed Alpaca bar for {symbol!r}: {item}") from exc
    bars.sort(key=lambda b: b.day)
    return bars


class AlpacaDataProvider(DataProvider):
    def __init__(
        self,
        api_key: str | None,
        secret_key: str | None,
        *,
        feed: str = "iex",
        timeout: float = 15.0,
    ) -> None:
        if not api_key or not secret_key:
            raise DataError("Alpaca data provider requires ALPACA_API_KEY and ALPACA_SECRET_KEY")
        self.api_key = api_key
        self.secret_key = secret_key
        self.feed = feed
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
        }

    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        from urllib.parse import urlencode

        base_params = {
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "adjustment": "all",
            "feed": self.feed,
            "limit": "10000",
        }
        bars: list[Bar] = []
        token: str | None = None
        while True:
            params = dict(base_params)
            if token:
                params["page_token"] = token
            url = ALPACA_DATA_URL.format(symbol=symbol.upper()) + "?" + urlencode(params)
            payload = http_get_json(url, headers=self._headers(), timeout=self.timeout)
            bars.extend(parse_alpaca_bars(payload, symbol, start, end))
            token = payload.get("next_page_token")
            if not token:
                break
        return bars
