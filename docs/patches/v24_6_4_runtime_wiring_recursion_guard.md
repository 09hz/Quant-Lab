# v24.6.4 — Runtime Wiring Recursion Guard + App Load Fix

## Purpose

Fix app startup/loading problems caused by recursive quant capture hooks.

## Symptom

The app prints many lines like:

```text
[v24.5 quant wiring] capture skipped: RecursionError: maximum recursion depth exceeded
```

and the Dash UI may stop loading or become extremely slow.

## Cause

The broad v24.5 runtime hook layer can wrap too many functions during app import. Some wrapped functions return complex objects, Dash objects, callbacks, or nested run objects. Capturing those during startup can recursively call capture logic again or recurse while trying to serialize complex objects.

## Fix

1. Disable the broad v24.5 runtime hook layer by default.
2. Keep direct producer wiring available separately.
3. Add a re-entrant capture guard so capture cannot recursively capture itself.
4. Add recursion-safe JSON serialization for nested/cyclic objects.
5. Add a small self-test for this guard behavior.

## Runtime controls

Broad v24.5 hooks are now OFF unless explicitly enabled:

```powershell
$env:ALGOTRADER_ENABLE_BROAD_RUNTIME_HOOKS = "1"
```

Emergency disable all quant wiring:

```powershell
$env:ALGOTRADER_ENABLE_QUANT_WIRING = "0"
```

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
