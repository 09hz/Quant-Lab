# Patch 18 — Strategy Context Export Framework

This patch sets up the framework for exporting Strategy Lab and Backtest state.

## Added

- `Live/services/ai/strategy_context.py`
- `Live/scripts/check_strategy_context_export.py`
- `Live/docs/patches/strategy_context_framework_patch_18.md`

## Purpose

The next UI patch can use this service to:

- build a sanitized snapshot of the strategy editor
- include selected symbol/timeframe/date range
- include backtest inputs such as initial cash and quantity
- include last backtest summary when available
- export context as JSON
- export context as Markdown
- attach selected context to the advisory AI panel

## Safety

This framework is advisory-only and export-only.

It does not:

- place orders
- access broker accounts
- call external tools
- expose API keys
- grant AI automatic access to every tab

Context should be attached to AI only after the user chooses to attach/export it.

## Test

```powershell
python -m py_compile .\Live\services\ai\strategy_context.py
python -m py_compile .\Live\scripts\check_strategy_context_export.py
python .\Live\scripts\check_strategy_context_export.py
```

## Expected output

The script writes demo files under:

```text
strategy_context_exports/
```

These exported scratch files should remain local and should not be committed.
