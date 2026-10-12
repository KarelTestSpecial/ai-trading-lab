# RISICO.md — honest risks and limitations

This file is deliberately blunt. A credible system states what can go wrong; that
is what makes the rest believable.

## 1. No profitability promise

A backtest that looks good is not evidence of future returns. Most retail
strategies fail after costs. This project's claim is **engineering quality and
honesty**, not returns.

## 2. Known methodological risks

- **Overfitting** — mitigated by walk-forward / out-of-sample testing, never
  in-sample tuning.
- **Cost drag** — fees and slippage can erase an edge; always modelled, never
  omitted.
- **Survivorship bias** — using today's index members on historical data inflates
  results; delisted names must be included.
- **Look-ahead bias** — every feature uses only information strictly before the
  decision; enforced by timestamp discipline and logged snapshots.
- **Calibration drift** — if the judgment model says P=0.8, we must verify events
  tagged 0.8 actually happen ~80% of the time (Brier/ECE). Vendor calibration is
  not our calibration.

## 3. Market-structure limits

- Retail cannot compete in the microsecond lane of US equities (colocated firms).
  This project operates at daily cadence, where latency is irrelevant — not in the
  HFT lane.
- Free data feeds (IEX) cover only part of consolidated volume; this affects
  intraday analysis, not end-of-day bars.

## 4. AI-layer risks

- Public frontier models are available to everyone; a public model alone is **not**
  an edge.
- LLM outputs can be confidently wrong; hence typed judgments + confidence + the
  hard risk veto, never "let the model trade".

## 5. Operational & legal

- **Simulation only.** No real money, no advice, no management of third-party
  capital. See [DISCLAIMER.md](DISCLAIMER.md).
- If the project were ever pointed at real accounts, that would raise regulatory
  (FSMA) questions and require KYC, funding and tax handling — out of scope here.
- No personal data, no PII, no medical/legal context of the author is included in
  this repository.
