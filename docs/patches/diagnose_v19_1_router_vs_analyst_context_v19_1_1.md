# diagnose_v19_1_router_vs_analyst_context_v19_1_1

## Purpose

Read-only diagnostic for the case where the visible Research Brief contains FRED rows, but the Analyst says no FRED rows were included.

This checks whether the current system is reading:

1. the visible Research Brief rows,
2. the new v19.1 router evidence packet,
3. the older Research Analyst combined context,
4. the older SEC/FRED/BLS tail guards.

## Why this matters

The latest result showed two mismatch signs:

```text
Visible brief contains FRED rows:
- CPIAUCSL fred-data
- CPILFESL fred-data
- FRED metadata links

Analyst answer:
- says no FRED rows were included
```

Also:

```text
Visible brief had only 4 SEC rows,
but Analyst answered with 6 SEC rows.
```

That suggests the Analyst may still be reading an older forced context/tail guard instead of the current visible brief/router packet.

## Test tools

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\diagnose_v19_1_router_vs_analyst_context_v19_1_1.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader"
```

## Safety

- Read-only.
- No app files are changed.
- No backups are created.
- No broker/order/live-trading behavior is added.
