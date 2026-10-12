# ARCHITECTURE

## Principles

1. **Code computes, the model judges.** All arithmetic (returns, MAs, volatility,
   z-scores, inventory, drawdown) is deterministic code. The AI layer only
   answers atomic, fuzzy questions about a compact state snapshot.
2. **Hard risk vetoes have absolute power.** Checked before every order, never
   delegated to the model.
3. **Honesty is enforced in code.** No performance report without a benchmark and
   a cost model.
4. **Paper by default; live is hard-gated.**
5. **Everything is logged.** Append-only journal; each run is reproducible.

## Pipeline

```
Data layer            → adjusted daily bars (Alpaca IEX primary, Stooq fallback, CSV offline)
Feature/State engine  → deterministic snapshot (< 400 tokens)
Context layer         → LLM synthesises news/filings/macro into typed context
Judgment layer        → pluggable: LLMJudge | JevAdapter | DeterministicJudge
Policy engine         → combines signals with weights defined in code
Risk engine           → deterministic vetoes (absolute)
Execution             → Broker abstraction (Paper/Live)
Journal               → append-only JSONL, committed daily
```

## Backtest engine (Fase 1)

The engine is deliberately **pure Python — no pandas/numpy** — so every number is
inspectable and the whole backtest runs offline in milliseconds. Timing is
look-ahead free:

- A decision at the close of day *t* sees only bars dated `<= t`.
- The resulting weights are held during day *t+1*, so the portfolio earns
  *t+1*'s return.
- Costs are charged on **turnover** (`Σ|Δweight| × one-way fraction`).
- Weights are validated: gross exposure `> 1.0` (leverage) is rejected.
- `build_report` refuses to run without a benchmark series and a cost model.

## AI layer (Fase 3)

```
Context (news/filings/macro) → Digest → Judgment model → Policy → weights
```

- **Context** (`src/context/`): `ContextProvider` interface, an RSS/Atom provider
  (stdlib XML) and a static provider. `build_digest` condenses items into a
  token-budgeted block — trimming is code, so prompts are reproducible.
- **Judgment** (`src/judgment/`): the model answers atomic questions over a
  snapshot and returns a typed `Judgment(value, confidence, rationale)`. Clients:
  `LLMJudge` over a pluggable `LLMClient` (`GeminiClient` = Google AI Studio REST,
  stdlib only; `StaticLLMClient` for tests), `JevAdapter` over `JevClient` (arm
  C, from cadence-core; requires a JEV key, otherwise a hard explicit error) and
  `RuleBasedJudge` (deterministic offline).
  Parsing is defensive: anything out of schema/range raises `JudgmentError`.
- **Policy** (`src/policy/policy.py`): maps judgments to signed scores and then to
  long-only, non-levered weights capped by the hard limits. Weights live in code,
  never in the prompt.
- **Arms**: `build_arm("B", judge=...)` / `build_arm("C", judge=...)` build the
  same `JudgmentStrategy` with a different model, so B and C are comparable.

Honesty rules: a missing key or unwired model fails loudly (no silent fallback);
a judgment never silently becomes a trade. Full LLM backtests are intentionally
**not** run here — one call per symbol per day would be slow and rate-limited;
the daily paper loop (Fase 5) is where the real model runs once per day.

## Arms comparison & calibration (Fase 4)

- **Arm D — hybrid** (`src/strategy/hybrid.py`): the trend rule *gates* the
  universe (only symbols above their MA are eligible) and the judgment model
  sizes within it. Rules prune, AI selects.
- **`compare-arms`** (`src/backtest/compare.py`): runs several arms through the
  same engine, same data, same costs, and renders one comparison. An arm that
  cannot run is an explicit error row, never silently dropped.
- **Calibration** (`src/backtest/calibration.py`): the engine accepts an
  `on_decision` observer; `CalibrationRecorder` captures (prob_up, realised
  direction) per decision. `brier_score` and `expected_calibration_error` quantify
  whether a stated confidence is honest. A deterministic judge is expected to be
  miscalibrated — the point is that the machinery measures it.

