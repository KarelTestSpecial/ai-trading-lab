# Capability narrative

A 2-minute read for a technical evaluator (a hiring manager, a client, a peer).

## One-liner

A public, transparent **AI trading and backtesting platform** for US equities
(daily/swing): the engine, the data layer, the AI judgment layer and the daily
paper loop are all built from scratch in dependency-light Python, with honesty
and safety enforced in code rather than promised in a README.

## What I built

A complete pipeline, not a script:

```
Data → Features → Context → Judgment → Policy → Risk veto → Execution → Journal
```

- **Data layer** — Alpaca (IEX) primary, Stooq fallback, CSV offline; one
  standard-library HTTP client, no vendor SDK.
- **Feature engine** — deterministic snapshots (returns, MA distances, z-scores,
  volatility). No black boxes.
- **Backtest engine** — walk-forward, look-ahead-free, costs on turnover, SPY
  benchmark mandatory.
- **AI layer** — a pluggable judgment model (Google AI Studio over plain REST, a
  deterministic offline judge, and an adapter stub for a calibrated decision
  model) that answers atomic, confidence-scored questions about a snapshot.
- **Policy + hard risk vetoes** — weights live in code; drawdown, daily-loss,
  position-count and position-size limits have absolute veto power.
- **Paper loop** — a daily GitHub Action places Alpaca paper orders and commits
  an append-only journal, so the track record is tamper-evident.
- **Dashboard** — a static site (Vite + TypeScript, no chart libraries) that
  renders the committed journal.

## Key engineering decisions

1. **Code computes, the model judges.** All arithmetic is deterministic; the LLM
   only supplies fuzzy judgments with calibrated confidence.
2. **Honesty enforced in code.** A performance report *cannot* be produced
   without a benchmark and a cost model; the report always states its own
   limitations.
3. **No silent fallback.** A missing API key, an unwired model, or a malformed
   model answer fails loudly — a judgment never quietly becomes a trade.
4. **Live trading is hard-gated.** Three independent switches, plus a public-demo
   switch that makes live impossible.
5. **Calibration is measured, not claimed.** Every confidence is scored against
   realised outcomes (Brier/ECE).
6. **Dependency-light by design.** No pandas/numpy, no LLM SDK, no HTTP client
   library — the whole system is auditable and runs offline in tests.

## What I deliberately did not do

- No proprietary-feed or indicator reverse-engineering.
- No live trading and no profitability claims.
- No fabricated track record: the dashboard shows the real (currently empty)
  journal, not seeded numbers.

## How to verify it yourself

```bash
uv run --group dev pytest -q                 # 100+ tests, offline
uv run python -m src.cli doctor              # safety gates
uv run python scripts/make_sample_data.py --out var/sample_bars
uv run python -m src.cli backtest --data-dir var/sample_bars
uv run python -m src.cli report --data-dir var/sample_bars --synthetic
uv run python -m src.cli compare --data-dir var/sample_bars --synthetic --arms A,B,C,D
uv run python -m src.cli judge --data-dir var/sample_bars --judge rules
```

Then read `ARCHITECTURE.md`, `RISICO.md`, the generated report, and the
`journal/decisions.jsonl` git history.
