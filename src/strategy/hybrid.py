"""Hybrid strategy (arm D): rules gate, AI sizes.

A genuine hybrid: the deterministic trend rule prunes the universe (only symbols
above their moving average are eligible), and the judgment model then decides
direction/weight among those survivors. This keeps the AI from acting on symbols
that the rules already exclude, while still letting it size within the trend.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from src.data.base import Bar
from src.features.state_engine import simple_moving_average
from src.strategy.judgment import JudgmentStrategy


class HybridStrategy(JudgmentStrategy):
    def __init__(self, *args, ma_window: int = 50, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if ma_window < 2:
            raise ValueError("ma_window must be >= 2")
        self.ma_window = ma_window

    def _above_ma(self, bars: Sequence[Bar]) -> bool:
        closes = [bar.close for bar in bars]
        ma = simple_moving_average(closes, self.ma_window)
        return ma is not None and closes[-1] > ma

    def target_weights(
        self, day: date, history: Mapping[str, Sequence[Bar]]
    ) -> dict[str, float]:
        gated = {symbol: bars for symbol, bars in history.items() if self._above_ma(bars)}
        return super().target_weights(day, gated)
