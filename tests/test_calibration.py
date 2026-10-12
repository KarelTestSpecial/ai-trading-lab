"""Calibration tests: Brier score, ECE, and the backtest observer."""

from __future__ import annotations

from datetime import date

import pytest

from src.backtest.calibration import (
    CalibrationRecorder,
    Prediction,
    brier_score,
    calibration_table,
    expected_calibration_error,
    judgment_prob_up,
)
from src.backtest.engine import run_backtest
from src.backtest.metrics import CostModel
from src.judgment.base import Judgment
from src.judgment.rules import RuleBasedJudge
from src.policy.risk import RiskLimits
from src.strategy.judgment import JudgmentStrategy
from tests.helpers import make_bars

D = date(2025, 1, 2)


def test_judgment_prob_up():
    assert judgment_prob_up(Judgment("direction", "up", 0.8)) == 0.8
    assert judgment_prob_up(Judgment("direction", "down", 0.8)) == pytest.approx(0.2)
    assert judgment_prob_up(Judgment("direction", "flat", 0.5)) is None


def test_brier_perfect_is_zero():
    preds = [
        Prediction("A", D, 1.0, True),
        Prediction("A", D, 0.0, False),
    ]
    assert brier_score(preds) == pytest.approx(0.0)


def test_brier_worst_case():
    preds = [Prediction("A", D, 1.0, False)]
    assert brier_score(preds) == pytest.approx(1.0)


def test_ece_zero_when_calibrated():
    preds = [Prediction("A", D, 1.0, True), Prediction("A", D, 0.0, False)]
    assert expected_calibration_error(preds) == pytest.approx(0.0)


def test_ece_positive_when_miscalibrated():
    preds = [Prediction("A", D, 0.9, True), Prediction("A", D, 0.9, False)]
    assert expected_calibration_error(preds) == pytest.approx(0.4)


def test_calibration_table_bins():
    preds = [Prediction("A", D, 0.95, True), Prediction("A", D, 0.05, False)]
    table = calibration_table(preds, n_bins=10)
    assert len(table) == 2
    assert table[0]["count"] == 1


def test_empty_predictions():
    assert brier_score([]) is None
    assert expected_calibration_error([]) is None


def test_recorder_captures_from_backtest():
    bars = {
        "UP": make_bars("UP", [100.0 * 1.003**i for i in range(120)]),
        "DOWN": make_bars("DOWN", [100.0 * 0.997**i for i in range(120)]),
    }
    benchmark = make_bars("SPY", [100.0 * 1.001**i for i in range(120)])
    strategy = JudgmentStrategy(RuleBasedJudge(), RiskLimits())
    recorder = CalibrationRecorder()
    run_backtest(
        bars, benchmark, strategy, CostModel(), on_decision=recorder
    )
    assert recorder.predictions
    assert all(0.0 <= p.prob_up <= 1.0 for p in recorder.predictions)
