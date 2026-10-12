"""Arm-comparison tests."""

from __future__ import annotations

from src.backtest.compare import (
    ArmSpec,
    ComparisonContext,
    compare_arms,
    render_comparison,
)
from src.backtest.metrics import CostModel
from src.judgment.jev import JevAdapter
from src.judgment.rules import RuleBasedJudge
from src.policy.risk import RiskLimits
from src.strategy.arms import build_arm
from tests.helpers import make_bars


def _data():
    bars = {
        "UP": make_bars("UP", [100.0 * 1.003**i for i in range(200)]),
        "DOWN": make_bars("DOWN", [100.0 * 0.997**i for i in range(200)]),
    }
    benchmark = make_bars("SPY", [100.0 * 1.001**i for i in range(200)])
    return bars, benchmark


def test_evaluate_arms_a_b_c_d():
    bars, benchmark = _data()
    limits = RiskLimits()
    specs = [
        ArmSpec("A", "rules", build_arm("A")),
        ArmSpec("B", "llm", build_arm("B", judge=RuleBasedJudge(), limits=limits)),
        ArmSpec("C", "jev", build_arm("C", judge=JevAdapter(), limits=limits)),
        ArmSpec("D", "hybrid", build_arm("D", judge=RuleBasedJudge(), limits=limits)),
    ]
    results = {r.key: r for r in compare_arms(specs, bars, benchmark, CostModel())}

    assert results["A"].report is not None
    assert results["A"].calibration is None  # no judgments in arm A
    assert results["B"].calibration is not None
    assert results["C"].error is not None  # stub fails loudly
    assert results["D"].report is not None


def test_render_comparison_contains_arms_and_error_section():
    bars, benchmark = _data()
    limits = RiskLimits()
    specs = [
        ArmSpec("A", "rules", build_arm("A")),
        ArmSpec("B", "llm", build_arm("B", judge=RuleBasedJudge(), limits=limits)),
        ArmSpec("C", "jev", build_arm("C", judge=JevAdapter(), limits=limits)),
    ]
    results = compare_arms(specs, bars, benchmark, CostModel())
    ctx = ComparisonContext(
        title="compare",
        symbols=("UP", "DOWN"),
        benchmark="SPY",
        data_source="CSV (test)",
        costs=CostModel(fee_bps=1, slippage_bps=5),
        data_is_synthetic=True,
    )
    markdown = render_comparison(results, ctx)
    assert "# compare" in markdown
    assert "| arm |" in markdown
    assert "Calibration" in markdown
    assert "could not run" in markdown
    assert "Synthetic data" in markdown
