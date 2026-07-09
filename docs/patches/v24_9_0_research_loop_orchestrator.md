# v24.9.0 — Research Loop Orchestrator

## Purpose

Add the first simulation-only strategy/backtest improvement loop.

This connects the project directionally:

```text
Market Memory theme/symbols
  -> strategy candidates
  -> proxy backtest evaluation
  -> walk-forward proxy validation
  -> universe robustness scoring
  -> Quant Schema rows
  -> Markdown/JSON loop report
  -> Market Memory feedback note
```

This version is intentionally conservative. It creates a deterministic local research loop that stores results in the typed Quant Schema and produces reports. It does not place trades and does not connect to brokers.

## Recommended defaults

```text
theme = AI infrastructure semiconductors
symbols = AMD,NVDA,SMH
max_candidates = 10
max_loops = 1
min_trades = 10
max_drawdown_limit = -0.20
min_sharpe = 0.25
backend = sqlite
mode = simulation_only
```

## Adds

- `Live/services/research_loop/__init__.py`
- `Live/services/research_loop/models.py`
- `Live/services/research_loop/strategy_candidate_generator.py`
- `Live/services/research_loop/scoring.py`
- `Live/services/research_loop/memory_feedback.py`
- `Live/services/research_loop/orchestrator.py`
- `Live/services/research_loop/self_test_v24_9_0.py`
- `docs/research_loop_orchestrator.md`
- `docs/patches/v24_9_0_research_loop_orchestrator.md`

## How to run

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.research_loop.orchestrator `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --theme "AI infrastructure semiconductors" `
  --symbols "AMD,NVDA,SMH" `
  --max-candidates 10 `
  --max-loops 1 `
  --backend sqlite
```

Then refresh the Quant Dashboard.

## Safety

- Simulation/research only
- No broker calls
- No live trading
- No order placement
- No credentials written
- No file moves or deletes
- No Data Library changes
- No main app layout changes
