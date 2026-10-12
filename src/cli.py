"""Command-line entry point.

Commands:
  * `doctor`   — verify configuration and the safety gates.
  * `backtest` — run the walk-forward backtest over a directory of CSV bars and
                 print an honest report (benchmark + costs are mandatory).
  * `report`   — run the backtest and write a publishable Markdown report
                 (walk-forward by default).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from src.backtest.compare import ArmSpec, ComparisonContext, compare_arms, render_comparison
from src.backtest.engine import run_backtest
from src.backtest.metrics import CostModel
from src.backtest.report import ReportContext, render_markdown
from src.backtest.walkforward import run_walk_forward
from src.config import ConfigError, TradingMode, load_settings
from src.config_loader import (
    ConfigLoadError,
    UniverseConfig,
    load_risk,
    load_strategy,
    load_universe,
)
from src.data.base import Bar, DataError
from src.data.registry import build_data_provider
from src.execution.broker import BrokerError, LiveTradingDisabledError, get_broker
from src.journal.journal import Journal
from src.judgment.base import JudgmentError
from src.judgment.factory import build_judge
from src.judgment.jev import JevAdapter
from src.judgment.rules import RuleBasedJudge
from src.loop import run_paper_once
from src.strategy.arms import ARM_DESCRIPTIONS, build_arm
from src.strategy.judgment import JudgmentStrategy


def cmd_doctor(args: argparse.Namespace) -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"[FAIL] invalid configuration: {exc}")
        return 1

    print("ai-trading-lab :: doctor")
    print(f"  TRADING_MODE      = {settings.trading_mode.value}")
    print(f"  ALLOW_LIVE_TRADING= {settings.allow_live_trading}")
    print(f"  PUBLIC_DEMO       = {settings.public_demo}")
    print(f"  JOURNAL_PATH      = {settings.journal_path}")
    print(f"  ALPACA key set    = {bool(settings.alpaca_api_key)}")

    ok = True
    if settings.trading_mode is TradingMode.LIVE:
        try:
            get_broker(settings, confirm_live=args.confirm_live)
        except LiveTradingDisabledError as exc:
            print(f"[FAIL] live requested but blocked: {exc}")
            ok = False
        else:
            print("[WARN] LIVE trading would be enabled. This must never happen in the demo.")
    else:
        get_broker(settings)
        print("[OK]   paper mode; live trading is gated off.")

    return 0 if ok else 1


def _window(args: argparse.Namespace) -> tuple[date, date]:
    start = date.fromisoformat(args.start) if args.start else date(1900, 1, 1)
    end = date.fromisoformat(args.end) if args.end else date(2100, 1, 1)
    return start, end


def _load_bars(
    data_dir: str, universe: UniverseConfig, start: date, end: date
) -> tuple[dict[str, list[Bar]], list[Bar]]:
    settings = load_settings()
    provider = build_data_provider(settings, name="csv", csv_dir=data_dir)
    bars_by_symbol: dict[str, list[Bar]] = {}
    for symbol in universe.symbols:
        bars = provider.daily_bars(symbol, start, end)
        if bars:
            bars_by_symbol[symbol] = bars
    benchmark = provider.daily_bars(universe.benchmark, start, end)
    return bars_by_symbol, benchmark


def _fmt(value, pct: bool = False) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}" if pct else f"{value:.3f}"


def _print_report(result_report: dict, universe: UniverseConfig, n_trades: int, args) -> None:
    print("ai-trading-lab :: backtest")
    print(f"  benchmark      = {universe.benchmark}")
    print(f"  periods        = {result_report['n_periods']} trading days")
    print(f"  costs          = {args.fee_bps} bps fee + {args.slippage_bps} bps slippage (per side)")
    print()
    print(f"  {'metric':<22}{'strategy':>14}{'benchmark':>14}")
    print(f"  {'-' * 22}{'-' * 14}{'-' * 14}")
    print(
        f"  {'cumulative return':<22}"
        f"{_fmt(result_report['cumulative_return'], pct=True):>14}"
        f"{_fmt(result_report['benchmark_cumulative_return'], pct=True):>14}"
    )
    print(f"  {'excess return':<22}{_fmt(result_report['excess_return'], pct=True):>14}{'':>14}")
    print(f"  {'annualized return':<22}{_fmt(result_report['annualized_return'], pct=True):>14}{'':>14}")
    print(
        f"  {'sharpe':<22}"
        f"{_fmt(result_report['sharpe']):>14}{_fmt(result_report['benchmark_sharpe']):>14}"
    )
    print(
        f"  {'max drawdown':<22}"
        f"{_fmt(result_report['max_drawdown'], pct=True):>14}"
        f"{_fmt(result_report['benchmark_max_drawdown'], pct=True):>14}"
    )
    print(f"  {'hit rate':<22}{_fmt(result_report['hit_rate'], pct=True):>14}{'':>14}")
    print()
    print(f"  trades         = {n_trades}")


def cmd_backtest(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        load_strategy(args.strategy)  # validate the strategy config exists/parses
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    start, end = _window(args)
    try:
        bars_by_symbol, benchmark = _load_bars(args.data_dir, universe, start, end)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol:
        print(f"[FAIL] no bars found in {args.data_dir}")
        return 1

    try:
        strategy = build_arm(args.arm, ma_window=args.ma_window, max_positions=args.max_positions)
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1
    costs = CostModel(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    try:
        result = run_backtest(
            bars_by_symbol, benchmark, strategy, costs, initial_equity=args.equity
        )
    except ValueError as exc:
        print(f"[FAIL] backtest error: {exc}")
        return 1

    _print_report(result.report, universe, len(result.trades), args)
    if args.json:
        print()
        print(json.dumps(result.report, indent=2, sort_keys=True))
    return 0


def _parse_grid(raw: str) -> list[float]:
    grid = [float(part) for part in raw.split(",") if part.strip()]
    if not grid:
        raise ValueError("--ma-grid must contain at least one number")
    return grid


def cmd_report(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        load_strategy(args.strategy)
        grid = _parse_grid(args.ma_grid)
    except (ConfigError, ConfigLoadError, ValueError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    start, end = _window(args)
    try:
        bars_by_symbol, benchmark = _load_bars(args.data_dir, universe, start, end)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol:
        print(f"[FAIL] no bars found in {args.data_dir}")
        return 1

    def arm_factory(ma_window: float):
        return build_arm(args.arm, ma_window=int(ma_window), max_positions=args.max_positions)

    costs = CostModel(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)

    try:
        if args.no_walk_forward:
            result = run_backtest(
                bars_by_symbol, benchmark, arm_factory(grid[0]), costs, initial_equity=args.equity
            )
            report = result.report
            folds: list[dict] = []
        else:
            wf = run_walk_forward(
                bars_by_symbol,
                benchmark,
                arm_factory,
                costs,
                param_grid=grid,
                n_folds=args.folds,
                initial_train_frac=args.train_frac,
                initial_equity=args.equity,
            )
            report = wf.report
            folds = wf.folds
    except ValueError as exc:
        print(f"[FAIL] backtest error: {exc}")
        return 1

    context = ReportContext(
        title=args.title,
        symbols=tuple(sorted(bars_by_symbol)),
        benchmark=universe.benchmark,
        strategy=f"arm {args.arm} — {ARM_DESCRIPTIONS.get(args.arm.upper(), '')}",
        data_source=f"CSV ({args.data_dir})",
        data_is_synthetic=args.synthetic,
        walk_forward=not args.no_walk_forward,
        start=date.fromisoformat(args.start) if args.start else None,
        end=date.fromisoformat(args.end) if args.end else None,
        folds=folds,
    )
    markdown = render_markdown(report, context)

    out = Path(args.out) if args.out else Path("var/reports") / f"{date.today():%Y%m%d}_backtest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"wrote {out}")
    if args.json:
        json_path = out.with_suffix(".json")
        json_path.write_text(
            json.dumps({"report": report, "folds": folds, "context": context}, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        print(f"wrote {json_path}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        params = load_strategy(args.strategy)
        limits = load_risk()
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    start, end = _window(args)
    try:
        bars_by_symbol, benchmark = _load_bars(args.data_dir, universe, start, end)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol:
        print(f"[FAIL] no bars found in {args.data_dir}")
        return 1

    costs = CostModel(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    specs: list[ArmSpec] = []
    for key in [k.strip().upper() for k in args.arms.split(",") if k.strip()]:
        judge = None
        description = ARM_DESCRIPTIONS.get(key, "")
        if key in {"B", "D"}:
            judge = RuleBasedJudge()
            description += " (offline rule-based judge)"
        elif key == "C":
            judge = JevAdapter()
        try:
            strategy = build_arm(
                key,
                judge=judge,
                limits=limits,
                params=params,
                ma_window=args.ma_window,
                max_positions=args.max_positions,
            )
        except ValueError as exc:
            print(f"[FAIL] {exc}")
            return 1
        specs.append(ArmSpec(key=key, description=description, strategy=strategy))

    results = compare_arms(
        specs, bars_by_symbol, benchmark, costs, initial_equity=args.equity
    )

    print("ai-trading-lab :: compare")
    for result in results:
        if result.report is None:
            print(f"  arm {result.key}: error: {result.error}")
            continue
        brier = result.calibration["brier"] if result.calibration else None
        print(
            f"  arm {result.key}: cum {result.report['cumulative_return']:+.2%} "
            f"excess {result.report['excess_return']:+.2%} "
            f"sharpe {result.report['sharpe']:.3f} "
            f"brier {'n/a' if brier is None else f'{brier:.3f}'}"
        )

    context = ComparisonContext(
        title=args.title,
        symbols=tuple(sorted(bars_by_symbol)),
        benchmark=universe.benchmark,
        data_source=f"CSV ({args.data_dir})",
        costs=costs,
        data_is_synthetic=args.synthetic,
    )
    markdown = render_comparison(results, context)
    out = Path(args.out) if args.out else Path("var/reports") / f"{date.today():%Y%m%d}_compare.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"wrote {out}")
    if args.json:
        json_path = out.with_suffix(".json")
        json_path.write_text(
            json.dumps(
                {"arms": [{"key": r.key, "report": r.report, "calibration": r.calibration, "error": r.error} for r in results]},
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"wrote {json_path}")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    try:
        universe = load_universe(args.universe)
        params = load_strategy(args.strategy)
        limits = load_risk()
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    start, end = _window(args)
    try:
        bars_by_symbol, _ = _load_bars(args.data_dir, universe, start, end)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if args.symbols:
        wanted = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        bars_by_symbol = {s: b for s, b in bars_by_symbol.items() if s in wanted}
    if not bars_by_symbol:
        print("[FAIL] no bars to judge")
        return 1

    try:
        judge = build_judge(args.judge, load_settings())
    except JudgmentError as exc:
        print(f"[FAIL] {exc}")
        return 1

    strategy = JudgmentStrategy(judge, limits, params=params)
    day = max(bar.day for bars in bars_by_symbol.values() for bar in bars)
    history = {s: [b for b in bars if b.day <= day] for s, bars in bars_by_symbol.items()}
    try:
        weights = strategy.target_weights(day, history)
    except JudgmentError as exc:
        print(f"[FAIL] judgment error: {exc}")
        return 1

    print("ai-trading-lab :: judge")
    print(f"  day     = {day.isoformat()}")
    print(f"  judge   = {args.judge}")
    print(f"  limits  = max {limits.max_positions} positions, {limits.max_position_pct:.0%} each")
    print()
    print(f"  {'symbol':<8}{'direction':>11}{'confidence':>12}{'weight':>10}")
    print(f"  {'-' * 8}{'-' * 11}{'-' * 12}{'-' * 10}")
    for symbol in sorted(bars_by_symbol):
        judgment = strategy.last_judgments.get(symbol, {}).get("direction")
        value = judgment.value if judgment else "n/a"
        confidence = f"{judgment.confidence:.2f}" if judgment else "n/a"
        print(f"  {symbol:<8}{value:>11}{confidence:>12}{weights.get(symbol, 0.0):>10.2%}")
    print()
    print(f"  gross exposure = {sum(weights.values()):.2%}")
    if args.json:
        print()
        print(
            json.dumps(
                {"day": day, "weights": weights, "judgments": strategy.last_judgments},
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
    return 0


def cmd_paper_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    try:
        universe = load_universe(args.universe)
        params = load_strategy(args.strategy)
        limits = load_risk()
    except (ConfigError, ConfigLoadError) as exc:
        print(f"[FAIL] configuration error: {exc}")
        return 1

    arm = args.arm.strip().upper()
    try:
        judge = build_judge(args.judge, settings) if arm in {"B", "C", "D"} else None
        strategy = build_arm(
            arm,
            judge=judge,
            limits=limits,
            params=params,
            ma_window=args.ma_window,
            max_positions=args.max_positions,
        )
        broker = get_broker(settings)
    except (ValueError, JudgmentError, LiveTradingDisabledError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    if args.provider == "csv" and not args.data_dir:
        print("[FAIL] --provider csv requires --data-dir")
        return 1

    try:
        provider = build_data_provider(settings, name=args.provider, csv_dir=args.data_dir)
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1

    start, end = date(1900, 1, 1), date(2100, 1, 1)
    try:
        bars_by_symbol: dict[str, list[Bar]] = {}
        for symbol in universe.symbols:
            bars = provider.daily_bars(symbol, start, end)
            if bars:
                bars_by_symbol[symbol] = bars
    except DataError as exc:
        print(f"[FAIL] data error: {exc}")
        return 1
    if not bars_by_symbol:
        print("[FAIL] no bars available")
        return 1

    journal = Journal(settings.journal_path)
    try:
        record = run_paper_once(
            strategy=strategy,
            broker=broker,
            bars_by_symbol=bars_by_symbol,
            journal=journal,
            limits=limits,
            dry_run=args.dry_run,
        )
    except (BrokerError, DataError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    print("ai-trading-lab :: paper-run")
    print(f"  as_of       = {record['as_of']}")
    print(f"  arm         = {arm}")
    print(f"  broker      = {broker.mode.value}")
    print(f"  dry_run     = {record['dry_run']}")
    print(f"  equity      = {record['account_equity']:.2f}")
    print(f"  drawdown    = {record['drawdown_pct']:.2%}")
    print(f"  target      = {record['target_weights']}")
    print(f"  submitted   = {len(record['submitted'])} order(s)")
    for order in record["submitted"]:
        print(f"    {order['side']:<4} {order['symbol']:<6} qty={order['qty']} ~{order['notional']:.2f}")
    if record["vetoed"]:
        print(f"  vetoed      = {len(record['vetoed'])} order(s)")
        for order in record["vetoed"]:
            print(f"    {order['side']:<4} {order['symbol']:<6} blocked: {order['veto_reason']}")
    if not args.dry_run:
        print(f"  journal     = {settings.journal_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-trading-lab")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="verify configuration and safety gates")
    doctor.add_argument(
        "--confirm-live",
        action="store_true",
        help="satisfy the third live-trading gate (for diagnostics only)",
    )
    doctor.set_defaults(func=cmd_doctor)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--data-dir", required=True, help="directory of <SYMBOL>.csv files")
        p.add_argument("--universe", default=None, help="path to universe.yaml")
        p.add_argument("--strategy", default=None, help="path to strategy.yaml")
        p.add_argument("--start", default=None, help="ISO start date (inclusive)")
        p.add_argument("--end", default=None, help="ISO end date (inclusive)")
        p.add_argument("--arm", default="A", help="experiment arm (A..D)")
        p.add_argument("--ma-window", type=int, default=50, help="trend moving-average window")
        p.add_argument("--max-positions", type=int, default=10)
        p.add_argument("--fee-bps", type=float, default=1.0, help="per-side fee in bps")
        p.add_argument("--slippage-bps", type=float, default=5.0, help="per-side slippage in bps")
        p.add_argument("--equity", type=float, default=100_000.0, help="initial equity")

    backtest = sub.add_parser("backtest", help="run the walk-forward backtest over CSV bars")
    add_common(backtest)
    backtest.add_argument("--json", action="store_true", help="also print the raw report JSON")
    backtest.set_defaults(func=cmd_backtest)

    report = sub.add_parser("report", help="write a publishable Markdown backtest report")
    add_common(report)
    report.add_argument("--out", default=None, help="output markdown path")
    report.add_argument("--title", default="ai-trading-lab — backtest report")
    report.add_argument("--json", action="store_true", help="also write the raw report JSON")
    report.add_argument("--synthetic", action="store_true", help="mark data as synthetic")
    report.add_argument("--no-walk-forward", action="store_true", help="use a single window")
    report.add_argument("--ma-grid", default="20,50,100,200", help="comma-separated MA candidates")
    report.add_argument("--folds", type=int, default=5, help="number of walk-forward folds")
    report.add_argument("--train-frac", type=float, default=0.4, help="initial in-sample fraction")
    report.set_defaults(func=cmd_report)

    judge = sub.add_parser("judge", help="run the judgment pipeline for the latest day")
    judge.add_argument("--data-dir", required=True, help="directory of <SYMBOL>.csv files")
    judge.add_argument("--universe", default=None, help="path to universe.yaml")
    judge.add_argument("--strategy", default=None, help="path to strategy.yaml")
    judge.add_argument("--start", default=None, help="ISO start date (inclusive)")
    judge.add_argument("--end", default=None, help="ISO end date (inclusive)")
    judge.add_argument(
        "--judge", default="rules", choices=["rules", "gemini", "jev"], help="judgment model"
    )
    judge.add_argument("--symbols", default=None, help="comma-separated subset of symbols")
    judge.add_argument("--json", action="store_true", help="also print the raw JSON")
    judge.set_defaults(func=cmd_judge)

    compare = sub.add_parser("compare", help="compare experiment arms on the same data")
    compare.add_argument("--data-dir", required=True, help="directory of <SYMBOL>.csv files")
    compare.add_argument("--universe", default=None, help="path to universe.yaml")
    compare.add_argument("--strategy", default=None, help="path to strategy.yaml")
    compare.add_argument("--start", default=None, help="ISO start date (inclusive)")
    compare.add_argument("--end", default=None, help="ISO end date (inclusive)")
    compare.add_argument("--arms", default="A,B,D", help="comma-separated arms (A,B,C,D)")
    compare.add_argument("--ma-window", type=int, default=50, help="trend moving-average window")
    compare.add_argument("--max-positions", type=int, default=10)
    compare.add_argument("--fee-bps", type=float, default=1.0, help="per-side fee in bps")
    compare.add_argument("--slippage-bps", type=float, default=5.0, help="per-side slippage in bps")
    compare.add_argument("--equity", type=float, default=100_000.0, help="initial equity")
    compare.add_argument("--out", default=None, help="output markdown path")
    compare.add_argument("--title", default="ai-trading-lab — arm comparison")
    compare.add_argument("--synthetic", action="store_true", help="mark data as synthetic")
    compare.add_argument("--json", action="store_true", help="also write the raw JSON")
    compare.set_defaults(func=cmd_compare)

    paper = sub.add_parser("paper-run", help="run one daily paper-trading cycle")
    paper.add_argument(
        "--provider", default="auto", choices=["auto", "alpaca", "stooq", "csv"]
    )
    paper.add_argument("--data-dir", default=None, help="required when --provider csv")
    paper.add_argument("--universe", default=None, help="path to universe.yaml")
    paper.add_argument("--strategy", default=None, help="path to strategy.yaml")
    paper.add_argument("--arm", default=os.environ.get("PAPER_ARM", "A"), help="experiment arm")
    paper.add_argument(
        "--judge",
        default=os.environ.get("PAPER_JUDGE", "rules"),
        choices=["rules", "gemini", "jev"],
    )
    paper.add_argument("--ma-window", type=int, default=50)
    paper.add_argument("--max-positions", type=int, default=10)
    paper.add_argument("--dry-run", action="store_true", help="plan orders without submitting")
    paper.set_defaults(func=cmd_paper_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
