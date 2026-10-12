"""The daily paper-trading loop.

One run = fetch data -> build a snapshot per symbol -> judge -> policy weights ->
plan orders -> hard risk vetoes -> submit to the paper broker -> append to the
append-only journal. The journal is the artefact that turns this into a
tamper-evident public track record (committed daily by the GitHub Action).

Nothing here talks to a vendor directly; the broker, provider and strategy are
injected, so the whole loop is unit-tested offline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date

from src.execution.broker import Broker, Order
from src.execution.orders import PlannedOrder, plan_orders
from src.journal.journal import Journal
from src.policy.risk import RiskLimits, RiskState, veto_reason


def _peak_equity(journal: Journal, current: float) -> float:
    peak = current
    for record in journal.read():
        value = record.get("account_equity")
        if isinstance(value, (int, float)):
            peak = max(peak, float(value))
    return peak


def _serialise_judgments(strategy) -> dict:
    judgments = getattr(strategy, "last_judgments", None) or {}
    return {
        symbol: {name: asdict(judgment) for name, judgment in symbol_judgments.items()}
        for symbol, symbol_judgments in judgments.items()
    }


def run_paper_once(
    *,
    strategy,
    broker: Broker,
    bars_by_symbol: Mapping[str, Sequence],
    journal: Journal,
    limits: RiskLimits,
    as_of: date | None = None,
    dry_run: bool = False,
) -> dict:
    days = sorted({bar.day for bars in bars_by_symbol.values() for bar in bars})
    if not days:
        raise ValueError("no bars available for the paper loop")
    as_of = as_of or days[-1]

    history = {
        symbol: [bar for bar in bars if bar.day <= as_of]
        for symbol, bars in bars_by_symbol.items()
    }
    history = {symbol: bars for symbol, bars in history.items() if bars}
    prices = {symbol: bars[-1].close for symbol, bars in history.items()}

    target_weights = strategy.target_weights(as_of, history)

    account = broker.account()
    positions = broker.positions()
    current_qty = {symbol: position.qty for symbol, position in positions.items()}

    peak = _peak_equity(journal, account.equity)
    drawdown_pct = 0.0 if peak <= 0 else max(0.0, 1.0 - account.equity / peak)

    planned = plan_orders(target_weights, account.equity, current_qty, prices)

    submitted: list[dict] = []
    vetoed: list[dict] = []
    for order in planned:
        state = RiskState(
            portfolio_value=account.equity,
            position_value=order.notional,
            daily_pnl_pct=account.daily_pnl_pct,
            drawdown_pct=drawdown_pct,
            open_positions=len(positions),
            days_to_earnings=None,
        )
        reason = veto_reason(state, limits)
        if reason is not None:
            vetoed.append(_order_record(order, reason))
            continue
        order_id = None
        if not dry_run:
            order_id = broker.submit(Order(symbol=order.symbol, qty=order.qty, side=order.side))
        submitted.append(_order_record(order, None, order_id))

    record = {
        "event": "paper_decision",
        "as_of": as_of.isoformat(),
        "dry_run": dry_run,
        "strategy": type(strategy).__name__,
        "account_equity": account.equity,
        "cash": account.cash,
        "daily_pnl_pct": account.daily_pnl_pct,
        "drawdown_pct": drawdown_pct,
        "target_weights": target_weights,
        "submitted": submitted,
        "vetoed": vetoed,
        "snapshots": getattr(strategy, "last_snapshots", None) or {},
        "judgments": _serialise_judgments(strategy),
    }
    if not dry_run:
        journal.append(record)
    return record


def _order_record(order: PlannedOrder, reason: str | None, order_id: str | None = None) -> dict:
    record = {
        "symbol": order.symbol,
        "side": order.side,
        "qty": order.qty,
        "notional": order.notional,
    }
    if order_id is not None:
        record["order_id"] = order_id
    if reason is not None:
        record["veto_reason"] = reason
    return record
