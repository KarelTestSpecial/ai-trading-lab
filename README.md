# ai-trading-lab

A transparent, open AI-driven **paper-trading and backtesting platform** for US
equities (daily/swing). Built as a capability showcase: the point is not to
promise returns, but to demonstrate honest, production-grade engineering of an
AI/quant system.

> **This is a simulation. It does not trade real money. It is not investment
> advice.** See [DISCLAIMER.md](DISCLAIMER.md).

## Why this exists

Most "AI trading bot" projects overfit a backtest and hide the costs. This one is
built around the opposite idea:

- **Honesty is enforced in code.** A performance report *cannot* be produced
  without a benchmark and a cost model (`src/backtest/metrics.py`).
- **Live trading is hard-gated.** Paper is the default; going live requires three
  independent switches *and* is impossible while `PUBLIC_DEMO=true`
  (`src/execution/broker.py`).
- **Every decision is logged.** An append-only journal records the exact input
  snapshot, the rationale and the outcome — the audit trail and the calibration
  data.
- **Confidence must mean something.** Every judgment's stated probability is
  scored against realised outcomes (Brier/ECE); miscalibration is shown, not
  hidden.
- **The model only judges; code computes.** Indicators are pure functions; the AI
  layer answers atomic, calibrated questions about a compact state snapshot.
- **No silent fallback.** A missing LLM key or an unwired model fails loudly; a
  judgment is never faked. Malformed model output can never become a trade.

## Architecture (short)

```
Data → Features → Context (LLM) → Judgment → Policy → Risk veto → Execution → Journal
```

Full details: [ARCHITECTURE.md](ARCHITECTURE.md). Risks and limitations:
[RISICO.md](RISICO.md).

## Status

| Fase | Deliverable | Status |
|---|---|---|
| 0 | Plan, scaffold, guardrails, broker gate, CI | ✅ |
| 1 | Data layer + features + backtest engine (costs + SPY benchmark) | ✅ |
| 2 | Baseline rules (arm A) + honest metrics report | ✅ |
| 3 | LLM context + judgment layer (arm B) + Jev stub (arm C) | ✅ |
| 4 | Hybrid (arm D) + `compare-arms` + calibration (Brier/ECE) | ✅ |
| 5 | GitHub-Action daily paper loop + journal-in-git | ✅ |
| 6 | Dashboard + deployment + capability narrative | ✅ |

## Quickstart

```bash
cp .env.example .env      # defaults are safe: paper mode, live disabled
uv run python -m src.cli doctor
uv run --group dev pytest -q

# End-to-end backtest on synthetic sample data (no network, no API keys):
uv run python scripts/make_sample_data.py --out var/sample_bars
uv run python -m src.cli backtest --data-dir var/sample_bars --ma-window 50

# Publishable Markdown report (walk-forward by default):
uv run python -m src.cli report --data-dir var/sample_bars --synthetic --json

# AI judgment pipeline for the latest day (offline "rules" judge; no key needed):
uv run python -m src.cli judge --data-dir var/sample_bars --judge rules

# Compare arms A/B/C/D on identical data + costs, with calibration:
uv run python -m src.cli compare --data-dir var/sample_bars --synthetic --arms A,B,C,D --json
```

`doctor` prints the resolved configuration and verifies that live trading is
gated off. `backtest` runs the walk-forward engine and prints an honest report:
strategy vs SPY, net of modelled costs, with no look-ahead.

## Running the daily paper loop

The loop runs as a GitHub Action (`.github/workflows/daily-paper.yml`) on weekday
evenings: it places Alpaca **paper** orders, appends to `journal/decisions.jsonl`
and commits it, so the public git history becomes a tamper-evident track record.

Setup:
1. Create a free Alpaca **paper** account and generate API keys.
2. Add repository secrets `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`.
3. Enable the workflow (or run it manually). Keys are never committed.

Locally (dry run plans orders without submitting):

```bash
export ALPACA_API_KEY=... ALPACA_SECRET_KEY=...
uv run python -m src.cli paper-run --provider auto --dry-run
```

## Dashboard

`dashboard/` is a static Vite + TypeScript site (no chart libraries) that renders
the committed `journal/decisions.jsonl`: equity curve, drawdown, latest target
weights, submitted orders, risk vetoes and the full decision log. It shows an
honest empty state until the paper loop has run.

```bash
cd dashboard
pnpm install
pnpm build     # copies ../journal/decisions.jsonl into public/ and builds dist/
```

Deployment is a GitHub Pages workflow (`.github/workflows/pages.yml`). A
generated example report lives in [docs/example-backtest-report.md](docs/example-backtest-report.md),
and the 2-minute capability pitch in [docs/capability-narrative.md](docs/capability-narrative.md).

## Repository layout

```
config/     universe · strategy · risk
src/        data features context judgment policy backtest execution journal api cli
dashboard/  Vite + TypeScript dashboard (Fase 6)
tests/      guardrail tests
```

## Licence

MIT — see [LICENSE](LICENSE).
