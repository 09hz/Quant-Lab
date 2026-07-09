# v24.7.2 — Data Library UI Safe Wrapper Repair

## Purpose

Fix the second v24.7 Data Library UI syntax failure:

```text
SyntaxError: expected 'except' or 'finally' block
```

## Cause

The v24.7/v24.7.1 insertion placed a top-level Quant Dashboard import block inside or near an existing `try:` block in `Live/ui/data_library_ui.py`.

## Fix

This repair avoids fragile inline layout insertion.

It:

1. Removes malformed v24.7 Quant Dashboard import/panel lines from `data_library_ui.py`.
2. Appends a safe wrapper around the existing Data Library builder function.
3. The wrapper appends the Quant Dashboard panel to the returned layout at runtime.
4. Ensures the callback registration block exists in `app.py`.
5. Compiles the repaired files.
6. Optionally runs v24.7 self-test and a new v24.7.2 UI wrapper self-test.

## Safety

Read-only dashboard repair.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
