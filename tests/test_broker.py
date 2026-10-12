"""Broker-client tests (offline via a fake transport)."""

from __future__ import annotations

import pytest

from src.config import load_settings
from src.execution.broker import (
    Account,
    BrokerError,
    Order,
    PaperBroker,
)


class FakeTransport:
    def __init__(self, get=None, post=None):
        self.gets: list[str] = []
        self.posts: list[tuple[str, dict]] = []
        self._get = get or (lambda url, headers: {})
        self._post = post or (lambda url, payload, headers: {})

    def get(self, url, *, headers):
        self.gets.append(url)
        return self._get(url, headers)

    def post(self, url, payload, *, headers):
        self.posts.append((url, payload))
        return self._post(url, payload, headers)


def _settings():
    return load_settings({"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"})


def test_submit_posts_to_paper_orders():
    transport = FakeTransport(post=lambda url, payload, headers: {"id": "abc"})
    broker = PaperBroker(_settings(), transport=transport)
    order_id = broker.submit(Order("aapl", 1.5, "buy"))
    assert order_id == "abc"
    url, payload = transport.posts[0]
    assert url.endswith("/v2/orders")
    assert payload == {
        "symbol": "AAPL",
        "qty": "1.5",
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
    }


def test_positions_parsed():
    transport = FakeTransport(
        get=lambda url, headers: [
            {"symbol": "AAPL", "qty": "2", "market_value": "300", "avg_entry_price": "140"}
        ]
    )
    positions = PaperBroker(_settings(), transport=transport).positions()
    assert positions["AAPL"].qty == 2.0
    assert positions["AAPL"].market_value == 300.0


def test_account_parsed_and_daily_pnl():
    transport = FakeTransport(
        get=lambda url, headers: {
            "equity": "100000",
            "cash": "5000",
            "buying_power": "200000",
            "last_equity": "99000",
        }
    )
    account = PaperBroker(_settings(), transport=transport).account()
    assert account.equity == 100000.0
    assert account.daily_pnl_pct == pytest.approx(100000.0 / 99000.0 - 1.0)


def test_missing_credentials_raise():
    broker = PaperBroker(load_settings({}), transport=FakeTransport())
    with pytest.raises(BrokerError):
        broker.account()


def test_uses_paper_endpoint():
    transport = FakeTransport(
        get=lambda url, headers: {"equity": "1", "cash": "0", "buying_power": "0", "last_equity": "1"}
    )
    PaperBroker(_settings(), transport=transport).account()
    assert "paper-api.alpaca.markets" in transport.gets[0]


def test_account_dataclass_defaults_last_equity():
    account = Account(equity=100.0, cash=0.0, buying_power=0.0, last_equity=100.0)
    assert account.daily_pnl_pct == 0.0
