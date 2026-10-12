"""Report-renderer tests: the honesty sections must always be present."""

from __future__ import annotations

from src.backtest.metrics import CostModel, build_report
from src.backtest.report import ReportContext, render_markdown


def _report():
    return build_report(
        [0.01, -0.005, 0.02, 0.0],
        benchmark_returns=[0.005, -0.01, 0.015, 0.001],
        costs=CostModel(fee_bps=1, slippage_bps=5),
    )


def _context(**overrides):
    base = {
        "title": "ai-trading-lab — backtest report",
        "symbols": ("AAPL", "MSFT"),
        "benchmark": "SPY",
        "strategy": "arm A",
        "data_source": "CSV (var/sample_bars)",
    }
    base.update(overrides)
    return ReportContext(**base)


def test_report_contains_honesty_sections():
    md = render_markdown(_report(), _context())
    assert "# ai-trading-lab" in md
    assert "SPY" in md
    assert "## Limitations" in md
    assert "## Disclaimer" in md
    assert "Simulation only" in md
    assert "Survivorship bias" in md


def test_report_marks_synthetic_data():
    md = render_markdown(_report(), _context(data_is_synthetic=True))
    assert "Synthetic data" in md


def test_report_includes_folds_table_when_walk_forward():
    folds = [
        {
            "fold": 0,
            "train_start": "2024-01-01",
            "train_end": "2024-03-01",
            "test_start": "2024-03-04",
            "test_end": "2024-04-01",
            "chosen_param": 50,
            "train_return": 0.1,
            "test_return": 0.02,
            "benchmark_test_return": 0.03,
        }
    ]
    md = render_markdown(_report(), _context(walk_forward=True, folds=folds))
    assert "## Walk-forward folds" in md
    assert "out-of-sample" in md
    assert "| 0 |" in md
