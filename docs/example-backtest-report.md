# ai-trading-lab — example backtest report (synthetic data)

_Generated 2026-10-12 07:33 UTC._

This is a **simulation** produced by the `ai-trading-lab` backtest engine. It does not trade real money and is not investment advice.

## Configuration

| field | value |
|---|---|
| strategy | arm A — Deterministic trend baseline: equal-weight the symbols above their MA. |
| universe | AAPL, AMZN, GOOGL, JPM, META, MSFT, NVDA, UNH, V, XOM |
| benchmark | SPY |
| period | 295 trading days |
| data source | CSV (var/sample_bars) |
| costs | 1 bps fee + 5 bps slippage (per side) |
| evaluation | walk-forward (out-of-sample) |

## Results (295 periods)

| metric | strategy | benchmark |
|---|---|---|
| cumulative return | +5.32% | +5.94% |
| annualized return | +4.53% | n/a |
| sharpe | 0.468 | 0.423 |
| sortino | 0.683 | n/a |
| max drawdown | -8.72% | -11.90% |
| hit rate | +51.19% | n/a |
| **excess return** | **-0.62%** | |

## Walk-forward folds

| fold | train | test | chosen MA | train ret | test ret | benchmark test ret |
|---|---|---|---|---|---|---|
| 0 | 2024-11-11 → 2025-08-15 | 2025-08-18 → 2025-11-07 | 200 | +0.00% | -1.67% | -4.62% |
| 1 | 2024-11-11 → 2025-11-07 | 2025-11-10 → 2026-01-30 | 200 | -1.70% | +2.54% | +1.80% |
| 2 | 2024-11-11 → 2026-01-30 | 2026-02-02 → 2026-04-24 | 200 | +0.92% | +2.23% | +13.84% |
| 3 | 2024-11-11 → 2026-04-24 | 2026-04-27 → 2026-07-17 | 200 | +3.73% | -1.61% | -1.84% |
| 4 | 2024-11-11 → 2026-07-17 | 2026-07-20 → 2026-10-09 | 200 | +2.42% | +3.85% | -2.37% |

## Limitations

- ⚠️ **Synthetic data.** These numbers come from generated prices, not real markets. They validate the engine, not any strategy edge.
- **Simulation only.** No real money is traded; this is not investment advice.
- **Past performance is not indicative of future results.**
- **Survivorship bias:** the universe is today's list of large-caps; using it historically overstates returns because delisted losers are absent.
- **Walk-forward** chooses parameters on in-sample windows only and scores the next unseen window; the per-fold choices are shown above so the selection cannot be hidden.
- **Costs** are modelled as a flat per-side fee + slippage on turnover; real fills, market impact and borrow costs differ.
- **No live track record yet.** The paper-trading loop (Fase 5) is what turns this into tamper-evident evidence; a backtest alone is not.

## Disclaimer

See [DISCLAIMER.md](../DISCLAIMER.md) in the repository root.
