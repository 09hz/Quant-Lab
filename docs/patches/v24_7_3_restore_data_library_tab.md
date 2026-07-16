# v24.7.3 — Restore Data Library Tab

## Purpose

Restore the Data Library tab after the v24.7 Quant Dashboard UI insertion caused the Data tab to fail at runtime.

## What this patch does

This is a safe rollback/disable for the v24.7 UI integration only.

It keeps the Quant Dashboard service files on disk for later repair, but removes the dashboard from the Data Library layout and removes its Dash callback registration so the original Data Library tab can load again.

## Patches

- `Live/ui/data_library_ui.py`
- `Live/app.py`

## Removes

- v24.7 Quant Dashboard import block from `data_library_ui.py`
- v24.7 Quant Dashboard safe wrapper block from `data_library_ui.py`
- leftover `build_quant_dashboard_panel(...)` insertion lines
- v24.7 Quant Dashboard callback registration block from `app.py`

## Keeps

The following files are kept for later reuse:

- `Live/services/data_catalog/quant_dashboard_queries.py`
- `Live/services/data_catalog/quant_dashboard_ui.py`
- `Live/services/data_catalog/quant_dashboard_callbacks.py`

## Safety

Read-only repair.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
