"""Probability calibration for judgments (Brier score, ECE).

The credibility rule (PLAN.md §2) requires that a confidence actually means
something. If a model says P=0.8, events tagged 0.8 should happen ~80% of the
time. We measure that on the binary question "did the symbol go up?":

  * prob_up = confidence        when the judgment is "up"
  * prob_up = 1 - confidence    when the judgment is "down"
  * "flat" judgments are excluded (not a binary up/down bet)

Brier is the mean squared error of these probabilities; ECE is the average gap
between predicted and empirical frequency across probability bins.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from src.backtest.engine import Strategy
from src.judgment.base import Judgment


@dataclass(frozen=True)
class Prediction:
    symbol: str
    day: date
    prob_up: float
    went_up: bool


def judgment_prob_up(judgment: Judgment) -> float | None:
    if judgment.value == "up":
        return judgment.confidence
    if judgment.value == "down":
        return 1.0 - judgment.confidence
    return None


def brier_score(predictions: Sequence[Prediction]) -> float | None:
    if not predictions:
        return None
    total = sum((p.prob_up - (1.0 if p.went_up else 0.0)) ** 2 for p in predictions)
    return total / len(predictions)


def calibration_table(predictions: Sequence[Prediction], n_bins: int = 10) -> list[dict]:
    buckets: list[list[Prediction]] = [[] for _ in range(n_bins)]
    for prediction in predictions:
        index = min(int(prediction.prob_up * n_bins), n_bins - 1)
        buckets[index].append(prediction)

    table: list[dict] = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        avg_prob = sum(p.prob_up for p in bucket) / len(bucket)
        empirical = sum(1 for p in bucket if p.went_up) / len(bucket)
        table.append(
            {
                "bin_lower": i / n_bins,
                "bin_upper": (i + 1) / n_bins,
                "count": len(bucket),
                "avg_prob": avg_prob,
                "empirical": empirical,
            }
        )
    return table


def expected_calibration_error(
    predictions: Sequence[Prediction], n_bins: int = 10
) -> float | None:
    if not predictions:
        return None
    table = calibration_table(predictions, n_bins)
    n = len(predictions)
    return sum((row["count"] / n) * abs(row["avg_prob"] - row["empirical"]) for row in table)


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
