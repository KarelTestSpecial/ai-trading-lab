"""Hard risk vetoes.

Deterministic, checked before every order, with absolute veto power. The model
never overrides these (PLAN.md §3). Values come from config/risk.yaml (Fase 1);
Fase 0 provides the dataclass and the veto function.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct: float = 0.10
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.20
    max_positions: int = 10
    earnings_blackout_days: int = 3


@dataclass(frozen=True)
class RiskState:
    portfolio_value: float
    position_value: float
    daily_pnl_pct: float
    drawdown_pct: float
    open_positions: int
    days_to_earnings: int | None


def veto_reason(state: RiskState, limits: RiskLimits) -> str | None:
    """Return a reason string if the proposed order must be blocked, else None."""
    if state.drawdown_pct >= limits.max_drawdown_pct:
        return f"max drawdown breached ({state.drawdown_pct:.1%})"
    if state.daily_pnl_pct <= -limits.max_daily_loss_pct:
        return f"max daily loss breached ({state.daily_pnl_pct:.1%})"
    if state.open_positions >= limits.max_positions:
        return f"max positions reached ({state.open_positions})"
    if state.portfolio_value > 0 and state.position_value / state.portfolio_value > limits.max_position_pct:
        return "max position size exceeded"
    if state.days_to_earnings is not None and state.days_to_earnings <= limits.earnings_blackout_days:
        return f"earnings blackout ({state.days_to_earnings} days)"
    return None
