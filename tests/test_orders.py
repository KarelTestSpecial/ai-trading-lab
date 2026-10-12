"""Order-planning tests (pure function)."""

from __future__ import annotations

from src.execution.orders import plan_orders


def test_plan_buy_and_sell():
    planned = plan_orders(
        {"AAPL": 0.5, "MSFT": 0.0},
        equity=10_000.0,
        current_qty={"MSFT": 5.0},
        prices={"AAPL": 100.0, "MSFT": 50.0},
    )
    by_symbol = {order.symbol: order for order in planned}
    assert by_symbol["AAPL"].side == "buy"
    assert by_symbol["AAPL"].qty == 50.0  # 0.5 * 10000 / 100
    assert by_symbol["MSFT"].side == "sell"
    assert by_symbol["MSFT"].qty == 5.0


def test_no_order_below_min_notional():
    assert plan_orders({"AAPL": 0.000001}, 10_000.0, {}, {"AAPL": 100.0}) == []


def test_missing_price_is_skipped():
    assert plan_orders({"AAPL": 0.5}, 10_000.0, {}, {}) == []


def test_rebalance_within_tolerance_is_skipped():
    # currently 50 shares of a $100 stock = $5000 = 50% of equity; target 50%.
    planned = plan_orders({"AAPL": 0.5}, 10_000.0, {"AAPL": 50.0}, {"AAPL": 100.0})
    assert planned == []
