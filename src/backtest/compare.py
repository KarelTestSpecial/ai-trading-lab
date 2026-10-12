"""Compare experiment arms on identical data and costs.

Runs several arms through the same engine, collects each arm's honest report and
(for AI arms) its probability calibration, and renders a single comparison. An
arm that cannot run (e.g. arm C without its model) is reported as an explicit
error row rather than being silently dropped.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from cadence_core.calibration import brier_score, calibration_table, expected_calibration_error
from cadence_core.judgment.base import JudgmentError

from src.backtest.calibration import CalibrationRecorder
from src.backtest.engine import Strategy, run_backtest
from src.backtest.metrics import CostModel
from src.data.base import Bar


@dataclass(frozen=True)
class ArmSpec:
    key: str
    description: str
    strategy: Strategy


@dataclass(frozen=True)
class ArmResult:
    key: str
    description: str
    report: dict | None
    calibration: dict | None
    error: str | None


def evaluate_arm(
    spec: ArmSpec,
    bars_by_symbol: dict[str, list[Bar]],
    benchmark: list[Bar],
    costs: CostModel,
    *,
    initial_equity: float = 100_000.0,
) -> ArmResult:
    recorder = CalibrationRecorder()
    try:
        result = run_backtest(
            bars_by_symbol,
            benchmark,
            spec.strategy,
            costs,
            initial_equity=initial_equity,
            on_decision=recorder,
        )
    except (ValueError, JudgmentError) as exc:
        return ArmResult(spec.key, spec.description, None, None, str(exc))

    calibration = None
    if recorder.predictions:
        calibration = {
            "n": len(recorder.predictions),
            "brier": brier_score(recorder.predictions),
            "ece": expected_calibration_error(recorder.predictions),
            "table": calibration_table(recorder.predictions),
        }
    return ArmResult(spec.key, spec.description, result.report, calibration, None)


def compare_arms(
    specs: Sequence[ArmSpec],
    bars_by_symbol: dict[str, list[Bar]],
    benchmark: list[Bar],
    costs: CostModel,
    *,
    initial_equity: float = 100_000.0,
) -> list[ArmResult]:
    return [
        evaluate_arm(spec, bars_by_symbol, benchmark, costs, initial_equity=initial_equity)
        for spec in specs
    ]


@dataclass(frozen=True)
class ComparisonContext:
    title: str
    symbols: tuple[str, ...]
    benchmark: str
    data_source: str
    costs: CostModel
    data_is_synthetic: bool = False


def _pct(value) -> str:
    return "n/a" if value is None else f"{value:+.2%}"


def _num(value, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_comparison(results: Sequence[ArmResult], ctx: ComparisonContext) -> str:
    lines = [
        f"# {ctx.title}",
        "",
        (
            "Same universe, same period, same costs — only the arm changes. "
            "This is a **simulation**; not investment advice."
        ),
        "",
        "## Configuration",
        "",
        "| field | value |",
        "|---|---|",
        f"| universe | {', '.join(ctx.symbols)} |",
        f"| benchmark | {ctx.benchmark} |",
        f"| data source | {ctx.data_source} |",
        f"| costs | {ctx.costs.fee_bps:g} bps fee + {ctx.costs.slippage_bps:g} bps slippage (per side) |",
        "",
        "## Arms",
        "",
        "| arm | what | cum. return | excess | sharpe | max DD | brier | ECE |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        if result.report is None:
            lines.append(f"| {result.key} | {result.description} | — | — | — | — | — | — |")
            continue
        report = result.report
        calibration = result.calibration or {}
        lines.append(
            f"| {result.key} | {result.description} "
            f"| {_pct(report['cumulative_return'])} | {_pct(report['excess_return'])} "
            f"| {_num(report['sharpe'])} | {_pct(report['max_drawdown'])} "
            f"| {_num(calibration.get('brier'))} | {_num(calibration.get('ece'))} |"
        )
    lines.append("")

    errors = [r for r in results if r.error]
    if errors:
        lines.append("### Arms that could not run")
        lines.append("")
        lines.extend(f"- **{r.key}**: {r.error}" for r in errors)
        lines.append("")

    calibrated = [r for r in results if r.calibration]
    if calibrated:
        lines.append("## Calibration (P(up) vs realised)")
        lines.append("")
        for result in calibrated:
            calibration = result.calibration
            lines.append(
                f"### Arm {result.key} — n={calibration['n']}, "
                f"Brier={_num(calibration['brier'])}, ECE={_num(calibration['ece'])}"
            )
            lines.append("")
            lines.append("| bin | count | avg prob | empirical |")
            lines.append("|---|---|---|---|")
            for row in calibration["table"]:
                lines.append(
                    f"| {row['bin_lower']:.1f}–{row['bin_upper']:.1f} | {row['count']} "
                    f"| {row['avg_prob']:.2f} | {row['empirical']:.2f} |"
                )
            lines.append("")

    lines.append("## Limitations")
    lines.append("")
    if ctx.data_is_synthetic:
        lines.append(
            "- ⚠️ **Synthetic data.** These numbers come from generated prices; they "
            "validate the pipeline, not any edge."
        )
    lines.extend(
        [
            "- **Simulation only** — no real money, not investment advice.",
            "- **Survivorship bias:** the universe is today's large-caps.",
            "- **No live track record yet** (the paper loop is Fase 5).",
            (
                "- Calibration of a deterministic judge is expected to be poor; the "
                "point is that the machinery measures it honestly."
            ),
        ]
    )
    lines.append("")
    lines.append("## Disclaimer")
    lines.append("")
    lines.append("See [DISCLAIMER.md](../DISCLAIMER.md) in the repository root.")
    lines.append("")
    return "\n".join(lines)
