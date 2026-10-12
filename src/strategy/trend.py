"""Reference strategy used to exercise the backtest engine end to end.

This is a deliberately simple, fully deterministic *baseline* (arm A in PLAN.md
§3 will formalise the arm comparison): hold an equal-weighted basket of the
symbols trading above their moving average, capped at `max_positions`. It exists
so the engine can be run and demonstrated before the AI judgment layer arrives.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from src.data.base import Bar
from src.features.state_engine import simple_moving_average


class TrendFollowingStrategy:
    def __init__(self, ma_window: int = 50, max_positions: int = 10) -> None:
        if ma_window < 2:
            raise ValueError("ma_window must be >= 2")
        self.ma_window = ma_window
        self.max_positions = max_positions

    def target_weights(
        self, day: date, history: Mapping[str, Sequence[Bar]]
    ) -> dict[str, float]:
        above: list[str] = []
        for symbol in sorted(history):
            closes = [bar.close for bar in history[symbol]]
            ma = simple_moving_average(closes, self.ma_window)
            if ma is not None and closes[-1] > ma:
                above.append(symbol)
        selected = above[: self.max_positions]
        if not selected:
            return {}
        weight = 1.0 / len(selected)
        return {symbol: weight for symbol in selected}
