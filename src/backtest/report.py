"""Honest performance-report renderer.

Turns a backtest report into a Markdown artefact that is safe to publish: it
always shows the benchmark and the cost model, and it always states its own
limitations. A report is never produced from a bare return number (the honesty
invariant in `metrics.build_report` already blocks that upstream).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime


@dataclass(frozen=True)
class ReportContext:
    title: str
    symbols: tuple[str, ...]
    benchmark: str
    strategy: str
    data_source: str
    data_is_synthetic: bool = False
    walk_forward: bool = False
    start: date | None = None
    end: date | None = None
    folds: list[dict] = field(default_factory=list)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2%}"


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _period(ctx: ReportContext, report: dict) -> str:
    if ctx.start and ctx.end:
        return f"{ctx.start.isoformat()} → {ctx.end.isoformat()}"
    return f"{report['n_periods']} trading days"


def _results_table(report: dict) -> list[str]:
    rows = [
        ("cumulative return", _pct(report["cumulative_return"]), _pct(report["benchmark_cumulative_return"])),
        ("annualized return", _pct(report["annualized_return"]), "n/a"),
        ("sharpe", _num(report["sharpe"]), _num(report["benchmark_sharpe"])),
        ("sortino", _num(report["sortino"]), "n/a"),
        ("max drawdown", _pct(report["max_drawdown"]), _pct(report["benchmark_max_drawdown"])),
        ("hit rate", _pct(report["hit_rate"]), "n/a"),
    ]
    lines = ["| metric | strategy | benchmark |", "|---|---|---|"]
    lines += [f"| {name} | {s} | {b} |" for name, s, b in rows]
    lines.append(f"| **excess return** | **{_pct(report['excess_return'])}** | |")
    return lines


def _folds_table(folds: list[dict]) -> list[str]:
    lines = [
        "| fold | train | test | chosen MA | train ret | test ret | benchmark test ret |",
        "|---|---|---|---|---|---|---|",
    ]
    for fold in folds:
        lines.append(
            f"| {fold['fold']} | {fold['train_start']} → {fold['train_end']} "
            f"| {fold['test_start']} → {fold['test_end']} "
            f"| {fold['chosen_param']:.0f} | {_pct(fold['train_return'])} "
            f"| {_pct(fold['test_return'])} | {_pct(fold['benchmark_test_return'])} |"
        )
    return lines


def _limitations(ctx: ReportContext) -> list[str]:
    items = [
        "**Simulation only.** No real money is traded; this is not investment advice.",
        "**Past performance is not indicative of future results.**",
        (
            "**Survivorship bias:** the universe is today's list of large-caps; using "
            "it historically overstates returns because delisted losers are absent."
        ),
        (
            "**Costs** are modelled as a flat per-side fee + slippage on turnover; "
            "real fills, market impact and borrow costs differ."
        ),
        (
            "**No live track record yet.** The paper-trading loop (Fase 5) is what "
            "turns this into tamper-evident evidence; a backtest alone is not."
        ),
    ]
    if ctx.walk_forward:
        items.insert(
            3,
            "**Walk-forward** chooses parameters on in-sample windows only and scores "
            "the next unseen window; the per-fold choices are shown above so the "
            "selection cannot be hidden.",
        )
    if ctx.data_is_synthetic:
        items.insert(
            0,
            "⚠️ **Synthetic data.** These numbers come from generated prices, not real "
            "markets. They validate the engine, not any strategy edge.",
        )
    return items


def render_markdown(report: dict, ctx: ReportContext) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    costs = report["cost_model"]
    lines: list[str] = []
    lines.append(f"# {ctx.title}")
    lines.append("")
    lines.append(f"_Generated {generated}._")
    lines.append("")
    lines.append(
        "This is a **simulation** produced by the `ai-trading-lab` backtest engine. "
        "It does not trade real money and is not investment advice."
    )
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    lines.append(f"| strategy | {ctx.strategy} |")
    lines.append(f"| universe | {', '.join(ctx.symbols)} |")
    lines.append(f"| benchmark | {ctx.benchmark} |")
    lines.append(f"| period | {_period(ctx, report)} |")
    lines.append(f"| data source | {ctx.data_source} |")
    lines.append(
        f"| costs | {costs['fee_bps']:g} bps fee + {costs['slippage_bps']:g} bps slippage (per side) |"
    )
    lines.append(f"| evaluation | {'walk-forward (out-of-sample)' if ctx.walk_forward else 'single window'} |")
    lines.append("")
    lines.append(f"## Results ({report['n_periods']} periods)")
    lines.append("")
    lines.extend(_results_table(report))
    lines.append("")
    if ctx.walk_forward and ctx.folds:
        lines.append("## Walk-forward folds")
        lines.append("")
        lines.extend(_folds_table(ctx.folds))
        lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.extend(f"- {item}" for item in _limitations(ctx))
    lines.append("")
    lines.append("## Disclaimer")
    lines.append("")
    lines.append("See [DISCLAIMER.md](../DISCLAIMER.md) in the repository root.")
    lines.append("")
    return "\n".join(lines)
