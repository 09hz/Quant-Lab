# v24.7 — Data Library Quant Dashboard

## Purpose

Add a read-only Quant Research Dashboard inside the Data Library tab.

This dashboard reads the typed v24.4 Quant Research Schema tables created by the wiring work in v24.5/v24.6.

## Adds

- `Live/services/data_catalog/quant_dashboard_queries.py`
- `Live/services/data_catalog/quant_dashboard_ui.py`
- `Live/services/data_catalog/quant_dashboard_callbacks.py`
- `Live/services/data_catalog/quant_dashboard_self_test_v24_7.py`
- `docs/quant_dashboard.md`
- `docs/patches/v24_7_data_library_quant_dashboard.md`

## Patches

- `Live/ui/data_library_ui.py`
- `Live/app.py`
- `Live/assets/data_library.css`

## Dashboard sections

- Quant table counts
- Recent experiment runs
- Recent strategy runs
- Best backtests
- Walk-forward validation runs
- Universe runs
- Data quality events

## Backend support

The dashboard supports:

- SQLite fallback
- PostgreSQL when environment credentials are available

v24.7 is read-only. It does not migrate, insert, update, delete, move files, or place trades.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
