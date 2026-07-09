# Research AI Loop Design

This document describes how the current tools can work together as a research loop.

This is research/simulation only. It does not place orders or connect to brokers.

## Current pieces

| Layer | Existing role |
| --- | --- |
| Market Memory | Stores evidence, relationships, hypotheses, packets, and research themes. |
| Data Catalog / Data Library | Organizes JSON, CSV, Markdown, and managed artifacts. |
| Artifact Writer | Saves research outputs in consistent locations. |
| Output Router | Registers existing outputs without moving or deleting them. |
| Quant Schema | Stores typed research rows such as experiments, strategies, backtests, walk-forward runs, and data-quality events. |
| Quant Dashboard | Shows recent experiments, best backtests, validation runs, universe runs, and warnings. |
| Auto Lab / Strategy Engine | Generates or evaluates strategy candidates. |
| BackTestEngine | Simulates strategies on historical data. |
| Walk-forward runner | Tests whether results survive out-of-sample validation. |
| Universe runner | Tests whether a strategy works across multiple related symbols. |

## Target loop

```text
1. Market Memory chooses research theme
   Example: AI infrastructure semiconductors

2. Universe Builder chooses symbols
   Example: AMD, NVDA, TSM, ASML, AVGO, SMH

3. Strategy Generator proposes candidates
   Example: momentum breakout, pullback, volatility filter, trend confirmation

4. Backtest Engine simulates each candidate
   Records return, drawdown, Sharpe, win rate, trade count, slippage assumptions

5. Walk-forward validates survivors
   Splits training/testing windows to reduce overfitting

6. Universe runner checks robustness
   Tests across a basket rather than only one symbol

7. Risk/Data Quality layer checks warnings
   Flags missing prices, too few rows, extreme NaN values, unrealistic metrics

8. Quant Schema stores typed results
   experiment_runs, strategy_runs, backtest_runs, walk_forward_runs, universe_runs

9. Quant Dashboard shows what happened
   Best candidates, weak candidates, warnings, coverage

10. Market Memory absorbs the outcome
   Good patterns become stronger hypotheses
   Bad patterns become warnings
   Missing-data issues become data-quality memories

11. Next loop starts smarter
```

## Why this makes the AI smarter

The AI should not just generate strategies once. It should learn from the outcomes of every simulated test.

The loop improves strategy research by tracking:

- What themes produced useful candidates
- What symbols had stable results
- Which indicators failed repeatedly
- Which strategies only worked in one backtest but failed walk-forward
- Which results were invalid because of poor data
- Which hypotheses deserve more testing
- Which hypotheses should be retired

## Required guardrails

The loop should be conservative.

Minimum checks before a candidate is promoted:

```text
Backtest complete
Walk-forward complete
Universe test complete
Data quality PASS or WARN-only
Minimum trade count satisfied
Max drawdown under configured limit
No impossible return or NaN metrics
Out-of-sample metrics not much worse than in-sample metrics
```

## Suggested scoring model

A simple research score can start like this:

```text
research_score =
    25% backtest quality
  + 25% walk-forward stability
  + 20% universe robustness
  + 15% risk quality
  + 10% data quality
  +  5% Market Memory theme confidence
```

The score should not mean "trade this." It should mean:

```text
This is a better candidate for more research.
```

## Next implementation patch

Recommended next patch:

```text
v24.9.0 Research Loop Orchestrator
```

Scope:

- Add a read-only/simulation-only orchestrator service.
- Pull the current theme and suggested symbols from Market Memory.
- Build a research queue.
- Run only local backtest/walk-forward/universe functions that already exist.
- Capture all outputs through Artifact Writer and Quant Schema.
- Write a loop report to managed artifacts.
- Show loop runs in Quant Dashboard.

No broker integration.
No live orders.
No credential changes.
