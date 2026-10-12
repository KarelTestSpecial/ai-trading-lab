"""Turn target weights into concrete orders (pure function).

Long-only: a positive weight is a long, a missing symbol means "close it". The
function only *plans*; risk vetoes and submission happen in the loop, so the
planning stays a pure, unit-testable function of its inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PlannedOrder:
    symbol: str
    side: str  # "buy" | "sell"
    qty: float
    notional: float


def plan_orders(
    target_weights: Mapping[str, float],
    equity: float,
    current_qty: Mapping[str, float],
    prices: Mapping[str, float],
    *,
    min_notional: float = 1.0,
) -> list[PlannedOrder]:
    planned: list[PlannedOrder] = []
    for symbol in sorted(set(target_weights) | set(current_qty)):
        price = prices.get(symbol)
        if not price or price <= 0:
            continue  # no price -> cannot size a trade safely
        target_qty = target_weights.get(symbol, 0.0) * equity / price
        delta_qty = target_qty - current_qty.get(symbol, 0.0)
        notional = abs(delta_qty) * price
        if notional < min_notional:
            continue
        planned.append(
            PlannedOrder(
                symbol=symbol,
                side="buy" if delta_qty > 0 else "sell",
                qty=round(abs(delta_qty), 6),
                notional=round(notional, 2),
            )
        )
    return planned
