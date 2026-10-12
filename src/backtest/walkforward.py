"""Walk-forward evaluation.

The credibility rule (PLAN.md §2) forbids in-sample overfitting. Walk-forward is
the antidote: split the timeline into consecutive out-of-sample test windows,
choose the strategy parameter on the preceding in-sample window only, then score
the *next, unseen* window with that choice. The per-fold record of what was
chosen (and what it earned) is itself evidence against cherry-picking.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from src.backtest.engine import Strategy, aligned_days, run_backtest
from src.backtest.metrics import CostModel, build_report
from src.data.base import Bar


@dataclass(frozen=True)
class Fold:
    index: int
    train: list[date]
    test: list[date]


@dataclass(frozen=True)
class WalkForwardResult:
    report: dict
    portfolio_returns: list[float]
    benchmark_returns: list[float]
    folds: list[dict]


def make_folds(
    days: Sequence[date], *, n_folds: int = 5, initial_train_frac: float = 0.4
) -> list[Fold]:
    """Expanding-window folds: each test window is preceded by all earlier days."""
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")
    if not 0.0 < initial_train_frac < 1.0:
        raise ValueError("initial_train_frac must be in (0, 1)")
    n = len(days)
    start = int(n * initial_train_frac)
    if start < 2 or n - start < n_folds * 2:
        raise ValueError("not enough days for the requested number of folds")
    size = (n - start) // n_folds
    folds: list[Fold] = []
    for i in range(n_folds):
        lo = start + i * size
        hi = start + (i + 1) * size if i < n_folds - 1 else n
        folds.append(Fold(index=i, train=list(days[:lo]), test=list(days[lo:hi])))
    return folds


def run_walk_forward(
    bars_by_symbol: Mapping[str, Sequence[Bar]],
    benchmark_bars: Sequence[Bar],
    arm_factory: Callable[[float], Strategy],
    costs: CostModel,
    *,
    param_grid: Sequence[float],
    n_folds: int = 5,
    initial_train_frac: float = 0.4,
    initial_equity: float = 100_000.0,
) -> WalkForwardResult:
    """Run an expanding-window walk-forward and return the concatenated OOS report."""
    if not param_grid:
        raise ValueError("param_grid must not be empty")

    days = aligned_days(bars_by_symbol, benchmark_bars)
    folds = make_folds(days, n_folds=n_folds, initial_train_frac=initial_train_frac)

    oos_returns: list[float] = []
    oos_benchmark: list[float] = []
    records: list[dict] = []

    for fold in folds:
        best_param: float | None = None
        best_score: float | None = None
        for param in param_grid:
            train_result = run_backtest(
                bars_by_symbol,
                benchmark_bars,
                arm_factory(param),
                costs,
                initial_equity=initial_equity,
                start_day=fold.train[0],
                end_day=fold.train[-1],
            )
            score = train_result.report["cumulative_return"]
            if best_score is None or score > best_score:
                best_score, best_param = score, param

        assert best_param is not None
        test_result = run_backtest(
            bars_by_symbol,
            benchmark_bars,
            arm_factory(best_param),
            costs,
            initial_equity=initial_equity,
            start_day=fold.test[0],
            end_day=fold.test[-1],
        )
        oos_returns.extend(test_result.portfolio_returns)
        oos_benchmark.extend(test_result.benchmark_returns)
        records.append(
            {
                "fold": fold.index,
                "train_start": fold.train[0].isoformat(),
                "train_end": fold.train[-1].isoformat(),
                "test_start": fold.test[0].isoformat(),
                "test_end": fold.test[-1].isoformat(),
                "chosen_param": best_param,
                "train_return": best_score,
                "test_return": test_result.report["cumulative_return"],
                "benchmark_test_return": test_result.report["benchmark_cumulative_return"],
            }
        )

    report = build_report(oos_returns, oos_benchmark, costs)
    return WalkForwardResult(
        report=report,
        portfolio_returns=oos_returns,
        benchmark_returns=oos_benchmark,
        folds=records,
    )
