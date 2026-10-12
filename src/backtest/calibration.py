"""Backtest calibration observer (Brier score, ECE).

The calibration math is owned by cadence-core and imported here. Only what is
specific to this project stays: the `Prediction` record (keyed on a calendar
`day`, because equities trade one session per day, where cadence-core's record
carries a `ts: datetime`) and the `CalibrationRecorder` backtest observer, which
is coupled to the strategy contract.

The math is duck-typed on `prob_up`/`went_up`, so it works with this record
unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from cadence_core.calibration import judgment_prob_up

from src.backtest.engine import Strategy

__all__ = ["CalibrationRecorder", "Prediction"]


@dataclass(frozen=True)
class Prediction:
    symbol: str
    day: date
    prob_up: float
    went_up: bool


class CalibrationRecorder:
    """Backtest observer that captures per-decision (prob_up, outcome) pairs."""

    def __init__(self) -> None:
        self.predictions: list[Prediction] = []

    def __call__(
        self,
        day: date,
        next_day: date,
        strategy: Strategy,
        price: Mapping[str, Mapping[date, float]],
    ) -> None:
        judgments = getattr(strategy, "last_judgments", None)
        if not judgments:
            return
        for symbol, symbol_judgments in judgments.items():
            judgment = symbol_judgments.get("direction")
            if judgment is None:
                continue
            prob_up = judgment_prob_up(judgment)
            if prob_up is None:
                continue
            series = price.get(symbol)
            if not series or not series.get(day) or next_day not in series:
                continue
            self.predictions.append(
                Prediction(
                    symbol=symbol,
                    day=day,
                    prob_up=prob_up,
                    went_up=series[next_day] > series[day],
                )
            )
