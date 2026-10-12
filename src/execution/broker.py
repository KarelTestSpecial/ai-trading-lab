"""Broker abstraction with a hard live-trading gate.

Design rule (see PLAN.md §3b): paper <-> live is a *configuration* difference
(endpoint + keys), never a code rewrite. Switching to live requires ALL THREE
gates simultaneously:

    1. TRADING_MODE=live
    2. ALLOW_LIVE_TRADING=true
    3. confirm_live=True passed explicitly in code

Additionally, PUBLIC_DEMO=true makes live trading impossible, unconditionally.

The Alpaca REST calls go through an injectable `Transport`, so the whole client
is unit-tested offline with a fake transport — no credentials, no network.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

from src.config import Settings, TradingMode
from src.data.http import http_get_json, http_post_json


class BrokerError(RuntimeError):
    """Raised when the broker rejects a request or is misconfigured."""


class LiveTradingDisabledError(RuntimeError):
    """Raised when live trading is attempted without satisfying the safety gates."""


@dataclass(frozen=True)
class Order:
    symbol: str
    qty: float
    side: str  # "buy" | "sell"

    def __post_init__(self) -> None:
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"side must be 'buy' or 'sell', got {self.side!r}")
        if self.qty <= 0:
            raise ValueError("qty must be positive")


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    market_value: float
    avg_entry_price: float


@dataclass(frozen=True)
class Account:
    equity: float
    cash: float
    buying_power: float
    last_equity: float

    @property
    def daily_pnl_pct(self) -> float:
        if self.last_equity <= 0:
            return 0.0
        return self.equity / self.last_equity - 1.0


class Transport(Protocol):
    def get(self, url: str, *, headers: dict[str, str]) -> Any: ...
    def post(self, url: str, payload: dict, *, headers: dict[str, str]) -> Any: ...


class UrllibTransport:
    """Default transport: the standard-library HTTP client."""

    def get(self, url: str, *, headers: dict[str, str]) -> Any:
        return http_get_json(url, headers=headers)

    def post(self, url: str, payload: dict, *, headers: dict[str, str]) -> Any:
        return http_post_json(url, payload, headers=headers)


class Broker(ABC):
    """Common interface for paper and live execution backends."""

    mode: TradingMode

    @abstractmethod
    def submit(self, order: Order) -> str:
        """Submit an order and return a broker order id."""

    @abstractmethod
    def positions(self) -> dict[str, Position]:
        """Return current positions keyed by symbol."""

    @abstractmethod
    def account(self) -> Account:
        """Return the account snapshot (equity, cash, ...)."""


class AlpacaBroker(Broker):
    def __init__(self, settings: Settings, *, live: bool, transport: Transport | None = None) -> None:
        self._settings = settings
        base = settings.alpaca_live_base_url if live else settings.alpaca_paper_base_url
        self._base_url = base.rstrip("/")
        self._transport = transport or UrllibTransport()

    def _headers(self) -> dict[str, str]:
        key = self._settings.alpaca_api_key
        secret = self._settings.alpaca_secret_key
        if not key or not secret:
            raise BrokerError(
                "Alpaca credentials are required (ALPACA_API_KEY / ALPACA_SECRET_KEY)"
            )
        return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    def submit(self, order: Order) -> str:
        payload = {
            "symbol": order.symbol.upper(),
            "qty": str(order.qty),
            "side": order.side,
            "type": "market",
            "time_in_force": "day",
        }
        data = self._transport.post(f"{self._base_url}/v2/orders", payload, headers=self._headers())
        order_id = data.get("id") if isinstance(data, dict) else None
        if not order_id:
            raise BrokerError(f"order rejected: {data}")
        return str(order_id)

    def positions(self) -> dict[str, Position]:
        data = self._transport.get(f"{self._base_url}/v2/positions", headers=self._headers())
        positions: dict[str, Position] = {}
        for item in data or []:
            positions[item["symbol"]] = Position(
                symbol=item["symbol"],
                qty=float(item["qty"]),
                market_value=float(item.get("market_value", 0.0) or 0.0),
                avg_entry_price=float(item.get("avg_entry_price", 0.0) or 0.0),
            )
        return positions

    def account(self) -> Account:
        data = self._transport.get(f"{self._base_url}/v2/account", headers=self._headers())
        equity = float(data["equity"])
        return Account(
            equity=equity,
            cash=float(data.get("cash", 0.0) or 0.0),
            buying_power=float(data.get("buying_power", 0.0) or 0.0),
            last_equity=float(data.get("last_equity", equity) or equity),
        )


class PaperBroker(AlpacaBroker):
    mode = TradingMode.PAPER

    def __init__(self, settings: Settings, *, transport: Transport | None = None) -> None:
        super().__init__(settings, live=False, transport=transport)


class LiveBroker(AlpacaBroker):
    mode = TradingMode.LIVE

    def __init__(self, settings: Settings, *, transport: Transport | None = None) -> None:
        super().__init__(settings, live=True, transport=transport)


def get_broker(settings: Settings, *, confirm_live: bool = False) -> Broker:
    """Return the correct broker, enforcing the live-trading safety gates."""
    if settings.trading_mode is TradingMode.LIVE:
        if settings.public_demo:
            raise LiveTradingDisabledError(
                "PUBLIC_DEMO=true: live trading is disabled for the public demo."
            )
        if not settings.allow_live_trading:
            raise LiveTradingDisabledError(
                "Live trading requires ALLOW_LIVE_TRADING=true."
            )
        if not confirm_live:
            raise LiveTradingDisabledError(
                "Live trading requires confirm_live=True passed explicitly in code."
            )
        return LiveBroker(settings)

    return PaperBroker(settings)