## Experiment arms & walk-forward (Fase 2)

- **Arms** (`src/strategy/arms.py`): a single `build_arm(name, **params)` factory
  so every arm is constructed identically and compared fairly. Fase 2 ships
  **arm A** (deterministic trend baseline); B/C/D follow in Fase 3-4.
- **Walk-forward** (`src/backtest/walkforward.py`): expanding windows. A parameter
  is chosen on the in-sample window only, then scored on the next *unseen*
  window. The per-fold choices are printed, so selection cannot be hidden — the
  direct antidote to in-sample overfitting.
- **Report** (`src/backtest/report.py`): renders a publishable Markdown artefact
  that always shows the benchmark and the cost model, and always states its own
  limitations (survivorship bias, synthetic-data warning, no live record yet).

## Dashboard & deployment (Fase 6)

`dashboard/` is a Vite + TypeScript static site with **no chart libraries** — the
equity curve is drawn with inline SVG. At build time `scripts/copy-journal.mjs`
copies the committed `journal/decisions.jsonl` into `public/`, so the deployed
site ships exactly the data that is in git. Deployment is a GitHub Pages workflow.

## Daily paper loop & journal-in-git (Fase 5)

`src/loop.py::run_paper_once` is one cycle: fetch bars -> snapshot -> judge ->
policy weights -> `plan_orders` (pure) -> hard risk vetoes -> submit to the paper
broker -> append to the journal. The broker, provider and strategy are injected,
so the loop is unit-tested offline.

- **Broker client** (`src/execution/broker.py`): Alpaca REST over the stdlib via
  an injectable `Transport`; paper vs live differ only by endpoint. A missing key
  or a rejected order raises `BrokerError` — never a silent no-op.
- **Journal** (`journal/decisions.jsonl`): append-only and **committed**. The
  daily Action appends and pushes, so the public git history is tamper-evident.
- **GitHub Action** (`.github/workflows/daily-paper.yml`): weekday cron, paper
  mode + public-demo forced, commits the journal with a bot identity.
- Risk vetoes (`src/policy/risk.py`) run before every order: drawdown, daily
  loss, max positions and per-position size have absolute power.

## Broker abstraction & live gate

Paper and live differ only by **endpoint + keys**, never by code:

| | Paper | Live |
|---|---|---|
| Base URL | `paper-api.alpaca.markets` | `api.alpaca.markets` |
| KYC | not required | required |
| Funds | simulated | real |

Live trading requires **all three** gates simultaneously:

1. `TRADING_MODE=live`
2. `ALLOW_LIVE_TRADING=true`
3. `confirm_live=True` passed explicitly in code

Additionally, `PUBLIC_DEMO=true` makes live trading **impossible**, even with all
three gates satisfied. See `src/execution/broker.py`.

Belgium is covered for live accounts via Alpaca's EEA passporting (July 2026;
Alpaca Europe / WealthKernel, plus Alpaca Clearing in the US). Live is a
*product capability for others* — this project itself never trades real money.

## Data sources (all free)

| Data | Primary | Fallback |
|---|---|---|
| Historical/recent daily bars | Alpaca (IEX) | yfinance, Stooq |
| Fundamentals/filings | SEC EDGAR | yfinance |
| News | RSS | NewsAPI free |
| Macro | FRED | — |
| Earnings calendar | yfinance | Finnhub free |

**No proprietary-feed or indicator reverse-engineering.** Indicators are either
our own implementations or open-source. Charting uses open-source libraries
(e.g. TradingView Lightweight Charts, MIT).

## Data integrity

- One primary source + cross-check; discrepancies are logged, never silently
  resolved.
- The exact input snapshot is stored with each decision (reproducibility).
- Adjusted bars (splits/dividends).
- Survivorship bias handled in universe selection for backtests.
