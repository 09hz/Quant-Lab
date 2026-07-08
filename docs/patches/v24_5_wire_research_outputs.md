# v24.5 — Wire Research Outputs into Artifact Writer + Quant Schema

## Purpose

Start wiring real research outputs into the new infrastructure.

This patch adds a safe capture layer for:

- Backtest results
- Auto Lab results
- Walk-forward results
- Universe runs
- Strategy results
- Generic research outputs

The capture layer writes outputs through the v24.2 Artifact Writer and promotes key metrics into the v24.4 typed Quant Research Schema.

## What this patch adds

- `Live/services/quant_schema/result_capture.py`
- `Live/services/quant_schema/promote_artifacts.py`
- `Live/services/quant_schema/runtime_wiring.py`
- `Live/services/quant_schema/self_test_v24_5.py`
- `docs/quant_output_wiring.md`
- `docs/patches/v24_5_wire_research_outputs.md`

## App wiring

The patch adds a guarded block to `Live/app.py`:

```python
from services.quant_schema.runtime_wiring import install_quant_output_hooks
install_quant_output_hooks()
```

The hook installer is defensive:

- It does not crash Dash startup.
- It only wraps recognizable research methods.
- Capture errors are swallowed and reported as warnings.
- Original method returns are preserved.
- It can be disabled with `ALGOTRADER_ENABLE_QUANT_WIRING=0`.

## Database behavior

If PostgreSQL credentials are available in the current process, typed rows are written to PostgreSQL.

If PostgreSQL credentials are not available, the capture layer falls back to SQLite so the research output is still structured locally.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
