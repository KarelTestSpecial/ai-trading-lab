"""Daily paper-loop tests (offline: fake broker, fixed strategy)."""

from __future__ import annotations

import pytest

from src.execution.broker import Account, Position
from src.journal.journal import Journal
from src.loop import run_paper_once
from src.policy.risk import RiskLimits
from tests.helpers import make_bars


class FakeBroker:
    def __init__(self, account: Account, positions: dict[str, Position] | None = None):
        self._account = account
        self._positions = positions or {}
        self.submitted = []

    def account(self) -> Account:
        return self._account

    def positions(self) -> dict[str, Position]:
        return self._positions

    def submit(self, order):
        self.submitted.append(order)
        return f"oid-{len(self.submitted)}"


class FixedStrategy:
    def __init__(self, weights: dict[str, float]):
        self.weights = weights

    def target_weights(self, day, history):
        return self.weights


def _bars():
    return {
        "AAPL": make_bars("AAPL", [100.0] * 60),
        "MSFT": make_bars("MSFT", [50.0] * 60),
    }


def test_loop_submits_planned_orders(tmp_path):
    broker = FakeBroker(Account(100_000, 100_000, 100_000, 100_000))
    journal = Journal(tmp_path / "decisions.jsonl")
    record = run_paper_once(
        strategy=FixedStrategy({"AAPL": 0.1}),
        broker=broker,
        bars_by_symbol=_bars(),
        journal=journal,
        limits=RiskLimits(),
    )
    assert record["submitted"][0]["symbol"] == "AAPL"
    assert broker.submitted[0].qty == pytest.approx(100.0)  # 0.1 * 100000 / 100
    assert journal.path.exists()


def test_dry_run_neither_submits_nor_appends(tmp_path):
    broker = FakeBroker(Account(100_000, 100_000, 100_000, 100_000))
    journal = Journal(tmp_path / "decisions.jsonl")
    run_paper_once(
        strategy=FixedStrategy({"AAPL": 0.1}),
        broker=broker,
        bars_by_symbol=_bars(),
        journal=journal,
        limits=RiskLimits(),
        dry_run=True,
    )
    assert broker.submitted == []
    assert not journal.path.exists()


def test_drawdown_veto_blocks_all_orders(tmp_path):
    journal = Journal(tmp_path / "decisions.jsonl")
    journal.append({"event": "paper_decision", "account_equity": 200_000})
    broker = FakeBroker(Account(100_000, 100_000, 100_000, 100_000))
    record = run_paper_once(
        strategy=FixedStrategy({"AAPL": 0.1}),
        broker=broker,
        bars_by_symbol=_bars(),
        journal=journal,
        limits=RiskLimits(max_drawdown_pct=0.20),
    )
    assert record["submitted"] == []
    assert record["vetoed"]
    assert broker.submitted == []


def test_sell_closes_position(tmp_path):
    broker = FakeBroker(
        Account(100_000, 100_000, 100_000, 100_000),
        {"AAPL": Position("AAPL", qty=10.0, market_value=1000.0, avg_entry_price=90.0)},
    )
    journal = Journal(tmp_path / "decisions.jsonl")
    record = run_paper_once(
        strategy=FixedStrategy({}),  # target: nothing held
        broker=broker,
        bars_by_symbol=_bars(),
        journal=journal,
        limits=RiskLimits(),
    )
    assert record["submitted"][0]["side"] == "sell"
    assert broker.submitted[0].symbol == "AAPL"
