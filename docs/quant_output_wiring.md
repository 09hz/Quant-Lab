# Quant Output Wiring

v24.5 starts wiring real research outputs into the Artifact Writer and typed Quant Research Schema.

## Capture helpers

```python
from services.quant_schema.result_capture import capture_backtest_result

capture_backtest_result(
    {
        "symbol": "NVDA",
        "strategy_name": "DemoMomentum",
        "sharpe": 1.5,
        "max_drawdown": -0.07,
        "win_rate": 0.58,
    },
    context={"module": "backtest", "method": "run_backtest"},
)
```

## Promote existing managed artifacts

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"

& $PY -m services.quant_schema.promote_artifacts `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --backend sqlite `
  --dry-run `
  --limit 25
```

## Promote to PostgreSQL

Set PostgreSQL env vars first:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"
.\scripts\set_postgres_env.ps1
cd ".\Live"

& $PY -m services.quant_schema.promote_artifacts `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --backend postgres `
  --limit 100
```

## Runtime hooks

The patch adds a guarded app startup block that calls:

```python
install_quant_output_hooks()
```

Disable with:

```powershell
$env:ALGOTRADER_ENABLE_QUANT_WIRING = "0"
```

## Safety

Research/simulation only. No broker calls, no order placement, no live trading.
