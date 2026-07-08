# Quant Research Schema

The quant research schema adds typed tables for faster research queries and dashboards.

## Tables

- `symbols`
- `experiment_runs`
- `strategy_runs`
- `backtest_runs`
- `walk_forward_runs`
- `universe_runs`
- `feature_snapshots`
- `risk_snapshots`
- `model_candidates`
- `data_quality_events`

## Migrate SQLite fallback

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.quant_schema.status `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --backend sqlite `
  --migrate
```

## Migrate PostgreSQL

Use the Data Library browser setup flow or set environment variables, then run:

```powershell
& $PY -m services.quant_schema.status `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --backend postgres `
  --migrate
```

## Example query

```sql
SELECT symbol, strategy_name, sharpe, max_drawdown, win_rate, created_at
FROM algotrader.backtest_runs
WHERE symbol = 'NVDA'
ORDER BY sharpe DESC
LIMIT 25;
```

## Repository helpers

```python
from services.quant_schema.repository import insert_backtest_run

insert_backtest_run(
    db,
    symbol="NVDA",
    strategy_name="DemoMomentum",
    sharpe=1.4,
    max_drawdown=-0.08,
    win_rate=0.56,
    status="PASS",
)
```

## Safety

Research/simulation only. No broker calls, no order placement, and no live trading.
