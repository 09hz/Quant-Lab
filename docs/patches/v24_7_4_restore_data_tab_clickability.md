# v24.7.4 — Restore Data Tab Clickability

## Purpose

Fix the Data Library tab after v24.7 dashboard integration made the Data tab unclickable or non-responsive.

## What this patch does

This is a defensive UI restore patch.

It:

1. Removes all v24.7 Quant Dashboard layout/callback integration fragments from `data_library_ui.py` and `app.py`.
2. Leaves the standalone Quant Dashboard service files on disk for later repair.
3. Removes/neutralizes any damaged Quant Dashboard import/wrapper blocks.
4. Ensures Data Library UI and `app.py` compile.
5. Adds a small CSS rescue file to force top-level Dash tabs to remain clickable.
6. Adds a self-test that imports the Data Library UI and verifies the builder still returns a component.

## Files patched

- `Live/ui/data_library_ui.py`
- `Live/app.py`

## Files added

- `Live/assets/v24_7_4_tab_clickability_rescue.css`
- `Live/services/data_catalog/data_tab_clickability_self_test_v24_7_4.py`
- `docs/patches/v24_7_4_restore_data_tab_clickability.md`

## Safety

Read-only UI repair.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
