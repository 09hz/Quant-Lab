# v24.7.1 — Data Library Quant Dashboard UI Indentation Fix

## Purpose

Fix the v24.7 patch failure:

```text
IndentationError: unexpected indent (data_library_ui.py, line 204)
```

## Cause

The first v24.7 patch inserted the Quant Dashboard panel expression into `Live/ui/data_library_ui.py`, but the insertion landed with invalid indentation in the existing layout structure.

## Fix

This repair script:

1. Removes any malformed v24.7 panel-expression lines.
2. Ensures the Quant Dashboard UI import block exists once.
3. Reinserts the Quant Dashboard panel next to the PostgreSQL/Data Library controls using the surrounding file's indentation.
4. Re-registers the callback block in `Live/app.py` if missing.
5. Compiles patched files.
6. Optionally runs the v24.7 self-test.

## Safety

Read-only dashboard repair.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
